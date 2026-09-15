import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.prayer_calculator import calculate_prayer_times
from datetime import date

# London, UK (MWL Method)
# March 21, 2026
res = calculate_prayer_times(
    lat=51.5074, 
    lng=-0.1278, 
    date=date(2026, 3, 21), 
    timezone=0, 
    method=0
)

print(f"Fajr: {res['Fajr']}")
print(f"Dhuhr: {res['Dhuhr']}")
print(f"Asr: {res['Asr']}")
print(f"Maghrib: {res['Maghrib']}")
print(f"Isha: {res['Isha']}")
