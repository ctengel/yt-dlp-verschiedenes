"""Solution extractor"""
from yt_dlp.extractor.common import InfoExtractor

class LosungenIE(InfoExtractor):
    """Extractor for Losungen"""

    _WORKING = False
    _TESTS = []
    _VALID_URL = r'losungen://(?P<site_domain>[^:]+):(?P<secret_key>\d+)\@(?P<domain>[^/]+)/(?P<path>[^/]+)/(?P<filename>[^/]+)$'

    def _time_to_seconds(self, time_str):
        if not time_str:
            return None
        hours, minutes, seconds = map(int, time_str.split(':'))
        return hours * 3600 + minutes * 60 + seconds

    def _extract_entry(self, data, base_video_url, site_domain, base_image_url):
        # TODO LPM
        site = data['site']
        full_name = site + ' ' + data['name']
        video_url = base_video_url + full_name + '.mp4'
        image_url = base_image_url + full_name + '.jpg'
        site_url = f'https://{site_domain}/'
        duration = self._time_to_seconds(data['duration'])
        return {
            'id': data['_id'],
            'channel_id': site,
            'channel': site_domain,
            'uploader_id': site,
            'uploader': site_domain,
            'channel_url': site_url,
            'uploader_url': site_url,
            'title': full_name,
            'url': video_url,
            'ext': 'mp4',
            'duration': duration,
            'display_id': full_name,
            'is_live': False,
            'protocol': 'https',
            'webpage_url': video_url,
            'thumbnail': image_url
        }

    def _site_videos_list(self, pl_url, base_video_url, pl_id, site_domain, base_image_url):
        playlist = self._download_json(pl_url, pl_id)
        for entry in playlist:
            yield self._extract_entry(entry, base_video_url, site_domain, base_image_url)

    def _real_extract(self, url):
        site_domain, secret_key, domain, path, filename = self._match_valid_url(url).groups()
        pl_url = f'https://{domain}/{path}/{filename}'
        base_video_url = f'https://{site_domain}/assets/videos{secret_key}/'
        base_image_url = f'https://{site_domain}/assets/images/'
        pl_id = filename
        return self.playlist_result(self._site_videos_list(pl_url, base_video_url, pl_id, site_domain, base_image_url), playlist_id=pl_id, playlist_title=site_domain)
    