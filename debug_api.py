from src.api_handler import PrayerTimeHandler
import requests

print("Testing PrayerTimeHandler...")
try:
    pt = PrayerTimeHandler()
    print(f"Handler initialized: {pt}")
    
    # Test 1: Standard Call
    print("Attempting to fetch prayer times...")
    result = pt.get_prayer_times()
    
    if result:
        print("Success!")
        print(result)
    else:
        print("Failed to get result (returned None).")
        
    # Manual Request Check
    print("\n--- Manual Request Check ---")
    url = "http://api.aladhan.com/v1/timingsByCity" # Verify if I used wrong endpoint in class vs debug
    # Wait, in the class I used: http://api.aladhan.com/v1/timings/{date}
    # Let's try that exact one
    from datetime import datetime
    date_str = datetime.now().strftime("%d-%m-%Y")
    url2 = f"http://api.aladhan.com/v1/timings/{date_str}"
    
    params = {"city": "Cairo", "country": "Egypt", "method": 5}
    print(f"GET {url2} with params {params}")
    
    r = requests.get(url2, params=params)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text[:200]}...") # Print first 200 chars

except Exception as e:
    print(f"CRITICAL EXCEPTION: {e}")
