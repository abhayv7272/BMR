# BMR Trinity — Ultra-Deep Diagnosis: "0 EXIT + 0 Open + 0 New" kyun aa raha hai

**Date:** 23-Oct-2026 · **Branch:** `arena/b59756be-daily-report` · **Code changed:** ❌ kuch nahi (sirf ye report file add ki hai)
**Report analysed:** `📈 BMR: 0 EXIT + 0 Open + 0 New (0💎) + 79 Radar | 22-Oct-2026` (19:16 IST)

---

## 1. TL;DR — Verdict

**Data fetching toota nahi hai. main.py me koi regression nahi hua. Ye "bug" nahi, screener ka
AND-gate + market ka CORRECTION regime ka collision hai.**

Teen proof-chains:

1. **Pipeline healthy hai** — 80/80 runs success, main.py ka runtime pichhle 5 hafte me constant
   (84–137 sec = poori 1000-stock scan chalti hai), aur 22-Oct ke report me 79 Radar + live RSI/MACD
   values hain. Agar Yahoo download fail hota to Radar 0 hota.
2. **Code 14-Sep ke baad change hi nahi hua** — `git log` me `main.py` ka last logic commit
   `9c403bf` (7-Sep) hai; uske baad ke commits sirf IST timezone, email retry aur workflow timing hain.
   Yaani "pehle aata tha, ab nahi" ka karan code nahi ho sakta.
3. **Aapke hi report ka data zero ko explain kar deta hai** — day ke 12 radar names me se sirf **1**
   aisa tha jo RSI + MACD dono gate cross karta hai, aur wo bhi do "falling-knife" guards me atak
   jata hai (neeche §4).

Asli story: market 3-4 hafte se ek one-way correction me hai (NIFTY 30D = **−4.59%**, regime =
**CORRECTION**). Is strategy ka setup hai "uptrend stock jo lower Bollinger par girke green hook de" —
lekin code me do guard aise hain jo **exactly usi girawat ko veto** karte hain jisse ye setup banta hai.
Isliye jab tak market sideways/bull me nahi aata, output structurally 0 rahega — chahe data perfect ho.

---

## 2. Jo verify kiya (evidence, guess nahi)

### 2.1 Workflow runs — sab green, koi skip/fail nahi

`gh run list --workflow=daily.yml --limit 80` → **80/80 `success`**, 14-Sep se 22-Oct tak.
Har trading day 2 scheduled slot (13:40 IST + 15:45 IST) + ek external dispatch (jab tak chala).

### 2.2 main.py ka actual runtime (step-level API se)

| Date | "Report banao aur email bhejo" step | Interpretation |
|---|---|---|
| 14-Sep | 107 s | full scan |
| 18-Sep | 114 s | full scan |
| 25-Sep | 127 s | full scan |
| 02-Oct | 88 s | full scan |
| 09-Oct | 84 s | full scan |
| 13-Oct | 95 s | full scan |
| 15-Oct | 133 s | full scan |
| 16-Oct | 127 s | full scan |
| 19-Oct | 128 s | full scan |
| 20-Oct | 133 s | full scan |
| 21-Oct | 92 s | full scan |
| 22-Oct | 137 s | full scan |

Agar Yahoo 1000 tickers me se aadhe bhi reject karne lagta, ye number 20–40 s pe gir jata. **Nahi gira.**
Matlab 10 chunks × 100 tickers download ho rahe hain, aur scan poora chal raha hai.

### 2.3 Universe data intact

Embedded catalog decode kiya: **1000 rows, 998 unique symbols**, 0 empty names.
(`INOXGREEN` aur `TRIVENI` duplicate hain — harmless, bas 2 tickers do baar scan hote hain.)

### 2.4 Repo history

`main.py` ka last logic-touching commit: **7-Sep (`9c403bf`)**.
14-Sep ke baad ke sabhi changes = IST timestamp, SMTP retry, workflow cron/guard. Screener ki ek bhi
threshold, condition ya formula 6 hafte se touch nahi hui.

---

## 3. Aapke 22-Oct report ka funnel math (yahi asli jawab hai)

Report me Radar = 79, lekin **Radar ka matlab "trigger ke paas" nahi hai**. Radar condition
(`main.py:427-429`) = uptrend + close lower band se **0–3.5%** upar + RSI ≤ 45. Trigger ke liye
alag se chahiye: band ka **aaj/ kal pierce** + green candle + RSI hook + MACD turn.

Top-12 radar names (jo band ke sabse paas hain, 0.1–0.5%):

| Stock | RSI | MACD turning? | RSI ≤ 40? | Dono gate pass? |
|---|---|---|---|---|
| LLOYDSENGG | 42.4 | ⏳ Wait | ✗ | ✗ |
| NEOGEN | 41.1 | ⏳ Wait | ✗ | ✗ |
| RATEGAIN | 35.2 | ⏳ Wait | ✓ | ✗ (MACD) |
| KTKBANK | 41.0 | ⏳ Wait | ✗ | ✗ |
| **ALIVUS** | 34.7 | 🟢 YES | ✓ | **✓ (1)** |
| CALSOFT | 36.5 | ⏳ Wait | ✓ | ✗ (MACD) |
| FLUOROCHEM | 39.8 | ⏳ Wait | ✓ | ✗ (MACD) |
| MANORAMA | 33.7 | ⏳ Wait | ✓ | ✗ (MACD) |
| WELCORP | 43.9 | ⏳ Wait | ✗ | ✗ |
| APLAPOLLO | 40.8 | ⏳ Wait | ✗ | ✗ |
| TI | 35.5 | ⏳ Wait | ✓ | ✗ (MACD) |
| AUROPHARMA | 41.4 | 🟢 YES | ✗ (41.4) | borderline |

**12 me se 1 hi candidate** (ALIVUS) trigger ke दरवाजे tak pahuncha — aur usko bhi 2 slope guards,
green candle aur 1.2–8% risk band cross karna tha. Isliye `0 New`. Ye "data gayab" nahi, **funnel ka
normal output** hai. Baaki 67 radar names 0.6%–3.5% door hain — wo trigger ho hi nahi sakte.

> **Deduction:** report me `0 Open` + `0 EXIT` + tracker 25 sessions peeche tak dekhta hai
> (`TRACK_DAYS = 25`, `main.py:18`) → matlab **pichhle ~25 trading sessions (lagbhag 17-Sep se aaj) me
> ek bhi signal qualify nahi hua**. Aapka "2 week" observation actually ~5 hafte ka drought hai.

---

## 4. Asli culprit: teen gates jo correction me mathematically band ho jate hain

### 4.1 `bb_slope_ok` — sabse bada dushman (`main.py:348`)

```python
bb_slope_ok = not (not np.isnan(bb_low_slope[i]) and bb_low_slope[i] < -0.012)
# BB_Lower ka (aaj - 3 din pehle) / 3 din pehle  >=  -1.2%  hona chahiye
```

Lower band = MA20 − 2σ. 3 din me MA20 ka change ≈ **−3 × daily drift** (3/20 weight ka simple maths).
Yaani veto tab lagta hai jab stock **~0.4%/din se tez** gire. Maine simulate kiya:

| Stock ka daily drift | BB_Lower 3-bar slope | Veto? (−1.2% rule) |
|---|---|---|
| −0.80%/din | −2.34% | ❌ VETO |
| −0.60%/din | −1.75% | ❌ VETO |
| −0.50%/din | −1.45% | ❌ VETO |
| −0.40%/din | −1.15% | ✅ pass |
| −0.20%/din | −0.56% | ✅ pass |
| 0.00% | 0.00% | ✅ pass |

Ab dekho contradiction: trigger ke liye chahiye **"RSI ≤ 40 + lower band touch"** (yaani stock gir raha ho)
aur **"band ki slope > −1.2%"** (yaani stock na gire). RSI 33–40 wale stock ka drift normally
−0.5% se −1.5%/din hota hai → **wo is gate par 100% reject hote hain.** Sirf sideways stock bachta hai,
aur sideways stock lower band ko RSI 40 se neeche touch hi nahi karta.

**Yehi ek condition akeli pichhle 5 hafte ka zero explain karne ke liye kaafi hai.**

### 4.2 `slope_ok` — EMA50 5-session guard (`main.py:342`)

EMA50 aaj, 5 din pehle se 0.2% se zyada neeche ho to reject. Correction me har stock ka EMA50
5 din me 0.5–2% neeche hota hai → reject. Simulation me bhi ek genuine "−1%/din × 5 din, phir +1.4%
bounce" setup yahin fail hua:

```
A) Healthy uptrend, 5 din −1.0%/din, aaj +1.4% bounce (textbook setup)
   RSI 32.1 | BB slope −2.02% | MACD turn ✓ | green candle ✓ | risk 2.75% ✓
   uptrend ✓  pierced ✓  rsi_oversold ✓  rsi_hook ✓  macd ✓  candle ✓  wick ✓  risk-band ✓
   ema50_slope ✗   bb_slope_ok ✗        -->  REJECTED
```

Wahi setup halka ho to pass ho jata hai:

```
B) 4 din −0.6%/din, aaj +1.2%   --> ALL GATES PASS ✅
C) Flat consolidation +0.8%     --> ALL GATES PASS ✅
```

Matlab screener sirf **halki girawat / sideways** wale setups leta hai. Market jab ek hi direction me
tez girta hai, output zero — by design, bug nahi.

### 4.3 Ek-din ka trigger, 10 conditions ka AND

`candle_ok` (close > open, green day) + `rsi_hook` (RSI aaj badha) + `macd_turn` (hist aaj badha) +
`pierced_lower` (kal/aaj band toota) — chaaron **ek hi din** ghatni chahiye. Correction me green days
kam hote hain, aur jab green day aata hai to EMA50/BB slope guards pehle hi reject kar chuke hote hain.
Isliye "799 stocks me 0" nahi, "~12 real candidates me 0" — jo statistics ke hisaab se normal hai.

---

## 5. Code me jo REAL bugs / blind spots mile (aaj ka karan nahi, par khatarnaak)

Ye sab **silent** hain — inki wajah se data failure aur market drought dikhne me ek jaise lagte hain.
Isliye "0" dekh kar pata nahi chalta ki problem kya hai.

| # | Line | Bug | Impact |
|---|---|---|---|
| 1 | `main.py:511-512` | `except Exception: continue` per-ticker | koi bhi indicator/column error **chupchaap** ticker skip kar deta hai. Na log, na counter. |
| 2 | `main.py:284-287` | batch download fail → `print` + `continue` | ek chunk (100 stocks) fail hua to 10% universe gayab, run phir bhi green. |
| 3 | `main.py:300-302` | `dropna()` ke baad `i = len(df)-1` — **koi fresh-bar check nahi** | Yahoo market close ke baad naye bar me `Close = NaN` deta hai (aapke notebook ka §7 isi ko fix karta hai). Yahan wo bar chupchaap drop ho jata hai → screener **kal ki candle** pe chalta hai, par report header aaj ki date dikhata hai. Ek din ka lag = 1-day trigger ka permanent miss. |
| 4 | `main.py:542-556` | SCAN SUMMARY sirf console me | Actions logs blob-storage pe hain; report/Excel me scanned count, failed chunks, data-date kahin nahi. |
| 5 | `main.py:774-796` | Sheet 4 ka naam "Market Regime & **Breadth**" hai par breadth (advancers/decliners, % above EMA200, scanned count) **hai hi nahi** | breadth ke bina correction vs data-failure distinguish karna impossible. |
| 6 | `requirements.txt` | `yfinance>=0.2.54,<1` (unpinned) | yfinance ka koi bhi minor release `yf.download` ka column/auto_adjust behaviour badal sakta hai → silent partial data. |
| 7 | `main.py:427` | Radar 3.5% + RSI ≤ 45 | 79 ka number trigger funnel jaisa lagta hai, par asli funnel ~12. Isi se "79 radar hain phir bhi 0" ka confusion. |
| 8 | workflow | external `repository_dispatch` **14-Oct ke baad band** (last: run 38563650525) | reports 18:00 ki jagah 19:00–21:00 IST pe aa rahi hain. cron-job.org trigger dobara on karna hoga. |

**Note (limitation):** is sandbox se main Actions logs aur artifacts download nahi kar saka
(GitHub blob storage allowlist me nahi hai) aur Yahoo Finance reachable nahi hai, isliye live replay
nahi kar paya. Diagnosis run-metadata + code + aapke report ke numbers par based hai — teeno
independent sources same conclusion de rahe hain.

---

## 6. Kya NOT toota (isliye tension na lein)

- ✅ Yahoo se 1000 stocks ka 1-year data aa raha hai (runtime + 79 radar + varied RSI/CMP values proof hain)
- ✅ NIFTY benchmark + regime calculation chal raha hai (CMP ₹22,687.65, 30D −4.59%, EMA-based regime)
- ✅ Excel 5 sheets ban rahi hain, mail ja rahi hai (attachment 15 KB, 22-Oct 19:16)
- ✅ Position tracker engine chal raha hai — usne 25 sessions scan kiye aur imaandaari se 0 nikala
- ✅ Universe catalog (1000 rows) intact
- ✅ Workflow guard/duplicate logic sahi kaam kar raha hai (22-Oct 20:47 wala run 10 sec me skip hua kyunki 19:16 wala already artifact bana chuka tha)

---

## 7. 2-minute checks jo aap khud kar sakte hain (koi code change nahi)

1. **Data date confirm karein:** kisi bhi app pe NIFTY 50 ka **22-Oct-2026 close** dekhein.
   Report me `NIFTY 50 CMP = ₹22,687.65` hai. Agar ye 22-Oct ka close hai → data fresh hai, sab theek.
   Agar ye 21-Oct ka close hai → bug #3 (NaN latest bar) confirm ho jayega.
2. **Actions log** (run 39789385593) me `SCAN SUMMARY` block dekhein:
   `1000 STOCKS SCANNED` + `Actionable: 0` + `Radar: 79` + `Tracked: 0` aana chahiye.
   Agar wahan scanned count 1000 se kam hai → bug #2 pakda gaya.
3. Excel ki **"Market Regime & Breadth"** sheet kholke NIFTY 30D = −4.59% confirm karein.

---

## 8. Recommended fixes (maine lagaye NAHI hain — aapke approval ke baad)

Priority order (agar aap bolein to main ye is branch par kar deta hoon):

1. **Diagnostics add karo (zero behaviour change):** per-gate rejection counter
   (`rs_ok: 12, bb_slope_ok: 11, macd_turn: 10, risk_band: 9…`), scanned/failed/skipped counts,
   aur data ka last date — console + Sheet 4 me. Isse har din pata rahega ki 0 kis gate ki wajah se hai.
2. **Fresh-bar guard + backfill:** `dates[-1]` aaj nahi hai to 15-min data se latest candle rebuild karo
   (aapke notebook ka cell §4 already yahi karta hai), warna report me saaf likho "data as of DD-MMM".
3. **Slope guards ko regime-aware karo:** correction me `bb_slope_ok` ko `-0.012` se `-0.03` karo, aur
   `ema50_slope` ko EMA50 ke bajaye **price vs EMA50 distance** par base karo — warna strategy apne hi
   setup ko reject karti rahegi.
4. **`except Exception` ko `except Exception as e: failures.append(...)` karo** — silent skip band.
5. `yfinance` ko pin karo (jo version aaj chal raha hai wahi lock ho).
6. cron-job.org ka external dispatch dobara on karo (6 PM delivery ke liye).

---

### Bottom line

> Data pipeline theek hai, main.py theek hai, tumhari soch bhi theek hai — **market galat hai.**
> Screener ka design "uptrend me halka dip" dhoondhta hai; abhi NIFTY −4.59%/30D correction me halka dip
> hi nahi mil raha. `0` ek valid answer hai — par code us `0` ka **karan** kahin print nahi karta,
> isliye wo bug jaisa lagta hai. Fix #1 (diagnostics) karte hi har roz saaf dikhega:
> "aaj 0 kyunki 11/12 ne bb_slope_ok fail kiya".
