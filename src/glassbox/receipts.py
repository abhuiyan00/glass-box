"""The three documents that exist so the rest can be checked: receipts, gaps, how it works.

`receipts.html` is the page the previous design put on the front. Moving it here is the
substantive change, not a reshuffle: a table of retrieval metrics is an answer to "should I
believe the front page", and nobody asks that before they have read the front page.

The form changed with the position. Eight numbered rows with a footnote each became one
table with a **How it is counted** column, because a figure whose derivation is not next to
it is a figure a reader has to take on faith — which is exactly what this site claims not to
ask for. Where a number cannot be counted, the cell says so and the reason is written out.

Nothing on any of these three pages is authored except the prose in the third column. Every
value is read from `content/stats.json`.
"""

from .shell import document, esc, num

FIGURE = "figure"


def table(rows, head=("", "Counts", "How it is counted")):
    """rows: (value, what, how). A None value renders as a visible gap, never a zero."""
    out = ["<div class=\"tw\"><table class=\"receipts\"><thead><tr>",
           f"<th>{esc(head[0])}</th><th>{esc(head[1])}</th><th>{esc(head[2])}</th>",
           "</tr></thead><tbody>"]
    for value, what, how in rows:
        out.append(f'<tr><td class="fig">{num(value)}</td>'
                   f"<td>{what}</td><td class=\"how\">{how}</td></tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def receipts(bundle, cfg):
    c = bundle.stats.get("corpus") or {}
    e = bundle.stats.get("evals") or {}
    b = bundle.stats.get("budget") or {}

    corpus_rows = [
        (c.get("repos"), "source repositories read",
         "Distinct first path segments of every page's <code>sources:</code> field. There is "
         "no list of repositories in any code — a sixteenth appears the moment a page cites "
         "it."),
        (c.get("pages_knowledge"), "pages in the private wiki",
         "Every markdown page under <code>wiki/</code> carrying one of the six page types. "
         "Catalogue and index files are not counted."),
        (c.get("pages_publishable"), "pages that <em>may</em> be published",
         "Session records are categorically unpublishable, so the publishable universe is "
         "smaller than the wiki. The difference is not an oversight; it is a rule."),
        (c.get("published_now"), "pages public on this site",
         "Flipping a page public is a human decision made once per page, and it is the one "
         "step in the whole pipeline that is never automated."),
        (c.get("decisions_total"), "decisions recorded",
         "Pages of type <code>decision</code>: one choice each, with a date."),
        (c.get("decisions_with_reject"), "of those that name the alternative they rejected",
         "Counted structurally — the page must carry a rejected-alternatives heading or "
         "table, not merely mention a rejection in prose. An earlier hand count said 35 and "
         "was wrong in the flattering direction."),
        (c.get("claims_superseded"), "claims retired since they were first written",
         "Rows in a dated claim table whose validity has an end date. The old claim is never "
         "deleted — it keeps its dates and the page says what changed."),
    ]

    held = e.get("hit_at_5_heldout")
    eval_rows = [
        (held, "hit@5 on phrasings the search has never seen",
         f"Of {num(e.get('heldout_set_size'))} held-out questions, the share where the right "
         f"page came back in the top five. The gate is {num(e.get('hit_at_5_gate'))}. "
         f"<strong>The questions were written by the author</strong>, so this is "
         f"reproducible, not independent — it is the direction of travel, not a benchmark."),
        (e.get("hit_at_5_tuned"), "hit@5 on the set the search was tuned against",
         f"{num(e.get('golden_set_size'))} questions. Anyone can publish this number; it "
         f"proves only that nothing regressed."),
        (e.get("refuse_measured"), "share of unanswerable questions it correctly refuses",
         f"Held back on purpose. It measures {num(e.get('refuse_cases'))} cases and the "
         f"gate is {num(e.get('refuse_gate'))} — a perfect score on that few reads as a "
         f"proven property and is not one. The cell fills in when the negative set reaches "
         f"20."),
        (e.get("changes_vetoed"), "changes the evaluation rejected that looked like wins",
         "A word-stemming change that read as obviously better and measured worse, and a "
         "scoring path whose ties were broken by set iteration, so identical code scored "
         "0.73, 0.53 and 0.60 on three runs. The evaluation outranks the author."),
    ]

    cost_rows = [
        (b.get("spend_to_date_usd"), "US dollars spent on model calls, total",
         "Every metered call appends to a ledger; this is its sum. Building and searching "
         "this site costs nothing — no model runs at request time."),
        (b.get("cap_usd"), "hard spending cap",
         "Reached, the tooling aborts rather than continuing."),
        (b.get("per_call_usd"), "single-call ceiling",
         "Refused before the call rather than discovered after it."),
    ]

    body = f"""
<section class="page-head">
  <h1>The numbers, and how each one is counted</h1>
  <p class="lede">Every figure below is computed when this site is built, from the same
    files the pages are written from. None of them is typed into a template. Where something
    has not been measured the cell says so — an unmeasured value is never shown as a zero.</p>
</section>

<section class="band">
  <h2>What is in here</h2>
  {table(corpus_rows)}
</section>

<section class="band">
  <h2>Does the search actually work</h2>
  <p class="band-b">The honest figure is the first one, and it is not flattering. It is the
    one printed largest anyway.</p>
  {table(eval_rows)}
</section>

<section class="band">
  <h2>What it costs to run</h2>
  {table(cost_rows)}
</section>

<section class="band closing">
  <h2>What this page does not prove</h2>
  <p>That the pages are <em>correct</em>. These figures measure coverage, retrieval and
    process — whether a claim can be traced to a source, not whether the source was right.
    The pages carry their own confidence levels and name their own gaps; see
    <a href="gaps.html">what it does not know</a>.</p>
</section>
"""
    return document("Receipts", "Every figure on this site, and how each one is counted.",
                    body, current="receipts", depth=0, cfg=cfg, stats=bundle.stats,
                    path="receipts.html")


def gaps(bundle, cfg):
    c = bundle.stats.get("corpus") or {}
    e = bundle.stats.get("evals") or {}
    held = e.get("hit_at_5_heldout")
    miss = round((1 - held) * 100) if isinstance(held, (int, float)) else None

    rows = [
        (miss, "percent of unseen phrasings that return nothing at all",
         "The inverse of the held-out score on the <a href=\"receipts.html\">receipts</a> "
         "page. Roughly one question in three, asked in words the pages do not use, comes "
         "back empty."),
        (c.get("todo_count"), "gaps written into the pages themselves",
         "Each one sits next to the claim it qualifies rather than in a list at the back. "
         "They render on the page as a marked block, not as hidden text."),
        ((c.get("published_by_confidence") or {}).get("medium"),
         "published pages carrying a stated limit",
         "Drawn from the repository, with no second source and no confirmation from the "
         "author. They open with a block saying so. The gate admitted them because the "
         "alternative was hiding a page rather than its limit — but the count belongs here, "
         "not only on the page."),
        (c.get("low_confidence"), "claims held at low confidence, and not published",
         "Single-sourced, or resting on a question that was asked and not answered. These "
         "are the pages the gate still refuses: publishing one would ship the absence of a "
         "fact in the shape of one."),
        ((c.get("pages_knowledge") or 0) - (c.get("published_now") or 0) or None,
         "pages that exist privately and are not here",
         "The low-confidence set above, plus one session record, which is categorically "
         "unpublishable. Everything else the wiki holds is on this site."),
        # The published-scoped figure, not the wiki-wide one. This row used to print the
        # latter — a count over all 240 private pages under a heading that describes the
        # search box on this site, so eight of the pages it counted were ones no visitor can
        # reach. `pages_without_aliases` is still measured; it is the author's work queue,
        # and it does not belong on a page about what a reader can and cannot find here.
        (c.get("published_without_aliases"), "published pages findable only if your words "
         "match theirs",
         "A page named for its conclusion is asked for by its symptom. Without alternative "
         "phrasings recorded, such a page scores zero against the question it exists to "
         "answer — and most misses in the evaluation are one of these."),
        (c.get("dangling_from_published"), "links from a public page to a private one",
         "Counted once per page per distinct target. The build log counts every marker it "
         "writes instead, so it reports a larger number for the same fact — the two are "
         "labelled differently now rather than left to look like a contradiction. Each "
         "renders as plain text, never as a dead link: the private wiki is one connected "
         "web, and publishing a slice of it necessarily cuts edges."),
        (c.get("dangling_pages"), "public pages carrying at least one of those",
         "The row above spread over pages. Two hundred of the pages here name no private "
         "page at all, which is the fact that count on its own hides."),
    ]

    body = f"""
<section class="page-head">
  <h1>What it does not know</h1>
  <p class="lede">A knowledge base that only advertises its coverage is a brochure. These
    figures come out of the same build as every other number here, and not one of them
    flatters it. Raise any of them in the source and it drops on the next build — nothing on
    this page is written by hand.</p>
</section>
<section class="band">{table(rows)}</section>
<section class="band closing">
  <h2>Two limits worth stating plainly</h2>
  <p><strong>It is one person's account.</strong> Every page was written from repositories
    the author built, and where a reason was not recorded anywhere it is marked as missing
    rather than reconstructed. An invented reason is indistinguishable from a real one
    later, which is why none were invented.</p>
  <p><strong>The search is words, not meaning.</strong> There is no model and no embedding
    behind the box on the front page — it matches terms, weights fields, and follows one
    link. Ask it something in vocabulary the pages never use and it will tell you it found
    nothing, which is the correct answer and an unhelpful one.</p>
</section>
"""
    return document("Gaps", "What this knowledge base cannot answer, counted.",
                    body, current="gaps", depth=0, cfg=cfg, stats=bundle.stats,
                    path="gaps.html")


def how(bundle, cfg):
    c = bundle.stats.get("corpus") or {}
    # This sentence said "high confidence" and had been false since the gate was widened to
    # admit `medium` — 43 of the 232 published pages are medium, each one carrying a banner
    # that says so, on a site whose argument is that its own description can be checked. The
    # levels are now read from the same count the rest of the page prints, so widening the
    # gate again rewrites this line instead of contradicting it.
    levels = " or ".join(sorted(c.get("published_by_confidence") or {})) or "high"
    body = f"""
<section class="page-head">
  <h1>How it works</h1>
  <p class="lede">Two repositories and one file boundary between them. This one is public and
    holds no private page; the other is private and renders no HTML.</p>
</section>

<section class="band">
  <h2>The path a page takes</h2>
  <ol class="steps">
    <li><span class="step-n">01</span><div><h3>It gets written once</h3>
      <p>A repository is read, then the author is interviewed about what the code cannot
      say — why a tool was chosen, what was tried and abandoned, whether the project is
      actually finished. Answers become quoted evidence on the page. Questions that go
      unanswered become a recorded gap, never a plausible-sounding reason.</p></div></li>
    <li><span class="step-n">02</span><div><h3>It has to pass a gate to leave</h3>
      <p>Pages default to private. A page becomes public only when a person marks it so, and
      only if it clears mechanical checks first: the right type, {esc(levels)} confidence,
      current status, and no unreviewed dependency on a sensitive source. Anything the gate
      rates <em>low</em> — one weak source, or a question that was asked and never answered —
      stays private, and session records can never be published at all. Pages admitted below
      the top level open with a block saying exactly what that costs you.</p></div></li>
    <li><span class="step-n">03</span><div><h3>What crosses is data, not the wiki</h3>
      <p>An export writes a bundle of the {c.get("published_now", 0)} cleared pages —
      their text, what they link to, and every measured figure — and scans it for anything
      secret-shaped before it is written. The private repository is not present when this
      site is built, so it cannot leak a page it has never seen.</p></div></li>
    <li><span class="step-n">04</span><div><h3>This site is generated from that bundle</h3>
      <p>Python standard library, no dependencies, no build tooling. Output is flat HTML with
      relative links, so it works on a static host and equally well from a folder on your
      desktop with no network at all.</p></div></li>
  </ol>
</section>

<section class="band">
  <h2>What happens when you type a question</h2>
  <p class="band-b">Nothing leaves your browser. The index ships with the page.</p>
  <ul class="plain">
    <li>Your words are matched against six fields per page — its name, title, alternative
      phrasings, summary, tags and source paths — each weighted differently, plus the body
      text at the lowest weight.</li>
    <li>Rare words count for more than common ones, measured across the pages published
      here. That is why a ranking on this site can differ slightly from the author's private
      tool: the same scorer, a smaller corpus.</li>
    <li>A score is multiplied by how much of your question the page actually covered,
      squared. This is what stops a page about a data-protection <em>controller</em> from
      answering a question about a Kubernetes ingress <em>controller</em>.</li>
    <li>Then it follows exactly one link outward, because a link between two pages is the
      author's own judgement that they belong together — the most reliable signal available
      and one that word matching cannot see.</li>
    <li>If nothing clears the relevance floor, it says so and offers what it does cover.
      A designed refusal beats a confident wrong answer.</li>
  </ul>
</section>

<section class="band closing">
  <h2>Why not just use a chatbot over the pages</h2>
  <p>Because a summary you cannot check is worth less than a page you can. This returns
    pages, and every page names the files it was written from and quotes them. The failure
    mode of a language model here is a fluent sentence with nothing behind it, which is the
    exact failure this whole system was built to avoid. If prose answers are added later,
    they will cite the page every claim came from or they will not ship.</p>
</section>
"""
    return document("How it works", "Two repositories, one gate, and a search that runs in "
                    "your browser.", body, current="how", depth=0, cfg=cfg,
                    stats=bundle.stats, path="how.html")
