"""Vereinigt extractor"""
import itertools
import re
from urllib.parse import urlparse, urljoin, urlunparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, clean_html, parse_duration


class VereinigtClipIE(InfoExtractor):
    """Single clip"""

    _WORKING = False
    _TESTS = []
    _VALID_URL = (
        r'vereinigtclip://(?P<site>[^/]+)/(?P<cdn>[^/]+)/'
        r'(?P<guid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        r'/(?P<slug>[^/?#]+)'
    )
    _RETURN_TYPE = 'video'

    def _real_extract(self, url):
        site, cdn, guid, slug = self._match_valid_url(url).group(
            'site', 'cdn', 'guid', 'slug')
        headers = {'Referer': f'https://{site}/'}
        formats = self._extract_m3u8_formats(
            f'https://{cdn}/{guid}/playlist.m3u8', slug, 'mp4',
            m3u8_id='hls', headers=headers,
            note='Downloading HLS playlist')
        if not formats:
            raise ExtractorError('No HLS formats found', expected=True)
        for fmt in formats:
            fmt['http_headers'] = {**fmt.get('http_headers', {}), **headers}
        return {
            'id': slug,
            'title': slug,
            'webpage_url': f'https://{site}/videos/{slug}/',
            'thumbnail': f'https://{cdn}/{guid}/thumbnail.jpg',
            'formats': formats,
        }


class VereinigtIE(InfoExtractor):
    """Listing (playlist) extractor for the vereinigt site."""

    _WORKING = False
    _TESTS = []
    _VALID_URL = r'vereinigt://.+'
    _RETURN_TYPE = 'playlist'

    _THUMB_RE = (
        r'src=["\'](?P<thumb>https?://(?P<cdn>[^/"\']+)/'
        r'(?P<guid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        r'/thumbnail[^"\']*\.jpg(?:\?[^"\']*)?)["\']'
    )

    def _extract_entry(self, block, site):
        """Build a flat clip pointer from one ``<article>`` block, or None."""
        thumb_url, cdn, guid = self._search_regex(
            self._THUMB_RE, block, 'thumbnail', group=('thumb', 'cdn', 'guid'),
            default=(None, None, None))
        if not guid:
            return None

        slug = self._search_regex(
            r'href=["\'][^"\']*/videos/(?P<slug>[^/"\']+)/?["\']',
            block, 'slug', default=None)
        if not slug:
            return None

        title = self._search_regex(
            r'<img[^>]+\balt=["\']([^"\']+)["\']', block, 'title',
            default=None)
        if not title:
            raw = self._search_regex(
                r'<h2 class="entry-title">\s*<a[^>]*>(.*?)</a>',
                block, 'title', default='', flags=re.S)
            title = clean_html(re.split(r'<span', raw, maxsplit=1)[0]) or None

        duration = parse_duration(self._search_regex(
            r'\U0001F552\s*([0-9:]+)', block, 'duration', default=None))

        return self.url_result(
            f'vereinigtclip://{site}/{cdn}/{guid}/{slug}', VereinigtClipIE,
            video_id=slug, video_title=title, url_transparent=True,
            duration=duration, thumbnail=thumb_url)

    def _page_entries(self, page_url, playlist_id, page_num, site):
        webpage = self._download_webpage(
            page_url, playlist_id, fatal=False,
            note=f'Downloading listing page {page_num}')
        if not webpage:
            return []
        blocks = re.split(r'(?=<article class="entry)', webpage)[1:]
        entries = []
        for block in blocks:
            entry = self._extract_entry(block, site)
            if entry:
                entries.append(entry)
        return entries

    def _real_extract(self, url):
        url = url.replace('vereinigt://', 'https://', 1)
        parsed = urlparse(url)

        m = re.match(r'^(?P<base>.*?/)page/(?P<n>\d+)/?$', parsed.path)
        if m:
            base_path, start = m.group('base'), int(m.group('n'))
        else:
            base_path = parsed.path if parsed.path.endswith('/') else parsed.path + '/'
            start = 1
        base_url = urlunparse(parsed._replace(path=base_path))
        playlist_id = base_path.strip('/').split('/')[-1] or parsed.netloc

        entries = []
        for page_num in itertools.count(start):
            page_url = base_url if page_num == 1 else urljoin(base_url, f'page/{page_num}/')
            page_entries = self._page_entries(page_url, playlist_id, page_num, parsed.netloc)
            if not page_entries:
                break
            entries.extend(page_entries)

        return self.playlist_result(
            entries, playlist_id=playlist_id, playlist_title=playlist_id)
