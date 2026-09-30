"""网络层：SSRF 防护、域名公网校验、页面抓取与资源探测。

仅使用 Python 标准库，零第三方依赖。抓取逻辑对齐线上 PHP 版本：
  - 自动协商并解压 gzip / deflate / br，避免拿到压缩乱码导致评分失真；
  - 仅允许公网 http/https，拒绝内网 / 回环 / 保留地址与非标准端口。
"""

import gzip
import ipaddress
import socket
import zlib

try:
    import brotli  # 可选依赖，仅用于解码 br 压缩
except Exception:  # pragma: no cover
    brotli = None

import urllib.request
import urllib.error

MAX_BYTES = 1_200_000  # 单页抓取上限 ~1.2MB
UA = "Mozilla/5.0 (compatible; GooFutureAIChecker/1.1; +https://goofuture.com/)"
DEFAULT_TIMEOUT = 12
PROBE_TIMEOUT = 6

_DOMAIN_RE = (
    r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$"
)


def is_public_domain(domain):
    import re
    if not re.match(_DOMAIN_RE, domain):
        return False
    try:
        ip = socket.gethostbyname(domain)
    except Exception:
        return False
    if ip == domain:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local:
        return False
    return True


def ssrf_check(url):
    """返回 (ok: bool, msg: str, host: str)。"""
    import re
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return False, "仅支持 http/https 开头的网址", ""
    from urllib.parse import urlparse
    p = urlparse(url)
    if not p.hostname:
        return False, "无效的网址，请检查是否填写完整", ""
    if p.port and p.port not in (80, 443):
        return False, "仅支持标准 80/443 端口的网址", ""
    host = p.hostname.lower()
    if host in ("localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0") \
            or host.endswith(".local") \
            or re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|127\.)", host):
        return False, "不支持检测内网 / 本地地址", ""
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        return False, "域名无法解析，请确认网址可以公开访问", ""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False, "DNS 解析异常", ""
    if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local:
        return False, "不支持检测内网 / 保留地址", ""
    return True, "", host


def _decompress(data, encoding):
    enc = (encoding or "").lower()
    if not enc or enc == "identity":
        return data
    try:
        if "gzip" in enc:
            return gzip.decompress(data)
        if "deflate" in enc:
            try:
                return zlib.decompress(data)
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS)
        if "br" in enc:
            if brotli is None:
                raise RuntimeError("服务器返回 br 压缩，但本机未安装 brotli（pip install brotli）")
            return brotli.decompress(data)
    except Exception as e:
        raise RuntimeError("解压响应体失败：%s" % e)
    return data


def fetch_body(url, timeout=DEFAULT_TIMEOUT):
    """抓取页面正文，返回 (body: str, http_code: int, final_url: str, error: str)。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = b""
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                raw += chunk
                if len(raw) > MAX_BYTES:
                    break
            code = resp.getcode()
            final_url = resp.geturl()
            encoding = resp.headers.get("Content-Encoding", "")
            ctype = resp.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        return "", e.code, url, str(e)
    except Exception as e:  # noqa: BLE001
        return "", 0, url, str(e)

    try:
        data = _decompress(raw, encoding)
    except Exception as e:
        return "", code, final_url, str(e)
    try:
        body = data.decode(ctype, errors="replace")
    except Exception:
        body = data.decode("utf-8", errors="replace")
    return body, code, final_url, ""


def probe_reachable(url, timeout=PROBE_TIMEOUT):
    """轻量探测资源（llms.txt / robots.txt / sitemap.xml）是否可达。"""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
        return 200 <= code < 400
    except Exception:  # noqa: BLE001
        # 部分服务器不支持 HEAD，退化为 GET 仅取状态码
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
            return 200 <= code < 400
        except Exception:  # noqa: BLE001
            return False


def normalize_url(raw):
    """补全协议；返回 (final_url, domain, error)。"""
    import re
    from urllib.parse import urlparse
    raw = (raw or "").strip()
    if not raw:
        return "", "", "请输入企业官网地址"
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    ok, msg, host = ssrf_check(raw)
    if not ok:
        return "", "", msg
    domain = re.sub(r"[^a-z0-9.\-]", "", host.lower())[:64]
    if not domain:
        return "", "", "域名格式不正确"
    return raw, domain, ""
