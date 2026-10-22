# Ultra-Deep Data Audit — 23-Oct-2026

**Sawal:** kya sab kuch perfectly chal raha hai? Saara data fetch ho raha hai? Sab latest data par hai?

---

## 0. Pehle ek deployment sach (important)

| Cheez | Status |
|---|---|
| Code kahan tha? | `arena/b59756be-daily-report` (branch) |
| Production kahan chalta hai? | `main` branch → scheduled workflow |
| `origin/main` kab tak purana tha? | **PR #4 merge tak `9e63b77` (14-Sep)** |

Yaani **diagnosis se pehle** jo bhi analysis hoti, wo purane code par hoti. Ab:
- PR #4 **merged** → main `4ff1452`
- Live run ab main se hi naya code uthayega
- ⚠️ Manual `workflow_dispatch` mere token se nahi ho saka (`403 Resource not accessible`) → **pehla live run aaj ka 13:40 IST scheduled slot** hai. Uske baad hi "live data par verified" keh sakte hain.

---

## 1. Audit method

Live Yahoo/NSE tak sandbox se pahunch nahi hai, isliye **8 failure scenarios** ke saath ek deterministic offline Yahoo stand-in banaya (real API jaisa hi shape) aur poora `main.py` chalaya. Har scenario me dekha: crash hota hai? data chupchaap gayab hota hai? galat signal banta hai? report kya dikhati hai?

| # | Scenario | Kya simulate karta hai |
|---|---|---|
| 1 | `normal` | sab theek |
| 2 | `no_bench` | NIFTY benchmark empty |
| 3 | `bench_nan` | benchmark ke last bar me `Close = NaN` (Yahoo late bar) |
| 4 | `bench_intraday` | benchmark me market ke andar ka (adhoora) bar |
| 5 | `partial` | batch response me 10% tickers gayab (yfinance silent partial) |
| 6 | `zeropx` | Close/OHLC = 0 (corrupt prices) |
| 7 | `novolume` | `Volume` column hi missing |
| 8 | `dupdates` | duplicate timestamps |

---

## 2. Findings (before fix) — 5 real bugs

### 🔴 F1 — Benchmark NaN → report me `₹nan` (silent corruption)
`bench_nan` scenario me:
```
[+] NIFTY 50 CMP: ₹nan | 200 EMA: ₹105.25
[+] Market Regime: CORRECTION
```
Run green, mail jaati, Excel me NIFTY CMP `₹nan`. Regime bhi `NaN` comparisons se galat. **Koi error nahi.**

### 🔴 F2 — Benchmark missing → poora run crash
`no_bench` scenario:
```
KeyError: 'Close'  (calculate_benchmark_regime)
```
Na report, na Excel, na mail — bas red run.

### 🔴 F3 — Adhoora (intraday) bar signals bana sakta tha
`bench_intraday` scenario:
```
benchmark last bar: 2026-10-23   (aaj, jabki session complete nahi)
Stale tickers: 968 (false alarm)
```
Aur stocks ke liye bhi: agar run market ke andar chale (manual dispatch guard bypass karta hai — `event_name != schedule`), to aaj ki **adhoori candle** par signal ban sakta tha = **false signal**.

### 🟠 F4 — Zero/negative prices detect hi nahi hote the
`zeropx` scenario: `NaN indicators: 0`, koi warning nahi — ATR/BB/RSI garbage numbers bante, aur `risk` calculation me 0 division tak pahunch sakta tha.

### 🟠 F5 — Missing `Volume` / duplicate dates
- `novolume`: 28 tickers `KeyError: 'Volume'` — pehle **chupchaap** skip (Phase 1 ke baad dikha)
- `dupdates`: duplicate timestamps ka koi guard nahi (indicator alignment par asar)

---

## 3. Fixes (all fail-safe — sirf invalid data reject/flag karta hai)

| # | Fix | Kahan |
|---|---|---|
| 1 | `load_benchmark()` — empty / missing column / NaN close / <210 bars / non-positive → validate, warna saaf error | `main.py` DATA INTEGRITY layer |
| 2 | Benchmark fail → **run crash nahi**, warning + neutral regime + **naye entry signals SUPPRESSED** (radar/tracker sirf reference) | `run_screener` |
| 3 | `drop_incomplete_last_bar()` — aaj ka adhoora bar (IST < 15:35) hatao, benchmark + stocks + turnover ranking, sab par | same |
| 4 | `sanitize_ohlcv()` — missing columns, `Close/Open/High/Low <= 0`, `High < Low`, `Volume < 0`, duplicate timestamps | same |
| 5 | `expected_session_date()` — aakhri completed NSE session; `stale` / `future-dated` bars isi se compare | same |
| 6 | Diagnostics: `benchmark_ok`, `benchmark_error`, `benchmark_lag_sessions`, `expected_session`, `intraday_bar_dropped`, `tickers_missing_columns`, `tickers_bad_prices`, `tickers_duplicate_dates_fixed`, `tickers_future_bar`, `actionable_suppressed`, `contract_issues` | console + Excel breadth + `results.json` |
| 7 | Email/HTML me **red warning banner** (benchmark problem, intraday bars dropped, bad prices, benchmark lag) | `build_html_report` |
| 8 | IST/`now_ist()` file ke **top** par move (pehle Excel section me tha, jisse data layer ko milta hi nahi tha — silent `except` me nigal jata tha) | `main.py` top |

---

## 4. After fix — same scenarios (proven)

| Scenario | Before | After |
|---|---|---|
| `normal` | radar 65, actionable 0 | **bilkul same** ✅ (regression) |
| `no_bench` | 💥 crash | warning + **1 signal suppressed** + report banti hai ✅ |
| `bench_nan` | `CMP ₹nan` | benchmark 21-Oct par, **`lag 1 session`** warning ✅ |
| `bench_intraday` | aaj ka adhoora bar use hua | bar **hata diya**, `benchmark last bar: 2026-10-22` ✅ |
| `partial` | 104 missing (detected) | same + counted ✅ |
| `zeropx` | 0 detect | **27 bad-price tickers** skipped + samples ✅ |
| `novolume` | 28 chupchaap | **29 counted** + `missing_columns:Volume` sample ✅ |
| `dupdates` | no guard | duplicate dates fixed + counted ✅ |

**Regression proof (merged main vs hardened code, same fake data):**
```
actionable  identical=True (n=0)
watchlist   identical=True (n=65)
recent      identical=True (n=3)
regime      values identical (extra keys: valid, error)
```

---

## 5. "Sab latest data par hai?" — honest answer

**Ab haan, teen layers se guarantee hoti hai:**
1. **Bar completeness:** aaj ka adhoora bar hata diya jata hai → signal sirf completed session par.
2. **Freshness visibility:** report me `Data as of` + `Expected session` + `Stale tickers` + `Future-dated bars` — sab printed.
3. **Turnover ranking** bhi adhoori candle ignore karti hai (warna galat stocks top-500 me aa jate).

**Par 2 baatein sach me pending hain:**
- **Live verification** abhi nahi hui — sirf aaj ke 13:40 IST run ke baad pata chalega ki asli Yahoo/NSE response in guards se clean nikalta hai. Us run me check karna: `Data as of = expected session`, `Benchmark OK (lag 0)`, `Batches failed 0`, `Calculation errors 0`.
- **Email delivery ka proof** sandbox se possible nahi (SMTP + Gmail access yahan nahi). Workflow success + artifact hi proxy hain.

---

## 6. Jo abhi bhi known-limitation hai (bug nahi, design)

- **NSE live list** GitHub runner ke IP se block ho sakti hai → embedded extras fallback (1500 phir bhi pura). Diagnostics me `Extras pool source` batata hai.
- **RS filter** benchmark ke 30-day return par hai; benchmark 1 session peeche ho to thoda stale (ab warning aati hai).
- **Shadow test** ke forward-test me cost/slippage model nahi (relative comparison ke liye hai).
- **Tracker dedupe** per-ticker hai (ek stock ek waqt me ek signal) — by design.

---

## 7. Aaj ke run par 60-second checklist

Mail/Excel kholte hi:
1. `Data as of` == `Expected session`? (dono print hote hain)
2. `Benchmark (NIFTY): OK (lag 0 session(s))`?
3. `Batches failed = 0`, `Calculation errors = 0`?
4. `Extras pool source` = nse_live ya embedded fallback? `Extras ranked = 502`?
5. Excel *Market Regime & Breadth* me naye integrity rows; *Shadow* tab me variants ka win%.
6. Agar 0 signal — funnel ka top gate dekho (yahi asli jawab hai).
