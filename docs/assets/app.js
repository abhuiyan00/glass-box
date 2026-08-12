/* glass-box runtime. Three jobs: theme, search, browse filter.
   No dependencies, no network, no analytics. The index arrives as window.GLASSBOX from a
   <script src> because file:// blocks fetch — a downloaded copy of this site has a working
   search box, and that is not an accident.

   Every scoring constant below is read from the index, never written here. The site claims
   to run the same retrieval as the author's private tool; a weight retyped in JavaScript is
   how that claim quietly stops being true. */
'use strict';

var IDX = window.GLASSBOX || null;
var root = document.documentElement;

/* ── theme ─────────────────────────────────────────────────────────────────
   The saved theme is applied by an inline script in <head>, before first paint. All that is
   left here is the toggle. Which word the button shows is CSS's job, not this file's — see
   shell.py THEME_TOGGLE for why. */
function setTheme(t) {
  root.setAttribute('data-theme', t);
  try { localStorage.setItem('gb-theme', t); } catch (e) { /* private mode */ }
}
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-theme-toggle]');
  if (!b) return;
  var dark = root.getAttribute('data-theme')
    ? root.getAttribute('data-theme') === 'dark'
    : matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(dark ? 'light' : 'dark');
});

/* ── scoring ─────────────────────────────────────────────────────────────
   Mirrors the private tool exactly. The coverage ratio is squared and the floor is
   absolute; that pair is what stops a question about a Kubernetes ingress controller
   reaching a page about a data-protection controller on the word "controller" alone.

   Terms are integer ids into IDX.vocab, never words — see the note in src/glassbox/search.py
   for why. A query word the corpus has never seen gets id -1: it matches nothing, and it
   still counts toward q.length, so it still drags the coverage ratio down. That is the whole
   point of asking about Kubernetes and being told no. */
var VOCAB = null;

/* Undo the gap coding: [3,1,1,7] -> [3,4,5,12]. In place, because these arrays are the
   index and nothing else reads them in the coded form. */
function ungap(a) {
  for (var i = 1; i < a.length; i++) a[i] += a[i - 1];
  return a;
}

/* One pass over the index at load: word -> id, and per document a Set of the field ids and a
   Map from term id to body count. Doing this per query instead would repeat ~50,000 additions
   on every keystroke, and the typeahead fires on every keystroke. */
function hydrate() {
  if (VOCAB) return;
  VOCAB = new Map();
  for (var i = 0; i < IDX.vocab.length; i++) VOCAB.set(IDX.vocab[i], i);
  for (i = 0; i < IDX.docs.length; i++) {
    var d = IDX.docs[i], name;
    for (name in d.f) d.f[name] = new Set(ungap(d.f[name]));
    var ti = ungap(d.ti);
    d.tf = new Map();
    for (var j = 0; j < ti.length; j++) d.tf.set(ti[j], d.tc[j]);
  }
}

function vocabId(word) {
  hydrate();
  var id = VOCAB.get(word);
  return id === undefined ? -1 : id;
}

/* Query words, as ids. `words()` returns the same list spelled as strings — the typeahead
   needs those, the scorer does not. */
function words(s) {
  if (!IDX) return [];
  var rx = new RegExp(IDX.token, 'g');
  var stop = IDX._stopSet || (IDX._stopSet = new Set(IDX.stop));
  var found = String(s).toLowerCase().match(rx) || [];
  var out = [];
  for (var i = 0; i < found.length; i++) {
    if (found[i].length >= IDX.minlen && !stop.has(found[i])) out.push(found[i]);
  }
  return out;
}

function terms(s) {
  return words(s).map(vocabId);
}

function search(query, top) {
  if (!IDX) return null;
  var qw = words(query), q = qw.map(vocabId);
  if (!q.length) return { rows: [], considered: 0, q: [], qw: [] };
  var F = IDX.field;
  var idf = function (t) { return t < 0 ? IDX.idf_default : IDX.idf[t]; };

  var direct = [];
  for (var i = 0; i < IDX.docs.length; i++) {
    var d = IDX.docs[i], total = 0, covered = new Set(), name, j;
    for (name in d.f) {
      var ids = d.f[name], hits = 0, sum = 0;
      for (j = 0; j < q.length; j++) {
        if (q[j] >= 0 && ids.has(q[j])) { hits++; sum += idf(q[j]); covered.add(q[j]); }
      }
      if (hits) total += F[name] * hits * sum / q.length;
    }
    var body = 0;
    for (j = 0; j < q.length; j++) {
      var c = q[j] < 0 ? 0 : d.tf.get(q[j]);
      if (c) { body += idf(q[j]) * (1 + Math.log(c)); covered.add(q[j]); }
    }
    total += F.body * body / (1 + Math.log(1 + d.n));
    if (total > 0) direct.push([d.s, total * Math.pow(covered.size / q.length, 2)]);
  }

  var kept = direct.filter(function (p) { return p[1] >= IDX.floor; });
  var byStem = new Map(IDX.docs.map(function (d) { return [d.s, d]; }));
  var out = new Map(kept.map(function (p) { return [p[0], { v: p[1], how: 'match' }]; }));
  /* One hop along the author's own links. An edge between two pages is a human judgement
     that they belong together, and word matching cannot see it. */
  kept.forEach(function (p) {
    var d = byStem.get(p[0]);
    (d ? d.l : []).forEach(function (nb) {
      if (!out.has(nb) && byStem.has(nb)) out.set(nb, { v: p[1] * IDX.hop, how: 'linked' });
    });
  });

  var rows = Array.from(out).sort(function (a, b) {
    return b[1].v - a[1].v || a[0].localeCompare(b[0]);
  }).slice(0, top || 5).map(function (pair) {
    var d = byStem.get(pair[0]);
    return { stem: pair[0], score: pair[1].v, how: pair[1].how, k: d.k, t: d.t, g: d.g, r: d.r };
  });
  return { rows: rows, considered: direct.length, q: q, qw: qw };
}

/* ── rendering ─────────────────────────────────────────────────────────────
   Where every link on this page starts from. The runtime used to write `p/stem.html` as a
   literal, which was correct exactly as long as results only ever appeared on the landing
   page. They now appear from the header box on all 232 article pages, where that path
   resolves to `p/p/stem.html`. The shell writes the depth onto <body> because it is the only
   thing that knows it. */
var BASE = (document.body && document.body.getAttribute('data-base')) || '';

/* Escapes for *attribute* context, not only text.
   The old version set `textContent` and read `innerHTML` back, which is the serialiser's
   text-node rule: it escapes `&`, `<` and `>` and leaves quotes alone — correct between tags
   and wrong inside them, and most uses here are inside them. One `"` in a page title or an
   eval question would have closed `data-seed="` early and let the rest of the string be
   parsed as markup. No such string exists in the corpus today, which is the whole reason it
   would have shipped. */
function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function cardHTML(r) {
  return '<a class="card" href="' + BASE + 'p/' + esc(r.stem) + '.html">' +
    '<span class="kind k-' + esc(r.k) + '">' + esc(r.k) + '</span>' +
    '<span class="card-t">' + esc(r.t) + '</span>' +
    '<span class="card-g">' + esc(r.g) + '</span>' +
    (r.how === 'linked'
      ? '<span class="hop">reached by a link from a match, not by your words</span>'
      : (r.r ? '<span class="from">' + esc(r.r) + '</span>' : '')) +
    '</a>';
}

/* What a refusal offers instead. This used to be `IDX.docs.slice(0, 3)`, which is the first
   three stems in alphabetical order — at 60 pages that looked like a sample and at 232 it
   reads as a non-answer: somebody asking about Kubernetes was told the site does cover
   "Ackermann and Primitive Recursion". Still generated, still never written into the page,
   but now one page per kind, each the best-connected page of its kind, so the three lines
   say what sort of thing lives here rather than what sorts alphabetically first. */
function examples(n) {
  if (IDX._eg) return IDX._eg.slice(0, n);
  var best = {};
  for (var i = 0; i < IDX.docs.length; i++) {
    var d = IDX.docs[i];
    if (!best[d.k] || d.l.length > best[d.k].l.length) best[d.k] = d;
  }
  var order = ['project', 'decision', 'pattern', 'concept', 'tech'];
  IDX._eg = order.filter(function (k) { return best[k]; }).map(function (k) { return best[k]; });
  return IDX._eg.slice(0, n);
}

/* A refusal is a recovery surface, not a dead end. Everything it offers is generated from
   the index — never written into the page — so it can never be empty and never invented. */
function refusalHTML(query, res) {
  var near = examples(3);
  var seed = IDX.questions && IDX.questions.length ? IDX.questions[0] : null;
  var why = res.qw.length
    ? 'None of <code>' + res.qw.map(esc).join('</code>, <code>') +
      '</code> clears the relevance floor on any page here.'
    : 'That reduced to no searchable words.';
  return '<div class="refusal"><h3>Nothing here answers that.</h3>' +
    '<p>' + why + ' Rather than return the closest thing and let you assume it is an ' +
    'answer, it stops.</p><ul>' +
    near.map(function (d) {
      return '<li><span class="tag">it does cover</span><a href="' + BASE + 'p/' + esc(d.s) +
        '.html">' + esc(d.t) + '</a>' + (d.g ? ' — ' + esc(d.g) : '') + '</li>';
    }).join('') +
    (seed ? '<li><span class="tag">try</span><button type="button" data-seed="' +
      esc(seed) + '">' + esc(seed) + '</button></li>' : '') +
    '<li><span class="tag">or</span> <a href="' + BASE + 'gaps.html">see what it knows it ' +
    'cannot answer</a></li></ul></div>';
}

/* ── typeahead ─────────────────────────────────────────────────────────────
   The suggestion list under the box, and the one place on this site where it would be easy
   to overclaim. It is not embeddings and it is not a model — there is no network call to
   make one with. Three sources, in this order, and the site says which is which:

     1. Pages, ranked by the same scorer the Search button runs. Typing half a question
        already shows the pages that answer it, so the dropdown is the result, not a guess
        at what you meant to type. This is the part that behaves like a search engine's
        suggestions and it is the reason the list is worth having at all.
     2. Word completions, from the vocabulary — but only words that some page carries in its
        stem, title, aliases or tags. The body vocabulary is 7,361 words and completing to a
        word that merely occurs in a paragraph offers a query that then finds nothing. A
        word in a title is a word this corpus is *about*.
     3. Whole questions, from the eval set, which are questions the corpus has been measured
        answering.

   Costs no index bytes. The completion pool is reconstructed from `vocab` and the field ids
   already shipped for scoring; nothing was added to carry it. */
var NAMEISH = null;

function nameish() {
  if (NAMEISH) return NAMEISH;
  hydrate();
  /* How many pages carry this word in a naming field. Used to rank completions: a word four
     pages are titled with is a better thing to offer than a word one alias mentions. */
  var weight = new Map();
  for (var i = 0; i < IDX.docs.length; i++) {
    var f = IDX.docs[i].f, seen = new Set(), name;
    for (name in f) {
      if (name === 'sources') continue;   /* file paths, not language a person types */
      f[name].forEach(function (id) { seen.add(id); });
    }
    seen.forEach(function (id) { weight.set(id, (weight.get(id) || 0) + 1); });
  }
  NAMEISH = Array.from(weight, function (kv) {
    return { w: IDX.vocab[kv[0]], n: kv[1] };
  }).sort(function (a, b) { return b.n - a.n || a.w.localeCompare(b.w); });
  return NAMEISH;
}

/* The fragment the user is still typing: the last run of word characters, and only when the
   caret is at the end of it. Completing a word in the middle of a sentence rewrites text the
   user has already moved past. */
function tail(query) {
  var m = /[a-z0-9]+$/.exec(query.toLowerCase());
  return m ? m[0] : '';
}

function suggest(query, caretAtEnd) {
  var q = query.trim();
  if (!q) return [];
  var out = [], seen = new Set();

  var res = search(q, 5);
  (res ? res.rows : []).forEach(function (r) {
    out.push({ kind: 'page', stem: r.stem, label: r.t, sub: r.g, k: r.k, how: r.how });
    seen.add(r.stem);
  });

  var frag = caretAtEnd ? tail(q) : '';
  if (frag.length >= 2) {
    var pool = nameish(), added = 0;
    for (var i = 0; i < pool.length && added < 3; i++) {
      var w = pool[i].w;
      if (w === frag || w.indexOf(frag) !== 0) continue;
      var completed = q.slice(0, q.length - frag.length) + w;
      if (seen.has(completed)) continue;
      seen.add(completed);
      out.push({ kind: 'term', label: completed, match: q.length - frag.length + frag.length });
      added++;
    }
  }

  var needle = q.toLowerCase();
  (IDX.questions || []).forEach(function (question) {
    if (out.length >= 9 || seen.has(question)) return;
    if (question.toLowerCase().indexOf(needle) === -1) return;
    seen.add(question);
    out.push({ kind: 'ask', label: question });
  });

  return out.slice(0, 9);
}

function markHTML(text, needle) {
  var at = String(text).toLowerCase().indexOf(String(needle).toLowerCase());
  if (at === -1 || !needle) return esc(text);
  return esc(text.slice(0, at)) + '<b>' + esc(text.slice(at, at + needle.length)) +
    '</b>' + esc(text.slice(at + needle.length));
}

var field = document.querySelector('[data-ask]');
var panel = document.querySelector('[data-results]');
var box = document.querySelector('[data-suggest]');
var cursor = -1;
var items = [];

function closeSuggest() {
  if (!box) return;
  box.hidden = true;
  box.innerHTML = '';
  items = [];
  cursor = -1;
  if (field) {
    field.setAttribute('aria-expanded', 'false');
    field.removeAttribute('aria-activedescendant');
  }
}

function paintCursor() {
  for (var i = 0; i < box.children.length; i++) {
    var on = i === cursor;
    box.children[i].classList.toggle('on', on);
    box.children[i].setAttribute('aria-selected', on ? 'true' : 'false');
  }
  if (field) {
    if (cursor >= 0) field.setAttribute('aria-activedescendant', 'sg' + cursor);
    else field.removeAttribute('aria-activedescendant');
  }
}

var LABEL = { page: 'page', term: 'complete', ask: 'question' };

function openSuggest(query) {
  if (!box || !IDX) return;
  var atEnd = field.selectionStart === null || field.selectionStart === field.value.length;
  items = suggest(query, atEnd);
  if (!items.length) { closeSuggest(); return; }
  cursor = -1;
  box.innerHTML = items.map(function (s, i) {
    var body = s.kind === 'page'
      ? '<span class="kind k-' + esc(s.k) + '">' + esc(s.k) + '</span>' +
        '<span class="sg-t">' + markHTML(s.label, query) + '</span>' +
        '<span class="sg-g">' + esc(s.sub || '') + '</span>' +
        (s.how === 'linked' ? '<span class="sg-h">via a link</span>' : '')
      : '<span class="sg-k">' + esc(LABEL[s.kind]) + '</span>' +
        '<span class="sg-t">' + markHTML(s.label, query) + '</span>';
    return '<li id="sg' + i + '" role="option" aria-selected="false" ' +
      'class="sg sg-' + esc(s.kind) + '" data-i="' + i + '">' + body + '</li>';
  }).join('');
  box.hidden = false;
  field.setAttribute('aria-expanded', 'true');
  paintCursor();
}

function choose(i) {
  var s = items[i];
  if (!s) return;
  if (s.kind === 'page') { location.href = BASE + 'p/' + s.stem + '.html'; return; }
  field.value = s.label + (s.kind === 'term' ? ' ' : '');
  closeSuggest();
  /* No results panel means this is the header box on an article page: there is nowhere to
     render an answer, so completing a word has to take the reader to the page that can. */
  if (!panel) { location.href = BASE + 'index.html?q=' + encodeURIComponent(field.value.trim()); return; }
  ask(field.value.trim());
  field.focus();
}

if (box) {
  box.addEventListener('mousedown', function (e) {
    /* mousedown, not click: the input's blur handler closes the list, and blur lands first. */
    var li = e.target.closest('[data-i]');
    if (!li) return;
    e.preventDefault();
    choose(+li.getAttribute('data-i'));
  });
  box.addEventListener('mousemove', function (e) {
    var li = e.target.closest('[data-i]');
    if (li && +li.getAttribute('data-i') !== cursor) {
      cursor = +li.getAttribute('data-i');
      paintCursor();
    }
  });
}

/* A search you cannot send to somebody is a dead end. The query goes in the URL, so a result
   is a link — and arriving on one runs it, which also makes every state on this page
   reachable without a keystroke. `replaceState`, not `push`: typing a nine-character question
   would otherwise leave nine entries in the history and make Back mean "delete one letter".
   Under file:// there is no origin to write to, and that throws; the search still works. */
function remember(query) {
  try {
    var url = location.pathname + (query ? '?q=' + encodeURIComponent(query) : '') + location.hash;
    history.replaceState(null, '', url);
  } catch (e) { /* file:// — nothing to update, and nothing depends on it */ }
}

function ask(query) {
  if (!panel) return;
  remember(query);
  if (!IDX) { panel.innerHTML = '<p class="ask-note">Search index did not load.</p>'; return; }
  if (!query) { panel.innerHTML = ''; return; }
  var t0 = performance.now();
  var res = search(query, 5);
  var ms = Math.max(1, Math.round(performance.now() - t0));
  if (!res.rows.length) {
    /* Mid-word is not a refusal. Typing "how do you anonym" put a full "Nothing here answers
       that" block on screen while the list directly above it was offering "anonymisation" —
       the page contradicting itself, and the loudest element on it being wrong. A refusal is
       an answer to a question somebody finished asking. */
    if (items.length && items.some(function (s) { return s.kind !== 'ask'; })) {
      panel.innerHTML = '<p class="ask-note">Still typing — pick a suggestion above, ' +
        'or press Enter to search for “' + esc(query) + '”.</p>';
      return;
    }
    panel.innerHTML = refusalHTML(query, res);
    return;
  }
  panel.innerHTML =
    '<div class="res-h"><strong>' + res.rows.length + ' pages</strong>' +
    '<span>for “' + esc(query) + '”</span>' +
    '<span>' + res.considered + ' considered · ' + ms + ' ms · in your browser</span></div>' +
    '<div class="cards">' + res.rows.map(cardHTML).join('') + '</div>';
}

/* The input's own form, whichever it is: the landing page's big box or the header box on
   every other page. Asking for `[data-askform]` found only the first, so Enter in the header
   box skipped this handler entirely and a highlighted suggestion was silently discarded. */
var form = field ? field.form : null;
if (form) {
  form.addEventListener('submit', function (e) {
    /* Enter with a suggestion highlighted takes the suggestion. Enter with none runs the
       query as typed — the list never silently substitutes something the user did not pick. */
    if (cursor >= 0) { e.preventDefault(); choose(cursor); return; }
    closeSuggest();
    /* Only the page that can show results handles its own submit. Everywhere else the
       browser's native GET does the work, which is also what happens with JavaScript off:
       `action="index.html"` and `name="q"` are a working search box with no script at all. */
    if (!panel) return;
    e.preventDefault();
    ask(field.value.trim());
  });
}
if (field) {
  var timer = null;
  field.addEventListener('input', function () {
    /* Suggestions are synchronous and local, so they open on the keystroke. The results
       panel below is debounced: it rewrites a large subtree, and doing that on every
       keystroke is what makes a search box feel like it is fighting you. */
    openSuggest(field.value.trim());
    clearTimeout(timer);
    timer = setTimeout(function () { ask(field.value.trim()); }, 140);
  });
  field.addEventListener('focus', function () {
    if (field.value.trim()) openSuggest(field.value.trim());
  });
  field.addEventListener('blur', function () { setTimeout(closeSuggest, 90); });
  field.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!items.length) { openSuggest(field.value.trim()); if (!items.length) return; }
      e.preventDefault();
      var step = e.key === 'ArrowDown' ? 1 : -1;
      /* Wraps through -1, which is "nothing selected, my own text". A list you cannot get
         back out of with the same key that got you in is a trap. */
      cursor = cursor + step;
      if (cursor >= items.length) cursor = -1;
      if (cursor < -1) cursor = items.length - 1;
      paintCursor();
    } else if (e.key === 'Escape') {
      if (!box.hidden) { e.stopPropagation(); closeSuggest(); }
    } else if (e.key === 'Tab' && cursor >= 0 && items[cursor].kind !== 'page') {
      e.preventDefault();
      field.value = items[cursor].label + ' ';
      closeSuggest();
      openSuggest(field.value.trim());
    }
  });
}
document.addEventListener('click', function (e) {
  var s = e.target.closest('[data-seed]');
  if (!s || !field) return;
  field.value = s.getAttribute('data-seed');
  field.focus();
  closeSuggest();
  ask(field.value);
  if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});
/* Arriving on a shared link runs the search it names, before any keystroke. */
if (field) {
  (function fromUrl() {
    var m = /[?&]q=([^&#]*)/.exec(location.search);
    if (!m) return;
    var q = decodeURIComponent(m[1].replace(/\+/g, ' ')).trim();
    if (!q) return;
    field.value = q;
    ask(q);
  })();
}

document.addEventListener('keydown', function (e) {
  var active = document.activeElement;
  var typing = !!active && (/^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName) ||
    active.isContentEditable);
  if ((e.key === '/' || e.key === 's') && field && !typing && !e.metaKey && !e.ctrlKey) {
    e.preventDefault();
    field.focus();
    field.select();
  }
  if (e.key === 'Escape' && document.activeElement === field) {
    field.value = '';
    closeSuggest();
    ask('');
    field.blur();
  }
});

/* ── the map ───────────────────────────────────────────────────────────────
   The picture is drawn at build time — this only decides what is lit. Two independent
   filters (a ring, a kind) and a readout, and clicking an active filter clears it, because
   a filter you can turn on and not off is a trap on a page whose whole point is the whole. */
(function mapPage() {
  var svg = document.querySelector('.map-svg');
  if (!svg) return;
  var readout = document.querySelector('[data-map-readout]');
  var ringList = document.querySelector('[data-map-rings]');
  var ringButtons = Array.prototype.slice.call(document.querySelectorAll('[data-map-ring]'));
  var nodes = Array.prototype.slice.call(svg.querySelectorAll('.node'));
  var edges = Array.prototype.slice.call(svg.querySelectorAll('.edge'));
  var circles = Array.prototype.slice.call(svg.querySelectorAll('.ring-o'));
  var kindButtons = Array.prototype.slice.call(document.querySelectorAll('[data-map-kind]'));
  var ring = '', kind = '';

  function apply() {
    var on = ring || kind;
    svg.classList.toggle('filtered', !!on);
    var lit = {};
    nodes.forEach(function (n) {
      var ok = (!ring || n.getAttribute('data-ring') === ring) &&
        (!kind || n.getAttribute('data-kind') === kind);
      n.classList.toggle('hit', ok);
      if (ok) lit[n.getAttribute('data-stem')] = 1;
    });
    edges.forEach(function (e) {
      e.classList.toggle('on', !!on &&
        lit[e.getAttribute('data-a')] === 1 && lit[e.getAttribute('data-b')] === 1);
    });
    circles.forEach(function (c) {
      c.classList.toggle('on', !!ring && c.getAttribute('data-ring') === ring);
    });
    if (ringList) {
      Array.prototype.forEach.call(ringList.children, function (li) {
        li.classList.toggle('on', li.getAttribute('data-ring') === ring);
      });
    }
    ringButtons.forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-map-ring') === ring ? 'true' : 'false');
    });
    kindButtons.forEach(function (b) {
      var selected = b.getAttribute('data-map-kind') === kind;
      b.classList.toggle('on', selected);
      b.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
  }

  if (ringList) {
    ringList.addEventListener('click', function (e) {
      /* The project name stays a link; only the native button changes the filter. */
      var button = e.target.closest('[data-map-ring]');
      if (!button) return;
      var selectedRing = button.getAttribute('data-map-ring');
      ring = selectedRing === ring ? '' : selectedRing;
      apply();
    });
  }
  kindButtons.forEach(function (b) {
    b.addEventListener('click', function () {
      kind = b.getAttribute('data-map-kind') === kind ? '' : b.getAttribute('data-map-kind');
      apply();
    });
  });

  function name(n) {
    if (!readout) return;
    if (!n) { readout.innerHTML = 'Hover or focus a page to name it. Click to open it.'; return; }
    var t = n.querySelector('title');
    var label = t ? t.textContent.split(' — ')[0] : n.getAttribute('data-stem');
    readout.innerHTML = '<span class="kind k-' + esc(n.getAttribute('data-kind')) + '">' +
      esc(n.getAttribute('data-kind')) + '</span><strong>' + esc(label) + '</strong> — ' +
      esc(n.getAttribute('data-ring') || 'no repository');
  }
  svg.addEventListener('mouseover', function (e) {
    var n = e.target.closest('.node');
    if (n) name(n);
  });
  svg.addEventListener('mouseout', function (e) {
    if (e.target.closest('.node')) name(null);
  });
  svg.addEventListener('focusin', function (e) { name(e.target.closest('.node')); });
  svg.addEventListener('focusout', function () { name(null); });
})();

/* ── browse filter ───────────────────────────────────────────────────────── */
(function browseFilter() {
  var text = document.querySelector('[data-filter-text]');
  var count = document.querySelector('[data-filter-count]');
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-filter]'));
  var rows = Array.prototype.slice.call(document.querySelectorAll('.row'));
  if (!rows.length) return;
  var kind = '';

  function apply() {
    var needle = (text ? text.value : '').trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (row) {
      var ok = (!kind || row.getAttribute('data-kind') === kind) &&
        (!needle || row.getAttribute('data-text').indexOf(needle) !== -1);
      row.hidden = !ok;
      if (ok) shown++;
    });
    document.querySelectorAll('.grp').forEach(function (grp) {
      grp.hidden = !grp.querySelector('.row:not([hidden])');
    });
    if (count) {
      count.textContent = (needle || kind)
        ? shown + ' of ' + rows.length + ' pages shown'
        : rows.length + ' pages';
    }
  }

  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      kind = b.getAttribute('data-filter');
      buttons.forEach(function (o) { o.classList.toggle('on', o === b); });
      apply();
    });
  });
  if (text) text.addEventListener('input', apply);
  apply();
})();
