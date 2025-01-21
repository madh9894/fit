from flask import Flask, jsonify
from pymongo import MongoClient
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from threading import Thread
from datetime import datetime, timedelta
import time
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

app = Flask(__name__)
CORS(app)

# MongoDB connection URI and database name
MONGODB_URI = "mongodb+srv://googlefit:0000@googlefit.enqkg.mongodb.net/?retryWrites=true&w=majority&appName=googlefit"
DB_NAME = "google_fit"

# Define the necessary Google Fit API scopes
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.nutrition.read'
]

def authenticate_google_fit():
    """Authenticate and return Google Fit API credentials."""
    creds = None
    token_file = 'token.json'

    # Check if the token file exists
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If no valid credentials, perform the OAuth flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return creds

def fetch_data(service, data_source_id, dataset):
    """Fetch data from a specific data source."""
    try:
        response = service.users().dataSources().datasets().get(
            userId='me',
            dataSourceId=data_source_id,
            datasetId=dataset
        ).execute()
        return response.get('point', [])
    except Exception as e:
        print(f"Error fetching data for {data_source_id}: {e}")
        return []

def save_data_to_mongodb_separate(data, db_uri, db_name):
    """Save the retrieved data to MongoDB Atlas, avoiding duplicates."""
    try:
        client = MongoClient(db_uri)
        db = client[db_name]

        for data_type, data_points in data.items():
            collection = db[data_type]

            # Ensure the unique index exists (create it once)
            try:
                collection.create_index([("start_time", 1), ("end_time", 1)], unique=True)
            except Exception as e:
                print(f"Index creation failed or already exists for {data_type}: {e}")

            for point in data_points:
                # Check for duplicates before inserting
                if not collection.find_one({"start_time": point["start_time"], "end_time": point["end_time"]}):
                    try:
                        collection.insert_one(point)
                    except Exception as e:
                        print(f"Error inserting data into {data_type}: {e}")
                else:
                    print(f"Duplicate record skipped for {data_type}: {point}")
            print(f"Data for {data_type} successfully stored!")
    except Exception as e:
        print(f"Error saving data to MongoDB: {e}")

def fetch_and_store_data():
    """Fetch data from Google Fit API and store it in MongoDB."""
    print("Fetching and storing data...")
    try:
        credentials = authenticate_google_fit()
        service = build('fitness', 'v1', credentials=credentials)

        # Define the dataset (last 24 hours)
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        dataset = f"{int(one_day_ago.timestamp() * 1e9)}-{int(now.timestamp() * 1e9)}"

        # Define data sources to fetch
        data_sources = {
            "heart_rate": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm",
            "step_count": "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas",
            "calories": "derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended",
            "distance": "derived:com.google.distance.delta:com.google.android.gms:merge_distance_delta",
        }

        fit_data = {}
        for key, source in data_sources.items():
            print(f"Fetching data for {key}...")
            data_points = fetch_data(service, source, dataset)
            fit_data[key] = []
            for point in data_points:
                start_time = int(point['startTimeNanos']) / 1e9
                end_time = int(point['endTimeNanos']) / 1e9
                value = point['value'][0].get('fpVal', point['value'][0].get('intVal', None))
                fit_data[key].append({
                    "start_time": datetime.utcfromtimestamp(start_time).isoformat(),
                    "end_time": datetime.utcfromtimestamp(end_time).isoformat(),
                    "value": value
                })

        save_data_to_mongodb_separate(fit_data, MONGODB_URI, DB_NAME)
    except Exception as e:
        print(f"Error in fetch_and_store_data: {e}")

@app.route('/api/fit_vitals', methods=['GET'])
def get_fit_vitals():
    """API endpoint to fetch fitness data from MongoDB."""
    collections = ["heart_rate", "step_count", "calories", "distance"]
    result = {}
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        for collection_name in collections:
            collection = db[collection_name]
            result[collection_name] = list(collection.find({}, {"_id": 0}))
    except Exception as e:
        print(f"Error fetching data from MongoDB: {e}")
    return jsonify(result)

def run_flask():
    """Run the Flask app."""
    app.run(debug=False, use_reloader=False)

if __name__ == "__main__":
    # Initialize and start the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store_data, 'interval', minutes=3)
    scheduler.start()

    # Run Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    try:
        while True:
            time.sleep(1)  # Keep the main thread alive
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler stopped.")