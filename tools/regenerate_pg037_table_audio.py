#!/usr/bin/env python3
"""Sync and regenerate page 37 table audio in row-first reading order."""

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
    ("one", "He brushed his teeth in the morning.", "Did he brush his teeth in the morning?", "Yes, he brushed his teeth in the morning.", "No, he did not brush his teeth in the morning.", "Yes, he did.", "No, he did not."),
    ("two", "Neema combed her hair in the morning.", "Did she comb her hair in the morning?", "Yes, she combed her hair in the morning.", "No, she did not comb her hair in the morning.", "Yes, she did.", "No, she did not."),
    ("three", "The pupils ate ugali for lunch in the afternoon.", "Did the pupils eat ugali for lunch in the afternoon?", "Yes, the pupils ate ugali for lunch in the afternoon.", "No, the pupils did not eat ugali for lunch in the afternoon.", "Yes, they did.", "No, they did not."),
    ("four", "She went to school today.", "Did she go to school today?", "Yes, she went to school today.", "No, she did not go to school today.", "Yes, she did.", "No, she did not."),
    ("five", "Kemy and Jane did the homework.", "Did Kemy and Jane do the homework?", "Yes, Kemy and Jane did the homework.", "No, Kemy and Jane did not do the homework?", "Yes, they did.", "No, they did not."),
)


def items() -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for row, (number, statement, question, long_yes, long_no, short_yes, short_no) in enumerate(ROWS, 1):
        prefix = f"pg037_tbl_r{row}"
        values = (
            (f"{prefix}_num", f"{row}.", f"Number {number}."),
            (f"{prefix}_statement", statement, f"Statement. {statement}"),
            (f"{prefix}_question", question, f"Question. {question}"),
            (f"{prefix}_long_yes", long_yes, f"Long answer. {long_yes}"),
            (f"{prefix}_long_or", "or", "or"),
            (f"{prefix}_long_no", long_no, long_no),
            (f"{prefix}_short_yes", short_yes, f"Short answer. {short_yes}"),
            (f"{prefix}_short_or", "or", "or"),
            (f"{prefix}_short_no", short_no, short_no),
        )
        result.extend(values)
    return result


def sync_metadata() -> None:
    texts_path = I18N / "texts.json"
    audios_path = I18N / "audios.json"
    texts = json.loads(texts_path.read_text(encoding="utf-8"))
    audios = json.loads(audios_path.read_text(encoding="utf-8"))
    for text_id, visible, _spoken in items():
        filename = f"{text_id}.mp3"
        texts[text_id] = visible
        texts[f"{text_id}_easy_read"] = visible
        audios[text_id] = filename
        audios[f"{text_id}_easy_read"] = filename
    texts_path.write_text(json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audios_path.write_text(json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def generate(concurrency: int) -> None:
    import edge_tts

    semaphore = asyncio.Semaphore(concurrency)
    with tempfile.TemporaryDirectory(prefix="adt-pg037-table-", dir="/tmp") as temp:
        work = Path(temp)
        work_items = [(text_id, spoken, f"{text_id}.mp3") for text_id, _visible, spoken in items()]
        completed = 0

        async def render(item: tuple[str, str, str]) -> None:
            nonlocal completed
            await rebuild_one(edge_tts, *item, work, semaphore)
            completed += 1
            print(f"Generated {completed}/{len(work_items)}: {item[0]}", flush=True)

        await asyncio.gather(*(render(item) for item in work_items))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if args.sync:
        sync_metadata()
    if args.generate:
        asyncio.run(generate(args.concurrency))


if __name__ == "__main__":
    main()
