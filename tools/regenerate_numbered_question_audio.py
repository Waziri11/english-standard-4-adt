#!/usr/bin/env python3
"""Regenerate numbered-question audio with an explicit "Question number …" lead-in."""

import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
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
    parser.add_argument("--voice", default="Samantha")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    questions = []
    for text_id, visible_text in texts.items():
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

    with tempfile.TemporaryDirectory(prefix="adt-question-audio-") as tmp:
        tmpdir = Path(tmp)
        for index, (text_id, filename, spoken_text) in enumerate(questions, 1):
            aiff = tmpdir / f"{text_id}.aiff"
            mp3 = tmpdir / filename
            subprocess.run(
                ["say", "-v", args.voice, "-o", str(aiff), spoken_text], check=True
            )
            subprocess.run(
                [
                    "ffmpeg", "-loglevel", "error", "-y", "-i", str(aiff),
                    "-ar", "24000", "-ac", "1", "-codec:a", "libmp3lame",
                    "-b:a", "64k", str(mp3),
                ],
                check=True,
            )
            mp3.replace(I18N / "audio" / filename)
            if index % 25 == 0 or index == len(questions):
                print(f"Generated {index}/{len(questions)}")


if __name__ == "__main__":
    main()
