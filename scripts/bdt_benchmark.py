"""Benchmark BDT parsing throughput across layout families.

Run:
    python scripts/bdt_benchmark.py [--save-baseline] [--max-files N]

--save-baseline  Write results to scripts/bdt_benchmark_baseline.json
                 (commit this file to record the baseline for future comparisons).
--max-files N    Cap number of files scanned (default 100).

Exit code 1 if throughput regresses more than 20% vs the saved baseline.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_BASELINE_PATH = Path(__file__).parent / "bdt_benchmark_baseline.json"
_REGRESSION_THRESHOLD = 0.20  # 20% drop triggers non-zero exit

DATA_DIRS = [
    Path("/Users/mikawi/Developer/orange/data/2024_pm_tests"),
    Path("/Users/mikawi/Developer/orange/data/test_pms"),
    Path("/Users/mikawi/Developer/orange/data"),
]


def collect_bdt_files(dirs: list[Path], max_files: int) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for pattern in ("*.xlsx", "*.XLSX"):
            for f in d.rglob(pattern):
                if f not in seen:
                    seen.add(f)
                    files.append(f)
                    if len(files) >= max_files:
                        return files
    return files


def _parse_one(parse_fn, f: Path) -> dict:
    try:
        d = parse_fn(str(f), skip_photos=True)
        return {"ok": True, "family": d.core_layout_family or "UNKNOWN"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_benchmark(parse_fn, files: list[Path]) -> dict:
    workers = min(len(files), (os.cpu_count() or 1) * 4, 32)
    by_family: dict[str, int] = {}
    errors = 0

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_parse_one, parse_fn, f): f for f in files}
        for fut in as_completed(futs):
            r = fut.result()
            if r["ok"]:
                fam = r["family"]
                by_family[fam] = by_family.get(fam, 0) + 1
            else:
                errors += 1
    elapsed = time.perf_counter() - start

    return {
        "files": len(files),
        "workers": workers,
        "elapsed_s": round(elapsed, 3),
        "files_per_sec": round(len(files) / elapsed, 1),
        "errors": errors,
        "by_family": by_family,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="BDT parser benchmark")
    ap.add_argument("--save-baseline", action="store_true",
                    help="Write result to bdt_benchmark_baseline.json")
    ap.add_argument("--max-files", type=int, default=100)
    args = ap.parse_args()

    # Bootstrap path so alarm_app is importable
    repo_root = Path(__file__).parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from alarm_app.bdt.parser import parse_bdt_file  # noqa: PLC0415

    files = collect_bdt_files(DATA_DIRS, args.max_files)
    if not files:
        print("No BDT files found — skipping benchmark")
        return 0

    print(f"Benchmarking {len(files)} files with up to {(os.cpu_count() or 1) * 4} workers…")
    # Warm-up pass: prime OS file cache so timed run reflects parser speed, not cold I/O.
    print("Warming up…")
    run_benchmark(parse_bdt_file, files)
    result = run_benchmark(parse_bdt_file, files)

    print(f"Results : {result['files']} files in {result['elapsed_s']:.2f}s "
          f"({result['files_per_sec']:.1f} files/sec) using {result['workers']} workers")
    print(f"Errors  : {result['errors']}")
    print(f"By family: {result['by_family']}")

    if args.save_baseline:
        _BASELINE_PATH.write_text(json.dumps(result, indent=2))
        print(f"Baseline saved → {_BASELINE_PATH}")
        return 0

    if _BASELINE_PATH.exists():
        baseline = json.loads(_BASELINE_PATH.read_text())
        base_fps = baseline.get("files_per_sec", 0)
        curr_fps = result["files_per_sec"]
        if base_fps > 0:
            delta = (curr_fps - base_fps) / base_fps
            marker = "✓" if delta >= -_REGRESSION_THRESHOLD else "✗ REGRESSION"
            print(f"vs baseline: {base_fps:.1f} → {curr_fps:.1f} files/sec "
                  f"({delta:+.1%}) {marker}")
            if delta < -_REGRESSION_THRESHOLD:
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
