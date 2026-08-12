"""Audit a built site for dead links, leaked privacy data and outbound requests.

    python tools/audit_site.py docs

AUDIT.md §14 records the standing tension: the contrast probe and the header-search
suite need `playwright` and `jsdom`, so they live outside the repository, and the checks
they perform are therefore not reproducible by a reader. This tool takes back the part of
that ground which does not need a browser. It is stdlib-only, so it costs the
zero-dependency claim nothing, and it reads every page rather than the handful a browser
harness has time to visit.

What it will not tell you: computed contrast, focus order, or anything that depends on
layout. Those still need a real engine. What it does tell you is the class of regression
that actually ships — a renamed page leaving dead links behind, a machine name reaching
the public build, or a stylesheet that quietly points at a CDN.

Two distinctions the naive version of this script gets wrong, both of which produced
false failures before they were fixed:

  * `<a href="https://…">` is a **link**, not a request. Only `src`/`href` on a
    resource-loading element (script, link, img, iframe, …) makes the page reach the
    network. The site has 239 external citations and zero remote loads; a checker that
    conflates them reports the site's honesty as a violation.
  * `<script type="application/ld+json">` is **data**. Matching `WebSocket` or `fetch(`
    inside it — or inside prose on a page that documents networking code — finds the
    subject matter, not behaviour.
"""

import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag

RESOURCE_TAGS = {"script", "link", "img", "iframe", "source", "video", "audio",
                 "embed", "object", "track"}

# Executable script only. JSON-LD and other data blocks carry a type that is not
# JavaScript, and their contents are strings, not statements.
JS_TYPES = {"", "text/javascript", "application/javascript", "module"}

NETWORK_CALL = re.compile(r"\b(fetch\s*\(|XMLHttpRequest|new\s+WebSocket|sendBeacon)")

PRIVACY = [
    (re.compile(r"DESKTOP-[A-Z0-9]+"), "developer machine name"),
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\"'<>\s]+"), "local user path"),
    (re.compile(r"(?i)mongodb(\+srv)?://[^\s\"'<]+"), "database connection string"),
    (re.compile(r"(?i)\b(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{8,}"), "payment key"),
    (re.compile(r"(?i)password\s*[=:]\s*[\"'][^\"']{3,}"), "inline password"),
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@(?:gmail|outlook|yahoo|hotmail)\.[a-z]{2,}"),
     "personal email address"),
]

REMOTE = re.compile(r"^(?:https?:)?//", re.I)
NON_FETCHING = ("mailto:", "tel:", "data:", "#", "javascript:", "blob:")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []          # (tag, url) for every reference
        self.remote_loads = []   # references that cause a network request
        self.images = 0
        self.images_no_alt = 0
        self.lang = None
        self.has_title = False
        self.scripts = []
        self._script_is_js = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        url = a.get("href") or a.get("src")

        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "img":
            self.images += 1
            if a.get("alt") is None:
                self.images_no_alt += 1
        elif tag == "script":
            self._script_is_js = a.get("type", "").lower() in JS_TYPES

        if url:
            self.links.append((tag, url))
            if tag in RESOURCE_TAGS and REMOTE.match(url):
                self.remote_loads.append((tag, url))

    def handle_data(self, data):
        if self._in_title and data.strip():
            self.has_title = True
        elif self._script_is_js:
            self.scripts.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._script_is_js = False


def audit(root):
    findings = {"broken": [], "remote": [], "network": [], "privacy": [],
                "no_lang": [], "no_title": [], "no_alt": []}
    external = Counter()
    pages = 0

    for dirpath, _, files in os.walk(root):
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            pages += 1
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            text = open(path, encoding="utf-8", errors="replace").read()

            page = Page()
            page.feed(text)

            if not page.lang:
                findings["no_lang"].append(rel)
            if not page.has_title:
                findings["no_title"].append(rel)
            if page.images_no_alt:
                findings["no_alt"].append((rel, page.images_no_alt))

            for tag, url in page.remote_loads:
                findings["remote"].append((rel, tag, url))

            for body in page.scripts:
                if NETWORK_CALL.search(body):
                    findings["network"].append(rel)
                    break

            for pattern, label in PRIVACY:
                for hit in pattern.findall(text):
                    findings["privacy"].append((rel, label, str(hit)[:60]))

            for tag, url in page.links:
                if REMOTE.match(url):
                    external[url.split("/")[2] if "//" in url else url] += 1
                    continue
                if url.startswith(NON_FETCHING):
                    continue
                target = unquote(urldefrag(url)[0])
                if not target:
                    continue
                base = root if target.startswith("/") else os.path.dirname(path)
                dest = os.path.normpath(os.path.join(base, target.lstrip("/")))
                if os.path.isdir(dest):
                    dest = os.path.join(dest, "index.html")
                if not os.path.exists(dest):
                    findings["broken"].append((rel, url))

    return pages, findings, external


def main(argv):
    root = argv[1] if len(argv) > 1 else "docs"
    if not os.path.isdir(root):
        print(f"no such directory: {root}", file=sys.stderr)
        return 2

    pages, f, external = audit(root)

    print(f"pages                     {pages}")
    print(f"dead internal links       {len(f['broken'])}")
    for rel, url in f["broken"][:20]:
        print(f"    {rel} -> {url}")
    print(f"remote resource loads     {len(f['remote'])}")
    for rel, tag, url in f["remote"][:20]:
        print(f"    {rel} <{tag}> {url}")
    print(f"scripts calling the network {len(f['network'])}")
    for rel in f["network"][:20]:
        print(f"    {rel}")
    print(f"privacy matches           {len(f['privacy'])}")
    for rel, label, hit in f["privacy"][:20]:
        print(f"    {rel}  {label}: {hit}")
    print(f"pages without <html lang> {len(f['no_lang'])}")
    print(f"pages without <title>     {len(f['no_title'])}")
    print(f"images missing alt        {sum(n for _, n in f['no_alt'])}")
    print(f"external citations        {sum(external.values())} "
          f"across {len(external)} hosts (links, not requests)")

    failed = [k for k in ("broken", "remote", "network", "privacy",
                          "no_lang", "no_title", "no_alt") if f[k]]
    print()
    if failed:
        print("FAIL:", ", ".join(failed))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
