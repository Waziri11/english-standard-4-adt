#!/usr/bin/env python3
"""Regenerate Column B audio so option letters are spoken."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
sys.path.insert(0, str(ROOT / "tools" / "_vendor"))
sys.path.insert(0, str(ROOT / "tools"))

from rebuild_mixed_voice_audio import rebuild_one

IDS = ("pg012_n0033", "pg012_n0041", "pg012_n0049", "pg012_n0057", "pg012_n0065")


async def main() -> None:
    import edge_tts

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    items = [(text_id, texts[text_id], audios[text_id]) for text_id in IDS]
    items += [
        (f"{text_id}_easy_read", texts[f"{text_id}_easy_read"], audios[f"{text_id}_easy_read"])
        for text_id in IDS
    ]
    semaphore = asyncio.Semaphore(4)
    with tempfile.TemporaryDirectory(prefix="adt-pg012-column-b-", dir="/tmp") as temp:
        await asyncio.gather(*(
            rebuild_one(edge_tts, text_id, text, filename, Path(temp), semaphore)
            for text_id, text, filename in items
        ))
    print(f"Generated {len(items)} Column B audio files.")


if __name__ == "__main__":
    asyncio.run(main())
