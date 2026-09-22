import numpy as np
import time
import httpx
import logging
import argparse
import os
import threading
from typing import Dict, Any, Tuple, Optional

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NEXUS-AUDIO] %(message)s")
logger = logging.getLogger("nexus.audio")

class AudioService:
    """
    Local Acoustic Intelligence Subsystem.
    Continuously streams live microphone input into a rolling FIFO audio buffer,
    extracts physical DSP descriptors (RMS energy, Zero-Crossing Rate, Spectral Centroid),
    and classifies operational acoustic classes with Voice Activity Detection (VAD) hangover:
    NORMAL, SPEECH, ALARM, IMPACT, SUDDEN_NOISE.
    """
    def __init__(
        self,
        backend_url: str = "http://127.0.0.1:8000",
        room_id: str = "lab_02",
        sample_rate: int = 16000,
        device_index: Optional[int] = None,
        use_mic: bool = True,
        buffer_duration: float = 1.0
    ):
        self.backend_url = backend_url
        self.room_id = room_id
        self.sample_rate = sample_rate
        self.device_index = device_index
        self.mic_available = False
        self.stream = None
        self.lock = threading.Lock()
        
        # Continuous rolling buffer (default 1.0s at 16kHz)
        self.buffer_size = int(self.sample_rate * buffer_duration)
        self.audio_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        
        # VAD hangover timer (preserves SPEECH classification across brief speech pauses)
        self.last_speech_time = 0.0
        self.speech_hangover_s = 1.0
        self.noise_floor = 0.003

        if use_mic and SOUNDDEVICE_AVAILABLE:
            self._init_microphone()
        else:
            logger.info("Microphone capture disabled or unavailable. Operating in synthetic simulation mode.")

    def _audio_callback(self, indata, frames, time_info, status):
        """Continuous non-blocking audio stream callback."""
        if status:
            logger.debug(f"Audio stream status: {status}")
        with self.lock:
            data = indata[:, 0]
            if len(data) >= self.buffer_size:
                self.audio_buffer[:] = data[-self.buffer_size:]
            else:
                self.audio_buffer = np.roll(self.audio_buffer, -len(data))
                self.audio_buffer[-len(data):] = data

    def _init_microphone(self):
        try:
            devices = sd.query_devices()
            valid_inputs = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
            if not valid_inputs:
                logger.warning("No audio input devices found on system. Using synthetic generator.")
                return

            chosen_dev = self.device_index
            env_dev = os.getenv("AUDIO_DEVICE_INDEX")
            if chosen_dev is None and env_dev is not None and env_dev.strip().isdigit():
                chosen_dev = int(env_dev.strip())

            if chosen_dev is None:
                # 1. On laptops, prioritize the OS default input device (built-in microphone array)
                default_in = sd.default.device[0]
                if default_in in valid_inputs:
                    chosen_dev = default_in
                    logger.info(f"Using default system microphone [{chosen_dev}]: {devices[chosen_dev]['name']}")
                else:
                    # 2. Look for common built-in laptop microphone names
                    mic_devs = [i for i in valid_inputs if any(k in devices[i]['name'].lower() for k in ["microphone", "array", "realtek", "internal", "built-in", "intel"])]
                    if mic_devs:
                        chosen_dev = mic_devs[0]
                        logger.info(f"Detected built-in laptop microphone [{chosen_dev}]: {devices[chosen_dev]['name']}")
                    else:
                        chosen_dev = valid_inputs[0]
                        logger.info(f"Using available audio input device [{chosen_dev}]: {devices[chosen_dev]['name']}")

            self.device_index = chosen_dev
            
            # Start continuous input stream
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=int(self.sample_rate * 0.05), # 50ms blocks
                device=self.device_index,
                dtype='float32',
                callback=self._audio_callback
            )
            self.stream.start()
            self.mic_available = True
            logger.info(f"Continuous microphone stream started on device [{chosen_dev}]: {devices[chosen_dev]['name']} ({self.sample_rate}Hz).")
        except Exception as e:
            logger.warning(f"Failed to initialize continuous microphone ({e}). Falling back to synthetic simulation.")
            self.mic_available = False

    def get_latest_samples(self) -> np.ndarray:
        """Retrieves the latest continuous audio samples with smooth dynamic boost."""
        if not self.mic_available:
            return self.generate_synthetic_chunk("NORMAL")
        
        with self.lock:
            raw = self.audio_buffer.copy()

        # Apply soft-knee compression boost (tanh): amplifies distant weak speech ~3.5x
        # while smoothly saturating loud audio to prevent digital clipping / distortion.
        boosted = np.tanh(raw * 3.5).astype(np.float32)
        return boosted

    def extract_features(self, audio_chunk: np.ndarray) -> Dict[str, float]:
        """Calculates physical DSP acoustic descriptors from audio samples."""
        if len(audio_chunk) == 0:
            return {
                "rms": 0.0,
                "zcr": 0.0,
                "spectral_centroid": 0.0,
                "peak_freq": 0.0,
                "peak_ratio": 1.0,
                "vocal_energy_ratio": 0.0
            }

        # 1. RMS Energy
        rms = float(np.sqrt(np.mean(audio_chunk**2)))

        # 2. Zero-Crossing Rate (ZCR)
        zero_crossings = np.nonzero(np.diff(audio_chunk > 0))[0]
        zcr = float(len(zero_crossings) / len(audio_chunk)) if len(audio_chunk) > 0 else 0.0

        # 3. Spectral Centroid via Fast Fourier Transform (FFT) & Tonal Prominence
        fft_magnitudes = np.abs(np.fft.rfft(audio_chunk))
        frequencies = np.fft.rfftfreq(len(audio_chunk), d=1.0 / self.sample_rate)
        sum_mag = np.sum(fft_magnitudes)
        mean_mag = np.mean(fft_magnitudes) if len(fft_magnitudes) > 0 else 1.0

        spectral_centroid = float(np.sum(frequencies * fft_magnitudes) / sum_mag) if sum_mag > 0 else 0.0

        peak_idx = int(np.argmax(fft_magnitudes))
        peak_freq = float(frequencies[peak_idx])
        peak_ratio = float(fft_magnitudes[peak_idx] / (mean_mag + 1e-6))

        # Vocal energy ratio (250Hz - 3400Hz)
        vocal_mask = (frequencies >= 250) & (frequencies <= 3400)
        vocal_energy_ratio = float(np.sum(fft_magnitudes[vocal_mask]) / (sum_mag + 1e-6))

        return {
            "rms": round(rms, 4),
            "zcr": round(zcr, 4),
            "spectral_centroid": round(spectral_centroid, 1),
            "peak_freq": round(peak_freq, 1),
            "peak_ratio": round(peak_ratio, 2),
            "vocal_energy_ratio": round(vocal_energy_ratio, 3)
        }

    def classify_signal(self, features: Dict[str, float]) -> Tuple[str, float]:
        """Classifies acoustic features into operational event classes with Voice Activity Hangover."""
        rms = features["rms"]
        sc = features["spectral_centroid"]
        zcr = features["zcr"]
        peak_ratio = features.get("peak_ratio", 1.0)
        peak_freq = features.get("peak_freq", 0.0)
        current_time = time.time()

        # Dynamically adapt ambient noise floor baseline during quiet periods
        if not hasattr(self, 'noise_floor') or self.noise_floor is None:
            self.noise_floor = 0.002
        if rms < max(0.006, self.noise_floor * 1.5) and peak_freq < 80.0:
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * rms
            self.noise_floor = max(0.0008, min(self.noise_floor, 0.015))

        # 1. Audible Alarm Siren / Pure Beep Detection
        # Triggers on frequency-swept emergency sirens or tonal alarm beepers
        is_siren = (sc > 1800.0 and zcr > 0.25 and rms >= max(0.006, self.noise_floor * 2.0))
        is_pure_alarm = (850.0 <= peak_freq <= 4500.0 and peak_ratio >= 6.0 and rms >= max(0.006, self.noise_floor * 2.0))
        is_loud_alarm = (rms > 0.15 and sc > 1800.0 and zcr > 0.25)

        if is_siren or is_pure_alarm or is_loud_alarm:
            confidence = min(0.98, max(0.90, 0.85 + (rms * 0.2)))
            return "ALARM", round(confidence, 2)

        # 2. Hard transient impact (high energy impulse, high ZCR, non-tonal)
        elif rms > 0.25 and zcr > 0.28 and peak_ratio < 5.0:
            return "IMPACT", 0.88

        # 3. Voice Activity Detection (Human Speech)
        # Speech energy clearly distinct from ambient noise, with voice fundamental >= 80Hz
        speech_threshold = max(0.0050, self.noise_floor * 1.8)
        is_speech_spectrum = (120.0 <= sc <= 4200.0) and (0.008 <= zcr <= 0.35) and (peak_freq >= 80.0)

        if rms >= speech_threshold and is_speech_spectrum:
            self.last_speech_time = current_time
            confidence = min(0.96, max(0.72, 0.70 + (rms * 1.0)))
            return "SPEECH", round(confidence, 2)

        # 4. Speech Hangover (Smooths out brief natural pauses between words)
        hangover_threshold = max(0.0035, self.noise_floor * 1.3)
        if (current_time - self.last_speech_time) < self.speech_hangover_s and rms >= hangover_threshold and (peak_freq >= 75.0 or rms > speech_threshold):
            return "SPEECH", 0.78

        # 5. Loud unclassified noise
        elif rms > 0.18:
            return "SUDDEN_NOISE", 0.80

        # 6. Ambient normal room baseline
        else:
            return "NORMAL", 0.95

    def generate_synthetic_chunk(self, event_type: str = "NORMAL", duration_s: float = 1.0) -> np.ndarray:
        """Generates realistic synthetic acoustic wave samples for testing."""
        n_samples = int(self.sample_rate * duration_s)
        t = np.linspace(0, duration_s, n_samples, endpoint=False)

        if event_type == "ALARM":
            freq = 2500 + 400 * np.sin(2 * np.pi * 4 * t)
            signal = 0.55 * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.05, n_samples)
        elif event_type == "IMPACT":
            decay = np.exp(-t * 20)
            signal = 0.8 * decay * np.sin(2 * np.pi * 120 * t) + np.random.normal(0, 0.02, n_samples)
        elif event_type == "SPEECH":
            signal = 0.25 * np.sin(2 * np.pi * 800 * t) + 0.20 * np.sin(2 * np.pi * 1800 * t) + np.random.normal(0, 0.005, n_samples)
        else:
            signal = 0.02 * np.sin(2 * np.pi * 60 * t) + np.random.normal(0, 0.005, n_samples)

        return signal.astype(np.float32)

    def step(self, simulated_event: Optional[str] = None) -> Dict[str, Any]:
        """Samples the continuous buffer, extracts DSP metrics, classifies, and dispatches to backend."""
        source = "synthetic_generator"
        if simulated_event is not None:
            samples = self.generate_synthetic_chunk(simulated_event)
            source = f"synthetic_{simulated_event.lower()}"
        elif self.mic_available:
            samples = self.get_latest_samples()
            source = f"microphone_dev_{self.device_index}"
        else:
            samples = self.generate_synthetic_chunk("NORMAL")

        features = self.extract_features(samples)
        classified_type, confidence = self.classify_signal(features)

        if simulated_event is not None and simulated_event != "NORMAL":
            classified_type = simulated_event
            confidence = 0.90

        payload = {
            "room_id": self.room_id,
            "event_type": classified_type,
            "confidence": confidence,
            "rms_energy": features["rms"],
            "spectral_centroid": features["spectral_centroid"],
            "zero_crossing_rate": features["zcr"],
            "metadata": {
                "source": source,
                "sample_rate": self.sample_rate,
                "classification_model": "continuous_stream_vad_v3"
            }
        }

        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.post(f"{self.backend_url}/api/audio/event", json=payload)
                if res.status_code == 200:
                    logger.info(f"Audio event dispatched: {classified_type} (RMS: {features['rms']}, Centroid: {features['spectral_centroid']}Hz, Source: {source})")
        except Exception as e:
            logger.warning(f"Could not dispatch audio event: {e}")

        return payload

    def stop(self):
        """Cleanly releases audio stream hardware."""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            self.mic_available = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS Acoustic Intelligence Subsystem")
    parser.add_argument("--room", default="lab_02", help="Monitored Room ID")
    parser.add_argument("--device", type=int, default=None, help="Audio input device index (default: OS default built-in microphone)")
    parser.add_argument("--simulate", choices=["NORMAL", "SPEECH", "ALARM", "IMPACT", "SUDDEN_NOISE"], default=None, help="Force simulated acoustic event")
    parser.add_argument("--interval", type=float, default=1.0, help="Dispatch interval in seconds")
    args = parser.parse_args()

    service = AudioService(room_id=args.room, device_index=args.device, use_mic=(args.simulate is None))
    print(f"[NEXUS-AUDIO] Monitoring room '{args.room}' (Mic: {service.mic_available}, Device: {service.device_index})...")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            service.step(simulated_event=args.simulate)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        service.stop()
        print("\n[NEXUS-AUDIO] Stopped.")
