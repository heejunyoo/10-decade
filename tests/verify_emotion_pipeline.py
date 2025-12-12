import sys
import os

from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
import models
from services.rag import memory_vector_store

def verify_pipeline():
    print("🧪 Starting Emotion Pipeline Verification...")
    
    # 1. Database Setup
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 2. Cleanup Test Data
        db.query(models.Face).filter(models.Face.location == "TEST_LOC").delete()
        db.query(models.Person).filter(models.Person.name == "Test Happy Person").delete()
        db.query(models.TimelineEvent).filter(models.TimelineEvent.title == "Test Emotion Event").delete()
        db.commit()
        
        # 3. Create Mock Data (Simulate successful DeepFace analysis)
        print("   Creating Mock Event & Face with Emotion='happy'...")
        
        person = models.Person(name="Test Happy Person")
        db.add(person)
        db.commit()
        
        event = models.TimelineEvent(
            date="2024-01-01",
            title="Test Emotion Event",
            image_url="/static/test.jpg",
            media_type="photo",
            mood="Joyful" # Simulated Gemini Mood
        )
        db.add(event)
        db.commit()
        
        face = models.Face(
            event_id=event.id,
            person_id=person.id,
            encoding=b"fake_encoding",
            location="TEST_LOC",
            emotion="happy" # Simulated DeepFace Result
        )
        db.add(face)
        db.commit()
        
        # 4. Verify DB Storage
        saved_face = db.query(models.Face).filter(models.Face.location == "TEST_LOC").first()
        if saved_face.emotion == "happy":
            print("   ✅ DB Verification Passed: Face.emotion is 'happy'")
        else:
            print(f"   ❌ DB Verification Failed: Got {saved_face.emotion}")
            
        # 5. Indexing Test
        print("   Indexing Event to ChromaDB...")
        memory_vector_store.add_events([event])
        
        # 6. RAG Search Test
        print("   Running Semantic Search for 'happy'...")
        hits = memory_vector_store.search("happy", k=3)
        found = False
        for hit in hits:
            # Check if our test event is in results
            if str(event.id) == hit['id']:
                found = True
                print(f"   ✅ Search Hit: {hit['text']}")
                if "looks happy" in hit['text']:
                    print("   ✅ Context Verification Passed: 'looks happy' found in text")
                else:
                    print("   ❌ Context Verification Failed: 'looks happy' NOT found")
                break
                
        if not found:
            print("   ❌ Search Verification Failed: Test event not found in results")
        
        if found:
            print("\n🎉 Emotion Pipeline Verified Successfully!")
        else:
            print("\n⚠️ Pipeline Verification Failed.")
            
    finally:
        # Cleanup
        db.query(models.Face).filter(models.Face.location == "TEST_LOC").delete()
        db.query(models.Person).filter(models.Person.name == "Test Happy Person").delete()
        db.query(models.TimelineEvent).filter(models.TimelineEvent.title == "Test Emotion Event").delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    verify_pipeline()
