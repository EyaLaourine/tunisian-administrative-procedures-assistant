"""Counts spoken words per member and per slide in SPEAKER_NOTES.md and estimates durations.

usage: python presentation/check_timing.py [--wpm 135]
Only the main talk (slides 1-19) is timed; stage directions in *(...)* are excluded. Member 6 adds the live
demo time (DEMO_SECONDS) on top of the spoken words.
"""

import argparse
import json
import re
from pathlib import Path

NOTES = Path(__file__).with_name("SPEAKER_NOTES.md")
DEMO_SECONDS = 90  # slide 16 lasts max(narration, 90 s): the presenter narrates while the bot answers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wpm", type=float, default=135)
    args = ap.parse_args()
    text = NOTES.read_text(encoding="utf-8").split("## Backup slides")[0]
    members = re.split(r"^## (Member \d)[^\n]*\n", text, flags=re.M)
    out, t = [], 0.0
    for name, body in zip(members[1::2], members[2::2]):
        slides = re.split(r"^### Slide (\d+)[^\n]*\n", body, flags=re.M)
        rows = []
        for n, s in zip(slides[1::2], slides[2::2]):
            spoken = re.sub(r"\*\([^)]*\)\*", "", s)
            words = len(re.findall(r"[\w'’-]+", spoken))
            sec = words / args.wpm * 60
            rows.append({"slide": int(n), "words": words, "start": round(t), "seconds": round(sec)})
            t += sec
        narration = next((r["seconds"] for r in rows if r["slide"] == 16), 0)
        extra = max(0, DEMO_SECONDS - narration) if name == "Member 6" else 0
        if extra:
            rows.append({"slide": 16, "words": 0, "start": round(t), "seconds": extra, "note": "demo time beyond narration"})
            t += extra
        total = sum(r["seconds"] for r in rows)
        out.append({"member": name, "words": sum(r["words"] for r in rows), "seconds": total, "slides": rows})
    print(json.dumps({"wpm": args.wpm, "members": out, "total_seconds": round(t), "total_mmss": f"{int(t // 60)}:{int(t % 60):02d}"}, indent=1))


if __name__ == "__main__":
    main()
