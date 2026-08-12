"""The map: one ring per source repository, drawn at build time.

This project shipped without a graph on purpose, and the reason is in the README: every
note-taking app has a force-directed hairball, every interviewer has seen one, and it says
less in five minutes than one honest number says in five seconds. That objection is right
about hairballs. It is not an argument against *structure*, and the difference is the whole
design of this page.

A force layout puts a node where a physics simulation settles. Nothing is on the left because
left means anything; run it again and the picture is different. Here a node's position is a
fact: **which ring it is on is which repository it came from, and rings are ordered outward by
how many pages rest on them.** Radius is rank, not count — the gap between ring 8 and ring 9 is
one place in the order, not four pages — because a count-proportional radius would put the
thinnest repositories on top of each other at the centre and waste the whole outer third.
Nothing moves, nothing animates, nothing is simulated, and two builds of the same bundle
produce identical coordinates — the layout is `sorted()` and arithmetic. A reader who learns
the one rule can then read every position on the screen, which is the thing a hairball can
never offer.

The ring list is derived, never written. Add another repository to the wiki, export, and a
new ring appears with its own count; there is no list in this file to edit and no place to
forget. Same for the legend, which is built from the types actually present.

Edges are the author's own wikilinks, drawn only when both ends are published. They are the
faint layer, deliberately: they are the least legible thing here and the most tempting to
make loud.
"""

import math

from .shell import document, esc

W, H = 760, 760
CX, CY = W / 2, H / 2
# Measured, not guessed. The SVG lays out around 660px wide on a desktop, so a viewBox unit is
# about 0.87px. At 74..336 the fifteen rings sat 16.4px apart carrying 9.1px nodes — 7px of
# daylight, which is why the first screenshot read as a speckled disc rather than as rings.
# Widening the band to 46..354 buys 19px spacing and 10px of daylight, and the innermost ring
# holds six pages, so tightening its radius costs nothing.
INNER, OUTER = 46, 354
# The nodes are small because there are a couple of hundred of them and the ring, not the
# node, is the thing being read. Anything bigger and adjacent pages on a crowded ring touch.
R_NODE = 5.2


def assign(bundle):
    """(rings, home) — rings ascending by page count, and every page's ring.

    A page may cite several repositories; a pattern confirmed across nine of them cites all
    nine. It is drawn once, on the ring of the first repository it names in sorted order, and
    the page says so. Drawing it nine times would make the busiest patterns look like nine
    separate ideas, and picking "the most important repository" would be inventing a fact the
    wiki does not record.
    """
    counts = {}
    for page in bundle.pages:
        for repo in page.get("repos") or []:
            counts[repo] = counts.get(repo, 0) + 1
    order = sorted(counts, key=lambda r: (counts[r], r))
    home = {}
    for page in bundle.pages:
        repos = sorted(page.get("repos") or [])
        home[page["stem"]] = repos[0] if repos else None
    return order, home


def geometry(bundle):
    """{stem: (x, y)} plus the ring radii. Pure arithmetic on sorted input."""
    order, home = assign(bundle)
    members = {repo: [] for repo in order}
    for page in sorted(bundle.pages, key=lambda p: p["stem"]):
        if home[page["stem"]] in members:
            members[home[page["stem"]]].append(page)

    radii, at = {}, {}
    span = max(len(order) - 1, 1)
    for i, repo in enumerate(order):
        r = INNER + (OUTER - INNER) * (i / span)
        radii[repo] = r
        rows = members[repo]
        # A quarter turn per ring, so pages on neighbouring rings do not line up into
        # spokes that read as a relationship they do not have.
        phase = (i * math.pi / 2) / max(len(order), 1) + i * 0.7
        for j, page in enumerate(rows):
            a = phase + 2 * math.pi * j / max(len(rows), 1)
            at[page["stem"]] = (CX + r * math.cos(a), CY + r * math.sin(a))
    return order, radii, members, at


def svg(bundle):
    order, radii, members, at = geometry(bundle)
    kind_of = {p["stem"]: p["type"] for p in bundle.pages}
    title_of = {p["stem"]: (p.get("title") or p["stem"]) for p in bundle.pages}

    circles = "".join(
        f'<circle class="ring-o" cx="{CX:.0f}" cy="{CY:.0f}" r="{radii[repo]:.1f}" '
        f'data-ring="{esc(repo)}"/>'
        for repo in order)

    # Every label was placed at the same angle, which put all fifteen on one radius and
    # stacked them into an unreadable column down the middle of the picture — a defect only
    # visible by looking at it, since the markup was correct and every number was there.
    # Fanning them over the whole circle keeps each one on its own ring and next to nothing
    # else; a partial fan still bunched the inner numbers, where the arc is shortest.
    labels = []
    for i, repo in enumerate(order):
        a = -math.pi / 2 + i * (2 * math.pi / max(len(order), 1))
        r = radii[repo]
        labels.append(
            f'<text class="ring-n" x="{CX + r * math.cos(a):.1f}" '
            f'y="{CY + r * math.sin(a):.1f}">{i + 1:02d}</text>')
    labels = "".join(labels)

    # Deduplicated: the wiki's links are undirected, so a-b and b-a are one line.
    seen, edges = set(), []
    for page in sorted(bundle.pages, key=lambda p: p["stem"]):
        a = page["stem"]
        for b in sorted(page.get("links") or []):
            key = (a, b) if a < b else (b, a)
            if key in seen or a not in at or b not in at:
                continue
            seen.add(key)
            (x1, y1), (x2, y2) = at[a], at[b]
            edges.append(f'<line class="edge" x1="{x1:.1f}" y1="{y1:.1f}" '
                         f'x2="{x2:.1f}" y2="{y2:.1f}" data-a="{esc(a)}" data-b="{esc(b)}"/>')

    nodes = []
    for repo in order:
        for page in members[repo]:
            stem = page["stem"]
            x, y = at[stem]
            nodes.append(
                f'<a class="node k-{esc(kind_of[stem])}" href="p/{esc(stem)}.html" '
                f'data-stem="{esc(stem)}" data-ring="{esc(repo)}" '
                f'data-kind="{esc(kind_of[stem])}">'
                f'<title>{esc(title_of[stem])} — {esc(kind_of[stem])}</title>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{R_NODE}"/></a>')

    return (f'<svg class="map-svg" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{len(bundle.pages)} pages arranged on {len(order)} rings, '
            f'one ring per source repository">'
            f'<g class="rings">{circles}</g><g class="edges">{"".join(edges)}</g>'
            f'<g class="labels">{labels}</g><g class="nodes">{"".join(nodes)}</g></svg>'), order, members


def page(bundle, cfg):
    markup, order, members = svg(bundle)

    rows = []
    for i, repo in enumerate(order):
        project = bundle.project_for(repo)
        name = project.get("title") if project else repo
        link = (f'<a href="p/{esc(project["stem"])}.html">{esc(name)}</a>'
                if project else esc(name))
        rows.append(
            f'<li class="ring-r" data-ring="{esc(repo)}">'
            f'<button type="button" class="ring-i" data-map-ring="{esc(repo)}" '
            f'aria-pressed="false" aria-label="Filter map to {esc(name)}">'
            f'{i + 1:02d}</button>'
            f'<span class="ring-t">{link}</span>'
            f'<span class="ring-c">{len(members[repo])}</span></li>')

    kinds = "".join(
        f'<button type="button" class="lg lg-{esc(k)}" data-map-kind="{esc(k)}" '
        f'aria-pressed="false">'
        f'<span class="lg-d"></span>{esc(k)} <span class="lg-n">{len(v)}</span></button>'
        for k, v in bundle.by_type().items())

    unplaced = [p for p in bundle.pages if not (p.get("repos") or [])]
    unplaced_note = (
        f'<p class="band-b">{len(unplaced)} pages name no repository and are not drawn.</p>'
        if unplaced else "")

    body = f"""
<section class="page-head">
  <h1>The map</h1>
  <p class="lede">One ring per source repository, ordered outward by how many pages rest on
    it. Every position on this picture means something: nothing is placed by a simulation,
    and two builds of the same content draw it identically.</p>
</section>

<section class="map">
  <div class="map-c">
    {markup}
    <p class="map-r" data-map-readout aria-live="polite">Hover or focus a page to name it.
      Click to open it.</p>
  </div>
  <aside class="map-s">
    <div class="map-h"><span>Ring</span><span>Pages</span></div>
    <ul class="rings-l" data-map-rings>{"".join(rows)}</ul>
    <div class="lgs">{kinds}</div>
    <p class="map-n">The list is built from the <code>sources:</code> field of the pages
      themselves. A repository appears here the moment a page cites it and disappears when
      none does — there is no list in the code to keep in step.</p>
    {unplaced_note}
    <p class="map-n">A page citing several repositories is drawn once, on the ring of the
      first it names alphabetically. Lines are the author's own links between pages, drawn
      only where both ends are public.</p>
  </aside>
</section>
"""
    return document("Map", f"{len(bundle.pages)} published pages on {len(order)} rings, "
                           f"one per source repository.",
                    body, current="map", depth=0, cfg=cfg, stats=bundle.stats,
                    path="map.html")
