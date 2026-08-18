#!/usr/bin/env python3
"""Ensure every ADT blank is explicitly spoken as "blank".

Literal text fields receive a screen-reader-only localized token immediately
before the field. Inline [[blank:...]] markers and printed placeholder runs
keep their visible textbook text, but their existing MP3 narration is rebuilt
with every placeholder spoken as "blank".
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
AUDIO = I18N / "audio"
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

TITLE_ID_RE = re.compile(r'<meta\s+name="title-id"\s+content="([^"]+)"')
FIELD_RE = re.compile(
    r'(?P<token><input\b(?=[^>]*\btype=["\']text["\'])[^>]*>|<textarea\b[^>]*>)',
    re.IGNORECASE,
)
EXISTING_TOKEN_RE = re.compile(
    r'<span\s+class="sr-only"\s+data-adt-blank-audio="true"\s+'
    r'data-id="([^"]+)">blank</span>\s*$',
    re.IGNORECASE,
)
BLANK_MARKER_RE = re.compile(r"\[\[blank:[^\]]+\]\]")
PRINTED_BLANK_RE = re.compile(r"(?<!\w)(?:_{3,}|-{3,}|\.{4,})(?!\w)")
TAG_RE = re.compile(r"<[^>]+>")


def load_json(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict[str, str]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def add_literal_tokens(*, write: bool) -> tuple[list[str], int]:
    token_ids: list[str] = []
    field_count = 0
    for path in sorted(ROOT.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        title_match = TITLE_ID_RE.search(source)
        if not title_match:
            continue
        section_id = title_match.group(1)
        next_number = 1
        for match in re.finditer(
            rf'data-id="{re.escape(section_id)}_blank_(\d{{3}})"', source
        ):
            next_number = max(next_number, int(match.group(1)) + 1)

        pieces: list[str] = []
        position = 0
        changed = False
        for match in FIELD_RE.finditer(source):
            field_count += 1
            prefix = source[position : match.start()]
            existing = EXISTING_TOKEN_RE.search(prefix)
            if existing:
                token_ids.append(existing.group(1))
                pieces.extend((prefix, match.group("token")))
            else:
                text_id = f"{section_id}_blank_{next_number:03d}"
                next_number += 1
                token_ids.append(text_id)
                token = (
                    f'<span class="sr-only" data-adt-blank-audio="true" '
                    f'data-id="{text_id}">blank</span>'
                )
                pieces.extend((prefix, token, match.group("token")))
                changed = True
            position = match.end()
        if changed:
            pieces.append(source[position:])
            if write:
                path.write_text("".join(pieces), encoding="utf-8")
    return token_ids, field_count


def spoken_text(value: str) -> str:
    value = html.unescape(TAG_RE.sub("", value))
    value = BLANK_MARKER_RE.sub(" blank ", value)
    value = PRINTED_BLANK_RE.sub(" blank ", value)
    return re.sub(r"\s+", " ", value).strip()


def candidate_existing_ids(texts: dict[str, str], audios: dict[str, str]) -> list[str]:
    return sorted(
        text_id
        for text_id, value in texts.items()
        if text_id in audios
        and (BLANK_MARKER_RE.search(value) or PRINTED_BLANK_RE.search(value))
    )


async def synthesize(items: list[tuple[str, str]], voice: str, concurrency: int) -> None:
    import edge_tts

    AUDIO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adt-blank-audio-") as temp:
        work = Path(temp)
        destinations: dict[str, list[str]] = {}
        for filename, speech in items:
            destinations.setdefault(speech, []).append(filename.split("?", 1)[0])
        semaphore = asyncio.Semaphore(concurrency)
        completed = 0

        async def render(index: int, speech: str, filenames: list[str]) -> None:
            nonlocal completed
            output = work / f"{index:05d}.mp3"
            async with semaphore:
                last_error: Exception | None = None
                for attempt in range(4):
                    try:
                        await edge_tts.Communicate(speech, voice, rate="-4%").save(str(output))
                        break
                    except Exception as error:
                        last_error = error
                        output.unlink(missing_ok=True)
                        await asyncio.sleep(1.5 * (attempt + 1))
                else:
                    raise RuntimeError(f"TTS failed for {speech!r}: {last_error}")
            for filename in filenames:
                shutil.copyfile(output, AUDIO / filename)
            completed += len(filenames)
            if completed % 50 < len(filenames) or completed == len(items):
                print(f"Generated {completed}/{len(items)} audio files", flush=True)

        await asyncio.gather(*(
            render(index, speech, filenames)
            for index, (speech, filenames) in enumerate(destinations.items(), 1)
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--voice", default="en-TZ-ImaniNeural")
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()

    texts_path = I18N / "texts.json"
    audios_path = I18N / "audios.json"
    texts = load_json(texts_path)
    audios = load_json(audios_path)
    token_ids, fields = add_literal_tokens(write=args.apply)
    existing_ids = candidate_existing_ids(texts, audios)

    print(f"Literal text fields/textareas: {fields}")
    print(f"Dedicated blank narration tokens: {len(token_ids)}")
    print(f"Inline or printed blank narration IDs: {len(existing_ids)}")

    if not args.apply:
        return

    for text_id in token_ids:
        texts[text_id] = "blank"
        texts[f"{text_id}_easy_read"] = "blank"
        audios[text_id] = f"{text_id}.mp3"
        audios[f"{text_id}_easy_read"] = f"{text_id}_easy_read.mp3"
    save_json(texts_path, texts)
    save_json(audios_path, audios)

    items: list[tuple[str, str]] = []
    for text_id in token_ids:
        items.append((audios[text_id], "blank"))
        items.append((audios[f"{text_id}_easy_read"], "blank"))
    for text_id in existing_ids:
        items.append((audios[text_id], spoken_text(texts[text_id])))

    # A filename should have only one source ID, but de-duplicate defensively.
    unique = list(dict.fromkeys(items))
    asyncio.run(synthesize(unique, args.voice, args.concurrency))


if __name__ == "__main__":
    main()
