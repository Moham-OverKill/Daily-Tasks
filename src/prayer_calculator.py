"""
Prayer Time Calculator — Pure Math, Zero API Dependencies

Calculates the 5 daily Islamic prayer times + Sunrise using the user's
latitude, longitude, date, and chosen calculation method. Based on the
standard astronomical equations used by Adhan libraries worldwide.

Supported Calculation Methods:
  0 = Muslim World League (MWL)
  1 = Islamic Society of North America (ISNA)
  2 = Egyptian General Authority of Survey (Egypt)
  3 = Umm Al-Qura University, Makkah
  4 = University of Islamic Sciences, Karachi
  5 = Institute of Geophysics, University of Tehran
  6 = Shia Ithna-Ashari, Leva Institute, Qum
"""

import math
from datetime import datetime, timedelta


# ─── Calculation Method Definitions ──────────────────────────────────────────
# Each method defines Fajr angle, Isha angle, and optionally Isha offset (minutes).
# fmt: (fajr_angle, isha_angle, isha_offset_minutes_or_None)
CALCULATION_METHODS = {
    0: {"name": "Muslim World League",                 "fajr": 18.0, "isha": 17.0, "isha_min": None},
    1: {"name": "ISNA (North America)",                "fajr": 15.0, "isha": 15.0, "isha_min": None},
    2: {"name": "Egyptian General Authority",          "fajr": 19.5, "isha": 17.5, "isha_min": None},
    3: {"name": "Umm Al-Qura (Makkah)",               "fajr": 18.5, "isha":  0.0, "isha_min": 90},
    4: {"name": "University of Karachi",               "fajr": 18.0, "isha": 18.0, "isha_min": None},
    5: {"name": "Institute of Geophysics, Tehran",     "fajr": 17.7, "isha": 14.0, "isha_min": None},
    6: {"name": "Shia Ithna-Ashari (Qum)",             "fajr": 16.0, "isha": 14.0, "isha_min": None},
}


def get_method_names():
    """Return dict of {id: display_name} for all methods."""
    return {k: v["name"] for k, v in CALCULATION_METHODS.items()}


# ─── Core Astronomical Math ──────────────────────────────────────────────────

def _to_rad(deg):
    return deg * math.pi / 180.0

def _to_deg(rad):
    return rad * 180.0 / math.pi

def _fix_angle(a):
    """Normalize angle to [0, 360)."""
    a = a - 360.0 * math.floor(a / 360.0)
    return a if a >= 0 else a + 360.0

def _fix_hour(h):
    """Normalize hour to [0, 24)."""
    h = h - 24.0 * math.floor(h / 24.0)
    return h if h >= 0 else h + 24.0


def _julian_date(year, month, day):
    """Convert Gregorian date to Julian Day Number."""
    if month <= 2:
        year -= 1
        month += 12
    A = math.floor(year / 100.0)
    B = 2 - A + math.floor(A / 4.0)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5


def _sun_position(jd):
    """
    Calculate the Sun's declination and equation of time for a given Julian Day.
    Returns (declination_degrees, equation_of_time_minutes).
    """
    D = jd - 2451545.0  # Days since J2000.0

    # Mean anomaly
    g = _fix_angle(357.529 + 0.98560028 * D)
    # Mean longitude
    q = _fix_angle(280.459 + 0.98564736 * D)
    # Ecliptic longitude
    L = _fix_angle(q + 1.915 * math.sin(_to_rad(g)) + 0.020 * math.sin(_to_rad(2 * g)))

    # Obliquity of the ecliptic
    e = 23.439 - 0.00000036 * D

    # Right ascension
    RA = _to_deg(math.atan2(math.cos(_to_rad(e)) * math.sin(_to_rad(L)), math.cos(_to_rad(L)))) / 15.0

    # Equation of time (in minutes)
    eqt = q / 15.0 - _fix_hour(RA)

    # Declination
    decl = _to_deg(math.asin(math.sin(_to_rad(e)) * math.sin(_to_rad(L))))

    return decl, eqt


def _compute_asr_factor(school=0):
    """
    Asr shadow factor.
    Standard (Shafi'i): shadow = 1 × object height
    Hanafi:             shadow = 2 × object height
    """
    return 1 if school == 0 else 2


def _hour_angle(lat, decl, angle):
    """
    Compute the hour angle for a given solar angle below horizon.
    Returns hours, or None if no valid result (midnight sun / polar night).
    """
    lat_r = _to_rad(lat)
    decl_r = _to_rad(decl)
    
    cos_ha = (
        -math.sin(_to_rad(angle)) - math.sin(lat_r) * math.sin(decl_r)
    ) / (math.cos(lat_r) * math.cos(decl_r))
    
    # Clamp for high latitudes where the sun doesn't reach the angle
    if cos_ha < -1.0 or cos_ha > 1.0:
        return None
    
    return _to_deg(math.acos(cos_ha)) / 15.0


def _mid_day(eqt, lng, timezone):
    """Calculate solar noon (Dhuhr) in hours from midnight, local time."""
    # Solar noon = 12:00 - EqT - (longitude offset from timezone meridian)
    # timezone meridian = timezone * 15 degrees
    # offset = (lng - timezone * 15) / 15 hours
    return _fix_hour(12.0 - eqt - (lng - timezone * 15.0) / 15.0)


# ─── Public API ──────────────────────────────────────────────────────────────

def calculate_prayer_times(lat, lng, date=None, timezone=None, method=0, asr_school=0):
    """
    Calculate the 5 prayer times + Sunrise for a given location and date.

    Args:
        lat:        Latitude in decimal degrees (positive = North)
        lng:        Longitude in decimal degrees (positive = East)
        date:       datetime.date or None (defaults to today)
        timezone:   UTC offset in hours (e.g. 2 for UTC+2).
                    If None, auto-detected from system clock.
        method:     Calculation method ID (see CALCULATION_METHODS)
        asr_school: 0 = Standard/Shafi'i, 1 = Hanafi

    Returns:
        dict: {'Fajr': 'HH:MM', 'Sunrise': 'HH:MM', 'Dhuhr': 'HH:MM',
               'Asr': 'HH:MM', 'Maghrib': 'HH:MM', 'Isha': 'HH:MM'}
        Returns None on calculation failure.
    """
    if date is None:
        date = datetime.now().date()

    if timezone is None:
        # Auto-detect from system
        utc_offset = datetime.now().astimezone().utcoffset()
        timezone = utc_offset.total_seconds() / 3600.0

    # Validate method
    if method not in CALCULATION_METHODS:
        method = 0
    m = CALCULATION_METHODS[method]

    # Julian date at noon
    jd = _julian_date(date.year, date.month, date.day)

    # Sun position
    decl, eqt = _sun_position(jd)

    # Solar noon (Dhuhr)
    noon = _mid_day(eqt, lng, timezone)

    # ── Sunrise & Sunset (0.833° below horizon accounts for refraction + solar disc) ──
    sunrise_ha = _hour_angle(lat, decl, 0.833)
    
    if sunrise_ha is None:
        # Extreme latitude — fallback: estimate ±6h from noon
        sunrise_ha = 6.0

    sunrise = noon - sunrise_ha
    sunset  = noon + sunrise_ha

    # ── Fajr ──
    fajr_ha = _hour_angle(lat, decl, m["fajr"])
    if fajr_ha is None:
        # High-latitude fallback: 1/7th of the night before sunrise
        night_duration = 24.0 - (sunset - sunrise)
        fajr = sunrise - night_duration / 7.0
    else:
        fajr = noon - fajr_ha

    # ── Asr ──
    asr_factor = _compute_asr_factor(asr_school)
    delta = abs(lat - decl)
    asr_angle = _to_deg(math.atan(1.0 / (asr_factor + math.tan(_to_rad(delta)))))
    asr_ha = _hour_angle(lat, decl, -asr_angle)  # negative = above horizon
    
    if asr_ha is None:
        asr = noon + 3.0  # Safe fallback
    else:
        asr = noon + asr_ha

    # ── Maghrib = Sunset ──
    maghrib = sunset

    # ── Isha ──
    if m["isha_min"] is not None:
        # Fixed offset after Maghrib (e.g. Umm Al-Qura: 90 min)
        isha = maghrib + m["isha_min"] / 60.0
    else:
        isha_ha = _hour_angle(lat, decl, m["isha"])
        if isha_ha is None:
            # High-latitude fallback: 1/7th of the night after sunset
            night_duration = 24.0 - (sunset - sunrise)
            isha = sunset + night_duration / 7.0
        else:
            isha = noon + isha_ha

    # ── Dhuhr: add 1 minute safety margin ──
    dhuhr = noon + 1.0 / 60.0

    # ── Format output ──
    def fmt(hours):
        """Convert decimal hours to HH:MM string."""
        h = _fix_hour(hours)
        hour = int(h)
        minute = int(round((h - hour) * 60))
        if minute >= 60:
            hour += 1
            minute = 0
        hour = hour % 24
        return f"{hour:02d}:{minute:02d}"

    return {
        'Fajr':    fmt(fajr),
        'Sunrise': fmt(sunrise),
        'Dhuhr':   fmt(dhuhr),
        'Asr':     fmt(asr),
        'Maghrib': fmt(maghrib),
        'Isha':    fmt(isha),
    }


# ─── Self-test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test: Cairo (30.0444, 31.2357) — Egyptian method
    result = calculate_prayer_times(30.0444, 31.2357, method=2, timezone=2)
    print("Cairo (Egyptian method):")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Test: New York (40.7128, -74.0060) — ISNA method
    result = calculate_prayer_times(40.7128, -74.0060, method=1, timezone=-5)
    print("\nNew York (ISNA method):")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Test: London (51.5074, -0.1278) — MWL method
    result = calculate_prayer_times(51.5074, -0.1278, method=0, timezone=0)
    print("\nLondon (MWL method):")
    for k, v in result.items():
        print(f"  {k}: {v}")
