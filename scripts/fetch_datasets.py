"""Download the free external datasets used for evaluation (see DATASETS.md).

    python scripts/fetch_datasets.py                 # FLEURS 50 clips/lang + AI4I 2020
    python scripts/fetch_datasets.py --fleurs-n 200  # bigger WER benchmark

Everything goes to data/external/ (git-ignored: licences require attribution, and
audio doesn't belong in git). FLEURS audio ships as one large .tar.gz per split;
it is read as a stream and the download stops after the first N clips, so 50
clips cost ~20 MB instead of ~570 MB.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external"
FLEURS = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/{lang}/{name}"
FLEURS_LANGS = {"de": "de_de", "en": "en_us"}
AI4I_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
UA = {"User-Agent": "voice-assistant-dataset-fetch/1.0"}


def _open(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)


def fetch_fleurs(n: int, split: str) -> None:
    csv.field_size_limit(10**7)
    for short, lang in FLEURS_LANGS.items():
        dest = OUT / "fleurs" / short
        dest.mkdir(parents=True, exist_ok=True)

        # TSV columns: id, file, raw_transcription, transcription, phonemes, num_samples, gender
        with _open(FLEURS.format(lang=lang, name=f"{split}.tsv")) as r:
            rows = list(csv.reader(io.TextIOWrapper(r, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
        meta = {row[1]: row for row in rows}

        got: list[dict] = []
        with _open(FLEURS.format(lang=lang, name=f"audio/{split}.tar.gz")) as r, \
                tarfile.open(fileobj=r, mode="r|gz") as tar:
            for member in tar:
                name = Path(member.name).name
                if not member.isfile() or name not in meta:
                    continue
                src = tar.extractfile(member)
                with open(dest / name, "wb") as f:
                    shutil.copyfileobj(src, f)
                row = meta[name]
                got.append({
                    "id": row[0], "file": f"{short}/{name}", "language": short,
                    "reference": row[2], "reference_normalized": row[3],
                    "seconds": round(int(row[5]) / 16000, 2), "gender": row[6],
                })
                if len(got) >= n:
                    break  # stop the stream: no need to download the rest

        with open(dest / "manifest.jsonl", "w", encoding="utf-8") as f:
            for rec in got:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"FLEURS {lang} {split}: {len(got)} clips -> {dest.relative_to(ROOT)}")


def fetch_ai4i() -> None:
    dest = OUT / "ai4i2020.csv"
    with _open(AI4I_URL) as r:
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        dest.write_bytes(z.read(name).decode("utf-8-sig").encode("utf-8"))  # drop BOM
    lines = dest.read_text(encoding="utf-8").splitlines()
    print(f"AI4I 2020: {len(lines) - 1} rows -> {dest.relative_to(ROOT)}\n  columns: {lines[0]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleurs-n", type=int, default=50, help="clips per language")
    ap.add_argument("--fleurs-split", default="test", choices=["dev", "test"])
    ap.add_argument("--skip-fleurs", action="store_true")
    ap.add_argument("--skip-ai4i", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.skip_fleurs:
        fetch_fleurs(args.fleurs_n, args.fleurs_split)
    if not args.skip_ai4i:
        fetch_ai4i()


if __name__ == "__main__":
    main()
