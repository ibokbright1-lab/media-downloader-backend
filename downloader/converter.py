import subprocess
import os


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


def merge_video_audio(video_path: str, audio_path: str, output_path: str):
    """
    Merge a video-only file and an audio-only file into a single video.
    """

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


def convert_video(input_file: str, output_file: str):
    """
    Convert video to mp4 (useful when source is webm or mkv).
    """

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


def convert_audio(input_file: str, output_file: str):
    """
    Convert audio to mp3.
    """

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


def scale_video(input_file: str, resolution: int, output_file: str):
    """
    Scale video to a specific resolution (e.g., 720p, 480p).
    """

    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vf", f"scale=-2:{resolution}",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_file
    ]

    run_command(command)
    return output_file


def cleanup_files(*files):
    """
    Remove temporary files after processing.
    """

    for file in files:
        if file and os.path.exists(file):
            os.remove(file)
