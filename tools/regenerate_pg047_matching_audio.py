#!/usr/bin/env python3
"""Generate the ordered Column A and Column B narration for page 47."""

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

IDS = [f"pg047_n{number:04d}" for number in range(40, 52)]


async def main() -> None:
    import edge_tts

    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    semaphore = asyncio.Semaphore(4)
    with tempfile.TemporaryDirectory(prefix="adt-pg047-matching-", dir="/tmp") as temp:
        work = Path(temp)
        await asyncio.gather(*(
            rebuild_one(edge_tts, text_id, texts[text_id], audios[text_id], work, semaphore)
            for text_id in IDS
        ))
    print(f"Generated {len(IDS)} matching-activity audio files.")


if __name__ == "__main__":
    asyncio.run(main())
