import os
import random
import glob
import yt_dlp
from moviepy.editor import ImageClip, AudioFileClip
import google_auth_oauthlib.flow
import googleapiclient.discovery
from pathlib import Path

from get_repo_root import find_repo_root

class YoutubeService:

    def __init__(self):
        self.project_root = find_repo_root()
        self.video_output_path = os.path.join(self.project_root, "src/playground/input/youtube")
        self.audio_input_path = os.path.join(self.project_root, "src/playground/output/podcast")

    def download_youtube_to_audio(self, video_url: str) -> str:
        ydl_opts = {
            'format': 'bestaudio/best',  # Select the best available audio format
            'outtmpl': f'{self.video_output_path}/%(title)s.%(ext)s',  # Set output file name and location
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
                    'preferredcodec': 'mp3',  # Convert audio to MP3
                    'preferredquality': '192',  # Set audio quality (192 kbps)
                }
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(video_url, download=True)
            title = result.get('title', None)

        return title

    def create_video_from_image_and_audio(self, image_path: Path, audio_path: Path, output_path: Path, duration: float = None):
        # Load the image and audio files
        image_clip = ImageClip(image_path)
        audio_clip = AudioFileClip(audio_path)

        # Set duration based on audio duration if not specified
        if duration is None:
            duration = audio_clip.duration

        # Set duration and add audio to the image clip
        video = image_clip.set_duration(duration)
        video = video.set_audio(audio_clip)

        # Save video
        video.write_videofile(output_path, fps=1)

    def upload_to_youtube_util(self, video_file_path: Path, title: str, description: str, category_id: str = "28", privacy_status: str = "public") ->  None:

        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        scopes = ["https://www.googleapis.com/auth/youtube.upload"]

        project_root = find_repo_root()

        # OAuth authentication
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        os.path.join(project_root, "client_secret.apps.googleusercontent.com.json"), scopes)

        credentials = flow.run_local_server(port=0)
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

        # Request body for video upload
        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }

        # Upload video
        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=googleapiclient.http.MediaFileUpload(str(video_file_path))  # Convert Path to str
        )
        response = request.execute()
        print(f"Upload completed. Video ID: {response['id']}")

    def upload_to_youtube(self, title: str, description: str) -> None:

        image_files = glob.glob(os.path.join(self.project_root, "src/playground/output/images", "*.png"))
        image_path = image_files[random.randint(0, len(image_files)-1)]
        audio_path = os.path.join(self.project_root, "src/playground/output/podcast", f"{title}.mp3")
        output_path = os.path.join(self.project_root, "src/playground/output/youtube", f"{title}.mp4")

        self.create_video_from_image_and_audio(image_path, audio_path, output_path)

        self.upload_to_youtube_util(output_path, title, description, category_id="28", privacy_status="public")

youtube_service = YoutubeService()
