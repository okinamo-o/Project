import cv2
import numpy as np
import base64
import time
import httpx
import logging
import os
import argparse
import threading
from typing import Dict, Any, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NEXUS-VISION] %(message)s")
logger = logging.getLogger("nexus.vision")

class VisionService:
    """
    Local Computer Vision Subsystem.
    Performs real-time human object detection using Deep Learning (YOLOv5n ONNX + YuNet Face Detector),
    extracts persistent occupancy counts, tracks bounding boxes, and monitors sudden movement events.
    Supports real camera capture (DroidCam, USB webcam, IP stream) with automatic fallback to synthetic surveillance.
    """
    def __init__(self, backend_url: str = "http://127.0.0.1:8000", room_id: str = "lab_02", camera_source: Optional[Any] = None):
        self.backend_url = backend_url
        self.room_id = room_id
        self.cap = None
        self.camera_source = None
        self.camera_available = False
        self.prev_gray = None
        
        # Threading for real-time camera capture & decoupled 45 FPS stream
        self.frame_lock = threading.Lock()
        self.inference_lock = threading.Lock()
        self.latest_raw_frame = None
        self.capture_thread = None
        self.inference_thread = None
        self.running = True

        # Decoupled state updated by background inference and rendered at 45 FPS
        self.last_detection_time = 0.0
        self.persistence_window_s = 0.5
        self.cached_occupancy = 0
        self.cached_bboxes = []
        self.current_event_type = "NO_SUBJECT"
        self.is_feed_blank = False
        self.mean_brightness = 30.0
        self.std_brightness = 15.0

        # Persistent HTTP client for low-latency network dispatches
        self.client = httpx.Client(timeout=2.0)

        # Models
        self.yolo_net = None
        self.face_detector = None
        self._init_models()
        self._init_camera(camera_source)
        self._start_inference_thread()

    @staticmethod
    def _download_model_if_missing(model_path: str, url: str, model_name: str):
        if not os.path.exists(model_path):
            try:
                import urllib.request
                logger.info(f"Downloading missing {model_name} model from {url}...")
                urllib.request.urlretrieve(url, model_path)
                logger.info(f"Downloaded {model_name} successfully.")
            except Exception as e:
                logger.warning(f"Could not auto-download {model_name} model: {e}")

    def _init_models(self):
        """Initializes Deep Learning ONNX object detection and face models with auto-download fallback."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, "models")
        os.makedirs(models_dir, exist_ok=True)

        yolo_path = os.path.join(models_dir, "yolov5n.onnx")
        yunet_path = os.path.join(models_dir, "face_detection_yunet_2023mar.onnx")

        # Ensure models exist on new machines
        self._download_model_if_missing(
            yolo_path,
            "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx",
            "YOLOv5n"
        )
        self._download_model_if_missing(
            yunet_path,
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "YuNet"
        )

        # 1. Load YOLOv5n Object Detector
        if os.path.exists(yolo_path):
            try:
                self.yolo_net = cv2.dnn.readNetFromONNX(yolo_path)
                logger.info("YOLOv5n Person Object Detector loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load YOLOv5n ONNX model: {e}")

        # 2. Load YuNet Face Detector
        if os.path.exists(yunet_path) and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.face_detector = cv2.FaceDetectorYN.create(
                    model=yunet_path,
                    config="",
                    input_size=(640, 480),
                    score_threshold=0.5,
                    nms_threshold=0.3,
                    top_k=5000
                )
                logger.info("YuNet Face Detector loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load YuNet Face Detector: {e}")

    def _init_camera(self, explicit_source: Optional[Any] = None):
        if explicit_source == "synthetic":
            logger.info("Explicit synthetic camera mode requested.")
            self.camera_available = False
            return

        sources_to_try = []
        env_source = os.getenv("VISION_CAMERA_SOURCE") or os.getenv("DROIDCAM_SOURCE")

        if explicit_source is not None:
            sources_to_try.append(explicit_source)
        elif env_source is not None and str(env_source).strip() != "":
            sources_to_try.append(int(env_source) if str(env_source).isdigit() else env_source)
        
        # Priority for laptops: 0 (Built-in primary webcam), 1 (External/virtual camera), 2
        for s in [0, 1, 2]:
            if s not in sources_to_try:
                sources_to_try.append(s)

        # Probe candidates across multiple backends (DSHOW for standard/USB, MSMF for Windows laptops, CAP_ANY default)
        backends = [
            ("V4L2", cv2.CAP_V4L2),
            ("DEFAULT", cv2.CAP_ANY),
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF", cv2.CAP_MSMF)
        ]

        candidate_cap = None
        candidate_src = None

        for src in sources_to_try:
            is_index = isinstance(src, int) or (isinstance(src, str) and src.isdigit())
            src_val = int(src) if is_index else str(src)

            probe_backends = backends if is_index else [("URL/FILE", cv2.CAP_ANY)]
            for backend_name, backend_api in probe_backends:
                try:
                    cap = cv2.VideoCapture(src_val, backend_api) if is_index else cv2.VideoCapture(src_val)
                    try:
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception:
                        pass
                    if cap.isOpened():
                        # Read multiple frames to verify stream stability and brightness
                        valid_frame = None
                        for _ in range(5):
                            ret, frame = cap.read()
                            if ret and frame is not None and frame.size > 0:
                                valid_frame = frame
                        
                        if valid_frame is not None:
                            mean_b = float(np.mean(valid_frame))
                            # If the feed has realistic brightness (>1.0), it's definitely an active live camera
                            if mean_b > 1.0:
                                self.cap = cap
                                try:
                                    self.cap.set(cv2.CAP_PROP_FPS, 60)
                                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                                except Exception:
                                    pass
                                self.camera_source = src_val
                                self.camera_available = True
                                self._start_capture_thread()
                                logger.info(f"Active camera connected on source [{src_val}] via {backend_name} (resolution: {valid_frame.shape[1]}x{valid_frame.shape[0]}, brightness: {mean_b:.1f}).")
                                if candidate_cap:
                                    candidate_cap.release()
                                return
                            elif candidate_cap is None:
                                # Keep as fallback if no brighter camera is found
                                candidate_cap = cap
                                candidate_src = src_val
                                continue
                        cap.release()
                except Exception as e:
                    logger.debug(f"Source probe [{src_val}] via {backend_name} failed: {e}")

        if candidate_cap is not None:
            self.cap = candidate_cap
            self.camera_source = candidate_src
            self.camera_available = True
            self._start_capture_thread()
            logger.info(f"Camera opened on source [{candidate_src}] (awaiting live frames / privacy shutter).")
            return

        logger.info("No physical or virtual webcam detected. Operating in synthetic camera generation mode.")
        self.camera_available = False

    def _start_capture_thread(self):
        """Starts real-time background capture worker to eliminate video buffer delay."""
        if self.cap and self.camera_available and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
            self.capture_thread.start()

    def _capture_worker(self):
        """Continuously reads latest frames from hardware camera buffer."""
        while self.running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.frame_lock:
                        self.latest_raw_frame = frame
                else:
                    time.sleep(0.01)
            except Exception:
                time.sleep(0.02)

    def _start_inference_thread(self):
        """Starts background AI inference worker to decouple DNN compute from 45 FPS stream delivery."""
        if self.inference_thread is None or not self.inference_thread.is_alive():
            self.inference_thread = threading.Thread(target=self._inference_worker, daemon=True)
            self.inference_thread.start()

    def _inference_worker(self):
        """Asynchronously runs YOLOv5n + YuNet + motion detection on latest frame without blocking 45 FPS stream."""
        while self.running:
            raw = None
            if self.camera_available:
                with self.frame_lock:
                    if self.latest_raw_frame is not None:
                        raw = self.latest_raw_frame.copy()

            if raw is None:
                time.sleep(0.02)
                continue

            # 1. Lens occlusion check
            is_cov, mean_b, std_b = self.is_camera_covered(raw)
            current_time = time.time()

            if is_cov:
                with self.inference_lock:
                    self.is_feed_blank = True
                    self.mean_brightness = mean_b
                    self.std_brightness = std_b
                    self.cached_occupancy = 0
                    self.cached_bboxes = []
                    self.current_event_type = "NO_SUBJECT"
                    self.last_detection_time = 0.0
                time.sleep(0.05)
                continue

            # 2. YOLOv5n person detector
            bboxes = self.detect_objects_yolo(raw, conf_threshold=0.40)

            # 3. Secondary YuNet face detector if YOLO found nothing
            if not bboxes:
                face_boxes = self.detect_faces_yunet(raw)
                if face_boxes:
                    bboxes = face_boxes[:1]

            # 4. Motion detection
            sudden_move, _ = self.detect_motion(raw)

            # 5. Occupancy smoothing & Event classification
            with self.inference_lock:
                self.is_feed_blank = False
                self.mean_brightness = mean_b
                self.std_brightness = std_b

                if len(bboxes) > 0:
                    self.last_detection_time = current_time
                    capped = min(len(bboxes), 5)
                    self.cached_occupancy = capped
                    self.cached_bboxes = bboxes[:capped]
                    self.current_event_type = "SUDDEN_MOVEMENT" if sudden_move else "PERSON_DETECTED"
                elif (current_time - self.last_detection_time) < self.persistence_window_s and self.cached_occupancy > 0:
                    self.current_event_type = "SUDDEN_MOVEMENT" if sudden_move else "PERSON_DETECTED"
                else:
                    self.cached_occupancy = 0
                    self.cached_bboxes = []
                    self.current_event_type = "SUDDEN_MOVEMENT" if sudden_move else "NO_SUBJECT"

            time.sleep(0.02)

    def is_camera_covered(self, frame: np.ndarray) -> Tuple[bool, float, float]:
        """
        Robustly detects if the camera lens is physically covered (by hand, thumb, finger, shutter, tape, or paper).
        Checks darkness, flat contrast, edge density, and skin transillumination.
        Returns (is_covered, mean_val, std_val).
        """
        if frame is None or frame.size == 0:
            return True, 0.0, 0.0
        h, w = frame.shape[:2]
        mean_val = float(np.mean(frame))
        std_val = float(np.std(frame))

        # 1. Darkness / physical shutter closed
        if mean_val < 25.0:
            return True, mean_val, std_val

        # 2. Low contrast uniform surface
        if std_val < 10.0:
            return True, mean_val, std_val

        # 3. High-frequency edge check (a finger or thumb covering a lens causes extreme macro-blur with edge_ratio < 0.005)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 35, 100)
        edge_ratio = float(np.count_nonzero(edges)) / (h * w)

        if edge_ratio < 0.005:
            return True, mean_val, std_val

        # 4. Transilluminated flesh blob (thumb pressed on lens under room light: red channel heavily dominant and std < 40 with edge_ratio < 0.012)
        b_mean = float(np.mean(frame[:, :, 0]))
        g_mean = float(np.mean(frame[:, :, 1]))
        r_mean = float(np.mean(frame[:, :, 2]))
        if (r_mean > (b_mean * 1.4) and r_mean > (g_mean * 1.2)) and edge_ratio < 0.012:
            return True, mean_val, std_val

        return False, mean_val, std_val

    def detect_objects_yolo(self, frame: np.ndarray, conf_threshold: float = 0.40) -> List[Dict[str, Any]]:
        """Runs YOLOv5n forward pass to detect humans (class 0: person)."""
        if self.yolo_net is None:
            return []

        # If camera is covered, shutter closed, or pitch black, immediately return empty detections
        is_cov, _, _ = self.is_camera_covered(frame)
        if is_cov:
            return []

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.yolo_net.setInput(blob)
        output = self.yolo_net.forward()[0]

        # CRITICAL: Squeeze the batch dimension. ONNX outputs (1, 25200, 85);
        # we need (25200, 85) so each row is one detection proposal.
        if output.ndim == 3:
            output = output[0]

        boxes = []
        confidences = []
        x_factor = w / 640.0
        y_factor = h / 640.0

        for row in output:
            obj_conf = float(row[4])
            if obj_conf < conf_threshold:
                continue
                
            class_scores = row[5:]
            class_id = int(np.argmax(class_scores))
            
            if class_id == 0:  # COCO class 0: person
                person_score = float(class_scores[0])
                total_score = float(obj_conf * person_score)
                if total_score >= conf_threshold:
                    cx, cy, bw, bh = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                    left = int((cx - 0.5 * bw) * x_factor)
                    top = int((cy - 0.5 * bh) * y_factor)
                    width = int(bw * x_factor)
                    height = int(bh * y_factor)
                    
                    x1 = max(0, left)
                    y1 = max(0, top)
                    x2 = min(w, left + width)
                    y2 = min(h, top + height)
                    bw_clipped = x2 - x1
                    bh_clipped = y2 - y1

                    # Filter out noise (must be a realistic person proportion)
                    if bw_clipped > 35 and bh_clipped > 50:
                        boxes.append([x1, y1, bw_clipped, bh_clipped])
                        confidences.append(float(total_score))

        if not boxes:
            return []

        # NMS IoU 0.40: merge overlapping boxes
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, 0.40)
        raw_results = []
        if len(indices) > 0:
            for idx in indices.flatten():
                raw_results.append({
                    "class": "person",
                    "confidence": round(float(confidences[idx]), 2),
                    "box": boxes[idx]
                })

        if not raw_results:
            return []

        # Secondary Pass: Suppress Nested / Sub-part Boxes (Intersection over Smaller > 0.45)
        # e.g., when a person's head/torso proposal is nested inside the full person proposal
        def get_box_area(b):
            return b[2] * b[3]

        def get_ios(b1, b2):
            x1 = max(b1[0], b2[0])
            y1 = max(b1[1], b2[1])
            x2 = min(b1[0] + b1[2], b2[0] + b2[2])
            y2 = min(b1[1] + b1[3], b2[1] + b2[3])
            inter_w = max(0, x2 - x1)
            inter_h = max(0, y2 - y1)
            inter_area = inter_w * inter_h
            min_area = min(get_box_area(b1), get_box_area(b2))
            if min_area <= 0:
                return 0.0
            return inter_area / min_area

        # Sort by area descending so largest boxes come first
        raw_results.sort(key=lambda r: get_box_area(r["box"]), reverse=True)
        filtered_results = []
        for cand in raw_results:
            cand_box = cand["box"]
            is_duplicate_subpart = False
            for kept in filtered_results:
                kept_box = kept["box"]
                if get_ios(cand_box, kept_box) > 0.45:
                    is_duplicate_subpart = True
                    break
            if not is_duplicate_subpart:
                filtered_results.append(cand)

        return filtered_results

    def detect_faces_yunet(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Runs YuNet Face Detector as secondary verification for human presence."""
        if self.face_detector is None:
            return []
        is_cov, _, _ = self.is_camera_covered(frame)
        if is_cov:
            return []

        h, w = frame.shape[:2]
        self.face_detector.setInputSize((w, h))
        ret, faces = self.face_detector.detect(frame)
        if faces is None or len(faces) == 0:
            return []

        results = []
        for face in faces:
            score = float(face[-1])
            if score >= 0.70:
                fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                # Validate landmarks: eye distance to avoid false positives on thumb/skin wrinkles
                re_x, re_y = face[4], face[5]
                le_x, le_y = face[6], face[7]
                eye_dist = np.hypot(re_x - le_x, re_y - le_y)

                # A real human face sitting in front of a laptop webcam has eye distance >= 22px
                # and face dimensions >= 50x60
                if eye_dist < 22.0 or fw < 50 or fh < 60:
                    continue

                # Expand face bounding box to estimate upper body / person
                px = max(0, fx - int(fw * 0.5))
                py = max(0, fy - int(fh * 0.2))
                pw = min(w - px, int(fw * 2.0))
                ph = min(h - py, int(fh * 3.2))
                results.append({
                    "class": "person",
                    "confidence": round(score, 2),
                    "box": [px, py, pw, ph]
                })
        return results

    def detect_motion(self, frame: np.ndarray) -> Tuple[bool, float]:
        """Calculates global frame difference to detect sudden fast movement."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return False, 0.0

        frame_delta = cv2.absdiff(self.prev_gray, gray)
        self.prev_gray = gray
        
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        motion_score = float(np.sum(thresh) / 255.0)
        
        # Sudden movement if > 15,000 changed pixels
        is_sudden = motion_score > 15000.0
        return is_sudden, motion_score

    def generate_synthetic_frame(self, occupancy: int = 1, alert: bool = False) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Generates a synthetic surveillance camera frame when physical camera is offline."""
        frame = np.full((480, 640, 3), 20, dtype=np.uint8)
        
        # Grid flooring & lab benches
        cv2.line(frame, (0, 360), (640, 360), (45, 55, 65), 2)
        cv2.rectangle(frame, (50, 260), (220, 360), (35, 45, 55), -1)
        cv2.rectangle(frame, (420, 260), (590, 360), (35, 45, 55), -1)
        
        bboxes = []
        if occupancy > 0:
            cx = 320 + int(30 * np.sin(time.time() * 2))
            cy = 280
            
            # Head and torso
            cv2.circle(frame, (cx, cy - 60), 22, (90, 110, 130), -1)
            cv2.ellipse(frame, (cx, cy), (30, 55), 0, 0, 360, (70, 90, 110), -1)
            
            # Bounding box
            bx, by, bw, bh = cx - 45, cy - 90, 90, 170
            box_color = (0, 0, 240) if alert else (0, 230, 110)
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), box_color, 2)
            
            label = f"PERSON: 0.94 {'[UNUSUAL MOTION]' if alert else ''}"
            cv2.putText(frame, label, (bx, by - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 1)
            
            bboxes.append({
                "class": "person",
                "confidence": 0.94,
                "box": [bx, by, bw, bh]
            })

        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"NEXUS CAM 02 // {self.room_id.upper()}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 255), 1)
        cv2.putText(frame, f"SYNTHETIC SURVEILLANCE // {timestamp_str}", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        cv2.putText(frame, f"OCCUPANCY: {occupancy}", (480, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 230, 255), 1)

        return frame, bboxes

    def frame_to_base64(self, frame: np.ndarray) -> str:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return base64.b64encode(buffer).decode('utf-8')

    def step(self, occupancy: Optional[int] = None, trigger_movement: bool = False) -> Dict[str, Any]:
        """Renders live surveillance HUD at true 45 FPS and dispatches stream snapshot/event to backend."""
        current_time = time.time()
        source_name = f"camera_source_{self.camera_source}" if self.camera_available else "synthetic_generator"
        is_feed_blank = False
        mean_brightness = 30.0
        bboxes = []
        final_occupancy = 0
        event_type = "NO_SUBJECT"

        if self.camera_available and self.cap:
            raw_frame = None
            with self.frame_lock:
                if self.latest_raw_frame is not None:
                    raw_frame = self.latest_raw_frame.copy()

            if raw_frame is None and self.cap.isOpened():
                ret, rf = self.cap.read()
                if ret and rf is not None:
                    raw_frame = rf.copy()

            if raw_frame is not None:
                frame = raw_frame.copy()

                with self.inference_lock:
                    is_feed_blank = self.is_feed_blank
                    mean_brightness = self.mean_brightness
                    std_brightness = self.std_brightness
                    bboxes = list(self.cached_bboxes)
                    final_occupancy = self.cached_occupancy
                    event_type = self.current_event_type

                if trigger_movement:
                    event_type = "SUDDEN_MOVEMENT"
                if occupancy is not None:
                    final_occupancy = occupancy
                    if occupancy > 0 and event_type == "NO_SUBJECT":
                        event_type = "PERSON_DETECTED"

                if is_feed_blank:
                    final_occupancy = 0
                    event_type = "NO_SUBJECT"
                    bboxes = []
                    cv2.rectangle(frame, (15, 200), (625, 305), (10, 10, 30), -1)
                    cv2.rectangle(frame, (15, 200), (625, 305), (0, 0, 255), 2)
                    cv2.putText(frame, f"[!] CAMERA FEED IS BLANK / COVERED (Mean: {mean_brightness:.1f}, Std: {std_brightness:.1f})", (25, 230),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 255), 2)
                    cv2.putText(frame, "Lens is covered or physical privacy shutter is closed.", (25, 260),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 255), 1)
                    cv2.putText(frame, "Real-time occupancy reported as 0 (Zone clear).", (25, 285),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 255), 1)
                else:
                    # Draw Surveillance Bounding Boxes & HUD Overlays
                    for b in bboxes:
                        bx, by, bw, bh = b["box"]
                        conf = b.get("confidence", 0.90)
                        box_color = (0, 0, 240) if event_type == "SUDDEN_MOVEMENT" else (0, 230, 110)

                        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), box_color, 2)

                        cor_len = min(15, bw // 4, bh // 4)
                        cv2.line(frame, (bx, by), (bx + cor_len, by), (0, 255, 255), 2)
                        cv2.line(frame, (bx, by), (bx, by + cor_len), (0, 255, 255), 2)
                        cv2.line(frame, (bx + bw, by + bh), (bx + bw - cor_len, by + bh), (0, 255, 255), 2)
                        cv2.line(frame, (bx + bw, by + bh), (bx + bw, by + bh - cor_len), (0, 255, 255), 2)

                        label = f"PERSON: {int(conf * 100)}%"
                        cv2.putText(frame, label, (bx, max(18, by - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

                    # Surveillance OSD Header with 45 FPS indicator
                    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, f"NEXUS AI SURVEILLANCE // {self.room_id.upper()}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 255), 2)
                    cv2.putText(frame, f"45 FPS LIVE STREAM // YOLOV5n + YUNET // {timestamp_str}", (15, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

                    # Occupancy Status Badge
                    badge_color = (0, 230, 110) if final_occupancy > 0 else (120, 120, 120)
                    cv2.putText(frame, f"OCCUPANCY: {final_occupancy}", (480, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, badge_color, 2)
            else:
                sim_occ = occupancy if occupancy is not None else 0
                frame, bboxes = self.generate_synthetic_frame(sim_occ, trigger_movement)
                final_occupancy = sim_occ
                event_type = "PERSON_DETECTED" if sim_occ > 0 else "NO_SUBJECT"
        else:
            sim_occ = occupancy if occupancy is not None else 0
            frame, bboxes = self.generate_synthetic_frame(sim_occ, trigger_movement)
            final_occupancy = sim_occ
            event_type = "PERSON_DETECTED" if sim_occ > 0 else "NO_SUBJECT"

        b64_snapshot = self.frame_to_base64(frame)

        metadata = {
            "source": source_name,
            "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
            "engine": "yolov5n_yunet_dnn_v2",
            "fps": 45
        }
        if is_feed_blank:
            metadata["feed_status"] = "BLANK_FEED"
            metadata["mean_brightness"] = round(mean_brightness, 2)
        elif self.camera_available:
            metadata["feed_status"] = "ACTIVE_STREAM"

        payload = {
            "room_id": self.room_id,
            "event_type": event_type,
            "confidence": 0.95 if final_occupancy > 0 else 1.0,
            "occupancy_count": final_occupancy,
            "bounding_boxes": bboxes,
            "snapshot_base64": b64_snapshot,
            "metadata": metadata
        }

        try:
            res = self.client.post(f"{self.backend_url}/api/vision/event", json=payload)
        except Exception:
            pass

        return payload

    def release(self):
        self.running = False
        if self.inference_thread and self.inference_thread.is_alive():
            try:
                self.inference_thread.join(timeout=0.5)
            except Exception:
                pass
        if self.capture_thread and self.capture_thread.is_alive():
            try:
                self.capture_thread.join(timeout=0.5)
            except Exception:
                pass
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except Exception:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS Vision Subsystem")
    parser.add_argument("--source", default=None, help="Camera index (e.g. 1) or stream URL (e.g. http://192.168.1.144:4747/video)")
    parser.add_argument("--room", default="lab_02", help="Monitored Room ID")
    parser.add_argument("--interval", type=float, default=0.022, help="Dispatch interval in seconds (default: 0.022 = 45 FPS)")
    args = parser.parse_args()

    service = VisionService(room_id=args.room, camera_source=args.source)
    print(f"[NEXUS-VISION] Streaming vision frames for {args.room} at 45 FPS (Source: {service.camera_source}, Interval: {args.interval:.3f}s)...")
    print("Press Ctrl+C to stop.")
    try:
        target_interval = args.interval
        while True:
            t0 = time.time()
            service.step()
            elapsed = time.time() - t0
            sleep_time = max(0.001, target_interval - elapsed)
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        service.release()
        print("[NEXUS-VISION] Stopped.")
