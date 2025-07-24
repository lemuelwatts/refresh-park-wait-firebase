import os
import json
from datetime import datetime
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
    now = datetime.utcnow()
    last = ride.get('last_updated')
    last_api = datetime.utcfromtimestamp(last) if isinstance(last, (int, float)) else now
    return {
        'name': ride.get('name', 'Unknown Ride'),
        'wait_time': int(ride.get('wait_time')) if isinstance(ride.get('wait_time'), (int, float)) else 0,
        'is_open': bool(ride.get('is_open', False)),
        'last_api_update': last_api,
        'updated_at': now,
    }

def save_rides_batch(park_id: str, rides_data: list):
    """Save multiple rides in a single batch operation."""
    if not rides_data:
        return 0
    
    # Firestore batch can handle up to 500 operations
    batch = db.batch()
    batch_count = 0
    total_saved = 0
    
    for ride_id, ride_data in rides_data:
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
    
    print(f"✔️ {count} rides processed, {saved_count} saved for park {park_id}")
    return {'park_id': park_id, 'updated_rides': count, 'saved_rides': saved_count, 'timestamp': datetime.utcnow().isoformat()}

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
        'timestamp': datetime.utcnow().isoformat()
    }

def update_park_waits_http(event):
    params = (event.get('query', {}) if isinstance(event, dict) else {}) or {}
    if params.get('all', '').lower() == 'true':
        return update_all_parks()
    pid = params.get('park_id')
    if pid:
        return update_park_waits(pid)
    return update_all_parks()