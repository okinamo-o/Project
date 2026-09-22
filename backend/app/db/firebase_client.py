import os
import logging
import firebase_admin
from firebase_admin import credentials, db as rtdb

logger = logging.getLogger("nexus.firebase")

_initialized = False
DEFAULT_RTDB_URL = "https://nexus-7ba7a-default-rtdb.europe-west1.firebasedatabase.app"

def init_firebase():
    global _initialized
    if _initialized:
        return True

    if os.environ.get("TESTING") == "1":
        logger.info("Firebase sync bypassed in test mode.")
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
        logger.warning("Firebase credentials not found. Firebase syncing will be disabled.")
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
    """Update room telemetry in Firebase Realtime Database."""
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"telemetry/{room_id}")
            ref.update(payload)
    except Exception as e:
        logger.error(f"Error syncing telemetry to Firebase: {e}")

def sync_incident_to_firebase(incident_id: str, payload: dict):
    """Save/update an incident in Firebase Realtime Database."""
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"incidents/{incident_id}")
            ref.set(payload)
    except Exception as e:
        logger.error(f"Error syncing incident to Firebase: {e}")

def sync_room_state_to_firebase(room_id: str, state: str, incident_id: str = None):
    """Update room condition state in Firebase Realtime Database."""
    try:
        database = get_rtdb()
        if database:
            ref = database.reference(f"rooms/{room_id}")
            data = {"state": state}
            if incident_id:
                data["last_incident_id"] = incident_id
            ref.update(data)
    except Exception as e:
        logger.error(f"Error syncing room state to Firebase: {e}")
