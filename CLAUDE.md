# Outreach automation – project context

## What this is

A small cold-outreach system for a freelance web designer based in India (timezone Asia/Kolkata).
It finds US plumbing companies and interior designers whose websites need work, emails them a personalized pitch
for a new website ($350 one-off, live within a week), sends one follow-up, and stops for anyone who
replies, opts out or bounces. Sending is 30–50 emails a day from the owner's **personal Gmail account**.

It runs for free on **GitHub Actions** (private repo) on an hourly schedule. There is no server and
no paid service. Keeping it free is a hard requirement: no Google Places API (it needs billing),
no paid email providers, no paid lead databases.

## Files

| File | Role |
|---|---|
| `config.py` | All tunable settings: `NICHES` (OSM tags, name pattern, name excludes per kind of business), state order, send window, warm-up caps, follow-up delay. No secrets. |
| `templates.py` | Email subject, footer, and `BODY`/`FOLLOWUP_BODY` dicts keyed by niche, with `{business}`, `{observation}`, `{website}`, `{sender_name}` placeholders. |
| `store.py` | Reads/writes `leads.csv` and `state.json` (atomic writes). Defines lead fields and status values. |
| `find_leads.py` | Lead finder: OpenStreetMap Overpass query per US state → scrape website for email → check site → mark lead `ready` or skip. |
| `send.py` | Checks Gmail inbox over IMAP for replies/opt-outs/bounces, then sends due emails over SMTP. Modes: `run`, `preview`, `test`. |
| `.github/workflows/outreach.yml` | Schedule + manual runs; commits `leads.csv`/`state.json` back to the repo after each run. |
| `outreach.yml` | Convenience copy of the workflow at the repo root (not used by GitHub). Keep it in sync or delete it. |
| `SETUP.md` | Non-technical setup guide for the owner. Update it when setup steps change. |
| `leads.csv`, `state.json` | Created by the workflow. Data, not code. |

## How it works

### Finding leads (`find_leads.py`)
- Source: OpenStreetMap via the public Overpass API (no key). Tries several Overpass mirrors and
  gives up politely if all are busy; the next run retries the same state.
- Niches live in `config.NICHES` (currently `plumbing`, `interior_design`). One Overpass query per
  state covers all niches' tags and name patterns; `niche_of()` assigns each result to the first
  niche whose tag or name matches, then that niche's `exclude` list filters it (plumbing supply
  stores and big franchises; car/boat upholsterers). The niche is stored per lead (`niche` column);
  `send.py` picks `templates.BODY[niche]` / `FOLLOWUP_BODY[niche]` (empty niche → `interior_design`).
  Adding a niche = a `NICHES` entry plus a template under the same key (`template_ready` enforces it).
- States are processed in `config.STATES` order; progress is `state_index` in `state.json`.
  Up to `MAX_STATES_PER_RUN` states per run, and only while fewer than `LEAD_BUFFER` leads are `ready`
  (unless run with `--force`, which the manual `find` mode does).
- Website handling: social/directory URLs (facebook, houzz, yelp…) → `no_site`. Duplicate domains skipped.
- Email: OSM `email`/`contact:email` tag if present, plus mailto links, Cloudflare `data-cfemail`
  decoding, and regex on the homepage; if none, up to 3 contact/about pages. Prefers an address on
  the site's own domain. Junk addresses filtered (`BAD_EMAIL_BITS`, image extensions).
- Site check, in priority order, produces one `observation` sentence:
  1. PageSpeed Insights mobile performance score < `PAGESPEED_BAD_SCORE` (50) → `slow_mobile`
  2. site not on https → `not_secure`
  3. footer © year ≥ `OLD_COPYRIGHT_YEARS` (3) years old → `outdated`
  No issue → `good_site` (not emailed). PageSpeed uses `GOOGLE_API_KEY` if set (no billing needed),
  otherwise keyless; failures just skip that check.
- Websites are checked 6 at a time in a thread pool, in groups of 12, saving after each group.
- Time zone: from lat/lon via `timezonefinder` (IANA name stored per lead).

### Sending (`send.py`)
- `run` mode: first scans INBOX (read-only, last `INBOX_LOOKBACK_DAYS`) for:
  - bounces (`X-Failed-Recipients` or mailer-daemon messages) → `bounced`
  - replies from a lead's address or (non-freemail) domain, received after `sent_at` →
    `opted_out` if the reply text matches `OPT_OUT_RE`, else `replied`.
    Quoted text (lines starting `>` and everything after "On … wrote:") is stripped first,
    because the footer we send contains "no thanks".
- Then sends, only to leads whose **local time** is 09:00–11:59 Mon–Fri (`in_window`).
  Follow-ups (status `sent`, ≥ `FOLLOWUP_AFTER_DAYS` old) go first, then new `ready` leads.
- Limits: daily cap from warm-up (`WARMUP = [(7,10),(14,25)]`, then `FULL_DAILY_CAP` 50; counted
  per UTC day in `state.sent_log`, follow-ups included), max `MAX_PER_RUN` per run, random
  `GAP_SECONDS` pause between emails. Warm-up day 1 = first day anything was actually sent.
- Each email is plain text, from `SENDER_NAME <GMAIL_ADDRESS>`, with its own Message-ID; follow-ups
  are threaded via In-Reply-To/References and "Re: " subject. Footer always includes postal address
  and an opt-out line.
- Leads and state are saved after every single send so a crash can't cause double-sending.
- Any SMTP error other than a rejected recipient stops the run (protects the Gmail account).
- Safety guards: refuses to send if `[PASTE YOUR EMAIL BODY HERE]` is still in the template or if
  `SENDER_POSTAL_ADDRESS` / Gmail secrets are missing.
- `preview` mode prints the next 5 emails to the GitHub run summary; sends nothing.
- `test` mode sends one real example email per niche to the owner's own address only.

### Scheduling (`.github/workflows/outreach.yml`)
- Cron `17 13-20 * * 1-5` (UTC, hourly) covers 9am–noon on both US coasts in summer and winter time.
  The script decides per lead whether it is inside that lead's window.
- Scheduled runs only execute when repo variable `OUTREACH_ENABLED` is `true`; manual runs always work.
- Manual run modes: `find`, `preview`, `test`, `run`.
- `concurrency: outreach` prevents overlapping runs. Timeout 60 minutes.
- After each run the bot commits `leads.csv` and `state.json`. **Always `git pull` before editing**,
  or pushes will conflict.
- Budget: private repos get 2,000 free Action minutes/month; keep runs short.

## Secrets (GitHub → Settings → Secrets and variables → Actions)
`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (Google App Password, not the real password),
`GOOGLE_API_KEY` (PageSpeed only, optional), `SENDER_NAME`, `SENDER_POSTAL_ADDRESS`.
Never write secrets into any file in this repo, never print them, never commit a `.env`.
For local testing, set them as environment variables in the terminal.

## Lead statuses (`leads.csv` → `status`)
`ready`, `no_email`, `no_site`, `good_site`, `duplicate`, `sent`, `followed_up`, `replied`,
`opted_out`, `bounced`. Only `ready` (first email) and `sent` (follow-up) are ever emailed.
`followed_up` is the end of the sequence (exactly one follow-up).

## Rules to keep (legal + deliverability)
- US CAN-SPAM applies (commercial email, B2B included): every email must contain a real postal
  address (street, registered PO box, or virtual mailbox; a city alone is not enough) and a working
  opt-out. Opt-outs must be honoured permanently. Don't remove the footer or the opt-out handling.
- No false claims in emails. The template must only state things the script actually checked
  (e.g. don't say "found you on Google Maps" or "great reviews"; leads come from OpenStreetMap and
  reviews aren't checked). The plumbing email links one generic example homepage
  (https://plumbing-mockup-alpha.vercel.app/, a fictional plumber). It must be described as an example,
  never as made for the recipient; a personalised version is offered on reply/follow-up.
  The interior design email has no link; its mock-up is offered on reply because none exists yet.
- Don't scrape Google Maps or Google search; it breaks Google's terms and gets blocked.
- Keep emails plain text, no images/attachments, at most one link. Keep volume ≤ 50/day from Gmail,
  keep the warm-up, keep the random gaps.
- If UK targets are ever added: UK law (PECR) only allows cold email to limited companies/LLPs,
  not sole traders or partnerships, and send window/times would need a UK schedule (09:00–11:59
  Europe/London ≈ 13:30–16:30 IST, cron around 08–11 UTC).

## Local development
```
pip install -r requirements.txt
# preview needs no secrets:
MODE=preview SENDER_NAME="Name" SENDER_POSTAL_ADDRESS="..." python send.py
# find (OSM is open; GOOGLE_API_KEY optional):
python find_leads.py --force
```
Don't run `MODE=run` locally against the real `leads.csv` unless intentionally sending; it sends real
email and the next Action run won't know unless the updated CSV is committed and pushed.

## Status / known limits
- OSM live queries haven't been verified end-to-end yet (the first manual `find` run is the live test).
  Overpass QL is in `osm_query()`; if a state returns errors or nothing, check that first.
- OSM has far fewer US businesses than Google Maps; states may run out in 1–2 months. Options:
  widen a niche's `names` pattern, add tags, add a niche, or reset `state_index` to 0 later.
- No manual lead import yet. A planned option: a `manual_leads.csv` (name, website) that
  `find_leads.py` merges in and processes like OSM results.
- Owner is not a developer; explain changes simply and update `SETUP.md` when setup changes.