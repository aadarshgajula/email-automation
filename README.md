# Outreach automation

Finds US plumbing companies and interior designers whose websites need work, and emails each one a short, personal pitch for a new website ($350, live within a week). Everything runs for free on GitHub Actions and sends from a personal Gmail account.

**Setting it up for the first time?** Follow [SETUP.md](SETUP.md) step by step. It takes about 30 minutes.

## What it does

1. **Finds businesses.** It searches OpenStreetMap (free, no account) one US state at a time for plumbers and interior designers.
2. **Checks their websites.** It visits each site, finds an email address, and looks for a real problem: a slow mobile speed score, no https ("Not secure"), or an old © year in the footer. Businesses with good sites are skipped.
3. **Sends the email.** Each business gets the email for its type, opening with one sentence about the problem found on its site.
   - Plumbers get a link to an example homepage: https://plumbing-mockup-alpha.vercel.app/
   - Interior designers are offered a free mockup if they reply.
4. **Follows up once,** 4 days later, then stops.
5. **Stops automatically** for anyone who replies, says "no thanks", or whose email bounces.

Emails go out only between 9:00 and 11:59, Monday to Friday, in **each business's own time zone**. Sending starts slowly to protect your Gmail account: 10 a day in week 1, 25 a day in week 2, then up to 50 a day.

## Files

| File | What it's for |
|---|---|
| [templates.py](templates.py) | The email text: one email and one follow-up for each type of business. **Edit this to change what you send.** |
| [config.py](config.py) | Settings: which businesses to search for, the order of states, daily limits, send times, follow-up delay. |
| [find_leads.py](find_leads.py) | Finds businesses and checks their websites. |
| [send.py](send.py) | Checks your inbox for replies and bounces, then sends emails. |
| [store.py](store.py) | Saves and loads the lead list. |
| [.github/workflows/outreach.yml](.github/workflows/outreach.yml) | The schedule that runs it all on GitHub. |
| `leads.csv` | Every business found and where it's up to (`ready`, `sent`, `replied`, …). Created automatically. |
| `state.json` | Progress through the states and how many emails were sent each day. Created automatically. |

## Running it by hand

On GitHub, go to **Actions → outreach → Run workflow** and choose a mode:

| Mode | What happens |
|---|---|
| `find` | Searches for new businesses right now. |
| `preview` | Shows the next 5 emails in the run summary. Sends nothing. |
| `test` | Sends you one example email for each type of business. Nobody else gets anything. |
| `run` | Does a normal run: checks your inbox, then sends whatever is due. |

Automatic runs happen every weekday only once the repository variable `OUTREACH_ENABLED` is set to `true` (see [SETUP.md](SETUP.md)).

## Rules it follows

- **US law (CAN-SPAM):** every email includes your postal address and a way to opt out. Anyone who opts out is never emailed again.
- **No false claims:** emails only mention things the script actually checked. The plumbing homepage is described as an example, not as something made for them.
- **Plain text only:** no images or attachments, and at most one link per email.
- **Free to run:** no paid services, and no scraping of Google Maps or Google search.

## Good to know

- **Pull before you edit:** the bot commits `leads.csv` and `state.json` after every run, so run `git pull` before editing files on your computer. If you edit on the GitHub website, you don't need to.
- **Keep secrets out of files:** your Gmail app password and other secrets go in GitHub Secrets, never in a file in this repo.
