import os
import time
from huey import SqliteHuey
from services.logger import get_logger
from database import get_db
import models

logger = get_logger("tasks")

# Initialize Huey with SQLite backend
# This creates a local file 'decade_ops.db' for the queue
huey = SqliteHuey(filename='decade_ops.db')

@huey.task()
def process_ai_for_event(event_id: int):
    """
    Full AI Pipeline for a single event (Huey Task).
    This runs in a separate process managed by the Huey consumer.
    """
    logger.info(f"🚀 [Huey] Starting AI Analysis for Event {event_id}")
    
    # Database Session Management
    # Since we are in a separate process, we need a fresh DB session
    # get_db is a generator, so we need to handle it manually
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # Lazy imports to minimize startup time of the main web process
        # But for the worker process, they will be loaded once and cached
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
            
            # Helper to try importing individually
            try: from services.vision import vision_service
            except: pass
            try: from services.faces import process_faces
            except: pass
            try: from services.context import context_service
            except: pass
            try: from services.rag import memory_vector_store
            except: pass

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

        # 1.5 Smart Cropping (Use faces to improve thumbnail)
        try:
             from services.media import generate_smart_thumbnail
             logger.info("🎨 Refining Thumbnail (Smart Crop)...")
             generate_smart_thumbnail(event.id)
        except Exception as e:
             logger.error(f"Thumb error: {e}")

        # 2 & 3. Scene Analysis (Tags + Caption)
        if vision_service:
            try:
                analysis_result = None
                
                if event.media_type == "photo":
                    analysis_result = vision_service.analyze_scene(file_path, names=found_names)
                elif event.media_type == "video":
                    # Video Intelligence (Tri-Frame)
                    logger.info("🎥 Starting Video Analysis...")
                    analysis_result = vision_service.analyze_video(file_path)
                
                if analysis_result:
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
                    
                    # Update Mood
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
                 logger.info("Indexing to Vector DB...")
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

        logger.info(f"✅ Finished AI Analysis for Event {event_id}")

    except Exception as e:
        logger.error(f"Fatal error in process_ai_for_event: {e}")
    finally:
        # Close the session!
        db.close()
        # RATE LIMIT THROTTLE:
        # Gemini Free Tier is ~15 RPM.
        time.sleep(5)

def enqueue_event(event_id: int):
    """
    Enqueues the event analysis task.
    Now uses Huey to send to background process.
    """
    logger.info(f"📥 Enqueuing Event {event_id} to Huey")
    process_ai_for_event(event_id)

@huey.task()
def process_caption_update(event_id: int):
    """
    Updates ONLY the caption (summary) for an event.
    """
    logger.info(f"🚀 [Huey] Updating Caption for Event {event_id}")
    db_gen = get_db()
    db = next(db_gen)
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
                # Force Flash model dynamically for bulk updates to avoid Rate Limits
                from services.gemini import gemini_service
                flash_model = gemini_service.get_flash_model_name()
                
                caption = vision_service.generate_caption(file_path, names=found_names, model_name=flash_model)
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
        # RATE LIMIT THROTTLE:
        # Gemini Free Tier is ~15 RPM.
        # This worker process runs sequentially. To be safe, we sleep 5s after every task.
        # This limits us to max 12 tasks/min, keeping us safe.
        time.sleep(5)

# Legacy / Compatibility methods
def start_worker():
    """
    No-op: Huey handles the worker.
    But we could print a warning if this is called.
    """
    logger.info("ℹ️ Huey is enabled. Ensure you run the consumer: `huey_consumer.py services.tasks.huey`")

def reprocess_orphans():
    """
    Finds events that were uploaded but not analyzed (server crash, etc.)
    and re-enqueues them.
    Logic: (media_type='photo' OR media_type='video') AND summary IS NULL
    """
    logger.info("🚑 Checking for Orphaned Events (Incomplete Analysis)...")
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        from sqlalchemy import or_
        
        # Find Orphans (Photos OR Videos)
        orphans = db.query(models.TimelineEvent).filter(
            or_(models.TimelineEvent.media_type == "photo", models.TimelineEvent.media_type == "video"),
            models.TimelineEvent.summary == None
        ).all()
        
        if not orphans:
            logger.info("✅ No orphans found. System healthy.")
            return
            
        logger.info(f"⚠️ Found {len(orphans)} orphans. Rescuing...")
        
        for event in orphans:
            logger.info(f"🚑 Re-enqueuing Event {event.id}...")
            enqueue_event(event.id) # Use enqueue wrapper to use Huey
            
    except Exception as e:
        logger.error(f"Failed to reprocess orphans: {e}")
    finally:
        db.close()

