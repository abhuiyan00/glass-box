"""Glass Box — the public reading surface over a private second brain.

Six modules, one job each, no dependencies:

    content.py   load the exported bundle and refuse to build from a tampered one
    markdown.py  the closed set of constructs the wiki actually uses
    search.py    the client-side index, built from parameters the bundle carries
    shell.py     one <head>, one header, one footer, for every document
    views.py     the five standing documents: ask, browse, receipts, gaps, how
    pages.py     one article per page

**Nothing here reads a wiki.** The private repository is not on this machine when the site
builds; `content/` is the whole world. That is the point of the split — this project cannot
leak a page it has never seen.

Two rules shape every line of output:

  * **It opens by double-clicking.** Flat `.html` files, relative links, data loaded by
    `<script src>` rather than `fetch`. `file://` blocks cross-origin fetch, so an index
    delivered as JSON would make the search box dead on a downloaded copy.
  * **No number is written by hand.** Every figure comes from `content/stats.json`, and a
    figure the brain could not measure arrives as `null` and renders as a visible gap.
"""

__version__ = "1.0.0"
