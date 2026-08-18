#!/usr/bin/env python3
"""Regenerate page 44 table audio with row and column announcements."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from rebuild_mixed_voice_audio import rebuild_one  # noqa: E402


ROWS = (
    ("pg044_n0018", "one", "pg044_n0020", "pg044_n0022", "pg044_n0024", "pg044_n0028"),
    ("pg044_n0033", "two", "pg044_n0035", "pg044_n0037", "pg044_n0039", "pg044_n0043"),
    ("pg044_n0048", "three", "pg044_n0050", "pg044_n0052", "pg044_n0054", "pg044_n0058"),
    ("pg044_n0063", "four", "pg044_n0065", "pg044_n0067", "pg044_n0069", "pg044_n0073"),
    ("pg044_n0078", "five", "pg044_n0080", "pg044_n0082", "pg044_n0084", "pg044_n0088"),
)


def speech_overrides(texts: dict[str, str]) -> dict[str, str]:
    speech: dict[str, str] = {}
    for number_id, number, statement_id, question_id, long_id, short_id in ROWS:
        speech[number_id] = f"Number {number}."
        speech[statement_id] = f"Statement. {texts[statement_id]}"
        speech[question_id] = f"Question. {texts[question_id]}"
        speech[long_id] = f"Long answer. {texts[long_id]}"
        speech[short_id] = f"Short answer. {texts[short_id]}"
    return speech


async def generate(concurrency: int, start_row: int) -> None:
    import edge_tts

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    overrides = speech_overrides(texts)
    allowed_ids = {
        text_id
        for row in ROWS[start_row - 1 :]
        for text_id in (row[0], row[2], row[3], row[4], row[5])
    }
    items: list[tuple[str, str, str]] = []
    for text_id, spoken_text in overrides.items():
        if text_id not in allowed_ids:
            continue
        items.append((text_id, spoken_text, audios[text_id]))
        easy_id = f"{text_id}_easy_read"
        if easy_id in audios:
            items.append((easy_id, spoken_text, audios[easy_id]))

    semaphore = asyncio.Semaphore(concurrency)
    with tempfile.TemporaryDirectory(prefix="adt-pg044-table-", dir="/tmp") as temp:
        work = Path(temp)
        completed = 0

        async def render(item: tuple[str, str, str]) -> None:
            nonlocal completed
            await rebuild_one(edge_tts, *item, work, semaphore)
            completed += 1
            print(f"Generated {completed}/{len(items)}: {item[0]}", flush=True)

        await asyncio.gather(*(render(item) for item in items))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--start-row", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    if args.dry_run:
        for text_id, speech in speech_overrides(texts).items():
            print(f"{text_id}\t{speech}")
        return
    asyncio.run(generate(args.concurrency, args.start_row))


if __name__ == "__main__":
    main()
