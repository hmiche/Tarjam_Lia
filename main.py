
import json
import logging
import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
from configuration.config import Config
from mytypes.transcript_type import TranscriptType
from downloader.downloader import Downloader
from utils import time_utils
from writer.writer import Writer
from typing import Any, Generator, Union
from tqdm import tqdm
from recognizers.wit_recognizer import WitRecognizer
from utils import file_utils
from wit import file_utils as wit_file_utils
import csv
import logging
import os
import random
import re
import sys
import string    
import random # define the random module  
from os import path


LANGUAGE_API_KEYS = {
    'AR': os.getenv('WIT_API_KEY_ARABIC'),
    # Add more languages and API keys as needed
}


def is_wav_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            return file.read(4) == b'RIFF'
    except IOError:
        return False

def process_local(
    path: Path,
    model: 'WhisperModel',
    config: Config,
    progress_info: dict,
) -> Generator[tuple[dict[str, int], list[list[dict[str, Union[str, float]]]]], None, None]:
    filtered_media_files: list[Path] = file_utils.filter_media_files([path] if path.is_file() else path.iterdir())
    files: list[dict[str, Any]] = [{'file_name': file.name, 'file_path': file} for file in filtered_media_files]

    for idx, file in enumerate(tqdm(files, desc='Local files')):
        new_progress_info = progress_info.copy()
        new_progress_info.update(
            {
                'inner_total': len(files),
                'inner_current': idx + 1,
                'inner_status': 'processing',
                'progress': 0.0,
                'remaining_time': None,
            }
        )
        yield new_progress_info, []

        writer = Writer()
        if config.input.skip_if_output_exist and writer.is_output_exist(Path(file['file_name']).stem, config.output):
            new_progress_info['inner_status'] = 'completed'
            yield new_progress_info, []

            continue

        file_path = str(file['file_path'].absolute())

        if config.use_wit():
            wav_file_path = str(wit_file_utils.convert_to_wav(file['file_path']).absolute())
            recognize_generator = WitRecognizer(verbose=config.input.verbose).recognize(wav_file_path, config.wit)
        # else:
        #     recognize_generator = WhisperRecognizer(verbose=config.input.verbose).recognize(
        #         file_path,
        #         model,
        #         config.whisper,
        #     )

        while True:
            try:
                new_progress_info.update(next(recognize_generator))
                yield new_progress_info, []
            except StopIteration as exception:
                segments = exception.value
                break

        if config.use_wit() and file['file_path'].suffix != '.wav':
            Path(wav_file_path).unlink(missing_ok=True)

        writer.write_all(Path(file['file_name']).stem, segments, config.output)

        for segment in segments:
            segment['url'] = f"file://{file_path}&t={int(segment['start'])}"
            segment['file_path'] = file_path

        new_progress_info['inner_status'] = 'completed'
        new_progress_info['progress'] = 100.0
        yield new_progress_info, writer.compact_segments(segments, config.output.min_words_per_segment)

def farrigh(config):

    prepare_output_dir(config.output.output_dir)
    model = None
    segments = []
  
    for idx, item in enumerate(tqdm(config.input.urls_or_paths, desc='URLs or local paths')):
            progress_info = {
                'outer_total': len(config.input.urls_or_paths),
                'outer_current': idx + 1,
                'outer_status': 'processing',
            }

            if Path(item).exists():
                file_or_folder = Path(item)
                for progress_info, local_elements_segments in process_local(file_or_folder, model, config, progress_info):
                    segments.extend(local_elements_segments)

        
    #     progress_info['outer_status'] = 'completed'
    #     yield progress_info

    # write_output_sample(segments, config.output)

def transcribe_file(file_path, language_sign):

    wit_api_key = LANGUAGE_API_KEYS.get(language_sign.upper())
    if not wit_api_key:
        print(f"API key not found for language: {language_sign}")
        return
    config = Config(
        urls_or_paths=[str(file_path)],
        skip_if_output_exist=False,
        playlist_items="",
        verbose=False,
        model_name_or_path="",
        task="",
        language="",
        use_faster_whisper=False,
        beam_size=0,
        ct2_compute_type="",
        wit_client_access_tokens=[wit_api_key],
        max_cutting_duration=5,
        min_words_per_segment=1,
        save_files_before_compact=False,
        save_yt_dlp_responses=False,
        output_sample=0,
        output_formats=[TranscriptType.TXT, TranscriptType.SRT],
        output_dir=str(file_path.parent),
    )

    if not is_wav_file(file_path):
        print(f"Ski")
    else:
        farrigh(config)
       

def download_youtube_audio(youtube_url):
    S = 10  # number of characters in the string.  
    ran = ''.join(random.choices(string.ascii_uppercase + string.digits, k = S))   
     
    output_path = Path(__file__).parent / 'downloads' / ran / '%(id)s.%(ext)s'
   
    command = ['yt-dlp', '-f', 'bestaudio+bestvideo', '-o', str(output_path), youtube_url]
    subprocess.run(command, check=True)
    audio_file = next(Path(__file__).parent.glob('downloads/*.wav'))
    return audio_file

def prepare_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)




def write_output_sample(segments: list[dict[str, Union[str, float]]], output: Config.Output) -> None:
    if output.output_sample == 0:
        return

    random.shuffle(segments)

    with open(os.path.join(output.output_dir, 'sample.csv'), 'w') as fp:
        writer = csv.DictWriter(fp, fieldnames=['start', 'end', 'text', 'url', 'file_path'])
        writer.writeheader()

        for segment in segments[: output.output_sample]:
            segment['start'] = time_utils.format_timestamp(segment['start'], include_hours=True, decimal_marker=',')
            segment['end'] = time_utils.format_timestamp(segment['end'], include_hours=True, decimal_marker=',')
            writer.writerow(segment)


def process_url(
    url: str,
    model: 'WhisperModel',
    config: Config,
    progress_info: dict,
) -> Generator[tuple[dict[str, int], list[list[dict[str, Union[str, float]]]]], None, None]:
    url_data = Downloader(playlist_items=config.input.playlist_items, output_dir=config.output.output_dir).download(
        url,
        save_response=config.output.save_yt_dlp_responses,
    )

    if '_type' in url_data and url_data['_type'] == 'playlist':
        url_data = url_data['entries']
    else:
        url_data = [url_data]

    for idx, element in enumerate(tqdm(url_data, desc='URL elements')):
        if not element:
            continue

        new_progress_info = progress_info.copy()
        new_progress_info.update(
            {
                'inner_total': len(url_data),
                'inner_current': idx + 1,
                'inner_status': 'processing',
                'progress': 0.0,
                'remaining_time': None,
            }
        )
        yield new_progress_info, []

        writer = Writer()
        if config.input.skip_if_output_exist and writer.is_output_exist(element['id'], config.output):
            new_progress_info['inner_status'] = 'completed'
            yield new_progress_info, []

            continue

        file_path = os.path.join(config.output.output_dir, f"{element['id']}.wav")

        if config.use_wit():
            recognize_generator = WitRecognizer(verbose=config.input.verbose).recognize(file_path, config.wit)
   
        while True:
            try:
                new_progress_info.update(next(recognize_generator))
                yield new_progress_info, []
            except StopIteration as exception:
                segments = exception.value
                break

        writer.write_all(element['id'], segments, config.output)

        for segment in segments:
            segment['url'] = f"https://youtube.com/watch?v={element['id']}&t={int(segment['start'])}"
            segment['file_path'] = file_path

        new_progress_info['inner_status'] = 'completed'
        new_progress_info['progress'] = 100.0
        yield new_progress_info, writer.compact_segments(segments, config.output.min_words_per_segment)

def lunch(audio_file):
    youtube_url = "https://www.youtube.com/watch?v=Phc_kYY37GQ"
    language_sign = "AR"
    # audio_file = download_youtube_audio(youtube_url)
    # audio_file = next(Path(__file__).parent.glob('downloads/*.wav'))
    transcribe_file(audio_file, language_sign)

if __name__ == "__main__":
    lunch()