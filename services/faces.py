
import cv2
import numpy as np
import pickle
import json
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
import contextlib
import sys

# Silence ONNXRuntime and InsightFace Noise
os.environ["ORT_LOGGING_LEVEL"] = "3" 
import logging

# InsightFace Imports
import insightface
# Suppress InsightFace internal logging
logging.getLogger("insightface").setLevel(logging.WARNING)
from insightface.app import FaceAnalysis

from starlette.concurrency import run_in_threadpool
from database import get_db, SessionLocal
import models
from services.logger import get_logger
from services.config import UPLOAD_DIR, FACE_SIMILARITY_THRESHOLD, MIN_FACE_RATIO, FACE_DETECTION_THRESHOLD

logger = get_logger("faces")

# InsightFace Constants
# Threshold now loaded from config
MATCH_THRESHOLD = FACE_SIMILARITY_THRESHOLD 

STATUS_FILE = "indexing_status.json"

class FaceIdentifier:
    def __init__(self):
        # Initialize InsightFace App (Buffalo_L is light and accurate)
        # providers=['CPUExecutionProvider'] force CPU to avoid CUDA dependency hell issues if not set up
        # If user has GPU, they can change this, but CPU is safer for general consumption.
        try:
            # Context manager to suppress stdout/stderr from C++ libs (ONNXRuntime/InsightFace)
            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                    self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
                    self.app.prepare(ctx_id=0, det_size=(640, 640))
            
            logger.info("✅ InsightFace: Ready (Buffalo_L)")
        except Exception as e:
            logger.error(f"❌ Failed to load InsightFace: {e}")
            self.app = None
        except Exception as e:
            logger.error(f"❌ Failed to load InsightFace: {e}")
            self.app = None

    def detect_faces(self, image_path: str):
         # Legacy Sync Wrapper
         return self._detect_faces_sync(image_path)
         
    async def detect_faces_async(self, image_path: str):
        """
        Async wrapper for non-blocking UI calls.
        """
        return await run_in_threadpool(self._detect_faces_sync, image_path)

    def _detect_faces_sync(self, image_path: str):
        """
        InsightFace Detection Pipeline (Blocking/CPU-Bound):
        1. Load Image (cv2)
        2. InsightFace Inference (Detect + Align + Embed)
        3. Return 512d embeddings
        """
        if not self.app:
            logger.error("InsightFace app not initialized.")
            return []

        try:
            # 1. Load Image
            if not os.path.exists(image_path):
                logger.error(f"Image not found: {image_path}")
                return []

            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image with cv2: {image_path}")
                return []
            
            # InsightFace works with BGR (OpenCV default), no conversion needed generally,
            # but documentation usually implies standard cv2 image is fine.
            
            # 2. Inference
            # app.get() returns list of Face objects with embedding, bbox, kps, etc.
            faces = self.app.get(img)
            
            final_results = []
            
            for face in faces:
                # face.bbox is [x1, y1, x2, y2]
                # face.embedding is 512d numpy array
                
                # Convert bbox to int list
                bbox = face.bbox.astype(int).tolist()
                
                # Filter tiny faces (Background Noise)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                
                # Check absolute size (legacy)
                if w < 40 or h < 40:
                    continue
                    
                # 1. Size Ratio Filter
                img_h, img_w = img.shape[:2]
                face_area = w * h
                img_area = img_w * img_h
                
                if (face_area / img_area) < MIN_FACE_RATIO:
                    # logger.debug(f"Skipping tiny face: Ratio {face_area/img_area:.4f} < {MIN_FACE_RATIO}")
                    continue

                # 2. Detection Score Filter
                if face.det_score < FACE_DETECTION_THRESHOLD:
                    # logger.debug(f"Skipping low confidence face: {face.det_score:.2f} < {FACE_DETECTION_THRESHOLD}")
                    continue

                # Dlib format was [top, right, bottom, left]
                # We should standarize. But wait, our API likely consumes this.
                # Let's stick to a standard [top, right, bottom, left] for compatibility 
                # OR just store what we have and ensure consistency.
                # bbox is [left, top, right, bottom] in InsightFace.
                # Let's convert to [top, right, bottom, left] to match Dlib legacy format if any FE uses it?
                # Actually, let's store [top, right, bottom, left] to minimize friction.
                
                # InsightFace: x1(left), y1(top), x2(right), y2(bottom)
                top = bbox[1]
                right = bbox[2]
                bottom = bbox[3]
                left = bbox[0]
                
                compat_bbox = [top, right, bottom, left]

                final_results.append({
                    "bbox": compat_bbox, 
                    "embedding": face.embedding.tolist(), # 512d list
                    "name": "Unknown",
                    "det_score": float(face.det_score)
                })
            
            return final_results

        except Exception as e:
            logger.error(f"Error in detect_faces: {e}")
            import traceback
            traceback.print_exc()
            return []

# Singleton
face_identifier = FaceIdentifier()

def get_indexing_status():
    """
    Reads the status file to check if re-indexing is in progress.
    Returns: dict or None
    """
    if not os.path.exists(STATUS_FILE):
        return None
        
    try:
        with open(STATUS_FILE, "r") as f:
            data = json.load(f)
            # Check if stale (e.g. process died) - optional but simple check
            if not data.get("is_indexing", False):
                return None
            return data
    except:
        return None

def find_matching_person(db: Session, encoding: list) -> models.Person:
    """
    Find match using Cosine Similarity (InsightFace standard).
    Target: Similarity > MATCH_THRESHOLD (0.5)
    """
    known_faces = db.query(models.Face).all()
    if not known_faces:
        return None

    best_match_person = None
    max_sim = -1.0 # Start low (range -1 to 1)
    
    target_encoding = np.array(encoding)
    target_norm = np.linalg.norm(target_encoding)
    
    for face in known_faces:
        if face.encoding and face.person_id:
            try:
                known_encoding = pickle.loads(face.encoding)
                
                # InsightFace embeddings are 512D
                if len(known_encoding) != 512:
                    continue
                
                # Cosine Similarity = (A . B) / (||A|| * ||B||)
                # InsightFace embeddings are usually normalized, but let's be safe
                known_norm = np.linalg.norm(known_encoding)
                
                sim = np.dot(known_encoding, target_encoding) / (known_norm * target_norm)
                
                if sim > max_sim:
                    max_sim = sim
                    best_match_person = face.person
            except:
                continue
    
    if max_sim > MATCH_THRESHOLD:
        logger.info(f"   🔹 Match found! Sim: {max_sim:.4f} > {MATCH_THRESHOLD}")
        return best_match_person
    else:
        # logger.info(f"   🔸 No match. Best Sim: {max_sim:.4f}")
        return None

def process_faces(event_id: int):
    """
    Main entry point for Tasks.py
    """
    logger.info(f"👤 Processing faces for Event {event_id} (InsightFace)...")
    db = SessionLocal()
    try:
        event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
        if not event or not event.image_url or event.media_type != "photo":
            return []
            
        file_path = event.image_url.lstrip("/")
        
        # 1. Check Absolute Path first (if stored as such)
        if not os.path.exists(file_path):
             # 2. Try Standard Upload Dir
             possible_path = UPLOAD_DIR / os.path.basename(event.image_url)
             if possible_path.exists():
                 file_path = str(possible_path)
             else:
                 logger.warning(f"Image file missing: {event.image_url}")
                 return []

        # Clear existing faces for this event (Idempotency)
        db.query(models.Face).filter(models.Face.event_id == event_id).delete()
        db.commit()

        # Load Image for Cropping later
        img = cv2.imread(file_path)
        if img is None:
             logger.error(f"Failed to load image for processing: {file_path}")
             return []

        # DETECT (Sync call is fine in background worker)
        results = face_identifier._detect_faces_sync(file_path)
        logger.info(f"   Found {len(results)} faces.")
        
        found_names = []
        
        for res in results:
            encoding = res["embedding"]
            bbox = res["bbox"]
            
            # IDENTIFY
            person = find_matching_person(db, encoding)
            
            if not person:
                # Create New Person
                count = db.query(models.Person).count()
                person = models.Person(name=f"Unknown Person #{count + 1}")
                db.add(person)
                db.commit()
                db.refresh(person)
                logger.info(f"   ✨ Created new person: {person.name}")
            
            # 3. Emotion Analysis (DeepFace) - Local Hybrid Logic
            # InsightFace detected face -> Crop -> DeepFace Analysis
            dominant_emotion = None
            try:
                # bbox is [top, right, bottom, left] from our conversion earlier
                # But InsightFace returns [x1, y1, x2, y2] originally, which we converted.
                # Let's verify what `res["bbox"]` holds.
                # Code above: compat_bbox = [top, right, bottom, left]. Yes.
                
                # Crop logic
                top, right, bottom, left = bbox
                
                # Ensure valid crop (bound within image)
                h, w, _ = img.shape
                top = max(0, top)
                left = max(0, left)
                bottom = min(h, bottom)
                right = min(w, right)
                
                if (bottom - top) > 20 and (right - left) > 20: # Min 20x20
                   face_crop = img[top:bottom, left:right]
                   
                   # DeepFace expects BGR (cv2 default) or RGB.
                   # It handles standard numpy arrays.
                   from deepface import DeepFace
                   
                   # Optimize: Only load Emotion model, skip others
                   # detector_backend='skip' ensures it just processes the crop
                   analysis = DeepFace.analyze(
                       face_crop, 
                       actions=['emotion'], 
                       enforce_detection=False, 
                       detector_backend='skip', 
                       silent=True
                   )
                   
                   if isinstance(analysis, list):
                       analysis = analysis[0]
                       
                   dominant_emotion = analysis.get('dominant_emotion')
                   # logger.info(f"   🎭 Emotion detected: {dominant_emotion}")
                   
            except ImportError:
                 logger.warning("DeepFace not installed. Skipping emotion analysis.")
            except Exception as e:
                 logger.warning(f"Emotion analysis failed: {e}")

            # Create Face Record
            serialized_encoding = pickle.dumps(np.array(encoding))
            loc_json = json.dumps(bbox)
            
            # Update Cover Photo if needed
            if not person.cover_photo:
                person.cover_photo = event.image_url
                db.add(person)
                
            new_face = models.Face(
                event_id=event.id,
                person_id=person.id,
                encoding=serialized_encoding,
                location=loc_json,
                emotion=dominant_emotion # Save Emotion
            )
            db.add(new_face)
            found_names.append(person.name)
            
        db.commit()
        return list(set(found_names))
        
    except Exception as e:
        logger.error(f"❌ Error in process_faces: {e}")
        return []
    finally:
        db.close()

def reindex_faces():
    """
    Clears all faces/people and re-tags everything using the new InsightFace logic.
    CRITICAL: This wipes all existing face data because dimension mismatch (128 -> 512).
    """
    print("⚠️  STARTING FACE RE-INDEXING (InsightFace Upgrade) ⚠️")
    
    # 1. Set Status
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump({"is_indexing": True, "progress": 0, "total": 0, "message": "Initializing Hard Reset..."}, f)
    except:
        pass

    db = SessionLocal()
    try:
        # Clear Data
        db.query(models.Face).delete()
        db.query(models.Person).delete()
        try:
             db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('faces', 'people')"))
        except:
             pass
        db.commit()
        
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.image_url != None
        ).all()
        
        total = len(events)
        print(f"🔄 Re-processing {total} events...")
        
        # Update Status
        try:
             with open(STATUS_FILE, "w") as f:
                json.dump({"is_indexing": True, "progress": 0, "total": total, "message": "Optimizing InsightFace..."}, f)
        except: pass

        for i, event in enumerate(events):
            process_faces(event.id)
            if i % 5 == 0:
                 # Update Status File periodically
                 try:
                    with open(STATUS_FILE, "w") as f:
                        json.dump({
                            "is_indexing": True, 
                            "progress": i, 
                            "total": total, 
                            "message": f"Processing {i}/{total}"
                        }, f)
                 except: pass
                 print(f"   ...{i}/{total}")
                
        print("✅ Face Re-indexing Complete.")
    finally:
        # Clear Status
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
        db.close()


def get_unknown_clusters(threshold: float = 0.5):
    """
    Alias for get_grouped_unknown_faces with default threshold (0.5).
    """
    return get_grouped_unknown_faces(threshold)

def get_grouped_unknown_faces(threshold: float = 0.5):

    """
    Clusters 'Unknown' faces so user can label them in bulk.
    Uses Greedy Clustering (O(N^2)) with Cosine Similarity.
    """
    db = SessionLocal()
    try:
        unknown_people = db.query(models.Person).filter(models.Person.name.like("Unknown Person%")).all()
        if not unknown_people:
            return []
            
        person_ids = [p.id for p in unknown_people]
        faces = db.query(models.Face).filter(models.Face.person_id.in_(person_ids)).all()
        
        # Extract Encodings
        face_data = [] # list of (face_object, encoding_np)
        
        for f in faces:
            if not f.encoding: continue
            try:
                enc = pickle.loads(f.encoding)
                if len(enc) == 512:
                    face_data.append({"face": f, "vector": np.array(enc), "person": f.person})
            except:
                continue
                
        # Greedy Clustering
        clusters = [] # list of dict: {"centroid": vector, "faces": [face_data_item]}
        
        for item in face_data:
            vec = item["vector"]
            # Normalize vector for Cosine Similarity
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0: continue
            
            matched_cluster = None
            
            # InsightFace distance: Cosine Similarity > 0.5
            for cluster in clusters:
                centroid = cluster["centroid"]
                centroid_norm = np.linalg.norm(centroid)
                
                sim = np.dot(centroid, vec) / (centroid_norm * vec_norm)
                
                if sim > threshold:
                    matched_cluster = cluster
                    break
            
            if matched_cluster:
                matched_cluster["faces"].append(item)
                # Update centroid (simple running average)
                n = len(matched_cluster["faces"])
                matched_cluster["centroid"] = (matched_cluster["centroid"] * (n-1) + vec) / n
            else:
                # Start new cluster
                clusters.append({
                    "centroid": vec,
                    "faces": [item]
                })

        # Format Output
        results = []
        for i, cluster in enumerate(clusters):
            faces_in_cluster = cluster["faces"]
            if not faces_in_cluster: continue
            
            sample_thumbnails = []
            distinct_person_ids = set()
            
            for item in faces_in_cluster[:8]: # Grab up to 8 thumbnails for inspection
                 if item["face"].thumbnail_url:
                     sample_thumbnails.append(item["face"].thumbnail_url)
                 elif hasattr(item["face"].event, 'image_url'):
                     sample_thumbnails.append(item["face"].event.image_url) 
                     
            for item in faces_in_cluster:
                distinct_person_ids.add(item["person"].id)

            results.append({
                "cluster_id": i,
                "count": len(faces_in_cluster),
                "thumbnails": sample_thumbnails,
                "person_ids_to_merge": list(distinct_person_ids),
                "items": [
                    {
                        "face_url": item["face"].thumbnail_url or "/static/img/placeholder_face.png",
                        "original_url": item["face"].event.image_url if item["face"].event else "",
                        "date": item["face"].event.date if (item["face"].event and item["face"].event.date) else "",
                        "location": item["face"].location # [top, right, bottom, left] JSON string
                    }
                    for item in faces_in_cluster
                ]
            })
            
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    finally:
        db.close()

def batch_label_face_cluster(person_ids: list, new_name: str):
    """
    Merges multiple 'Unknown Person #X' into a single real identity 'new_name'.
    """
    db = SessionLocal()
    try:
        # Check if target person exists
        target_person = db.query(models.Person).filter(models.Person.name == new_name).first()
        if not target_person:
             target_person = models.Person(name=new_name)
             db.add(target_person)
             db.commit()
             db.refresh(target_person)
             
        # Update Faces
        db.query(models.Face).filter(models.Face.person_id.in_(person_ids))\
            .update({models.Face.person_id: target_person.id}, synchronize_session=False)
            
        # Delete the old Unknown Persons (cleanup)
        safe_ids = [pid for pid in person_ids if pid != target_person.id]
        if safe_ids:
            db.query(models.Person).filter(models.Person.id.in_(safe_ids)).delete(synchronize_session=False)
            
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Batch label failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()
