import csv
import requests
from pathlib import Path

# API Base URL (ensure the server is running on port 8000)
BASE_URL = "http://127.0.0.1:8000/api/v1"

# Path to the data directory
CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR.parent / "data"

# Dictionary to map days to the format expected by the backend schema
DAY_MAPPING = {
    "Saturday-Thursday": "Sat, Sun, Mon, Tue, Wed, Thu",
    "Sunday-Thursday": "Sun, Mon, Tue, Wed, Thu",
    "Saturday-Wednesday": "Sat, Sun, Mon, Tue, Wed"
}

def seed_doctors():
    print("👨‍⚕️ Registering doctors' data...")
    csv_file = DATA_DIR / "doctors.csv"
    
    with open(csv_file, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Map the days; if not found in the mapping, send the original value
            mapped_days = DAY_MAPPING.get(row["working_days"], row["working_days"])
            
            payload = {
                "name": row["name"],
                "specialty": row["specialty"],
                "experience_years": int(row["experience_years"]),
                "phone": row["phone"],
                "email": row["email"],
                "working_days": mapped_days, # Using the mapped days
                "start_time": row["start_time"],
                "end_time": row["end_time"]
            }
            
            # Send data to the API
            response = requests.post(f"{BASE_URL}/doctors", json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ Successfully added: {row['name']}")
            else:
                print(f"❌ Error adding {row['name']}: {response.text}")

def seed_services():
    print("\n🦷 Registering medical services...")
    csv_file = DATA_DIR / "services.csv"
    
    with open(csv_file, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            payload = {
                "name": row["name"],
                "price": float(row["price_egp"]),         # Renamed to match backend schema
                "duration": int(row["duration_minutes"]), # Renamed to match backend schema
                "doctor_specialty": row["doctor_specialty"]
            }
            
            # Send data to the API
            response = requests.post(f"{BASE_URL}/services", json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ Successfully added service: {row['name']}")
            else:
                print(f"❌ Error adding {row['name']}: {response.text}")

if __name__ == "__main__":
    try:
        # Check if the server is running first
        requests.get("http://127.0.0.1:8000/health")
        seed_doctors()
        seed_services()
        print("\n🎉 Data seeding completed successfully!")
    except requests.exceptions.ConnectionError:
        print("🚨 Server is not running! Please start Uvicorn first.")