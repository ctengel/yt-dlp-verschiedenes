# ⚠ Don't use relative imports
import itertools
from yt_dlp.extractor.common import InfoExtractor
import xml.etree.ElementTree as ET

class TumblrBlogIE(InfoExtractor):
    _WORKING = False
    _VALID_URL = r'https?://(?P<blog_name_1>[^/?#&]+)\.tumblr\.com/(?:(?P<blog_name_2>[a-zA-Z\d-]+)/)?$'
    _PAGE_LIMIT = 50

    @staticmethod
    def _page2posts(page_xml):
        """Get an array of posts from an XML string"""
        root = ET.fromstring(page_xml)
        postselm = root.find('posts')
        return postselm.findall('post')

    def _extract_entry(self, post):
        """Extract a video entry from a post element"""
        slug = post.attrib['slug']
        pid = post.attrib['id']
        self.to_screen(f'Considering post {pid} {slug}')
        video = post.find('video-player')
        if video is None:
            video = post.find('regular-body')
        if video is not None:
            for link in video.text.split('"'):
                if re.match(r"^https?\:\/\/.+\.mp4$", link):
                    # TODO extract more metadata
                    # TODO make sure we are returning correct type for extraction
                    self.to_screen(f"Found video {link}")
                    return {
                        "id": f"{slug}_{pid}",  # TODO let's think on this one
                        "title": slug,
                        "url": link,
                        "ext": "mp4",
                        "upload_date": None,
                    }
        # TODO fallback to tumblr IE
        self.to_screen(f'novid')
        self.report_warning(f"NOVID {pid} {slug}")
        return None

    def _blog_entries(self, blog):
        url = f'http://{blog}.tumblr.com/api/read'
        self.to_screen('API URL "%s" identified' % url)
        offset = 0
        #variables_common = self._make_variables(channel_name, *args)
        #entries_key = f'{self._ENTRY_KIND}s'
        for page_num in itertools.count():
            # TODO consider fatal=False
            self.to_screen(f'Page of {page_num * self._PAGE_LIMIT} to {self._PAGE_LIMIT}')
            webpage = self._download_webpage(url,
                                             video_id=blog,
                                             note=f'Downloading Tumblr blog page {page_num+1}',
                                             query={"start": page_num * self._PAGE_LIMIT, "num": self._PAGE_LIMIT})
            posts = self._page2posts(webpage)
            if not posts:
                break
            for post in posts:
                # TODO consider possibility of multiple videos
                entry = self._extract_entry(post)
                if entry:
                    yield entry
          
    def _real_extract(self, url):
        self.to_screen('URL "%s" being processed by poculum' % url)
        blog_1, blog_2 = self._match_valid_url(url).groups()
        blog = blog_2 or blog_1
        return self.playlist_result(self._blog_entries(blog), playlist_id=blog, playlist_title=blog)
