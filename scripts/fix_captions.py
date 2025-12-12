import sys
import os
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
from services.analyzer import analyzer

def is_repetitive(text: str) -> bool:
    """
    Check if text looks broken/repetitive.
    """
    if not text:
        return False
        
    # Check 1: Repeating phrases pattern "X X"
    # Matches words of length 3+ happening twice
    if re.search(r'\b(\w{3,}(?:\s+\w+)*)\s+\1\b', text, flags=re.IGNORECASE):
        return True
        
    # Check 2: Very short or suspiciously looking (optional)
    return False

def fix_captions():
    print("🔧 Starting Caption Repair Tool...")
    db = SessionLocal()
    try:
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            models.TimelineEvent.summary != None
        ).all()
        
        print(f"🔍 Scanning {len(events)} photos...")
        
        candidates = []
        for event in events:
            # Extract English part (before \n\n)
            english_part = event.summary.split('\n\n')[0]
            
            if is_repetitive(english_part):
                candidates.append(event)
                
        print(f"⚠️ Found {len(candidates)} potentially broken captions.")
        
        if not candidates:
            print("✅ No issues found.")
            return

        print("🔄 Regenerating captions (This may take a while)...")
        success_count = 0
        
        for event in candidates:
            print(f"  Fixing Event {event.id}...")
            print(f"    [Bad] {event.summary[:50]}...")
            
            if not event.image_url:
                print("    Skipping (No URL)")
                continue
                
            file_path = event.image_url
            if file_path.startswith('/'):
                file_path = file_path.lstrip('/')
            
            if not os.path.exists(file_path):
                 print(f"    Skipping (File not found: {file_path})")
                 continue
                 
            # Re-generate
            # Get names for context
            names = []
            for face in event.faces:
                if face.person:
                    names.append(face.person.name)
            names = list(set(names))
            
            try:
                new_caption = analyzer.generate_caption(file_path, names)
                event.summary = new_caption
                print(f"    [New] {new_caption.splitlines()[0]}...")
                success_count += 1
                
                # Commit iteratively to save progress
                if success_count % 5 == 0:
                    db.commit()
            except Exception as e:
                print(f"    ❌ Error: {e}")

        db.commit()
        print(f"✅ Finished. Fixed {success_count} captions.")
        
    finally:
        db.close()

if __name__ == "__main__":
    fix_captions()
