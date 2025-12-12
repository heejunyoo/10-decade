import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
from database import SessionLocal
from services.analyzer import analyzer

def reconstruct_captions():
    db = SessionLocal()
    try:
        print("🧠 Starting Batch AI Captioning...")
        
        # Initialize models once
        print("   (Initializing AI models...)")
        analyzer.initialize()
        analyzer.initialize_caption_model()
        
        # Find all photos with empty summary
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            (models.TimelineEvent.summary == None) | (models.TimelineEvent.summary == "")
        ).all()
        
        print(f"📸 Found {len(events)} photos needing captions.")
        
        count = 0
        for event in events:
            image_path = event.image_url
            if not image_path:
                continue
                
            # Handle path adjustment
            if image_path.startswith("/"):
                real_path = image_path.lstrip("/") # Remove leading slash
            else:
                real_path = image_path
                
            if not os.path.exists(real_path):
                # Try finding it in static/uploads
                filename = os.path.basename(image_path)
                real_path = os.path.join("static/uploads", filename)
                
            if not os.path.exists(real_path):
                print(f"⚠️ File not found: {image_path}")
                continue
                
            # Get Context (Names)
            names = []
            for face in event.faces:
                if face.person and face.person.name != "Unknown":
                    names.append(face.person.name)
            
            names = list(set(names))
            
            try:
                # Generate
                caption = analyzer.generate_caption(real_path, names=names)
                
                if caption:
                    event.summary = caption
                    print(f"✅ [{count+1}/{len(events)}] ID {event.id}: {caption}")
                    count += 1
                    
                    # Commit every 5 items
                    if count % 5 == 0:
                        db.commit()
                        
                # Sleep to prevent Ollama OOM/Crash
                import time
                time.sleep(2)
                        
            except Exception as e:
                print(f"❌ Error for ID {event.id}: {e}")
        
        db.commit()
        print(f"🎉 Completed! Generated captions for {count} photos.")
        print("ℹ️  Run 'python scripts/build_index.py' to update the Search Index.")

    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reconstruct_captions()
