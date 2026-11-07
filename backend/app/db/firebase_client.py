import os
import logging
from concurrent.futures import ThreadPoolExecutor
import firebase_admin
from firebase_admin import credentials, db as rtdb

logger = logging.getLogger("nexus.firebase")

# Separate thread pools so incident state changes never wait behind periodic telemetry writes
_telemetry_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="firebase-telemetry")
_incident_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="firebase-incident")

_initialized = False
_warned = False
DEFAULT_RTDB_URL = "https://nexus-7ba7a-default-rtdb.europe-west1.firebasedatabase.app"

def init_firebase():
    global _initialized, _warned
    if _initialized:
        return True
    if _warned:
        return False

    if os.environ.get("TESTING") == "1":
        logger.info("Firebase sync bypassed in test mode.")
        _warned = True
        return False
        
    candidate_paths = [
        os.getenv("FIREBASE_CREDENTIALS"),
        "serviceAccountKey.json",
        "backend/serviceAccountKey.json",
        os.path.join("..", "serviceAccountKey.json"),
    ]
    
    cred_path = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            cred_path = p
            break
            
    if not cred_path:
        if not _warned:
            logger.info(f"Using direct HTTPS REST sync for Firebase Realtime DB ({DEFAULT_RTDB_URL}).")
            _warned = True
        return False
        
    try:
        firebase_admin.get_app()
    except ValueError:
        try:
            database_url = os.getenv("FIREBASE_DATABASE_URL", DEFAULT_RTDB_URL)
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            })
            logger.info(f"Firebase Admin SDK initialized successfully with Realtime DB at {database_url}.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            return False
            
    _initialized = True
    return True

def get_rtdb():
    if not _initialized:
        init_firebase()
    return rtdb if _initialized else None

def sync_telemetry_to_firebase(room_id: str, payload: dict):
    """Update room telemetry in Firebase Realtime Database (runs off the event loop)."""
    if os.environ.get("TESTING") == "1":
        return
    _telemetry_executor.submit(_sync_telemetry_blocking, room_id, payload)

def _sync_telemetry_blocking(room_id: str, payload: dict):
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"telemetry/{room_id}")
            ref.update(payload)
        else:
            # REST Fallback: directly patch Firebase RTDB over HTTP
            import urllib.request, json
            url = f"{DEFAULT_RTDB_URL}/telemetry/{room_id}.json"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
    except Exception as e:
        logger.error(f"Error syncing telemetry to Firebase: {e}")

def sync_incident_to_firebase(incident_id: str, payload: dict):
    """Save/update an incident in Firebase Realtime Database (runs off the event loop)."""
    if os.environ.get("TESTING") == "1":
        return
    _incident_executor.submit(_sync_incident_blocking, incident_id, payload)

def _sync_incident_blocking(incident_id: str, payload: dict):
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"incidents/{incident_id}")
            ref.set(payload)
        else:
            import urllib.request, json
            url = f"{DEFAULT_RTDB_URL}/incidents/{incident_id}.json"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
    except Exception as e:
        logger.error(f"Error syncing incident to Firebase: {e}")

def remove_incident_from_firebase(incident_id: str):
    """Remove a resolved incident from active incidents in Firebase Realtime Database (runs off the event loop)."""
    if os.environ.get("TESTING") == "1":
        return
    _incident_executor.submit(_remove_incident_blocking, incident_id)

def _remove_incident_blocking(incident_id: str):
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"incidents/{incident_id}")
            ref.delete()
        else:
            import urllib.request
            url = f"{DEFAULT_RTDB_URL}/incidents/{incident_id}.json"
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
    except Exception as e:
        logger.error(f"Error removing resolved incident from Firebase: {e}")

def sync_room_state_to_firebase(room_id: str, state: str, incident_id: str = None):
    """Update room condition state in Firebase Realtime Database (runs off the event loop)."""
    if os.environ.get("TESTING") == "1":
        return
    _incident_executor.submit(_sync_room_state_blocking, room_id, state, incident_id)

def _sync_room_state_blocking(room_id: str, state: str, incident_id: str = None):
    try:
        data = {"state": state}
        if incident_id:
            data["last_incident_id"] = incident_id
        database = get_rtdb()
        if database:
            ref = database.reference(f"rooms/{room_id}")
            ref.update(data)
        else:
            import urllib.request, json
            url = f"{DEFAULT_RTDB_URL}/rooms/{room_id}.json"
            req_data = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, method="PATCH", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
    except Exception as e:
        logger.error(f"Error syncing room state to Firebase: {e}")
