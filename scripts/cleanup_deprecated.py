
import os

def cleanup():
    target = "services/face_onnx.py"
    if os.path.exists(target):
        os.remove(target)
        print(f"Deleted {target}")
    else:
        print(f"{target} already deleted.")

if __name__ == "__main__":
    cleanup()
