import os
import hashlib
import sqlite3
import shutil
from sqlalchemy.orm import Session
from sqlalchemy import text, or_ # Import text for raw sql
from database import SessionLocal, SQLALCHEMY_DATABASE_URL, engine
import models

# Try to import analyzer, but don't fail if dependencies are missing (e.g. if just running db migrations)
try:
    from services.analyzer import analyzer
except ImportError:
    analyzer = None

# Try to import imagehash for duplicate detection
try:
    import imagehash
    from PIL import Image
except ImportError:
    imagehash = None

def get_db_connection():
    # Helper for raw sqlite connections
    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    return sqlite3.connect(db_path)

def run_migrations():
    """
    Consolidated migration script for SQLite.
    Adds necessary columns if they don't exist.
    """
    print("🚀 Starting Database Migration Checks...")
    
    # 0. Create Missing Tables (Safe for existing ones)
    models.Base.metadata.create_all(bind=engine)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # List of Schema Changes
    # (Table, Column, Type, Default/Nullable)
    migrations = [
        ("timeline_events", "latitude", "FLOAT"),
        ("timeline_events", "longitude", "FLOAT"),
        ("timeline_events", "location_name", "VARCHAR"),
        ("timeline_events", "tags", "VARCHAR"),
        ("timeline_events", "thumbnail_url", "VARCHAR"),
        ("timeline_events", "file_hash", "VARCHAR"),
        ("timeline_events", "phash", "VARCHAR"),
        ("timeline_events", "summary", "TEXT"),
        ("time_capsules", "capsule_type", "VARCHAR DEFAULT 'custom'"),
        ("time_capsules", "prompt_question", "VARCHAR"),
        ("time_capsules", "is_read", "INTEGER DEFAULT 0"),
        ("memory_interactions", "author", "VARCHAR"),
        ("system_logs", "metadata_json", "TEXT"),
        ("system_logs", "level", "VARCHAR"),
        ("system_logs", "module", "VARCHAR"),
    ]

    for table, col, col_def in migrations:
        try:
            # Basic check - in SQLite ADD COLUMN is safe-ish but will fail if exists
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            print(f"✅ Added column {col} to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e) or "already exists" in str(e):
                print(f"🔹 {col} in {table} already exists.")
            else:
                print(f"❌ Error adding {col} to {table}: {e}")

    conn.commit()
    conn.close()
    print("🏁 Migration checks complete.")

def backfill_hashes():
    """
    Backfill SHA256 hashes for existing images.
    """
    print("🔄 Backfilling File Hashes...")
    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(models.TimelineEvent.image_url != None).all()
        count = 0
        for event in events:
            if not event.file_hash:
                filename = event.image_url.split("/")[-1]
                file_path = os.path.join("static/uploads", filename)
                
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read()
                            sha256_hash = hashlib.sha256(content).hexdigest()
                            
                        event.file_hash = sha256_hash
                        count += 1
                        print(f"  Updated hash for {filename}")
                    except Exception as e:
                        print(f"  Error processing {filename}: {e}")
                else:
                    print(f"  File not found: {file_path}")
        db.commit()
        print(f"✅ Backfill complete. Updated {count} events.")
    finally:
        db.close()

def backfill_gps():
    """
    Extract and backfill GPS data for existing images.
    """
    print("🌍 Backfilling GPS Data...")
    from utils.image import get_gps_from_image
    
    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.image_url != None,
            models.TimelineEvent.media_type == "photo"
        ).all()
        
        updated_count = 0
        for event in events:
            # Skip if already has GPS (optional, can remove check to force update)
            if event.latitude is not None and event.longitude is not None:
                continue

            if event.image_url.startswith("/"):
                relative_path = event.image_url.lstrip("/")
                file_path = os.path.join(os.getcwd(), relative_path)
                
                if os.path.exists(file_path):
                    lat, lon = get_gps_from_image(file_path)
                    if lat and lon:
                        event.latitude = lat
                        event.longitude = lon
                        updated_count += 1
                        print(f"  Found GPS for event {event.id}: {lat}, {lon}")
        
        db.commit()
        print(f"✅ GPS Backfill complete. Updated {updated_count} events.")
    finally:
        db.close()

def backfill_tags():
    """
    Run AI Analysis on all photos to backfill tags.
    """
    print("🏷️ Backfilling Tags (AI Analysis)...")
    if not analyzer:
        print("❌ Analyzer service not available. Check dependencies (torch, transformers, pillow).")
        return

    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.image_url != None
        ).all()
        
        updated_count = 0
        for event in events:
             if event.image_url and event.image_url.startswith('/static/uploads/'):
                filename = event.image_url.split('/')[-1]
                file_path = os.path.join("static/uploads", filename)
                
                if os.path.exists(file_path):
                    try:
                        # Existing tags
                        current_tags = [t.strip() for t in (event.tags or "").split(',') if t.strip()]
                        
                        # Analyze
                        print(f"  Analyzing {event.id}: {filename}...")
                        new_tags = analyzer.analyze_image(file_path)
                        
                        if new_tags:
                            # Merge
                            combined_set = set(current_tags + new_tags)
                            merged_tags = ",".join(list(combined_set))
                            
                            if merged_tags != event.tags:
                                event.tags = merged_tags
                                updated_count += 1
                                print(f"    -> Updated Tags: {merged_tags}")
                    except Exception as e:
                        print(f"    -> Error analyzing: {e}")
        
        db.commit()
        print(f"✅ Tag Backfill complete. Updated {updated_count} events.")
    finally:
        db.close()

def backfill_phash():
    """
    Backfill Perceptual Hashes (pHash) for visual duplicate detection.
    """
    print("👁️ Backfilling Visual Hashes (pHash)...")
    if not imagehash:
        print("❌ imagehash or Pillow not installed.")
        return

    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.image_url != None,
            models.TimelineEvent.phash == None
        ).all()
        
        print(f"  Found {len(events)} photos to process...")
        count = 0
        
        for event in events:
            try:
                if event.image_url.startswith("/"):
                    # Remove leading slash for local path e.g. /static/... -> static/...
                    file_path = event.image_url.lstrip("/")
                else:
                    file_path = event.image_url
                    
                if os.path.exists(file_path):
                    # We need to open the image. 
                    # Note: utils/image.py might be useful but we need the PIL object here for imagehash
                    with Image.open(file_path) as image:
                        phash = str(imagehash.phash(image))
                        event.phash = phash
                        count += 1
                        print(f"    Generated pHash for {event.id}")
                else:
                    print(f"    File not found: {file_path}")
            except Exception as e:
                print(f"    Error processing {event.id}: {e}")
        
        db.commit()
        print(f"✅ cpHash Backfill complete. Updated {count} events.")
    finally:
        db.close()

def cleanup_all():
    """
    DANGER: Deletes ALL timeline events and files in static/uploads.
    """
    print("🚨 STARTING CLEANUP: Deleting all data...")
    
    # 1. Delete DB Records
    db = SessionLocal()
    try:
        # Delete dependent tables first
        db.query(models.Face).delete()
        db.query(models.Person).delete()
        count = db.query(models.TimelineEvent).delete()
        
        
        db.commit()
        print(f"🗑️  Deleted {count} events, and all face/people data.")
        
        # Reset Sequences (Safe effort)
        try:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('timeline_events', 'people', 'faces')"))
            db.commit()
        except Exception:
            pass # Sequence table might not exist yet
            
    except Exception as e:
        print(f"❌ Error deleting DB records: {e}")
        db.rollback()
        print(f"❌ Error deleting DB records: {e}")
    finally:
        db.close()
        
    # 2. Delete Files
    uploads_dir = "static/uploads"
    if os.path.exists(uploads_dir):
        try:
            # Delete entries but keep the directory
            for filename in os.listdir(uploads_dir):
                file_path = os.path.join(uploads_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
            print(f"🗑️  Cleared {uploads_dir} directory.")
        except Exception as e:
            print(f"❌ Error clearing uploads dir: {e}")
    
    print("✨ Cleanup Complete. System is fresh.")

def backfill_faces():
    """
    Backfill faces for all photos.
    """
    print("👤 Backfilling Faces...")
    # Import inside function to avoid dependency error if not installed
    try:
        from services.faces import process_faces
    except ImportError as e:
        print(f"❌ Face service error (missing dependencies?): {e}")
        return

    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.image_url != None
        ).all()
        
        print(f"Found {len(events)} photos. Processing...")
        
        for i, event in enumerate(events):
            # Check if this event already has faces processed? 
            # Or just re-run (idempotency check done inside process_faces? No, it just adds faces currently)
            # We should check if faces exist for this event to avoid dupes.
            existing_faces = db.query(models.Face).filter(models.Face.event_id == event.id).count()
            if existing_faces > 0:
                print(f"  Skipping Event {event.id}, already has {existing_faces} faces.")
                continue
                
            process_faces(event.id)
            
    finally:
        db.close()

def backfill_captions(force: bool = False):
    """
    Generate AI Captions for photos.
    """
    print("📝 Backfilling Captions (AI Summary)...")
    if not analyzer:
        print("❌ Analyzer service not available.")
        return

    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.image_url != None
        ).all()
        
        print(f"Found {len(events)} photos. Processing...")
        processed = 0
        
        for event in events:
            # Skip if exists and not forced
            if event.summary and not force:
                continue
                
            if event.image_url and event.image_url.startswith('/static/uploads/'):
                filename = event.image_url.split('/')[-1]
                file_path = os.path.join("static/uploads", filename)
                
                if os.path.exists(file_path):
                    print(f"  Captioning Event {event.id}...")
                    try:
                        # Collect names for this event
                        names = []
                        faces = db.query(models.Face).filter(models.Face.event_id == event.id).all()
                        for f in faces:
                            if f.person:
                                names.append(f.person.name)
                        
                        unique_names = list(set(names))
                        if unique_names:
                            print(f"    Context: {unique_names}")
                        
                        caption = analyzer.generate_caption(file_path, names=unique_names)
                        if caption:
                            event.summary = caption
                            processed += 1
                            print(f"    -> '{caption}'")
                    except Exception as e:
                        print(f"    -> Error: {e}")
        
        db.commit()
        print(f"✅ Caption Backfill complete. Updated {processed} events.")
    finally:
        db.close()

def create_backup():
    """
    Create a backup of the database and uploads directory.
    Retains only the 5 most recent backups.
    """
    from datetime import datetime
    import glob
    
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    print(f"📦 Starting Backup: {backup_name}...")
    
    # 1. Prepare Staging Area (to zip everything cleanly)
    staging_dir = os.path.join(backup_dir, "temp_stage")
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir)
    
    try:
        # Copy DB
        if os.path.exists("decade_journey.db"):
            shutil.copy2("decade_journey.db", os.path.join(staging_dir, "decade_journey.db"))
            
        # Copy Uploads
        if os.path.exists("static/uploads"):
            shutil.copytree("static/uploads", os.path.join(staging_dir, "uploads"))
            
        # Zip It
        shutil.make_archive(backup_path, 'zip', staging_dir)
        print(f"✅ Backup created at: {backup_path}.zip")
        
    except Exception as e:
        print(f"❌ Backup Failed: {e}")
    finally:
        # Cleanup Staging
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
            
    # 2. Retention Policy (Keep last 5)
    zip_files = sorted(glob.glob(os.path.join(backup_dir, "backup_*.zip")))
    if len(zip_files) > 5:
        to_delete = zip_files[:-5]
        print(f"🧹 Cleaning up {len(to_delete)} old backups...")
        for f in to_delete:
            try:
                os.remove(f)
                print(f"  Deleted: {os.path.basename(f)}")
            except Exception as e:
                print(f"  Error deleting {f}: {e}")

def backfill_rag():
    """
    Re-index all events into ChromaDB for RAG search.
    """
    print("📇  Re-indexing content for RAG Search...")
    try:
        from services.rag import Indexer
    except ImportError as e:
        print(f"❌ RAG service error (missing dependencies?): {e}")
        return

    try:
        Indexer.index_all()
        print("✅ RAG Indexing complete.")
    except Exception as e:
        print(f"❌ Error during RAG indexing: {e}")

def retry_failures():
    """
    Find events that are missing AI analysis (faces/tags/summary) and re-queue them.
    Useful if the background worker crashed or failed during upload.
    """
    print("🚑  Retrying failed analysis tasks...")
    try:
        from services.tasks import enqueue_event
    except ImportError:
        print("❌ Task service not available.")
        return

    db = SessionLocal()
    try:
        # Find photos that are missing summary OR tags AND are not just "processing" (but we don't have a status flag yet)
        # We assume if it's been a while and they are empty, it failed.
        # Just selecting all photos with empty summary is a decent heuristic.
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            or_(models.TimelineEvent.summary == None, models.TimelineEvent.summary == ""),
            models.TimelineEvent.image_url != None
        ).all()
        
        print(f"Found {len(events)} potentially incomplete events.")
        
        for event in events:
             if event.image_url and os.path.exists(f"static/uploads/{event.image_url.split('/')[-1]}"):
                 enqueue_event(event.id)
             else:
                 print(f"Skipping {event.id}: File missing")
                 
        print(f"✅ Queued {len(events)} items for retry.")
    except Exception as e:
        print(f"❌ Error during retry: {e}")
    finally:
        db.close()

def process_all_media(force: bool = False):
    """
    Unified command to run the entire processing pipeline in the correct order.
    Order: Migrations -> Hashes -> GPS -> pHash -> Faces -> AI Captions -> RAG Index.
    """
    print("\n🚀 STARTING FULL PIPELINE PROCESSING\n" + "="*40)
    
    # 1. Database Schema
    run_migrations()
    print("-" * 20)
    
    # 2. File Integrity (SHA256)
    backfill_hashes()
    print("-" * 20)
    
    # 3. Metadata (GPS/Exif)
    backfill_gps()
    print("-" * 20)
    
    # 4. Visual Hash (Deduplication)
    backfill_phash()
    print("-" * 20)
    
    # 5. Face Detection (CPU Heavy)
    # This must run BEFORE captions so captions can use the names
    backfill_faces()
    print("-" * 20)
    
    # 6. AI Captions (GPU/CPU Heavy)
    backfill_captions(force=force)
    print("-" * 20)

    # 7. RAG Indexing (Fast, but needs captions)
    backfill_rag()
    
    print("="*40)
    print("✨ ALL TASKS COMPLETED SUCCESSFULLY ✨")

def reset_faces():
    """
    Clear all face data and re-index.
    """
    print("👤 Resetting and Re-indexing Faces...")
    try:
        from services.faces import reindex_faces
        reindex_faces()
    except ImportError as e:
        print(f"❌ Face service error: {e}")
