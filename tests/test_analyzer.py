from services.analyzer import analyzer
import os

def test():
    print("🧪 Testing Image Analyzer...")
    
    # Pick a sample image
    test_image = "static/uploads/IMG_0002.jpg"
    
    if not os.path.exists(test_image):
        # Try finding any jpg
        files = [f for f in os.listdir("static/uploads") if f.endswith(".jpg")]
        if files:
            test_image = os.path.join("static/uploads", files[0])
        else:
            print("❌ No images found in static/uploads to test with.")
            return

    print(f"📸 Analyzing {test_image}...")
    tags = analyzer.analyze_image(test_image)
    
    print("-" * 20)
    print(f"🏷️  Result Tags: {tags}")
    print("-" * 20)
    
    if tags:
        print("✅ Success! Model is working.")
    else:
        print("⚠️  No tags returned (or model failed).")

if __name__ == "__main__":
    test()
