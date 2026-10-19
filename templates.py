"""Your email text. Placeholders in {curly braces} are filled in automatically:

  {business}     the business name from Google
  {observation}  one sentence about their website (slow on mobile, "Not secure", old footer year)
  {website}      their website address
  {sender_name}  your name (from the SENDER_NAME secret)

Keep it plain text: no images, no attachments, at most one link.
"""

SUBJECT = "Quick question about {business}'s website"

BODY = """Hi {business} team,

{observation}

[PASTE YOUR EMAIL BODY HERE]

Best,
{sender_name}
"""

FOLLOWUP_BODY = """Hi again,

Just bringing this back to the top of your inbox in case it got buried. Would it be useful if I put together a quick idea of what a refreshed site for {business} could look like? No cost to see it.

{sender_name}
"""

# Added to every email. The postal address and the opt-out line are required
# for commercial email under US law (CAN-SPAM).
FOOTER = """
--
{sender_name} | {postal_address}
Not interested? Just reply "no thanks" and I won't contact you again.
"""
