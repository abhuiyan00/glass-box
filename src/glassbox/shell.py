"""One <head>, one header, one footer, for every document the site emits.

Every path this module writes is **relative to the document that contains it**. That is not a
style choice: the site must open by double-clicking a file, and an absolute `/assets/app.css`
resolves to the drive root under `file://`, so a downloaded copy would render unstyled with a
dead search box. `rel(depth)` is the whole mechanism — `""` at the root, `"../"` one level
down — and every link goes through it.

The consequence is that page URLs end in `.html` rather than being pretty directories. A
directory link resolves to its index only when a server says so, and there is no server when
someone opens the folder. Ugly URL, working file. That trade is stated here because it is the
kind of thing a reader will otherwise assume was an oversight.
"""

import html
import json
import tomllib
from pathlib import Path

NAV = [("index", "Ask"), ("browse", "Browse"), ("map", "Map"), ("receipts", "Receipts"),
       ("gaps", "Gaps"), ("how", "How it works")]

# The search box that follows the reader. The landing page owns the big one; every other
# document gets this, because the previous arrangement asked somebody who had just read a page
# about `pytest` to navigate home before they could ask a second question. 232 pages, one
# entry point.
#
# It is a real `<form method="get">` pointing at the landing page, which is what makes it work
# with JavaScript switched off — the browser builds `index.html?q=…` on submit and the landing
# page's own URL handler runs it. With JavaScript on, the same input carries `data-ask`, so it
# gets the full typeahead and can open a page directly without a round trip.
SEARCH_FORM = """<form class="hs" role="search" method="get" action="{base}index.html">
      <label class="vh" for="q">Search this knowledge base</label>
      <div class="ask-w">
        <input id="q" class="ask-i hs-i" name="q" type="search" autocomplete="off"
          spellcheck="false" data-ask role="combobox" aria-expanded="false"
          aria-controls="sg" aria-autocomplete="list" placeholder="Search…">
        <ul class="sg-box" id="sg" role="listbox" aria-label="Suggestions"
          data-suggest hidden></ul>
      </div>
      <button class="vh" type="submit">Search</button>
    </form>"""

# The theme control names the theme it will switch *to*, and it is rendered as two spans with
# CSS choosing between them rather than one span with JavaScript rewriting it.
#
# It said "Theme" before, which is the label on the setting and not on the action — a button
# that never changes cannot tell you which mode you are in or what pressing it does.
#
# The reason CSS decides is first paint. The theme comes from the OS preference or from
# localStorage, and the build knows neither, so a server-rendered word is a coin flip that
# JavaScript then corrects — which is a visible flicker on every page load, and the wrong word
# entirely for anyone who blocks scripts. `display: none` also keeps the hidden span out of
# the accessibility tree, so the button's accessible name is "Switch to Dark" or "Switch to
# Light" and never both.
THEME_TOGGLE = """<button class="ghost theme-b" type="button" data-theme-toggle>
      <span class="vh">Switch to </span>
      <span class="th-i" aria-hidden="true"></span>
      <span class="th-d">Dark</span><span class="th-l">Light</span>
    </button>"""

# A box inside a box: the site's one piece of iconography, inlined as a data URI so the
# favicon is not a fifth network request. Percent-encoded rather than raw — `<` and `>` in an
# attribute value are legal and every browser accepts them, but they are exactly the thing a
# proxy or a strict sanitiser rewrites, and the failure is silent.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2016%2016'%3E"
    "%3Crect%20width='16'%20height='16'%20rx='3'%20fill='%230b6e80'/%3E"
    "%3Crect%20x='4.5'%20y='4.5'%20width='7'%20height='7'%20rx='1'%20fill='none'"
    "%20stroke='white'%20stroke-width='1.5'/%3E%3C/svg%3E"
)


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def load_config(root):
    """glassbox.toml, merged over defaults. Never raises: a missing key is not fatal."""
    defaults = {
        "author": {"name": "", "github": "", "role": "", "location": ""},
        "site": {"title": "Glass Box", "subtitle": "", "out": "docs", "content": "content",
                 "url": ""},
        "budget": {"landing_kb": 120, "index_kb": 250},
    }
    try:
        raw = tomllib.loads((Path(root) / "glassbox.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    for section, values in raw.items():
        if isinstance(values, dict):
            defaults.setdefault(section, {}).update(values)
    return defaults


def rel(depth):
    """`depth` is how many directories down the document sits — or a literal base to use.

    The string form exists for exactly one document. A host serves `404.html` for any
    unmatched path at any depth, so that page is rendered once and read from `/p/typo.html`
    as readily as from `/typo.html`; a relative `assets/app.css` would resolve against
    whichever directory the reader guessed at and arrive unstyled. It passes `"/"` and is the
    only page on the site that may.
    """
    return depth if isinstance(depth, str) else "../" * depth


def num(value):
    """A measured number, or a visible gap. Never a plausible zero for an unknown.

    A float keeps two decimals even when it is whole. A retrieval score of 1.0 printed as
    "1" sits in a column next to 0.58 and reads as a count of one rather than a perfect
    ratio — the trailing zeros are what say "this is a proportion".
    """
    if value is None:
        return '<span class="gap-cell" title="not measured">not measured</span>'
    if isinstance(value, float):
        return esc(f"{value:.2f}")
    if isinstance(value, int) and value >= 10000:
        return esc(f"{value:,}")
    return esc(value)


def site_url(cfg):
    """The public origin, with exactly one trailing slash, or `""` if none is configured.

    Empty is a supported state, not a missing one. Absolute URLs are required by `og:url`,
    `rel=canonical` and `sitemap.xml`, and this repository has no remote to derive an origin
    from — so rather than guess `<user>.github.io/<repo>` and emit a canonical tag pointing at
    a page that may not exist, those three are omitted entirely until someone fills the key in.
    The parts that do not need an origin (`og:title`, the card type, the JSON-LD identity)
    ship either way, so a link pasted into Slack or LinkedIn still previews as something.
    """
    return (cfg["site"].get("url") or "").strip().rstrip("/") + "/" \
        if (cfg["site"].get("url") or "").strip() else ""


def ld(data):
    """One JSON-LD block. `<` is escaped so a string can never close the script element."""
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return ('<script type="application/ld+json">'
            + blob.replace("<", "\\u003c") + "</script>")


def social(title, description, path, cfg):
    """Open Graph and the Twitter card.

    A site built to be sent to somebody — a recruiter, an interviewer — that previews in
    their chat client as a bare grey URL is losing the first impression before the page
    opens. These tags are the whole of that fix and cost four lines of head.

    No `og:image`. Every platform that matters rasterises, so the card wants a PNG or JPEG,
    and this repository holds no binary assets and no image encoder — the honest options were
    a checked-in binary that nothing regenerates or a dependency, and both cost more than the
    thumbnail is worth. Named in AUDIT.md rather than left as a silent omission.
    """
    origin = site_url(cfg)
    tags = [
        f'<meta property="og:type" content="{"website" if path == "index.html" else "article"}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:site_name" content="{esc(cfg["site"]["title"])}">',
        '<meta name="twitter:card" content="summary">',
    ]
    if origin:
        tags.append(f'<meta property="og:url" content="{esc(origin + path)}">')
        tags.append(f'<link rel="canonical" href="{esc(origin + path)}">')
    return "\n".join(tags)


def head(title, description, depth, cfg, path="", jsonld=None):
    base = rel(depth)
    site = cfg["site"]["title"]
    full = title if title == site else f"{title} · {site}"
    blocks = "".join(ld(d) for d in (jsonld or []))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(description)}">
<meta name="color-scheme" content="light dark">
{social(full, description, path, cfg)}
<link rel="stylesheet" href="{base}assets/app.css">
<link rel="icon" href="{FAVICON}">
{blocks}
<script>/* Restore the saved theme before the first paint. In app.js this ran at the end of
the body, which is after the browser has already painted the other theme — a white flash on
every navigation for anyone whose choice disagrees with their OS. Inline and in the head is
the only place this can go. No network call: it is four statements. */
try{{var t=localStorage.getItem('gb-theme');
if(t)document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
</head>
<body data-base="{base}">
<a class="skip" href="#main">Skip to content</a>"""


def header(current, depth, cfg):
    base = rel(depth)
    parts = []
    for slug, label in NAV:
        mark = ' aria-current="page"' if slug == current else ""
        parts.append(f'<a href="{base}{slug}.html"{mark}>{esc(label)}</a>')
    links = "".join(parts)
    name = cfg["author"]["name"]
    who = f'<span class="who">{esc(name)}</span>' if name else ""
    title = esc(cfg["site"]["title"])
    # Not on the landing page, which already opens with the box this is a shrunk copy of.
    # Two elements carrying `data-ask` would also give the runtime two combobox inputs and one
    # suggestion list to bind them to, and it binds the first — so the visible one on that
    # page would be the dead one.
    find = "" if current == "index" else SEARCH_FORM.format(base=base)
    return f"""
<header class="top">
  <a class="brand" href="{base}index.html">
    <span class="mark" aria-hidden="true"></span>
    <span class="brand-t">{title}</span>
  </a>
  <nav class="nav" aria-label="Sections">{links}</nav>
  <div class="top-r">
    {find}
    {who}
    {THEME_TOGGLE}
  </div>
</header>
<main id="main">"""


def footer(depth, cfg, stats):
    base = rel(depth)
    gh = cfg["author"]["github"]
    gh_link = f'<a href="{esc(gh)}" rel="noopener">GitHub</a>' if gh else ""
    corpus = stats.get("corpus") or {}
    title = esc(cfg["site"]["title"])
    return f"""</main>
<footer class="foot">
  <div>
    <p class="foot-t">{title}</p>
    <p>Rendered from a private wiki of {num(corpus.get("pages_knowledge"))} pages;
      {num(corpus.get("published_now"))} of them are public. Every figure on this site was
      computed at build time from the same source as the pages.</p>
  </div>
  <nav aria-label="Footer">
    <a href="{base}browse.html">Browse everything</a>
    <a href="{base}receipts.html">The numbers, and how each is counted</a>
    <a href="{base}gaps.html">What it does not know</a>
    <a href="{base}how.html">How it works</a>
    {gh_link}
  </nav>
  <p class="built">Built {esc(stats.get("generated", ""))} · no trackers, no cookies,
    no network calls</p>
</footer>
<script src="{base}assets/search-index.js"></script>
<script src="{base}assets/app.js"></script>
</body>
</html>
"""


def document(title, description, body, *, current, depth, cfg, stats,
             path="", jsonld=None):
    """The only function that emits a complete page. Views return `body` and nothing else."""
    return (head(title, description, depth, cfg, path=path, jsonld=jsonld)
            + header(current, depth, cfg)
            + body
            + footer(depth, cfg, stats))
