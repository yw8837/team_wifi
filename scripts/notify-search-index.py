"""Notify IndexNow of changes in the two public sitemaps. Run on demand or on a timer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ORIGIN = "https://moduyuga.yeolmaeapps.kr"
KEY = "c70b27f9540e408d84d201bbd264a1cc"
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".runtime/search-index/state.json"

def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != urlsplit(ORIGIN).netloc or parsed.query or parsed.fragment:
        raise ValueError("Expected a canonical service URL")
    return url

def fetch(url):
    with urlopen(Request(public_url(url), headers={"User-Agent": "ModuYuga-IndexCheck/1.0"}), timeout=25) as response:
        public_url(response.url)
        return response.read()

def entries(url, depth=0):
    if depth > 2:
        raise ValueError("Nested sitemap limit")
    xml = ElementTree.fromstring(fetch(url))
    if xml.tag.endswith("}sitemapindex"):
        for child in xml:
            yield from entries(public_url(child.findtext("{*}loc")), depth + 1)
    elif xml.tag.endswith("}urlset"):
        for child in xml:
            yield public_url(child.findtext("{*}loc")), child.findtext("{*}lastmod") or ""
    else:
        raise ValueError("Invalid sitemap response")

def fingerprint(entry):
    url, stamp = entry
    if "/groupbuys/" in url and stamp:
        return url, stamp
    return url, sha256(fetch(url)).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", default=[], help="Also notify for a selected listed or removed URL")
    args = parser.parse_args()
    old = json.loads(STATE.read_text()) if STATE.exists() else {}
    urls = [*entries(ORIGIN + "/sitemap.xml"), *entries(ORIGIN + "/groupbuys/sitemap.xml")]
    if not urls: raise ValueError("Empty sitemap")
    with ThreadPoolExecutor(max_workers=4) as pool:
        current = dict(pool.map(fingerprint, urls))
    changed = {u for u in old.keys() | current.keys() if old.get(u) != current.get(u)}
    for url in args.url:
        if public_url(url) not in current and url not in old:
            raise ValueError("URL outside public sitemaps")
        changed.add(url)
    if changed:
        if fetch(ORIGIN + "/" + KEY + ".txt").decode().strip() != KEY:
            raise ValueError("Ownership key mismatch")
        listing = sorted(changed)
        for i in range(0, len(listing), 10000):
            body = {"host": urlsplit(ORIGIN).netloc, "key": KEY, "urlList": listing[i:i+10000]}
            req = Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
            with urlopen(req, timeout=30) as response:
                if response.status not in (200, 202): raise RuntimeError(response.status)
                print("IndexNow", response.status, "submitted", len(body["urlList"]))
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(current, sort_keys=True))
        tmp.replace(STATE)
    print("Public URLs", len(current), "changes", len(changed))

if __name__ == "__main__":
    main()
