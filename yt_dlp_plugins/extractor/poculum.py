"""Alternative extractor"""
import itertools
import re
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    clean_html,
    int_or_none,
    url_or_none,
    url_basename
)


def _blog_name_from_url(url):
    """Derive a blog name from a post/blog URL, if possible"""
    if not url:
        return None
    mobj = re.match(
        r'https?://(?:(?P<sub>[^./]+)\.tumblr\.com|(?:www\.)?tumblr\.com/(?:blog/view/)?(?P<path>[^/?#]+))',
        url)
    if not mobj:
        return None
    name = mobj.group('sub') or mobj.group('path')
    return name if name != 'www' else None


class PoculumIE(InfoExtractor):
    """v1 API for whole blog, focused on native video posts"""

    _WORKING = False  # TODO set to True when stable
    _VALID_URL = r'''(?x)^(?:
        https?://(?P<blog_name_1>[^/?#&]+)\.tumblr\.com/(?P<blog_name_2>[a-zA-Z\d-]+)?$
        |poculum://(?P<blog_name_3>[^/?#&]+)\.tumblr\.com/post/(?P<post_id>\d+)(?:/[^/?#]*)?$
    )'''
    _TESTS = []  # TODO build tests
    _PAGE_LIMIT = 50
    _RETURN_TYPE = 'playlist'

    def _extract_entry(self, post, blog):
        """Extract a video entry from a post element"""

        # extract post metadata
        slug = post.attrib.get('slug')
        pid = post.attrib.get('id')
        repost_count = int_or_none(post.attrib.get('notes'))
        post_url = url_or_none(post.attrib.get('url-with-slug')) or url_or_none(post.attrib.get('url'))
        timestamp = int_or_none(post.attrib['unix-timestamp'])
        og_url = url_or_none(post.attrib.get('reblogged-root-url')) or url_or_none(post.attrib.get('reblogged-from-url')) or post_url
        if not post_url and og_url:
            post_url = og_url

        # attribute to the original poster, not the reblogger
        orig_blog = (post.attrib.get('reblogged-root-name')
                     or _blog_name_from_url(url_or_none(post.attrib.get('reblogged-root-url')))
                     or post.attrib.get('reblogged-from-name')
                     or _blog_name_from_url(url_or_none(post.attrib.get('reblogged-from-url')))
                     or blog)
        attribution = {
            'uploader': orig_blog,
            'uploader_id': orig_blog,
            'uploader_url': f'https://{orig_blog}.tumblr.com/',
            'channel': orig_blog,
            'channel_id': orig_blog,
            'channel_url': f'https://{orig_blog}.tumblr.com/',
        }

        # root post id/slug, e.g. .../post/<id>/<slug> or .../<blog>/<id>/<slug>
        root_slug = None
        if og_url:
            mobj = (re.search(r'/post/(?P<id>\d+)(?:/(?P<slug>[^/?#]+))?', og_url)
                    or re.search(r'tumblr\.com/(?:blog/view/)?[^/?#]+/(?P<id>\d+)(?:/(?P<slug>[^/?#]+))?', og_url))
            if mobj:
                root_slug = mobj.group('slug')
        eff_slug = slug or root_slug

        # description from caption/body
        caption = post.find('video-caption')
        if caption is None:
            caption = post.find('regular-body')
        description = clean_html(caption.text) if caption is not None else None

        # Look for a video URL
        self.write_debug(f'Looking for video in {pid}-{slug}...')
        # TODO see if we can learn anything else from the main extractor,
        #      such as finding multiple/best format;
        #      it seems like the best one comes up first so we are OK)
        video = post.find('video-player')
        if video is None:
            video = post.find('regular-body')
        if video is not None:
            thumbnail = url_or_none(self._search_regex(
                r'poster=(["\'])(?P<u>.+?)\1', video.text or '', 'thumbnail',
                group='u', default=None))
            for link in (video.text or '').split('"'):
                if re.match(r"^https?\:\/\/.+\.mp4$", link):
                    self.write_debug(f"Found video {link} !")
                    return {
                        "id": self._search_regex(
                            r'(tumblr_\w+?)(?:_\d+)?\.mp4$', link, 'video id',
                            default=None) or url_basename(link),
                        "title": eff_slug or f"{blog}-{pid}",  # TODO try to use post title
                        **attribution,
                        'repost_count': repost_count,
                        "url": link,
                        "display_id": f"{blog}-{pid}-{eff_slug}" if eff_slug else f"{blog}-{pid}",
                        "ext": "mp4",
                        "is_live": False,
                        "protocol": "https",
                        "timestamp": timestamp,
                        "webpage_url": og_url,
                        "original_url": post_url,
                        "description": description,
                        "thumbnail": thumbnail
                        # TODO duration
                    }

        # Nothing found, fallback
        # NOTE in the unlikely event we have both native and non-native video,
        #      we will only get the native (vs a playlist with all)
        if not post_url:
            self.report_warning(f"No post or video URL found for {pid}-{slug}; skipping")
            return None
        fixed_url = post_url.replace('/blog/view/', '/')
        self.report_warning(f"Can't find video; fallback on main extractor for {fixed_url}")
        return self.url_result(fixed_url, 'Tumblr', pid, url_transparent=True, **attribution)

    def _blog_entries(self, blog, post_id=None):
        url = f'http://{blog}.tumblr.com/api/read'
        self.write_debug(f'API URL "{url}" identified')
        for page_num in itertools.count():
            if post_id:
                query = {"id": post_id}
                note = f'Downloading post {post_id}'
            else:
                query = {"start": str(page_num * self._PAGE_LIMIT),
                         "num": str(self._PAGE_LIMIT)}
                note = f'Downloading blog page {page_num+1}'
            webpage = self._download_xml(url, video_id=blog, note=note, query=query)
            posts_top = webpage.find('posts')
            if posts_top is None:
                break
            posts = posts_top.findall('post')
            if not posts:
                break
            for post in posts:
                entry = self._extract_entry(post, blog)
                if entry:
                    yield entry
            if post_id:
                break

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        blog_1, blog_2, blog_3, post_id = mobj.group(
            'blog_name_1', 'blog_name_2', 'blog_name_3', 'post_id')
        blog = blog_3 or blog_2 or blog_1
        return self.playlist_result(self._blog_entries(blog, post_id), playlist_id=blog, playlist_title=blog)

    def _get_automatic_captions(self, *args, **kwargs):
        self.report_warning('Automatic captions are not supported in this extractor')
        return {}

    def _get_comments(self, *args, **kwargs):
        self.report_warning('Comments are not supported in this extractor')
        return []

    def _get_subtitles(self, *args, **kwargs):
        self.report_warning('Subtitles are not supported in this extractor')
        return []

    def _mark_watched(self, *args, **kwargs):
        self.report_warning('Marking videos as watched is not supported in this extractor')
