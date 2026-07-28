"""Verus extractors

The site serves two structurally different listings, so they get one fake
scheme each rather than being guessed at:

    verus://HOST/       unauthenticated listing -- preview trailers, no
                        per-item pages
    verusauth://HOST/   authenticated listing -- links to per-item download
                        pages
    verusclip://HOST/PATH   a single authenticated item (emitted by
                            verusauth://)

Credentials for the authenticated side come from ``-u``/``-p`` or ``.netrc``
under the machine name ``verus``.
"""
import base64
import itertools
import re
from urllib.parse import urljoin, urlparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    clean_html,
    determine_ext,
    float_or_none,
    int_or_none,
    parse_duration,
    parse_filesize,
    unified_strdate,
)


class VerusListInfoExtractor(InfoExtractor):
    """Shared login and pagination for the verus extractors.

    Deliberately not named ``...IE``: the plugin loader registers every class
    in this module whose name ends in that suffix.
    """

    # Subclasses that need credentials set this to 'verus'; leaving it False
    # means yt-dlp never calls _perform_login, so _auth_headers stays empty
    # and no Authorization header is sent.
    _NETRC_MACHINE = False
    _auth_headers = {}

    def _perform_login(self, username, password):
        token = base64.b64encode(f'{username}:{password}'.encode()).decode()
        self._auth_headers = {'Authorization': f'Basic {token}'}

    def _paginate(self, url, playlist_id):
        """Walk the listing until a page yields no entries."""
        entries = []
        for page_num, page_url in self._page_urls(url):
            webpage = self._download_webpage(
                page_url, playlist_id, fatal=False, headers=self._auth_headers,
                note=f'Downloading listing page {page_num}')
            page_entries = self._page_entries(webpage, page_url) if webpage else []
            if not page_entries:
                break
            entries.extend(page_entries)
        return entries

    def _blocks(self, webpage, marker):
        """Split a listing page into item blocks, dropping the page chrome.

        A lookahead split keeps everything before the first block as a chunk of
        its own. Past the end of a listing there are no blocks at all -- and
        these sites answer 200 for any page number -- so that chunk would be
        the whole document, whose navigation anchors look enough like an entry
        to keep pagination running forever.
        """
        return [block for block in re.split(f'(?={re.escape(marker)})', webpage)
                if block.startswith(marker)]

    def _page_urls(self, url):
        """Yield ``(page number, url)`` for each successive listing page."""
        raise NotImplementedError('subclass must implement _page_urls')

    def _page_entries(self, webpage, page_url):
        raise NotImplementedError('subclass must implement _page_entries')


class VerusIE(VerusListInfoExtractor):
    """Unauthenticated listing: preview trailers, taken straight off the index.

    Unauthenticated items have no page of their own, so the trailer URL goes
    into the entry directly instead of being resolved through a clip pointer.
    """

    _WORKING = False
    _TESTS = []
    _VALID_URL = r'verus://(?P<id>[^/]+)(?:/.*)?'
    _RETURN_TYPE = 'playlist'

    def _extract_entry(self, block, page_url):
        trailer_path = self._search_regex(
            r"tload\('(/trailers/[^']+\.mp4)'\)", block, 'trailer url',
            default=None)
        if not trailer_path:
            return None

        title = clean_html(self._html_search_regex(
            r'<span class="update_title">([^<]+)</span>', block, 'title',
            default=None))

        date_str = self._html_search_regex(
            r'<span class="update_date">([^<]+)</span>', block, 'upload date',
            default=None)

        thumbnail = self._html_search_regex(
            r'<img[^>]+class="[^"]*large_update_thumb[^"]*"[^>]+src="([^"]+)"',
            block, 'thumbnail', default=None)

        # _search_regex, not _html_search_regex: the latter strips the <a>
        # tags we need to pick the individual tag names out of.
        tags_section = self._search_regex(
            r'Tags:\s*(.+?)</div>', block, 'tags section', default=None)
        tags = [clean_html(tag).strip()
                for tag in re.findall(r'>([^<]+)</a>', tags_section or '')]

        return {
            'id': trailer_path.rsplit('/', 1)[-1].removesuffix('.mp4'),
            'url': urljoin(page_url, trailer_path),
            'ext': determine_ext(trailer_path, 'mp4'),
            'title': title,
            # Same CMS as the authenticated listing, which dates US-style.
            'upload_date': unified_strdate(date_str, day_first=False),
            'thumbnail': urljoin(page_url, thumbnail) if thumbnail else None,
            'tags': tags,
        }

    def _page_urls(self, url):
        yield 1, url
        for page_num in itertools.count(2):
            yield page_num, urljoin(url, f'updates/page_{page_num}.html')

    def _page_entries(self, webpage, page_url):
        entries = []
        for block in self._blocks(webpage, '<div class="update_block">'):
            entry = self._extract_entry(block, page_url)
            if entry:
                entries.append(entry)
        return entries

    def _real_extract(self, url):
        if self.get_param('username') or self.get_param('usenetrc'):
            self.report_warning(
                'verus:// is the unauthenticated preview listing and ignores '
                'your credentials; use verusauth:// instead')
        playlist_id = self._match_id(url)
        return self.playlist_result(
            self._paginate(url.replace('verus://', 'https://', 1), playlist_id),
            playlist_id=playlist_id, playlist_title=playlist_id)


class VerusAuthIE(VerusListInfoExtractor):
    """Authenticated listing: one clip pointer per linked download page."""

    _WORKING = False
    _TESTS = []
    _NETRC_MACHINE = 'verus'
    _VALID_URL = r'verusauth://(?P<id>[^/]+)(?:/.*)?'
    _RETURN_TYPE = 'playlist'

    # Authenticated listings paginate inside the filename, not the path:
    # /members/categories/movies_1_d.html -> movies_2_d.html. The sort suffix
    # is matched without underscores so a category that ends in digits
    # ("top10_1_d.html") can't be mistaken for the page number.
    _PAGE_RE = r'_(?P<page>\d+)_[^/?#_]*\.html(?=$|[?#])'

    def _page_urls(self, url):
        m = re.search(self._PAGE_RE, url)
        if not m:
            # Not a paginated category URL; take it as a single page.
            yield 1, url
            return
        # Start from whatever page the given URL names, as vereinigt.py does.
        for page_num in itertools.count(int(m.group('page'))):
            yield page_num, f'{url[:m.start("page")]}{page_num}{url[m.end("page"):]}'

    def _extract_entry(self, block, page_url):
        """Build a clip pointer from one ``update_details`` block, or None."""
        # Two anchors point at the same page: the thumbnail (whose text is
        # just an <img>) and the title. Take the href off the first and the
        # name off the first one that actually has text.
        anchors = re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not anchors:
            return None
        detail = urlparse(urljoin(page_url, anchors[0][0]))
        clip_url = f'verusclip://{detail.netloc}{detail.path}'
        if detail.query:
            clip_url = f'{clip_url}?{detail.query}'

        title = next(
            (t for t in (clean_html(a[1]) or '' for a in anchors) if t.strip()),
            None)

        # The thumbnail is a JS rollover: no plain src, just srcN_Mx pairs.
        # Image 0 at 4x is the largest still of the first frame.
        thumbnail = self._search_regex(
            r'\bsrc0_4x="([^"]+)"', block, 'thumbnail',
            default=None) or self._search_regex(
                r'\bsrc0_1x="([^"]+)"', block, 'thumbnail', default=None)

        # US-format dates: 07/08/2026 is July 8th, so day_first must be off.
        date_str = clean_html(self._search_regex(
            r'<div[^>]+class="[^"]*update_date[^"]*"[^>]*>(.*?)</div>',
            block, 'upload date', default=None, flags=re.S))

        counts = clean_html(self._search_regex(
            r'<div[^>]+class="[^"]*update_counts[^"]*"[^>]*>(.*?)</div>',
            block, 'counts', default=None, flags=re.S)) or ''
        duration = parse_duration(self._search_regex(
            r'((?:\d+\s*(?:hrs?|hours?|mins?|minutes?|secs?|seconds?)\s*)+'
            r'|\d+(?::\d+)+)\s*of\s+video', counts, 'duration', default=None))

        return self.url_result(
            clip_url, VerusClipIE, url_transparent=True,
            video_id=re.sub(
                r'\.html?$', '', detail.path.strip('/').split('/')[-1]) or None,
            video_title=title,
            thumbnail=urljoin(page_url, thumbnail) if thumbnail else None,
            upload_date=unified_strdate(date_str, day_first=False),
            duration=duration,
            average_rating=float_or_none(self._search_regex(
                r'Avg Rating:\s*([\d.]+)', block, 'rating', default=None)))

    def _page_entries(self, webpage, page_url):
        entries, seen = [], set()
        for block in self._blocks(webpage, '<div class="update_details"'):
            entry = self._extract_entry(block, page_url)
            # A page can list the same set twice (e.g. featured plus regular).
            if entry and entry['url'] not in seen:
                seen.add(entry['url'])
                entries.append(entry)
        return entries

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        return self.playlist_result(
            self._paginate(url.replace('verusauth://', 'https://', 1), playlist_id),
            playlist_id=playlist_id, playlist_title=playlist_id)


class VerusClipIE(VerusListInfoExtractor):
    """A single authenticated item, resolved from its download page."""

    _WORKING = False
    _TESTS = []
    _NETRC_MACHINE = 'verus'
    _VALID_URL = r'verusclip://(?P<host>[^/]+)/(?P<path>.+)'
    _RETURN_TYPE = 'video'

    def _download_formats(self, webpage, page_url):
        """Authenticated download menu: one entry per offered resolution."""
        dropdown = self._search_regex(
            r'<ul[^>]+class="[^"]*downloaddropdown[^"]*"[^>]*>(.*?)</ul>',
            webpage, 'download menu', default=None, flags=re.S)
        if not dropdown:
            return []

        formats = []
        for href, label in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', dropdown, re.S):
            if href.startswith(('javascript:', '#')):
                continue
            # Labels look like "MP4 1080p (297.9 MB)". These links carry no
            # metadata of their own, so the height and size scraped out of the
            # label are all the format sorter has to rank them by; without at
            # least one it falls back to sorting on format_id, which is
            # alphabetical and therefore arbitrary.
            label = clean_html(label).strip()
            size = self._search_regex(
                r'\(?\b([\d.,]+\s*[KMGT]i?B)\b\)?', label, 'filesize',
                default=None)
            formats.append({
                'url': urljoin(page_url, href),
                # Drop the size from the name so `-f` stays typeable.
                'format_id': re.sub(r'\s*\([^)]*\)\s*$', '', label) or None,
                'height': int_or_none(self._search_regex(
                    r'(\d{3,4})p\b', f'{label} {href}', 'height',
                    default=None)),
                'filesize_approx': parse_filesize(size),
                'ext': determine_ext(href, 'mp4'),
                'http_headers': dict(self._auth_headers),
            })
        return formats

    def _trailer_formats(self, webpage, page_url):
        """Safety net for an item the account cannot download."""
        trailer_path = self._search_regex(
            r"tload\('(/trailers/[^']+\.mp4)'\)", webpage, 'trailer url',
            default=None)
        if not trailer_path:
            return []
        return [{
            'url': urljoin(page_url, trailer_path),
            'format_id': 'trailer',
            'preference': -10,
            'ext': determine_ext(trailer_path, 'mp4'),
        }]

    @staticmethod
    def _media_id(formats, fallback):
        """Name the item after the media file, the way the site names it.

        Every resolution is served under the same basename (only the
        directory differs), so this does not depend on which format the
        caller ends up selecting. Falls back to the page slug if a link ever
        has no usable filename.
        """
        for fmt in formats:
            stem = re.sub(
                r'\.[^./]+$', '', urlparse(fmt['url']).path.rsplit('/', 1)[-1])
            if stem:
                return stem
        return fallback

    def _real_extract(self, url):
        page_url = url.replace('verusclip://', 'https://', 1)
        slug = re.sub(
            r'\.html?$', '', urlparse(page_url).path.strip('/').split('/')[-1])

        webpage = self._download_webpage(
            page_url, slug, headers=self._auth_headers)

        formats = self._download_formats(webpage, page_url)
        if not formats:
            formats = self._trailer_formats(webpage, page_url)
        if not formats:
            raise ExtractorError(
                'No downloads found; login may be required', expected=True)

        title = self._html_search_regex(
            r'<span class="update_title">([^<]+)</span>', webpage, 'title',
            default=None) or self._html_extract_title(
                webpage, default=None) or slug

        return {
            # url_transparent exempts 'id', so this wins over the listing's
            # slug once the item is actually resolved.
            'id': self._media_id(formats, slug),
            'display_id': slug,
            'title': title,
            'webpage_url': page_url,
            'formats': formats,
        }
