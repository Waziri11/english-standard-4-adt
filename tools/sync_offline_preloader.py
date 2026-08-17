#!/usr/bin/env python3
"""Synchronize JSON and HTML embedded in the offline fetch preloader."""

from pathlib import Path
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parents[1]
PRELOADER = ROOT / "assets/offline-preloader.js"
PREFIX = "  var INLINE = "
SUFFIX = ";\n  var BASE_DIR = "


source = PRELOADER.read_text(encoding="utf-8")
start = source.index(PREFIX) + len(PREFIX)
end = source.index(SUFFIX, start)
inline = json.loads(source[start:end])

pages = json.loads((ROOT / "content/pages.json").read_text(encoding="utf-8"))
html_paths = sorted({ROOT / page["href"] for page in pages} | set(ROOT.glob("*.html")))

# Derive the public build version from source content, not from the generated
# preloader. Normalising the version query makes this calculation stable across
# repeated runs and avoids embedding pages that point to the previous build.
version_input = hashlib.sha256()
for local in html_paths:
    if not local.is_file():
        continue
    html = local.read_text(encoding="utf-8")
    normalized = re.sub(
        r"offline-preloader\.js(?:\?v=[^\"']+)?",
        "offline-preloader.js?v=__BUILD__",
        html,
    )
    version_input.update(local.name.encode("utf-8"))
    version_input.update(b"\0")
    version_input.update(normalized.encode("utf-8"))

for key in sorted(inline):
    relative = key[2:] if key.startswith("./") else key
    local = ROOT / relative
    if local.is_file() and local.suffix == ".json":
        version_input.update(relative.encode("utf-8"))
        version_input.update(b"\0")
        version_input.update(local.read_bytes())

digest = version_input.hexdigest()
version = digest[:12]

for html_path in html_paths:
    if not html_path.is_file():
        continue
    html = html_path.read_text(encoding="utf-8")
    revised = re.sub(
        r"offline-preloader\.js(?:\?v=[^\"']+)?",
        f"offline-preloader.js?v={version}",
        html,
    )
    if revised != html:
        html_path.write_text(revised, encoding="utf-8")

updated = 0
for key in list(inline):
    relative = key[2:] if key.startswith("./") else key
    local = ROOT / relative
    if local.is_file() and local.suffix == ".json":
        inline[key] = json.loads(local.read_text(encoding="utf-8"))
        updated += 1
    elif local.is_file() and local.suffix == ".html":
        inline[key] = local.read_text(encoding="utf-8")
        updated += 1
    elif local.suffix in {".html", ".json"}:
        del inline[key]

for page in pages:
    relative = page["href"]
    local = ROOT / relative
    if local.is_file():
        inline[f"./{relative}"] = local.read_text(encoding="utf-8")
        updated += 1

payload = json.dumps(inline, ensure_ascii=False, separators=(",", ":"))
PRELOADER.write_text(source[:start] + payload + source[end:], encoding="utf-8")

(ROOT / ".build-hash").write_text(digest + "\n", encoding="utf-8")
print(f"synchronized {updated} embedded resources for build {version}")
