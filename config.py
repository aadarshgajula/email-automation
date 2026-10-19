"""Settings you can tweak. No secrets go in this file."""

# --- Who to find (OpenStreetMap, free, no key) -----------------------------
# OpenStreetMap tags that mean "interior designer". Each is "key=value".
OSM_TAGS = ["office=interior_design", "shop=interior_decoration", "craft=interior_decorator"]
# Also match businesses whose name contains these words (case-insensitive).
OSM_NAME_PATTERN = "interior design|interiors|interior decorat"
# Skip names containing these (car/boat upholsterers etc.).
NAME_EXCLUDE = ["auto", "car ", "cars", "truck", "boat", "marine", "rv ", "aircraft", "jet"]

# US states searched in order (biggest markets first), until the list runs out.
STATES = [
    "CA", "NY", "FL", "TX", "IL", "GA", "NC", "NJ", "MA", "PA", "AZ", "CO", "WA",
    "VA", "TN", "OH", "MI", "MD", "CT", "SC", "MN", "OR", "UT", "NV", "MO", "IN",
    "WI", "LA", "AL", "KY", "OK", "DC", "HI", "ID", "NM", "KS", "IA", "AR", "MS",
    "NE", "NH", "RI", "DE", "ME", "MT", "VT", "WV", "SD", "ND", "WY", "AK",
]
MAX_STATES_PER_RUN = 3      # keeps each run short
LEAD_BUFFER = 40            # stop searching once this many leads are ready to email

# --- Which websites count as "needs a new one" -----------------------------
PAGESPEED_BAD_SCORE = 50    # mobile score below this is flagged
OLD_COPYRIGHT_YEARS = 3     # footer year this many years old or more is flagged

# --- When and how much to send ---------------------------------------------
SEND_WINDOW_START = 9       # recipient's local time, 24h clock
SEND_WINDOW_END = 12        # sends happen from 9:00 until 11:59
SEND_DAYS = {0, 1, 2, 3, 4} # Monday-Friday in the recipient's time zone

# Warm-up: (through day N, max emails that day). Counts start the first day it sends.
WARMUP = [(7, 10), (14, 25)]
FULL_DAILY_CAP = 50         # includes follow-ups

MAX_PER_RUN = 12            # the scheduler runs once an hour
GAP_SECONDS = (20, 60)      # random pause between emails within a run

FOLLOWUP_AFTER_DAYS = 4     # one follow-up, then stop
INBOX_LOOKBACK_DAYS = 21    # how far back to check for replies and bounces
