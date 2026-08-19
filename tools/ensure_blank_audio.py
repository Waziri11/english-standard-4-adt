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
import hashlib
import html
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from rebuild_mixed_voice_audio import rebuild_one


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


def add_literal_tokens(*, write: bool, section_ids: set[str]) -> tuple[list[str], int]:
    token_ids: list[str] = []
    field_count = 0
    for path in sorted(ROOT.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        title_match = TITLE_ID_RE.search(source)
        if not title_match:
            continue
        section_id = title_match.group(1)
        if section_ids and section_id not in section_ids:
            continue
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


def candidate_existing_ids(
    texts: dict[str, str], audios: dict[str, str], section_ids: set[str]
) -> list[str]:
    allowed_ids: set[str] = set()
    if section_ids:
        for path in ROOT.glob("*.html"):
            source = path.read_text(encoding="utf-8")
            title_match = TITLE_ID_RE.search(source)
            if title_match and title_match.group(1) in section_ids:
                ids = set(re.findall(r'data-id="([^"]+)"', source))
                allowed_ids.update(ids)
                allowed_ids.update(f"{text_id}_easy_read" for text_id in ids)
    return sorted(
        text_id
        for text_id, value in texts.items()
        if text_id in audios
        and (not section_ids or text_id in allowed_ids)
        and (BLANK_MARKER_RE.search(value) or PRINTED_BLANK_RE.search(value))
    )


async def synthesize(items: list[tuple[str, str, str]], concurrency: int) -> None:
    import edge_tts

    AUDIO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adt-blank-audio-") as temp:
        work = Path(temp)
        semaphore = asyncio.Semaphore(concurrency)
        completed = 0

        async def render(text_id: str, speech: str, filename: str) -> None:
            nonlocal completed
            clean_filename = filename.split("?", 1)[0]
            await rebuild_one(
                edge_tts, text_id, speech, clean_filename, work, semaphore
            )
            completed += 1
            if completed % 25 == 0 or completed == len(items):
                print(f"Generated {completed}/{len(items)} audio files", flush=True)

        await asyncio.gather(*(render(*item) for item in items))


def refresh_audio_versions(audios: dict[str, str], text_ids: list[str]) -> None:
    for text_id in text_ids:
        filename = audios[text_id].split("?", 1)[0]
        digest = hashlib.sha256((AUDIO / filename).read_bytes()).hexdigest()[:12]
        audios[text_id] = f"{filename}?v={digest}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument(
        "--sections",
        default="",
        help="Comma-separated exact section IDs; omit to process the whole book",
    )
    args = parser.parse_args()

    texts_path = I18N / "texts.json"
    audios_path = I18N / "audios.json"
    texts = load_json(texts_path)
    audios = load_json(audios_path)
    section_ids = {value.strip() for value in args.sections.split(",") if value.strip()}
    token_ids, fields = add_literal_tokens(write=args.apply, section_ids=section_ids)
    existing_ids = candidate_existing_ids(texts, audios, section_ids)

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

    items: list[tuple[str, str, str]] = []
    for text_id in token_ids:
        items.append((text_id, "blank", audios[text_id]))
        items.append((f"{text_id}_easy_read", "blank", audios[f"{text_id}_easy_read"]))
    for text_id in existing_ids:
        items.append((text_id, spoken_text(texts[text_id]), audios[text_id]))

    asyncio.run(synthesize(items, args.concurrency))
    refresh_audio_versions(audios, [item[0] for item in items])
    save_json(audios_path, audios)


if __name__ == "__main__":
    main()
