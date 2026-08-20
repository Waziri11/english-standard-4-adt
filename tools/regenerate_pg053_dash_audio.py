#!/usr/bin/env python3
"""Regenerate page 53 audio so ellipsis placeholders are spoken as "dash"."""

import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
sys.path.insert(0, str(ROOT / "tools" / "_vendor"))

TEXT_IDS = (
    "pg053_n0007",
    "pg053_n0012",
    "pg053_n0013",
    "pg053_n0017",
    "pg053_n0024",
    "pg053_n0028",
    "pg053_n0032",
)


async def main() -> None:
    import edge_tts

    text_ids = tuple(
        f"{text_id}{suffix}"
        for text_id in TEXT_IDS
        for suffix in ("", "_easy_read")
    )
    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios_path = I18N / "audios.json"
    audios = json.loads(audios_path.read_text(encoding="utf-8"))
    semaphore = asyncio.Semaphore(4)

    with tempfile.TemporaryDirectory(prefix="adt-pg053-dash-", dir="/tmp") as temp:
        work = Path(temp)

        async def render(text_id: str) -> None:
            filename = audios[text_id].split("?", 1)[0]
            temporary = work / filename
            async with semaphore:
                await edge_tts.Communicate(
                    texts[text_id], "en-TZ-ImaniNeural", rate="-4%"
                ).save(str(temporary))
            target = I18N / "audio" / filename
            temporary.replace(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
            audios[text_id] = f"{filename}?v={digest}"
            print(f"Generated {text_id}")

        await asyncio.gather(*(render(text_id) for text_id in text_ids))

    audios_path.write_text(
        json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
