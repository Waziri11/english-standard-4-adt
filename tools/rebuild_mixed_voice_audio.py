#!/usr/bin/env python3
"""Audit and rebuild English narration containing Swahili/Tanzanian terms.

English segments use en-TZ-ImaniNeural.  Swahili names, place names, and
borrowed nouns use sw-TZ-RehemaNeural.  The visible textbook text is untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
VENDOR = ROOT / "tools" / "_vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

ENGLISH_VOICE = "en-TZ-ImaniNeural"
SWAHILI_VOICE = "sw-TZ-RehemaNeural"

# Audited against every value in texts.json.  This intentionally contains only
# Tanzanian/Swahili names, locations, institutions, and Swahili lexical nouns.
# International English names (for example Sarah, John, Jane, and Naomi) stay
# with Imani.  Multiword entries are matched before their component words.
SWAHILI_TERMS = {
    # People and locally used character names.
    "Aika", "Ali", "Amani", "Amina", "Amon", "Aneth", "Asheli", "Ashura", "Asha",
    "Asukile", "Atu", "Babu", "Bahati", "Baraka", "Chakupewa", "Fikiri", "Gaspadus",
    "Gwakisa", "Halima", "Hamisi", "Hassan", "Hawa", "Hemed", "Iku", "Juma", "Kejo", "Kemy",
    "Kidoti", "Kipara", "Kipepe", "Kisanga", "Komba", "Lyabwene", "Maganga",
    "Magwaya", "Majara", "Makanjila", "Makelo", "Malea", "Mambo", "Mashaka",
    "Maweta", "Mbuke", "Mego", "Mkulia", "Msola", "Msimbe", "Mussa",
    "Mwanaidi", "Mwenda", "Mwikaje", "Mwombeki", "Mwandomola", "Mtahabwa",
    "Nangi", "Ndulila", "Neema", "Nengai", "Nkane", "Nyamizi", "Nyoni",
    "Oddo", "Olewado", "Omari", "Pendo", "Rehema", "Rejo", "Roza", "Sadick",
    "Safia", "Saleh", "Samwel", "Seko", "Tumaini", "Tumani", "Wawar",
    "Yambongo", "Yobu", "Yohana",
    # Tanzanian place, school, market, road, and institutional names.
    "Ali Hassan Mwinyi", "Dar es Salaam", "Historia ya Tanzania na Maadili",
    "Dodoma", "Ipole", "Kilimatinde", "Kilimanjaro", "Kigoma", "Kiswahili",
    "Mabo", "Mbeje", "Mikocheni", "Mikumi", "Mikunguni", "Mkulima", "Mkunguni",
    "Morogoro", "Moshi", "Mseto", "Mtakuja", "Mtani", "Mto wa mbu", "Mtoni",
    "Mwembeni", "Nduruma", "Nguruka", "Nkalama", "Pelalu", "Rau", "Serengeti",
    "Tambukareli", "Tanzania", "Tupendane", "Itilima",
    # Swahili food/culture/common nouns appearing in the English book.
    "chapatti", "makande", "mama", "pilau", "shamba", "Tsh", "Tshs", "ugali",
}

TAG_RE = re.compile(r"<[^>]+>")
BLANK_RE = re.compile(r"\[\[blank:[^\]]+\]\]")


def clean_speech_text(value: str) -> str:
    value = html.unescape(TAG_RE.sub("", value))
    value = BLANK_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def term_pattern() -> re.Pattern[str]:
    alternatives = "|".join(re.escape(term) for term in sorted(SWAHILI_TERMS, key=len, reverse=True))
    # Possessive suffixes remain in the Rehema segment (Nyoni's / Nyoni’s).
    return re.compile(rf"(?<![A-Za-z])(?:{alternatives})(?:['’]s)?(?![A-Za-z])", re.IGNORECASE)


TERM_RE = term_pattern()


def split_voices(value: str) -> list[tuple[str, str]]:
    """Return adjacent (voice, text) segments, preserving the complete text."""
    spoken = clean_speech_text(value)
    segments: list[tuple[str, str]] = []
    position = 0
    for match in TERM_RE.finditer(spoken):
        if match.start() > position:
            segments.append((ENGLISH_VOICE, spoken[position:match.start()]))
        segments.append((SWAHILI_VOICE, match.group()))
        position = match.end()
    if position < len(spoken):
        segments.append((ENGLISH_VOICE, spoken[position:]))
    return [(voice, text) for voice, text in segments if text]


def affected_items(texts: dict[str, str], audios: dict[str, str]) -> list[tuple[str, str, str]]:
    return [
        (key, value, audios[key])
        for key, value in texts.items()
        if key in audios and TERM_RE.search(clean_speech_text(value))
    ]


async def synthesize_segment(edge_tts, voice: str, text: str, output: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate="-4%").save(str(output))
            return
        except Exception as error:  # network-dependent retry
            last_error = error
            output.unlink(missing_ok=True)
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {voice}: {text!r}: {last_error}")


async def rebuild_one(edge_tts, key: str, visible: str, filename: str,
                      work: Path, semaphore: asyncio.Semaphore) -> None:
    segments = split_voices(visible)
    target = I18N / "audio" / filename
    async with semaphore:
        segment_files: list[Path] = []
        for index, (voice, text) in enumerate(segments):
            segment = work / f"{key}-{index:03d}.mp3"
            await synthesize_segment(edge_tts, voice, text, segment)
            segment_files.append(segment)

        joined = work / f"{key}-joined.mp3"
        if len(segment_files) == 1:
            shutil.copyfile(segment_files[0], joined)
        else:
            inputs: list[str] = []
            for segment in segment_files:
                inputs.extend(["-i", str(segment)])
            filter_graph = "".join(f"[{i}:a]" for i in range(len(segment_files)))
            filter_graph += f"concat=n={len(segment_files)}:v=0:a=1[out]"
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", *inputs,
                 "-filter_complex", filter_graph, "-map", "[out]", "-ar", "24000",
                 "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "64k", str(joined)],
                check=True,
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        joined.replace(target)


async def generate(items: list[tuple[str, str, str]], concurrency: int) -> None:
    import edge_tts

    semaphore = asyncio.Semaphore(concurrency)
    with tempfile.TemporaryDirectory(prefix="adt-mixed-voice-", dir="/tmp") as temp:
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
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ids", default="", help="Comma-separated exact text IDs")
    parser.add_argument("--report", type=Path, help="Write the complete JSON audit report")
    args = parser.parse_args()

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    items = affected_items(texts, audios)
    requested = {item.strip() for item in args.ids.split(",") if item.strip()}
    if requested:
        items = [item for item in items if item[0] in requested]
    if args.limit:
        items = items[:args.limit]

    counts: Counter[str] = Counter()
    report_items = []
    for key, visible, filename in items:
        hits = [match.group() for match in TERM_RE.finditer(clean_speech_text(visible))]
        counts.update(hit.casefold().replace("’", "'").removesuffix("'s") for hit in hits)
        report_items.append({"id": key, "audio": filename, "terms": hits,
                             "segments": split_voices(visible)})
    report = {
        "english_voice": ENGLISH_VOICE,
        "swahili_voice": SWAHILI_VOICE,
        "affected_audio_ids": len(items),
        "term_counts": dict(sorted(counts.items())),
        "items": report_items,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "items"},
                     ensure_ascii=False, indent=2))
    if args.generate:
        asyncio.run(generate(items, args.concurrency))


if __name__ == "__main__":
    main()
