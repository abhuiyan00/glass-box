"""Load `content/`, and refuse to build from a bundle somebody edited by hand.

Every file in the bundle opens with a banner saying DO NOT EDIT. A banner is a note; this
module is the rule. `MANIFEST.json` carries a sha256 for every other file, so an edited page
fails the build with the filename rather than quietly shipping prose that no longer matches
the private page it claims to be a copy of.

That check is the whole reason the manifest exists. The generator is otherwise indifferent to
where the bundle came from — the contract is the four data files, not the tool that wrote
them.
"""

import hashlib
import json
import re
from pathlib import Path

BANNER = re.compile(r"\A<!--.*?-->\s*", re.S)
REQUIRED = ("MANIFEST.json", "index.json", "stats.json", "scorer.json")


class BundleError(Exception):
    """The bundle is missing, malformed, or no longer matches its own manifest."""


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise BundleError(f"{path.name}: cannot read ({e})") from e
    except ValueError as e:
        raise BundleError(f"{path.name}: not valid JSON ({e})") from e


class Bundle:
    """The exported content, verified. Attribute access only; nothing here mutates."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise BundleError(
                f"no bundle at {self.root} — run `python brain.py export` in the private "
                f"second-brain repository, or point --content somewhere else")
        for name in REQUIRED:
            if not (self.root / name).is_file():
                raise BundleError(f"bundle is incomplete: {name} is missing")

        self.manifest = _read_json(self.root / "MANIFEST.json")
        self.verify()

        index = _read_json(self.root / "index.json")
        self.pages = list(index.get("pages", []))
        self.questions = list(index.get("questions", []))
        self.stats = _read_json(self.root / "stats.json")
        self.scorer = _read_json(self.root / "scorer.json")

        self.by_stem = {p["stem"]: p for p in self.pages}
        self.published = set(self.by_stem)
        self.bodies = {}
        for page in self.pages:
            src = self.root / "pages" / f"{page['stem']}.md"
            if not src.is_file():
                raise BundleError(f"index.json lists {page['stem']} but pages/"
                                  f"{page['stem']}.md does not exist")
            self.bodies[page["stem"]] = BANNER.sub("", src.read_text(encoding="utf-8"))

    def verify(self):
        """Every file the manifest names must hash to what the manifest says."""
        files = self.manifest.get("files") or {}
        if not files:
            raise BundleError("MANIFEST.json lists no files — refusing to build")
        bad = []
        for rel, digest in sorted(files.items()):
            path = self.root / rel
            if not path.is_file():
                bad.append(f"{rel} (missing)")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                bad.append(f"{rel} (edited since export)")
        if bad:
            raise BundleError(
                "bundle does not match its manifest — these files were changed after "
                "export:\n  " + "\n  ".join(bad) +
                "\n\ncontent/ is generated. Change the page in the private wiki and export "
                "again; editing it here makes the site disagree with its own source.")

    # -- convenience views over the same records, so no view module re-derives them ------

    def of_type(self, kind):
        return [p for p in self.pages if p["type"] == kind]

    def by_type(self):
        """{type: [page]} in the order the site presents them — projects first.

        Types outside the known order still appear, at the end. The wiki schema fixes six
        types, but this project does not own that schema and must not silently drop a page
        because a seventh arrived.
        """
        order = ["project", "decision", "pattern", "concept", "tech"]
        seen = [k for k in order if self.of_type(k)]
        extra = sorted({p["type"] for p in self.pages} - set(order))
        return {k: self.of_type(k) for k in seen + extra}

    def by_repo(self):
        """{repo: [page]} for every source repository any published page rests on."""
        out = {}
        for page in self.pages:
            for repo in page.get("repos", []):
                out.setdefault(repo, []).append(page)
        return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    def project_for(self, repo):
        """The project page claiming this repository, or None. Used for repo headings."""
        for page in self.of_type("project"):
            if repo in page.get("repos", []):
                return page
        return None

    def stat(self, *path, default=None):
        """stats.json lookup that returns None rather than raising. `None` renders a gap."""
        node = self.stats
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return default if node is None else node
