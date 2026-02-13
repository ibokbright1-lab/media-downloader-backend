import yt_dlp
from redis_client import cache_metadata, get_cached_metadata

def extract_info(url: str):
    cached = get_cached_metadata(url)
    if cached:
        return cached

    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Filter useful formats
    formats = []
    seen = set()
    for f in info.get("formats", []):
        fid = f.get("format_id")
        if fid in seen:
            continue
        seen.add(fid)
        res = f.get("height")
        ext = f.get("ext")
        # Only standard resolutions
        if f.get("acodec") != "none" and not f.get("vcodec") or res in [360,480,720,1080] or f.get("acodec") != "none":
            formats.append({
                "format_id": fid,
                "ext": ext,
                "resolution": f"{res}p" if res else None,
                "filesize": f.get("filesize"),
                "filesize_approx": f.get("filesize_approx"),
                "tbr": f.get("tbr")
            })

    result = {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "formats": formats
    }
    cache_metadata(url, result)
    return result
