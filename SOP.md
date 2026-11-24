# BlueCo client reporting — SOP

How the weekly inventory report and the mid-month / end-of-month client reports run, and
how anyone on the team can run them.

## What runs, and when

| Report | When | Goes to | Built by |
|---|---|---|---|
| Weekly inventory | Monday, ~07:30 UK | Each client's internal Slack channel + Weekly Inventory Report dashboard | `skills/blueco-weekly-inventory` |
| Mid-month report | 17th, ~08:00 UK (covers 1st–15th) | Client's internal Slack channel: team summary, dashboard, draft client email | `skills/blueco-report` |
| End-of-month report | 3rd, ~08:00 UK (covers last month) | Same as mid-month | `skills/blueco-report` |

Nothing posts to a client-shared Slack channel and nothing is emailed to a client
automatically. The account lead reviews and sends.

## One-time setup (per person who runs reports)

1. In Claude, connect: **DataDoe**, **Slack**, **GitHub** (with access to
   `blueco-agency/blueco-reporting`).
2. In DataDoe, check your role can read all client accounts. Scheduled runs should use a
   DataDoe **service account** (read-only, client accounts only) rather than a personal login.
3. Open a Claude chat in the BlueCo project and say: "Load the BlueCo reporting repo."

## Running a report on demand

In a Claude chat with the connectors above:

- "Run the weekly inventory report" — all clients, or name one.
- "Run the mid-month report for Vital Drinks."
- "Run the end-of-month report for all clients."

Claude reads this repo, pulls from DataDoe, and posts to the internal channels.

## Reviewing and sending a monthly report

1. Open the dashboard link in the client's internal channel and check the scorecard against
   what you know of the account (about 10 minutes).
2. Fix anything wrong by replying in the thread, e.g. "the March spike was clearance pricing,
   update page 2", or by adding a note in `context/<client>.md` and re-running.
3. Download the client PDF from the dashboard, edit the draft email if needed, attach the
   PDF, and send from your own email.

## Before each monthly run

Add anything the data can't explain to `context/<client>.md`: promos, suspensions, supplier
stock-outs, clearance pricing. One line each, with dates.

## Adding a client

1. Copy any file in `clients/` to `clients/<slug>.yaml` and fill in: DataDoe
   `seller_or_vendor_id` (ask Claude to list DataDoe accounts), marketplace, currency, the
   internal Slack channel ID, lead time and notes.
2. Add the client's DataDoe account name to `CLIENT_NAMES` in `scripts/inventory_flags.py`.
3. Run "Run the weekly inventory report for <client>" once and check the output.
4. Set `active: false` to pause a client without deleting it.

## When something fails

- **A client has no data:** the run posts a "no data" notice in that client's channel. Check
  the DataDoe connection for that account and open a DataDoe support ticket if needed.
- **The run errors:** it posts the error to `#blueco-ai`. Re-run on demand once fixed.
- **Numbers look wrong:** compare with Seller Central for the same dates. Snapshots can lag a
  day; the post says which date it used.

## Changing the rules

- Flag thresholds and inventory logic: `scripts/inventory_flags.py`.
- Report page order and client-facing conventions: `skills/blueco-report/SKILL.md`.
- Change them by pull request so every run, by anyone, uses the same version.

## Known gaps (Nov 2026)

- **Roarsome UK:** DataDoe returns no FBA inventory rows; support ticket needed.
- **Profit (page 3):** needs product cost for every selling SKU in DataDoe.
- **Search share (page 5):** needs Search Query Performance ASINs set up per client.
- **Ad change log (page 4):** the PPC team needs a shared log (Sheet or Notion) for changes.
- **Lead times and accent colours:** TODOs in `clients/*.yaml`.
