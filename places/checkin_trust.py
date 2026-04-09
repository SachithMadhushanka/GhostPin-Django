import hashlib
import logging
from datetime import timedelta

import exifread
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Points by trust tier ──────────────────────────────────
BASE_POINTS      = 10
PHOTO_POINTS     = 3   # photo alone proves less — reduced from 5
EXIF_GPS_POINTS  = 4   # GPS in EXIF matches place coordinates
EXIF_TIME_POINTS = 2   # EXIF timestamp within ±12h of submission
LOCATION_POINTS  = 3   # client GPS verified flag

MAX_EXIF_TIME_DELTA_HOURS = 12
MAX_GPS_DISTANCE_KM       = 0.5   # 500m


def compute_photo_hash(image_file) -> str:
    """
    Return SHA-256 hex digest of the raw file bytes.
    Call before saving the file. Resets the file pointer to 0 when done.
    """
    image_file.seek(0)
    h = hashlib.sha256()
    for chunk in iter(lambda: image_file.read(8192), b""):
        h.update(chunk)
    image_file.seek(0)
    return h.hexdigest()


def extract_exif(image_file) -> dict | None:
    """
    Extract GPS coordinates and original timestamp from an image's EXIF data.

    Returns a dict:
        {
            "gps_lat":   float | None,
            "gps_lng":   float | None,
            "timestamp": datetime | None,
        }
    Returns None on any read or parse error.
    """
    try:
        image_file.seek(0)
        tags = exifread.process_file(
            image_file, stop_tag="GPS GPSLongitude", details=False
        )
        image_file.seek(0)
    except Exception as exc:
        logger.debug("EXIF read failed: %s", exc)
        return None

    result = {"gps_lat": None, "gps_lng": None, "timestamp": None}

    # ── GPS coordinates ───────────────────────────────────
    try:
        lat_tag = tags.get("GPS GPSLatitude")
        lng_tag = tags.get("GPS GPSLongitude")
        lat_ref = str(tags.get("GPS GPSLatitudeRef",  "N"))
        lng_ref = str(tags.get("GPS GPSLongitudeRef", "E"))

        if lat_tag and lng_tag:
            result["gps_lat"] = _dms_to_decimal(lat_tag.values, lat_ref)
            result["gps_lng"] = _dms_to_decimal(lng_tag.values, lng_ref)
    except Exception:
        pass

    # ── Original timestamp ────────────────────────────────
    try:
        ts_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        if ts_tag:
            from datetime import datetime
            result["timestamp"] = datetime.strptime(str(ts_tag), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass

    return result


def _dms_to_decimal(dms_values, ref) -> float:
    """Convert a degrees/minutes/seconds IFDRational list to signed decimal degrees."""
    def to_float(v):
        return float(v.num) / float(v.den) if v.den else 0.0

    deg = to_float(dms_values[0])
    mn  = to_float(dms_values[1])
    sec = to_float(dms_values[2])
    decimal = deg + mn / 60.0 + sec / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in kilometres between two lat/lng points."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_trust_score(checkin, place, submitted_at=None) -> dict:
    """
    Compute a trust score for a check-in based on available evidence.

    Scoring breakdown (max 5 raw points → 'verified' tier):
      +1  photo present
      +2  EXIF GPS within 500m of place
      +1  EXIF timestamp within ±12h of submission time
      +1  client-side GPS verified flag

    Tier mapping:
      score 0–1  → 'unverified'  → BASE_POINTS only
      score 2–3  → 'likely'      → BASE_POINTS + PHOTO_POINTS + EXIF_TIME_POINTS
      score 4+   → 'verified'    → all bonus points

    Returns:
        {
            "score":     int,
            "tier":      'unverified' | 'likely' | 'verified',
            "points":    int,
            "exif_info": dict | None,
            "flags":     list[str],
        }
    """
    score     = 0
    flags     = []
    exif_info = None

    if submitted_at is None:
        submitted_at = timezone.now()

    # ── 1. Photo present ──────────────────────────────────
    if checkin.photo_proof:
        score += 1
        flags.append("photo_present")

        # ── 2. EXIF analysis ──────────────────────────────
        try:
            checkin.photo_proof.seek(0)
            exif_info = extract_exif(checkin.photo_proof)
        except Exception:
            exif_info = None

        if exif_info:
            # ── 2a. GPS proximity ────────────────────────
            if exif_info["gps_lat"] is not None and exif_info["gps_lng"] is not None:
                dist = _haversine_km(
                    exif_info["gps_lat"],
                    exif_info["gps_lng"],
                    float(place.latitude),
                    float(place.longitude),
                )
                if dist <= MAX_GPS_DISTANCE_KM:
                    score += 2
                    flags.append(f"exif_gps_match ({dist:.0f}m)")
                else:
                    flags.append(f"exif_gps_mismatch ({dist:.0f}m away)")
            else:
                flags.append("exif_no_gps")

            # ── 2b. Timestamp plausibility ───────────────
            if exif_info["timestamp"] is not None:
                naive = exif_info["timestamp"]
                aware = (
                    timezone.make_aware(naive)
                    if timezone.is_naive(naive)
                    else naive
                )
                delta_hours = abs((submitted_at - aware).total_seconds()) / 3600
                if delta_hours <= MAX_EXIF_TIME_DELTA_HOURS:
                    score += 1
                    flags.append(f"exif_time_ok (Δ{delta_hours:.1f}h)")
                else:
                    flags.append(f"exif_time_mismatch (Δ{delta_hours:.1f}h)")
            else:
                flags.append("exif_no_timestamp")

    # ── 3. Client GPS verified ────────────────────────────
    if checkin.location_verified:
        score += 1
        flags.append("client_gps")

    # ── 4. Tier + points ──────────────────────────────────
    if score >= 4:
        tier   = "verified"
        points = BASE_POINTS + PHOTO_POINTS + EXIF_GPS_POINTS + EXIF_TIME_POINTS + LOCATION_POINTS
    elif score >= 2:
        tier   = "likely"
        points = BASE_POINTS + PHOTO_POINTS + EXIF_TIME_POINTS
    else:
        tier   = "unverified"
        points = BASE_POINTS

    return {
        "score":     score,
        "tier":      tier,
        "points":    points,
        "exif_info": exif_info,
        "flags":     flags,
    }