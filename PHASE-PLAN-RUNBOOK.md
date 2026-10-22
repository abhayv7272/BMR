# Phase Plan Runbook — Diagnostics → Shadow → Promotion

**Status:** Phase 1 ✅ implemented · Phase 2 ✅ implemented (shadow, observation only) · Phase 3 ✅ gate implemented (auto-promote **OFF**)
**Rule:** in teeno phases me **actionable signals / email ki list bilkul nahi badli** — regression test se proven (neeche).

---

## Phase 1 — Diagnostics (0% signal change) ✅

### Kya add hua

| Kahan | Kya |
|---|---|
| `main.py` (`run_screener`) | `diagnostics` dict: ticks requested/scanned/missing/insufficient/nan/errors, `latest_bar_nan_close`, `stale_tickers`, `batches_failed`, `data_as_of`, `market_date`, `reject_first_gate` funnel |
| Console | "DATA HEALTH & SIGNAL FUNNEL" block + **"0 SIGNAL KA KARAN: bb_slope_ok ne 41 stocks block kiye"** |
| Excel → *Market Regime & Breadth* | 13 nayi breadth rows + rejection funnel table (gate × stocks blocked × matlab) |
| Excel → Sheet 1 subtitle | `Data as of: <last candle date>` |
| Excel → *Shadow* sheet | naya tab (Phase 2) |
| `report.html` (email) | header me `Data: <as-of>`, footer me `Data health: 966/998 scanned · failed batches · calc errors` + `0-signal reason` |
| `results.json` | `diagnostics` + `shadow_variants` keys |
| `requirements.txt` | exact pins (yfinance 0.2.66, pandas 2.3.3, numpy 2.4.6, openpyxl 3.1.5, requests 2.34.2) |
| Universe | duplicate symbols (`INOXGREEN`, `TRIVENI`) skip — warna same stock ki duplicate row aa sakti thi |

### Silent-skip bugs jo band hue
- `except Exception:` per ticker → ab counter + 5 error samples (`tickers_calc_error`, `ticker_error_samples`)
- batch download fail → pehle 100 stocks chupchaap gayab; ab `batches_failed` me batch number, stock count aur error
- Yahoo ka NaN latest bar → pehle chupchaap drop hokar screener kal ki candle par chalta tha; ab detect + `stale_tickers` me naam ke saath report hota hai (selection waisi hi)

### Regression proof (fake deterministic Yahoo, old vs new)

```
$ python old/main.py  ->  1 actionable, 65 radar, 9 tracked
$ python new/main.py  ->  1 actionable, 65 radar, 9 tracked
actionable   identical=True  (n=1)
watchlist    identical=True  (n=65)
recent       identical=True  (n=9)
regime       identical=True
```

Batch-failure test (`HTTP 429` on batch 3 injected):

```
Batches failed : 1
    - batch 3: 100 stocks lost -> simulated Yahoo HTTP 429 on batch 3
Tickers scanned: 872 (was 966)
```
→ ab aisa run "green but incomplete" nahi, **report me saaf dikhta hai**. (Actionable list par koi asar nahi — wahi 1 signal.)

---

## Phase 2 — Shadow mode (observation only) ✅

Har run 4 variants evaluate karta hai:

| Variant | Kya badla |
|---|---|
| `V0_current` | aaj ka code (baseline / comparison) |
| `V1_bb3` | bb slope guard −1.2% → −3.0% |
| `V2_bb3_noslope` | bb −3.0% **+ EMA50 slope guard OFF** |
| `V3_nomacd` | MACD turn gate OFF |

Har variant ke liye:
1. **Aaj ke marginal signals** — jo current gates se nahi aate (symbol, CMP, SL, T1, T2, RSI, BB slope)
2. **25-session forward-test** — entry agle din ka open, exit `simulate_exits` engine se (FULL_T1), phir WIN/SL/TIME/OPEN + win%

**Kahan dikhta hai:** console + Excel tab *Shadow (Loosened Filters)* + email footer ki ek line.
**Kahan NAHI dikhta:** actionable list, Excel Sheet 1, email ke signal tables. Shadow kabhi email me "trade" nahi banta.

Offline test output (fake data, 998 stocks):

```
variant         today  25d signals  WINS  SL  OPEN  win%
V0_current          1           11     5   2     4   46%
V1_bb3              2           30    16   5     9   53%
V2_bb3_noslope     12          195    98  44    53   50%
V3_nomacd           1           20    11   5     4   55%
```

> ⚠️ **Shadow ke caveats (honest):**
> - `V0` retro count (11) tracker ke `Tracked Signals` (9) se thoda alag ho sakta hai — tracker per-ticker dedupe karta hai, shadow nahi. Comparison ke liye shadow ke andar hi V0 vs V1/V2/V3 dekhein, tracker se cross-compare na karein.
> - Forward-test `FULL_T1` plan par hai (T1 +2% = exit), slippage/cost model nahi hai. Ye **relative** comparison hai, absolute P&L forecast nahi.
> - Sample 25 sessions × ~1000 stocks = chhota hai. 10–15 sessions ka accumulation zyada meaningful hoga.

---

## Phase 3 — Promotion gate ✅ (auto-promote OFF)

`shadow_promotion_review()` har variant ka verdict deta hai — **kuch bhi khud promote nahi karta**. Promote karne ke liye code me threshold manually badalna padta hai.

**READY** sirf tab jab teenon pass hon:
1. win-rate ≥ `V0` baseline (25-session forward-test)
2. volume ≤ **5 naye signals/day**
3. NIFTY regime **BULL** (correction me loosened filters kabhi on nahi)

Test:

```
BULL regime:
   V1_bb3         READY      | all criteria met
   V2_bb3_noslope NOT-READY  | 36.0 signals/day > cap 5
CORRECTION regime:
   V1_bb3         NOT-READY  | regime CORRECTION (only BULL me promote)
```

### Promote karne ka exact procedure (jab verdict READY aaye)
1. 10–15 sessions ka shadow data jama karein (Excel *Shadow* tab, ya `results.json` artifacts)
2. Verdict READY + volume cap ke andar + BULL regime — teenon confirm karein
3. `SHADOW_VARIANTS['V1_bb3']` ke values live code me le jaayein:
   - `main.py` line ~`bb_slope_ok = ... < -0.012` → `-0.030`
4. Saath me 3 safety nets lagayein:
   - `vol[i] > vol_sma[i]` ko **hard gate** banayein (abhi sirf scoring me hai)
   - per-day cap: top 5 by rank, baaki radar me
   - loosened mode me risk per trade 1.0% → 0.5%
5. Pehle `workflow_dispatch` se ek manual run karein, `results.json` compare karein — expected: actionable list badlegi (yahi point hai), radar/tracker nahi
6. Rollback: wahi threshold wapas `-0.012` (single-line revert)

---

## Ye file kaise interpret karein (daily routine)

1. Mail/Excel ka **"Data as of"** dekh lein — aaj ki date honi chahiye.
2. `Tickers scanned` ≈ `Tickers requested` hona chahiye (chhota gap normal: naye/illiquid names).
3. `Batches failed > 0` ya `Calculation errors > 0` → data issue, us din ke 0 ko "market" na samjhein.
4. `latest_bar_nan_close > 0` aur `stale_tickers > 0` → screener kuch stocks ke liye kal ki candle par hai (Yahoo lag). Iska matlab signals thode miss ho sakte hain.
5. 0 signal ho to **funnel** dekhein — top gate kaun hai. Wahi aapka asli "kya block ho raha hai" jawab hai.

---

## Universe change — TOP 1000 → TOP 1500 (23-Oct-2026)

**Kya badla:** scan universe ab 1500 stocks ka hai (pehle 1000).

Kahan se aate hain:
| Layer | Count | Source |
|---|---|---|
| Base catalog | 998 unique (1000 rows, 2 dupes skipped) | embedded `EMBEDDED_DATA_B64` — **waisa hi, chhua nahi** (already turnover-ranked) |
| Extras pool | ~1250 | NSE ka live `EQUITY_L.csv` (nseindia archives) — na mile to embedded `EXTRA_SYMBOLS_B64` fallback |
| Extras selected | 502 | pool me se **average daily turnover (last ~10 sessions)** ke hisaab se top 502 |
| **Total scanned** | **1500** | |

Config: `BMR_UNIVERSE_SIZE` (default **1500**, workflow me set kiya hua hai).
**Rollback:** workflow me `BMR_UNIVERSE_SIZE: "1000"` — baaki kuch nahi badlega.

### Kya asar padta hai
- **Run time:** +~3–5 min (13 turnover-rank chunks + 5 extra scan chunks). Python step ka timeout 25 → **30 min** kiya gaya.
- **Signal count badh sakta hai** — 500 extra stocks scan hote hain, to radar/tracked/actionable ke numbers nikal sakte hain. Test (offline fake data): radar 65 → 105, tracked 9 → 14, actionable same.
- **Aapke tracker ki logic bilkul same** — `TRACK_DAYS`, `simulate_exits`, `tracker_status` untouched. Sirf utne hi stocks track hote hain jitne scan hote hain.
- Naya stock jispar turnover data nahi mila → wo **bottom par** (turnover 0), guess se include nahi hota.
- Consistency ke liye base 1000 pehle, extras uske baad — dedupe automatic (`symbol` already in base → pool se hata diya jata hai).

### Diagnostics me naye rows (Excel "Market Regime & Breadth" + console)
```
Universe target / Extras pool source / Extras pool size
Extras ranked (turnover) / Extras with usable data / Rank batches failed / Universe note
```
`Universe note` me shortfall likha aata hai (e.g. "only 380 of 502 extras had usable turnover data").

### Offline test results (fake deterministic Yahoo)
```
BMR_NSE_LIST_FILE=/tmp/EQUITY_L.csv  ->  base 998 + ranked 502 = 1500 ✅  scanned 1458
NSE unreachable (fallback)           ->  base 998 + ranked 502 = 1500 ✅  scanned 1458
BMR_UNIVERSE_SIZE=1000               ->  base 998 + ranked   2 = 1000 ✅  scanned 966
```
Teeno cases me workbook ka label sahi (`NSE TOP1500` / `NSE TOP1000`) aur 6 sheets intact.
