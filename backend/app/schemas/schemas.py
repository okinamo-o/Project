import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class SensorReadingCreate(BaseModel):
    device_id: Optional[str] = "esp32_lab02"
    room_id: Optional[str] = "lab_02"
    sensor_type: str = Field(..., description="temperature, humidity, gas, smoke, motion, light, vibration")
    value: float
    unit: str = ""
    timestamp: Optional[datetime.datetime] = None

class SensorBatchCreate(BaseModel):
    device_id: str
    room_id: str
    readings: List[Dict[str, Any]]
    timestamp: Optional[datetime.datetime] = None

class RoomStateUpdate(BaseModel):
    state: str = Field(..., description="NORMAL, ATTENTION, ANOMALY, INCIDENT, OFFLINE")

class RoomResponse(BaseModel):
    id: str
    name: str
    floor: int
    type: str
    coordinates: Dict[str, Any]
    state: str
    room_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, validation_alias="room_metadata", serialization_alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class IncidentCreate(BaseModel):
    room_id: str
    type: str
    severity: str = "WARNING"
    confidence: float = 0.85
    summary: str
    evidence: List[Dict[str, Any]] = []

class IncidentEvidenceResponse(BaseModel):
    id: int
    incident_id: str
    source_type: str
    source_id: Optional[str] = ""
    contribution: float
    explanation: str
    timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class IncidentResponse(BaseModel):
    id: str
    room_id: str
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    type: str
    severity: str
    confidence: float
    status: str
    summary: str
    ai_explanation: Optional[str] = None
    timeline: List[Dict[str, Any]] = []
    evidence: List[IncidentEvidenceResponse] = []

    model_config = ConfigDict(from_attributes=True)

class PredictionResponse(BaseModel):
    room_id: str
    variable: str
    current_value: float
    trend_slope: float
    predicted_value: float
    horizon: str
    lower_bound: float
    upper_bound: float
    confidence: float
    explanation: str

class AIQuestionRequest(BaseModel):
    question: str
    room_id: Optional[str] = None
    incident_id: Optional[str] = None

class AIQuestionResponse(BaseModel):
    answer: str
    evidence_used: List[str] = []
    confidence: float = 0.9
    is_offline_mode: bool = False

class WhatIfSimulationRequest(BaseModel):
    scenario: str
    room_id: str = "lab_02"
    temperature_delta: float = 0.0
    gas_delta: float = 0.0
    smoke_delta: float = 0.0
    motion: bool = False
    person_present: bool = False
    acoustic_anomaly: bool = False
    disabled_sensors: List[str] = []  # e.g. ["gas", "camera", "smoke"]
