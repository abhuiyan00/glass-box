"""The two documents a visitor actually arrives on: ask, and browse.

The landing page leads with a question box and nothing else above it. That is the whole
argument of the redesign it replaces: the previous version opened with eight numbered rows of
retrieval metrics, which answers a question a hiring reader has not asked yet. Numbers are
evidence for a claim, and the claim has to come first — so the metrics moved to
`receipts.html`, one click away, where a sceptical reader will look for them anyway.

Every card, tile and count below is derived from the bundle. There is no editorial list in
this file: add a repository to the private wiki, export, rebuild, and it appears.
"""

from .shell import document, esc, site_url

KIND_LABEL = {
    "project": ("Projects", "One per repository — what it is, how it is built, where it stands."),
    "decision": ("Decisions", "One choice each, dated, with the alternative that lost and why."),
    "pattern": ("Patterns", "How this author builds, confirmed across repositories."),
    "concept": ("Concepts", "A transferable idea, explained once."),
    "tech": ("Tech", "A named tool or library, and what it was actually used for."),
}


def chips(items, attr="data-seed"):
    return "".join(f'<button type="button" {attr}="{esc(q)}">{esc(q)}</button>'
                   for q in items)


def person(cfg):
    """The author, as schema.org, with no field invented.

    `role` and `location` are deliberately empty in `glassbox.toml` — an empty value renders
    as nothing and never as a guess — so they are omitted here rather than shipped blank. A
    structured-data consumer treats an empty `jobTitle` as a claim that the person has none.
    """
    who = {"@type": "Person", "name": cfg["author"]["name"]}
    if cfg["author"].get("github"):
        who["url"] = cfg["author"]["github"]
        who["sameAs"] = [cfg["author"]["github"]]
    if cfg["author"].get("role"):
        who["jobTitle"] = cfg["author"]["role"]
    return who


def site_ld(bundle, cfg):
    """WebSite + the search action, so the query box is machine-discoverable.

    The `SearchAction` is only emitted with an origin configured: its whole content is a URL
    template, and a template built on a guessed origin points a search engine at a page that
    may not exist. Same rule as `og:url` — see `shell.site_url`.
    """
    origin = site_url(cfg)
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": cfg["site"]["title"],
        "description": cfg["site"]["subtitle"],
        "inLanguage": "en",
        "author": person(cfg),
    }
    if origin:
        data["url"] = origin
        data["potentialAction"] = {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint",
                       "urlTemplate": origin + "index.html?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        }
    return data


def card(page, depth_prefix="p/"):
    """One result-shaped card. Same markup the client renders, so the two cannot drift."""
    repo = (page.get("repos") or [None])[0]
    tail = f'<span class="from">{esc(repo)}</span>' if repo else ""
    return f"""<a class="card" href="{depth_prefix}{esc(page['stem'])}.html">
  <span class="kind k-{esc(page['type'])}">{esc(page['type'])}</span>
  <span class="card-t">{esc(page.get('title') or page['stem'])}</span>
  <span class="card-g">{esc(page.get('gist') or '')}</span>
  {tail}
</a>"""


def landing(bundle, cfg):
    stats = bundle.stats
    corpus = stats.get("corpus") or {}
    author = cfg["author"]["name"]
    projects = sorted(bundle.of_type("project"), key=lambda p: p.get("title") or p["stem"])
    tiles = []
    for kind, pages in bundle.by_type().items():
        label, blurb = KIND_LABEL.get(kind, (kind.title(), ""))
        tiles.append(f"""<a class="tile" href="browse.html#{esc(kind)}">
      <span class="tile-n">{len(pages)}</span>
      <span class="tile-t">{esc(label)}</span>
      <span class="tile-b">{esc(blurb)}</span></a>""")

    who = f"<strong>{esc(author)}</strong> — " if author else ""
    # The placeholder is a real question out of the verified set, not a written-in example.
    # A placeholder that would itself return nothing teaches the visitor the wrong thing
    # about the box on their very first look at it.
    placeholder = (bundle.questions[0] if bundle.questions
                   else "ask about a project, a decision or a tool")
    # Three different counts live near each other here and it would be easy to blur them:
    # repositories read, pages published, and project pages published. Each is derived and
    # stated where it belongs rather than one of them standing in for the others.
    n_repos = corpus.get("repos")
    if n_repos is None:
        n_repos = len(bundle.by_repo())
    n_pages = corpus.get("published_now") or len(bundle.pages)
    if len(projects) == n_repos:
        project_summary = "Every verified source repository has a public project page here."
    else:
        project_summary = (f"{len(projects)} of the {n_repos} verified source repositories have "
                           "a public project page here. The rest stayed private.")
    body = f"""
<section class="hero">
  <p class="eyebrow">{esc(cfg["site"]["subtitle"])}</p>
  <h1>Ask it something.</h1>
  <p class="lede">{who}{n_repos} verified source repositories, meaning sources named by
    published pages, written up as {n_pages} pages that each answer one question. Type below
    and it returns the pages that
    answer yours — or tells you plainly that nothing here does.</p>

  <form class="ask" role="search" method="get" action="index.html">
    <label class="vh" for="q">Ask the knowledge base</label>
    <div class="ask-w">
      <input id="q" class="ask-i" name="q" type="search" data-ask autocomplete="off"
        spellcheck="false" role="combobox" aria-expanded="false" aria-controls="sg"
        aria-autocomplete="list" placeholder="{esc(placeholder)}">
      <ul class="sg-box" id="sg" role="listbox" aria-label="Suggestions"
        data-suggest hidden></ul>
    </div>
    <button class="primary" type="submit">Search</button>
  </form>
  <p class="ask-note">Suggestions appear as you type: matching pages first, then word
    completions, then questions this has been measured answering. Everything runs in your
    browser — nothing is sent anywhere, and there is no model in the loop.
    <kbd>/</kbd> focuses the box, <kbd>↑</kbd><kbd>↓</kbd> move, <kbd>Esc</kbd> clears.</p>
  <div class="seeds">{chips(bundle.questions[:6])}</div>
</section>

<section class="results" data-results aria-live="polite"></section>

<section class="band">
  <h2>Browse instead</h2>
  <div class="tiles">{"".join(tiles)}</div>
</section>

<section class="band">
  <h2>The projects</h2>
  <p class="band-b">{project_summary} Each says what the thing is, what it runs on, and what
    state it is honestly in. Every page names the files it was written from.</p>
  <div class="cards">{"".join(card(p) for p in projects)}</div>
</section>

<section class="band closing">
  <h2>Why you can check any of this</h2>
  <div class="three">
    <div><h3>Sources, not assertions</h3><p>Every page names the files it was written from,
      and quotes them. A claim with nothing behind it is marked as such rather than
      smoothed over.</p></div>
    <div><h3>It publishes its own misses</h3><p>The
      <a href="gaps.html">gaps page</a> counts what this knowledge base cannot answer, and
      the count is computed, not written.</p></div>
    <div><h3>Nothing here is hand-typed</h3><p>Every number comes from the build. See
      <a href="receipts.html">receipts</a> for what each one counts and how.</p></div>
  </div>
</section>
"""
    desc = (f"{corpus.get('published_now', len(bundle.pages))} pages on how "
            f"{author or 'the author'} builds software, searchable in the browser.")
    return document(cfg["site"]["title"], desc, body,
                    current="index", depth=0, cfg=cfg, stats=stats,
                    path="index.html", jsonld=[site_ld(bundle, cfg)])


def browse(bundle, cfg):
    """Everything, grouped by kind, filterable without a page load."""
    sections = []
    for kind, pages in bundle.by_type().items():
        label, blurb = KIND_LABEL.get(kind, (kind.title(), ""))
        rows = []
        for page in sorted(pages, key=lambda p: (p.get("title") or p["stem"]).lower()):
            names = page.get("repos") or []
            repos = ", ".join(names)
            # Two names fit and say something; nine is 302 characters of hyphenated slug that
            # wraps to sixteen lines and buries the row it belongs to. Above two, the count is
            # the fact anyway — a pattern's claim is how *many* repositories confirm it, and
            # the page itself lists every source file. Filtering is unaffected: data-text below
            # still carries all of the names, so typing a repository still narrows the list.
            shown = repos if len(names) <= 2 else f"{len(names)} repositories"
            rows.append(f"""<li class="row" data-kind="{esc(kind)}"
   data-text="{esc(((page.get('title') or '') + ' ' + (page.get('gist') or '') + ' '
                    + ' '.join(page.get('tags') or []) + ' ' + repos).lower())}">
  <a href="p/{esc(page['stem'])}.html">{esc(page.get('title') or page['stem'])}</a>
  <span class="row-g">{esc(page.get('gist') or '')}</span>
  <span class="row-m" title="{esc(repos)}">{esc(shown)}</span>
</li>""")
        sections.append(f"""<section class="grp" id="{esc(kind)}">
  <h2>{esc(label)} <span class="cnt">{len(pages)}</span></h2>
  <p class="band-b">{esc(blurb)}</p>
  <ul class="rows">{"".join(rows)}</ul>
</section>""")

    kinds = "".join(f'<button type="button" data-filter="{esc(k)}">{esc(KIND_LABEL.get(k, (k,))[0])}</button>'
                    for k in bundle.by_type())
    body = f"""
<section class="page-head">
  <h1>Everything, {len(bundle.pages)} pages</h1>
  <p class="lede">Grouped by what kind of thing each page is. Filtering happens in the
    page — no requests, no reload.</p>
  <div class="filters">
    <label class="vh" for="f">Filter by word</label>
    <input id="f" class="filter-i" data-filter-text autocomplete="off"
      placeholder="filter by word, tag or repository…">
    <div class="chips"><button type="button" data-filter="" class="on">All</button>{kinds}</div>
  </div>
  <p class="filter-count" data-filter-count aria-live="polite"></p>
</section>
{"".join(sections)}
"""
    return document("Browse", f"All {len(bundle.pages)} published pages, grouped by kind.",
                    body, current="browse", depth=0, cfg=cfg, stats=bundle.stats,
                    path="browse.html")


def notfound(bundle, cfg):
    """404. A dead end on a site about retrieval is the one page it must recover from.

    GitHub Pages serves this for any unmatched path, at any depth — `/p/typo.html` renders
    this document, not a copy of it one level down. So every path in it must be site-absolute,
    which is the single exception to the relative-path rule the rest of this module keeps —
    `depth="/"` makes the shell emit it — and it only works on a host. Opened from disk a 404
    is unreachable anyway: the file manager reports the missing file itself.
    """
    body = f"""
<section class="page-head">
  <h1>No page at that address</h1>
  <p class="lede">The link was mistyped, or it pointed at a page that is not public. Nothing
    here is deleted once published — {len(bundle.pages)} pages are searchable below.</p>
  <form class="ask" role="search" method="get" action="/index.html">
    <label class="vh" for="nf">Search this knowledge base</label>
    <div class="ask-w">
      <input id="nf" class="ask-i" name="q" type="search" autocomplete="off"
        placeholder="ask about a project, a decision or a tool">
    </div>
    <button class="primary" type="submit">Search</button>
  </form>
  <p class="ask-note">Or go to <a href="/browse.html">everything, grouped by kind</a>,
    the <a href="/map.html">map</a>, or <a href="/gaps.html">what this does not know</a>.</p>
</section>
"""
    return document("Not found", "No page at that address.", body,
                    current="", depth="/", cfg=cfg, stats=bundle.stats)
