"""Markdown -> HTML for exactly the constructs the source wiki uses. Nothing more.

Not a general markdown implementation, deliberately. The input is one authored corpus
following a schema its own linter enforces, so the supported set is closed and verifiable:
every published page round-trips in CI, and a construct outside the list raises rather than
degrading. A renderer that silently drops what it does not understand is how a page loses the
sentence that mattered.

Supported: ATX headings (with slug anchors), paragraphs, fenced code, inline code, tables,
blockquotes, bullet and ordered lists, thematic breaks, bold, italic, links, wikilinks.

Two things are load-bearing rather than incidental:

  * **Escaping happens first, once.** Every inline rule runs on already-escaped text, so a
    page containing `<script>` renders as text and cannot introduce markup. Code spans are
    lifted out before the emphasis rules run and put back after, because a backtick span
    holding `**` is a literal and several pages have one. Escaping is not the whole defence,
    though — it protects the *shape* of an attribute and says nothing about what a URL points
    at, so link targets are separately held to an allow-list of schemes. See `link()`.
  * **A wikilink to a page that was not published becomes plain text, never an anchor.**
    The private wiki is one connected component; most pages link somewhere that did not
    ship. Those are not dead links here because they are not links at all.
"""

import html
import re

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^```(\w*)\s*$")
TABLE_SEP = re.compile(r"^\|[\s:|-]+\|$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
ORDERED = re.compile(r"^(\d+)\.\s+(.*)$")
QUOTE = re.compile(r"^>\s?(.*)$")
RULE = re.compile(r"^(-{3,}|\*{3,})$")
CODESPAN = re.compile(r"`([^`\n]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
WIKILINK = re.compile(r"\[\[([^\]|#]+?)(?:\|([^\]]+))?\]\]")
# Something the source wiki links that was not published. The exporter strips the target
# before writing, so what arrives is display text with no page name behind it — this project
# could not linkify it even if it tried, which is the point.
UNPUB = re.compile(r"\{\{([^}\n]+)\}\}")
SLUG_STRIP = re.compile(r"[^a-z0-9\s-]")
# An admitted gap at the head of a paragraph. The wiki writes it as `TODO:` inside a code
# span, so the backticks are part of the marker and are stripped with it.
TODO = re.compile(r"^\s*`?TODO:`?\s*")
# An evidence line: a quote followed by an em-dash attribution. The source wiki requires one
# on every decision and pattern page, so it is the most common block on the site and gets a
# shape of its own rather than a generic blockquote.
CITE = re.compile(r"^—\s*(.+)$")


class Unsupported(Exception):
    """A construct outside the closed set. Names the page; never swallowed."""


def slug(text):
    """Stable anchor id for a heading, so a citation can deep-link to one section."""
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = CODESPAN.sub(r"\1", text).replace("**", "")
    text = SLUG_STRIP.sub("", text.lower()).strip()
    return re.sub(r"[\s-]+", "-", text) or "section"


# What may become an `href`. Everything else renders as text.
#
# The module docstring above claims a page cannot introduce markup, and until this list existed
# that claim was one character wider than the code: escaping runs before the inline rules, so
# `"` inside a URL arrives as `&quot;` and cannot close the attribute — but nothing stopped
# `[click](javascript:…)` from becoming a live anchor with a script for a target. Escaping
# defends the attribute; it says nothing about the scheme.
#
# No page in the corpus does this, which is exactly why it belongs in an allow-list rather than
# a block-list: this repository does not own the wiki, the wiki is written by an agent pipeline,
# and "no page does this today" is a fact about today. Unknown scheme in, plain text out.
# A bare `word:` at the head of a URL is a scheme. A URL without one is a relative path, and
# safe by construction — it can only ever address this site.
HAS_SCHEME = re.compile(r"\A[a-z][a-z0-9+.-]*:", re.I)
SAFE_SCHEME = re.compile(r"\A(?:https?|mailto):", re.I)


def link(label, url):
    """One markdown link. An unroutable or unknown scheme degrades to text, never an anchor."""
    if HAS_SCHEME.match(url) and not SAFE_SCHEME.match(url):
        # Same treatment an unpublished wikilink gets, and for the same reason: showing the
        # words without the link loses nothing a reader needed and cannot mislead them.
        return label
    external = url.lower().startswith(("http://", "https://"))
    # `noopener` alone was inert — it only governs a window this site never opens, because no
    # link here carries `target`. `noreferrer` is the half that does something: it stops the
    # full URL of the page the reader was on from being handed to the destination.
    rel = ' rel="noopener noreferrer"' if external else ""
    return f'<a href="{url}"{rel}>{label}</a>'


def inline(text, published, href, unresolved):
    """Inline constructs. `text` is raw; escaping happens here and only here."""
    spans = []

    def stash(m):
        spans.append(html.escape(m.group(1)))
        return f"\x00{len(spans) - 1}\x00"

    text = CODESPAN.sub(stash, text)
    text = html.escape(text)

    def unpub(m):
        unresolved.append(m.group(1).strip())
        return (f'<span class="unpub" title="named in the source wiki; not published">'
                f"{m.group(1).strip()}</span>")

    text = UNPUB.sub(unpub, text)

    def wiki(m):
        stem, label = m.group(1).strip(), (m.group(2) or "").strip()
        if stem not in published:
            # Defence in depth. The exporter already removed every unpublished target, so
            # reaching this branch means the bundle disagrees with its own index — render the
            # text, never an anchor, and let the build report the count.
            unresolved.append(stem)
            return f'<span class="unpub">{html.escape(label or stem)}</span>'
        return f'<a class="wl" href="{href(stem)}">{html.escape(label or stem)}</a>'

    text = WIKILINK.sub(wiki, text)
    # Escaping already ran, so a markdown link's brackets survive as literals here.
    text = LINK.sub(lambda m: link(m.group(1), m.group(2)), text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)
    for i, code in enumerate(spans):
        text = text.replace(f"\x00{i}\x00", f"<code>{code}</code>")
    return text


def _table(rows, ctx):
    """A pipe table. Row 0 is the header; the separator row is already dropped."""
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    out = ['<div class="tw"><table>', "<thead><tr>"]
    for c in cells(rows[0]):
        out.append(f"<th>{inline(c, *ctx)}</th>")
    out.append("</tr></thead><tbody>")
    for line in rows[1:]:
        out.append("<tr>" + "".join(f"<td>{inline(c, *ctx)}</td>"
                                    for c in cells(line)) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def _quote(body, ctx):
    """A blockquote, with its attribution line pulled out as a citation if it has one."""
    lines = [x for x in body if x.strip()]
    cite = None
    if lines and CITE.match(lines[-1].strip()):
        cite = CITE.match(lines.pop().strip()).group(1)
    quoted = inline(" ".join(lines), *ctx)
    tail = f'<cite>{inline(cite, *ctx)}</cite>' if cite else ""
    return f"<blockquote><p>{quoted}</p>{tail}</blockquote>"


def render(text, published, href, where="?"):
    """(html, headings, unresolved stems). `href(stem)` returns the link for a page."""
    lines = text.replace("\r\n", "\n").split("\n")
    out, headings, unresolved = [], [], []
    ctx = (published, href, unresolved)
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        m = FENCE.match(line)
        if m:
            lang, body, i = m.group(1), [], i + 1
            while i < n and not FENCE.match(lines[i]):
                body.append(lines[i])
                i += 1
            if i >= n:
                raise Unsupported(f"{where}: unclosed code fence")
            i += 1
            cls = f' class="lang-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>")
            continue

        m = HEADING.match(line)
        if m:
            level, raw = len(m.group(1)), m.group(2).strip()
            sid = slug(raw)
            headings.append({"level": level, "text": raw, "id": sid})
            out.append(f'<h{level} id="{sid}">{inline(raw, *ctx)}</h{level}>')
            i += 1
            continue

        if RULE.match(line.strip()):
            out.append("<hr>")
            i += 1
            continue

        if line.startswith("|"):
            block = []
            while i < n and lines[i].startswith("|"):
                if not TABLE_SEP.match(lines[i].strip()):
                    block.append(lines[i])
                i += 1
            if block:
                out.append(_table(block, ctx))
            continue

        if QUOTE.match(line):
            body = []
            while i < n and QUOTE.match(lines[i]):
                body.append(QUOTE.match(lines[i]).group(1))
                i += 1
            out.append(_quote(body, ctx))
            continue

        if BULLET.match(line) or ORDERED.match(line):
            ordered = bool(ORDERED.match(line))
            items = []
            while i < n:
                m2 = ORDERED.match(lines[i]) if ordered else BULLET.match(lines[i])
                if m2:
                    items.append(m2.group(2) if ordered else m2.group(1))
                    i += 1
                # A wrapped continuation line is indented; join it to the open item.
                elif items and lines[i].startswith(("  ", "\t")) and lines[i].strip():
                    items[-1] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            body = "".join(f"<li>{inline(x, *ctx)}</li>" for x in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        para = []
        while i < n and lines[i].strip() and not (
            HEADING.match(lines[i]) or FENCE.match(lines[i])
            or lines[i].startswith(("|", ">")) or BULLET.match(lines[i])
            or ORDERED.match(lines[i]) or RULE.match(lines[i].strip())
        ):
            para.append(lines[i].strip())
            i += 1
        if para:
            joined = " ".join(para)
            # An admitted gap gets a designed treatment rather than shipping a bare `TODO:`
            # into public prose. The author's own habit made visible: the boundary of a
            # claim is written next to the claim, and hiding it here would be the one edit
            # this site is not allowed to make.
            m = TODO.match(joined)
            if m:
                out.append(f'<aside class="gap"><span class="gap-k">Known gap</span>'
                           f"<span>{inline(joined[m.end():], *ctx)}</span></aside>")
            else:
                out.append(f"<p>{inline(joined, *ctx)}</p>")

    return "\n".join(out), headings, unresolved
