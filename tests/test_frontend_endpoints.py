
import requests
import sys

def test_frontend():
    base_url = "http://localhost:8000"
    print("🖥️  Testing Frontend Endpoints...")

    # 1. Test Timeline Partial
    try:
        # Request with skip=5 (simulating first scroll)
        resp = requests.get(f"{base_url}/api/timeline?skip=5&limit=5")
        if resp.status_code == 200:
            if "timeline-item" in resp.text:
                print("✅ /api/timeline returns HTML fragments")
            else:
                print("⚠️ /api/timeline returned 200 but content doesn't look like timeline items.")
                print(resp.text[:200])
                
            if "hx-get" in resp.text:
                print("✅ /api/timeline includes next trigger (Infinite Scroll)")
            else:
                print("ℹ️ /api/timeline did not include next trigger (Limit reached or logic error?)")
        else:
            print(f"❌ /api/timeline failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

    # 2. Test Manage Partial
    try:
        resp = requests.get(f"{base_url}/api/manage-events?page=1&limit=5")
        if resp.status_code == 200:
            if "<tr" in resp.text:
                print("✅ /api/manage-events returns Table Rows")
            else:
                print("⚠️ /api/manage-events returned 200 but content doesn't look like rows.")
                
            if "hx-get" in resp.text:
                print("✅ /api/manage-events includes next trigger")
            else:
                print("ℹ️ /api/manage-events did not include next trigger")
        else:
            print(f"❌ /api/manage-events failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    test_frontend()
