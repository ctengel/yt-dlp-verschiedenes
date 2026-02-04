"""Alternative extractor"""
import itertools
import re
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    int_or_none,
    url_or_none,
    url_basename
)


class PoculumIE(InfoExtractor):
    """v1 API for whole blog, focused on native video posts"""

    _WORKING = False  # TODO set to True when stable
    _VALID_URL = r'https?://(?P<blog_name_1>[^/?#&]+)\.tumblr\.com/(?P<blog_name_2>[a-zA-Z\d-]+)?$'
    _TESTS = []  # TODO build tests
    _PAGE_LIMIT = 50

    def _extract_entry(self, post, blog):
        """Extract a video entry from a post element"""

        # extract post metadata
        slug = post.attrib.get('slug')
        pid = post.attrib.get('id')
        uploader_id = post.attrib.get('reblogged-root-name', blog)
        repost_count = int_or_none(post.attrib.get('notes'))
        post_url = url_or_none(post.attrib.get('url'))  # TODO is this correct format???
        timestamp = int_or_none(post.attrib['unix-timestamp'])

        # Look for a video URL
        self.to_screen(f'Looking for video in {pid}-{slug}...')
        # TODO see if we can learn anything else from the main extractor,
        #      such as finding multiple/best format;
        #      it seems like the best one comes up first so we are OK)
        video = post.find('video-player')
        if video is None:
            video = post.find('regular-body')
        if video is not None:
            for link in video.text.split('"'):
                if re.match(r"^https?\:\/\/.+\.mp4$", link):
                    self.to_screen(f"Found video {link} !")
                    return {
                        "id": url_basename(link),
                        "title": slug or blog,  # TODO try to use post title
                        "uploader_id": uploader_id,
                        "uploader": uploader_id,
                        "channel_id": blog,
                        "channel": blog,
                        "channel_url": f'https://{blog}.tumblr.com/',
                        'uploader_url': f'https://{uploader_id}.tumblr.com/',
                        'repost_count': repost_count,
                        "url": link,
                        "display_id": f"{pid}-{slug}" if slug else pid,
                        "ext": "mp4",
                        "is_live": False,
                        "protocol": "https",
                        "timestamp": timestamp,
                        "webpage_url": post_url
                        # TODO "description" (video-caption or regular-body)?
                        # TODO duration
                        # TODO thumbnail
                    }

        # Nothing found, fallback
        # NOTE in the unlikely event we have both native and non-native video,
        #      we will only get the native (vs a playlist with all)
        if not post_url:
            self.report_warning(f"No post or video URL found for {pid}-{slug}; skipping")
            return None
        fixed_url = post_url.replace('/blog/view/', '/')
        self.report_warning(f"Can't find video; fallback on main extractor for {fixed_url}")
        return self.url_result(fixed_url, 'Tumblr', pid)

    def _blog_entries(self, blog):
        url = f'http://{blog}.tumblr.com/api/read'
        self.to_screen(f'API URL "{url}" identified')
        for page_num in itertools.count():
            #self.to_screen(f'Page of {page_num * self._PAGE_LIMIT} to {self._PAGE_LIMIT}')
            webpage = self._download_xml(url,
                                         video_id=blog,
                                         note=f'Downloading Tumblr blog page {page_num+1}',
                                         query={"start": str(page_num * self._PAGE_LIMIT),
                                                "num": str(self._PAGE_LIMIT)})
            posts_top = webpage.find('posts')
            if posts_top is None:
                break
            posts = posts_top.findall('post')
            #self.to_screen(f'Got {len(posts)} posts')
            if not posts:
                break
            for post in posts:
                entry = self._extract_entry(post, blog)
                if entry:
                    yield entry

    def _real_extract(self, url):
        #self.to_screen(f'URL "{url}" being processed by poculum')
        blog_1, blog_2 = self._match_valid_url(url).groups()
        blog = blog_2 or blog_1
        return self.playlist_result(self._blog_entries(blog), playlist_id=blog, playlist_title=blog)

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
