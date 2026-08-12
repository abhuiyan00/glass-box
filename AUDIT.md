# Audit — 2026-07-31

> Two passes. **Pass one** below is the interface and coverage audit.
> **[Pass two](#pass-two--the-global-audit)** is the global one: correctness, disclosure,
> discoverability and the capabilities the site did not have.

A pass over the whole site: what it publishes, whether the search works for the people it is
aimed at, and whether the interface holds up when somebody actually uses it. Written after the
work, from the notes taken during it, including the parts that went wrong.

Everything below was measured on the build in `docs/` at the time of writing. Where a number is
self-graded or unscored, it says so.

---

## 1. Coverage — the site was publishing a quarter of what it knew

The trigger was a real observation: the tech page looked thin. It was worse than thin.

|                | before | after     |
| -------------- | -----: | --------- |
| knowledge pages published | 60 of 240 | **232 of 240** |
| tech           | 8 of 58 | 57 of 58 |
| project        | 3 of 15 | 15 of 15 |
| decision       | 21 of 38 | 38 of 38 |
| pattern        | 12 of 35 | 35 of 35 |
| concept        | 16 of 93 | 87 of 93 |

The gate was working exactly as written; the problem was what it was written to do. Three
things kept 180 pages private:

1. `confidence: high` only. 43 pages are `medium` — sourced from the repository alone, with no
   second independent witness. That is a real distinction and worth showing, not a reason to
   hide. **Medium now publishes, and says so on the page**: a `confidence medium` badge in the
   header and a banner that states what medium means before the reader has read a word of the
   body. `low` still does not publish — §4.1 defines it as one weak source or a question that
   was asked and never answered.
2. Three recorded `publish: false` stances, covering the fraud-analysis project and the
   cybersecurity cluster. These were reviewed and **reversed on the author's explicit
   decision**, not silently: before flipping anything, all 45 sensitive-source pages went
   through a mechanical secret sweep, a read-by-eye of the full list, and `audit-secrets`
   (0 matches). The redaction had already happened upstream — the raw lab reports are the dirty
   artefact; the wiki pages are synthesis. `brain.toml`'s `sensitive_reviewed` list went from 8
   stems to 63, and the reasoning is recorded there rather than in a commit message.
3. Four wiki pages whose prose still argued for withholding. Rewritten to record the reversal
   and, explicitly, what did *not* change.

**8 pages did not cross and will not**: 7 at `low` confidence, and 1 session page, which C2
excludes by construction.

Published split by confidence: **189 high, 43 medium** — shown on the receipts page, not just
in this file.

---

## 2. Search — the highest-leverage defect in the project

The corpus is written by its author, in the author's words. The people it is for ask in
different words. That gap was never measured, so it was never seen.

A set of 34 interviewer-phrased questions (`evals/interview.jsonl`) was written and run through
the real scorer:

| | hit@5 |
| --- | ---: |
| interview phrasing, before | **44%** |
| interview phrasing, after `aliases:` on 75 pages | **97%** (33 / 34) |

The one remaining miss is *"what is the subtlest bug you have run into"* — the corpus has no
page that frames itself that way, and inventing one to pass a test would be the wrong fix.

`interview.jsonl` is **deliberately never scored** in the published figures. The questions were
written after reading the corpus, against pages known to exist; a hit rate over them would
measure nothing but that. Its actual job is the suggestion list — export runs the real scorer
over every line and drops any question that does not surface its own expected pages, because a
suggested question that misses is the first thing a visitor clicks.

### The honest part

The published held-out figure moved the wrong way: **0.577 → 0.538**.

I assumed the aliases caused it and tested that assumption instead of reporting it. Blanking
every alias in memory and re-running gives **14/31 both ways** — aliases are net-neutral on this
set: one query recovered, one regressed. The drop is attributable to my own prose edits to the
stance paragraphs, which changed the wording the scorer sees. It is reported here rather than
buried because a self-graded number that only ever moves up is not evidence of anything.

Golden (tuned) stays at 1.00, which is what a tuned set is for and why it is labelled.

### Index size

Publishing 232 pages instead of 60 took the browser-side index to **247 KB gzipped against a
250 KB budget**. Rather than move the budget, the format changed: a shared integer vocabulary,
a parallel `idf` array, and delta-coded sorted term ids.

**247 KB → 157 KB**, budget untouched.

That change silently reranked results on the first attempt — the initial vocabulary dropped
field-only terms (title and alias words no body uses), which had previously scored through
`idf_default`. Caught before it shipped, fixed by keeping them in the vocabulary, and pinned by
a new test (`test_a_field_only_term_still_scores`). Three tests now assert the compressed index
scores **identically** to the spelled-out one and that two builds are byte-identical.

---

## 3. The theme button

Reported directly, and it was real: the control was labelled `Theme` and said the same thing
whatever state it was in.

Fixed **in CSS, not JavaScript**, so the label is correct at first paint rather than corrected a
frame later. Both words are in the DOM; three rules decide which one shows — the light default,
the OS dark preference, and the explicit override, which must beat both.

Verified in Chromium, in both OS schemes, through two clicks each:

```
OS prefers light   first paint "Dark"  → click → "Light" (root=dark) → click → "Dark" (root=light)
OS prefers dark    first paint "Light" → click → "Dark"  (root=light) → click → "Light" (root=dark)
```

Chromium's own accessibility tree computes the button's accessible name as
**`role=button name="Switch to Dark"`** — not "Theme", and not the concatenation of both words.

---

## 4. What the tests are

Four harnesses, run against the built site:

| harness | what it can see |
| --- | --- |
| `pytest` (glass-box) | 23 tests — build determinism, index equivalence, the publication gate at render time |
| `pytest` (second-brain) | 71 tests — disclosure, session exclusion, gate criteria |
| jsdom | 41 behaviour checks — filters, typeahead, map interaction, deep links, escaping |
| Chromium (Playwright) | layout, contrast, focus order, accessible names, and what actually paints |

The Chromium sweep covers 8 standing pages × 2 themes × 2 widths, plus 3 interaction states
(refusal, answer, mid-word) × 2 themes × 2 widths. It also asserts the claim the site makes about
itself: loaded over `file://`, **the network tab stays empty**.

State at the end of pass one: **23 + 71 pytest passing, 41/41 jsdom, Chromium sweep clean** —
no horizontal scroll, no unnamed control, no contrast failure, in either theme at either width.
Pass two added 12 pytest cases and a fifth harness, and found a contrast failure this sweep
could not see because it walks elements and the failure was on a pseudo-element — see §9.7.
Current figures are in [§13](#13-numbers-after).

---

## 5. Defects found and fixed

### Found by reading screenshots, not by assertions

These all had correct markup. Every number was present. They were only visible by looking.

- **All 15 ring labels stacked into one column** down the middle of the map. Fanned around the
  full circle; a partial fan still bunched the inner numbers, where the arc is shortest.
- **179 of 232 map nodes shared one grey.** The legend offered five categories and the picture
  drew three colours, so the two largest types were indistinguishable from each other and from
  the third. Five hues now, declared once and consumed by the chip, the node and the legend dot.
  Colour stays redundant: every node also carries a `<title>`, names its type in the readout, and
  can be isolated from the legend.
- **The rings were 7px apart carrying 9px nodes** and read as a speckled disc rather than as
  rings — which loses the one rule the page asks a reader to learn. Measured, not guessed:
  widening the band to 46..354 gives 19px spacing and 10px of daylight.
- **The refusal offered the three alphabetically-first pages.** Someone asking about Kubernetes
  was told the site does cover "Ackermann and Primitive Recursion". Now one page per kind, each
  the best-connected of its kind.
- **The refusal fired mid-word** while the dropdown above it was offering valid completions —
  the page said "nothing here answers that" and simultaneously offered four things that did.
  There is now a "still typing" state.
- **The map docstring overclaimed.** It said radius encodes how many pages a repository has;
  radius encodes *rank*. Corrected, with the reason the rank encoding is the right one.

### Found by the browser

- **`p/star-schema.html` scrolled sideways at 390px** from long source paths. Fixed at the
  source (`min-width: 0`, `overflow-wrap: anywhere`), with `body { overflow-x: hidden }` as a
  backstop — a last line of defence, not the fix.
- **`browse.html` had no container on its group sections.** The heading inset to 140px and the
  rows underneath it started at 0 and ran the full 1280px, with the repository column clipped by
  that same backstop. `.grp` was simply missing from the site's container rule. Nothing exceeded
  `clientWidth`, so the overflow sweep passed it — see §6.
- **The browse row could not shrink.** Three grid tracks sized `1fr 2fr auto`, and the widest
  source list is 302 characters of repository names — about 2,200px of monospace on one line.
  All three tracks are now `minmax(0, …)`, and above two repositories the row shows the count
  (16 rows), which is the fact a pattern page is making anyway. Filtering still matches on every
  name, and the page itself lists every source file.
- **The refusal list item could not shrink either** — a grid item at default `min-width: auto`,
  clipping the longest summary mid-word.

### Found in the data

- **Two project summaries were cut at a supervisor's initial.** "course led by T. Kubik" became
  "course led by T", and the trailing `.rstrip(".")` then removed the one character that would
  have made the cause obvious. Both are repository landing pages, so it showed on every card
  that listed them.

  The first fix was worse than the bug: a general rule — lowercase before the stop, capital
  after — fixed these two and ran **26 other pages into their second and third sentence**,
  because this wiki ends sentences on acronyms ("its hosted CI.", "querying RDF.") and starts
  them on lowercase identifiers ("factory_boy wraps that…"). Caught by diffing old against new
  across all 240 pages *before* exporting. The shipped fix blocks exactly one thing — a full
  stop after a lone capital following a space or bracket — and changes exactly 2 pages.
- **18 published summaries leaked literal markdown**, reading `*Optimization Methods* course` on
  the card, in the browse list and in the map readout. `plain()` stripped `**` and backticks but
  not single-asterisk italics. Now flattened, and narrower than markdown in the one direction
  that matters: the opening star may not follow a word character, so the glob in
  `all 20 KaTeX_*.woff2 font files` cannot open an emphasis run and swallow the sentence. 17 of
  18 fixed; the survivor is that glob, which should stay.

### Found in the tests

- **A test asserted `confidence == "high"`**, which is a copy of the rule rather than a test of
  it. Adding the medium tier changed the gate, the export was correct, and the test failed
  anyway. It now reads the gate's own `PUBLISHABLE_CONFIDENCE` set, and separately asserts the
  thing actually worth pinning: that `low` never joins it.

### Documentation drift

- README said 60 pages and "no graph visualisation". Now "232 of its 240 pages", the map row,
  and "no *force-directed* graph" — with the distinction argued rather than asserted. Added: an
  explicit "no claim that the search is semantic", and a paragraph on the 8 pages that did not
  cross.

---

## 6. Where my own tests lied

A checker that lies is worse than no checker, so these are listed as findings.

- **The contrast checker divided by 255 regardless of notation.** `getComputedStyle` returns
  `rgb(11, 110, 128)` normally but `color(srgb 0.043 0.431 0.502)` once `color-mix()` is
  involved — 0..1, not 0..255. Every tinted chip looked near-black and it reported **five
  contrast failures on colours that clear 4.9:1**. I nearly "fixed" a regression that did not
  exist. The parser now reads the scale off the notation; the real ratios are 4.89–5.87:1.
- **The unnamed-control checker read `textContent` only**, so both `<input>` elements looked
  unnamed. An input is named by its `<label for>`. Chromium's accessibility tree computes
  `role=combobox name="Ask the knowledge base"` and `role=textbox name="Filter by word"`.
- **The overflow checker flagged a contained table.** The wide table on `p/stickfps.html` is
  inside an `overflow-x: auto` scroller with `docScroll: 0` — that is the fix, not the bug. It
  now walks ancestors, and **stops at `<body>`**, because body carries the site-wide
  `overflow-x: hidden` backstop and walking past it would silence the entire check.
- **The screenshot sweep flagged the skip link five times.** It is parked at `left: -9999px` on
  purpose. Absolutely-positioned elements are now skipped.
- **The screenshot sweep reported the theme bug as still present.** It read raw `textContent`,
  which contains both words because CSS hides one — so it saw `"DarkLight"` before and after and
  declared no change. It now reads what renders.
- **The sweep only visited standing pages.** Half this site only exists after somebody types.
  The refusal panel was never on screen, which is why a real layout bug in it survived a clean
  run. The sweep now types, in both themes, at both widths.

---

## 7. Current numbers

```
pages          232 published of 240   (concept 87 · tech 57 · decision 38 · pattern 35 · project 15)
confidence     189 high · 43 medium   (7 low and 1 session page withheld)
repositories   15
links          1,303 drawn between published pages

search index   157.1 KB gzipped       (budget 250)
landing        4.0 KB gzipped         (budget 120)
map            33.3 KB gzipped
browse         25.2 KB gzipped
app.js         8.4 KB gzipped
app.css        7.1 KB gzipped

hit@5 golden   1.00   (tuned — that is what a tuned set is for)
hit@5 heldout  0.538  (self-graded, published)
hit@5 interview 0.971 (33/34, unscored by design — drives the suggestion list)

tests          23 pytest (glass-box) · 71 pytest (second-brain) · 41 jsdom · Chromium sweep clean
network        0 outbound requests over file://
```

---

## 8. Left open

- **The heldout set is self-graded and small** (31 questions). It is published anyway, with that
  label, because an unlabelled number would be worse. It is the weakest evidence on the site.
- **141 of 232 pages still carry no `aliases:`.** That is published as a gap figure, and it is
  the single highest-leverage thing left: aliases are the documented lever for the phrasing
  mismatch, and the interview set went from 44% to 97% on the back of adding them to 75 pages.
- **`evals.refuse_measured` is null** — the refusal rate is not measured, and the site shows the
  hole rather than an estimate.
- **The browser harnesses live outside the repository.** They need `playwright` and `jsdom`,
  and this project's zero-dependency, no-build-step posture is a claim it makes on its own
  pages. Committing them would weaken that claim; leaving them out means these checks are not
  reproducible by a reader. This is a real trade-off and it is currently unresolved.
- **The map's edge layer is faint by design and nearly invisible in dark mode.** That is the
  intended reading — the rings carry the meaning and the links are texture until you ask for
  them — but it is a judgement call, not a measurement.

---
---

# Pass two — the global audit

Pass one asked whether the site publishes what it knows and whether the interface works. This
one asks the questions a team would ask before putting a name on it: can it be wrong, can it
leak, can it be found, and what can a reader do that they currently cannot.

Same discipline as before. Every finding below was reproduced before it was fixed and measured
after. Where I got something wrong, that is written down next to the fix rather than quietly
corrected.

---

## 9. What was actually wrong

Nine defects. None was a crash, which is the point — a site whose entire argument is that its
claims can be checked fails by being subtly untrue, not by falling over.

### 9.1 The gate description had gone false — `how.html`

Step 02 of *How it works* said a page must clear "the right type, **high confidence**, current
status". The gate was widened to admit `medium` in the last pass. 43 of the 232 published
pages are medium. Every one of them carries a banner saying so, and the page explaining the
system said they could not exist.

This is the worst class of bug this project can have. It is not a broken feature; it is the
site describing a rule it does not follow, on the page a sceptical reader opens *specifically*
to check the rule.

Fixed by deriving the sentence from `published_by_confidence` — the same figure the receipts
table prints — so widening the gate again rewrites the prose instead of contradicting it. The
line now also names what `low` means and says that pages below the top level open with a
stated limit.

### 9.2 A public figure counted private pages — `gaps.html`

The row **"pages findable only if your words match theirs"** printed `pages_without_aliases`,
which the private tool computes over all 240 wiki pages. The heading is a claim about *this
site's search box*. Eight of the pages it counted are ones no visitor can reach.

| figure | counts | was shown as |
| --- | ---: | --- |
| `pages_without_aliases` | 141 | this site's findability |
| `published_without_aliases` | **134** | — |

Both numbers are true. Only one answers the question in the heading. The exporter now computes
both: the wiki-wide figure stays, because it is the author's work queue, and the site prints
the published-scoped one. Cross-checked against an independent count over the bundle — 134
both ways.

### 9.3 Two counts of the same thing, one label between them

The build log printed `50`. The gaps page printed `39`. Same-sounding fact, no way for a
reader to tell which was wrong.

Neither was. They count different things:

| number | what it counts |
| ---: | --- |
| 39 | (page, target) pairs — a page naming two private pages contributes two |
| 50 | markers written — a page naming the same private page twice contributes two |
| 32 | published pages carrying at least one |
| 8 | distinct private pages named |

All four measured independently and confirmed. The build log now says "markers for a private
page", the gaps row says "counted once per page per distinct target" and explains why the log
differs, and `dangling_pages` (32) ships as its own row — because "39 links" hides the fact
that 200 pages have none.

### 9.4 `javascript:` links were not blocked — `markdown.py`

```python
text = LINK.sub(lambda m: f'<a href="{m.group(2)}" rel="noopener">{m.group(1)}</a>', text)
```

Escaping runs before the inline rules, so a `"` inside a URL arrives as `&quot;` and cannot
close the attribute. That is a real defence and it is the one the module's docstring described.
It says nothing about the *scheme*. `[click](javascript:alert(1))` became a live anchor with a
script for a target.

No page in the corpus does this. That is exactly why it belongs in an allow-list rather than a
block-list: this repository does not own the wiki, the wiki is written by an agent pipeline,
and "no page does this today" is a fact about today. `http`, `https`, `mailto` and every
relative form stay links; anything else renders as its own text, the same treatment an
unpublished wikilink gets. The docstring now says escaping is not the whole defence.

`rel="noopener"` was also inert — it governs a window this site never opens, because no link
here carries `target`. External links now carry `noopener noreferrer`, the half that does
something.

### 9.5 The client escaped for text and wrote into attributes — `app.js`

```js
function esc(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;     // escapes & < > — leaves " and ' alone
}
```

That is the HTML serialiser's rule for *text nodes*. Correct between tags. Most uses here are
inside them: `href="p/…"`, `data-seed="…"`, `class="kind k-…"`. One `"` in a page title or an
eval question would have closed the attribute early and let the rest parse as markup.

No such string exists in the corpus, which is the whole reason it would have shipped. Replaced
with an explicit five-character escape, asserted against the file the browser actually loads.

### 9.6 A publish plan with 235 private paths, sitting in the public repository

`.publish-plan.json` — left over from the bulk publish decision in pass one — held **235
absolute paths inside the private wiki**, including the 63-page list of what had been cleared
against sensitive sources. Untracked, so nothing leaked. Nothing would have stopped it either:
`git add -A` is one keystroke, and the file it would have published is a map of the private
wiki, from the repository whose entire claim is that it holds no private page.

Moved out, added to `.gitignore`, and `test_nothing_tracked_names_the_private_repository` now
asks `git ls-files` — not the filesystem, because the question is what would be *disclosed*,
and an ignored working file discloses nothing.

**The first version of that guard was worthless.** See §11.

### 9.7 Placeholder ink was below the contrast threshold — everywhere, always

```css
.ask-i::placeholder { color: var(--muted); opacity: 0.75; }
```

`--muted` is the dimmest ink in the palette that clears 4.5:1 — it measures 5.78:1 on the light
surface. Multiplying it by 0.75 took the placeholder to **3.45:1 light, 4.43:1 dark**. This is
the hint text on the site's primary control, and it has been under threshold for the length of
the project.

Nothing caught it because the accessibility sweep walks *elements*, and a placeholder is a
pseudo-element. Measured with a probe that composites through ancestors and reads
`::placeholder` explicitly; now 5.98:1 and 6.89:1. Guarded by a test that fails if the dimming
comes back.

### 9.8 A note on 232 pages that applied to 32

Every article ended with a paragraph explaining that words in a certain style name a private
page. 32 pages contain that style. The other 200 carried a paragraph about something that is
not on them — which trains a reader to skip the small print on the 32 where it is load-bearing.
Now rendered only where `unresolved` is non-empty, asserted both ways: note without style
fails, style without note fails.

### 9.9 A dead CSS declaration describing a rendering that never happened

`.hlink { color: var(--line-2) }` never applied — `.prose a` is two classes to its one. The
marker has always drawn in the link colour, which is the correct outcome and measures 5.7:1.
Removed rather than "fixed", because a value that loses describes a rendering that does not
happen.

---

## 10. What the site can now do that it could not

### 10.1 Search follows the reader

The single largest gap, and it was structural rather than cosmetic: the question box existed
on **one** of 233 documents. A reader who finished an article and wanted to ask a second
question had to navigate home first.

Every page except the landing one now carries a header search with the full typeahead —
matching pages, word completions, measured questions, arrow keys, `Esc`.

Two things make it more than a decoration:

- **It is a real `<form method="get">`.** With JavaScript off the browser builds
  `index.html?q=…` and the landing page's URL handler runs it. Verified in Chromium with
  scripting disabled: the form still has its `action`, `method` and `name`, and the page is
  still styled.
- **`<body data-base>`.** The runtime wrote `p/stem.html` as a literal, which was correct
  exactly as long as results only ever appeared at depth 0. From an article page that resolves
  to `p/p/stem.html`. The shell writes the depth because it is the only thing that knows it.

### 10.2 A link to this site previews as something

No Open Graph tags existed. A URL pasted into Slack, LinkedIn or a message to an interviewer
rendered as a bare grey string — the first impression lost before the page opens. `og:title`,
`og:description`, `og:type`, `og:site_name` and `twitter:card` now ship on all 244 documents.

**No `og:image`.** Every platform that matters rasterises, this repository holds no binary
assets and no image encoder, and the honest options were a checked-in PNG that nothing
regenerates or a dependency. Named here rather than left as a silent omission.

### 10.3 It tells a machine what it is

`WebSite` + `SearchAction` on the landing page, `TechArticle` on every article — headline,
description, `dateModified`, keywords, and `citation` carrying the source files the page was
written from. That last one is the page's central claim, stated a second time in a register a
machine can read.

Every field is read from the bundle; none is defaulted. `role` and `location` are empty in
`glassbox.toml` on purpose, so they are omitted rather than shipped blank — a consumer treats
an empty `jobTitle` as a claim that the person has none.

### 10.4 A 404 that recovers instead of ending

GitHub Pages was serving its own generic page. There is now one with a working search box and
three routes out.

It is the only document on the site using absolute paths, and that is load-bearing: a host
serves it for any unmatched path at any depth, so a relative `assets/app.css` read from
`/p/typo.html` resolves to `/p/assets/app.css` and the lost reader gets an unstyled page with a
dead box. Two tests hold the line — one exempts exactly this file by name, the other asserts it
is absolute *everywhere*, because one relative path left in it would only surface for someone
who mistyped a URL two directories down.

### 10.5 Sections can be cited

The heading ids have been emitted since the first build and nothing revealed they existed.
Sending a colleague one section of a long page meant reading the HTML source. Every heading
now has a permalink, and pages with four or more sections get an outline.

Revealed on hover **and on `:focus`** — not `:focus-visible`. The narrower rule hides the
marker from focus that arrived any way other than a keypress, leaving an outline drawn around
something at `opacity: 0`.

### 10.6 `robots.txt`, and a sitemap when there is somewhere to point it

`robots.txt` always — with no rules in it, its job is still to answer a crawler's first request
with a 200 rather than the host's 404.

`sitemap.xml`, `og:url` and `rel=canonical` need an absolute origin, and this repository has no
git remote to derive one from. Rather than guess `<user>.github.io/<repo>` and emit a canonical
tag pointing at a page that may not exist, all three are **omitted** until `[site] url` is
filled in. One line in `glassbox.toml` turns them on; a test asserts both directions, because
testing only the empty case would let a hardcoded origin through and testing only the
configured case would miss the default this repository actually ships.

The 404 is excluded from the sitemap — a "no page at that address" result in a search engine is
a dead end presented as an answer.

---

## 11. Where I was wrong this pass

Three, and the first is the one worth reading.

### The disclosure guard passed while detecting nothing

I wrote `test_nothing_tracked_names_the_private_repository`, ran it, watched 35 tests go green,
and nearly moved on. Then I ran the pattern against the actual file it was written for:

```
ok    detect=True   D:\Stuff\...\<repo>\wiki\concepts\x.md      one separator
ok    detect=True   ../<repo>/wiki/tech/example.md              one separator
ok    detect=False  the <repo> repository is private            prose, not a path
ok    detect=False  content/pages/example.md                    the export, exempt

against the real artefact: 0 paths detected
```

**Four invented cases passed. All 172 real ones did not.** A Windows path inside JSON escapes
its separators, so the boundary in the real file is spelled with a doubled backslash — two
characters — and a single-separator class matches one. Making the separator repeatable fixes
it; the real artefact now yields 172.

A guard that reports green over the exact thing it exists to find is worse than no guard,
because it also removes the instinct to look. The lesson is not "write better regexes" — it is
that a test written from imagined inputs has been validated against imagination. This one is
now checked against the real file, and the check is in the scratchpad next to it.

**Postscript, from the commit that published this file.** The four sample paths above
originally spelled the private repository's name and two of its page paths in full. That was
fine while `AUDIT.md` sat untracked, and stopped being fine the moment a `git add -A` staged
it — which is exactly the one keystroke §12 warns about, arriving from the direction nobody
was watching. The guard caught its own documentation, which is the strongest evidence it
works that this audit can offer. Nothing was carved out for it: the samples are now written
with a placeholder, and every claim above survives the substitution intact, because the
finding was always about separators and never about which pages.

### I nearly widened a CSS rule to fix a stopwatch

The harness reported the heading anchor at `opacity: 0` while focused. I changed
`:focus-visible` to `:focus` and it still failed. The rule was working: I was reading
`getComputedStyle` on the same tick as `.focus()`, which returns the animated value at t=0 —
the *before* state of a 100 ms transition.

The `:focus` change stands, for the reason written in the CSS, but it is a widening and not a
bug fix, and it would have been recorded as a fix if I had not gone back.

### I mistook a race for a broken navigation

`waitForLoadState('load')` resolved against the page already loaded and read the old URL back,
so submitting the header form looked like it did nothing. It worked. `waitForURL` waits for the
thing being asserted.

### And one from the last pass, restated

Six harness bugs are catalogued in §6. The count is now nine across two passes, against nine
product defects this pass. That ratio is not a coincidence and it is not embarrassing: checking
tools get less scrutiny than shipped code precisely because their output is what scrutiny looks
like.

---

## 12. What was checked and found sound

Not everything was broken. Recording the clean results matters as much as the findings —
otherwise this reads as a list of what I happened to look at.

| check | result |
| --- | --- |
| Rebuild is byte-identical | 244 files, **0 changed** on a second run |
| Bundle matches its manifest | 235 files hashed, verified at load |
| Session pages in the bundle | 0 — C2 holds, checked in three places |
| Dangling links in `index.json` | 0 — every `links:` target is published |
| Orphan pages | 0 — no page is unreachable and unreaching |
| Pages with no gist | 0 of 232 |
| Non-slug stems | 0 — no stem can break a URL |
| Secret sweep over the wiki | 0 matches, hard classes |
| Outbound network requests over `file://` | 0, both themes, both widths |
| Sideways overflow with the suggestion list open | none at 1280 or 390 |
| Contrast of every element added this pass | 5.47:1 – 17.76:1, both themes |
| Gate violations | 0 (64 warnings, all reviewed sensitive sources) |
| Search index against budget | 157.1 KB of 250 |
| Landing against budget | 4.2 KB of 120 |

---

## 13. Numbers, after

```
pages          232 published of 240   (concept 87 · tech 57 · decision 38 · pattern 35 · project 15)
confidence     189 high · 43 medium   (7 low and 1 session page withheld)
repositories   15 · links 1,303
documents      244 files — 233 HTML, +404, robots.txt, 2 assets, index

search index   157.1 KB gzipped (budget 250)
landing          4.2 KB gzipped (budget 120)
404              1.8 KB gzipped
app.js           9.1 KB gzipped   (8.4 before — header search, BASE, attribute escaping)
app.css          9.2 KB gzipped   (7.1 before — header search, outline, anchors, print)

gaps           134 published pages without aliases · 39 private-page links over 32 pages
               226 gaps written into the pages themselves

tests          35 pytest (glass-box, +12 this pass) · 71 pytest (second-brain)
               41/41 jsdom · 24/24 header-search Chromium · contrast probe clean
determinism    0 of 244 files differ on rebuild
```

---

## 14. Left open

**`[site] url` is empty.** `sitemap.xml`, `og:url` and `rel=canonical` are switched off until
it is filled in. This is deliberate — there is no remote to derive an origin from and a guessed
canonical is worse than none — but it means three of the discoverability wins are dormant. One
line in `glassbox.toml` and a rebuild turns them on.

**No `og:image`.** Reasoned above. A link previews with title and description but no thumbnail.

**The browser harnesses still live outside the repository.** Unchanged from pass one and still
unresolved: they need `playwright` and `jsdom`, and this project's zero-dependency,
no-build-step posture is a claim it makes on its own pages. Committing them weakens that claim;
leaving them out means the contrast probe, the header-search suite and the disclosure
guard-check are not reproducible by a reader. Two of this pass's findings — the placeholder
contrast and the guard that detected nothing — came from those harnesses and could not have
come from pytest.

**Neither repository is committed.** Both have substantial uncommitted changes. No commit,
branch or push has been made, because none was asked for.
