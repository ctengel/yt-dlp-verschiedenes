import datetime
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    int_or_none,
    str_or_none,
    traverse_obj,
)


class MarcusIE(InfoExtractor):
    _WORKING = False
    _VALID_URL = r'https://api\.streamspot\.com/broadcaster/(?P<id>[^/]+)/videos.*'

    def _real_extract(self, url):

        playlist_id = self._match_id(url)

        json_data = self._download_json(
            url,
            playlist_id,
            note="Downloading JSON playlist",
            errnote="Unable to download JSON playlist",
        )

        videos = traverse_obj(json_data, ('data', 'videos'))

        if not isinstance(videos, list):
            raise ExtractorError("Invalid JSON structure: expected data.videos list")

        entries = []

        for video in videos:
            if not isinstance(video, dict):
                continue

            video_id = str_or_none(video.get("file_id"))
            if not video_id:
                continue

            title = video.get("custom_name") or video.get("name") or video_id
            duration = int_or_none(video.get("duration"))
            timestamp = int_or_none(video.get("dateTime"))
            if timestamp is not None:
                title += f" {datetime.datetime.fromtimestamp(timestamp).date().isoformat()}"
            thumbnail = video.get("thumbnailLink")

            src = video.get("src") or {}
            formats = []

            mp4_url = src.get("mp4")
            if mp4_url:
                formats.append({
                    "url": mp4_url,
                    "format_id": "http-mp4",
                    "ext": "mp4",
                })

            if not formats:
                continue

            entries.append({
                "id": video_id,
                "title": title,
                "formats": formats,
                "duration": duration,
                "timestamp": timestamp,
                "thumbnail": thumbnail,
                "webpage_url": mp4_url
            })

        if not entries:
            raise ExtractorError("No public videos found")

        playlist_title = traverse_obj(
            videos, (0, "church")
        ) or playlist_id

        return {
            "_type": "playlist",
            "id": playlist_id,
            "title": playlist_title,
            "entries": entries,
        }