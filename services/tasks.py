import queue
import threading
import time
import os
from sqlalchemy.orm import Session
from database import get_db
import models
from services.logger import get_logger

logger = get_logger("tasks")

# Global Queue for AI Tasks
analysis_queue = queue.Queue()

def worker():
    """
    Background worker thread that consumes events from the queue and runs AI analysis.
    This ensures uploads are fast (just IO) while AI runs sequentially in background.
    """
    logger.info("⚙️ Background Worker: Ready (Optimization)")
    while True:
        try:
            event_id = analysis_queue.get()
            if event_id is None: # Sentinel to stop
                break
            
            # Artificial small delay to let DB commit fully propagate if needed
            # (though queue put happens after commit usually)
            time.sleep(0.5)
            
            process_ai_for_event(event_id)
            
        except Exception as e:
            logger.error(f"Worker Thread Error: {e}")
        finally:
            analysis_queue.task_done()

def start_worker():
    t = threading.Thread(target=worker, daemon=True)
    t.start()

def enqueue_event(event_id: int):
    logger.info(f"Queued Event {event_id} for AI analysis")
    analysis_queue.put(event_id)

def process_ai_for_event(event_id: int):
    """
    Full AI Pipeline for a single event:
    1. Face Recognition
    2. Tag Analysis
    3. Caption Generation (BLIP)
    4. Context Enrichment (Location/Weather)
    """
    db = next(get_db())
    try:
    # Lazy imports to minimize startup time
        try:
            from services.vision import vision_service
            from services.faces import process_faces
            from services.context import context_service
            from services.rag import memory_vector_store
        except ImportError as e:
            logger.warning(f"Partial Import Error in Worker: {e}")
            vision_service = None
            process_faces = None
            context_service = None
            memory_vector_store = None
            
            try: from services.vision import vision_service
            except ImportError: pass
            
            try: from services.faces import process_faces
            except ImportError: pass
            
            try: from services.context import context_service
            except ImportError: pass
            
            try: from services.rag import memory_vector_store
            except ImportError: pass

        event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
        if not event:
            logger.warning(f"Event {event_id} not found in worker.")
            return

        file_path = None
        if event.image_url and event.image_url.startswith('/static/uploads/'):
             filename = event.image_url.split('/')[-1]
             file_path = os.path.join("static/uploads", filename)
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File not found for Event {event_id}")
            return

        logger.info(f"Processing Event {event_id} ({event.media_type})...")
        found_names = []

        # 1. Face Recognition
        if process_faces and event.media_type == "photo":
            try:
                found_names = process_faces(event.id)
                logger.info(f"Faces: {found_names}")
            except Exception as e:
                logger.error(f"Face error: {e}")

        # 2 & 3. Scene Analysis (Tags + Caption) - Optimized Single Pass
        if vision_service and event.media_type == "photo":
            try:
                analysis_result = vision_service.analyze_scene(file_path, names=found_names)
                
                tags = analysis_result.get("tags", [])
                caption = analysis_result.get("summary")
                mood = analysis_result.get("mood")
                
                # Update Tags
                if tags:
                    existing_tags = [t.strip() for t in event.tags.split(',')] if event.tags else []
                    all_tags = list(set(existing_tags + tags))
                    event.tags = ",".join(all_tags)
                    logger.info(f"Tags: {tags}")
                
                # Update Caption
                if caption:
                    event.summary = caption
                    logger.info(f"Caption: {caption}")
                
                # Update Mood (if model supports it)
                if mood:
                     event.mood = mood
                     logger.info(f"Mood: {mood}")

                db.commit()
            except Exception as e:
                logger.error(f"Scene Analysis error: {e}")

        # 4. Context (Location/Weather)
        if context_service and event.latitude and event.longitude:
            try:
                logger.info("Fetching Context...")
                context_service.enrich_event(event.id)
            except Exception as e:
                logger.error(f"Context error: {e}")
                
        # 5. RAG Indexing
        if memory_vector_store:
             try:
                 logger.info("Indexing to ChromaDB...")
                 memory_vector_store.add_events([event])
             except Exception as e:
                 logger.error(f"RAG Indexing error: {e}")

        # 6. Photo Stacking (Grouping)
        try:
            from services.grouping import grouping_service
            logger.info("Running Photo Stacking Grouping...")
            grouping_service.process_event(event_id)
        except ImportError:
            pass
        except Exception as e:
             logger.error(f"Grouping error: {e}")

        logger.info(f"Finished AI Analysis for Event {event_id}")

    except Exception as e:
        logger.error(f"Fatal error in process_ai_for_event: {e}")
    finally:
        db.close()

# Keep legacy function if imported elsewhere, or redirect
def analyze_image_task(event_id: int):
    enqueue_event(event_id)

def process_caption_update(event_id: int):
    """
    Updates ONLY the caption (summary) for an event, using existing faces.
    Used when a person is renamed, to reflect the new name in the caption without re-running expensive face detection.
    """
    logger.info(f"Updating Caption for Event {event_id}...")
    db = next(get_db())
    try:
        from services.vision import vision_service
        from services.rag import memory_vector_store
        
        event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
        if not event or not event.image_url:
            return

        file_path = event.image_url.lstrip("/")
        if not os.path.exists(file_path):
             file_path = f"static/uploads/{event.image_url.split('/')[-1]}"
        
        if not os.path.exists(file_path):
            return

        # 1. Get Existing Names
        found_names = []
        if event.faces:
            for f in event.faces:
                if f.person:
                    found_names.append(f.person.name)
        found_names = list(set(found_names))
        
        # 2. Generate Caption
        if vision_service:
            try:
                caption = vision_service.generate_caption(file_path, names=found_names)
                if caption:
                    event.summary = caption
                    db.commit()
                    logger.info(f"Updated Caption: {caption}")
            except Exception as e:
                logger.error(f"Caption update error: {e}")

        # 3. Update RAG Index
        if memory_vector_store:
             try:
                 memory_vector_store.add_events([event])
             except Exception as e:
                 logger.error(f"RAG Indexing error: {e}")

    except Exception as e:
        logger.error(f"Error in process_caption_update: {e}")
    finally:
        db.close()
