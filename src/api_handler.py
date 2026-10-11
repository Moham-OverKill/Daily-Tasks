"""
Global Prayer Time Handler — Location-Aware With Offline Calculation

Auto-detects user location via IP geolocation (free, no permissions needed),
stores coordinates in local config, and calculates prayer times using pure math.
Falls back to the Aladhan API only if local calculation fails.

Features:
  - Auto-detect location on first launch (IP geolocation via ip-api.com)
  - Manual city/country entry as alternative
  - 7 calculation methods (MWL, ISNA, Egypt, Umm Al-Qura, Karachi, Tehran, Qum)
  - Pure-math local calculation (zero-lag, works offline)
  - Aladhan API as a verification/fallback layer
  - Time zone auto-detection from system clock
  - Persistent location config in %APPDATA%/DailyTasks/
"""

import os
import sys
import json
import time
import urllib.parse
from datetime import datetime

from .prayer_calculator import calculate_prayer_times, CALCULATION_METHODS, get_method_names


def _http_get_json(url, params=None, headers=None, timeout=3):
    """
    Zero-dependency HTTP/HTTPS JSON fetcher.
    Uses native Win32 WinINet on Windows (zero Python networking/SSL imports at cold boot),
    with lazy-imported stdlib urllib.request fallback.
    """
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params)}"

    if sys.platform == "win32":
        try:
            import ctypes
            wininet = ctypes.windll.wininet
            wininet.InternetOpenW.restype = ctypes.c_void_p
            wininet.InternetOpenUrlW.restype = ctypes.c_void_p
            h_inet = wininet.InternetOpenW("DailyTasks/2.5", 0, None, None, 0)
            if h_inet:
                try:
                    INTERNET_FLAG_RELOAD = 0x80000000
                    INTERNET_FLAG_NO_CACHE_WRITE = 0x04000000
                    hdr_str = None
                    if headers:
                        hdr_str = "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n"
                    h_url = wininet.InternetOpenUrlW(
                        ctypes.c_void_p(h_inet), url, hdr_str, len(hdr_str) if hdr_str else 0,
                        INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE, 0
                    )
                    if h_url:
                        try:
                            chunks = []
                            buf = ctypes.create_string_buffer(4096)
                            bytes_read = ctypes.c_ulong(0)
                            while wininet.InternetReadFile(
                                ctypes.c_void_p(h_url), buf, 4096, ctypes.byref(bytes_read)
                            ) and bytes_read.value > 0:
                                chunks.append(buf.raw[:bytes_read.value])
                            if chunks:
                                return json.loads(b"".join(chunks).decode("utf-8", errors="replace"))
                        finally:
                            wininet.InternetCloseHandle(ctypes.c_void_p(h_url))
                finally:
                    wininet.InternetCloseHandle(ctypes.c_void_p(h_inet))
        except Exception:
            pass

    req_headers = {"User-Agent": "DailyTasks/2.5"}
    if headers:
        req_headers.update(headers)

    try:
        import urllib.request
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) == 200:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        pass
    return None



class PrayerTimeHandler:
    """
    Handles prayer time calculation with global location awareness.
    Primary: Local daily cache / pure-math calculation (offline, instant).
    Fallback: Aladhan API (online, cached daily).
    """
    
    def __init__(self):
        # Use APPDATA for persistent storage
        appdata = os.getenv('APPDATA', os.path.expanduser('~'))
        self.config_dir = os.path.join(appdata, 'DailyTasks', 'data')
        self.config_file = os.path.join(self.config_dir, 'location_config.json')
        self.cache_file = os.path.join(self.config_dir, 'prayers_cache.json')
        
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Location state (loaded from config or auto-detected)
        self.latitude = None
        self.longitude = None
        self.city = None
        self.country = None
        self.timezone = None  # UTC offset in hours
        self.method = 2       # Default: Egyptian General Authority
        self.asr_school = 0   # Default: Standard (Shafi'i)
        
        # Load saved location
        self._load_location_config()
            
    def get_prayer_times(self):
        """
        Get prayer times for today.
        Returns dict: {'Fajr': '05:00', 'Sunrise': '06:30', ...} or None if failed.
        
        Strategy:
          1. Check local cache first. If stamped with today's date, return immediately (0ms network cost).
          2. Ensure coordinates exist (auto-detect or fallback).
          3. Try Aladhan API to populate today's cache.
          4. Fall back to local astronomical calculation if offline.
        """
        # 1. FAST PATH: Check today's cached results first (eliminates redundant network requests)
        try:
            cached_result = self._load_cache()
            if cached_result:
                return cached_result
        except Exception as e:
            print(f"Failed to load cached prayer times: {e}")

        now = datetime.now()
        # Ensure we have a location
        if self.latitude is None or self.longitude is None:
            if not self.auto_detect_location():
                print("Location detection failed. Falling back to default coordinates (Mecca).")
                self.latitude = 21.4225
                self.longitude = 39.8262
                self.city = "Mecca"
                self.country = "Saudi Arabia"
        
        # Auto-detect timezone from system clock
        try:
            utc_offset = datetime.now().astimezone().utcoffset()
            self.timezone = utc_offset.total_seconds() / 3600.0
        except Exception:
            if self.timezone is None:
                self.timezone = 0
        
        # 2. ONLINE FETCH: Try Aladhan API when today's cache is missing
        try:
            api_result = self._fetch_from_api()
            if api_result:
                self._save_cache(api_result)
                return api_result
        except Exception as e:
            print(f"Internet fetch failed, falling back to local calculation: {e}")

        # 3. OFFLINE CALCULATION: Pure math fallback with cached coordinates
        if self.latitude is not None and self.longitude is not None:
             try:
                result = calculate_prayer_times(
                    lat=self.latitude, lng=self.longitude, date=now.date(),
                    timezone=self.timezone or 0, method=self.method or 2, asr_school=self.asr_school or 0
                )
                if result:
                    self._save_cache(result)
                    return result
             except Exception:
                pass
        
        return None
    
    # ─── Location Management ──────────────────────────────────────────────
    
    def auto_detect_location(self):
        """
        Auto-detect user's location via IP geolocation.
        Uses ip-api.com (free, no API key, 45 req/min limit).
        Returns True if successful, False otherwise.
        """
        try:
            data = _http_get_json(
                "http://ip-api.com/json/?fields=status,city,country,lat,lon,timezone,offset",
                timeout=3
            )
            if isinstance(data, dict) and data.get('status') == 'success':
                self.latitude = data['lat']
                self.longitude = data['lon']
                self.city = data.get('city', 'Unknown')
                self.country = data.get('country', 'Unknown')
                # offset is in seconds, convert to hours
                self.timezone = data.get('offset', 0) / 3600.0
                
                # Auto-select calculation method based on country
                self._auto_select_method()
                
                # Persist
                self._save_location_config()
                
                print(f"Location detected: {self.city}, {self.country} "
                      f"({self.latitude}, {self.longitude}) UTC{self.timezone:+.1f}")
                return True
                    
        except Exception as e:
            print(f"Auto-detect location failed: {e}")
        
        return False
    
    def set_location_manual(self, city, country):
        """
        Set location by city/country name using Nominatim geocoding.
        Returns True if successful, False otherwise.
        """
        try:
            # Use Nominatim (OpenStreetMap) for geocoding — free, no API key
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f"{city}, {country}",
                'format': 'json',
                'limit': 1
            }
            headers = {'User-Agent': 'DailyTasks/1.3'}
            
            results = _http_get_json(url, params=params, headers=headers, timeout=5)
            if results and isinstance(results, list):
                self.latitude = float(results[0]['lat'])
                self.longitude = float(results[0]['lon'])
                self.city = city
                self.country = country
                
                # Auto-detect timezone from system
                utc_offset = datetime.now().astimezone().utcoffset()
                self.timezone = utc_offset.total_seconds() / 3600.0
                
                self._auto_select_method()
                self._save_location_config()
                
                print(f"Location set: {city}, {country} ({self.latitude}, {self.longitude})")
                return True
                    
        except Exception as e:
            print(f"Manual location lookup failed: {e}")
        
        return False
    
    def set_location_coordinates(self, lat, lng, city="Custom", country="Custom"):
        """Directly set coordinates (for advanced users or testing)."""
        self.latitude = lat
        self.longitude = lng
        self.city = city
        self.country = country
        
        # Auto-detect timezone from system
        try:
            utc_offset = datetime.now().astimezone().utcoffset()
            self.timezone = utc_offset.total_seconds() / 3600.0
        except Exception:
            pass
        
        self._save_location_config()
        return True
    
    def set_method(self, method_id):
        """Set calculation method by ID."""
        if method_id in CALCULATION_METHODS:
            self.method = method_id
            self._save_location_config()
            return True
        return False
    
    def set_asr_school(self, school):
        """Set Asr calculation school (0=Shafi'i/Standard, 1=Hanafi)."""
        self.asr_school = school
        self._save_location_config()
    
    def get_location_display(self):
        """Return a human-readable location string for the UI."""
        if self.city and self.country:
            return f"{self.city}, {self.country}"
        elif self.latitude is not None:
            return f"{self.latitude:.2f}°, {self.longitude:.2f}°"
        return "Not set"
    
    def has_location(self):
        """Check if a location has been configured."""
        return self.latitude is not None and self.longitude is not None
    
    # ─── Auto Method Selection ────────────────────────────────────────────
    
    def _auto_select_method(self):
        """Auto-select calculation method based on detected country."""
        if not self.country:
            return
        
        country_lower = self.country.lower()
        
        # Region-to-method mapping
        north_america = {'united states', 'canada', 'usa', 'us'}
        egypt_region = {'egypt'}
        saudi_region = {'saudi arabia', 'saudi', 'qatar', 'bahrain', 'uae', 
                       'united arab emirates', 'oman', 'yemen', 'kuwait'}
        pakistan_region = {'pakistan', 'afghanistan', 'bangladesh', 'india'}
        iran_region = {'iran'}
        
        if country_lower in north_america:
            self.method = 1  # ISNA
        elif country_lower in egypt_region:
            self.method = 2  # Egyptian General Authority
        elif country_lower in saudi_region:
            self.method = 3  # Umm Al-Qura
        elif country_lower in pakistan_region:
            self.method = 4  # University of Karachi
        elif country_lower in iran_region:
            self.method = 5  # Tehran
        else:
            self.method = 0  # MWL (global default)
    
    # ─── Persistence ──────────────────────────────────────────────────────
    
    def _load_location_config(self):
        """Load saved location configuration."""
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.latitude = config.get('latitude')
            self.longitude = config.get('longitude')
            self.city = config.get('city')
            self.country = config.get('country')
            self.timezone = config.get('timezone')
            self.method = config.get('method', 2)
            self.asr_school = config.get('asr_school', 0)
            
        except Exception as e:
            print(f"Failed to load location config: {e}")
    
    def _save_location_config(self):
        """Persist location configuration."""
        try:
            config = {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'city': self.city,
                'country': self.country,
                'timezone': self.timezone,
                'method': self.method,
                'asr_school': self.asr_school,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save location config: {e}")
    
    # ─── API Fallback ─────────────────────────────────────────────────────
    
    def _fetch_from_api(self):
        """Fallback: Fetch today's prayer times from Aladhan API using coordinates."""
        if self.latitude is None:
            return None
        
        try:
            url = "http://api.aladhan.com/v1/timings"
            params = {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'method': self._aladhan_method_id(),
                'date_or_timestamp': int(time.time())
            }
            
            data = _http_get_json(url, params=params, timeout=3)
            if isinstance(data, dict) and 'data' in data and 'timings' in data['data']:
                timings = data['data']['timings']
                # Clean timezone suffixes like "(EEST)"
                clean = {}
                for prayer, time_str in timings.items():
                    clean[prayer] = time_str.split()[0]
                return clean
                    
        except Exception as e:
            print(f"Aladhan API fallback failed: {e}")
        
        return None
    
    def _aladhan_method_id(self):
        """Map internal method ID to Aladhan API method number."""
        # Our IDs roughly align with Aladhan's:
        # 0=MWL(3), 1=ISNA(2), 2=Egypt(5), 3=UmmAlQura(4), 4=Karachi(1), 5=Tehran(7), 6=Qum(0)
        mapping = {0: 3, 1: 2, 2: 5, 3: 4, 4: 1, 5: 7, 6: 0}
        return mapping.get(self.method, 3)
    
    # ─── Legacy Cache (kept for backward compatibility) ───────────────────
    
    def _load_cache(self):
        """Load today's cached prayer times."""
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Use strict YYYY-MM-DD validation
            today = datetime.now().strftime('%Y-%m-%d')
            if cache_data.get('date') == today:
                return cache_data.get('timings', {})
            
            return {} # Cache is stale (for a different day)
        except Exception as e:
            print(f"Cache load error: {e}")
            return {}

    def _save_cache(self, timings):
        """Save timings to persistent cache with daily date stamp."""
        try:
            cache_data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'timings': timings
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=4)
        except Exception as e:
            print(f"Failed to save cache: {e}")
