# Mail 6 baje pakka kaise aaye — setup guide

## Problem kya thi

Mail 6 PM IST ki jagah **raat 10–11:40 PM** aa raha tha.

Wajah: **GitHub ka scheduled cron is repo pe roz 3–6 ghante late chalta hai.**
7 din ka naapa hua data:

| Din | Cron ka time | Mail aaya (IST) | Deri |
|---|---|---|---|
| 08 Sep | 6:00 PM | 10:20 PM | 4.3 h |
| 09 Sep | 6:00 PM | 10:23 PM | 4.3 h |
| 10 Sep | 6:00 PM | 10:09 PM | 4.1 h |
| 11 Sep | 6:00 PM | 10:14 PM | 4.2 h |
| 12 Sep | 6:00 PM | 9:17 PM  | 3.3 h |
| 13 Sep | 6:00 PM | 10:07 PM | 4.1 h |
| 14 Sep | 6:00 PM | 11:41 PM | 5.7 h |

**Average 4.3 ghante. Sabse kam bhi 3.3 ghante.**

Ye "peak minute" ki baat nahi hai — deri har roz hai. Sirf GitHub cron
ko exact 6 PM IST par rakhna reliable **nahi** hai, kyunki GitHub use late
chala sakta hai.

Repo me ab old `12:30 UTC / 6:00 PM IST` GitHub slot hata diya gaya hai.
Backup ke liye workflow me adjusted slots hain:

- `08:10 UTC` / `01:40 PM IST` — observed GitHub delay ke baad approx 6 PM IST
- `10:15 UTC` / `03:45 PM IST` — market close ke baad safety net

## Best Solution

`repository_dispatch` **0–2 second** me chalta hai (verify kiya gaya —
push aur manual dispatch dono turant chale). Exact 5:55-6:00 PM IST ke
liye bahar se trigger karo.

---

## Setup — 5 minute, ek baar (FREE)

### Step 1 — GitHub token banao

1. Kholo: https://github.com/settings/personal-access-tokens/new
2. **Token name**: `daily-report-trigger`
3. **Expiration**: `No expiration` (ya 1 year)
4. **Repository access** → `Only select repositories` → **daily-report** chuno
5. **Permissions** → `Repository permissions` → **Contents** → `Read and write`
6. **Generate token** dabao → token copy karo (`github_pat_...`)

> Ye token sirf isi repo pe kaam karta hai. Kahin aur paste mat karna.

### Step 2 — cron-job.org pe scheduler lagao

1. https://cron-job.org/en/signup/ pe free account banao
2. **CREATE CRONJOB** dabao
3. Bharo:

   | Field | Value |
   |---|---|
   | **Title** | `BMR Daily Report` |
   | **URL** | `https://api.github.com/repos/abhayv7272/daily-report/dispatches` |
   | **Schedule** → Custom | Days: **Mon–Fri** · Time: **17:55** |
   | **Timezone** | `Asia/Kolkata` ← *ye zaroor set karna* |

4. **ADVANCED** tab kholo:

   - **Request method**: `POST`
   - **Headers** — teen add karo:

     | Key | Value |
     |---|---|
     | `Accept` | `application/vnd.github+json` |
     | `Authorization` | `Bearer github_pat_...` ← Step 1 wala token |
     | `Content-Type` | `application/json` |

   - **Request body**:
     ```json
     {"event_type":"daily-report"}
     ```

5. **CREATE** dabao

### Step 3 — test karo

cron-job.org pe job kholo → **TEST RUN** dabao.

- Response **`204 No Content`** aana chahiye ✅
- GitHub → Actions tab me run turant dikhega
- 2 minute me mail aa jayega

`401` aaye to token galat hai. `404` aaye to token ko repo ka access nahi mila.

---

## Setup ke baad

- Mail roz **5:57 PM IST** tak (5:55 trigger + ~2 min run)
- Sirf **Mon–Fri** (NSE weekend pe band)
- 6 baje se pehle chahiye to cron-job.org pe time badal lo

## Backup

Agar cron-job.org kabhi down ho, workflow me 2 GitHub cron backup slots
abhi bhi hain (1:40 PM aur 3:45 PM IST fire). GitHub inhe late chala sakta
hai, par mail bilkul na aane se behtar hai.

Duplicate guard laga hua hai — ek din me market close ke baad **ek hi mail**
aayega, chahe kitne bhi trigger lagein. Subah ka manual/test run evening
mail ko skip nahi karega.

## Alternative (agar cron-job.org pasand na aaye)

Koi bhi scheduler chalega jo HTTP POST kar sake — EasyCron, Zapier,
Make.com, ya apne phone pe Tasker. Bas wahi URL + headers + body use karo.
