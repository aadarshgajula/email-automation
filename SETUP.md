# Outreach automation: setup

What it does, every weekday:
1. Searches OpenStreetMap (free, no account) for plumbing companies and interior designers, one US state at a time.
2. Visits each website, finds an email address, and checks the site (Google mobile speed score, https, old © year).
3. Keeps only businesses whose site has a real issue, and writes one sentence about it into your email.
4. Sends from your Gmail between 9:00 and 11:59 in **each business's own time zone**, Monday-Friday.
5. Sends one follow-up 4 days later, and stops for anyone who replies, says "no thanks", or bounces.
6. Warms up: 10/day in week 1, 25/day in week 2, then 50/day (including follow-ups).

It runs on GitHub Actions (free). Do the setup on a computer; it takes about 30 minutes.

---

## 1. Gmail app password (5 min)

1. Turn on 2-Step Verification: https://myaccount.google.com/signinoptions/twosv
2. Create an app password: https://myaccount.google.com/apppasswords. Name it `outreach`. Copy the 16-character code.

This code can only send and read mail. It can't change your password or account, and you can delete it at that page any time to cut off access instantly.

## 2. Free Google key for the speed test (5 min, no billing)

This key is only for the mobile speed test. It needs **no billing account and no card**. The speed test also runs without a key, but Google limits keyless use heavily, so the key makes it reliable.

1. Go to https://console.cloud.google.com and create a project called `outreach`. Skip any billing prompts.
2. **APIs & Services → Library**: search for **PageSpeed Insights API** and enable it.
3. **APIs & Services → Credentials → Create credentials → API key**. Copy it.
4. Click the key → **API restrictions → Restrict key** → tick only **PageSpeed Insights API** → Save. If the key ever leaked, it could only run free speed tests.

## 3. Private GitHub repository (10 min)

1. Create a GitHub account if you don't have one, and turn on two-factor authentication (Settings → Password and authentication).
2. New repository → name `outreach` → choose **Private** (important: your lead list is stored in it) → Create.
3. **Add file → Upload files** and upload: `config.py`, `templates.py`, `store.py`, `find_leads.py`, `send.py`, `requirements.txt`, `SETUP.md`. Commit.
4. The workflow file sits in a hidden folder, which upload pages often skip. So: **Add file → Create new file**, type the name `.github/workflows/outreach.yml` (typing the slashes creates the folders), paste the contents of `outreach.yml` (a copy sits at the top of the zip so it's easy to find), and commit.

## 4. Add your secrets

Repository → **Settings → Secrets and variables → Actions → New repository secret**. Add these five:

| Name | Value |
|---|---|
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | the 16-character app password |
| `GOOGLE_API_KEY` | the speed-test key from step 2 (optional but recommended) |
| `SENDER_NAME` | the name to sign emails with |
| `SENDER_POSTAL_ADDRESS` | a real postal address (US law requires one in commercial email; a business address or PO box works) |

Secrets are encrypted. Nobody can view them after saving (not even you), they're hidden as `***` in run logs, and they're never in your code. Never paste them anywhere else, including into chats.

## 5. Add your email text

`templates.py` already has two emails: one for plumbers (it links your example homepage) and one for interior designers (no link). To change the wording: open `templates.py` on GitHub → pencil icon → edit the text → Commit. The opening line about their website is added above it automatically.

## 6. Test, then switch it on

Go to the **Actions** tab, click **outreach** on the left, then **Run workflow**, and pick a mode:

1. `find` – searches the first few states and fills `leads.csv` (takes 10–30 minutes). If OpenStreetMap's free server is busy, the run says so; just run it again later.
2. `preview` – open the finished run and scroll to the summary to read the next 5 emails exactly as they'll go out. Nothing is sent.
3. `test` – sends one real example to your own inbox. Check it arrives and reads well.

When you're happy: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**, name `OUTREACH_ENABLED`, value `true`. From then on it runs by itself every weekday evening (India time). Scheduled runs never happen until this variable is set.

**To pause:** change `OUTREACH_ENABLED` to `false`.

## Day to day

- **Replies arrive in your Gmail** like normal email. Answer them yourself; the system already stops emailing that person.
- **See everything** in `leads.csv` in the repo (status, email, issue found, dates). Each run's summary on the Actions tab lists who was emailed.
- **Change settings** in `config.py`: what to search for (`NICHES`), the order of states, daily limits, send window, follow-up delay.
- **Running low on leads?** OpenStreetMap lists fewer US businesses than Google Maps, so the states may run out after a month or two. The run will say so. You can then widen the name search in `config.py` (for example add `home staging|decorator`), or reset `state_index` in `state.json` to 0 later to pick up newly mapped businesses.
- **Warning signs**: several bounces in a day, or Gmail showing a sending-limit error in a run. Pause for a few days if that happens.

## Free-tier usage

- GitHub Actions: private repos get 2,000 free minutes a month. This setup should use roughly 1,000–1,400. Check under Settings → Billing and plans.
- OpenStreetMap and the PageSpeed speed test are free. Nothing in this setup needs a card.
