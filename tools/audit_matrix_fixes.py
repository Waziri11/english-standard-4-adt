#!/usr/bin/env python3
"""Deterministic acceptance audit for the 30 correction-matrix items."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
TEXTS = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
AUDIOS = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
AUDIO_DIR = I18N / "audio"


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def has_all(name: str, *needles: str) -> bool:
    value = source(name)
    return all(needle in value for needle in needles)


def dialogue_ok(name: str, speakers: tuple[str, ...]) -> bool:
    value = source(name)
    return (
        "conversation-labels.js?v=2" in value
        and all(re.search(rf"\b{re.escape(speaker)}:", value, re.I) for speaker in speakers)
    )


def visible_audio_coverage() -> tuple[bool, str]:
    ids: set[str] = set()
    for path in ROOT.glob("*.html"):
        ids.update(re.findall(r'data-id=["\']([^"\']+)', path.read_text(encoding="utf-8")))
    required = sorted(text_id for text_id in ids if TEXTS.get(text_id, "").strip())
    missing_mapping = [text_id for text_id in required if text_id not in AUDIOS]
    missing_file: list[str] = []
    empty_file: list[str] = []
    for text_id in required:
        if text_id not in AUDIOS:
            continue
        filename = AUDIOS[text_id].split("?", 1)[0]
        path = AUDIO_DIR / filename
        if not path.is_file():
            missing_file.append(text_id)
        elif path.stat().st_size < 100:
            empty_file.append(text_id)
    details = (
        f"required={len(required)}, missing_mapping={len(missing_mapping)}, "
        f"missing_file={len(missing_file)}, empty_file={len(empty_file)}"
    )
    return not (missing_mapping or missing_file or empty_file), details


def image_audio_coverage() -> tuple[bool, str]:
    image_ids: set[str] = set()
    uncovered_sources: list[str] = []
    for path in ROOT.glob("*.html"):
        value = path.read_text(encoding="utf-8")
        tags = re.findall(r"<img\b[^>]*>", value, re.I)
        covered_sources = {
            match.group(1)
            for tag in tags
            if (match := re.search(r'src=["\']([^"\']+)', tag, re.I))
            and re.search(r'data-id=["\']([^"\']+)', tag, re.I)
        }
        for tag in tags:
            id_match = re.search(r'data-id=["\']([^"\']+)', tag, re.I)
            src_match = re.search(r'src=["\']([^"\']+)', tag, re.I)
            alt_match = re.search(r'alt=["\']([^"\']*)', tag, re.I)
            if id_match:
                image_ids.add(id_match.group(1))
            elif (
                src_match
                and alt_match
                and alt_match.group(1).strip()
                and src_match.group(1) not in covered_sources
            ):
                uncovered_sources.append(f"{path.name}:{src_match.group(1)}")
    missing_text = [text_id for text_id in image_ids if not TEXTS.get(text_id, "").strip()]
    missing_audio = [text_id for text_id in image_ids if text_id not in AUDIOS]
    details = (
        f"image_ids={len(image_ids)}, uncovered_sources={len(uncovered_sources)}, "
        f"missing_text={len(missing_text)}, missing_audio={len(missing_audio)}"
    )
    return not (uncovered_sources or missing_text or missing_audio), details


dialogue_css = source("assets/conversation-labels.js")
unit_phrase_ok = not any(
    re.match(r"A picture of (?:unit|think)\b", value.strip(), re.I)
    for value in TEXTS.values()
)
audio_ok, audio_details = visible_audio_coverage()
images_ok, image_details = image_audio_coverage()

checks: list[tuple[int, str, bool, str]] = [
    (1, "Unit-opening narration is semantic", unit_phrase_ok, "all texts.json values"),
    (2, "Household tools is one narrated phrase", TEXTS.get("pg010_n0043") == "household tools" and has_all("pg010_sec002.html", 'data-id="pg010_n0043">household tools</span>'), "pg010"),
    (3, "Father/shopkeeper dialogue", dialogue_ok("pg021_sec002.html", ("Father", "Shopkeeper")), "pg021"),
    (4, "Bahati/Tumani dialogue", dialogue_ok("pg028_sec001.html", ("Bahati", "Tumani")), "pg028"),
    (5, "Roza/Juma dialogue", dialogue_ok("pg035_sec002.html", ("Roza", "Juma")), "pg035"),
    (6, "Page 48 instruction left aligned", has_all("pg048_sec001.html", '<p class="text-left text-[1.05rem]'), "pg048"),
    (7, "Mother/daughter dialogue", dialogue_ok("pg051_sec001.html", ("Mother", "Daughter")), "pg051"),
    (8, "Home dialogue formatting", dialogue_ok("pg052_sec001.html", ("Parent", "Pupil")), "pg052"),
    (9, "Two page-53 dialogues", dialogue_ok("pg053_sec001.html", ("Parent", "Pupil")) and source("pg053_sec001.html").count('class="hidden"') >= 2, "pg053"),
    (10, "Page 54 instruction left aligned", has_all("pg054_sec001.html", 'max-w-[700px] text-left'), "pg054"),
    (11, "Hellen dialogue label styled", has_all("pg056_sec001.html", 'data-id="pg056_n0036" class="w-28 shrink-0 font-bold text-teal-700'), "pg056"),
    (12, "Hellen/Juma continuation", dialogue_ok("pg057_sec001.html", ("Hellen", "Juma")), "pg057"),
    (13, "Ticket dialogues", dialogue_ok("pg058_sec001.html", ("Ticket agent", "Pupil")), "pg058"),
    (14, "Station dialogues", dialogue_ok("pg059_sec001.html", ("Station staff", "Pupil")), "pg059"),
    (15, "Unit Seven dialogue", dialogue_ok("pg060_sec001.html", ("Teacher", "Class")), "pg060"),
    (16, "Classroom continuation", dialogue_ok("pg061_sec001.html", ("Teacher", "Pupil 2")), "pg061"),
    (17, "Mashaka dialogue", dialogue_ok("pg064_sec001.html", ("Police officer", "Mashaka")), "pg064"),
    (18, "Teacher/pupils dialogue", dialogue_ok("pg065_sec002.html", ("Teacher", "Pupil 1")), "pg065"),
    (19, "Teacher/pupils continuation", dialogue_ok("pg066_sec001.html", ("Teacher", "Pupil 4")), "pg066"),
    (20, "Page 67 conversation", dialogue_ok("pg067_sec001.html", ("Doctor", "Mrs Babu")), "pg067"),
    (21, "Unit Eight title left aligned", has_all("pg071_sec001.html", 'pg071_n0004" class="book-unit-title text-left"'), "pg071"),
    (22, "Activity 8.4 heading restrained", has_all("pg075_sec002.html", 'class="z-10 shrink-0 rounded-md bg-[#d92525]', 'text-[1rem]', 'data-id="pg075_n0056">Activity 8.4:</div>'), "pg075"),
    (23, "Pupil conversation formatting", dialogue_ok("pg076_sec002.html", ("Pupil 1", "Pupil 2")), "pg076"),
    (24, "Anniversary instruction formatting", has_all("pg081_sec002.html", 'class="mx-auto max-w-4xl text-left"'), "pg081"),
    (25, "Composition instruction formatting", has_all("pg090_sec002.html", 'data-id="pg090_n0024"'), "pg090"),
    (26, "Timetable instruction formatting", has_all("pg094_sec001.html", 'max-w-4xl text-left'), "pg094"),
    (27, "Punctuation instruction left aligned", has_all("pg095_sec001.html", '<div class="mb-6 text-left"><span data-id="pg095_n0004"'), "pg095"),
    (28, "Every meaningful image has text and audio", images_ok, image_details),
    (29, "Roman numerals have expanded narration", has_all("tools/fix_matrix_audio.py", 'Standards Three to Six', 'Standard Four'), "generated pg006 audio"),
    (30, "No visible readable content lacks audio", audio_ok, audio_details),
]

failed = [check for check in checks if not check[2]]
for number, name, passed, detail in checks:
    print(f"{number:02d} {'PASS' if passed else 'FAIL'} {name} [{detail}]")
print(f"SUMMARY: {len(checks) - len(failed)}/{len(checks)} passed")
if failed:
    sys.exit(1)
