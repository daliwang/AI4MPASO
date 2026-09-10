"""Month-aligned 50→600 yr pair table.

The on-disk index is portable: pair_id / years / month / split / npz name.
Frontier absolute paths are reconstructed from ``oceanai.paths`` only when
extracting from raw restarts.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from oceanai.paths import early_rst, late_rst, processed_dirs

INDEX_FIELDS = ("pair_id", "year_x", "year_y", "month", "split", "npz")


def build_pair_index() -> list[dict]:
    rows = []
    for early_year in range(51, 56):
        late_year = early_year + 550
        split = "holdout" if early_year == 55 else "train"
        for month in range(1, 13):
            px = early_rst(early_year, month)
            py = late_rst(late_year, month)
            if not px.exists():
                raise FileNotFoundError(px)
            if not py.exists():
                raise FileNotFoundError(py)
            pid = f"{early_year:04d}-{month:02d}"
            rows.append(
                {
                    "pair_id": pid,
                    "year_x": early_year,
                    "year_y": late_year,
                    "month": month,
                    "split": split,
                    "npz": f"{pid}.npz",
                    "path_x": str(px),
                    "path_y": str(py),
                }
            )
    return rows


def portable_row(row: dict) -> dict:
    pid = row["pair_id"]
    return {
        "pair_id": pid,
        "year_x": int(row["year_x"]),
        "year_y": int(row.get("year_y", int(row["year_x"]) + 550)),
        "month": int(row["month"]),
        "split": row["split"],
        "npz": row.get("npz", f"{pid}.npz"),
    }


def write_portable_index(rows: list[dict], pairs_dir: Path) -> Path:
    portable = [portable_row(r) for r in rows]
    pairs_dir = Path(pairs_dir)
    pairs_dir.mkdir(parents=True, exist_ok=True)
    csv_path = pairs_dir / "index.csv"
    json_path = pairs_dir / "index.json"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(INDEX_FIELDS))
        w.writeheader()
        w.writerows(portable)
    json_path.write_text(json.dumps(portable, indent=2))
    n_train = sum(r["split"] == "train" for r in portable)
    n_hold = sum(r["split"] == "holdout" for r in portable)
    print(f"wrote {len(portable)} pairs ({n_train} train / {n_hold} holdout) → {csv_path}")
    return csv_path


def write_pair_index(rows: list[dict] | None = None, root: Path | None = None) -> Path:
    rows = rows or build_pair_index()
    return write_portable_index(rows, processed_dirs(root)["pairs"])


def load_pair_index(root: Path | None = None) -> list[dict]:
    path = processed_dirs(root)["pairs"] / "index.json"
    if not path.exists():
        from oceanai.paths import raw_available

        if not raw_available():
            raise FileNotFoundError(
                f"No pair index at {path}. Point OCEANAI_PROCESSED at an AI-ready "
                "pack, or set OCEANAI_RAW to Kang's dump and rebuild."
            )
        write_pair_index(root=root)
    rows = json.loads(path.read_text())
    for r in rows:
        r.setdefault("npz", f"{r['pair_id']}.npz")
        r.setdefault("year_y", int(r["year_x"]) + 550)
    return rows
