# utils/progress.py

from typing import Dict, Any


# -----------------------------------
# Convert bytes to human readable
# -----------------------------------
def human_readable_bytes(num: float, suffix: str = "B") -> str:
    """
    Convert raw bytes into human-readable format (KB, MB, GB, etc.)
    """
    if num is None:
        return ""

    try:
        num = float(num)
    except Exception:
        return ""

    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0

    return f"{num:.1f}Y{suffix}"


# -----------------------------------
# Parse yt-dlp progress dictionary
# -----------------------------------
def parse_progress(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize progress data from yt-dlp hook.
    Returns clean, frontend-friendly values.
    """

    # ----------------------------
    # Raw values from yt-dlp
    # ----------------------------
    percent_str = d.get("_percent_str") or "0%"
    speed_str = d.get("_speed_str") or "0"
    eta_str = d.get("_eta_str") or "0"

    total_bytes = d.get("_total_bytes")
    downloaded_bytes = d.get("_downloaded_bytes")

    total_bytes_str = d.get("_total_bytes_str")
    downloaded_bytes_str = d.get("_downloaded_bytes_str")

    # ----------------------------
    # Convert percentage to float
    # ----------------------------
    try:
        progress = float(percent_str.replace("%", "").strip())
    except Exception:
        progress = 0.0

    # ----------------------------
    # Convert sizes
    # ----------------------------
    if total_bytes:
        total_size = human_readable_bytes(total_bytes)
    else:
        total_size = total_bytes_str or ""

    if downloaded_bytes:
        downloaded_size = human_readable_bytes(downloaded_bytes)
    else:
        downloaded_size = downloaded_bytes_str or ""

    # ----------------------------
    # Final structured response
    # ----------------------------
    return {
        "progress": progress,              # float (0–100)
        "speed": speed_str,                # string (e.g. 1.2MiB/s)
        "eta": eta_str,                    # string (e.g. 00:12)
        "total_size": total_size,          # string (e.g. 50.3MB)
        "downloaded_size": downloaded_size # string (e.g. 21.4MB)
    }


# -----------------------------------
# Optional: Safe fallback (if needed)
# -----------------------------------
def empty_progress() -> Dict[str, Any]:
    """
    Returns a default empty progress structure
    """
    return {
        "progress": 0.0,
        "speed": "0",
        "eta": "0",
        "total_size": "",
        "downloaded_size": ""
    }
