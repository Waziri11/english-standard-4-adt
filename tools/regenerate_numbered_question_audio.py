#!/usr/bin/env python3
"""Regenerate numbered-question audio with an explicit "Question number …" lead-in."""

import argparse
import html
import json
import re
import asyncio
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
}
QUESTION_RE = re.compile(r"^\s*(\d+)[.)]\s+(.+\?)\s*$", re.DOTALL)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="en-TZ-ImaniNeural")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument(
        "--id-prefix",
        help="Only regenerate text IDs beginning with this prefix",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    questions = []
    for text_id, visible_text in texts.items():
        if args.id_prefix and not text_id.startswith(args.id_prefix):
            continue
        match = QUESTION_RE.match(visible_text)
        if not match:
            continue
        number = int(match.group(1))
        if number not in NUMBER_WORDS:
            raise ValueError(f"Unsupported question number {number}: {text_id}")
        filename = audios.get(text_id)
        if not filename:
            raise KeyError(f"No audio mapping for numbered question {text_id}")
        spoken_text = (
            f"Question number {NUMBER_WORDS[number]}. "
            f"{html.unescape(match.group(2))}"
        )
        questions.append((text_id, filename, spoken_text))

    print(f"Numbered questions: {len(questions)}")
    if args.dry_run:
        for text_id, filename, spoken_text in questions:
            print(f"{text_id}\t{filename}\t{spoken_text}")
        return

    async def generate() -> None:
        import edge_tts

        semaphore = asyncio.Semaphore(args.concurrency)
        with tempfile.TemporaryDirectory(prefix="adt-question-audio-") as tmp:
            tmpdir = Path(tmp)
            completed = 0

            async def render(text_id: str, filename: str, spoken_text: str) -> None:
                nonlocal completed
                async with semaphore:
                    mp3 = tmpdir / filename
                    last_error: Exception | None = None
                    for attempt in range(4):
                        try:
                            await edge_tts.Communicate(
                                spoken_text, args.voice, rate="-4%"
                            ).save(str(mp3))
                            break
                        except Exception as error:
                            last_error = error
                            mp3.unlink(missing_ok=True)
                            await asyncio.sleep(1.5 * (attempt + 1))
                    else:
                        raise RuntimeError(
                            f"TTS failed for {text_id}: {last_error}"
                        )
                    mp3.replace(I18N / "audio" / filename)
                    completed += 1
                    if completed % 25 == 0 or completed == len(questions):
                        print(f"Generated {completed}/{len(questions)}", flush=True)

            await asyncio.gather(*(render(*question) for question in questions))

    asyncio.run(generate())


if __name__ == "__main__":
    main()
