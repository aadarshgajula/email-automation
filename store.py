"""Reading and writing leads.csv and state.json."""
import csv
import datetime as dt
import json
import os
from urllib.parse import urlparse

LEADS_FILE = "leads.csv"
STATE_FILE = "state.json"

FIELDS = [
    "place_id", "business", "website", "email", "address", "lat", "lng", "timezone",
    "issue", "observation", "status", "found_at", "sent_at", "message_id",
    "followup_at", "updated_at", "note", "niche",
]
# niche: a key of config.NICHES (which email template the lead gets)
# status values:
#   ready        found, has an email, site has an issue -> will be emailed
#   no_email     no email found on the site
#   no_site      no website, or only a social/directory page
#   good_site    site looked fine, skipped
#   duplicate    email already used by another lead
#   sent         first email sent
#   followed_up  follow-up sent, sequence finished
#   replied      they replied, sequence stopped
#   opted_out    they asked not to be contacted
#   bounced      address doesn't exist


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def iso(d):
    return d.isoformat(timespec="seconds")


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def domain_of(value):
    """Bare domain from a URL or email address, without www."""
    if not value:
        return ""
    value = value.strip().lower()
    if "@" in value and "://" not in value:
        d = value.rsplit("@", 1)[1]
    else:
        if "://" not in value:
            value = "http://" + value
        d = urlparse(value).netloc.split(":")[0]
    return d[4:] if d.startswith("www.") else d


def load_leads():
    if not os.path.exists(LEADS_FILE):
        return []
    with open(LEADS_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in FIELDS:
            r.setdefault(k, "")
            if r[k] is None:
                r[k] = ""
    return rows


def save_leads(leads):
    tmp = LEADS_FILE + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(leads)
    os.replace(tmp, LEADS_FILE)


def load_state():
    state = {"state_index": 0, "start_date": None, "sent_log": {}}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state.update(json.load(f))
    return state


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, STATE_FILE)
