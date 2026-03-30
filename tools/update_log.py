# tools/update_log.py
from pathlib import Path
import sys, json
from datetime import datetime

LOG_PATH = Path("docs/PROJECT_LOG.md")

def append_entry(title: str, content: str):
    now = datetime.utcnow().isoformat() + "Z"
    entry = f"\n### {now} — {title}\n\n{content}\n"
    LOG_PATH.write_text(LOG_PATH.read_text(encoding="utf-8") + entry)
    print("Appended log")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/update_log.py \"Title\" \"content text\"")
        sys.exit(1)
    append_entry(sys.argv[1], sys.argv[2])
