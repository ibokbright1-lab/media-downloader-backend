# downloader/converter.py

import subprocess
import os


# ----------------------------
# Core Runner
# ----------------------------
def run_command(command: list):
    """
    Run an ffmpeg command safely and raise error if it fails.
    """
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {process.stderr}")

    return process.stdout


# ----------------------------
# Merge Video + Audio
# ----------------------------
def merge_video_audio(video_path: str, audio_path: str, output_path: str):
    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        output_path
    ]

    run_command(command)
    return output_path


# ----------------------------
# Convert Video to MP4
# ----------------------------
def convert_video(input_file: str, output_file: str):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-c:v", "libx264",
        "-c:a", "aac",
        output_file
    ]

    run_command(command)
    return output_file


# ----------------------------
# Convert Audio (Generic)
# ----------------------------
def convert_audio(input_file: str, output_file: str):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        output_file
    ]

    run_command(command)
    return output_file


# ----------------------------
# ✅ REQUIRED FIX (THIS WAS MISSING)
# ----------------------------
def convert_to_mp3(input_file: str, output_file: str, bitrate="192k"):
    """
    Explicit MP3 converter (used by download.py)
    """

    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", bitrate,
        "-ar", "44100",
        "-ac", "2",
        output_file
    ]

    run_command(command)
    return output_file


# ----------------------------
# Scale Video (CRITICAL FEATURE)
# ----------------------------
def scale_video(input_file: str, resolution: int, output_file: str):
    """
    Scale video to target resolution (this enables your
    'generate missing formats' feature)
    """

    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vf", f"scale=-2:{resolution}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_file
    ]

    run_command(command)
    return output_file


# ----------------------------
# Cleanup
# ----------------------------
def cleanup_files(*files):
    for file in files:
        if file and os.path.exists(file):
            os.remove(file)
