import urllib.request
import sys

def verify_search_endpoint():
    print("🚀 Verifying /search Endpoint...")
    url = "http://127.0.0.1:8000/search"
    
    try:
        with urllib.request.urlopen(url) as response:
            status = response.getcode()
            print(f"📡 GET {url} -> Status: {status}")
            
            if status == 200:
                print("✅ Success: Endpoint is accessible without query params.")
            else:
                print(f"⚠️ Unexpected Status: {status}")
                
    except urllib.error.HTTPError as e:
        print(f"❌ Failed: HTTP Error {e.code} - {e.reason}")
        if e.code == 422:
            print("   -> 422 Unprocessable Content (Issue persists)")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("Make sure the server is running on port 8000.")

if __name__ == "__main__":
    verify_search_endpoint()
