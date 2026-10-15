"""Build a clean GitHub-ready ZIP. No secrets, runtime state or git metadata."""

import argparse
import zipfile
from pathlib import Path

EXCLUDED = {
    ".git",
    ".venv",
    ".servicepilot",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "reports",
    "out",
    "node_modules",
}
parser = argparse.ArgumentParser()
parser.add_argument("--output", default="dist/servicepilot.zip")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = Path(args.output).resolve()
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.name == ".coverage" or path.suffix in {".db", ".pyc", ".zip"}:
            continue
        archive.write(path, Path("servicepilot") / relative)
print(output)
