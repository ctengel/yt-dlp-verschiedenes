import re
from urllib.parse import urljoin, urlparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import clean_html, ExtractorError


class AdeptoIE(InfoExtractor):
    #IE_DESC = 'Generic static HTML MP4 + image gallery'
    #_VALID_URL = r'https?://.+'
    #_PRIORITY = -10

    _WORKING = False
    _TESTS = []
    _VALID_URL = r'adepto://[^/]+/.+'

    VIDEO_EXTENSIONS = ('.mp4',)  #, '.m4v', '.mov')
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg')  #, '.png', '.webp')

    def _real_extract(self, url):

        url = url.replace('adepto://', 'http://', 1)

        webpage = self._download_webpage(url, url)

        if '<html' not in webpage.lower():
            raise ExtractorError('Not an HTML page', expected=True)

        parsed_page = urlparse(url)
        page_domain = parsed_page.netloc

        entries = []
        seen = set()

        # ---------------------------------------------------------
        # 1️⃣ Extract ALL anchor links
        # ---------------------------------------------------------
        for match in re.finditer(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            webpage,
            re.I | re.S
        ):
            rel_url, anchor_html = match.groups()
            lower = rel_url.lower()

            if not lower.endswith(self.VIDEO_EXTENSIONS + self.IMAGE_EXTENSIONS):
                continue

            media_url = urljoin(url, rel_url)

            if urlparse(media_url).netloc != page_domain:
                continue

            if media_url in seen:
                continue

            seen.add(media_url)

            anchor_text = clean_html(anchor_html).strip()
            title = anchor_text or rel_url.split('/')[-1]

            entry = {
                'url': media_url,
                'title': title,
                'id': rel_url.split('/')[-1].split('.')[0]
            }

            # ---- VIDEO extras ----
            if lower.endswith(self.VIDEO_EXTENSIONS):

                # Duration parsing (mm:ss)
                dur_match = re.search(r'(\d+):(\d+)', anchor_text or '')
                if dur_match:
                    m, s = dur_match.groups()
                    entry['duration'] = int(m) * 60 + int(s)

                # Thumbnail extraction (prefer xthumbnail-orig-image)
                context_start = max(0, match.start() - 800)
                context_html = webpage[context_start:match.start()]

                thumb_match = re.search(
                    r'<img[^>]+xthumbnail-orig-image=["\']([^"\']+)["\']',
                    context_html,
                    re.I
                )

                if not thumb_match:
                    thumb_match = re.search(
                        r'<img[^>]+src=["\']([^"\']+)["\']',
                        context_html,
                        re.I
                    )

                if thumb_match:
                    entry['thumbnail'] = urljoin(url, thumb_match.group(1))

            # ---- IMAGE filtering ----
            elif lower.endswith(self.IMAGE_EXTENSIONS):
                # Skip thumbnail-style filenames
                if re.search(r'(_t\.|_small\.|thumb)', lower):
                    continue

            if not entry:
                continue

            entries.append(entry)

        if not entries:
            raise ExtractorError('No media found', expected=True)

        # ---------------------------------------------------------
        # Playlist metadata
        # ---------------------------------------------------------
        title = self._html_search_regex(
            r'<title>([^<]+)</title>',
            webpage,
            'title',
            fatal=False,
        )

        description = self._html_search_meta(
            'description',
            webpage,
            default=None
        )

        return {
            '_type': 'playlist',
            'id': url,
            'title': title,
            'description': description,
            'entries': entries,
        }