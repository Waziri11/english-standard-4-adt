#!/usr/bin/env python3
"""Generate the ordered Column A and Column B narration for page 47."""

import asyncio
import json
import shutil
import subprocess
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


def offline_main() -> None:
    audios = json.loads((I18N / "audios.json").read_text(encoding="utf-8"))
    audio_dir = I18N / "audio"
    shutil.copyfile(audio_dir / "pg012_n0022.mp3", audio_dir / audios["pg047_n0040"])
    shutil.copyfile(audio_dir / "pg012_n0025.mp3", audio_dir / audios["pg047_n0046"])

    # The original five clips contain "Column A sentence — Column B sentence"
    # with a clear pause between them. Split at those pauses, retaining the
    # book's original Tanzanian-English narration and pronunciation.
    splits = {
        32: (2.96925, 3.925417),
        33: (1.679875, 2.649833),
        34: (2.369458, 3.357292),
        35: (2.114792, 3.0615),
        36: (2.97625, 3.924),
    }
    for offset, (source_number, (first_end, second_start)) in enumerate(splits.items()):
        source = audio_dir / f"pg047_n{source_number:04d}.mp3"
        for target_id, start, end in (
            (f"pg047_n{41 + offset:04d}", None, first_end),
            (f"pg047_n{47 + offset:04d}", second_start, None),
        ):
            target = audio_dir / audios[target_id]
            command = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source)]
            if start is not None:
                command.extend(["-ss", str(start)])
            if end is not None:
                command.extend(["-to", str(end)])
            command.extend(["-codec:a", "copy", str(target)])
            subprocess.run(command, check=True)
    print(f"Generated {len(IDS)} matching-activity audio files offline.")


if __name__ == "__main__":
    if "--offline" in sys.argv:
        offline_main()
    else:
        asyncio.run(main())
