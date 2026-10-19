"""Find businesses on OpenStreetMap, pull an email from each website, and flag
sites that need work. New leads are added to leads.csv.

OpenStreetMap needs no key or account. GOOGLE_API_KEY (PageSpeed Insights API,
no billing needed) is optional: without it the speed test runs keyless with a
lower limit, and if it fails the https and footer-year checks still work.
Run with --force to search even when enough leads are already waiting.
"""
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from timezonefinder import TimezoneFinder

import config
from store import domain_of, iso, load_leads, load_state, save_leads, save_state, utcnow

API_KEY = os.environ.get("GOOGLE_API_KEY", "")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
COPYRIGHT_RE = re.compile(
    r"(?:©|&copy;|\(c\)|copyright)\s*(?:\d{4}\s*[-–—]\s*)?((?:19|20)\d{2})", re.I
)
# Sites that are a profile page, not the business's own website.
NOT_A_REAL_SITE = (
    "facebook.com", "instagram.com", "houzz.com", "yelp.com", "linktr.ee", "linkedin.com",
    "google.com", "business.site", "g.page", "pinterest.com", "tiktok.com", "x.com",
    "twitter.com", "thumbtack.com", "angi.com", "homeadvisor.com", "nextdoor.com",
)
BAD_EMAIL_BITS = (
    "example.", "sentry", "wixpress", "yourdomain", "domain.com", "yourname", "email.com",
    "godaddy", "squarespace", "wordpress", "noreply", "no-reply", "@2x", "user@",
    "name@", "test@", "privacy@", "abuse@", "webmaster@",
)
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
CONTACT_WORDS = ("contact", "about", "connect", "inquir", "enquir", "get-in-touch", "work-with")


# --------------------------------------------------------------------------- OpenStreetMap
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
OSM_UA = {"User-Agent": "small-business-outreach/1.0 (one query per run)"}


def osm_query(state):
    """One query per state covering every niche in config.NICHES."""
    parts = []
    for niche in config.NICHES.values():
        for tag in niche["tags"]:
            k, v = tag.split("=", 1)
            parts.append(f'nwr["{k}"="{v}"](area.a);')
        parts.append(f'nwr["name"~"{niche["names"]}",i](area.a);')
    return (
        "[out:json][timeout:180];"
        f'area["ISO3166-2"="US-{state}"]["admin_level"="4"]->.a;'
        "(" + "".join(parts) + ");"
        "out center tags;"
    )


def osm_search(state):
    """All matching businesses in one US state, as a list of OSM elements."""
    q = osm_query(state)
    last = ""
    for attempt in range(2):
        for url in OVERPASS_SERVERS:
            try:
                r = requests.post(url, data={"data": q}, headers=OSM_UA, timeout=200)
                if r.status_code == 200:
                    return r.json().get("elements", [])
                last = f"{url} returned {r.status_code}"
            except (requests.RequestException, ValueError) as e:
                last = f"{url}: {e}"
            time.sleep(5)
        time.sleep(30)
    print(f"  OpenStreetMap is busy right now ({last}); will try {state} again next run.")
    return None


def niche_of(tags, name):
    """Which config.NICHES entry an OSM element belongs to, or None."""
    for key, niche in config.NICHES.items():
        if any(tags.get(t.split("=", 1)[0]) == t.split("=", 1)[1] for t in niche["tags"]):
            return key
        if re.search(niche["names"], name, re.I):
            return key
    return None


def osm_to_place(el):
    """Turns an OSM element into a simple dict, or None if it isn't usable."""
    tags = el.get("tags", {})
    name = (tags.get("name") or "").strip()
    if not name or any(k in tags for k in ("highway", "railway", "waterway")):
        return None
    niche = niche_of(tags, name)
    if not niche:
        return None
    low = name.lower() + " "
    if any(x in low for x in config.NICHES[niche]["exclude"]):
        return None
    if tags.get("shop") in ("car", "car_repair", "car_parts", "boat", "motorcycle"):
        return None
    if tags.get("disused") or tags.get("closed") or "disused:shop" in tags:
        return None
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
    website = website.split(";")[0].strip()
    if website and "://" not in website:
        website = "http://" + website
    address = ", ".join(x for x in (
        " ".join(x for x in (tags.get("addr:housenumber", ""), tags.get("addr:street", "")) if x),
        tags.get("addr:city", ""), tags.get("addr:state", ""),
    ) if x)
    osm_email = (tags.get("email") or tags.get("contact:email") or "").split(";")[0].strip()
    return {
        "id": f"osm:{el.get('type')}/{el.get('id')}",
        "name": name,
        "niche": niche,
        "website": website,
        "address": address,
        "lat": lat,
        "lon": lon,
        "osm_email": clean_email(osm_email) if osm_email else None,
    }


def pagespeed_score(url):
    params = {"url": url, "strategy": "mobile", "category": "performance"}
    if API_KEY:
        params["key"] = API_KEY
    try:
        r = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params,
            timeout=120,
        )
        if r.status_code != 200:
            return None
        s = r.json().get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score")
        return round(s * 100) if s is not None else None
    except (requests.RequestException, ValueError):
        return None


# --------------------------------------------------------------------------- Websites
def fetch(url):
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
    except requests.RequestException:
        return None, None
    if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "").lower():
        return None, None
    return r.url, r.text


def decode_cfemail(h):
    """Cloudflare hides emails as data-cfemail="..."; this reverses it."""
    try:
        key = int(h[:2], 16)
        return "".join(chr(int(h[i:i + 2], 16) ^ key) for i in range(2, len(h), 2))
    except ValueError:
        return ""


def clean_email(e):
    e = unquote(e).strip().strip(".,;:()[]<>'\"").lower()
    if not EMAIL_RE.fullmatch(e) or len(e) > 80:
        return None
    if e.endswith(IMG_EXT) or any(b in e for b in BAD_EMAIL_BITS):
        return None
    return e


def emails_in(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    raw = []
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            raw.append(a["href"][7:].split("?")[0])
    for el in soup.select("[data-cfemail]"):
        raw.append(decode_cfemail(el["data-cfemail"]))
    raw += EMAIL_RE.findall(soup.get_text(" "))
    raw += EMAIL_RE.findall(html_text)
    out = []
    for e in raw:
        c = clean_email(e)
        if c and c not in out:
            out.append(c)
    return out, soup


def contact_links(soup, base_url, limit=3):
    base = domain_of(base_url)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        blob = (href + " " + a.get_text(" ")).lower()
        if any(w in blob for w in CONTACT_WORDS):
            full = urljoin(base_url, href).split("#")[0]
            if domain_of(full) == base and full not in links:
                links.append(full)
        if len(links) >= limit:
            break
    return links


def pick_email(emails, site_domain):
    same = [e for e in emails if domain_of(e) == site_domain or domain_of(e).endswith("." + site_domain)]
    if same:
        return same[0]
    return emails[0] if emails else None


def copyright_year(soup):
    this_year = utcnow().year
    years = [int(y) for y in COPYRIGHT_RE.findall(soup.get_text(" ")) if int(y) <= this_year]
    return max(years) if years else None


def make_observation(score, https, year):
    """Returns (issue, sentence). Empty if the site looks fine."""
    if score is not None and score < config.PAGESPEED_BAD_SCORE:
        return "slow_mobile", (
            f"I ran your website through Google's mobile speed test and it scored {score} out of 100, "
            "which can mean visitors on phones leave before it finishes loading."
        )
    if not https:
        return "not_secure", (
            "I noticed your website doesn't load over a secure connection, so browsers like Chrome "
            'show visitors a "Not secure" warning.'
        )
    if year and utcnow().year - year >= config.OLD_COPYRIGHT_YEARS:
        return "outdated", (
            f"I noticed the footer on your website still says © {year}, which can make visitors "
            "wonder whether the business is still active."
        )
    return "", ""


def analyze(place):
    """Visit one business's website. Runs in a thread; returns field updates."""
    website = place["website"]
    final_url, html_text = fetch(website)
    if not html_text:
        return {"status": "no_email", "note": "website did not load"}
    emails, soup = emails_in(html_text)
    if not emails:
        for link in contact_links(soup, final_url):
            _, page = fetch(link)
            if page:
                found, _ = emails_in(page)
                emails += [e for e in found if e not in emails]
            if emails:
                break
    if place.get("osm_email") and place["osm_email"] not in emails:
        emails.insert(0, place["osm_email"])
    email = pick_email(emails, domain_of(final_url))
    if not email:
        return {"status": "no_email"}
    https = final_url.lower().startswith("https://")
    year = copyright_year(soup)
    score = pagespeed_score(final_url)
    issue, observation = make_observation(score, https, year)
    note = f"mobile score {score}" if score is not None else "mobile score unavailable"
    return {
        "email": email,
        "website": final_url,
        "issue": issue,
        "observation": observation,
        "status": "ready" if issue else "good_site",
        "note": note,
    }


# --------------------------------------------------------------------------- Main
def main():
    force = "--force" in sys.argv
    leads = load_leads()
    state = load_state()
    ready = sum(1 for l in leads if l["status"] == "ready")
    if ready >= config.LEAD_BUFFER and not force:
        print(f"{ready} leads already waiting; no search needed.")
        return

    seen_ids = {l["place_id"] for l in leads}
    seen_domains = {domain_of(l["website"]) for l in leads if l["website"]}
    seen_emails = {l["email"] for l in leads if l["email"]}
    tf = TimezoneFinder()
    states_done = 0

    while states_done < config.MAX_STATES_PER_RUN and (ready < config.LEAD_BUFFER or force):
        idx = state.get("state_index", 0)
        if idx >= len(config.STATES):
            print("Every state in config.STATES has been searched. "
                  "Add more search terms in config.py, or reset state_index in state.json to 0 "
                  "to pick up businesses added to OpenStreetMap since.")
            break
        us_state = config.STATES[idx]
        print(f"Searching OpenStreetMap: {', '.join(config.NICHES)} in {us_state}")
        elements = osm_search(us_state)
        if elements is None:
            break
        time.sleep(3)

        batch = []
        for el in elements:
            p = osm_to_place(el)
            if not p or p["id"] in seen_ids or p["lat"] is None:
                continue
            seen_ids.add(p["id"])
            lead = {k: "" for k in ("email", "issue", "observation", "sent_at", "message_id",
                                    "followup_at", "note")}
            lead.update({
                "place_id": p["id"],
                "business": p["name"],
                "niche": p["niche"],
                "website": p["website"],
                "address": p["address"],
                "lat": p["lat"],
                "lng": p["lon"],
                "timezone": tf.timezone_at(lat=p["lat"], lng=p["lon"]) or "America/New_York",
                "found_at": iso(utcnow()),
                "updated_at": iso(utcnow()),
                "osm_email": p["osm_email"],
            })
            site = p["website"]
            d = domain_of(site)
            if not site or any(d == s or d.endswith("." + s) for s in NOT_A_REAL_SITE):
                lead["status"] = "no_site"
                leads.append(lead)
                continue
            if d in seen_domains:
                continue
            seen_domains.add(d)
            batch.append(lead)

        print(f"  {len(elements)} map entries, {len(batch)} new websites to check")
        # Check websites in groups so progress is saved as it goes.
        for i in range(0, len(batch), 12):
            group = batch[i:i + 12]
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(analyze, group))
            for lead, res in zip(group, results):
                lead.update(res)
                lead.pop("osm_email", None)
                if lead.get("email"):
                    if lead["email"] in seen_emails:
                        lead["status"] = "duplicate"
                    seen_emails.add(lead["email"])
                if lead["status"] == "ready":
                    ready += 1
                leads.append(lead)
            save_leads(leads)

        print(f"  {us_state} done: {ready} leads ready in total")
        state["state_index"] = idx + 1
        save_state(state)
        states_done += 1

    save_leads(leads)
    print(f"Done. {ready} leads ready to email.")


if __name__ == "__main__":
    main()
