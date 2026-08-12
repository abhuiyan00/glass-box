"""A checker that cannot fail is not evidence.

`tools/audit_site.py` reports PASS on the real site. That is only worth something if the
tool would have said FAIL had the site been broken, so each test here builds a small site
carrying exactly one defect and asserts the tool finds it.

The last two tests are the ones that matter most. Both defects were present in the first
version of the checker, and both made it report the site's correct behaviour as a
violation: 239 external citations counted as outbound requests, and the word "WebSocket"
inside JSON-LD metadata counted as a script calling the network. A checker that cries
wolf gets switched off, which costs more than the check was worth.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import audit_site  # noqa: E402

SHELL = ('<!doctype html><html lang="en"><head><title>t</title></head>'
         "<body>{body}</body></html>")


def build(tmp_path, pages):
    for name, body in pages.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(SHELL.format(body=body) if "<html" not in body else body,
                     encoding="utf-8")
    return audit_site.audit(str(tmp_path))


def test_clean_site_passes(tmp_path):
    _, f, _ = build(tmp_path, {
        "index.html": '<a href="other.html">go</a>',
        "other.html": "<p>here</p>",
    })
    assert not any(f[k] for k in f)


def test_dead_internal_link_is_found(tmp_path):
    _, f, _ = build(tmp_path, {"index.html": '<a href="gone.html">go</a>'})
    assert len(f["broken"]) == 1


def test_link_into_a_directory_resolves_through_its_index(tmp_path):
    """`href="p/"` is not dead just because `p` is a folder."""
    _, f, _ = build(tmp_path, {
        "index.html": '<a href="p/">section</a>',
        "p/index.html": "<p>section</p>",
    })
    assert not f["broken"]


def test_fragment_and_mailto_are_not_treated_as_files(tmp_path):
    _, f, _ = build(tmp_path, {
        "index.html": '<a href="#top">top</a> <a href="mailto:a@b.c">mail</a>',
    })
    assert not f["broken"]


# Every fixture below is synthetic on purpose. A test that proves the auditor finds
# leaked machine names must not itself be the leak — and this repository's whole claim
# is that it publishes no private data, tests included.
@pytest.mark.parametrize("body,label", [
    ('<p>built on DESKTOP-EXAMPLE1</p>', "developer machine name"),
    (r'<p>C:\Users\someone\notes.txt</p>', "local user path"),
    ('<p>mongodb+srv://user:pw@cluster.example/db</p>', "database connection string"),
    ('<p>sk_test_abcdefgh1234</p>', "payment key"),
])
def test_privacy_leaks_are_found(tmp_path, body, label):
    _, f, _ = build(tmp_path, {"index.html": body})
    assert [hit for _, found, hit in f["privacy"] if found == label]


def test_remote_stylesheet_is_a_violation(tmp_path):
    """The site claims it makes no outbound requests. A CDN stylesheet breaks that."""
    page = ('<!doctype html><html lang="en"><head><title>t</title>'
            '<link rel="stylesheet" href="https://cdn.example/x.css">'
            "</head><body></body></html>")
    _, f, _ = build(tmp_path, {"index.html": page})
    assert len(f["remote"]) == 1


def test_external_citation_is_not_a_request(tmp_path):
    """239 of these exist on the real site. Counting them as outbound requests turned
    the site's own honesty into a failure."""
    _, f, external = build(tmp_path, {
        "index.html": '<a href="https://www.w3.org/TR/WCAG22/">WCAG 2.2</a>',
    })
    assert not f["remote"]
    assert sum(external.values()) == 1


def test_json_ld_naming_websocket_is_not_a_network_call(tmp_path):
    """Two real pages carry `"articleSection":["…WebSocket…"]` in their structured
    data. It is a string in a data block, not a call."""
    page = ('<!doctype html><html lang="en"><head><title>t</title>'
            '<script type="application/ld+json">'
            '{"@type":"TechArticle","name":"new WebSocket and fetch("}'
            "</script></head><body></body></html>")
    _, f, _ = build(tmp_path, {"index.html": page})
    assert not f["network"]


def test_real_script_calling_the_network_is_found(tmp_path):
    page = ('<!doctype html><html lang="en"><head><title>t</title>'
            '<script>fetch("/api/x")</script></head><body></body></html>')
    _, f, _ = build(tmp_path, {"index.html": page})
    assert f["network"] == ["index.html"]


def test_missing_lang_title_and_alt_are_found(tmp_path):
    page = "<!doctype html><html><head></head><body><img src=\"a.png\"></body></html>"
    _, f, _ = build(tmp_path, {"index.html": page, "a.png": ""})
    assert f["no_lang"] and f["no_title"] and f["no_alt"]


def test_empty_alt_is_allowed(tmp_path):
    """alt="" is the correct markup for a decorative image, not a missing alt."""
    _, f, _ = build(tmp_path, {"index.html": '<img src="a.png" alt="">', "a.png": ""})
    assert not f["no_alt"]
