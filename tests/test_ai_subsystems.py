import pytest
import numpy as np
from ai.vision.vision_service import VisionService
from ai.audio.audio_service import AudioService

def test_vision_service_synthetic():
    service = VisionService(camera_source="synthetic")
    payload = service.step(occupancy=1)
    assert payload["room_id"] == "lab_02"
    assert payload["occupancy_count"] == 1
    assert payload["event_type"] == "PERSON_DETECTED"
    assert len(payload["bounding_boxes"]) == 1
    assert len(payload["snapshot_base64"]) > 0
    service.release()

def test_vision_service_zero_occupancy():
    service = VisionService(camera_source="synthetic")
    payload = service.step(occupancy=0)
    assert payload["occupancy_count"] == 0
    assert payload["event_type"] == "NO_SUBJECT"
    service.release()

def test_audio_service_dsp_speech_classification():
    service = AudioService(use_mic=False)
    # Generate synthetic speech chunk
    chunk = service.generate_synthetic_chunk("SPEECH")
    features = service.extract_features(chunk)
    assert features["rms"] > 0.003
    assert 150.0 <= features["spectral_centroid"] <= 4000.0
    
    event, conf = service.classify_signal(features)
    assert event == "SPEECH"
    assert conf >= 0.70

def test_audio_service_dsp_alarm_classification():
    service = AudioService(use_mic=False)
    chunk = service.generate_synthetic_chunk("ALARM")
    features = service.extract_features(chunk)
    event, conf = service.classify_signal(features)
    assert event == "ALARM"
    assert conf >= 0.90

def test_audio_service_step_dispatch_contract():
    service = AudioService(use_mic=False)
    payload = service.step(simulated_event="SPEECH")
    assert payload["event_type"] == "SPEECH"
    assert payload["room_id"] == "lab_02"
    assert "rms_energy" in payload
    assert "spectral_centroid" in payload
    assert "zero_crossing_rate" in payload
    service.stop()
