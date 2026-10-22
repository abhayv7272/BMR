# P1 — Yahoo 429 hardening (`yf_download_retry`)

**Date:** 23-Oct-2026 · **Scope:** sirf data-fetch layer. Signal gates, thresholds,
shadow variants, tracker (`simulate_exits` / `tracker_status` / `TRACK_DAYS`) —
sab **untouched**.

---

## Asli problem (jo diagnosis me chhoot gayi thi)

Ek run me Yahoo ko **~29 download calls** jaate hain:
1 benchmark + 15 scan chunks + 13 turnover-ranking chunks.

**429 (Too Many Requests) par yfinance EXCEPTION NAHI deta.** Wo har ticker ka
error `shared._ERRORS` me daal kar **khali DataFrame return** karta hai:

```python
# yfinance/multi.py (0.2.66)
except Exception as e:
    shared._DFS[ticker.upper()] = utils.empty_df()
    shared._ERRORS[ticker.upper()] = repr(e)      # <- YFRateLimitError yahan
```

Purana wrapper sirf `except Exception` par retry karta tha, isliye 429 kabhi
pakda hi nahi jata tha. Nateeja:

| Symptom | Pehle | Ab |
|---|---|---|
| `Batches failed` | **0** (jhooth) | 429 wale batch ka number + stocks + reason |
| `Missing from download` | 0 (batch `continue` kar jata tha) | poore batch ke stocks count hote hain |
| Warning banner | nahi | laal banner: "Yahoo ne N download(s) me data nahi diya … report incomplete" |
| Retry | sirf exception par, fixed 10s × 3 | 429 / empty / exception teenon par, exponential backoff |

Isi wajah se "sab green, phir bhi 0 signal" wale din data-side karan invisible reh
jata tha.

---

## Kya badla (`main.py`)

### 1. Retry ab 3 wajahon par hota hai
```python
YF_MAX_ATTEMPTS   = 4      # BMR_YF_MAX_ATTEMPTS
YF_BACKOFF_BASE   = 5      # BMR_YF_BACKOFF_BASE  -> 5s, 10s, 20s ...
YF_BACKOFF_CAP    = 60     # BMR_YF_BACKOFF_CAP
YF_CHUNK_DELAY    = 1.5    # BMR_YF_CHUNK_DELAY   -> har call ke beech gap
```
1. **exception** — network/JSON error
2. **rate-limit signature** — `shared._ERRORS` me `429` / `Too Many Requests` / `YFRateLimitError`
3. **multi-ticker chunk ka khali result** — Yahoo ne data hi nahi diya

Single-ticker call (benchmark) ka khali result bina 429 ke retry nahi karta —
warna delisted ticker par 35s barbaad hote.

### 2. Partial data kabhi nahi khota
Agar attempt 1 ne kuch data diya aur attempt 2 rate-limited hua, to **jo mila
wahi return hota hai** (`best` frame). Sab attempts fail + koi exception nahi →
khali frame return (batch `batches_failed` me chala jata hai). Sab attempts
exception → last exception raise (purana behaviour, call sites waise hi handle
karte hain).

### 3. Throttle
Har download ke beech minimum `1.5s` gap (`_yf_throttle`). 29 calls × 1.5s ≈ **+45s**
per run — 30 min ke job timeout ke andar aaram se.

### 4. Diagnostics (chhupna nahi chahiye)
`results.json → diagnostics`, console, Excel (*Regime & Breadth*) aur email footer:

```
Yahoo downloads (calls)       : 29
Yahoo retries / 429 hits      : 2 / 2   (empty results: 0, gave up: 0, backoff wait: 0.6s)
```

| Key | Matlab |
|---|---|
| `yf_calls` | logical downloads (chunk = 1 call) |
| `yf_attempts` | actual `yf.download` invocations |
| `yf_retries` | extra attempts after a failure |
| `yf_rate_limit_hits` | 429 signatures mile |
| `yf_empty_results` | multi-ticker chunk ne khali frame diya |
| `yf_gave_up` | attempts khatam, data nahi mila |
| `yf_sleep_seconds` | backoff + throttle me kitna time gaya |
| `yf_last_error` | aakhri failure ka reason |

### 5. Empty-batch detection (do call sites)
- `run_screener` scan loop → `batches_failed` + `tickers_missing_from_download += len(chunk)`
- `rank_candidates_by_turnover` → `chunks_failed` (warna universe chupchaap 1000 par aa jata)

---

## Verification (offline harness, `tools/offline_harness/`)

### A. Regression — signals bilkul same (golden rule #3)
```
python tools/offline_harness/regression.py --ref df26413 --salt 7
  actionable old=  2  new=  2  identical=True
  watchlist  old=117  new=117  identical=True
  recent     old= 14  new= 14  identical=True
REGRESSION PASS ✅

python tools/offline_harness/regression.py --ref df26413        # salt = default
  actionable old=  0  new=  0  identical=True
  watchlist  old=105  new=105  identical=True
  recent     old=  4  new=  4  identical=True
REGRESSION PASS ✅
```
(Production-settings run — `BMR_YF_CHUNK_DELAY=1.5`, `BMR_YF_BACKOFF_BASE=5` — bhi
ye hi output deta hai; throttle/retry successful case me data ko chhoota nahi.)

### B. 429 injection (2 calls rate-limited → recover)
```
[!] Yahoo download failed (rate limit 429 (1 ticker(s) failed)). Attempt 1/4 - retrying in 0.2s...
[!] Yahoo download failed (rate limit 429 (1 ticker(s) failed)). Attempt 2/4 - retrying in 0.4s...
Extras ranked         : 502   (baseline 502 — kuch nahi khoya)
Batches failed        : 0
Yahoo retries / 429   : 2 / 2
actionable/watchlist/recent = baseline ke saath identical ✅
```

### C. Exception injection (`STUB_FAIL_MODE=raise`, 2 calls)
```
[!] Yahoo download failed (RuntimeError: 429 Too Many Requests (injected)). Attempt 1/4 ...
Yahoo retries / 429 hits : 2 / 0
actionable/watchlist/recent = identical ✅
```

### D. Permanent 429 (Yahoo ne poore run me data nahi diya)
```
Extras ranked                 : 0   (rank batches failed: 13)
Missing from download         : 998
Batches failed                : 10
Yahoo retries / 429 hits      : 24 / 48   (gave up: 24, backoff wait: 2.4s)
Benchmark (NIFTY)             : PROBLEM -> empty response
email banner: "⚠ Yahoo ne 24 download(s) me data nahi diya (retries ke baad bhi;
48 rate-limit hit) — 998 stocks scan se bahar rahe, report incomplete ho sakti hai."
```
→ crash nahi, jhoothi "green" report nahi, aur naye entry signals fail-safe se
suppress (`actionable_suppressed`).

### E. Data-integrity injections (pre-existing layer, post-change re-check)
| Injection | Result |
|---|---|
| `STUB_BENCH_NAN=1` | benchmark last NaN bar drop, `lag 1 session`, koi crash nahi |
| `STUB_INTRADAY=1` | `Adhoori intraday bars hataye: 1488`, `data_as_of = 2026-10-22` |
| `STUB_ZERO_PRICE=1` | `Bad prices: 49`, `ASTRAL.NS: bad_prices:1bars` |
| `STUB_NO_VOLUME=1` | `Missing columns: 45`, `ABB.NS: missing_columns:Volume` |

---

## Rollback

Code revert (single commit) — ya behaviour ko env se purana karo, deploy ke bina:

```bash
BMR_YF_MAX_ATTEMPTS=1     # retry off (purana 10s-fixed-retry bhi nahi, seedha single try)
BMR_YF_CHUNK_DELAY=0      # throttle off
```

## Production verification checklist (P2)

Ek command me (artifact zip ya `results.json` par):
```bash
python tools/verify_run.py results.json
python tools/verify_run.py --artifact daily-report-93.zip
```

Ye wahi checks karta hai jo neeche listed hain, aur `LIVE RUN OK ✅` / `ISSUES
FOUND ❌` deta hai. Sandbox se GitHub artifact download (blob host) aur
`workflow_dispatch` (403) block hain, isliye live run ki final confirmation
aapke side se hi possible hai — script usi ke liye hai.

Run ke baad `results.json` / email footer me:
1. `Data as of == Expected session`
2. `Benchmark (NIFTY) : OK (lag 0)`
3. `Batches failed : 0`
4. `Calculation errors : 0`
5. `Extras ranked : 502 / 1256`
6. **`Yahoo retries / 429 hits`** — 0/0 = Yahoo khush; >0 par bhi `gave up 0` hona chahiye
