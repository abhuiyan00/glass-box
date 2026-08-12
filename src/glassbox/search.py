"""The search index, precomputed here so the browser never calls anything.

The site runs the same retrieval as the private tool it is a window onto. That claim is only
true if the parameters are shipped rather than retyped, so `content/scorer.json` carries the
field weights, the relevance floor, the hop share and the stopword list, and this module
reads them. Nothing in this file or in `assets/app.js` may invent a constant — a number
restated across a language boundary is a config file that lies.

What this module *does* own is the corpus arithmetic: term frequencies per field, document
frequencies, and the idf table. Those are measured over the **published set only**, which is
why a rare word can rank differently here than in the private tool. That is a real
difference and the site says so rather than hiding it: word rarity is relative to the pages a
visitor can actually open, not the ones they cannot.

Emitted as JavaScript, not JSON. `file://` blocks cross-origin `fetch`, so a downloaded copy
of this site would have a dead search box if the index arrived as data to be fetched. A
`<script src>` assignment works from a local file, a static host and a CDN alike.

Terms travel as integer ids into `vocab`, never as words. That is the one thing in this file
worth reading twice, because it looks like premature optimisation and is not. Spelling each
term out wherever it occurs cost 247 KB gzipped against a 250 KB budget at 232 pages — 3 KB
of headroom, which is not a margin, it is a cliff one page away. 51,488 (document, term)
pairs draw on 7,361 distinct words, so the words were being written an average of seven times
each and 74% of the counts were the literal digit 1.

The alternative was raising the budget, and it was the wrong one twice over. The budget is
the promise that a visitor on a phone gets a working search box, and moving it to fit is how
that promise becomes decorative. It would also have bought one release: the same cliff
returns at 240 pages.

**Nothing here changes what the search returns.** The ids are a spelling of the same numbers.
An encoding that quietly reranked results would break the claim this whole project rests on,
so `tests/test_build.py` scores the corpus both ways and asserts the orderings are identical.
"""

import json
import math
import re
from collections import Counter

# Strip fenced blocks and inline code before counting body terms: a quoted source line is
# evidence, not vocabulary, and letting a code block vote skews idf toward whatever language
# a page happens to quote.
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
CODE = re.compile(r"`[^`\n]*`")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
HEADER_BAR = re.compile(r"^[|:\-\s]+$", re.M)


def tokenizer(scorer):
    """A `terms(text)` function built from the shipped pattern, never a literal here."""
    rx = re.compile(scorer.get("token_pattern", "[a-z0-9]+"))
    stop = set(scorer.get("stop", []))
    floor = int(scorer.get("min_term_length", 2))
    return lambda text: [w for w in rx.findall(text.lower())
                         if len(w) >= floor and w not in stop]


def plain(text):
    """Body prose: wikilinks flattened to their words, code and table rules removed."""
    text = FENCE.sub(" ", text)
    text = CODE.sub(" ", text)
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = HEADER_BAR.sub(" ", text)
    return text.replace("**", " ").replace("#", " ")


def fields(page, terms):
    """The six weighted fields, as term lists. Same names and shape as the private tool."""
    return {
        "stem": terms(page["stem"].replace("-", " ")),
        "title": terms(page.get("title") or page["stem"]),
        "aliases": terms(" ".join(page.get("aliases") or [])),
        "gist": terms(page.get("gist") or ""),
        "tags": terms(" ".join(page.get("tags") or [])),
        "sources": terms(" ".join(page.get("sources") or []).replace("/", " ")),
    }


def gaps(sorted_ids):
    """A sorted id list as first-value-then-differences. Reversed by a running sum.

    Vocabulary ids run to five digits; the gaps between the ids one page uses are mostly one
    or two. Same information, smaller alphabet, far more repetition for gzip to find.
    """
    out, previous = [], 0
    for value in sorted_ids:
        out.append(value - previous)
        previous = value
    return out


def build(bundle):
    """The whole client index as one dict. Deterministic: sorted everywhere it can be."""
    terms = tokenizer(bundle.scorer)
    raw, df = [], Counter()

    for page in sorted(bundle.pages, key=lambda p: p["stem"]):
        tf = Counter(terms(plain(bundle.bodies[page["stem"]])))
        df.update(set(tf))
        raw.append((page, tf, fields(page, terms)))

    n = len(raw) or 1
    default_idf = round(math.log(n + 1), 4)

    # One vocabulary for the corpus, sorted so the ids are a function of the content and not
    # of iteration order — two builds of the same bundle must give the same file.
    #
    # Field terms are in it even when no body contains them. A title or an alias can carry a
    # word the prose never uses, and such a word scored before this change: it had no document
    # frequency, so `idf()` fell through to `idf_default`. Admitting only body terms here would
    # have been tidier and would have deleted that path, which is a reranking dressed as an
    # encoding. It keeps its id and it keeps `idf_default` as its weight.
    # A plain set union, not `Counter | Counter`: that operator keeps the larger count and
    # drops anything at zero, which is exactly the field-only terms this line exists to keep.
    vocab = sorted(set(df) | {w for _, _, flds in raw
                              for words in flds.values() for w in words})
    ids = {word: i for i, word in enumerate(vocab)}

    docs = []
    for page, tf, flds in raw:
        docs.append({
            "s": page["stem"],
            "k": page["type"],
            "t": page.get("title") or page["stem"],
            "g": page.get("gist") or "",
            "r": (page.get("repos") or [None])[0],
            # Deduplicated per field, which the scorer already did implicitly: it asked
            # `indexOf(term) !== -1` and counted one hit however many times the word occurred.
            "f": {name: gaps(sorted({ids[w] for w in words}))
                  for name, words in sorted(flds.items())},
            # Term ids and their counts as two parallel arrays rather than one object.
            # `{"1234":3}` spends ten bytes to say what `[1234]` and `[3]` say in six, and
            # the ids are sorted, so `gaps` turns them into small numbers that repeat — which
            # is the shape gzip is actually good at. This pair is 46 KB where the object was
            # 110. The client rebuilds a lookup once, at load, not per query.
            "ti": gaps(sorted(ids[w] for w in tf)),
            "tc": [c for _, c in sorted(tf.items(), key=lambda kv: ids[kv[0]])],
            "n": sum(tf.values()),
            "l": sorted(page.get("links") or []),
        })

    return {
        "generated": bundle.stats.get("generated"),
        "field": bundle.scorer["field"],
        "floor": bundle.scorer["floor"],
        "hop": bundle.scorer["hop"],
        "stop": sorted(bundle.scorer.get("stop", [])),
        "token": bundle.scorer.get("token_pattern", "[a-z0-9]+"),
        "minlen": int(bundle.scorer.get("min_term_length", 2)),
        "vocab": vocab,
        # Parallel to `vocab`, by position. A term with no document frequency is one that
        # only a title, alias or tag carries; it takes `idf_default`, which is what the
        # lookup gave it when the table was keyed by word.
        "idf": [round(math.log(n / (1 + df[w])) + 0.5, 4) if df[w] else default_idf
                for w in vocab],
        "idf_default": default_idf,
        "docs": docs,
        "questions": list(bundle.questions),
    }


def as_script(data):
    """`window.GLASSBOX = {...}` — loadable with <script src> from a local file."""
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return ("/* GENERATED by glass-box build.py from content/. DO NOT EDIT.\n"
            "   Loaded with <script src> rather than fetch() so the search box still works\n"
            "   when this site is opened from disk. */\n"
            f"window.GLASSBOX={blob};\n")
