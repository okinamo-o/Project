# NEXUS Relational Schema & Database Architecture

## 1. Engine & Strategy

NEXUS uses **SQLAlchemy 2.0 Async ORM** supporting dual backends:
1. **Local SQLite (`sqlite+aiosqlite:///./nexus.db`)**: Active by default for immediate, zero-friction local execution without requiring Docker Desktop to be running.
2. **PostgreSQL 15 (`postgresql+asyncpg://...`)**: Seamlessly supported via Docker Compose (`docker-compose.yml`) for multi-client concurrency.

---

## 2. Normalized Entity Relationship Model

```
┌─────────────┐       1:N       ┌─────────────┐       1:N       ┌─────────────────┐
│    rooms    ├─────────────────┤   devices   ├─────────────────┤ sensor_readings │
└──────┬──────┘                 └─────────────┘                 └─────────────────┘
       │
       │ 1:N
       ├────────────────────────┐
       │                        │
       ▼                        ▼
┌──────────────┐         ┌──────────────┐
│  incidents   │         │ vision_events│
└──────┬───────┘         └──────────────┘
       │
       │ 1:N
       ▼
┌───────────────────┐
│ incident_evidence │
└───────────────────┘
```

---

## 3. Core Tables

### `rooms`
* `id` (VARCHAR 64, PK)
* `name` (VARCHAR 128)
* `floor` (INTEGER)
* `type` (VARCHAR 64): `classroom`, `lab`, `hall`, `server_room`, `storage_room`, `entrance`, `exit`
* `coordinates` (JSON): 3D coordinates $\{x, y, z, w, h, d\}$
* `state` (VARCHAR 32): `NORMAL`, `ATTENTION`, `ANOMALY`, `INCIDENT`, `OFFLINE`
* `metadata` (JSON)

### `devices`
* `id` (VARCHAR 64, PK)
* `room_id` (VARCHAR 64, FK -> `rooms.id`)
* `device_type` (VARCHAR 64)
* `name` (VARCHAR 128)
* `status` (VARCHAR 32): `ONLINE`, `DEGRADED`, `OFFLINE`
* `last_seen` (DATETIME)

### `sensor_readings`
* `id` (INTEGER, PK, Auto-increment)
* `device_id` (VARCHAR 64, FK -> `devices.id`)
* `timestamp` (DATETIME, Indexed)
* `sensor_type` (VARCHAR 64): `temperature`, `humidity`, `gas`, `motion`, `light`, `vibration`
* `value` (FLOAT)
* `unit` (VARCHAR 16)
* `quality` (VARCHAR 32)
* Index: `(device_id, timestamp, sensor_type)`

### `vision_events`
* `id` (INTEGER, PK)
* `room_id` (VARCHAR 64, FK -> `rooms.id`)
* `timestamp` (DATETIME)
* `event_type` (VARCHAR 64)
* `confidence` (FLOAT)
* `metadata` (JSON): `occupancy_count`, `bounding_boxes`

### `audio_events`
* `id` (INTEGER, PK)
* `room_id` (VARCHAR 64, FK -> `rooms.id`)
* `timestamp` (DATETIME)
* `event_type` (VARCHAR 64)
* `confidence` (FLOAT)
* `metadata` (JSON): `rms_energy`, `spectral_centroid`, `zero_crossing_rate`

### `incidents`
* `id` (VARCHAR 64, PK)
* `room_id` (VARCHAR 64, FK -> `rooms.id`)
* `created_at` (DATETIME)
* `resolved_at` (DATETIME, Nullable)
* `type` (VARCHAR 64)
* `severity` (VARCHAR 32): `LOW`, `MEDIUM`, `WARNING`, `CRITICAL`
* `confidence` (FLOAT)
* `status` (VARCHAR 32): `ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`
* `summary` (TEXT)
* `timeline` (JSON)

### `incident_evidence`
* `id` (INTEGER, PK)
* `incident_id` (VARCHAR 64, FK -> `incidents.id`)
* `source_type` (VARCHAR 64): `SENSOR`, `VISION`, `AUDIO`, `PREDICTION`, `HISTORICAL`
* `source_id` (VARCHAR 128)
* `contribution` (FLOAT): Fractional attribution weight ($0.0 - 1.0$)
* `explanation` (TEXT)
* `timestamp` (DATETIME)
