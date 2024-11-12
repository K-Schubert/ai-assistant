import os
from dotenv import load_dotenv
import io
import glob
from pathlib import Path
from openai import AsyncOpenAI, OpenAI
import concurrent.futures as cf
import time
import asyncio
from pydub import AudioSegment

from get_repo_root import find_repo_root
from youtube_service import youtube_service
from arxiv_service import arxiv_service

import sys
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

try:
    sys.path.remove(str(parent))
except ValueError:
    pass

from schemas import Dialogue
from functions.prompts import SINGLE_PODCAST_PROMPT

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", None)

project_root = find_repo_root()

class PodcastGenerator:
    def __init__(self):
        self.project_root = find_repo_root()
        self.data_to_process = os.path.join(self.project_root, "src/playground/input/data_to_process.txt")
        self.client = OpenAI(
            api_key=OPENAI_API_KEY
        )
        self.async_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY
            )
        self.youtube_service = youtube_service
        self.arxiv_service = arxiv_service

    def cleanup(self, *args):
        """Delete files"""
        for file in args:
            os.remove(file)

    async def transcribe_chunk(self, chunk_path: Path) -> str:
        with open(chunk_path, "rb") as audio_file:
            transcription = await self.async_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                prompt="Retrieval Augmented Generation (RAG)"
            )
        return transcription.text

    def split_audio(self, audio_file_path: Path, output_path: Path):
        audio_file = AudioSegment.from_file(audio_file_path)

        # Split the audio into chunks of 15 minutes
        for i, seg in enumerate(range(0, len(audio_file), 840_000)):
            chunk = audio_file[seg:seg + 840_000]
            chunk.export(os.path.join(output_path, f"{audio_file_path.stem}_chunk_{i}.mp3"), format="mp3")

    async def transcribe_audio_file(self, audio_file_path: Path) -> str:
        audio_file = AudioSegment.from_file(audio_file_path)
        if len(audio_file) < 840_000: # 14 minutes
            with open(audio_file_path, "rb") as audio_file:
                transcription = await self.async_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    prompt="Retrieval Augmented Generation (RAG)"
                )
            self.cleanup(audio_file_path)
            return transcription.text
        else:
            # Split the audio into chunks and transcribe each chunk
            output_path = audio_file_path.parent / "chunks"
            output_path.mkdir(exist_ok=True)
            self.split_audio(audio_file_path, output_path)

            chunk_files = list(output_path.glob(f"{audio_file_path.stem}_chunk_*.mp3"))
            transcriptions = await asyncio.gather(*[self.transcribe_chunk(chunk) for chunk in chunk_files])

            # Cleanup chunk files
            for chunk in chunk_files:
                self.cleanup(chunk)

            return " ".join(transcriptions)

    async def create_youtube_transcript(self, video_url: str) -> None:
        title = self.youtube_service.download_youtube_to_audio(video_url)
        audio_file_path = Path(os.path.join(self.project_root, "src/playground/input/youtube", f"{title}.mp3"))

        transcription = await self.transcribe_audio_file(audio_file_path)

        with open(os.path.join(self.project_root, "src/playground/input/md", f"{title}.md"), "w", encoding="utf-8") as f:
            f.write(transcription)

        return title

    async def create_arxiv_transcript(self, entry: str, max_results: int = 10) -> None:

        titles, descriptions = self.arxiv_service.search_arxiv_papers(topic=entry, max_results=max_results)
        await self.arxiv_service.parse_pdfs()

        return titles, descriptions

    def get_mp3(self, text: str, voice: str) -> bytes:

        with self.client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
        ) as response:
            with io.BytesIO() as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
                return file.getvalue()

    async def generate_audio(self, title: str, cleanup: bool = False) -> None:

        with open(os.path.join(self.project_root, "src/playground/input/md", f"{title}.md"), "rb") as f:
            text = f.read()

        async def generate_dialogue(text: str) -> Dialogue:

            messages = [{"role": "system", "content": SINGLE_PODCAST_PROMPT.format(text=text)}]

            llm_output = await self.async_client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    temperature=1,
                    top_p=0.95,
                    max_tokens=16384,
                    messages=messages,
                    response_format=Dialogue
                )

            return llm_output.choices[0].message

        llm_output = await generate_dialogue(text)

        audio = b""
        transcript = ""

        characters = 0

        with cf.ThreadPoolExecutor() as executor:
            futures = []
            for line in llm_output.parsed.dialogue:
                transcript_line = f"{line.speaker}: {line.text}"
                future = executor.submit(self.get_mp3, line.text, line.voice)
                futures.append((future, transcript_line))
                characters += len(line.text)

            for future, transcript_line in futures:
                audio_chunk = future.result()
                audio += audio_chunk
                transcript += transcript_line + "\n\n"

        output_directory = os.path.join(project_root, "src/playground/output/podcast")
        os.makedirs(output_directory, exist_ok=True)

        output_file_path = os.path.join(output_directory, f"{title}.mp3")

        with open(output_file_path, "wb") as temporary_file:
            temporary_file.write(audio)

        # Delete any files in the podcast directory that end with .mp3 and are over a day old
        if cleanup:
            for file in glob.glob(f"{output_directory}*.mp3"):
                if os.path.isfile(file) and time.time() - os.path.getmtime(file) > 24 * 60 * 60:
                    os.remove(file)

            self.cleanup(os.path.join(self.project_root, "src/playground/input/md", f"{title}.md"))

        with open(os.path.join(project_root, "src/playground/output/podcast", f"{title}.md"), "w", encoding="utf-8") as f:
            f.write(transcript)

    async def get_summary(self, title: str) -> str:
        with open(os.path.join(self.project_root, "src/playground/input/md", f"{title}.md"), "r", encoding="utf-8") as f:
            transcription = f.read()

        description = await self.async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Summarize the following text in 5-10 sentences max: {transcription}"},
            ]
        ).choices[0].message
        return description

    async def process(self, upload_to_youtube: bool = False) -> None:
        with open(self.data_to_process, "r", encoding="utf-8") as f:
            data = f.readlines()

        for entry in data:
            if "https://www.youtube" in entry:
                title = await self.create_youtube_transcript(entry)
                await self.generate_audio(title, cleanup=False)
                if upload_to_youtube:
                    continue
                    description = await self.get_summary(title)
                    self.youtube_service.upload_to_youtube(title, description)
            else:
                titles, descriptions = await self.create_arxiv_transcript(entry, max_results=10)
                #await self.generate_audio(title, cleanup=False)
                await asyncio.gather(*[self.generate_audio(title, cleanup=False) for title in titles])
                if upload_to_youtube:
                    [self.youtube_service.upload_to_youtube(title, description) for title, description in zip(titles, descriptions)]

if __name__ == "__main__":
    podcast_generator = PodcastGenerator()
    asyncio.run(podcast_generator.process(upload_to_youtube=True))
