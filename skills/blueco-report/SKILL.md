---
name: blueco-report
description: Build BlueCo's mid-month and end-of-month Amazon client report - one interactive dashboard per client in a fixed nine-page order, a client PDF, a team summary posted to the client's internal Slack channel, and a draft client email for review. Use for "mid-month report", "end of month report", "monthly client report", "BlueCo report", or when the 17th / 3rd scheduled task fires.
---

# BlueCo client report (mid-month and end of month)

Same structure for both runs. Every client report reads in the same order, so a reviewer
can check it in minutes.

| Run | Fires | Period | Compared with |
|---|---|---|---|
| Mid-month | 17th, 08:00 UK | 1st–15th of this month | Same days last month; trailing 3-month average for the same days |
| End of month | 3rd, 08:00 UK | Whole previous month | Previous month; same month last year if available; trailing 3 months |

The two-day gap lets Amazon's sales and ad attribution settle. Flag the last 3 days of any
period as provisional if they changed between pulls.

## What you need

- DataDoe connector, plus these DataDoe skills (Plugins): Keyword Rank SQP Tracker (page 5),
  Buy Box Loss Root Cause (page 8), Daily Account Health Check (page 7)
- Slack connector
- This repo: `clients/*.yaml`, `scripts/inventory_flags.py`
- `context/<slug>.md` for the client, if present: notes from the team for this period
  (promos, suspensions, stock issues, clearance pricing) that the data can't explain

## Data rules (from DataDoe's Daily Performance Health Check skill)

- **Exports:** every `exports_create` needs `limit` and `outputType`. Aggregation aliases must
  differ from column names (sum of `ad_spend` → `total_ad_spend`). Text columns go in `groupBy`,
  not aggregations. Load every page of `exports_source_get`. Use CSV and `exports_raw_url_get`
  for anything processed in code; JSON caps at 1,000 rows, CSV at 5,000 (page with `skip`).
- **Sales and units for a closed period:** `Profit by SKU & Date` (`amazon_profit_by_sku_and_date`).
  Amazon's fees settle days to weeks after the sale, so on the 3rd and the 17th the last days of
  the period are incomplete for fees: mark net profit and margin **provisional** for those days.
- **Tax:** UK prices include VAT, so net sales = `item_price_value` − `item_tax_value`. US prices
  are already net of tax: don't subtract it there.
- **Off-Amazon lines:** drop order lines whose `sales_channel` isn't blank and isn't an Amazon
  marketplace domain (amazon.co.uk, amazon.com, …).
- **Ratios from sums:** ACoS = ad spend ÷ ad sales, TACoS = ad spend ÷ net sales, Total ROAS =
  net sales ÷ ad spend, all from period totals, never averaged across days. One currency per
  client; never add GBP and USD.
- **Ads:** `amazon_ads_performance_by_campaign_by_date`; Sponsored Brands rows arrive last, so
  check every ad type has rows for the period's final day before trusting spend.
- **Buy Box:** `avg_buybox_percentage` lags up to ~3 days. A 0 on a day that hasn't loaded is not
  a lost Buy Box.
- **COGS:** if selling SKUs lack product cost (`cogs_missing_list`), state the share of sales
  without COGS and treat profit as overstated.

DataDoe skills to reuse for single pages (load from Plugins, follow their method):
Keyword Rank SQP Tracker (page 5), Daily Account Health Check (page 7 verdict),
Buy Box Loss Root Cause (page 8), FBA Stock & Restock Planner (page 6 method).

## Page order

Each page opens with one sentence stating its finding. Every number shows its date range and
source table. The layout must read on a phone.

1. **Scorecard.** Sales, units, ad spend, ACoS, TACoS, Total ROAS, net profit, margin, days of
   cover and the account health verdict, each against the comparison periods above.
2. **What changed and why.** The five biggest movers by sales change, each split into traffic,
   conversion, price or Buy Box, with a one-line cause.
3. **Profit.** Waterfall from sales through Amazon fees, ads, returns and product cost to net
   profit, then a SKU table with a visible "unallocated" line so SKU totals reconcile to the
   account. If any selling SKU is missing product cost (DataDoe `cogs_missing_list`), say so on
   the page and in the team summary; do not show net profit as final.
4. **Advertising.** Spend and sales by ad type, the ten worst campaigns, wasted spend in
   currency, and the change log of what the team altered this period (from the ad change log).
5. **Search share.** Money keywords with share of impressions, clicks and purchases, and the
   terms rising, slipping or emerging (Keyword Rank SQP Tracker method). Needs SQP ASINs set up.
6. **Stock.** Days of cover and reorder date per SKU, stranded stock and storage fees. Anything
   inside the client's `lead_time_days` is red. Use `scripts/inventory_flags.py` for flags.
7. **Account health and listings.** Red/amber/green verdict, suppressed listings, top review
   and return themes.
8. **Competitors.** Buy Box share and price gap against the featured offer. Drop the category
   benchmark line unless DataDoe provides it.
9. **Next two weeks.** Three recommended actions with expected effect, owner and anything
   waiting on client approval.

## Two versions from one run

- **Internal version** (team): everything above.
- **Client version** (PDF + email): same page order, with these BlueCo conventions:
  - Total ROAS (total revenue ÷ ad spend), never Ad ROAS.
  - Takeaways framed positively and forward-looking.
  - Page 4 shows spend and sales by ad type only: no worst-campaigns list, no wasted spend,
    no change log.
  - Page 7 shows the verdict and themes; internal operational flags are removed.
  - Negative deltas after a sales event (e.g. post-Prime Day) shown in neutral blue.

## Delivery

1. Publish the internal dashboard for the client (one artifact per client per period).
2. Post to the client's `slack.internal_channel`:
   - 4–6 line team summary: headline result, the biggest mover, top risk, data gaps.
   - The dashboard link.
   - A **draft client email** (subject + body, in BlueCo's voice) for the account lead to
     review, attach the client PDF to, and send. Never send it to the client.
3. Final message: what was posted where, and anything that blocked a page.

## Rules

- Internal Slack channels only. Never post to a client-shared channel and never email a client.
- A page that can't be built from data says why on the page ("Search share needs SQP set up
  for these ASINs"), rather than being filled from memory or estimates.
- Never invent a cause. If the data doesn't explain a mover and `context/` doesn't either,
  say "cause not clear from the data" and put it on the team's list.
