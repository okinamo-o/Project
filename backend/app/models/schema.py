import datetime
from typing import Optional, Any
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text, Boolean, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class Room(Base):
    __tablename__ = "rooms"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    floor = Column(Integer, default=1)
    type = Column(String(64), default="classroom")  # lab, classroom, hall, server_room, etc.
    coordinates = Column(JSON, default=dict)        # 3D bounding coordinates {x, y, z, width, height, depth}
    state = Column(String(32), default="NORMAL")    # NORMAL, ATTENTION, ANOMALY, INCIDENT, OFFLINE
    room_metadata = Column("metadata", JSON, default=dict)

    devices = relationship("Device", back_populates="room", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="room")
    vision_events = relationship("VisionEvent", back_populates="room")
    audio_events = relationship("AudioEvent", back_populates="room")
    predictions = relationship("Prediction", back_populates="room")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, index=True)
    room_id = Column(String(64), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    device_type = Column(String(64), default="esp32_multisensor")  # esp32, webcam, mic, gateway
    name = Column(String(128), nullable=False)
    status = Column(String(32), default="ONLINE")                  # ONLINE, DEGRADED, OFFLINE
    device_metadata = Column("metadata", JSON, default=dict)
    last_seen = Column(DateTime(timezone=True), default=utcnow)

    room = relationship("Room", back_populates="devices")
    readings = relationship("SensorReading", back_populates="device", cascade="all, delete-orphan")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    sensor_type = Column(String(64), nullable=False, index=True)   # temperature, humidity, gas, motion, light, vibration
    value = Column(Float, nullable=False)
    unit = Column(String(16), default="")
    quality = Column(String(32), default="GOOD")

    device = relationship("Device", back_populates="readings")

    __table_args__ = (
        Index("idx_reading_dev_time_type", "device_id", "timestamp", "sensor_type"),
    )


class VisionEvent(Base):
    __tablename__ = "vision_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(64), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    event_type = Column(String(64), nullable=False)                # PERSON_DETECTED, OCCUPANCY_CHANGE, SUDDEN_MOVEMENT, OBJECT_LEFT
    confidence = Column(Float, default=1.0)
    event_metadata = Column("metadata", JSON, default=dict)        # {occupancy: 4, bboxes: [...]}

    room = relationship("Room", back_populates="vision_events")


class AudioEvent(Base):
    __tablename__ = "audio_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(64), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    event_type = Column(String(64), nullable=False)                # NORMAL, SPEECH, ALARM, IMPACT, KNOCK, SUDDEN_NOISE, MACHINE_ANOMALY
    confidence = Column(Float, default=1.0)
    event_metadata = Column("metadata", JSON, default=dict)        # {rms: 0.85, spectral_centroid: 2400}

    room = relationship("Room", back_populates="audio_events")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(64), primary_key=True, index=True)          # e.g. "INC-20260918-001"
    room_id = Column(String(64), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    type = Column(String(64), nullable=False)                      # THERMAL_RUNAWAY, GAS_HAZARD, MULTI_SIGNAL_ANOMALY, etc.
    severity = Column(String(32), default="WARNING")               # LOW, MEDIUM, WARNING, CRITICAL
    confidence = Column(Float, default=0.85)
    status = Column(String(32), default="ACTIVE")                  # ACTIVE, ACKNOWLEDGED, RESOLVED
    summary = Column(Text, default="")
    ai_explanation = Column(Text, default="")
    timeline = Column(JSON, default=list)

    room = relationship("Room", back_populates="incidents")
    evidence = relationship("IncidentEvidence", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(64), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(64), nullable=False)               # SENSOR, VISION, AUDIO, PREDICTION, HISTORICAL
    source_id = Column(String(128), default="")
    contribution = Column(Float, default=0.25)                     # Fractional weighting e.g. 0.35
    explanation = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    incident = relationship("Incident", back_populates="evidence")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(64), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    variable = Column(String(64), nullable=False)                  # temperature, gas, occupancy
    horizon = Column(String(32), default="+5m")                    # +1m, +5m, +15m
    predicted_value = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    confidence = Column(Float, default=0.80)
    model_version = Column(String(64), default="nexus-trend-v1")

    room = relationship("Room", back_populates="predictions")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    scenario = Column(String(64), nullable=False)                  # fire_hazard, gas_leak, sensor_failure
    parameters = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
