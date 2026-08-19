#!/usr/bin/env python3
"""Regenerate every image-description recording from the current English text."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from rebuild_mixed_voice_audio import rebuild_one  # noqa: E402


IMAGE_ID_RE = re.compile(r"^pg\d{3}_im\d{3}(?:_[a-z0-9_]+)?$")
DESCRIPTION_RE = re.compile(r"^A picture of\b", re.IGNORECASE)


async def generate(items: list[tuple[str, str, str]], concurrency: int) -> None:
    import edge_tts

    semaphore = asyncio.Semaphore(concurrency)
    with tempfile.TemporaryDirectory(prefix="adt-image-audio-", dir="/tmp") as temp:
        work = Path(temp)
        completed = 0

        async def run(item: tuple[str, str, str]) -> None:
            nonlocal completed
            await rebuild_one(edge_tts, *item, work, semaphore)
            completed += 1
            if completed % 25 == 0 or completed == len(items):
                print(f"Generated {completed}/{len(items)}", flush=True)

        await asyncio.gather(*(run(item) for item in items))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    image_ids = [key for key in texts if IMAGE_ID_RE.fullmatch(key)]
    invalid = [key for key in image_ids if not DESCRIPTION_RE.match(texts[key].strip())]
    if invalid:
        raise ValueError(
            "Image descriptions must start with 'A picture of': " + ", ".join(invalid)
        )
    unmapped = [key for key in image_ids if key not in audios]
    if unmapped:
        raise KeyError("Image descriptions missing audio mappings: " + ", ".join(unmapped))

    items = [(key, texts[key], audios[key]) for key in image_ids]
    print(f"Regenerating {len(items)} image-description recordings")
    asyncio.run(generate(items, args.concurrency))


if __name__ == "__main__":
    main()
