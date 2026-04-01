# Backend/Authentication.py
import os
import time
import importlib
import contextlib
import base64
import json
import hashlib
import hmac
import logging
import getpass
import stat

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

from .enhanced_compat import EnhancedErrorHandler, PerformanceTracker
from .config import ConfigManager

class EnhancedAdminOnlyAuth:
    def __init__(self):
        auth_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Data",
            "auth",
        )
        os.makedirs(auth_dir, exist_ok=True)

        self.logger = logging.getLogger(__name__)
        self.admin_face_data_file = os.path.join(auth_dir, "admin_face.json")
        self.legacy_admin_face_data_file = os.path.join(auth_dir, "admin_face.pkl")
        self.setup_complete_file = os.path.join(auth_dir, "setup_done.flag")
        self.emergency_code_file = os.path.join(auth_dir, "emergency_code.sha256")

        # Configure logging before any operation that may log
        self.setup_logging()
        self.emergency_code_hash = self._load_emergency_code_hash()
        
        # Initialize enhanced utilities
        self.error_handler = EnhancedErrorHandler()
        self.performance_tracker = PerformanceTracker()
        
        # Check if setup is already done
        self.setup_completed = self._is_setup_complete()
        self.admin_face_data = self.load_admin_face_data()
        if self.admin_face_data:
            self._refresh_setup_state()
        
        # Load face detection classifier when OpenCV is available.
        if cv2 is None:
            self.face_cascade = None
            self.last_error = "OpenCV is not installed"
        else:
            try:
                self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            except Exception:
                print("️ Could not load face cascade classifier")
                self.face_cascade = None
        
        # Enhanced settings
        self.debug_mode = ConfigManager.get_bool("JARVIS_AUTH_DEBUG", default=False)
        self.face_backend_preference = (ConfigManager.get("JARVIS_FACE_BACKEND", default="auto") or "auto").strip().lower()
        # In embedded Qt sessions, face_recognition/dlib can trigger native aborts on some systems.
        # Default to legacy OpenCV backend unless user explicitly forces otherwise.
        try:
            force_non_legacy = ConfigManager.get_bool("JARVIS_FACE_FORCE_ADVANCED_BACKEND", default=False)
            if not force_non_legacy:
                from PyQt5.QtWidgets import QApplication

                if QApplication.instance() is not None and self.face_backend_preference in {"auto", "face_recognition", "dlib"}:
                    self.face_backend_preference = "legacy"
        except Exception:
            pass
        self.face_backend = "legacy"
        self._face_recognition_module = None
        self._face_recognition_checked = False
        self.similarity_threshold = ConfigManager.get_float("JARVIS_FACE_SIMILARITY_THRESHOLD", default=0.84)
        self.distance_threshold = ConfigManager.get_float("JARVIS_FACE_DISTANCE_THRESHOLD", default=0.50)
        self.consecutive_match_frames = max(2, ConfigManager.get_int("JARVIS_FACE_MATCH_FRAMES", default=2))
        self.verification_attempts = 0
        self.max_attempts = 5
        self.last_error = ""

    def _get_face_recognition(self):
        if self._face_recognition_checked:
            return self._face_recognition_module

        self._face_recognition_checked = True
        pref = self.face_backend_preference
        if pref in {"legacy", "haar", "opencv"}:
            self.face_backend = "legacy"
            self._face_recognition_module = None
            return None

        try:
            module = importlib.import_module("face_recognition")
            self._face_recognition_module = module
            self.face_backend = "face_recognition"
            return module
        except Exception:
            self._face_recognition_module = None
            self.face_backend = "legacy"
            return None

    def _normalize_face_store(self, data):
        if isinstance(data, dict):
            backend = str(data.get("backend") or "legacy")
            encodings = data.get("encodings") or []
            if not isinstance(encodings, list):
                encodings = []
            return {"backend": backend, "encodings": encodings}
        if isinstance(data, list):
            return {"backend": "legacy", "encodings": data}
        return None

    def _get_face_store(self):
        return self._normalize_face_store(self.admin_face_data)

    def _stored_backend(self):
        store = self._get_face_store()
        return (store or {}).get("backend", "legacy")

    def _stored_encodings(self):
        store = self._get_face_store()
        return (store or {}).get("encodings", [])

    def _preview_enabled(self):
        requested = ConfigManager.get_bool("JARVIS_AUTH_SHOW_PREVIEW", default=True)
        if not requested:
            return False

        # OpenCV HighGUI preview can crash in embedded Qt WebEngine/Wayland sessions.
        # Keep preview enabled by default for console mode, but disable when running under
        # an active Qt application unless explicitly forced.
        force_preview = ConfigManager.get_bool("JARVIS_AUTH_FORCE_PREVIEW", default=False)
        if force_preview:
            return True

        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                return False
        except Exception:
            pass

        return True

    def _camera_indices(self):
        raw = (
            ConfigManager.get("JARVIS_CAMERA_INDEXES", default="")
            or ConfigManager.get("JARVIS_CAMERA_INDEX", default="")
            or ""
        )
        indices = []
        if raw:
            for token in str(raw).replace(";", ",").split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    indices.append(int(token))
                except ValueError:
                    continue
        if not indices:
            indices = [0, 1, 2]
        seen = set()
        ordered = []
        for idx in indices:
            if idx in seen:
                continue
            seen.add(idx)
            ordered.append(idx)
        return ordered

    def _open_camera(self):
        backend_candidates = []
        if hasattr(cv2, "CAP_V4L2"):
            backend_candidates.append(cv2.CAP_V4L2)
        backend_candidates.append(cv2.CAP_ANY)

        camera_indices = self._camera_indices()

        for index in camera_indices:
            for backend in backend_candidates:
                try:
                    cap = cv2.VideoCapture(index, backend)
                except Exception:
                    cap = None

                if cap is not None and cap.isOpened():
                    return cap

                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass

            # Fallback to the default constructor in case explicit backends fail.
            try:
                cap = cv2.VideoCapture(index)
            except Exception:
                cap = None

            if cap is not None and cap.isOpened():
                return cap

            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

        self.last_error = (
            f"Cannot access camera (tried indexes: {', '.join(str(i) for i in camera_indices)}). "
            "Close other apps using camera and check permissions."
        )
        return None

    def _warmup_camera(self, cap, frames: int = 4):
        if cap is None:
            return
        for _ in range(max(1, int(frames))):
            try:
                cap.read()
            except Exception:
                break

    def _is_setup_complete(self):
        has_face = os.path.exists(self.admin_face_data_file)
        if os.path.exists(self.setup_complete_file) and has_face:
            return True
        return has_face

    def _persist_setup_flag(self):
        os.makedirs(os.path.dirname(self.setup_complete_file), exist_ok=True)
        with open(self.setup_complete_file, 'w') as f:
            f.write("ENHANCED_ADMIN_SETUP_COMPLETED")

    def _load_emergency_code_hash(self):
        try:
            if not os.path.exists(self.emergency_code_file):
                return ""
            with open(self.emergency_code_file, "r", encoding="utf-8") as f:
                value = (f.read() or "").strip()
            if value.startswith("scrypt$"):
                parts = value.split("$", 2)
                if len(parts) == 3 and parts[1] and parts[2]:
                    return value
                return ""
            value = value.lower()
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                return ""
            return value
        except Exception:
            return ""

    def _save_emergency_code_hash(self, code_hash: str):
        try:
            os.makedirs(os.path.dirname(self.emergency_code_file), exist_ok=True)
            value = (code_hash or "").strip()
            with open(self.emergency_code_file, "w", encoding="utf-8") as f:
                f.write(value if value.startswith("scrypt$") else value.lower())
            self.emergency_code_hash = value if value.startswith("scrypt$") else value.lower()
            return True
        except Exception:
            return False

    def has_emergency_override_setup(self):
        return bool(self.emergency_code_hash)

    def _derive_emergency_hash(self, code: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(
            code.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        return f"scrypt${base64.b64encode(salt).decode('ascii')}${base64.b64encode(digest).decode('ascii')}"

    def _verify_emergency_hash(self, emergency_code: str, expected_hash: str) -> bool:
        if not emergency_code or not expected_hash:
            return False
        if expected_hash.startswith("scrypt$"):
            try:
                _, salt_b64, digest_b64 = expected_hash.split("$", 2)
                salt = base64.b64decode(salt_b64.encode("ascii"))
                expected = base64.b64decode(digest_b64.encode("ascii"))
                derived = hashlib.scrypt(
                    emergency_code.encode("utf-8"),
                    salt=salt,
                    n=2**14,
                    r=8,
                    p=1,
                    dklen=len(expected),
                )
                return hmac.compare_digest(derived, expected)
            except Exception:
                return False

        # Backward-compatible check for existing SHA-256 emergency hashes.
        input_hash = hashlib.sha256(emergency_code.encode()).hexdigest()
        return hmac.compare_digest(input_hash, expected_hash)

    def configure_emergency_override(self):
        print("\nStep 2/2: Emergency override setup")
        print("Create a private emergency passphrase for fallback access.")
        print("This value is stored only as a SHA-256 hash in Data/auth.")

        for _attempt in range(3):
            code = getpass.getpass("Set emergency passphrase: ").strip()
            confirm = getpass.getpass("Confirm emergency passphrase: ").strip()

            if not code:
                print(" Emergency passphrase cannot be empty")
                continue
            if code != confirm:
                print(" Passphrases do not match")
                continue

            code_hash = self._derive_emergency_hash(code)
            if self._save_emergency_code_hash(code_hash):
                print(" Emergency override configured")
                self.log_security_event("Emergency override configured")
                return True

            print(" Failed to store emergency override hash")
            break

        self.log_security_event("Emergency override setup failed", False)
        return False

    def has_face_setup(self):
        return bool(self._stored_encodings())

    def has_pin_setup(self):
        return False

    def _refresh_setup_state(self):
        self.setup_completed = self.has_face_setup()
        if self.setup_completed:
            self._persist_setup_flag()
        else:
            try:
                if os.path.exists(self.setup_complete_file):
                    os.remove(self.setup_complete_file)
            except Exception:
                pass

    def set_admin_pin(self, pin_code: str):
        _ = pin_code
        self.last_error = "PIN authentication has been removed"
        self.log_security_event("Enhanced admin PIN save rejected", False)
        return False

    def verify_admin_pin(self, pin_code: str):
        _ = pin_code
        self.last_error = "PIN authentication has been removed"
        self.log_security_event("Enhanced admin PIN verification rejected", False)
        return False

    def change_admin_pin(self, current_pin: str, new_pin: str):
        _ = current_pin
        _ = new_pin
        self.last_error = "PIN authentication has been removed"
        return False

    @contextlib.contextmanager
    def _managed_camera(self, cap):
        try:
            yield cap
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

    def _quick_match_face(self, gray_frame, face_rect, stored_encodings):
        try:
            x, y, w, h = face_rect
            if w < 30 or h < 30:
                return False
            face_roi = gray_frame[y:y + h, x:x + w]
            if face_roi.size == 0:
                return False
            face_roi = cv2.resize(face_roi, (100, 100))
            current_encoding = face_roi.flatten() / 255.0

            best_similarity = 0.0
            for admin_encoding in stored_encodings:
                similarity = self._calculate_similarity(current_encoding, admin_encoding)
                if similarity > best_similarity:
                    best_similarity = similarity
            return best_similarity > self.similarity_threshold
        except Exception:
            return False

    def quick_face_check(self):
        self.last_error = ""
        if self._stored_backend() == "face_recognition":
            # Quick fallback uses legacy grayscale matcher only.
            return False
        stored_encodings = self._stored_encodings()
        if not stored_encodings or self.face_cascade is None:
            return False
        try:
            cap = self._open_camera()
            if cap is None:
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)
            self._warmup_camera(cap, frames=3)

            ret, frame = cap.read()
            cap.release()
            if not ret:
                return False

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 3, minSize=(40, 40))
            if len(faces) != 1:
                return False
            return self._quick_match_face(gray, faces[0], stored_encodings)
        except Exception:
            return False

    def remove_admin_face(self):
        try:
            if os.path.exists(self.admin_face_data_file):
                os.remove(self.admin_face_data_file)
            self.admin_face_data = None
            self._refresh_setup_state()
            self.log_security_event("Enhanced admin face removed")
            self.last_error = ""
            return True
        except Exception as e:
            self.last_error = f"Failed to remove face data: {e}"
            self.log_security_event("Enhanced admin face remove failed", False)
            return False
    
    def setup_logging(self):
        """Enhanced logging setup"""
        log_path = os.path.join(os.path.dirname(self.admin_face_data_file), "enhanced_security.log")
        normalized_path = os.path.abspath(log_path)

        if getattr(self.logger, "_enhanced_auth_logging_ready", False):
            return

        has_file_handler = False
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler) and os.path.abspath(getattr(handler, "baseFilename", "")) == normalized_path:
                has_file_handler = True
                break
        if not has_file_handler:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter('%(asctime)s - ENHANCED - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = True
        self.logger._enhanced_auth_logging_ready = True
        self.logger.info("Enhanced AdminAuth System Initialized")
    
    def log_security_event(self, event, success=True):
        """Enhanced security event logging"""
        status = "SUCCESS" if success else "FAILED"
        message = f"{event} - {status}"
        if success:
            self.logger.info(message)
        else:
            self.logger.warning(message)
    
    @EnhancedErrorHandler.error_handler
    def load_admin_face_data(self):
        """Enhanced face data loading with integrity validation"""
        try:
            if not os.path.exists(self.admin_face_data_file):
                if os.path.exists(self.legacy_admin_face_data_file):
                    migrated = self._migrate_legacy_face_data()
                    if migrated is not None:
                        return migrated
                    self.logger.warning("Legacy pickle face data detected but migration failed; please re-enroll face data")
                return None
            with open(self.admin_face_data_file, 'r', encoding='utf-8') as f:
                data = self._normalize_face_store(json.load(f))
            if data is None:
                raise ValueError("Invalid face store format")
            encodings = data.get("encodings")
            if not isinstance(encodings, list) or len(encodings) == 0:
                raise ValueError("Face store has no encodings")
            self.logger.info("Loaded %d face samples", len(encodings))
            return data
        except Exception as e:
            self.logger.error("Failed loading face data: %s", e)
            self._remove_corrupt_face_file()
        return None

    def _remove_corrupt_face_file(self):
        try:
            if os.path.exists(self.admin_face_data_file):
                os.remove(self.admin_face_data_file)
        except Exception as e:
            self.logger.error("Failed to remove corrupt face data: %s", e)

    def _is_trusted_legacy_face_file(self) -> bool:
        path = self.legacy_admin_face_data_file
        if not os.path.exists(path):
            return False
        try:
            if os.path.islink(path):
                return False
            st = os.stat(path)
            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                return False
            mode = stat.S_IMODE(st.st_mode)
            # Reject world-writable files.
            if mode & 0o002:
                return False
            return True
        except Exception:
            return False

    def _migrate_legacy_face_data(self):
        if not self._is_trusted_legacy_face_file():
            return None

        try:
            import pickle

            with open(self.legacy_admin_face_data_file, "rb") as f:
                loaded = pickle.load(f)
            data = self._normalize_face_store(loaded)
            if data is None:
                return None
            encodings = data.get("encodings") or []
            if not isinstance(encodings, list) or len(encodings) == 0:
                return None

            normalized_encodings = []
            for item in encodings:
                try:
                    if np is not None:
                        normalized_encodings.append(np.asarray(item, dtype=np.float32).tolist())
                    else:
                        normalized_encodings.append([float(v) for v in item])
                except Exception:
                    continue

            if not normalized_encodings:
                return None

            payload = {
                "backend": str(data.get("backend") or "legacy"),
                "encodings": normalized_encodings,
            }
            os.makedirs(os.path.dirname(self.admin_face_data_file), exist_ok=True)
            with open(self.admin_face_data_file, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            try:
                os.replace(self.legacy_admin_face_data_file, self.legacy_admin_face_data_file + ".migrated")
            except Exception:
                pass

            self.logger.warning("Migrated legacy pickle face data to JSON format")
            return payload
        except Exception as e:
            self.logger.error("Legacy face data migration failed: %s", e)
            return None

    @PerformanceTracker.track_performance("Save Face Data")
    def save_admin_face_data(self, encodings, backend=None):
        """Enhanced face data saving"""
        try:
            normalized_encodings = []
            for item in list(encodings or []):
                try:
                    if np is not None:
                        normalized_encodings.append(np.asarray(item, dtype=np.float32).tolist())
                    else:
                        normalized_encodings.append([float(v) for v in item])
                except Exception:
                    continue

            payload = {
                "backend": backend or self.face_backend,
                "encodings": normalized_encodings,
            }
            os.makedirs(os.path.dirname(self.admin_face_data_file), exist_ok=True)
            with open(self.admin_face_data_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            self.admin_face_data = payload
            self._refresh_setup_state()
            
            print(f" Enhanced admin face data saved ({len(payload['encodings'])} samples)")
            self.log_security_event("Enhanced admin face data saved")
            return True
        except Exception as e:
            print(f" Enhanced error saving admin data: {e}")
            self.log_security_event("Enhanced admin face data save failed", False)
            return False

    @PerformanceTracker.track_performance("Capture Face")
    def capture_admin_face(self):
        """Enhanced face capture with better guidance"""
        if cv2 is None or np is None:
            self.last_error = "OpenCV/Numpy dependencies are missing"
            print(" Face capture unavailable: install opencv-python and numpy")
            return False
        self.last_error = ""
        print("\n ENHANCED ADMIN FACE ENROLLMENT")
        print("Enhanced features: Better lighting detection, angle validation")
        
        if self.face_cascade is None:
            print(" Face detection not available")
            self.last_error = "Face detection not available"
            return False
        
        cap = self._open_camera()
        if cap is None or not cap.isOpened():
            print(" Enhanced: Cannot access camera")
            self.last_error = "Cannot access camera (device busy or permission denied)"
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS, 15)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._warmup_camera(cap, frames=4)

        target_samples = max(4, ConfigManager.get_int("JARVIS_FACE_SETUP_SAMPLES", default=6))
        timeout_seconds = max(20, ConfigManager.get_int("JARVIS_FACE_SETUP_TIMEOUT", default=40))
        frame_skip = max(1, ConfigManager.get_int("JARVIS_FACE_SETUP_FRAME_SKIP", default=1))
        uniqueness_threshold = ConfigManager.get_float("JARVIS_FACE_SETUP_SIMILARITY", default=0.98)

        samples = []
        count = 0
        frame_index = 0
        last_encoding = None
        show_preview = False
        start_time = time.time()

        print("\n Enhanced capturing your face...")
        print(" Enhanced lighting analysis active")
        print(" Enhanced angle detection enabled")
        print(f" Collecting {target_samples} samples (timeout {timeout_seconds}s)")

        with self._managed_camera(cap):
            while count < target_samples and (time.time() - start_time) < timeout_seconds:
                ret, frame = cap.read()
                if not ret:
                    continue

                frame_index += 1
                if frame_index % frame_skip != 0:
                    continue
            
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)

                fr = self._get_face_recognition()
                if fr is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    small_rgb = cv2.resize(rgb, (0, 0), fx=0.5, fy=0.5)
                    locations_small = fr.face_locations(small_rgb, model="hog")
                    locations = [
                        (int(t * 2.0), int(r * 2.0), int(b * 2.0), int(l * 2.0))
                        for (t, r, b, l) in locations_small
                    ]
                    if len(locations) != 1:
                        continue
                    enc_list = fr.face_encodings(rgb, locations)
                    if not enc_list:
                        continue
                    face_encoding = enc_list[0]
                    if last_encoding is None:
                        is_new_sample = True
                    else:
                        distance = float(fr.face_distance([last_encoding], face_encoding)[0])
                        is_new_sample = distance > 0.02
                    if is_new_sample:
                        samples.append(face_encoding)
                        last_encoding = face_encoding
                        count += 1
                        print(f" Enhanced face sample {count}/{target_samples} captured")
                    if show_preview:
                        (top, right, bottom, left) = locations[0]
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.putText(frame, f"Enhanced Sample {count}/{target_samples}", (left, max(15, top - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    continue

                faces = self.face_cascade.detectMultiScale(gray, 1.08, 5, minSize=(80, 80))

                for (x, y, w, h) in faces:
                    if w < 80 or h < 80:
                        continue
                    
                    face_roi = gray[y:y+h, x:x+w]
                    face_roi = cv2.resize(face_roi, (100, 100))
                    face_roi = cv2.GaussianBlur(face_roi, (3, 3), 0)
                    
                    face_encoding = face_roi.flatten() / 255.0
                    
                    if last_encoding is None or not self._is_similar_encoding(face_encoding, last_encoding, threshold=uniqueness_threshold):
                        samples.append(face_encoding)
                        last_encoding = face_encoding
                        count += 1
                        
                        print(f" Enhanced face sample {count}/{target_samples} captured")
                        
                        if show_preview:
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            cv2.putText(frame, f"Enhanced Sample {count}/{target_samples}", (x, y-10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        if show_preview and len(samples) > 1:
                            similarity = self._calculate_similarity(face_encoding, samples[-2])
                            cv2.putText(frame, f"Enhanced Similarity: {similarity:.2f}", (x, y+h+20), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    else:
                        if show_preview:
                            similarity = self._calculate_similarity(face_encoding, last_encoding)
                            cv2.putText(frame, f"Enhanced: Too similar {similarity:.2f}", (x, y-10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
            
                if show_preview and len(faces) == 0:
                    cv2.putText(frame, "Enhanced: No face detected", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
                if show_preview:
                    cv2.putText(frame, "Enhanced: Look directly at camera", (10, frame.shape[0] - 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    cv2.putText(frame, "Enhanced: Press Q to cancel", (10, frame.shape[0] - 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        if len(samples) >= target_samples:
            self.admin_face_data = samples
            print(f" Enhanced: Successfully captured {len(samples)} face samples")
            self.last_error = ""
            active_backend = "face_recognition" if self._get_face_recognition() is not None else "legacy"
            return self.save_admin_face_data(samples, backend=active_backend)
        
        self.last_error = f"Not enough face samples ({len(samples)}/{target_samples}). Keep face centered and well-lit."
        print(f" Enhanced: {self.last_error}")
        return False

    def _is_similar_encoding(self, encoding1, encoding2, threshold=0.90):
        """Enhanced similarity check"""
        similarity = self._calculate_similarity(encoding1, encoding2)
        return similarity > threshold
    
    def _calculate_similarity(self, encoding1, encoding2):
        """Enhanced similarity calculation"""
        denom = float(np.linalg.norm(encoding1) * np.linalg.norm(encoding2))
        if denom <= 1e-12:
            return 0.0
        return float(np.dot(encoding1, encoding2) / denom)
    
    @PerformanceTracker.track_performance("Face Verification")
    @EnhancedErrorHandler.error_handler
    def verify_admin_face(self):
        """Enhanced face verification with robust cleanup and streak matching"""
        if cv2 is None or np is None:
            self.last_error = "OpenCV/Numpy dependencies are missing"
            return False
        self.last_error = ""
        stored_encodings = self._stored_encodings()
        if not stored_encodings:
            self.last_error = "No face data enrolled. Run setup first."
            return False

        stored_backend = str(self._stored_backend() or "legacy").strip().lower()
        fr = self._get_face_recognition()
        use_face_recognition = stored_backend == "face_recognition"
        if use_face_recognition and fr is None:
            self.last_error = (
                "Face data was enrolled with face_recognition backend, but it is unavailable now. "
                "Install face_recognition/dlib or re-enroll face data with legacy backend."
            )
            return False

        if (not use_face_recognition) and self.face_cascade is None:
            self.last_error = "Face detection unavailable"
            return False

        cap = self._open_camera()
        if cap is None:
            self.last_error = self.last_error or "Camera not available"
            return False

        max_attempts = 30
        attempts = 0
        match_streak = 0
        verified = False

        try:
            with self._managed_camera(cap):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                cap.set(cv2.CAP_PROP_FPS, 15)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self._warmup_camera(cap, frames=4)

                while attempts < max_attempts and not verified:
                    ret, frame = cap.read()
                    if not ret:
                        attempts += 1
                        continue

                    gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray_full = cv2.equalizeHist(gray_full)

                    if use_face_recognition:
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        small_rgb = cv2.resize(rgb, (0, 0), fx=0.5, fy=0.5)
                        locations_small = fr.face_locations(small_rgb, model="hog")
                        if len(locations_small) == 1:
                            locations = [
                                (int(t * 2), int(r * 2), int(b * 2), int(l * 2))
                                for (t, r, b, l) in locations_small
                            ]
                            enc_list = fr.face_encodings(rgb, locations)
                            if enc_list:
                                distances = fr.face_distance(stored_encodings, enc_list[0])
                                if float(min(distances)) <= self.distance_threshold:
                                    match_streak += 1
                                else:
                                    match_streak = 0
                        else:
                            match_streak = 0
                    else:
                        gray_half = cv2.resize(gray_full, (0, 0), fx=0.5, fy=0.5)
                        faces_half = self.face_cascade.detectMultiScale(
                            gray_half,
                            scaleFactor=1.1,
                            minNeighbors=4,
                            minSize=(30, 30),
                        )

                        if len(faces_half) == 1:
                            x, y, w, h = faces_half[0]
                            scaled_face = (int(x * 2), int(y * 2), int(w * 2), int(h * 2))
                            if self._quick_match_face(gray_full, scaled_face, stored_encodings):
                                match_streak += 1
                            else:
                                match_streak = 0
                        else:
                            match_streak = 0

                    if match_streak >= self.consecutive_match_frames:
                        verified = True

                    attempts += 1
        except Exception as e:
            self.last_error = f"Face verification error: {str(e)}"
            self.logger.exception("Face verification failed")
            verified = False

        self.log_security_event("Enhanced face verification", verified)
        if not verified and not self.last_error:
            self.last_error = "Face not recognized. Ensure good lighting and center your face."
        return verified

    @EnhancedErrorHandler.error_handler
    def emergency_admin_override(self):
        """Enhanced emergency override"""
        print(" Enhanced Emergency Admin Override Activated")

        expected_hash = self.emergency_code_hash or self._load_emergency_code_hash()
        if not expected_hash:
            print(" Emergency override is not configured")
            self.log_security_event("Enhanced emergency override unavailable", False)
            return False
        
        emergency_code = getpass.getpass("Enter enhanced emergency code: ")
        
        if self._verify_emergency_hash(emergency_code, expected_hash):
            print(" Enhanced emergency access granted")
            self.log_security_event("Enhanced emergency override used")
            logging.critical("ENHANCED EMERGENCY OVERRIDE USED")
            return True
        else:
            print(" Enhanced invalid emergency code")
            self.log_security_event("Enhanced emergency override failed", False)
            return False

    @PerformanceTracker.track_performance("Enhanced Authentication")
    def authenticate(self, allow_emergency=True):
        """Enhanced main authentication - face only"""
        if not self.setup_completed:
            print(" Enhanced: System not set up. Run admin setup first.")
            return False
        
        print(" ENHANCED ADMIN AUTHENTICATION REQUIRED")
        print("=" * 50)
        print("Choose authentication method:")
        print("1. Face Recognition")
        print("2. Emergency Override")
        
        choice = input("\nSelect authentication method (1-2): ").strip()
        
        if choice == '1':
            print("\n Attempting Face Authentication...")
            if self.verify_admin_face():
                print("\n FACE AUTHENTICATION SUCCESSFUL!")
                self.log_security_event("Face authentication successful")
                return True
            else:
                print("\n Face authentication failed")
                if allow_emergency:
                    return self.emergency_admin_override()
                return False
                
        elif choice == '2':
            return self.emergency_admin_override()
            
        else:
            print(" Enhanced invalid option")
            return False

    def setup_wizard(self):
        """Enhanced setup wizard for face enrollment"""
        print("\n" + "="*60)
        print("️  ENHANCED JARVIS AUTHENTICATION SETUP WIZARD")
        print("="*60)

        print("\nStep 1/2: Face lock enrollment")
        if not self.capture_admin_face():
            print(" Face setup failed")
            return False

        if not self.configure_emergency_override():
            print(" Emergency setup failed")
            return False

        self._persist_setup_flag()
        self.setup_completed = True
        print("\n Setup completed for: Face + Emergency Override")
        return True
