"""Old vs new regression runner (offline, deterministic).

Kya karta hai:
  1. `git show <ref>:main.py` se purana version nikalta hai (default: HEAD).
  2. Dono versions ko offline `yfinance` stub ke saath chalata hai (network nahi).
  3. `results.json` ke actionable / watchlist / recent ko byte-compare karta hai.

Golden rule #3: merge se pehle actionable/watchlist/recent identical hone chahiye.

Usage:
    python tools/offline_harness/regression.py                    # HEAD vs working tree
    python tools/offline_harness/regression.py --ref df26413
    python tools/offline_harness/regression.py --salt 7           # alag market scenario
    python tools/offline_harness/regression.py --universe 1000
"""

import argparse
import base64
import csv
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def _git_show(ref, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{ref}:{path}"],
                          check=True, capture_output=True, text=True).stdout


def _extract_extras_csv(main_py_src, out_path):
    """main.py ke embedded extras blob se NSE EQUITY_L.csv jaisa local file banao.

    Isse turnover-ranking chunks network ke bina chalti hain aur pool har run me
    same rehta hai (production ka 'NSE live list' wala behaviour)."""
    m = re.search(r'EXTRA_SYMBOLS_B64\s*=\s*"([^"]+)"', main_py_src)
    if not m:
        return None
    raw = gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(raw)))
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["SYMBOL", "NAME OF COMPANY", " SERIES"])
        n = 0
        for r in rows:
            sym = (r.get("Symbol") or r.get("symbol") or "").strip()
            if not re.fullmatch(r"[A-Z0-9&\-]{1,20}", sym):
                continue
            w.writerow([sym, (r.get("Company Name") or sym).strip(), "EQ"])
            n += 1
    return out_path if n else None


def _run(main_path, workdir, env_extra, timeout=1800):
    os.makedirs(workdir, exist_ok=True)
    shutil.copy(main_path, os.path.join(workdir, "main.py"))
    env = dict(os.environ)
    env.pop("MY_EMAIL", None)            # email band - run end par RuntimeError aayega
    env.pop("MY_APP_PASSWORD", None)
    env["PYTHONPATH"] = HERE + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.update(env_extra)
    proc = subprocess.run([sys.executable, "-u", "main.py"], cwd=workdir, env=env,
                          capture_output=True, text=True, timeout=timeout)
    results = os.path.join(workdir, "results.json")
    if not os.path.exists(results):
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
        raise SystemExit(f"[FAIL] results.json nahi bana: {workdir}")
    with open(results, encoding="utf-8") as fh:
        return json.load(fh), proc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD", help="purana git ref (default HEAD)")
    ap.add_argument("--new", default=os.path.join(REPO, "main.py"), help="naya main.py")
    ap.add_argument("--salt", default="", help="STUB_SEED_SALT (different market scenario)")
    ap.add_argument("--universe", default="1500", help="BMR_UNIVERSE_SIZE")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--keep", action="store_true", help="temp workdir rakho")
    args = ap.parse_args()

    tmp = args.workdir or tempfile.mkdtemp(prefix="bmr-regression-")
    old_main = os.path.join(tmp, "old_main.py")
    with open(old_main, "w", encoding="utf-8") as fh:
        fh.write(_git_show(args.ref, "main.py"))

    list_csv = _extract_extras_csv(_git_show(args.ref, "main.py"),
                                   os.path.join(tmp, "EQUITY_L.csv"))

    env_extra = {
        "BMR_UNIVERSE_SIZE": str(args.universe),
        # test me speed: retry backoff/gap production jaisa nahi chahiye
        "BMR_YF_CHUNK_DELAY": "0",
        "BMR_YF_BACKOFF_BASE": "0.2",
    }
    if args.salt:
        env_extra["STUB_SEED_SALT"] = str(args.salt)
    if list_csv:
        env_extra["BMR_NSE_LIST_FILE"] = list_csv

    print(f"[*] ref={args.ref} salt={args.salt or '-'} universe={args.universe}")
    old, _ = _run(old_main, os.path.join(tmp, "old"), env_extra)
    new, _ = _run(args.new, os.path.join(tmp, "new"), env_extra)

    ok = True
    for key in ("actionable", "watchlist", "recent"):
        a, b = old.get(key, []), new.get(key, [])
        same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        ok &= same
        print(f"  {key:10s} old={len(a):3d}  new={len(b):3d}  identical={same}")
        if not same:
            syms_a = [x.get("symbol") for x in a]
            syms_b = [x.get("symbol") for x in b]
            print(f"    only old: {sorted(set(syms_a) - set(syms_b))[:10]}")
            print(f"    only new: {sorted(set(syms_b) - set(syms_a))[:10]}")

    if not args.keep and not args.workdir:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"[i] artifacts: {tmp}")
    print("REGRESSION PASS ✅" if ok else "REGRESSION FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
