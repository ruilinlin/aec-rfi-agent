"""Export the FastAPI app's OpenAPI spec deterministically.

Usage (from the repo root):
    .venv/bin/python scripts/export_openapi.py [--out path/to/openapi.json]

sort_keys + fixed indent make the output byte-stable for identical code, so
the consuming frontend repo (aec-rfi-console) can diff snapshots meaningfully.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="write here instead of stdout")
    args = parser.parse_args()

    from src.api.main import app

    spec = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(spec)
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
