import os
import json
from datetime import datetime, timedelta, timezone
import requests
import firebase_admin
from firebase_admin import credentials, firestore

service_key = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
project_id = os.environ.get('FIREBASE_PROJECT_ID')

if not service_key or not project_id:
    raise RuntimeError("Missing FIREBASE_SERVICE_ACCOUNT_KEY or FIREBASE_PROJECT_ID")

# Parse JSON from env var
cred = credentials.Certificate(json.loads(service_key))
# Initialize with explicit cert and project ID
firebase_admin.initialize_app(cred, {'projectId': project_id})

# Use firestore from firebase_admin instead of google.cloud
db = firestore.client()

PARK_IDS = ["5", # EPCOT
            "6", # Magic Kingdom
            "7", # Disney's Hollywood Studios
            "8"] # Disney's Animal Kingdom

def fetch_park_data(park_id: str):
    url = f"https://queue-times.com/parks/{park_id}/queue_times.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get('lands'):
        raise ValueError("Invalid API response: missing lands")
    return data

def process_ride(ride: dict) -> dict:
    now = datetime.now(timezone.utc)
    last = ride.get('last_updated')
    last_api = datetime.fromtimestamp(last, tz=timezone.utc) if isinstance(last, (int, float)) else now
    return {
        'name': ride.get('name', 'Unknown Ride'),
        'wait_time': int(ride.get('wait_time')) if isinstance(ride.get('wait_time'), (int, float)) else 0,
        'is_open': bool(ride.get('is_open', False)),
        'last_api_update': last_api,
        'updated_at': now,
    }

def get_existing_rides(park_id: str) -> dict:
    """Get all existing rides for a park."""
    rides_ref = db.collection('parks').document(park_id).collection('rides')
    docs = rides_ref.stream()
    existing = {}
    for doc in docs:
        existing[doc.id] = doc.to_dict()
    return existing

def rides_data_changed(existing_data: dict, new_data: dict) -> bool:
    """Check if ride data has meaningfully changed."""
    if not existing_data:
        return True
    
    # Compare key fields that matter for wait times
    key_fields = ['wait_time', 'is_open', 'name']
    for field in key_fields:
        if existing_data.get(field) != new_data.get(field):
            return True
    
    return False

def save_rides_batch(park_id: str, rides_data: list):
    """Save multiple rides in a single batch operation, only if data changed."""
    if not rides_data:
        return 0
    
    # Get existing data to compare
    existing_rides = get_existing_rides(park_id)
    
    # Filter to only rides that need updating
    rides_to_update = []
    for ride_id, ride_data in rides_data:
        existing = existing_rides.get(ride_id, {})
        if rides_data_changed(existing, ride_data):
            rides_to_update.append((ride_id, ride_data))
    
    if not rides_to_update:
        print(f"✓ No changes needed for park {park_id}")
        return 0
    
    # Firestore batch can handle up to 500 operations
    batch = db.batch()
    batch_count = 0
    total_saved = 0
    
    for ride_id, ride_data in rides_to_update:
        doc_ref = db.collection('parks').document(park_id).collection('rides').document(ride_id)
        batch.set(doc_ref, ride_data)
        batch_count += 1
        
        # Commit batch when we reach 500 operations or at the end
        if batch_count >= 500:
            batch.commit()
            total_saved += batch_count
            print(f"✓ Batch committed: {batch_count} rides for park {park_id}")
            batch = db.batch()  # Create new batch
            batch_count = 0
    
    # Commit any remaining operations
    if batch_count > 0:
        batch.commit()
        total_saved += batch_count
        print(f"✓ Final batch committed: {batch_count} rides for park {park_id}")
    
    return total_saved

def update_park_waits(park_id: str):
    print(f"Fetching park {park_id} data…")
    data = fetch_park_data(park_id)
    
    # Collect all ride data for batch processing
    rides_to_save = []
    count = 0
    
    for land in data['lands']:
        for ride in land.get('rides', []):
            rid = str(ride.get('id'))
            if not rid:
                continue
            rd = process_ride(ride)
            rides_to_save.append((rid, rd))
            count += 1
    
    # Save all rides in batch(es)
    saved_count = save_rides_batch(park_id, rides_to_save)
    
    print(f"✔️ {count} rides processed, {saved_count} actually updated for park {park_id}")
    return {'park_id': park_id, 'updated_rides': count, 'saved_rides': saved_count, 'timestamp': datetime.now(timezone.utc).isoformat()}

def update_all_parks():
    results = []
    total_processed = 0
    total_saved = 0
    failed_parks = []
    
    for pid in PARK_IDS:
        try:
            r = update_park_waits(pid)
            total_processed += r['updated_rides']
            total_saved += r['saved_rides']
            results.append(r)
        except Exception as e:
            print(f"✗ Park {pid} update failed: {e}")
            failed_parks.append({'park_id': pid, 'error': str(e)})
    
    return {
        'success': len(failed_parks) == 0,
        'total_processed': total_processed,
        'total_saved': total_saved,
        'parks_updated': len(results),
        'parks_failed': len(failed_parks),
        'results': results,
        'failures': failed_parks,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

def update_park_waits_http(event):
    params = (event.get('query', {}) if isinstance(event, dict) else {}) or {}
    if params.get('all', '').lower() == 'true':
        return update_all_parks()
    pid = params.get('park_id')
    if pid:
        return update_park_waits(pid)
    return update_all_parks()