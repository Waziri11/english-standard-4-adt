#!/usr/bin/env python3
"""Speak "dash" only for placeholders embedded within readable sentences.

Standalone text fields remain silent. Inline ``[[blank:...]]`` markers and
printed placeholder runs keep their visible textbook text. Their narration is
rebuilt so a placeholder is spoken as "dash" only when readable text occurs
on both sides of it.
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
LITERAL_TOKEN_RE = re.compile(
    r'<span\s+class="sr-only"\s+data-adt-blank-audio="true"\s+'
    r'data-id="([^"]+)">(?:blank|dash)</span>',
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


def remove_literal_tokens(*, write: bool, section_ids: set[str]) -> list[str]:
    token_ids: list[str] = []
    for path in sorted(ROOT.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        title_match = TITLE_ID_RE.search(source)
        if not title_match:
            continue
        section_id = title_match.group(1)
        if section_ids and section_id not in section_ids:
            continue
        token_ids.extend(LITERAL_TOKEN_RE.findall(source))
        cleaned = LITERAL_TOKEN_RE.sub("", source)
        if write and cleaned != source:
            path.write_text(cleaned, encoding="utf-8")
    return token_ids


def replace_mid_sentence_placeholders(value: str, pattern: re.Pattern[str]) -> str:
    """Replace placeholders with 'dash' only when words occur on both sides."""
    pieces: list[str] = []
    position = 0
    for match in pattern.finditer(value):
        pieces.append(value[position : match.start()])
        left = value[: match.start()]
        right = value[match.end() :]
        pieces.append(" dash " if re.search(r"[A-Za-z0-9]", left) and re.search(r"[A-Za-z0-9]", right) else " ")
        position = match.end()
    pieces.append(value[position:])
    return "".join(pieces)


def spoken_text(value: str) -> str:
    value = html.unescape(TAG_RE.sub("", value))
    value = replace_mid_sentence_placeholders(value, BLANK_MARKER_RE)
    value = replace_mid_sentence_placeholders(value, PRINTED_BLANK_RE)
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
    token_ids = remove_literal_tokens(write=args.apply, section_ids=section_ids)
    existing_ids = candidate_existing_ids(texts, audios, section_ids)

    print(f"Standalone field narration tokens to remove: {len(token_ids)}")
    print(f"Inline or printed blank narration IDs: {len(existing_ids)}")

    if not args.apply:
        return

    for text_id in token_ids:
        for dedicated_id in (text_id, f"{text_id}_easy_read"):
            mapping = audios.pop(dedicated_id, "").split("?", 1)[0]
            texts.pop(dedicated_id, None)
            if mapping:
                (AUDIO / mapping).unlink(missing_ok=True)
    items: list[tuple[str, str, str]] = []
    for text_id in existing_ids:
        speech = spoken_text(texts[text_id])
        if speech:
            items.append((text_id, speech, audios[text_id]))
        else:
            mapping = audios.pop(text_id, "").split("?", 1)[0]
            if mapping:
                (AUDIO / mapping).unlink(missing_ok=True)

    save_json(texts_path, texts)
    save_json(audios_path, audios)

    asyncio.run(synthesize(items, args.concurrency))
    refresh_audio_versions(audios, [item[0] for item in items])
    save_json(audios_path, audios)


if __name__ == "__main__":
    main()
