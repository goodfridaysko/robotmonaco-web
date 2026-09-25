# Content brief for robotmonaco.com (English source)

The site sells **humanoid robot hire with an operator** for events, brand activations and marketing in
**Monaco and the French Riviera**, plus **custom robot software** and **AI assistant** builds.
Target reader: an event producer, a marketing director or a brand manager working in Monaco.

Read `content/en/ui.json` and `content/en/home.json` first. They set the voice and the quality bar.

## Voice
- British English. Confident, concrete, premium. Short sentences. No exclamation marks, no hype words
  ("revolutionary", "cutting-edge", "game-changing"), no marketing filler.
- **Never use an em dash or an en dash as punctuation.** Use a comma or a full stop.
- Sell the effect on the room, not the specification sheet. The promise is attention, photographs and a
  moment guests talk about, delivered without risk because an operator runs it.
- Be honest about limits. That honesty is part of the pitch.

## Hard facts (never invent others)
- Fleet: **MONTARI** (Unitree G1, event humanoid), **NOVA** (Unitree G1 EDU, developer humanoid with full
  SDK), **ORYX** (Unitree Go2, four-legged robot dog).
- Prices, the only valid figures: event humanoid and the dog **from €2,000 per day**, NOVA **from €3,000 per
  day**, both **with an operator, multi-day rate, excluding VAT**. Single days, custom scripts, travel and
  staging are quoted separately. Never print any other number as a price.
- An operator is **always** included. The robot never performs unattended.
- Battery: about **two hours** of active show, swapped on site by the operator.
- Needs a flat, dry, firm surface, roughly **3 by 3 metres** to work in. No rain, no loose gravel, no stairs
  as a routine.
- It does **not** lift heavy loads, does not replace staff, does not work unsupervised.
- Languages: the robot can speak **English and French**.
- Branding: the wordmark on the chest is a printed decal that we replace with the client's logo.
- Area: Monaco, Monte-Carlo, Nice, Cannes, Antibes, Saint-Tropez, Menton, Villefranche-sur-Mer, Èze.
- Contact: info@robotmonaco.com, +377 37 73 06 01. Reply within 24 hours.

## SEO
- Put the main keyword in `title`, `h1`, the first paragraph of `intro`, one `items` heading and one FAQ
  question. Natural placement only, never stuffed.
- `title` **≤ 60 characters**, and the build appends " | ROBOTMONACO" only when it still fits, so write the
  title so it works either way. `desc` (meta description) **120 to 155 characters**, and it should name
  Monaco or the Riviera.
- Write FAQ questions the way a client would type them into Google ("how much does it cost to hire a robot
  for an event in Monaco", "is a humanoid robot safe around guests").

## Allowed values
- `icon`, anywhere: bot, box, camera, clapperboard, code-2, cog, cpu, database, eye, factory, flag, globe,
  graduation-cap, headset, megaphone, mic, monitor, party-popper, plug, radar, scan-barcode, scan-face,
  shield-check, sparkles, store, truck, workflow, wrench.
- `photo` / `photo2`: hero, software, ai-assistant, montari-hero, nova-hero, oryx-hero, montari-tile,
  nova-tile, oryx-tile, brand-activations, product-launches, corporate-events, trade-shows, yacht-shows,
  grand-prix-hospitality, luxury-retail, galas-and-awards, private-parties, conferences.
  **Each use case must use the photo named after its own slug.**
- `preset`, when present, must be one of the `contact.types` values in `ui.json`.

## Files and their exact shape

### content/en/robots.json
```
{
  "_hub": { "crumb", "eyebrow", "h1", "lead", "title", "desc", "faq": [{q,a} x5] },
  "montari": { ...robot... }, "nova": { ...robot... }, "oryx": { ...robot... }
}
```
robot = `name` (MONTARI / NOVA / ORYX), `tagline` (one line, used on the home tiles), `teaser` (one line for
the directory tile, ≤ 110 chars), `alt` (image alt text), `title`, `desc`, `h1`, `lead`,
`specs`: 4 pairs `[label, value]` (height, weight, battery, languages, degrees of freedom, speed: pick the 4
that matter to an event client, values short like "1.32 m", "about 2 h"), `does`: {h2, items: 6 x {icon,h,p}},
`fit`: {h2, lead, list: 6 items}, `faq`: 5 x {q,a}, `preset`.
MONTARI is the crowd-working showpiece. NOVA is the same body with the full SDK, for clients who want custom
behaviour, research or a robot they can programme. ORYX is the four-legged one: entrances, photographs,
walking a red carpet, carrying a small branded load.

### content/en/use-cases.json
```
{ "_hub": { "crumb","eyebrow","h1","lead","title","desc","faq": [{q,a} x5] },
  "<slug>": { ...use case... } }
```
Slugs, in this order: brand-activations, product-launches, corporate-events, trade-shows, yacht-shows,
grand-prix-hospitality, luxury-retail, galas-and-awards, private-parties, conferences.
use case = `label` (2 to 4 words), `teaser` (≤ 110 chars), `eyebrow`, `h1` (ends with a full stop), `lead`,
`title`, `desc`, `photo` (= its own slug), `photo2` (any allowed photo), `alt`,
`intro`: {h2, p: 3 paragraphs, 180 to 260 words in total},
`ideas`: {h2, items: 6 x {icon,h,p}} — concrete things the robot does at this kind of event,
`included`: {h2, lead, list: 6 to 8 bullets} — what the client gets on the day,
`faq`: 5 x {q,a}, `related`: exactly 3 other slugs from the list, `preset`.
Write each page for its real Monaco context: yacht-shows means the Monaco Yacht Show and superyacht clients,
grand-prix-hospitality means race week suites and terraces above the circuit, luxury-retail means the Golden
Square boutiques, galas means charity galas and award dinners.

### content/en/services.json
```
{ "robot-software-development": {...}, "ai-assistant-upgrade": {...} }
```
service = `label`, `eyebrow`, `h1`, `lead`, `title`, `desc`, `photo` (software / ai-assistant), `photo2`,
`alt`, `intro`: {h2, p: 3 paragraphs}, `features`: {h2, items: 6 x {icon,h,p}},
`scope`: {h2, lead, list: 6 to 8}, `process`: {h2, steps: 4 x {h,p}}, `faq`: 5 x {q,a}, `preset`.
Software development: custom behaviour, motion sequences, voice and speech, remote control, integrations,
show control, ROS 2 and the Unitree SDK, Python and C++. AI assistant upgrade: the robot listens, understands
and answers visitors, knows your product catalogue or venue, speaks English and French, hands over to a human
when it does not know. Both are quoted per project, never priced on the page.

### content/en/pricing.json
`crumb`, `eyebrow`, `h1`, `lead`, `title`, `desc`,
`cards`: 3 x {k ("01".."03"), h, amount ("€2,000" / "€3,000" / "On request"), unit ("per day with an
operator" / "per project"), p, list: 4 to 6 bullets} — event hire, developer hire, software and AI projects,
`includes`: {h2, list: 6 to 8 bullets of what every booking contains},
`faq`: 6 x {q,a} about cost, what moves the price, deposits, cancellation, travel, VAT.

### content/en/faq.json
`crumb`, `eyebrow`, `h1`, `lead`, `title`, `desc`,
`groups`: 4 x {h2, items: 5 to 6 x {q,a}}. Group them as: Booking and price, On the day, Safety and limits,
Branding and software. Do not repeat the same answer twice across groups.

### content/en/contactPage.json
`crumb`, `eyebrow`, `h1`, `lead`, `title`, `desc`, `formH2`, `formP`, `faq`: 4 x {q,a}.

### content/en/privacy.json
`crumb`, `eyebrow`, `h1`, `title`, `desc`, `sections`: 6 to 8 x {h2, p: 1 to 3 paragraphs}.
A plain, honest GDPR notice for an enquiry form: what is collected, why, the legal basis, how long it is
kept, who sees it, the visitor's rights, cookies (the site sets none beyond what it needs), and how to
contact us. Do not invent a company registration number or a postal address beyond "Monaco".

## Output rules
UTF-8 JSON, 2-space indent, trailing newline, no comments, no trailing commas. Validate with
`python3 -c "import json;json.load(open('<file>'))"`. Do not touch any other file. Do not commit.
