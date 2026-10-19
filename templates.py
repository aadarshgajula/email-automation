"""Your email text. Placeholders in {curly braces} are filled in automatically:

  {business}     the business name from OpenStreetMap
  {observation}  one sentence about their website (slow on mobile, "Not secure", old footer year)
  {website}      their website address
  {sender_name}  your name (from the SENDER_NAME secret)

Keep it plain text: no images, no attachments, at most one link.
"""

SUBJECT = "Quick question about {business}'s website"

# One email per kind of business (the keys match NICHES in config.py).
# The plumbing email links the example homepage; it's a generic example (a
# made-up company), so never word it as if it was made for them.
BODY = {
    "plumbing": """Hi {business} team,

{observation}

I'm a web designer and I build fast, modern websites for plumbing companies. Here's an example homepage I designed for a plumber, so you can see the style:

https://plumbing-mockup-alpha.vercel.app/

I could build something like this for {business}: $350 one-off, live within a week, and it works properly on phones (where most "I need a plumber now" searches happen).

Would that be worth a quick chat?

Best,
{sender_name}
""",
    "interior_design": """Hi {business} team,

{observation}

I'm a web designer and I build clean, modern websites for interior designers, where the portfolio does the selling. I could build a new one for {business}: $350 one-off, live within a week, and it looks great on phones.

If it's useful, I can put together a quick mockup of what a refreshed homepage could look like, free.

Would that be worth a quick chat?

Best,
{sender_name}
""",
}

FOLLOWUP_BODY = {
    "plumbing": """Hi again,

Just bringing this back to the top of your inbox in case it got buried. If you liked the example homepage, I'm happy to put together a version with {business}'s name and services so you can see exactly how it would look. No cost to see it.

{sender_name}
""",
    "interior_design": """Hi again,

Just bringing this back to the top of your inbox in case it got buried. Would it be useful if I put together a quick idea of what a refreshed site for {business} could look like? No cost to see it.

{sender_name}
""",
}

# Added to every email. The postal address and the opt-out line are required
# for commercial email under US law (CAN-SPAM).
FOOTER = """
--
{sender_name} | {postal_address}
Not interested? Just reply "no thanks" and I won't contact you again.
"""
