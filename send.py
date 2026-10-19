"""Check Gmail for replies, opt-outs and bounces, then send emails to leads whose
local time is inside the send window.

MODE environment variable:
  run      check inbox, then send (what the schedule uses)
  preview  show the next few emails without sending anything
  test     send one real example email to yourself
"""
import datetime as dt
import email
import imaplib
import os
import random
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

import config
import templates
from store import domain_of, iso, load_leads, load_state, parse_iso, save_leads, save_state, utcnow

MODE = (os.environ.get("MODE") or "run").strip().lower()
SENDER = os.environ.get("GMAIL_ADDRESS", "").strip()
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
SENDER_NAME = os.environ.get("SENDER_NAME", "").strip() or SENDER
POSTAL = os.environ.get("SENDER_POSTAL_ADDRESS", "").strip()
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")

OPT_OUT_RE = re.compile(
    r"\b(no thanks|no thank you|not interested|unsubscribe|remove me|take me off|"
    r"do not (?:contact|email)|don'?t (?:contact|email)|stop emailing|stop)\b",
    re.I,
)
FREEMAIL = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com",
    "msn.com", "live.com", "me.com", "comcast.net", "att.net", "verizon.net",
}


def out(text=""):
    print(text)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as f:
            f.write(text + "\n")


# --------------------------------------------------------------------------- Emails
def render(lead, followup=False):
    ctx = {
        "business": lead["business"],
        "observation": lead["observation"],
        "website": lead["website"],
        "sender_name": SENDER_NAME,
    }
    subject = templates.SUBJECT.format(**ctx)
    if followup:
        subject = "Re: " + subject
        body = templates.FOLLOWUP_BODY.format(**ctx)
    else:
        body = templates.BODY.format(**ctx)
    body = body.rstrip() + "\n" + templates.FOOTER.format(sender_name=SENDER_NAME, postal_address=POSTAL)
    return subject, body


def build_message(lead, followup=False, to=None):
    subject, body = render(lead, followup)
    msg = EmailMessage()
    msg["From"] = formataddr((SENDER_NAME, SENDER))
    msg["To"] = to or lead["email"]
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=SENDER.split("@")[-1] or None)
    if followup and lead.get("message_id"):
        msg["In-Reply-To"] = lead["message_id"]
        msg["References"] = lead["message_id"]
    msg.set_content(body)
    return msg


def smtp_connect():
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
    server.starttls()
    server.login(SENDER, APP_PASSWORD)
    return server


# --------------------------------------------------------------------------- Timing
def in_window(tz_name, now=None):
    now = now or utcnow()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    local = now.astimezone(tz)
    return local.weekday() in config.SEND_DAYS and config.SEND_WINDOW_START <= local.hour < config.SEND_WINDOW_END


def daily_cap(state, today):
    start = state.get("start_date")
    if not start:
        day_n = 1
    else:
        day_n = (dt.date.fromisoformat(today) - dt.date.fromisoformat(start)).days + 1
    for through_day, cap in config.WARMUP:
        if day_n <= through_day:
            return cap
    return config.FULL_DAILY_CAP


# --------------------------------------------------------------------------- Inbox
def reply_text(msg):
    """Plain text of a reply, without the quoted original (which contains 'no thanks')."""
    part = None
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition", "")):
                part = p
                break
    else:
        part = msg
    if part is None:
        return ""
    try:
        text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*On .+wrote:\s*$", line) or line.strip().startswith(("-----Original", "From:")):
            break
        if not line.lstrip().startswith(">"):
            lines.append(line)
    return "\n".join(lines)


def check_inbox(leads):
    contacted = [l for l in leads if l["status"] in ("sent", "followed_up")]
    if not contacted:
        return
    by_email = {l["email"].lower(): l for l in contacted}
    by_domain = {}
    for l in contacted:
        for d in (domain_of(l["email"]), domain_of(l["website"])):
            if d and d not in FREEMAIL:
                by_domain[d] = l

    since = (utcnow() - dt.timedelta(days=config.INBOX_LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(SENDER, APP_PASSWORD)
    imap.select("INBOX", readonly=True)
    _, data = imap.search(None, "SINCE", since)
    ids = data[0].split()

    replies, bounce_ids = [], []
    for i in range(0, len(ids), 300):
        chunk = b",".join(ids[i:i + 300])
        _, resp = imap.fetch(chunk, "(BODY.PEEK[HEADER.FIELDS (FROM DATE X-FAILED-RECIPIENTS)])")
        for item in resp:
            if not isinstance(item, tuple):
                continue
            num = item[0].split()[0]
            hdr = email.message_from_bytes(item[1])
            sender = parseaddr(hdr.get("From", ""))[1].lower()
            failed = hdr.get("X-Failed-Recipients", "")
            if failed or sender.startswith(("mailer-daemon", "postmaster")):
                hit = False
                for addr in re.split(r"[,\s]+", failed):
                    lead = by_email.get(addr.lower())
                    if lead:
                        mark(lead, "bounced", "bounce notice received")
                        hit = True
                if not hit:
                    bounce_ids.append(num)
                continue
            lead = by_email.get(sender) or by_domain.get(domain_of(sender))
            if not lead:
                continue
            try:
                received = parsedate_to_datetime(hdr.get("Date"))
            except (TypeError, ValueError):
                received = None
            sent_at = parse_iso(lead["sent_at"])
            if received and sent_at and received.tzinfo and received < sent_at:
                continue
            replies.append((num, lead))

    for num, lead in replies:
        if lead["status"] not in ("sent", "followed_up"):
            continue
        _, resp = imap.fetch(num, "(BODY.PEEK[])")
        msg = email.message_from_bytes(resp[0][1])
        if OPT_OUT_RE.search(reply_text(msg)):
            mark(lead, "opted_out", "asked not to be contacted")
        else:
            mark(lead, "replied", "replied - check your inbox")

    for num in bounce_ids:
        _, resp = imap.fetch(num, "(BODY.PEEK[])")
        raw = resp[0][1].decode("utf-8", "replace").lower()
        for addr, lead in by_email.items():
            if lead["status"] in ("sent", "followed_up") and addr in raw:
                mark(lead, "bounced", "bounce notice received")

    imap.logout()


def mark(lead, status, note):
    if lead["status"] != status:
        out(f"- {lead['business']} <{lead['email']}>: {status}")
    lead["status"] = status
    lead["note"] = note
    lead["updated_at"] = iso(utcnow())


# --------------------------------------------------------------------------- Modes
def require(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit("Missing secrets: " + ", ".join(missing))


def template_ready():
    if "[PASTE YOUR EMAIL BODY HERE]" in templates.BODY:
        sys.exit("Paste your email text into templates.py before sending.")


def preview(leads):
    ready = [l for l in leads if l["status"] == "ready"][:5]
    if not ready:
        out("No leads ready yet. Run the 'find' mode first.")
        return
    out(f"## Next {len(ready)} emails (nothing was sent)\n")
    for l in ready:
        subject, body = render(l)
        local = utcnow().astimezone(ZoneInfo(l["timezone"] or "America/New_York"))
        out(f"**To:** {l['email']} ({l['timezone']}, local time now {local:%a %H:%M})  ")
        out(f"**Subject:** {subject}\n")
        out("```\n" + body + "\n```\n")


def test_send(leads):
    require("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "SENDER_POSTAL_ADDRESS")
    template_ready()
    lead = next((l for l in leads if l["status"] == "ready"), None)
    if not lead:
        lead = {"business": "Example Interiors", "website": "https://example.com", "email": SENDER,
                "observation": "I ran your website through Google's mobile speed test and it scored 31 out of 100.",
                "message_id": ""}
    msg = build_message(lead, to=SENDER)
    msg.replace_header("Subject", "[TEST] " + msg["Subject"])
    server = smtp_connect()
    server.send_message(msg)
    server.quit()
    out(f"Test email sent to {SENDER} (written for {lead['business']}). Nothing else was sent.")


def run(leads, state):
    require("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "SENDER_POSTAL_ADDRESS")
    template_ready()

    check_inbox(leads)
    save_leads(leads)

    now = utcnow()
    today = now.date().isoformat()
    cap = daily_cap(state, today)
    sent_today = state["sent_log"].get(today, 0)
    budget = min(config.MAX_PER_RUN, cap - sent_today)
    out(f"Daily limit today: {cap}. Already sent today: {sent_today}.")
    if budget <= 0:
        out("Daily limit reached.")
        return

    due = now - dt.timedelta(days=config.FOLLOWUP_AFTER_DAYS)
    followups = [l for l in leads if l["status"] == "sent" and (parse_iso(l["sent_at"]) or now) <= due
                 and in_window(l["timezone"], now)]
    fresh = [l for l in leads if l["status"] == "ready" and in_window(l["timezone"], now)]
    queue = ([(l, True) for l in followups] + [(l, False) for l in fresh])[:budget]
    if not queue:
        out("Nobody is in their 9am-noon window right now.")
        return

    server = smtp_connect()
    for i, (lead, is_followup) in enumerate(queue):
        msg = build_message(lead, followup=is_followup)
        try:
            try:
                server.send_message(msg)
            except smtplib.SMTPServerDisconnected:
                server = smtp_connect()
                server.send_message(msg)
        except smtplib.SMTPRecipientsRefused:
            mark(lead, "bounced", "address rejected")
            save_leads(leads)
            continue
        except smtplib.SMTPException as e:
            out(f"Gmail refused to send ({e}). Stopping this run to protect your account.")
            break

        stamp = iso(utcnow())
        if is_followup:
            lead["status"], lead["followup_at"] = "followed_up", stamp
        else:
            lead["status"], lead["sent_at"], lead["message_id"] = "sent", stamp, msg["Message-ID"]
        lead["updated_at"] = stamp
        if not state.get("start_date"):
            state["start_date"] = today
        state["sent_log"][today] = state["sent_log"].get(today, 0) + 1
        save_leads(leads)
        save_state(state)
        out(f"- {'follow-up' if is_followup else 'sent'}: {lead['business']} <{lead['email']}>")

        if i < len(queue) - 1:
            time.sleep(random.uniform(*config.GAP_SECONDS))
    try:
        server.quit()
    except smtplib.SMTPException:
        pass

    cutoff = (now.date() - dt.timedelta(days=30)).isoformat()
    state["sent_log"] = {d: n for d, n in state["sent_log"].items() if d >= cutoff}
    save_state(state)


def status_counts(leads):
    counts = {}
    for l in leads:
        counts[l["status"]] = counts.get(l["status"], 0) + 1
    out("\n**Leads by status:** " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none yet"))


def main():
    leads = load_leads()
    state = load_state()
    if MODE == "preview":
        preview(leads)
    elif MODE == "test":
        test_send(leads)
    elif MODE == "run":
        run(leads, state)
    else:
        sys.exit(f"Unknown MODE {MODE!r}")
    status_counts(leads)


if __name__ == "__main__":
    main()
