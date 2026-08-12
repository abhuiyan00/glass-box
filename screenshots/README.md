# Screenshots

Real captures of `docs/` as `build.py` renders it, served over `python -m http.server` and
photographed in headless Chromium at 1280 CSS px. Nothing here is a mockup.

They live in `screenshots/` rather than `assets/` because `assets/` is a build *input* —
`build.py` copies every file in it into `docs/assets/`, so a README image placed there would
be published as part of the site and counted in its file budget.

| File | What it shows |
|---|---|
| `site-ask.png` | The front page: the search box, the suggested questions, and the five browse cards with their live counts. |
| `site-project-page.png` | A project page — the confidence and bi-temporal header, the section index, and the opening account, including a stance the author later reversed. |

Recapture after any change to the theme or the landing copy:

```
python build.py
cd docs && python -m http.server 8731
```
