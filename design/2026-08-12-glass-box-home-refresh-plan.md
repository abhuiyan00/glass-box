# Glass Box home refresh implementation plan

Date: 2026-08-12

## 1. Pin the evidence-derived landing copy

1. Add rendered-output tests for `N verified source repositories`, the `receipts.html` link, and correct equal/non-equal source/project wording.
2. Confirm the tests fail before production changes.
3. In `views.landing()`, read the source count from `stats["corpus"]["repos"]`, falling back to `by_repo()` only when the source total is absent or `None`.
4. Preserve explicit zero totals and keep `content/` immutable.
5. Re-run the focused landing tests.

## 2. Add progressive home-only motion

1. Add focused tests for `.hero-home`, five existing reveal targets, named keyframes, the existing reduced-motion override, and un-clipped search suggestions.
2. Confirm focused tests fail before the renderer/CSS changes.
3. Add the home class and `data-reveal` hooks without changing search semantics or order.
4. Add CSS-only halo and 450 ms staggered reveal styling in `assets/app.css`; use opacity/transform only, existing tokens, no external assets, and no JavaScript.
5. Re-run focused motion tests and `git diff --check`.

## 3. Build, audit, and publish generated output

1. Run the full suite with the workspace-level scratch directory:

   ```powershell
   python -m pytest -q --basetemp 'D:\Git area (testing)\.test-temp-glass-box' -p no:cacheprovider
   ```

2. Run `python build.py`; verify the manifest and 120 KB landing gzip budget.
3. Run `python tools/audit_site.py docs`; require zero findings in every audit category.
4. Run `git diff --check` and inspect `git status --short` before staging.
5. Stage only changed generated assets and durable root-level `design/` records; never stage `content/`, `.superpowers/`, or the test scratch directory.
6. Commit publishable output and design records separately, retaining exact command results and commit SHAs in the Task 3 report.

## Completed evidence

- Full suite: `58 passed`.
- Build: manifest verified with 284 files; landing 5.4 KB gzipped (120 KB budget).
- Audit: PASS with zero dead links, remote loads, network-calling scripts, privacy matches, language/title omissions, and missing image alt text.
- Generated assets were committed as `5d086f9c6ad090a18e4b26e5762f15004e27ea74` (`docs: publish refreshed home assets`).
