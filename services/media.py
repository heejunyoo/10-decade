import os
import shutil
import hashlib
import imagehash
from datetime import datetime
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()
from database import get_db
import models
from utils.image import get_gps_from_image, extract_date_from_image, extract_timestamp_from_image
from services.tasks import analyze_image_task
try:
    from services.faces import process_faces
except ImportError:
    process_faces = None
try:
    from services.analyzer import analyzer
except ImportError:
    analyzer = None

def calculate_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_exact_duplicate(db, file_hash: str) -> bool:
    return db.query(models.TimelineEvent).filter(models.TimelineEvent.file_hash == file_hash).first() is not None

def check_visual_duplicate(db, image: Image.Image) -> tuple[bool, str | None]:
    """Returns (is_duplicate, phash_str)"""
    try:
        p_hash = imagehash.phash(image)
        p_hash_str = str(p_hash)
        
        # Check against DB
        existing_hashes = db.query(models.TimelineEvent.phash).filter(models.TimelineEvent.phash != None).all()
        for (db_phash,) in existing_hashes:
            if db_phash:
                dist = imagehash.hex_to_hash(p_hash_str) - imagehash.hex_to_hash(db_phash)
                if dist < 4:
                    return True, p_hash_str
        return False, p_hash_str
    except Exception as e:
        print(f"⚠️ Error calculating pHash: {e}")
        return False, None

def process_upload_task(temp_file_path: str, original_filename: str, metadata: dict):
    """
    Process an uploaded file from temp storage.
    """
    print(f"⚙️ [Background] Processing {original_filename}...")
    
    db = next(get_db())
    try:
        upload_dir = "static/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Detect file type
        file_ext = os.path.splitext(original_filename)[1].lower()
        is_video = file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        
        # 1. Calculate Hash (SHA256)
        file_hash = calculate_file_hash(temp_file_path)
        
        # 2. Exact Match Check
        if check_exact_duplicate(db, file_hash):
            print(f"⚠️ [Duplicate] {original_filename} (SHA256 match)")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return

        final_filename = f"IMG_{int(datetime.now().timestamp())}_{original_filename}"
        final_filename = "".join([c for c in final_filename if c.isalpha() or c.isdigit() or c in '._-'])
        
        # Perceptual Hash (Images only)
        p_hash_str = None
        lat, lon = None, None
        thumbnail_path = None
        
        if is_video:
            final_path = os.path.join(upload_dir, final_filename)
            shutil.move(temp_file_path, final_path)
            
            # Generate Thumbnail
            try:
                import cv2
                thumb_name = f"thumb_{os.path.splitext(final_filename)[0]}.jpg"
                thumb_full_path = os.path.join(upload_dir, thumb_name)
                cap = cv2.VideoCapture(final_path)
                ret, frame = cap.read()
                if ret:
                    cv2.imwrite(thumb_full_path, frame)
                    thumbnail_path = f"/static/uploads/{thumb_name}"
                cap.release()
            except Exception as e:
                print(f"❌ Video thumbnail error: {e}")
                
        else:
            # Image Processing
            # We open the image ONCE for pHash, Metadata, and Optimization
            try:
                with Image.open(temp_file_path) as image:
                    # 3. Visual Duplicate Check
                    is_dup, p_hash_str = check_visual_duplicate(db, image)
                    if is_dup:
                        print(f"⚠️ [Duplicate] {original_filename} (Visual match)")
                        return # Helper handles temp file removal?? No, we need to do it here. 
                        # Actually wait, context manager closes file. We can remove it after.
                
                if is_dup:
                     if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                     return

                # Re-open for modification (Pillow context manager closes it)
                # Or we can just keep it open?
                # The issue is `image.save` might need to be the last step. 
                # Let's simple re-open to be safe or structure differently. 
                # Actually, check_visual_duplicate doesn't modify. 
                
                with Image.open(temp_file_path) as image:
                     # Metadata
                    lat, lon = get_gps_from_image(image)
                    date_found = extract_date_from_image(image)
                    timestamp_found = extract_timestamp_from_image(image)

                    if date_found:
                        if metadata.get("date") and metadata.get("date") != date_found:
                            print(f"ℹ️  Example: Overriding form date with EXIF: {date_found}")
                        metadata['date'] = date_found
                    
                    # Orientation
                    image = ImageOps.exif_transpose(image)
                    
                    # Resize
                    max_width = 1920
                    if image.width > max_width:
                        ratio = max_width / float(image.width)
                        new_height = int((float(image.height) * float(ratio)))
                        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
                        
                    if image.mode == "P":
                        image = image.convert("RGB")
                        
                    # Save as WebP
                    base, _ = os.path.splitext(final_filename)
                    final_filename = f"{base}.webp"
                    final_path = os.path.join(upload_dir, final_filename)
                    
                    image.save(final_path, "WEBP", quality=80)
                    thumbnail_path = None # No separate thumb for images, we use the webp
                    
            except Exception as e:
                print(f"❌ Image processing error: {e}")
                # Fallback: just move the file
                final_path = os.path.join(upload_dir, final_filename)
                shutil.move(temp_file_path, final_path)
                timestamp_found = None

        # Cleanup
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # 5. Determine Date
        event_date = metadata.get("date")
        if not event_date:
            event_date = datetime.now().strftime("%Y-%m-%d")

        # 6. DB Insert
        new_event = models.TimelineEvent(
            title=metadata.get("title"),
            date=event_date,
            capture_time=timestamp_found,
            description=metadata.get("description"),
            image_url=f"/static/uploads/{final_filename}",
            file_hash=file_hash,
            tags=metadata.get("tags"),
            media_type="video" if is_video else "photo",
            thumbnail_url=thumbnail_path,
            latitude=lat,
            longitude=lon,
            phash=p_hash_str,
            summary=metadata.get("summary")
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        print(f"✅ [Success] Event {new_event.id} created.")
        
        # 7. AI Analysis (Async Trigger)
        if new_event.media_type == "photo":
            import services.tasks
            services.tasks.enqueue_event(new_event.id)
            
    except Exception as e:
        print(f"❌ Fatal error in upload task: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    finally:
        db.close()

def regenerate_captions_for_person(person_id: int):
    """
    Refreshes AI captions for all photos containing a specific person.
    Triggered when a person is named or renamed.
    """
    print(f"🔄 Regenerating captions for Person {person_id}...")
    db = next(get_db())
    try:
        person = db.query(models.Person).filter(models.Person.id == person_id).first()
        if not person:
            return

        # Get all events with this person
        events_to_process = set()
        for face in person.faces:
            if face.event and face.event.media_type == "photo":
                events_to_process.add(face.event)
        
        print(f"  Found {len(events_to_process)} photos to update.")
        
        # Enqueue re-analysis
        # Enqueue re-analysis (Caption Only)
        from services.tasks import process_caption_update
        for event in events_to_process:
            # Run directly in this background thread (FastAPI BackgroundTasks thread)
            # Since analyzer is thread-safe now, this is fine.
            process_caption_update(event.id)
        
        print(f"✅ Updated captions for {len(events_to_process)} events.")
            
    except Exception as e:
        print(f"❌ Error in regenerate_captions_for_person: {e}")
    finally:
        db.close()
