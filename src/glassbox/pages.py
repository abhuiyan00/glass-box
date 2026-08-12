"""One article per published page.

The page opens with the answer. A visitor who arrived from the search box came for one
sentence, and making them find it inside a thousand words of prose is how a knowledge base
becomes a document dump. The summary at the top is the same sentence the search result
showed, so the page confirms what brought them here instead of restating it differently.

It closes with where the page came from. That ordering is the author's own habit — the
boundary of a claim written next to the claim — and it is the one thing this site cannot
be allowed to tidy away.
"""

from .markdown import render
from .shell import document, esc, site_url

META_LABEL = {"project": "Project", "decision": "Decision", "pattern": "Pattern",
              "concept": "Concept", "tech": "Tech"}
CONFIDENCE_NOTE = {
    "high": "Confirmed by the author, or agreed by two or more independent sources.",
    "medium": "Supported by the repository, but not confirmed directly.",
    "low": "One weak source, or a question that was asked and not answered.",
}
# Shown in full, on the page, for anything below `high`.
#
# The gate used to publish only `high`, which had the effect of hiding the level rather than
# stating it: every page a reader could open said the same word, so the word carried no
# information and nobody read it. Publishing `medium` is only defensible if the difference is
# visible, and a badge alone is not visible enough — a one-word label in a metadata row is
# something a reader skims past and then, quite reasonably, assumes they were told nothing.
CONFIDENCE_BANNER = {
    "medium": ("Read this one with the caveat it carries",
               "Everything here is drawn from files in the repository, and the repository is "
               "the only witness. Nothing on this page was confirmed by the author in an "
               "interview, and no second independent source agrees with it. Where the code "
               "and the documents disagreed, that disagreement is recorded rather than "
               "resolved. Treat the mechanics as reliable and the intent behind them as "
               "inferred."),
}


def sources_block(page):
    """Where the page was written from. Repository first, in bold, then the path inside it."""
    items = []
    for src in page.get("sources") or []:
        repo, _, rest = src.partition("/")
        tail = f'<span class="src-p">/{esc(rest)}</span>' if rest else ""
        items.append(f'<li><code><span class="src-r">{esc(repo)}</span>{tail}</code></li>')
    if not items:
        return ""
    return f"""<section class="prov">
  <h2>Written from</h2>
  <p class="band-b">The files this page was compiled from. Quotations in the text above are
    verbatim from these.</p>
  <ul class="srcs">{"".join(items)}</ul>
</section>"""


def related_block(bundle, page):
    links = [bundle.by_stem[s] for s in page.get("links") or [] if s in bundle.by_stem]
    if not links:
        return ""
    rows = "".join(
        f'<a class="rel" href="{esc(p["stem"])}.html">'
        f'<span class="kind k-{esc(p["type"])}">{esc(p["type"])}</span>'
        f'<span class="rel-t">{esc(p.get("title") or p["stem"])}</span>'
        f'<span class="rel-g">{esc(p.get("gist") or "")}</span></a>'
        for p in sorted(links, key=lambda p: (p["type"], p["stem"])))
    return f"""<section class="prov">
  <h2>Related pages</h2>
  <p class="band-b">Linked by the author, not inferred. These are the edges the search
    follows when it looks one step beyond a direct match.</p>
  <div class="rels">{rows}</div>
</section>"""


def outline_block(headings):
    """Section links, for pages long enough that the reader cannot see the shape of one.

    Only h2s, and only from four of them up. A two-item contents list on a screen-and-a-half
    page is furniture: it costs a scroll to read and tells you what the next two headings
    already say. The threshold is what makes it worth having on the pages that have it.
    """
    tops = [h for h in headings if h["level"] == 2]
    if len(tops) < 4:
        return ""
    items = "".join(f'<li><a href="#{esc(h["id"])}">{esc(h["text"])}</a></li>' for h in tops)
    return (f'<nav class="toc" aria-label="On this page">'
            f'<span class="toc-k">On this page</span><ol>{items}</ol></nav>')


def anchors(html_body, headings):
    """A click target on every heading, so a section can be cited rather than described.

    The ids were already emitted — `markdown.slug` has produced stable ones from the start —
    and nothing on the page revealed they existed. A reader who wants to send a colleague one
    section of a long page had to read the source to find the fragment.

    Done as a string replacement over the rendered heading tags rather than inside the
    renderer, because the renderer is a general markdown module and this is presentation that
    belongs to the article view. Exactly one substitution per heading, keyed on the opening
    tag the renderer wrote, so it cannot match prose.
    """
    for h in headings:
        if h["level"] == 1:
            continue
        tag = f'<h{h["level"]} id="{h["id"]}">'
        if tag not in html_body:
            continue
        link = (f'<a class="hlink" href="#{esc(h["id"])}" '
                f'aria-label="Link to this section">#</a>')
        html_body = html_body.replace(
            tag, f'<h{h["level"]} id="{h["id"]}" class="h-anch">{link}', 1)
    return html_body


def article_ld(page, cfg, headings):
    """schema.org for one page. Every field is read; none is defaulted.

    `TechArticle` rather than `Article`: these are documentation pages about how something was
    built, and the more specific type is the true one. `citation` carries the source files the
    page was written from, which is the same claim the page makes in prose at the bottom —
    stating it twice in two registers is the point of structured data.
    """
    origin = site_url(cfg)
    data = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": page.get("title") or page["stem"],
        "inLanguage": "en",
        "isPartOf": {"@type": "WebSite", "name": cfg["site"]["title"]},
        "author": {"@type": "Person", "name": cfg["author"]["name"]},
    }
    if page.get("gist"):
        data["description"] = page["gist"]
    if page.get("updated"):
        data["dateModified"] = page["updated"]
    if page.get("tags"):
        data["keywords"] = list(page["tags"])
    if page.get("sources"):
        data["citation"] = list(page["sources"])
    if headings:
        data["articleSection"] = [h["text"] for h in headings if h["level"] == 2]
    if origin:
        data["url"] = f"{origin}p/{page['stem']}.html"
    return data


def dates_line(page):
    bits = []
    if page.get("updated"):
        bits.append(f'updated {esc(page["updated"])}')
    if page.get("valid_from"):
        span = f'in force since {esc(page["valid_from"])}'
        if page.get("valid_to"):
            span = (f'in force {esc(page["valid_from"])} to {esc(page["valid_to"])}'
                    f' — superseded')
        bits.append(span)
    return " · ".join(bits)


def article(bundle, page, cfg):
    stem = page["stem"]
    html_body, headings, unresolved = render(
        bundle.bodies[stem], bundle.published, lambda s: f"{s}.html", where=stem)

    confidence = page.get("confidence") or ""
    note = CONFIDENCE_NOTE.get(confidence, "")
    repos = " · ".join(page.get("repos") or [])
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in page.get("tags") or [])
    # The h1 is the page's own first heading, already inside html_body. Repeating the title
    # above it would give every page two headings that say the same thing.
    gist = page.get("gist") or ""
    summary = (f'<aside class="short"><span class="short-k">In short</span>'
               f"<p>{esc(gist)}</p></aside>") if gist else ""

    banner = ""
    if confidence in CONFIDENCE_BANNER:
        head, text = CONFIDENCE_BANNER[confidence]
        banner = (f'<aside class="conf-note c-{esc(confidence)}">'
                  f'<span class="conf-k">confidence {esc(confidence)}</span>'
                  f"<h2>{esc(head)}</h2><p>{esc(text)}</p></aside>")

    # Only where the convention is actually visible. This note used to render on all 232
    # pages and only 32 of them contain the style it explains — 200 pages carrying a paragraph
    # about a thing that is not on them, which trains a reader to skip the small print on the
    # 32 where it is load-bearing.
    unpub_note = (
        '<p class="unpub-note">Words in <span class="unpub">this style</span> name a page '
        'that exists privately and was not published. They are shown as text, never as a '
        'link that goes nowhere.</p>') if unresolved else ""

    body = f"""
<article class="page">
  <nav class="crumb" aria-label="Breadcrumb">
    <a href="../index.html">Ask</a> <span aria-hidden="true">/</span>
    <a href="../browse.html#{esc(page['type'])}">{esc(META_LABEL.get(page['type'],
      page['type']))}</a>
  </nav>
  <div class="meta">
    <span class="kind k-{esc(page['type'])}">{esc(page['type'])}</span>
    <span class="conf c-{esc(confidence)}" title="{esc(note)}">confidence {esc(confidence)}</span>
    <span class="dates">{dates_line(page)}</span>
    {f'<span class="repos">{esc(repos)}</span>' if repos else ""}
  </div>
  {summary}
  {banner}
  {outline_block(headings)}
  <div class="prose">{anchors(html_body, headings)}</div>
  {f'<div class="tags">{tags}</div>' if tags else ""}
  {sources_block(page)}
  {related_block(bundle, page)}
  {unpub_note}
</article>
"""
    desc = gist or f"{page['type']} page from a private knowledge base."
    doc = document(page.get("title") or stem, desc, body,
                   current="", depth=1, cfg=cfg, stats=bundle.stats,
                   path=f"p/{stem}.html", jsonld=[article_ld(page, cfg, headings)])
    return doc, headings, unresolved
