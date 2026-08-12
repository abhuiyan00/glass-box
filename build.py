#!/usr/bin/env python3
"""Build the site.

    python build.py                 build into docs/
    python build.py --check         build to a temporary directory and report; write nothing
    python build.py --open          build, then open the result in a browser
    python build.py --content DIR   read the bundle from somewhere other than content/
    python build.py --out DIR       build into an explicit output directory

No arguments, no dependencies, no configuration beyond `glassbox.toml`. If this file needs a
task runner to be usable, the task runner is the bug.

Deterministic by construction: sorted iteration everywhere, no build id, and the only date in
the output is the export date carried in the bundle. Identical input gives byte-identical
output, which is what makes "nothing changed, so nothing was published" a fact rather than a
hope — and it is why a rebuild with no new export produces an empty git diff.

Every gate fails closed. A bundle that does not match its manifest, a page that raises in the
renderer, or a landing document over budget stops the build; none of them degrades quietly
into output somebody then deploys.
"""

import gzip
import shutil
import sys
import tempfile
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from glassbox import pages as page_view          # noqa: E402
from glassbox import mapview, receipts, search, views  # noqa: E402
from glassbox.content import Bundle, BundleError  # noqa: E402
from glassbox.markdown import Unsupported        # noqa: E402
from glassbox.shell import load_config, site_url  # noqa: E402

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def crawl_files(bundle, cfg, standing):
    """robots.txt always; sitemap.xml only with an origin configured.

    A sitemap holds absolute URLs — the format has no relative form — so without
    `[site] url` there is nothing truthful to write and the file is skipped rather than
    emitted full of guesses. `robots.txt` has no such constraint and is written either way,
    because its job with no rules in it is still to answer the crawler's first request with a
    200 instead of the host's 404 page.

    `lastmod` is the bundle's export date, for every page. That is the truth available: the
    private wiki records when a page was updated, but a page whose text did not change is
    still republished by an export, and claiming a per-page date this repository cannot see
    would be inventing precision.
    """
    origin = site_url(cfg)
    out = {"robots.txt": "User-agent: *\nAllow: /\n"}
    if not origin:
        return out
    out["robots.txt"] += f"Sitemap: {origin}sitemap.xml\n"
    day = bundle.stats.get("generated") or ""
    stamp = f"<lastmod>{day}</lastmod>" if day else ""
    locs = list(standing) + [f"p/{p['stem']}.html"
                             for p in sorted(bundle.pages, key=lambda p: p["stem"])]
    urls = "\n".join(f"  <url><loc>{origin}{loc}</loc>{stamp}</url>" for loc in locs)
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          f"{urls}\n</urlset>\n")
    return out


def write(path, text):
    """Always LF, on every platform.

    `Path.write_text` opens in text mode, which on Windows turns every newline into CRLF.
    That makes the output byte-identical only against itself — build on Windows, verify on
    Linux CI, and every line of every file differs. The determinism claim is worth exactly
    as much as this argument.
    """
    path.write_text(text, encoding="utf-8", newline="\n")


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def output_path(argv, cfg, content, check):
    """Resolve an output without allowing a recursive delete to consume source.

    `--out` exists primarily for tests and preview automation. The normal configured output
    remains allowed inside the repository, but an override may not overlap this checkout or
    the input bundle. This turns a typo such as `--out ..` into a closed failure rather than
    a repository deletion.
    """
    explicit = arg(argv, "--out")
    if check and explicit is not None:
        raise ValueError("--check and --out are mutually exclusive")
    if check:
        return Path(tempfile.mkdtemp(prefix="glass-box-"))

    configured = Path(cfg["site"]["out"])
    default = configured if configured.is_absolute() else ROOT / configured
    if explicit is None:
        return default.resolve()

    candidate = Path(explicit)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    protected = (ROOT.resolve(), content.resolve())
    if any(candidate == path or candidate.is_relative_to(path) or path.is_relative_to(candidate)
           for path in protected):
        raise ValueError("--out must not overlap the repository or content bundle")
    return candidate


def utf8_stdout():
    """Windows picks the locale encoding for a redirected stream, which is cp1252 here.

    The build report separates fields with U+00B7, which cp1252 happens to have — but the
    page titles it prints on failure do not stay inside that set, so the tool worked in a
    console and died with UnicodeEncodeError the moment CI captured its output. That is the
    case that matters: a build log is always a pipe.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def render_all(bundle, cfg, out):
    """Write every document. Returns (files written, unresolved link count)."""
    written, unresolved = [], 0

    (out / "assets").mkdir(parents=True, exist_ok=True)
    for asset in sorted(ASSETS.iterdir()):
        if asset.is_file():
            shutil.copy2(asset, out / "assets" / asset.name)
            written.append(out / "assets" / asset.name)

    idx = search.build(bundle)
    write(out / "assets" / "search-index.js", search.as_script(idx))
    written.append(out / "assets" / "search-index.js")

    standing = {
        "index.html": views.landing(bundle, cfg),
        "browse.html": views.browse(bundle, cfg),
        "map.html": mapview.page(bundle, cfg),
        "receipts.html": receipts.receipts(bundle, cfg),
        "gaps.html": receipts.gaps(bundle, cfg),
        "how.html": receipts.how(bundle, cfg),
    }
    for name, doc in standing.items():
        write(out / name, doc)
        written.append(out / name)

    # Served by the host for any unmatched path, so it is not in `standing` and never in the
    # sitemap: a 404 that advertises itself for indexing is a 404 in search results.
    write(out / "404.html", views.notfound(bundle, cfg))
    written.append(out / "404.html")

    for name, text in crawl_files(bundle, cfg, standing).items():
        write(out / name, text)
        written.append(out / name)

    (out / "p").mkdir(parents=True, exist_ok=True)
    for page in sorted(bundle.pages, key=lambda p: p["stem"]):
        doc, _heads, missing = page_view.article(bundle, page, cfg)
        target = out / "p" / f"{page['stem']}.html"
        write(target, doc)
        written.append(target)
        unresolved += len(missing)

    # GitHub Pages runs Jekyll unless told not to, and Jekyll drops files and directories
    # beginning with an underscore. Nothing here starts with one today; the file costs
    # nothing and removes a class of failure that only ever shows up in production.
    write(out / ".nojekyll", "")
    written.append(out / ".nojekyll")
    return written, unresolved


def main(argv):
    utf8_stdout()
    cfg = load_config(ROOT)
    content = Path(arg(argv, "--content", cfg["site"]["content"]))
    if not content.is_absolute():
        content = ROOT / content

    try:
        bundle = Bundle(content)
    except BundleError as e:
        print(f"\nFAIL {e}", file=sys.stderr)
        return 1

    check = "--check" in argv
    try:
        out = output_path(argv, cfg, content, check)
    except (IndexError, ValueError) as e:
        print(f"\nFAIL {e}", file=sys.stderr)
        return 1
    if not check and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    try:
        written, unresolved = render_all(bundle, cfg, out)
    except Unsupported as e:
        print(f"\nFAIL renderer met a construct it does not support: {e}", file=sys.stderr)
        return 1

    landing_kb = round(len(gzip.compress((out / "index.html").read_bytes(), 9)) / 1024, 1)
    index_kb = round(len(gzip.compress(
        (out / "assets" / "search-index.js").read_bytes(), 9)) / 1024, 1)
    budget = cfg["budget"]
    over = []
    if landing_kb > budget["landing_kb"]:
        over.append(f"landing {landing_kb} KB > {budget['landing_kb']} KB")
    if index_kb > budget["index_kb"]:
        over.append(f"search index {index_kb} KB > {budget['index_kb']} KB")

    counts = {}
    for page in bundle.pages:
        counts[page["type"]] = counts.get(page["type"], 0) + 1
    print(f"\n{len(bundle.pages)} pages · {len(written)} files · "
          f"{' · '.join(f'{k} {v}' for k, v in sorted(counts.items()))}")
    print(f"  bundle exported {bundle.stats.get('generated')} · "
          f"manifest verified ({len(bundle.manifest.get('files') or {})} files)")
    print(f"  landing {landing_kb} KB gzipped (budget {budget['landing_kb']}) · "
          f"search index {index_kb} KB gzipped (budget {budget['index_kb']})")
    # Says which count this is. It reports markers written — a page naming the same private
    # page in two paragraphs contributes two — where the gaps page reports (page, target)
    # pairs. Both are right; printing them a word apart made one of them look wrong.
    print(f"  markers for a private page, rendered as text rather than a link: {unresolved}")
    placeholders = bundle.manifest.get("placeholders") or []
    print(f"  figures the source could not measure, shown as gaps: "
          f"{', '.join(placeholders) or 'none'}")

    if check:
        shutil.rmtree(out, ignore_errors=True)
        print("  --check: wrote nothing")
    else:
        try:
            shown = out.relative_to(ROOT).as_posix()
        except ValueError:
            shown = str(out)
        print(f"  -> {shown}/index.html")
        if "--open" in argv:
            webbrowser.open((out / "index.html").as_uri())

    if over:
        print("\nFAIL over budget: " + "; ".join(over), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
