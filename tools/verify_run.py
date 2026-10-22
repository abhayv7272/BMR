"""P2 — Live run verification.

Run ke `results.json` (ya GitHub artifact zip) par P2 checklist check karta hai.
Sandbox/CI me Yahoo reachable nahi hota, isliye live run ka data yahan se nahi
aata — ye script apke machine par ya artifact download karke chalti hai.

Usage:
    python tools/verify_run.py results.json
    python tools/verify_run.py --artifact daily-report-93.zip
    python tools/verify_run.py results.json --verbose

Exit code: 0 = sab OK, 1 = koi FAIL.
"""

import argparse
import json
import os
import sys
import zipfile

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"


def _load(path):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next((n for n in z.namelist() if n.endswith("results.json")), None)
            if not name:
                raise SystemExit(f"[FAIL] {path} me results.json nahi mila")
            path = name
            with z.open(name) as fh:
                return json.load(fh)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _int(d, key, default=0):
    try:
        return int(d.get(key, default) or 0)
    except (TypeError, ValueError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="results.json")
    ap.add_argument("--artifact", help="GitHub artifact zip (daily-report-*.zip)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = _load(args.artifact or args.path)
    d = data.get("diagnostics") or {}
    rows = []

    def add(status, check, value, note=""):
        rows.append((status, check, str(value), note))

    # 1. Data as of == expected session
    asof, exp = d.get("data_as_of"), d.get("expected_session")
    add(PASS if asof == exp else FAIL, "Data as of == Expected session", f"{asof} vs {exp}",
        "" if asof == exp else "Yahoo ne latest candle nahi di - purani candle par report ban gayi")

    # 2. Benchmark
    lag = _int(d, "benchmark_lag_sessions")
    if not d.get("benchmark_ok", True):
        add(FAIL, "Benchmark (NIFTY)", f"PROBLEM: {d.get('benchmark_error')}", "entry signals suppress hue honge")
    elif lag:
        add(WARN, "Benchmark (NIFTY)", f"OK but lag {lag}", "RS filter thoda stale")
    else:
        add(PASS, "Benchmark (NIFTY)", "OK (lag 0)", "")

    # 3. Batches failed
    bf = d.get("batches_failed") or []
    lost = sum(b.get("stocks", 0) for b in bf)
    add(PASS if not bf else FAIL, "Batches failed", len(bf),
        "" if not bf else f"{lost} stocks lost - {bf[0].get('error')}")

    # 4. Calculation errors
    ce = _int(d, "tickers_calc_error")
    add(PASS if ce == 0 else FAIL, "Calculation errors", ce,
        "" if ce == 0 else str((d.get("ticker_error_samples") or [""])[0])[:90])

    # 5. Yahoo retry health (P1)
    req, scanned = _int(d, "tickers_requested"), _int(d, "tickers_scanned")
    gave_up = _int(d, "yf_gave_up")
    add(PASS if gave_up == 0 else FAIL, "Yahoo gave up (no data)", gave_up,
        f"retries {_int(d, 'yf_retries')}, 429 hits {_int(d, 'yf_rate_limit_hits')}, "
        f"backoff {d.get('yf_sleep_seconds', 0)}s")
    if req:
        ratio = scanned / req
        add(PASS if ratio >= 0.95 else WARN, "Tickers scanned / requested",
            f"{scanned}/{req} ({ratio*100:.1f}%)", "" if ratio >= 0.95 else "kaafi stocks skip hue")

    # 6. Universe extras (502/1256 expected at BMR_UNIVERSE_SIZE=1500)
    target = _int(d, "universe_target")
    ranked, pool = _int(d, "universe_ranked_extras"), _int(d, "universe_pool_size")
    if not target:
        add(INFO, "Universe extras ranked", f"{ranked} / {pool}", "purana results.json (universe keys nahi)")
    else:
        need = max(target - 1000, 0)
        add(PASS if ranked >= need else WARN, "Universe extras ranked", f"{ranked} / {pool}",
            f"need {need}" + ("" if ranked >= need else " - universe chhota reh gaya"))

    # 7. Data-quality signals (informational, daily noise)
    stale, nan_close = _int(d, "stale_tickers"), _int(d, "latest_bar_nan_close")
    add(WARN if (scanned and (stale / scanned) > 0.05) else INFO, "Stale / NaN-close tickers",
        f"{stale} / {nan_close}", "Yahoo late-bar lag (normal: thoda hi hota hai)")

    width = max(len(r[1]) for r in rows) + 2
    print(f"file: {args.artifact or args.path}")
    print(f"generated: {d.get('generated_at_ist')}  |  universe: {d.get('universe_unique')} scanned")
    print("-" * 78)
    for status, check, value, note in rows:
        print(f"[{status:4s}] {check:<{width}} {value}")
        if note and (args.verbose or status in (WARN, FAIL)):
            print(f"         {note}")
    print("-" * 78)
    fails = sum(1 for r in rows if r[0] == FAIL)
    warns = sum(1 for r in rows if r[0] == WARN)
    print(f"actionable={len(data.get('actionable', []))} watchlist={len(data.get('watchlist', []))} "
          f"tracked={len(data.get('recent', []))}")
    print("LIVE RUN OK ✅" if not fails else f"ISSUES FOUND ❌ ({fails} fail, {warns} warn)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
