
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.media import process_upload_task
from services.logger import get_logger

logger = get_logger("rescue")

def rescue_uploads():
    temp_dir = "static/temp"
    if not os.path.exists(temp_dir):
        print(f"Directory {temp_dir} does not exist. Nothing to rescue.")
        return

    files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
    
    if not files:
        print("No orphaned files found in temp. All good!")
        return

    print(f"🚑 Found {len(files)} orphaned files in {temp_dir}. Starting rescue...")
    
    success_count = 0
    for filename in files:
        temp_path = os.path.join(temp_dir, filename)
        
        # We lost the original filename and metadata in the crash.
        # We will use the temp filename (UUID) or a generic name.
        # process_upload_task handles the final naming/moving.
        
        print(f"Processing {filename}...")
        try:
            # Metadata is empty as we lost it in the queue
            process_upload_task(temp_path, filename, metadata={})
            success_count += 1
        except Exception as e:
            print(f"❌ Failed to rescue {filename}: {e}")

    print(f"✅ Rescue complete. {success_count}/{len(files)} files recovered.")
    print("Please refresh the gallery.")

if __name__ == "__main__":
    rescue_uploads()
