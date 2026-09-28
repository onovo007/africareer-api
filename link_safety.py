"""Check public HTTPS links without permitting requests to private networks.

DNS is resolved and validated once per redirect hop, then the connection is
pinned to a validated address. TLS still validates the original hostname.
Only response headers are read; a successful check does not verify content.
"""
import http.client
import ipaddress
import socket
import time
from urllib.parse import urlsplit, urljoin


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, port=443, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def public_target(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs are allowed")
    if parsed.port not in (None, 443):
        raise ValueError("Unsupported port")
    host = parsed.hostname.encode("idna").decode("ascii")
    addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Non-public destination")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return host, sorted(addresses)[0], path


def reachable(url, timeout=6.0):
    deadline = time.monotonic() + timeout
    try:
        for _ in range(4):
            host, address, path = public_target(url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            connection = PublicHTTPSConnection(host, address, remaining)
            try:
                connection.request("GET", path, headers={"User-Agent": "AfriCareer-LinkCheck/1.0", "Accept": "text/html", "Connection": "close"})
                response = connection.getresponse()
                if 200 <= response.status < 300:
                    return True
                if response.status not in (301, 302, 303, 307, 308):
                    return False
                target = response.getheader("Location")
                if not target:
                    return False
                url = urljoin(url, target)
            finally:
                connection.close()
    except (ValueError, OSError, http.client.HTTPException, UnicodeError):
        return False
    return False


def public_html(url, timeout=6.0, max_bytes=750000):
    """Bounded HTML retrieval with the same pinned-address redirect protections."""
    deadline=time.monotonic()+timeout
    try:
        for _ in range(4):
            host,address,path=public_target(url)
            remaining=deadline-time.monotonic()
            if remaining<=0:return None
            connection=PublicHTTPSConnection(host,address,remaining)
            try:
                connection.request('GET',path,headers={'User-Agent':'AfriCareer-LinkCheck/1.0','Accept':'text/html','Connection':'close'})
                response=connection.getresponse()
                if response.status in (301,302,303,307,308):
                    target=response.getheader('Location')
                    if not target:return None
                    url=urljoin(url,target);continue
                if response.status!=200 or 'html' not in (response.getheader('Content-Type') or '').lower():return None
                raw=response.read(max_bytes+1)
                if len(raw)>max_bytes:return None
                return raw.decode('utf-8',errors='replace')
            finally:connection.close()
    except (ValueError,OSError,http.client.HTTPException,UnicodeError):
        return None
    return None
