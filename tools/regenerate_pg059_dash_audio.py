#!/usr/bin/env python3
"""Regenerate page 58 or 59 audio so ellipsis placeholders are spoken as "dash"."""

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "content" / "i18n" / "en"
VENDOR = ROOT / "tools" / "_vendor"
sys.path.insert(0, str(VENDOR))

PAGE_NUMBERS = {
    "058": ("0018", "0020", "0022", "0026", "0027", "0028", "0029", "0030", "0031"),
    "059": ("0006", "0008", "0010", "0016", "0018", "0024", "0026", "0028", "0038"),
}


async def main() -> None:
    import edge_tts

    parser = argparse.ArgumentParser()
    parser.add_argument("page", choices=PAGE_NUMBERS)
    args = parser.parse_args()
    text_ids = tuple(
        f"pg{args.page}_n{number}{suffix}"
        for number in PAGE_NUMBERS[args.page]
        for suffix in ("", "_easy_read")
    )
    texts = json.loads((I18N / "texts.json").read_text(encoding="utf-8"))
    audios_path = I18N / "audios.json"
    audios = json.loads(audios_path.read_text(encoding="utf-8"))
    semaphore = asyncio.Semaphore(4)

    with tempfile.TemporaryDirectory(prefix=f"adt-pg{args.page}-dash-", dir="/tmp") as temp:
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
