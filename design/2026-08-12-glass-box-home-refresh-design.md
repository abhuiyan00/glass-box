# Glass Box home refresh design

Date: 2026-08-12

## Purpose

Refresh the landing page while preserving Glass Box's technical-editorial character and its offline, evidence-backed model.

## Count and project truth

The landing-page source count is the bundle-derived `N verified source repositories`. `N` comes from `Bundle.stats["corpus"]["repos"]`; if that field is absent or `None`, it falls back to `len(Bundle.by_repo())`. An explicit measured zero remains zero. It is never a manually typed workspace count.

The page explains that this count means sources named by published pages and links to `receipts.html`. When every verified source has a public project page, the project summary states that every verified source repository has one; it must not claim a private remainder. The alternate wording retains the private-remainder qualification when the counts differ.

## Visual and motion constraints

Keep the system-font, technical-editorial visual language. The home hero alone gains a low-contrast, CSS-only ambient radial halo behind content and a 450 ms staggered reveal for five existing children: eyebrow, heading, lede, search form, and seed area.

Motion uses only opacity and transform. The halo is a non-interactive pseudo-element, is isolated to `.hero-home`, and uses existing theme tokens. Final opacity and transform values are declared normally so no-CSS and reduced-motion states remain complete. The existing `prefers-reduced-motion` override disables animation. Search form labels, role, action, hooks, keyboard behavior, focus visibility, `file://` operation, and responsive layout remain unchanged; the hero does not clip search suggestions.

## Boundaries

Do not modify `content/`, which is generated and manifest-verified. Add no dependency, webfont, CDN, analytics, image, JavaScript animation, or network request. No scrolling or parallax is introduced.

## Files changed

- `src/glassbox/views.py`: derive the verified source count and emit the home-only hero/reveal hooks.
- `assets/app.css`: add home-only halo/reveal styling and named keyframes.
- `tests/test_build.py`: cover derived count/project-summary wording, motion hooks, reduced-motion protection, and visible suggestions.
- `docs/index.html` and `docs/assets/app.css`: build-generated publishable output.

## Verification contract

Focused red/green checks use:

```powershell
python -m pytest tests/test_build.py -q --basetemp 'D:\Git area (testing)\.test-temp-glass-box' -p no:cacheprovider -k landing_
python -m pytest tests/test_build.py -q --basetemp 'D:\Git area (testing)\.test-temp-glass-box' -p no:cacheprovider -k 'hero or motion'
```

Release verification uses:

```powershell
python -m pytest -q --basetemp 'D:\Git area (testing)\.test-temp-glass-box' -p no:cacheprovider
python build.py
python tools/audit_site.py docs
git diff --check
```

The build must report a verified manifest and landing gzip size no greater than 120 KB. The audit must report zero findings in every audit category.
