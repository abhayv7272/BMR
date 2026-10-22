"""Offline `yfinance` stub — deterministic fake data for regression testing.

Kaise use karein:
    PYTHONPATH=tools/offline_harness python -u main.py

`main.py` `import yfinance as yf` karta hai; PYTHONPATH par ye folder pehle hone
se asli Yahoo ki jagah ye stub load hota hai. Data ticker naam ke hash se banta
hai, isliye har run me BILKUL same rehta hai — isse old vs new code ka results
compare kiya ja sakta hai (network ke bina).

Injection knobs (env):
    STUB_SEED_SALT      data ka seed badlo (alag market scenario ke liye)
    STUB_FAIL_CALLS     pehle N download calls fail karo (429 simulate)
    STUB_FAIL_MODE      empty | raise | ratelimit   (default: empty)
    STUB_INTRADAY=1     last bar aaj ka (adhoora) — intraday-drop test
    STUB_BENCH_NAN=1    benchmark ka last close NaN — data-integrity test
    STUB_ZERO_PRICE=1   kuch stocks me 0 price — bad-price test
    STUB_NO_VOLUME=1    kuch stocks me Volume column gayab — contract test
"""

import hashlib
import os
import types

import numpy as np
import pandas as pd

SALT = os.environ.get("STUB_SEED_SALT", "")
INTRADAY = os.environ.get("STUB_INTRADAY", "0") == "1"
BENCH_NAN = os.environ.get("STUB_BENCH_NAN", "0") == "1"
ZERO_PRICE = os.environ.get("STUB_ZERO_PRICE", "0") == "1"
NO_VOLUME = os.environ.get("STUB_NO_VOLUME", "0") == "1"

END = pd.Timestamp("2026-10-23") if INTRADAY else pd.Timestamp("2026-10-22")
IDX = pd.bdate_range(end=END, periods=260)

FAIL_CALLS = int(os.environ.get("STUB_FAIL_CALLS", "0"))
FAIL_MODE = os.environ.get("STUB_FAIL_MODE", "empty")   # empty | raise | ratelimit
CALLS = {"n": 0}

# yfinance ka asli shared module jaisa hi shape (main.py shared._ERRORS padhta hai)
shared = types.SimpleNamespace(_ERRORS={}, _DFS={})


def _seed(t):
    return int(hashlib.md5((t + SALT).encode()).hexdigest()[:8], 16)


def _series(ticker, n=260):
    rng = np.random.default_rng(_seed(ticker))
    h = _seed(ticker)
    drift = 0.0009 if h % 100 < 35 else (0.0001 if h % 100 < 70 else -0.0006)
    r = drift + rng.normal(0, 0.017, n)
    r[-20:] -= 0.004
    px = 100 * np.exp(np.cumsum(r))
    o = np.r_[px[0], px[:-1]] * (1 + rng.normal(0, 0.004, n))
    hi = np.maximum(o, px) * (1 + abs(rng.normal(0, 0.007, n)))
    lo = np.minimum(o, px) * (1 - abs(rng.normal(0, 0.007, n)))
    v = rng.integers(200_000, 5_000_000, n).astype(float)
    df = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": px, "Volume": v},
                      index=IDX[-n:])
    if h % 97 == 0:
        df.iloc[-1, df.columns.get_loc("Close")] = np.nan
    if h % 53 == 0:
        df = df.iloc[-90:]
    if ZERO_PRICE and h % 17 == 0:
        df.iloc[-3, df.columns.get_loc("Close")] = 0.0
    if NO_VOLUME and h % 23 == 0:
        df = df.drop(columns=["Volume"])
    if h % 89 == 0:
        return None
    return df


def download(tickers, period=None, progress=None, group_by=None, **kw):
    shared._ERRORS = {}
    CALLS["n"] += 1
    if CALLS["n"] <= FAIL_CALLS:
        if FAIL_MODE == "raise":
            raise RuntimeError("429 Too Many Requests (injected)")
        # asli yfinance 429 par exception nahi deta - khali frame + per-ticker error
        shared._ERRORS = {str(tickers)[:12]:
                          "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"}
        return pd.DataFrame()

    n = 260 if period in (None, "1y", "1Y") else 21
    if isinstance(tickers, str):
        d = _series("NIFTYBENCH", n=260) if tickers == "^NSEI" else _series(tickers, n=n)
        if d is None:
            return pd.DataFrame()
        d = d[["Open", "High", "Low", "Close", "Volume"]]
        if BENCH_NAN and tickers == "^NSEI":
            d.iloc[-1, d.columns.get_loc("Close")] = np.nan
        return d

    frames = {t: _series(t, n=n) for t in tickers}
    for k in list(tickers):
        if frames.get(k) is None:
            frames.pop(k, None)
            shared._ERRORS[k] = "YFPricesMissingError('possibly delisted')"
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()
