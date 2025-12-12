import os
import sys
import json

def verify_pwa():
    print("🚀 Starting PWA Verification...")
    
    # 1. Verify Manifest File
    manifest_path = "static/manifest.json"
    if not os.path.exists(manifest_path):
        print("❌ FAILED: static/manifest.json not found.")
        return
        
    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)
            if data['display'] != 'standalone':
                print("❌ FAILED: Manifest display is not 'standalone'.")
            else:
                print("✅ Manifest JSON is valid and set to standalone.")
    except Exception as e:
        print(f"❌ FAILED: Manifest JSON error: {e}")
        return

    # 2. Verify Base Template
    base_path = "templates/base.html"
    if not os.path.exists(base_path):
        print("❌ FAILED: templates/base.html not found.")
        return
        
    with open(base_path, 'r') as f:
        content = f.read()
        
    checks = [
        '<link rel="manifest" href="/static/manifest.json">',
        '<meta name="apple-mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
        '<meta name="apple-mobile-web-app-title" content="Decade">',
        'viewport-fit=cover',
        'safe-area-inset-top'
    ]
    
    all_passed = True
    for check in checks:
        if check not in content:
            print(f"❌ FAILED: Missing tag in base.html -> {check}")
            all_passed = False
        else:
            print(f"✅ Found tag: {check}")
            
    if all_passed:
        print("\n🎉 PWA Configuration Verified Successfully!")
    else:
        print("\n❌ Verification Failed.")

if __name__ == "__main__":
    verify_pwa()
