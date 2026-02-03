# ⚠ Don't use relative imports
import itertools
import re
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    int_or_none,
    url_or_none
)


class TumblrBlogIE(InfoExtractor):
    _WORKING = False
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
        post_url = url_or_none(post.attrib.get('url')) # TODO is this correct format???
        timestamp = int_or_none(post.attrib['unix-timestamp'])

        # Look for a video URL
        self.to_screen(f'Considering post {pid} {slug}')
        # TODO see if we can learn anything else from the main extractor, such as finding multiple/best format; it seems like the best one comes up first so we are OK)
        video = post.find('video-player')
        if video is None:
            video = post.find('regular-body')
        if video is not None:
            for link in video.text.split('"'):
                if re.match(r"^https?\:\/\/.+\.mp4$", link):
                    self.to_screen(f"Found video {link}")
                    return {
                        "id": f"{slug}_{pid}",  # TODO let's think on this one; alt would be post ID to match with main extractor
                        "title": slug or blog,  # TODO try to use post title instead before resorting to slug
                        "uploader_id": uploader_id,
                        'uploader_url': f'https://{uploader_id}.tumblr.com/' if uploader_id else None,  # TODO is this correct format?
                        'repost_count': repost_count,
                        "url": link,
                        "display_id": slug or None,
                        "ext": "mp4",
                        "is_live": False,
                        "protocol": "https",
                        "timestamp": timestamp
                        # TODO "description" (video-caption or regular-body)?
                        # TODO duration
                        # TODO thumbnail
                    }
        
        # Nothing found, fallback
        # NOTE in the unlikely event we have both native and non-native video, we will only get the native (vs a playlist with all)
        self.report_warning(f"Could not find a video so falling back on main extractor for post {pid} {slug}")
        return self.url_result(post_url, 'Tumblr', pid)


    def _blog_entries(self, blog):
        url = f'http://{blog}.tumblr.com/api/read'
        self.to_screen('API URL "%s" identified' % url)
        for page_num in itertools.count():
            self.to_screen(f'Page of {page_num * self._PAGE_LIMIT} to {self._PAGE_LIMIT}')
            webpage = self._download_xml(url,
                                         video_id=blog,
                                         note=f'Downloading Tumblr blog page {page_num+1}',
                                         query={"start": page_num * self._PAGE_LIMIT, "num": self._PAGE_LIMIT})
            posts = webpage.find('posts').findall('post')
            self.to_screen(f'Got {len(posts)} posts')
            if not posts:
                break
            for post in posts:
                entry = self._extract_entry(post, blog)
                if entry:
                    yield entry
          
    def _real_extract(self, url):
        self.to_screen('URL "%s" being processed by poculum' % url)
        blog_1, blog_2 = self._match_valid_url(url).groups()
        blog = blog_2 or blog_1
        return self.playlist_result(self._blog_entries(blog), playlist_id=blog, playlist_title=blog)
