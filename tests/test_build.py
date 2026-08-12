"""The build is the fixture. Everything here asserts against real rendered output.

There is no mock bundle: the checks that matter are about what actually ships — that no
private page is named as a link, that no figure was typed into a template, that a tampered
bundle stops the build. A test over a synthetic three-page corpus would pass while the site
leaked, so the corpus under test is the one being published.
"""

import gzip
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glassbox import receipts, search, views       # noqa: E402
from glassbox.content import Bundle, BundleError   # noqa: E402
from glassbox.markdown import render               # noqa: E402
from glassbox.shell import load_config, num        # noqa: E402


@pytest.fixture(scope="session")
def bundle():
    try:
        return Bundle(ROOT / "content")
    except BundleError as e:
        pytest.skip(f"no content bundle to test against: {e}")


@pytest.fixture(scope="session")
def cfg():
    return load_config(ROOT)


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """One real build into a temp directory, shared by every test that needs output."""
    out = tmp_path_factory.mktemp("site") / "docs"
    r = subprocess.run([sys.executable, str(ROOT / "build.py"), "--content",
                        str(ROOT / "content"), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def test_explicit_output_cannot_overlap_source(bundle, cfg, tmp_path):
    """A preview convenience must not turn a typo into recursive source deletion."""
    import build as build_mod

    for unsafe in (ROOT, ROOT.parent, ROOT / "src", ROOT / "content"):
        with pytest.raises(ValueError):
            build_mod.output_path(["--out", str(unsafe)], cfg, ROOT / "content", False)

    safe = tmp_path / "site"
    assert build_mod.output_path(["--out", str(safe)], cfg, ROOT / "content", False) == safe
    with pytest.raises(ValueError):
        build_mod.output_path(["--check", "--out", str(safe)], cfg, ROOT / "content", True)


# -- the bundle contract -------------------------------------------------------------

def test_manifest_covers_every_file(bundle):
    listed = set(bundle.manifest["files"])
    on_disk = {p.relative_to(bundle.root).as_posix()
               for p in bundle.root.rglob("*") if p.is_file()} - {"MANIFEST.json"}
    assert listed == on_disk, "a file in content/ is not hashed by the manifest"


def test_tampered_bundle_stops_the_build(bundle):
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "content"
        shutil.copytree(bundle.root, copy)
        victim = next(iter(sorted((copy / "pages").glob("*.md"))))
        victim.write_text(victim.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        with pytest.raises(BundleError) as e:
            Bundle(copy)
        assert victim.name in str(e.value)


def test_no_session_page_was_exported(bundle):
    assert not [p for p in bundle.pages if p["type"] == "session"]


def test_every_page_has_a_body_and_a_gist(bundle):
    for page in bundle.pages:
        assert bundle.bodies[page["stem"]].strip(), f"{page['stem']} has no body"
        assert page.get("gist"), f"{page['stem']} has no one-line summary to lead with"


def test_links_point_only_at_published_pages(bundle):
    for page in bundle.pages:
        for target in page.get("links") or []:
            assert target in bundle.published


# -- rendering -----------------------------------------------------------------------

def test_every_page_renders(bundle, cfg):
    from glassbox.pages import article
    for page in bundle.pages:
        doc, _heads, _missing = article(bundle, page, cfg)
        assert doc.startswith("<!doctype html>")
        assert doc.rstrip().endswith("</html>")


def test_unpublished_wikilink_is_text_not_an_anchor():
    """Defence in depth. The exporter strips these before they arrive, so reaching this
    branch means the bundle disagrees with its own index — it must still not emit a link."""
    html, _heads, missing = render("See [[secret-page|a private note]] and [[known]].",
                                   {"known"}, lambda s: f"{s}.html")
    assert "a private note" in html
    assert 'href="secret-page' not in html
    assert "secret-page" not in html, "the private stem leaked through the label"
    assert missing == ["secret-page"]


def test_the_unpublished_marker_renders_as_styled_text():
    html, _heads, missing = render("It links {{a private note}} here.", set(), lambda s: s)
    assert '<span class="unpub"' in html
    assert "a private note" in html
    assert "<a" not in html
    assert missing == ["a private note"]


def test_no_page_body_names_a_page_outside_the_bundle(bundle):
    """The committed bundle is public markdown. Every wikilink left in it must resolve."""
    stray = re.compile(r"\[\[([^\]|#\n]+)")
    for stem, body in bundle.bodies.items():
        # Code spans hold quoted evidence, which may legitimately contain a wikilink.
        prose = re.sub(r"`[^`\n]*`", " ", re.sub(r"^```.*?^```", " ", body, flags=re.S | re.M))
        for target in stray.findall(prose):
            assert target.strip() in bundle.published, \
                f"{stem} names [[{target.strip()}]], which is not in this bundle"


def test_script_tags_in_a_page_render_as_text():
    html, _h, _m = render("A paragraph with <script>alert(1)</script> in it.",
                          set(), lambda s: s)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_unmeasured_figures_render_as_a_visible_gap():
    assert "gap-cell" in num(None)
    assert "not measured" in num(None)
    assert num(0) == "0", "a real zero must not render as a gap"
    assert num(1.0) == "1.00", "a ratio must keep its decimals next to 0.58"


# -- the shipped site ----------------------------------------------------------------

def test_no_absolute_asset_or_page_paths(built):
    """Absolute paths break file:// — the site must open from a folder.

    `404.html` is the sole exemption and it is named here rather than pattern-matched, so
    adding a second such page is a decision somebody has to write down. A host serves that
    one document for every unmatched path at every depth: read from `/p/typo.html`, a
    relative `assets/app.css` resolves to `/p/assets/app.css` and the page arrives unstyled
    with a dead search box — which is the worst possible state for the page a lost reader
    lands on. It is unreachable from disk anyway; a missing local file never reaches a
    renderer at all.
    """
    bad = []
    for page in sorted(built.rglob("*.html")):
        if page.name == "404.html":
            continue
        for m in re.finditer(r'(?:href|src)="(/[^"]*)"', page.read_text(encoding="utf-8")):
            bad.append(f"{page.name}: {m.group(1)}")
    assert not bad, bad


def test_404_is_absolute_throughout(built):
    """The other half of the exemption above: it must be absolute *everywhere*, not mostly.

    One relative path left in this document is the failure the exemption exists to prevent,
    and it would show up only for a reader who mistyped a URL two directories down.
    """
    text = (built / "404.html").read_text(encoding="utf-8")
    bad = [m.group(0) for m in re.finditer(r'(?:href|src|action)="(?!/|https?:|data:|#)[^"]*"',
                                           text)]
    assert not bad, bad


def test_no_outbound_requests_in_markup(built):
    """No CDN, no font host, no analytics. The network tab stays empty."""
    allowed = re.compile(r'https?://(?:www\.w3\.org|github\.com)')
    bad = []
    for page in sorted(built.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for m in re.finditer(r'(?:href|src)="(https?://[^"]+)"', text):
            if not allowed.match(m.group(1)):
                bad.append(f"{page.name}: {m.group(1)}")
    assert not bad, bad


def test_search_index_is_a_script_not_a_fetch(built):
    idx = (built / "assets" / "search-index.js").read_text(encoding="utf-8")
    assert idx.startswith("/*")
    assert "window.GLASSBOX=" in idx
    app = (built / "assets" / "app.js").read_text(encoding="utf-8")
    assert "fetch(" not in app, "fetch is blocked under file:// — the index must be a script"


def test_map_filters_are_native_toggle_buttons(built):
    """Every visual map filter must work from a keyboard and announce its state.

    A native button supplies Enter/Space behavior without recreating it in JavaScript. The
    repository name stays a separate link, so filtering and navigation remain distinct
    actions for keyboard and screen-reader users.
    """
    text = (built / "map.html").read_text(encoding="utf-8")
    ring_rows = re.findall(r'<li class="ring-r" data-ring="[^"]+">', text)
    ring_buttons = re.findall(
        r'<button type="button" class="ring-i" data-map-ring="[^"]+" '
        r'aria-pressed="false" aria-label="[^"]+">', text)
    assert ring_rows
    assert len(ring_buttons) == len(ring_rows)
    assert re.search(r'<span class="ring-t"><a href="p/[^"]+\.html">', text)

    kind_buttons = re.findall(
        r'<button type="button" class="lg [^"]+" data-map-kind="[^"]+" '
        r'aria-pressed="false">', text)
    assert kind_buttons

    app = (built / "assets" / "app.js").read_text(encoding="utf-8")
    assert "b.setAttribute('aria-pressed'" in app
    assert "e.key === 'Enter'" not in app and "e.key === ' '" not in app, \
        "native buttons must own keyboard activation; do not duplicate it in JavaScript"


def test_index_contains_only_published_pages(bundle, built):
    raw = (built / "assets" / "search-index.js").read_text(encoding="utf-8")
    data = json.loads(raw[raw.index("window.GLASSBOX=") + len("window.GLASSBOX="):].rstrip(";\n"))
    assert {d["s"] for d in data["docs"]} == bundle.published


def test_scorer_parameters_come_from_the_bundle(bundle):
    """Not retyped here, not retyped in JavaScript. One source, shipped as data."""
    idx = search.build(bundle)
    assert idx["field"] == bundle.scorer["field"]
    assert idx["floor"] == bundle.scorer["floor"]
    assert idx["hop"] == bundle.scorer["hop"]


# -- the index encoding must not be a reranking ---------------------------------------
#
# `search.build` stopped spelling terms out and started shipping integer ids into a shared
# vocabulary, which took the index from 247 KB gzipped to 155 at 232 pages. That is a pure
# win only if it is invisible: the site's central claim is that it runs the author's own
# retrieval, and an encoding that moved a result two places down would break it silently,
# with no failing build and no visible symptom. So the old encoding is kept alive here, as a
# reference implementation, and the two are scored against each other.

def _score(docs, idf_of, field, floor, hop, q):
    """The client scorer, in Python. Mirrors `search()` in assets/app.js line for line.

    `docs` is [{s, f: {name: set(term)}, tf: {term: count}, n, l}] where `term` is whatever
    the caller's encoding uses — a word for the reference, an int for the shipped index. The
    arithmetic never looks inside a term, which is exactly why the swap is safe.
    """
    if not q:
        return []
    direct = []
    for d in docs:
        total, covered = 0.0, set()
        for name, ids in d["f"].items():
            hits, ssum = 0, 0.0
            for t in q:
                if t in ids:
                    hits += 1
                    ssum += idf_of(t)
                    covered.add(t)
            if hits:
                total += field[name] * hits * ssum / len(q)
        body = 0.0
        for t in q:
            c = d["tf"].get(t)
            if c:
                body += idf_of(t) * (1 + math.log(c))
                covered.add(t)
        total += field["body"] * body / (1 + math.log(1 + d["n"]))
        if total > 0:
            direct.append((d["s"], total * (len(covered) / len(q)) ** 2))

    kept = [p for p in direct if p[1] >= floor]
    by_stem = {d["s"]: d for d in docs}
    out = {s: v for s, v in kept}
    for s, v in kept:
        for nb in by_stem[s]["l"]:
            if nb not in out and nb in by_stem:
                out[nb] = v * hop
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))[:5]


def _reference(bundle):
    """The pre-change encoding: every term spelled out, idf keyed by word."""
    terms = search.tokenizer(bundle.scorer)
    docs, df = [], Counter()
    for page in sorted(bundle.pages, key=lambda p: p["stem"]):
        tf = Counter(terms(search.plain(bundle.bodies[page["stem"]])))
        df.update(set(tf))
        docs.append({"s": page["stem"], "n": sum(tf.values()), "tf": dict(tf),
                     "f": {k: set(v) for k, v in search.fields(page, terms).items()},
                     "l": sorted(page.get("links") or [])})
    n = len(docs) or 1
    idf = {w: round(math.log(n / (1 + c)) + 0.5, 4) for w, c in df.items()}
    default = round(math.log(n + 1), 4)
    return docs, (lambda t: idf.get(t, default)), terms


def _shipped(idx):
    """The index as the browser receives it, decoded the way `hydrate()` decodes it."""
    def ungap(a):
        out, run = [], 0
        for v in a:
            run += v
            out.append(run)
        return out

    docs = []
    for d in idx["docs"]:
        ids = ungap(d["ti"])
        docs.append({"s": d["s"], "n": d["n"], "l": d["l"],
                     "tf": dict(zip(ids, d["tc"])),
                     "f": {k: set(ungap(v)) for k, v in d["f"].items()}})
    at = {w: i for i, w in enumerate(idx["vocab"])}
    return docs, (lambda t: idx["idf"][t] if t >= 0 else idx["idf_default"]), at


QUERIES = [
    "how do you decide what to test?", "star schema", "why not kubernetes",
    "what database did you use", "tell me about a hard bug", "etl load order",
    "how do you handle secrets", "react", "docker compose networking",
    "fixed timestep", "anonymisation", "what is a fact grain",
    "zzzzz nothing matches this", "the and of a", "SQL injection defence",
    "graph database", "why did you choose python", "offline first",
]


def test_the_integer_index_scores_identically_to_spelled_out_terms(bundle):
    ref_docs, ref_idf, terms = _reference(bundle)
    idx = search.build(bundle)
    new_docs, new_idf, at = _shipped(idx)
    scorer = bundle.scorer
    for query in QUERIES:
        words = terms(query)
        a = _score(ref_docs, ref_idf, scorer["field"], scorer["floor"], scorer["hop"], words)
        b = _score(new_docs, new_idf, scorer["field"], scorer["floor"], scorer["hop"],
                   [at.get(w, -1) for w in words])
        assert [s for s, _ in a] == [s for s, _ in b], f"ranking moved for {query!r}"
        for (_, x), (_, y) in zip(a, b):
            assert abs(x - y) < 1e-9, f"score changed for {query!r}"


def test_a_field_only_term_still_scores(bundle):
    """A word in a title or alias that no body uses must keep its id and its default weight.

    This is the case the first version of the encoding got wrong. Admitting only body terms
    to the vocabulary looked like a tidy-up and deleted a live scoring path.
    """
    idx = search.build(bundle)
    body_terms = set()
    for d in idx["docs"]:
        run = 0
        for gap in d["ti"]:
            run += gap
            body_terms.add(run)
    field_terms = set()
    for d in idx["docs"]:
        for ids in d["f"].values():
            run = 0
            for gap in ids:
                run += gap
                field_terms.add(run)
    only_in_fields = field_terms - body_terms
    assert only_in_fields, "expected at least one term carried by a field and no body"
    for tid in only_in_fields:
        assert idx["idf"][tid] == idx["idf_default"]


def test_the_index_is_deterministic(bundle):
    """Two builds of one bundle must be byte-identical, or 'nothing changed' is a hope."""
    assert search.as_script(search.build(bundle)) == search.as_script(search.build(bundle))


def test_every_page_has_an_html_file(bundle, built):
    for page in bundle.pages:
        assert (built / "p" / f"{page['stem']}.html").is_file()


def test_landing_is_inside_its_budget(built, cfg):
    kb = len(gzip.compress((built / "index.html").read_bytes(), 9)) / 1024
    assert kb <= cfg["budget"]["landing_kb"]


def test_receipts_prints_no_hand_written_number(bundle, cfg):
    """Every figure in the receipts table must appear in stats.json."""
    html = receipts.receipts(bundle, cfg)
    cells = re.findall(r'<td class="fig">([^<]*)</td>', html)
    known = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            known.add(f"{node:.2f}" if isinstance(node, float) else str(node))

    walk(bundle.stats)
    for cell in cells:
        if cell.strip():
            assert cell.strip() in known, f"{cell!r} is not in stats.json"


def test_landing_leads_with_the_question_box(bundle, cfg):
    """The whole point of the redesign, asserted rather than remembered.

    The previous front page opened with a table of retrieval metrics. Nothing above the ask
    box may be a figure again — the nav may *link* to the receipts page, but the landing
    document must carry no table and no statistic before the input.
    """
    html = views.landing(bundle, cfg)
    # Anchored on the input rather than on a marker attribute that only this test read. The
    # form carried `data-askform` purely so this line could find it; when the runtime started
    # locating the form through `field.form` instead, the attribute went and took the test
    # with it. A test that depends on a hook nothing else uses is testing its own scaffolding.
    ask = html.index("data-ask")
    assert ask < html.index('class="tiles"'), "browse tiles must not precede the ask box"
    above = html[:ask]
    assert "<table" not in above, "a table appears above the question box"
    assert 'class="fig"' not in above, "a statistic appears above the question box"


def test_landing_qualifies_sources_and_links_to_receipts(bundle, built):
    """The landing count is published-source evidence, not a workspace inventory."""
    text = (built / "index.html").read_text(encoding="utf-8")
    sources = bundle.stats["corpus"]["repos"]

    assert f"{sources} verified source repositories" in text
    assert 'href="receipts.html"' in text
    assert re.search(r"sources named by\s+published pages", text)
    assert "repositories, read once" not in text


def test_landing_preserves_an_explicit_zero_source_total(bundle, cfg, monkeypatch):
    """A measured zero is evidence; it is not an invitation to infer a replacement count."""
    monkeypatch.setitem(bundle.stats["corpus"], "repos", 0)

    html = views.landing(bundle, cfg)

    assert "0 verified source repositories" in html


def test_landing_does_not_invent_private_remainder_when_projects_cover_sources(bundle, built):
    """A complete public project set must say it is complete, not imply hidden sources."""
    text = (built / "index.html").read_text(encoding="utf-8")

    assert len(bundle.of_type("project")) == len(bundle.by_repo())
    assert "Every verified source repository has a public project page here." in text
    assert "the rest stayed private" not in text


# -- what the page tells a machine, and what it lets one do ---------------------------

def test_every_json_ld_block_parses(built):
    """Structured data that does not parse is worse than none: it is a silent claim.

    Also asserts no raw `<` survives into the block. A page title containing `</script>` would
    otherwise close the element early and spill the rest of the JSON into the document as
    markup — the one injection this feature could introduce, and it is escaped at the source
    in `shell.ld`.
    """
    seen = {}
    for page in sorted(built.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
        for raw in blocks:
            json.loads(raw)
            assert "<" not in raw, f"{page.name}: unescaped < in JSON-LD"
        seen[page.relative_to(built).as_posix()] = len(blocks)
    # Counted per document rather than totalled, so this cannot pass on a total that happens
    # to add up while one article carries two blocks and another carries none.
    for name in ("index.html", "p/pytest.html", "p/stickfps.html"):
        assert seen[name] == 1, f"{name} has {seen[name]} structured-data blocks"
    assert all(n == 1 for k, n in seen.items() if k.startswith("p/")), \
        "every article page describes itself exactly once"


def test_social_preview_tags_on_every_page(built):
    """A link pasted into a chat client has to preview as something."""
    for page in sorted(built.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for tag in ('property="og:title"', 'property="og:description"',
                    'property="og:type"', 'name="twitter:card"'):
            assert tag in text, f"{page.name}: missing {tag}"


def test_canonical_and_sitemap_only_with_an_origin(bundle, cfg, tmp_path):
    """Absolute URLs appear when, and only when, one is configured — never guessed.

    Both directions are asserted. Testing only the empty case would let a typo that hardcodes
    an origin pass, and testing only the configured case would miss the default this
    repository actually ships with.
    """
    import build as build_mod

    without = views.landing(bundle, cfg)
    assert "rel=\"canonical\"" not in without
    assert "og:url" not in without
    assert "sitemap.xml" not in build_mod.crawl_files(bundle, cfg, {"index.html": ""})

    origin = {**cfg, "site": {**cfg["site"], "url": "https://example.test/gb"}}
    with_url = views.landing(bundle, origin)
    assert '<link rel="canonical" href="https://example.test/gb/index.html">' in with_url
    assert 'content="https://example.test/gb/index.html"' in with_url
    files = build_mod.crawl_files(bundle, origin, {"index.html": "", "browse.html": ""})
    assert "Sitemap: https://example.test/gb/sitemap.xml" in files["robots.txt"]
    sm = files["sitemap.xml"]
    assert sm.count("<loc>") == len(bundle.pages) + 2
    assert "https://example.test/gb/p/pytest.html" in sm
    # The 404 must never be indexable: a "no page at that address" result in a search engine
    # is a dead end presented as an answer.
    assert "404" not in sm


def test_a_lost_reader_can_still_search(built):
    """404 is a recovery surface. Both routes out of it must be on the page."""
    text = (built / "404.html").read_text(encoding="utf-8")
    assert 'action="/index.html"' in text
    assert 'name="q"' in text
    assert 'href="/browse.html"' in text


def test_search_reaches_every_page_not_just_the_landing_one(built):
    """The header box, and the depth prefix that makes its links resolve.

    `data-base` is the whole mechanism: the runtime writes `BASE + 'p/stem.html'`, so an
    article page must carry `../` or every suggestion from the header leads to `p/p/…`.
    """
    article = (built / "p" / "pytest.html").read_text(encoding="utf-8")
    assert '<body data-base="../">' in article
    assert 'class="hs"' in article and 'action="../index.html"' in article
    landing = (built / "index.html").read_text(encoding="utf-8")
    assert '<body data-base="">' in landing
    # Exactly one combobox per document, everywhere. Two would leave the runtime bound to the
    # first and the visible one inert.
    for page in sorted(built.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        assert text.count("data-ask ") + text.count("data-ask\n") <= 1, page.name


def test_the_client_escapes_for_attributes_not_only_text(built):
    """`esc` output lands inside `href="…"` and `data-seed="…"`, so it must escape quotes.

    Asserted against the shipped file rather than a copy: this is the version the browser
    runs. The old implementation round-tripped through `textContent`/`innerHTML`, which is the
    serialiser's text-node rule and leaves `"` untouched.
    """
    app = (built / "assets" / "app.js").read_text(encoding="utf-8")
    body = app[app.index("function esc("):]
    body = body[:body.index("\n}")]
    for pair in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert pair in body, f"esc does not produce {pair}"
    assert "innerHTML" not in body, "escaping must not depend on the HTML serialiser"


def test_unknown_link_schemes_never_become_anchors():
    """An allow-list, checked against the shapes that matter.

    `javascript:` and `data:` are the two that execute. The relative forms are here because a
    scheme gate that also blocked ordinary internal links would be caught by no other test —
    it would simply make the corpus quieter.
    """
    def out(md):
        html, _h, _u = render(md, set(), lambda s: f"{s}.html")
        return html

    for hostile in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<b>",
                    "vbscript:msgbox", "file:///etc/passwd"):
        html = out(f"[click]({hostile})")
        assert "<a" not in html, f"{hostile} became an anchor"
        assert "click" in html, f"{hostile} lost its text as well as its link"
    for fine in ("https://example.test/x", "http://example.test/x", "mailto:a@b.test",
                 "browse.html", "../index.html", "#section", "/assets/app.css"):
        assert "<a href=" in out(f"[ok]({fine})"), f"{fine} should have stayed a link"
    # External links hand over no referrer; internal ones need no rel at all.
    assert 'rel="noopener noreferrer"' in out("[x](https://example.test/)")
    assert "rel=" not in out("[x](browse.html)")


def test_the_private_link_note_appears_only_where_it_applies(bundle, cfg, built):
    """A note explaining a convention, on pages that do not use it, teaches readers to skip it."""
    with_note = with_style = 0
    for page in sorted((built / "p").glob("*.html")):
        text = page.read_text(encoding="utf-8")
        has_note = "unpub-note" in text
        has_style = '<span class="unpub"' in text.replace(
            '<span class="unpub">this style</span>', "")
        assert has_note == has_style, f"{page.name}: note and style disagree"
        with_note += has_note
        with_style += has_style
    assert 0 < with_note < len(bundle.pages), "the note is either everywhere or nowhere"


def test_headings_are_citable(built):
    """Every id the renderer emits gets a visible way to copy it."""
    text = (built / "p" / "stickfps.html").read_text(encoding="utf-8")
    ids = re.findall(r'<h2 id="([^"]+)"', text)
    assert ids, "no h2 ids to anchor"
    for sid in ids:
        assert f'href="#{sid}"' in text, f"heading {sid} has no anchor link"


def test_placeholder_ink_is_not_dimmed(built):
    """Measured 3.45:1 light and 4.43:1 dark, on the site's primary control.

    `--muted` is the dimmest ink in the palette that clears 4.5:1 (5.78:1 on the light
    surface). The rule multiplied it by `opacity: 0.75`, which put the placeholder under the
    threshold in both themes. Nothing caught it for the length of the project because the
    accessibility sweep walks elements and a placeholder is a pseudo-element.

    Guarded here rather than in the browser harness because this is the file that ships, and
    because a colour value cannot be asserted from Python — the absence of the dimming can.
    """
    css = (built / "assets" / "app.css").read_text(encoding="utf-8")
    rule = re.search(r"::placeholder\s*\{([^}]*)\}", css)
    assert rule, "no placeholder rule at all"
    assert "opacity" not in rule.group(1), \
        f"placeholder ink is dimmed again: {rule.group(1).strip()}"


def test_nothing_tracked_names_the_private_repository():
    """The public repository may not carry a path into the private one.

    Found by inspection, not by a check: a `.publish-plan.json` left over from a bulk
    publish decision sat untracked in the repository root holding 235 absolute paths into the
    private wiki, including the list of pages cleared against sensitive sources. It had not
    been committed. Nothing would have stopped it — `git add -A` is one keystroke,
    and the file it would have published is a map of the private wiki from the repository
    whose whole claim is that it holds no private page.

    Asked of git rather than of the filesystem: the question is what would be disclosed, and
    an ignored working file discloses nothing. `content/` is exempt — it is the export, and
    its `sources:` fields name repositories on purpose. Nothing else is exempt, including
    this file: the pattern below is assembled rather than written out, so the check does not
    have to make an exception for the docstring that explains it.
    """
    listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if listed.returncode != 0:
        pytest.skip("not a git checkout")
    bad = []
    for name in listed.stdout.split("\n"):
        if not name.strip() or name.startswith("content/"):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # `[/\\]+`, not `[/\\]`. A Windows path inside JSON has its separators escaped, so the
        # artefact this check was written against spells the boundary `second-brain\\wiki` —
        # two characters. The single-separator pattern matched all four of my invented cases
        # and none of the 235 real ones, which is the exact shape of a guard that reports
        # green over the thing it exists to find.
        for hit in re.finditer("second" "-brain" r"[/\\]+wiki[/\\]+\S+", text):
            bad.append(f"{name}: {hit.group(0)}")
    assert not bad, bad
