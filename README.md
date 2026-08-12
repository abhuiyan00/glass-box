<div align="center">

# GLASS BOX

### A knowledge base that shows its own seams

*Every number on the site is computed. Every page names the files it came from.*

</div>

```
╔══════════════════════════════════════════════════════════════════════════╗
║  SOURCE          a private wiki over verified repositories               ║
║  PUBLISHED       gated pages only; live counts and gaps are receipts     ║
║  BUILD           Python standard library · no dependencies · no npm      ║
║  SEARCH          runs in the browser · no server, no model, no key       ║
║  OUTPUT          flat HTML · relative links · opens from a file manager  ║
║  DEPLOY          GitHub Pages, branch → /docs. No pipeline.              ║
╚══════════════════════════════════════════════════════════════════════════╝
```

> **Start here.** This repository is the *public window*. The knowledge itself lives in a
> private repository that is not on this machine when the site builds, so this project
> cannot publish a page it has never been handed. What crosses between them is
> [`content/`](content) — a bundle of pages that already passed a publication gate, plus every
> figure the site is allowed to print.

**On pages that do not cross.** Low-confidence pages are held when evidence is weak or a
question was asked and never answered — publishing one would be shipping the absence of a
fact in the shape of one. Session records are categorically unpublishable. Every withheld
page is named and counted on [`/gaps.html`](docs/gaps.html), because a mostly public corpus
that stays silent about the rest tells you less than one that shows you the edge.

---

## What the site is for

Someone lands on it knowing nothing about the author. Within a few seconds they should be
able to **ask a real question and get pages that answer it** — not a wall of tiles, not a
force-directed graph, not a résumé.

So the front page is a search box and one sentence. Everything else is one click away:

![The front page of the built site: a search box, six suggested questions, and counts of the
281 pages behind it](screenshots/site-ask.png)

![A project page for Labour Fraud Analysis, showing the confidence and bi-temporal header,
the section index and the opening account](screenshots/site-project-page.png)

Both are captures of `docs/` as [`build.py`](build.py) renders it — the same files GitHub
Pages serves.


| Page | Answers |
|---|---|
| `/` | *Ask it something.* Type a question, get up to five pages, each with a one-line answer. Suggestions appear as you type; the query lives in the URL, so a result is a link. |
| `/browse.html` | Everything there is, grouped by kind, filterable without a page load. |
| `/map.html` | One ring per source repository. Every position means something; ring and page-kind filters are keyboard-operable toggle buttons. |
| `/p/<name>.html` | One page: the short answer, the full account, the files it was written from, the pages it links to. |
| `/receipts.html` | Every figure on the site, what it counts, and **how it is counted**. |
| `/gaps.html` | What it cannot answer, counted the same way as everything else. |
| `/how.html` | The pipeline, and why a search rather than a chatbot. |

**The receipts page used to be the front page.** It was eight numbered rows of retrieval
metrics, and it was answering a question — *should I believe this?* — that nobody asks before
they have read anything. It moved. The claim comes first; the evidence is one click behind it,
where a sceptical reader goes looking anyway.

---

## The arc at a glance

| Stage | What happens | Where |
|---|---|---|
| 1 | A repository is read and the author is interviewed about what the code cannot say | private |
| 2 | A page is marked publishable **by a person** — never automatically | private |
| 3 | A gate checks type, confidence, status and sensitive sources, then exports a bundle | private |
| 4 | The bundle is scanned for anything secret-shaped before a byte is written | private |
| 5 | [`content/`](content) lands here, hashed, with a do-not-edit banner on every file | **this repo** |
| 6 | [`build.py`](build.py) verifies the hashes and renders [`docs/`](docs) | **this repo** |
| 7 | GitHub Pages serves `docs/`. No action, no runner, no secret | **this repo** |

---

## Build it

```bash
python build.py            # render into docs/
python build.py --check    # render to a temp dir, report, write nothing
python build.py --open     # render, then open it
python build.py --out DIR  # render an isolated preview/test tree
```

Python 3.11 or newer. **That is the whole toolchain** — no `pip install`, no lockfile, no
Node, no bundler, no CSS framework, no webfont. If a dependency can be replaced by code that
fits in a file you can read, it is.

To refresh the content, run `python brain.py export` in the private repository. It writes
straight into `content/` here. Nothing in this repository ever reaches back the other way.

---

## Layout

```
glass-box/
├── build.py                 the only entry point
├── glassbox.toml            identity, output path, size budgets — nothing measurable
├── content/                 GENERATED by the private repo. Do not edit.
│   ├── MANIFEST.json        sha256 of every other file; the build verifies it
│   ├── index.json           one record per page, without the prose
│   ├── stats.json           every figure the site may print
│   ├── scorer.json          field weights, floor, hop share, stopwords
│   └── pages/<name>.md      the prose, one file per page
├── src/glassbox/
│   ├── content.py           load the bundle; refuse a tampered one
│   ├── markdown.py          the closed set of constructs the wiki uses
│   ├── search.py            the browser index, built from scorer.json
│   ├── shell.py             one head, one header, one footer
│   ├── views.py             ask · browse
│   ├── mapview.py           deterministic repository rings and link graph
│   ├── receipts.py          receipts · gaps · how it works
│   └── pages.py             one article per page
├── assets/                  app.css · app.js — hand-written, no framework
├── tests/                   pytest; the build is a test fixture
└── docs/                    GENERATED output. GitHub Pages serves this.
```

---

## Four decisions worth knowing about

**The site opens from a file, not just a server.** Links are relative and the search index
arrives via `<script src>` rather than `fetch`, because `file://` blocks cross-origin fetch and
a downloaded copy with a dead search box is not a copy. The cost is `.html` on the end of every
URL — a directory link only resolves to its index when a server says so, and there is no server
when someone opens the folder. Working file beats pretty URL.

**The search is the same search the author uses privately.** Not a reimplementation — the
field weights, relevance floor, hop share and stopword list are *shipped as data* in
`scorer.json` and read at build time. A constant retyped across a language boundary is a
config file that lies, and the site would quietly start answering differently from the tool it
claims to be a window onto.

**A refusal is a designed answer.** Ask it about Kubernetes and it says nothing here covers
that, then offers what it does cover. Returning the nearest page and letting you assume it is
an answer is the failure this whole system exists to avoid.

**The content is generated and the build enforces that.** Every file in `content/` opens with
a do-not-edit banner, and `MANIFEST.json` carries a sha256 for each one. A banner is a note;
the hash check is the rule. Edit a page here and the build stops with the filename — because a
page that has drifted from the private source it claims to copy is worse than no page.

---

## What it deliberately does not do

- **No prose answers.** A summary you cannot check is worth less than a page you can. If a
  language model is ever added it will cite the page behind every claim or it will not ship.
- **No *force-directed* graph.** This line used to read "no graph visualisation", and the
  reason it gave was right about the wrong thing: a hairball conveys less in five minutes
  than one honest number does in five seconds, because a node's position in a physics
  simulation means nothing and moves on every run. `/map.html` is the other kind. Every ring
  is a repository, distance from the centre is page count, the coordinates are `sorted()` and
  arithmetic rather than a solver, and two builds of the same bundle draw it identically. The
  objection was to positions that mean nothing, not to pictures.
- **No analytics, no cookies, no fonts, no outbound requests of any kind.** Open the network
  tab; it stays empty.
- **No claim that the search is semantic.** The suggestion list is the same lexical scorer
  plus one hop along the author's own links. There are no embeddings, because there is no
  model and no network call to reach one — see `/how.html`.
- **No claim that the pages are *correct*.** The figures measure coverage, retrieval and
  process. Whether a source was right is a separate question, and the pages carry their own
  confidence levels and name their own gaps.

---

## Licence

Code in `build.py`, `src/` and `assets/` is MIT — see [LICENSE](LICENSE).
The written content under `content/` and `docs/` is the author's own work and is **not** MIT;
see [NOTICE](NOTICE) for the line between them.
