#!/usr/bin/env python3
"""Regenerate narration affected by the external correction matrix."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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


BASE_IDS = {
    "pg006_n0004",
    "pg006_n0005",
    "pg007_im055",
    "pg007_im058",
    "pg010_n0043",
    "pg026_im057",
    "pg026_im060",
    "pg034_im056",
    "pg034_im059",
    "pg051_n0011",
    "pg060_im056",
    "pg060_im059",
    "pg077_im059",
    "pg081_n0009",
    "pg082_n0007",
    "pg083_im058_seg002_v1",
    "pg083_im061",
    "pg089_im056",
    "pg089_im059",
    "pg090_n0024",
    "pg091_n0002",
}

REMAINING_IDS = {
    "pg050_n0019",
    "pg050_n0021",
    "pg052_n0031",
    "pg052_n0033",
    "pg052_n0035",
    "pg052_n0040",
    "pg052_n0042",
    "pg052_n0044",
    "pg053_n0007",
    "pg053_n0012",
    "pg053_n0013",
    "pg053_n0017",
    "pg053_n0024",
    "pg053_n0028",
    "pg053_n0032",
    "pg058_n0018",
    "pg058_n0020",
    "pg058_n0022",
    "pg058_n0026",
    "pg058_n0027",
    "pg058_n0028",
    "pg058_n0029",
    "pg058_n0030",
    "pg058_n0031",
    "pg059_n0006",
    "pg059_n0008",
    "pg059_n0010",
    "pg059_n0016",
    "pg059_n0018",
    "pg059_n0024",
    "pg059_n0026",
    "pg059_n0028",
    "pg059_n0038",
    "pg071_n0016",
    "pg077_im056",
    "pg088_n0010",
    "pg088_n0016",
    "pg088_n0022",
}

BLANK_IDS = REMAINING_IDS - {
    "pg050_n0019",
    "pg050_n0021",
    "pg071_n0016",
    "pg077_im056",
}


def spoken_text(text_id: str, visible: str) -> str:
    if text_id.startswith("pg006_n0004"):
        return visible.replace("Standards III–VI", "Standards Three to Six")
    if text_id.startswith("pg006_n0005"):
        return visible.replace("Standard IV", "Standard Four")
    if text_id.removesuffix("_easy_read") in BLANK_IDS:
        spoken = re.sub(r"(?:…|\.{3}|_{3,})", ", blank, ", visible)
        return re.sub(r"\s+", " ", spoken).strip()
    return visible


async def generate(items: list[tuple[str, str, str]], concurrency: int) -> None:
    import edge_tts

    semaphore = asyncio.Semaphore(concurrency)
    with tempfile.TemporaryDirectory(prefix="adt-matrix-audio-", dir="/tmp") as temp:
        work = Path(temp)

        async def run(item: tuple[str, str, str]) -> None:
            text_id, speech, filename = item
            await rebuild_one(
                edge_tts,
                text_id,
                speech,
                filename.split("?", 1)[0],
                work,
                semaphore,
            )
            print(f"generated {text_id}", flush=True)

        await asyncio.gather(*(run(item) for item in items))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--remaining-only",
        action="store_true",
        help="Regenerate only audio changed by the remaining correction rows.",
    )
    args = parser.parse_args()

    texts_path = I18N / "texts.json"
    audios_path = I18N / "audios.json"
    texts = json.loads(texts_path.read_text(encoding="utf-8"))
    audios = json.loads(audios_path.read_text(encoding="utf-8"))

    selected = REMAINING_IDS if args.remaining_only else BASE_IDS | REMAINING_IDS
    ids = sorted(selected | {f"{text_id}_easy_read" for text_id in selected})
    missing = [text_id for text_id in ids if text_id not in texts or text_id not in audios]
    if missing:
        raise KeyError("Missing text/audio mappings: " + ", ".join(missing))

    items = [
        (text_id, spoken_text(text_id, texts[text_id]), audios[text_id])
        for text_id in ids
    ]
    asyncio.run(generate(items, args.concurrency))

    for text_id, _speech, filename in items:
        clean = filename.split("?", 1)[0]
        digest = hashlib.sha256((I18N / "audio" / clean).read_bytes()).hexdigest()[:12]
        audios[text_id] = f"{clean}?v={digest}"
    audios_path.write_text(
        json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
