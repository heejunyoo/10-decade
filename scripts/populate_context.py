
import sys
import os
sys.path.append(os.getcwd())

from database import SessionLocal
import models
from services.context import context_service
import time

def populate_all():
    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.latitude != None,
            models.TimelineEvent.longitude != None
        ).all()
        
        print(f"🔍 Found {len(events)} events with GPS.")
        count = 0
        
        for event in events:
            # Skip if already fully enriched
            if event.location_name and event.weather_info:
                continue
                
            print(f"Processing Event {event.id} ({event.date})...")
            context_service.enrich_event(event.id)
            count += 1
            # Rate limit politeness
            time.sleep(0.5)
            
        print(f"✅ Finished enriching {count} events.")
    finally:
        db.close()

if __name__ == "__main__":
    populate_all()
