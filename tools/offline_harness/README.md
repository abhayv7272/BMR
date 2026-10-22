# Offline harness — network ke bina screener test karo

Sandbox/CI me Yahoo & NSE reachable nahi hote. Ye folder ek **deterministic fake
`yfinance`** deta hai jisse `main.py` poora chalta hai (universe, indicators,
signals, tracker, Excel, HTML) — bas data asli nahi hota.

```bash
# 1. Poore screener ko fake data par chalao
PYTHONPATH=tools/offline_harness python -u main.py

# 2. Purane version se compare karo (merge se pehle golden rule #3)
python tools/offline_harness/regression.py --ref df26413
python tools/offline_harness/regression.py --ref df26413 --salt 7   # alag market scenario
```

> `main.py` ke aakhir me email step `MY_EMAIL`/`MY_APP_PASSWORD` ke bina
> `RuntimeError` deta hai — ye **expected** hai (silently skip nahi hona chahiye).
> `results.json`, `report.html` aur Excel uske pehle hi likhe ja chuke hote hain.

## Data kaisa banta hai

Har ticker ka data uske naam ke MD5 se seed hota hai, isliye **har run me bilkul
same**. `STUB_SEED_SALT` badalne par poora market scenario badal jata hai (jaise
`actionable = 0` wala din vs `actionable = 2` wala din).

Built-in (bina env ke):
- kuch stocks me last close `NaN` (Yahoo ka late-bar symptom)
- kuch stocks ke sirf 90 bars (insufficient history)
- kuch tickers ka data hi nahi (`_ERRORS` me missing) — diagnostics test

## Injection knobs

| Env | Kya karta hai | Kaunsa check |
|---|---|---|
| `STUB_FAIL_CALLS=N` | pehle N download calls fail | P1 retry/backoff |
| `STUB_FAIL_MODE` | `empty` (default) · `raise` · `ratelimit` | 429 ke dono roop |
| `STUB_INTRADAY=1` | last bar = aaj ka (adhoora) | `intraday_bar_dropped` |
| `STUB_BENCH_NAN=1` | benchmark ka last close NaN | benchmark lag / fail-safe |
| `STUB_ZERO_PRICE=1` | kuch stocks me price 0 | `tickers_bad_prices` |
| `STUB_NO_VOLUME=1` | kuch stocks me `Volume` column nahi | `tickers_missing_columns` |
| `STUB_SEED_SALT=x` | naya market scenario | regression coverage |

Screener ke apne knobs (production me bhi kaam karte hain):
`BMR_UNIVERSE_SIZE`, `BMR_NSE_LIST_FILE` (local `EQUITY_L.csv`),
`BMR_YF_MAX_ATTEMPTS`, `BMR_YF_BACKOFF_BASE`, `BMR_YF_BACKOFF_CAP`, `BMR_YF_CHUNK_DELAY`.

## Example: 429 storm reproduce karo (fast backoff ke saath)

```bash
PYTHONPATH=tools/offline_harness \
BMR_NSE_LIST_FILE=/tmp/EQUITY_L.csv \
STUB_FAIL_CALLS=1000 STUB_FAIL_MODE=ratelimit \
BMR_YF_MAX_ATTEMPTS=2 BMR_YF_BACKOFF_BASE=0.1 BMR_YF_CHUNK_DELAY=0 \
python -u main.py
```

Expected: koi crash nahi, `Batches failed 10`, `Missing from download 998`,
`Yahoo 429 hits 48`, aur email me laal warning banner.
