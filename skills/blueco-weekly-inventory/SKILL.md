---
name: blueco-weekly-inventory
description: Run BlueCo's Monday FBA inventory report for every active client - pull the latest FBA Inventory Health snapshot from DataDoe, flag SKUs with the shared rules, refresh the Weekly Inventory Report dashboard, and post a short summary to each client's internal Slack channel. Use for "weekly inventory report", "Monday stock report", "inventory flags", or when the Monday scheduled task fires.
---

# BlueCo weekly inventory report

Runs every Monday at about 10:40 UK time, and on demand. Output goes to **internal** Slack
channels only. Nothing in this skill posts to a channel shared with a client.

Why 10:40: DataDoe's FBA Inventory Health snapshot refreshes during the day (around 10:00,
13:00 and 16:00). Before the first refresh, today's snapshot doesn't exist and an earlier run
reports yesterday's stock. The script always uses the newest snapshot that exists and the post
names its date.

Method follows DataDoe's **FBA Stock & Restock Planner** skill (Plugins): one snapshot date
only, never summed across dates; `inbound_quantity` already includes working, shipped and
received (never add those on top); Amazon's ship-in recommendation is read per main SKU, and
Grade & Resell SKUs (`amzn.gr.…`) are left out because they repeat it. For a restock
workbook with warehouse stock, use that skill directly.

## What you need

- DataDoe connector (read access to the client accounts)
- Slack connector
- This repo: `clients/*.yaml` and `scripts/inventory_flags.py`
- The dashboard: **Weekly Inventory Report** artifact (URL in `config/dashboards.yaml`)

## Steps

1. **Load clients.** Read every `clients/*.yaml` with `active: true`. Each gives the DataDoe
   `seller_or_vendor_id`, currency and `slack.internal_channel`.

2. **Pull the snapshot.** One DataDoe `exports_create` call for all clients (max 5 accounts
   per call; batch if more):
   - `sourceId`: `44fc5ba0ce` (FBA Inventory Health)
   - `from`: today minus 3 days, `to`: today (the script keeps each client's latest date)
   - `outputType`: CSV, `limit`: 5000
   - `columns`: every column in `REQUIRED` in `scripts/inventory_flags.py`, plus
     `your_price` and `afn_inbound_receiving_quantity`
   - Download with `exports_raw_url_get` and save to a working folder.

3. **Check coverage before anything else.** For each active client, confirm the export has
   rows. A client with none gets the "no data" post in step 6, not a report. Known case:
   Roarsome UK (see `clients/roarsome.yaml`).

4. **Flag.** Run `python3 scripts/inventory_flags.py <export.csv> <out_dir>`. Never re-implement
   the rules in a prompt; the script is the source of truth and the dashboard explains them.
   If it exits with an error, stop and post the error to `#blueco-ai` instead of guessing.

5. **Refresh the dashboard.** Upload `inventory_<date>.csv` to the Weekly Inventory Report
   artifact as an asset, then update its `datasets/inventory` document: the new file `url`
   and `name`, `description` with the new snapshot date, and `updated: {at, by}`. Change
   nothing else on the page.

6. **Post to Slack.** One message per client in its `internal_channel`, built from
   `summary_<date>.json`. Keep it short enough to read on a phone:

   ```
   *<Client> stock check — snapshot <d Mon>*
   :red_circle: <n> need action · :large_yellow_circle: <n> on watch · <available> units available, <inbound> inbound
   • <flag>: <short product name> (<SKU>) — <available> left, <days> days cover, Amazon suggests <qty> by <date>
   (up to 5 bullets, action items first, then the biggest watch items)
   Full report: <dashboard link>
   ```

   - Use the product's short name (text before the first comma or `|`), or the SKU if Amazon
     has no name.
   - Read the client's `notes` first. A known situation (e.g. a stranded SKU under appeal) is
     reported as "still stranded — appeal pending", not as a new problem.
   - "No data" post: `*<Client> stock check* — DataDoe returned no inventory rows this week, so
     no report. Check stock in Seller Central.`
   - If nothing is flagged: `*<Client> stock check* — nothing flagged this week.` plus the totals line.

7. **Report back.** In the run's final message, list each client with its action/watch counts,
   which channels were posted to, and anything that failed.

## Rules

- Internal channels only. Never post to a Slack Connect (client-shared) channel.
- Never edit the flag thresholds from a run. Changes go in `scripts/inventory_flags.py` by PR.
- A snapshot older than 3 days means DataDoe hasn't refreshed. Say so in the post rather than
  presenting old numbers as this week's.
