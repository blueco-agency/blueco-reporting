#!/usr/bin/env python3
"""BlueCo weekly inventory: clean a DataDoe FBA Inventory Health export and flag SKUs.

Usage:
    python3 scripts/inventory_flags.py <export.csv> <out_dir>

Input: a CSV export of DataDoe's "FBA Inventory Health" source (sourceId 44fc5ba0ce)
for one or more clients, covering the last few days (the script keeps each client's
latest snapshot date). Required columns are listed in REQUIRED below.

Output in <out_dir>:
    inventory_<date>.csv   one row per SKU with BlueCo flags (the file the dashboard reads)
    summary_<date>.json    per-client totals and flagged SKUs (what the Slack posts are built from)

The flag rules here are the single source of truth. Change them here, not in a prompt.
"""
import json
import sys
from pathlib import Path

import pandas as pd

REQUIRED = [
    "seller_or_vendor_name", "date", "sku", "child_asin", "product_name", "currency",
    "available", "inbound_quantity", "total_reserved_quantity", "unfulfillable_quantity",
    "units_shipped_t7", "units_shipped_t30",
    "total_days_of_supply_including_units_from_open_shipments",
    "recommended_action", "fba_inventory_level_health_status",
    "recommended_ship_in_quantity", "recommended_ship_in_date",
    "estimated_excess_quantity", "inv_age_181_to_270_days", "inv_age_271_to_365_days",
    "inv_age_366_to_455_days", "inv_age_456_plus_days", "estimated_storage_cost_next_month",
]

# DataDoe account display name -> client name used in reports and clients/*.yaml
CLIENT_NAMES = {
    "AQUA GLOW DRINK UK": "AquaGlow UK",
    "Pain Safari US": "Pain Safari US",
    "VITAL Drinks UK": "Vital Drinks UK",
    "VNSH US": "VNSH US",
    "Roarsome UK": "Roarsome UK",
}

# Thresholds
MIN_MONTHLY_UNITS = 5        # below this a SKU is too slow to judge cover
ACTION_COVER_DAYS = 30       # under this = action
WATCH_COVER_DAYS = 60        # under this = watch
AGED_MIN_UNITS = 50          # aged stock needs at least this many 181+ day units
AGED_MIN_COVER_DAYS = 180    # ...and this much cover


def flag(row, asin_available):
    t30 = row.units_30d
    if row.available == 0 and asin_available > 0:
        return "Empty duplicate SKU", "grey"
    if row.available == 0 and t30 > 0:
        return "Out of stock", "red"
    if row.amazon_action == "GoToStranded":
        return "Stranded", "red"
    if t30 >= MIN_MONTHLY_UNITS and row.days_cover < ACTION_COVER_DAYS:
        return "Under 30 days cover", "red"
    if (t30 >= MIN_MONTHLY_UNITS and row.days_cover < WATCH_COVER_DAYS) or (
        row.amazon_status == "Low stock" and row.days_cover < WATCH_COVER_DAYS
    ):
        return "Restock soon", "amber"
    if row.excess_units > 0:
        return "Excess stock", "amber"
    if row.aged_181_plus >= AGED_MIN_UNITS and row.days_cover >= AGED_MIN_COVER_DAYS:
        return "Aged stock", "amber"
    return "OK", "green"


def main(src, out_dir):
    raw = pd.read_csv(src)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        sys.exit(f"Export is missing columns: {missing}")

    # Latest snapshot per client (snapshots are not additive across dates)
    raw = raw[raw.date == raw.groupby("seller_or_vendor_name").date.transform("max")].copy()

    # Alias SKUs: no sales figures and the same ASIN + stock as another row -> same units listed twice
    alias = raw.units_shipped_t30.isna() & raw.duplicated(
        ["seller_or_vendor_name", "child_asin", "available"], keep=False
    )
    raw = raw[~alias]

    # Grade & Resell SKUs (amzn.gr.…) repeat the main SKU's recommendations; leave them out
    raw = raw[~raw.sku.astype(str).str.startswith("amzn.gr.")]

    aged = raw[["inv_age_181_to_270_days", "inv_age_271_to_365_days",
                "inv_age_366_to_455_days", "inv_age_456_plus_days"]].fillna(0).sum(axis=1)
    df = pd.DataFrame({
        "client": raw.seller_or_vendor_name.map(CLIENT_NAMES).fillna(raw.seller_or_vendor_name),
        "currency": raw.currency,
        "sku": raw.sku,
        "asin": raw.child_asin,
        "product": raw.product_name.fillna("(name missing in Amazon report)"),
        "available": raw.available.fillna(0).astype(int),
        "inbound": raw.inbound_quantity.fillna(0).astype(int),
        "reserved": raw.total_reserved_quantity.fillna(0).astype(int),
        "unfulfillable": raw.unfulfillable_quantity.fillna(0).astype(int),
        "units_7d": raw.units_shipped_t7.fillna(0).astype(int),
        "units_30d": raw.units_shipped_t30.fillna(0).astype(int),
        "days_cover": raw.total_days_of_supply_including_units_from_open_shipments.fillna(0).round(0).astype(int),
        "amazon_status": raw.fba_inventory_level_health_status.fillna(""),
        "amazon_action": raw.recommended_action.fillna(""),
        "ship_in_qty": raw.recommended_ship_in_quantity.fillna(0).astype(int),
        "ship_in_by": raw.recommended_ship_in_date.fillna(""),
        "excess_units": raw.estimated_excess_quantity.fillna(0).astype(int),
        "aged_181_plus": aged.astype(int),
        "storage_next_month": raw.estimated_storage_cost_next_month.fillna(0).round(2),
        "snapshot_date": raw.date,
    })
    df.loc[df.ship_in_qty == 0, "ship_in_by"] = ""

    # Drop SKUs with no stock, nothing inbound and no recent sales
    df = df[(df.available > 0) | (df.inbound > 0) | (df.units_30d > 0) | (df.reserved > 0)].copy()

    asin_avail = df.groupby(["client", "asin"]).available.transform("sum")
    flags = [flag(r, a) for r, a in zip(df.itertuples(), asin_avail)]
    df["flag"] = [f for f, _ in flags]
    df["level"] = [lvl for _, lvl in flags]

    if df.duplicated(["client", "sku"]).any():
        sys.exit("Duplicate client+SKU rows after cleaning; check the export.")

    df = df.sort_values(["client", "units_30d"], ascending=[True, False])
    date = str(df.snapshot_date.max())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"inventory_{date}.csv", index=False)

    summary = []
    for client, g in df.groupby("client"):
        flagged = g[g.level.isin(["red", "amber"])].copy()
        flagged["order"] = flagged.level.map({"red": 0, "amber": 1})
        flagged = flagged.sort_values(["order", "units_30d"], ascending=[True, False]).drop(columns="order")
        summary.append({
            "client": client,
            "currency": g.currency.iloc[0],
            "snapshot_date": str(g.snapshot_date.iloc[0]),
            "skus": int(len(g)),
            "available": int(g.available.sum()),
            "inbound": int(g.inbound.sum()),
            "units_30d": int(g.units_30d.sum()),
            "action": int((g.level == "red").sum()),
            "watch": int((g.level == "amber").sum()),
            "storage_next_month": round(float(g.storage_next_month.sum()), 2),
            "flagged": flagged.to_dict(orient="records"),
        })
    (out / f"summary_{date}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {len(df)} SKUs for {len(summary)} clients, snapshot {date}")
    for s in summary:
        print(f"  {s['client']}: {s['action']} action, {s['watch']} watch")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
