# Pre-Fix Safety Check — "in fixes se false signals aayenge kya?"

**Date:** 23-Oct-2026 · **Code changed:** ❌ kuch nahi (ye sirf analysis hai)
**Sawal:** bugs fix karne se galat/extra signals to nahi aa jayenge?

## Seedha jawab

**6 me se 5 fixes signal-generation ko chhoote hi nahi — unse ek bhi naya signal nahi aayega.**
**Sirf 3 fixes signal selection badalte hain**, aur unme se 2 (slope guard + MACD gate) ka blast radius
itna bada hai ki blind apply karna galat hoga:

| Fix | Signal count par asar | False-signal risk | Verdict |
|---|---|---|---|
| 1. Diagnostics (gate-wise reject counters, scanned count, data-date) | **0** | none — sirf logging | ✅ aaj hi safe |
| 2. `except Exception` ko log karo (silent skip band) | **0** (jab tak koi error nahi) | na ke barabar — jo pehle chupchaap skip ho rahe the wo process honge | ✅ safe |
| 3. Fresh-bar guard (data as-of label) | **0** | none | ✅ safe |
| 4. Universe/dup cleanup, Sheet-4 breadth | **0** | none | ✅ safe |
| 5. yfinance version pin | **0** agar *aaj chal rahi version* pin karein; ⚠️ agar newest pin karein to auto_adjust badal sakta hai → saare indicators shift | low (pin current) | ⚠️ version freeze karke + shadow compare |
| 6. 15-min backfill se latest candle bharna | **kuch naye signals** (jo kal miss ho rahe the) | ⚠️ **market khula ho to partial candle ka signal** = asli false signal | ⚠️ sirf 15:30 IST ke baad, warna "preview" |
| 7. `bb_slope_ok` −1.2% → −3% | **2.9×** signals | ⚠️ marginal signals ka SL rate 23% → 31% | ❌ blind nahi, backtest chahiye |
| 8. EMA50 slope guard OFF | **6.4×** signals (31 → 197/38 sessions) | ⚠️ bharpoor | ❌ na karein |
| 9. `bb` −3% + EMA50 OFF | **17.4×** signals (31 → 539) | ⚠️⚠️ portfolio 1% risk/trade pe flood | ❌ na karein |
| 10. MACD turn gate OFF | **1.8×** signals | ⚠️ marginal SL rate **36%** — sabse kharab | ❌ na karein |
| 11. Risk band 1.2–8% → 1.2–12% | **1.4×** signals | marginal SL 31% | ⚠️ backtest ke baad |

*(Scan #7–#11 ke numbers niche simulation se hain.)*

---

## Simulation kaise kiya (aur uska limit)

main.py ki **exact** gate chain (line 332–372) ek calibrated synthetic market pe chalayi:
1000 stocks × 260 sessions, 200 sessions bull phir 60 sessions correction −0.15%/din
(= NIFTY −4.59%/30D, exactly aapke 22-Oct report jaisa), mean-reversion + stock-specific alpha.
Phir last 38 sessions pe signals count kiye aur har signal ka forward outcome simulate kiya
(T1 +2% / SL / 25-session TIME).

> ⚠️ **Sach:** synthetic data se **"kitne extra signals aayenge"** (blast radius) sahi pata chalta hai,
> lekin **real market ka win-rate nahi**. SL% ke numbers sirf *direction* batate hain (marginal signals
> ki quality girti hai), guarantee nahi. Asli backtest NSE data pe hi hoga.

### Result table

```
38 sessions × 1000 synthetic stocks | V0 = aaj ka code
  V0 aaj ka code            n=  31
  V1 bb -> -2.0%            n=  58 (1.9x)   marginal +27   SL 26%
  V2 bb -> -3.0%            n=  89 (2.9x)   marginal +58   SL 31%   <-- quality girti hai
  V3 EMA50 guard OFF        n= 197 (6.4x)   marginal +166  SL 22%
  V4 bb -3% + EMA50 OFF     n= 539 (17.4x)  marginal +508  SL 24%
  V5 MACD gate OFF          n=  56 (1.8x)   marginal +25   SL 36%   <-- sabse kharab
  V6 risk band -> 12%       n=  44 (1.4x)   marginal +13   SL 31%
```

**Padhne ka tareeka:** V0 me 38 sessions me 31 signals. Sirf `bb_slope_ok` ko −3% karne se 89 ho jate
hain — yaani **3x trades, wahi 1% risk per trade** → exposure 3x. Aur jo 58 extra signals aaye, unka
SL-hit 31% hai vs baseline 23%. Isliye ye fix "bug fix" nahi, **strategy ki definition badalna** hai —
usko bug list me nahi, backtest list me rakhna chahiye.

---

## Fix-by-fix: kyun 5 fixes bilkul safe hain

**Fix 1–4 (diagnostics, logging, freshness label, breadth)** — ye code path sirf *padhta* hai:
`print`, counter dict, Excel cell, aur ek "data as of <date>" string. Koi `if` condition badal kar
signal banne/marne ka faisla nahi badalta. **Mathematical guarantee: output identical.**
Verify karne ka tareeka: fix lagane ke baad `results.json` ka hash aaj ke run se **bilkul same** hona chahiye
(aur wahi 79 radar / 0 signal aana chahiye). Ye ek built-in regression test hai — main isko run karke dikha sakta hoon.

**Fix 5 (yfinance pin)** — khatra sirf tab hai jab aap *naya* version pin karein, kyunki naye yfinance me
`auto_adjust` default badal chuka hai (Close/High/Low adjusted prices ban jate hain) → RSI/MACD/ATR ke
values thode shift → kuch signals palat sakte hain. Isliye pin **jo version aaj pip install kar raha hai
wahi** karna hai (aaj ke run ka freeze), taaki behaviour freeze ho jaye.

**Fix 6 (fresh bar)** — yahan ek asli false-signal vector hai:
- Agar run **15:30 IST ke baad** chalta hai → 15-min data = final close → jo signal aayega wo *sahi* hai
  (aaj missing tha, ab milega). Ye "false" nahi, "recovered" signal hai.
- Agar run **market ke andar** chalta hai (manual `Run workflow` 11 baje, ya cron jaldi fire ho jaye aur
  guard bypass ho) → 15-min se bana candle **adhoora** hai → us par signal = **false signal**.
- Isliye rule: backfill sirf tab jab `IST >= 15:35` ho; warna Excel/email me header
  **"INTRADAY PREVIEW — not a close-based signal"** aur us candle ko actionable list me mat daalo.

---

## Safe rollout plan (agar aap haan bolein)

**Phase 1 — aaj (0% signal change):**
- fixes #1–#5 (diagnostics + logging + freshness label + breadth + pin)
- validation: wahi 79 radar / 0 signal reproduce ho, aur console pe aisa output aaye:
  `reject: ema50_slope=37, bb_slope_ok=41, rsi_oversold=23, macd_turn=9, candle=2, risk_band=3`

**Phase 2 — 10 sessions shadow mode (0% signal change):**
- loosened variants **compute** karo par email me actionable mat bhejo:
  Excel me nayi sheet **"Shadow — loosened filters"** (bb −3%, EMA50 off, MACD off) → sirf tracking
- har shadow signal ka forward result auto-track (T1/SL/TIME) — wahi tracker engine jo already hai
- 10 sessions ke baad **asli data** se pata chal jayega: kya loosening se edge milta hai ya sirf noise

**Phase 3 — promote sirf tab jab:**
- shadow variant ka hit-rate ≥ current variant AND
- signal volume cap ke andar (max 3–5 new/day), AND
- NIFTY regime BULL ho (correction me loosened mode band rahe)

**Agar kabhi loosen karein to ye 3 safety nets saath lagayen:**
1. `vol[i] > vol_sma[i]` ko **hard gate** banao (abhi sirf scoring me hai) — volume-less dip = fake
2. per-day cap: top 5 by rank, baaki radar me
3. loosened mode me risk per trade 1.0% → 0.5%

---

## Bottom line

> **Bugs fix karne se false signals ka koi risk nahi hai** — kyunki 5 fixes output ko *chhoote hi nahi*
> (sirf dikhate hain), aur fresh-bar fix galat signals nahi, *chhoote hue sahi* signals laata hai
> (bas 15:30 IST ke baad hi chalayein).
>
> **False signals ka asli risk threshold badalne me hai** — `bb_slope_ok` aur MACD gate. Simulation
> kehta hai wahan signals 2–6× ho jayenge aur unki quality neeche jaati hai. Isliye wahan "fix" nahi,
> **backtest + shadow mode** chahiye. Aapki 0-signal problem ka ilaaj bhi wahi hai — par **data se
> decide hoga, guess se nahi.**
