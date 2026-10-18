#!/usr/bin/env bash
echo "Arret des services NEXUS..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true
pkill -f "backend.app.main" 2>/dev/null || true
pkill -f "telemetry_generator.py" 2>/dev/null || true
pkill -f "vision_service.py" 2>/dev/null || true
pkill -f "audio_service.py" 2>/dev/null || true
echo "Services NEXUS arretes."
