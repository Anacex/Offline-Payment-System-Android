import requests
import traceback

BASE_URL = "http://127.0.0.1:8001"

try:
    print("Testing signup endpoint...")
    data = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "SecurePass@123",
        "phone": "+923001234567"
    }
    
    response = requests.post(f"{BASE_URL}/auth/signup", json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"Response Text: {response.text}")
    
    if response.status_code == 201:
        print("SUCCESS: Signup worked!")
        print(response.json())
    else:
        print(f"FAILED: Status {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
