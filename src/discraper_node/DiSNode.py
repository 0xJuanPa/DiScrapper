from .ChordNode import ChordNode
from .InfoContainer import InfoContainer
from .custom_xrpc import RedirectNodeResponse

import re
import urllib.request
import urllib.parse
import ssl


class DiSNode(ChordNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # '(?:(?P<urls>https?://.+?)(?:[ "]|(?:&quot;)))|(?:href=(?:[ "]|(?:&quot;))(?P<href>.+?)(?:[ "]|(?:&quot;)))')
        self.compiled_regex = re.compile('(?:href=(?:[ "]|(?:&quot;))(?P<href>.+?)(?:[ "]|(?:&quot;)))')
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'
        self.headers = {'Accept-Encoding': 'identity',
                        'Accept': 'text/html',
                        'User-Agent': user_agent}

    def _get_url(self, url):
        try:
            # disable content encoding  to avoid decompression

            # set accepted contents types to html
            # set user agent to avoid 403s and other problems
            request = urllib.request.Request(url, headers=self.headers)
            # allow weak certificate
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(request, timeout=20, context=context)  # this follows redirects
            # only accept mime type text/html
            if response.headers.get_content_type() == 'text/html':
                res = response.read().decode(response.headers.get_content_charset())
                domain = urllib.parse.urlsplit(response.geturl()).netloc
                return domain, res
            else:
                self.logger.info("mime type: " + response.info().get("Content-Type"))
                return None
        except Exception as e:
            self.logger.error("Failed getting url " + url + f" error {e}")
            return None

    def _get_links(self, domain, content):
        matches = self.compiled_regex.findall(content)
        urls = set()
        # get group href
        for url in matches:  # unpack only one as have only one group in regex
            url: str
            if url.startswith("#"):
                continue
            if not url.startswith("http"):
                url = "http://" + domain + "/" + url.lstrip("/")
            parsed = urllib.parse.urlsplit(url)
            n: str = parsed.netloc
            if n.endswith(domain):
                urls.add(url)
        return urls

    def SCRAP(self, level, url,i_remote=None):
        '''
        Scraps the url
        '''
        id_ = self.hasher(url)
        n0 = self.Find_Successor(id_)
        if n0 != self:
            self.logger.warning("Redirecting SCRAP to " + str(n0))
            if self.iterative_scheme and i_remote:
                return RedirectNodeResponse(n0)
            return n0.SCRAP(level,url)
        else:
            level = int(level)
            self.logger.warning("Scraping " + url + " level " + str(level))
            if level == 0:
                return []
            # get netloc of url
            found = self.GET(id_)
            if found:
                self.logger.warning("Found " + url + " in ring")
                return [found]
            try:
                domain, content = self._get_url(url)
            except Exception as e:
                self.logger.error("Failed getting url " + url + f" error {e}")
                return []
            refs = self._get_links(domain, content)
            info = InfoContainer(url, refs=refs, content=content)
            response = [info]
            self.Push(info, dstport=self.Address[1], recurse=True, resolve=False, i_addr=self.Address)
            if level > 1:
                for u in refs:
                    try:
                        v = self.SCRAP(level - 1, u)
                    except Exception as e:
                        self.logger.error(f"Failed scraping {u} error {e}")
                        continue
                    response.append(v)
            return response

    def DELETE(self,level,url_or_id,i_remote=None):
        level = int(level)
        try:
            id_ = int(url_or_id)
        except:
            id_ = self.hasher(url_or_id)
        n0 = self.Find_Successor(id_)
        if n0 != self:
            self.logger.warning("Redirecting DELETE to " + str(n0))
            if self.iterative_scheme and i_remote:
                return RedirectNodeResponse(n0)
            return n0.DELETE(level,id_)
        else:
            self.logger.warning("Deleting " + url_or_id + " level " + str(level))
            self.Delete(id_, dstport=self.Address[1], recurse=True, resolve=False, i_addr=self.Address)
            if level > 1:
                info = self.database.find_like(id_)
                for u in info.refs:
                    self.DELETE(level - 1,u)

    def GET(self, url_or_id,i_remote=None):
        try:
            id_ = int(url_or_id)
        except:
            id_ = self.hasher(url_or_id)
        n0 = self.Find_Successor(id_)
        if n0 != self:
            if self.iterative_scheme and i_remote:
                return RedirectNodeResponse(n0)
            return n0.GET(url_or_id)
        else:
            info = self.database.find_like(id_)
            return info

    def LIST(self):
        return self.database

    def PEERS(self):
        peers = set()
        peers.update(self.r_successors)
        peers.update(self.finger)
        peers.remove(None)
        peers.remove(self)
        return list(peers)

# curl -L "http://127.0.0.1:4443/SCRAP/1/http://www.freecodecamp.org/news/how-to-redirect-http-to-https-using-htaccess/"
# curl -L "http://127.0.0.1:4443/SCRAP/1/https://www.techwalla.com/articles/how-do-i-stop-links-from-redirecting-me-to-different-sites"
# curl -L  http://127.0.0.1:4443/SCRAP/1/https://goo.gle"
