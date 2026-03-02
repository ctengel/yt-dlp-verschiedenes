import re
from urllib.parse import urljoin

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    clean_html,
    unified_strdate,
    ExtractorError,
)


class VerusIE(InfoExtractor):
    _VALID_URL = r'verus://(?P<id>(?:[^/]+)?/*+'
    _WORKING = False

    def _extract_entries(self, url, playlist_id):
        webpage = self._download_webpage(url, playlist_id)
        entries = []

        update_blocks = re.split(
            r'(?=<div class="update_block">)',
            webpage
        )

        for block in update_blocks:
            if 'tload(' not in block:
                continue

            trailer_path = self._html_search_regex(
                r"tload\('(/trailers/[^']+\.mp4)'\)",
                block,
                'trailer url',
                fatal=False
            )
            if not trailer_path:
                continue

            title = clean_html(self._html_search_regex(
                r'<span class="update_title">([^<]+)</span>',
                block,
                'title',
                fatal=False
            ))

            date_str = self._html_search_regex(
                r'<span class="update_date">([^<]+)</span>',
                block,
                'upload date',
                fatal=False
            )

            thumbnail = self._html_search_regex(
                r'<img[^>]+class="[^"]*large_update_thumb[^"]*"[^>]+src="([^"]+)"',
                block,
                'thumbnail',
                fatal=False
            )

            # --- TAG EXTRACTION ---
            tags_section = self._html_search_regex(
                r'Tags:\s*(.+?)</div>',
                block,
                'tags section',
                fatal=False
            )

            tags = []
            if tags_section:
                tags = re.findall(
                    r'>([^<]+)</a>',
                    tags_section
                )
                tags = [clean_html(tag).strip() for tag in tags]

            entries.append({
                'id': trailer_path.rsplit('/', 1)[-1].replace('.mp4', ''),
                'url': urljoin(url, trailer_path),
                'title': title,
                'upload_date': unified_strdate(date_str),
                'thumbnail': urljoin(url, thumbnail) if thumbnail else None,
                'tags': tags,
            })

        return entries

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        url = url.replace('verus://', 'https://', 1)
        entries = []
        page_num = 1

        while True:
            page_url = url if page_num == 1 else urljoin(
                url, f'updates/page_{page_num}.html'
            )

            try:
                page_entries = self._extract_entries(page_url, playlist_id)
            except ExtractorError:
                break

            if not page_entries:
                break

            entries.extend(page_entries)
            page_num += 1

        return self.playlist_result(
            entries,
            playlist_id=playlist_id,
            playlist_title=f""
        )