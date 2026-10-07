"""Exercise the live cloud content builder without scheduling any posts."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if not os.environ.get("CARDTRADER_API_TOKEN"):
        raise SystemExit("Manca CARDTRADER_API_TOKEN")
    with tempfile.TemporaryDirectory(prefix="pullradar-check-") as scratch:
        work = Path(scratch)
        for name in ("pullradar.py", "italian_prices.py", "editorial.py", "cards.json"):
            shutil.copy2(ROOT / name, work / name)
        shutil.copytree(ROOT / "art", work / "art")
        environment = os.environ.copy()
        environment.pop("PULLRADAR_TEST_FIXTURE", None)
        subprocess.run([sys.executable, "pullradar.py", "prepare"], cwd=work,
                       env=environment, check=True)
        plan = json.loads((work / "plan.json").read_text())
        items = plan["items"]
        assert plan["source"] == "live"
        assert len([item for item in items if item["type"] == "post"]) == 3
        assert len([item for item in items if item["type"] == "story"]) == 2
        assert len(plan["cards"]) >= 3
        for card in plan["cards"]:
            assert card["price"] > 0 and card["offers"] >= 5
            assert card["previous"] is None or card["previous"] > 0
        for item in items:
            files = [work / name for name in item["files"]]
            assert all(path.is_file() and path.stat().st_size > 0 for path in files)
            if item["type"] == "post":
                assert len(files) == 3
                digests = [hashlib.sha256(path.read_bytes()).digest() for path in files]
                assert len(set(digests)) == 3, f"Slide duplicate: {item['key']}"
                assert "€" in item["caption"] and "italian" in item["caption"].lower()
        print("Controllo completo: 3 caroselli con slide diverse, 2 storie, prezzi italiani live.")


if __name__ == "__main__":
    main()
