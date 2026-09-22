import os
import sys
import urllib.request

MODELS = {
    "yolov5n.onnx": {
        "url": "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx",
        "desc": "YOLOv5n Person Object Detector (Deep Learning)",
        "expected_min_bytes": 3_500_000
    },
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "desc": "YuNet Fast Face Detector (OpenCV Zoo)",
        "expected_min_bytes": 200_000
    }
}

def ensure_models():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    print("=" * 60)
    print(" NEXUS AI Model Verification & Download Subsystem")
    print("=" * 60)

    for filename, info in MODELS.items():
        dest = os.path.join(models_dir, filename)
        exists = os.path.exists(dest)
        size = os.path.getsize(dest) if exists else 0

        if exists and size >= info["expected_min_bytes"]:
            print(f"[OK] {info['desc']}: PRESENT ({size / 1_000_000:.2f} MB)")
        else:
            print(f"[FETCH] Downloading {filename} from {info['url']}...")
            try:
                urllib.request.urlretrieve(info["url"], dest)
                new_size = os.path.getsize(dest)
                print(f"[SUCCESS] Downloaded {filename} ({new_size / 1_000_000:.2f} MB) to {dest}")
            except Exception as e:
                print(f"[ERROR] Failed to download {filename}: {e}")

    print("=" * 60)
    print(" Model verification complete.")
    print("=" * 60)

if __name__ == "__main__":
    ensure_models()
