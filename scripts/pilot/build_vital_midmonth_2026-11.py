"""Build the Vital Drinks UK mid-month report datasets (1-15 Nov 2026) from DataDoe exports.

Inputs (DataDoe exports, CSV/JSON, in this folder):
  daily.csv  amazon_profit_by_date, 2025-11-01..2026-11-23
  sku.csv    amazon_profit_by_sku_and_date grouped by date+child_asin (traffic = max per ASIN-day)
  ads.csv    amazon_ads_performance_by_campaign_by_date grouped by date+campaign
  sqp_money.csv / sqp_emerging.csv  SQP weekly, money keywords (brand-level share)
  price.json amazon_fba_inventory_health 2026-11-15 (price vs featured offer)
  ../inv/inventory_2026-11-23.csv  BlueCo inventory flags (scripts/inventory_flags.py)
Sales are Amazon total sales incl. VAT, as in earlier BlueCo reports. TACoS and Total ROAS use them.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
CODE = Path(__file__).read_text()

NOV = ("2026-11-01", "2026-11-15")
OCT = ("2026-10-01", "2026-10-15")
TRAIL = [("2026-08-01", "2026-08-15"), ("2026-09-01", "2026-09-15"), ("2026-10-01", "2026-10-15")]
LY = ("2025-11-01", "2025-11-15")

NAMES = {
    "B0CZ4KSCQG": "Lemon & Lime Still Vitamin Water 12pk",
    "B0DZ6L94KC": "Raspberry Gut Health 12pk",
    "B0D9HZQRD9": "Orange Gut Health 12pk",
    "B0CZ4M5YDX": "Strawberry & Yuzu Still Vitamin Water 12pk",
    "B0G45SW3JC": "Apple & Raspberry Sparkling Vitamin Water 12pk",
    "B0F9PLP92W": "Tropical Boost Energy 12pk",
    "B0D9HX6R3R": "Peach Sparkling Vitamin Water 12pk",
    "B0G45WQTM7": "Berry Cherry Energy Water 12pk",
    "B0HDCQQBYY": "Berry Cherry Energy Water 24pk",
    "B0HDCPYLLY": "Raspberry Gut Health 24pk",
    "B0HDCKQC86": "Orange Gut Health 24pk",
    "B0HDCF1J8W": "Tropical Boost Energy 24pk",
    "B0HDCXNW2V": "Apple & Raspberry Sparkling Vitamin Water 24pk",
    "B0HDCBXNTY": "24pk (SKU VDMPSP02)",
    "B0HDC9C682": "Strawberry & Yuzu Still Vitamin Water 24pk",
    "B0HN5HKYNL": "New 12pk (SKU BDMPHL)",
    "B0HN5FS4MZ": "New 12pk (SKU VDMPHRB)",
    "B0HKZNSVBW": "ASIN B0HKZNSVBW",
}


def meta(source, method):
    return [
        {"label": "Source", "value": source},
        {"label": "Method", "value": method},
        {"label": "build_vital.py", "value": CODE, "type": "code", "lang": "python"},
    ]


def write(name, rows, source, method):
    (OUT / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": meta(source, method)}, indent=1, default=float))


def r2(x):
    return None if pd.isna(x) else round(float(x), 2)


daily = pd.read_csv(HERE / "daily.csv", parse_dates=["date"])
sku = pd.read_csv(HERE / "sku.csv", parse_dates=["date"])
ads = pd.read_csv(HERE / "ads.csv", parse_dates=["date"])


def window(df, p):
    return df[(df.date >= p[0]) & (df.date <= p[1])]


def totals(p):
    x = window(daily, p)
    s = x[["total_sales", "sales_tax", "total_units_sold", "total_orders", "ad_spend", "ad_sales",
           "total_sessions", "total_page_views", "profit"]].sum()
    pv = x.total_page_views.where(x.avg_buybox_percentage.notna())
    s["bb"] = (x.avg_buybox_percentage * x.total_page_views).sum() / pv.sum()
    return s


T = {"nov": totals(NOV), "oct": totals(OCT), "ly": totals(LY)}
trail = [totals(p) for p in TRAIL]
inv = pd.read_csv(HERE.parent / "inv" / "inventory_2026-11-23.csv")
inv = inv[inv.client == "Vital Drinks UK"]
daily_units = inv.units_30d.sum() / 30
cover_days = (inv.available.sum() + inv.inbound.sum()) / daily_units


def metrics(s):
    return {
        "sales": s.total_sales,
        "units": s.total_units_sold,
        "orders": s.total_orders,
        "ad_spend": s.ad_spend,
        "acos": s.ad_spend / s.ad_sales * 100 if s.ad_sales else None,
        "tacos": s.ad_spend / s.total_sales * 100,
        "total_roas": s.total_sales / s.ad_spend if s.ad_spend else None,
        "sessions": s.total_sessions,
        "cvr": s.total_orders / s.total_sessions * 100,
        "buybox": s.bb,
        "profit": s.profit,
        "margin": s.profit / s.total_sales * 100,
    }


M = {k: metrics(v) for k, v in T.items()}
MT = {k: sum(metrics(t)[k] for t in trail) / 3 for k in M["nov"]}
LABELS = [
    ("sales", "Sales (incl. VAT)", "money", True),
    ("units", "Units", "int", True),
    ("orders", "Orders", "int", True),
    ("ad_spend", "Ad spend", "money", None),
    ("acos", "ACoS", "pct", False),
    ("tacos", "TACoS", "pct", False),
    ("total_roas", "Total ROAS", "x", True),
    ("sessions", "Sessions", "int", True),
    ("cvr", "Conversion (orders ÷ sessions)", "pct", True),
    ("buybox", "Buy Box", "pct", True),
    ("profit", "Profit before product cost", "money", True),
    ("margin", "Margin before product cost", "pct", True),
]
score = []
for key, label, fmt, up_good in LABELS:
    n, o, t, ly = M["nov"][key], M["oct"][key], MT[key], M["ly"][key]
    score.append({
        "metric": key, "label": label, "format": fmt, "higher_is_better": up_good,
        "nov": r2(n), "oct": r2(o),
        # Aug and early Sep have no VAT in DataDoe, so their profit is overstated: compare profit with October only
        "trail3": None if key in ("profit", "margin") else r2(t),
        "last_year": r2(ly) if key in ("sales", "units", "orders", "sessions") else None,
    })
score.append({"metric": "days_cover", "label": "Days of cover (all SKUs, 23 Nov)", "format": "int",
              "higher_is_better": None, "nov": r2(cover_days), "oct": None, "trail3": None, "last_year": None})
write("scorecard", score,
      "DataDoe amazon_profit_by_date (VITAL Drinks UK); days of cover from amazon_fba_inventory_health 23 Nov",
      "Period sums for 1–15 Nov, 1–15 Oct, the average of 1–15 Aug/Sep/Oct, and 1–15 Nov 2025. Ratios from summed totals. "
      "Buy Box weighted by page views. Profit = sales − VAT − Amazon fees − product cost − ads + refunds; no product costs are uploaded, so it is before product cost.")

# Daily trend
d = window(daily, NOV)
write("daily", [{"date": x.date.strftime("%Y-%m-%d"), "sales": r2(x.total_sales), "ad_spend": r2(x.ad_spend),
                 "provisional": x.date >= pd.Timestamp("2026-11-13")} for x in d.itertuples()],
      "DataDoe amazon_profit_by_date", "One row per day, 1–15 Nov. 13–15 Nov are provisional: Amazon fees can still settle.")


# Movers
def asin_window(p):
    x = window(sku, p)
    g = x.groupby("child_asin").agg(sales=("sales_sum", "sum"), units=("units_sum", "sum"),
                                     sessions=("sessions_max", "sum"), pv=("pv_max", "sum"))
    w = x.assign(w=x.bb_max * x.pv_max, pvb=x.pv_max.where(x.bb_max.notna()))
    gb = w.groupby("child_asin")[["w", "pvb"]].sum()
    g["bb"] = gb.w / gb.pvb.replace(0, float("nan"))
    return g


N, O = asin_window(NOV), asin_window(OCT)
m = N.join(O, lsuffix="_n", rsuffix="_o", how="outer").fillna(0)
m["change"] = m.sales_n - m.sales_o
m = m[(m.units_n >= 5) | (m.units_o >= 5)]
m = m.reindex(m.change.abs().sort_values(ascending=False).index).head(5)


def driver(r):
    sess = (r.sessions_n - r.sessions_o) / r.sessions_o if r.sessions_o else 0
    cvr_o = r.units_o / r.sessions_o if r.sessions_o else 0
    cvr_n = r.units_n / r.sessions_n if r.sessions_n else 0
    cv = (cvr_n - cvr_o) / cvr_o if cvr_o else 0
    p_o = r.sales_o / r.units_o if r.units_o else 0
    p_n = r.sales_n / r.units_n if r.units_n else 0
    pr = (p_n - p_o) / p_o if p_o else 0
    bbd = r.bb_n - r.bb_o
    parts = {"Traffic": sess, "Conversion": cv, "Price": pr, "Buy Box": bbd / 100}
    return max(parts, key=lambda k: abs(parts[k])), cvr_o * 100, cvr_n * 100, p_o, p_n


CAUSES = {
    "B0CZ4KSCQG": "Sessions up 26% with conversion steady at about 23% — more shoppers reached the listing.",
    "B0D9HZQRD9": "Conversion more than doubled (10% → 23%) while sessions fell by 29%.",
    "B0D9HX6R3R": "Conversion fell from 21% to 5% on steady traffic; small numbers (7 → 2 units).",
    "B0G45SW3JC": "Conversion fell from 18% to 10% on steady traffic; ad spend down 22%.",
    "B0HDCPYLLY": "Sessions down 30% on a new 24-pack; small numbers (5 → 3 units).",
}
movers = []
for asin, r in m.iterrows():
    drv, co, cn, po, pn = driver(r)
    movers.append({"asin": asin, "product": NAMES.get(asin, asin), "sales_oct": r2(r.sales_o), "sales_nov": r2(r.sales_n),
                   "change": r2(r.change), "sessions_oct": int(r.sessions_o), "sessions_nov": int(r.sessions_n),
                   "cvr_oct": r2(co), "cvr_nov": r2(cn), "price_oct": r2(po), "price_nov": r2(pn),
                   "bb_oct": r2(r.bb_o), "bb_nov": r2(r.bb_n), "driver": drv, "cause": CAUSES.get(asin, "Cause not clear from the data.")})
write("movers", movers, "DataDoe amazon_profit_by_sku_and_date (traffic = max per ASIN and day, summed over days)",
      "Five largest sales changes 1–15 Nov vs 1–15 Oct among products selling 5+ units in either period. "
      "Driver = the largest relative change among sessions, conversion (units ÷ sessions), average price and Buy Box.")

# Waterfall
x = window(daily, NOV)
fees_other = x.total_fees.sum() - x.total_selling_fees.sum() - x.fba_fees.sum()
wf = [
    {"step": "Sales (incl. VAT)", "amount": r2(x.total_sales.sum()), "kind": "total"},
    {"step": "VAT", "amount": r2(-x.sales_tax.sum()), "kind": "cost"},
    {"step": "Referral fees", "amount": r2(-x.total_selling_fees.sum()), "kind": "cost"},
    {"step": "FBA fees (incl. storage)", "amount": r2(-x.fba_fees.sum()), "kind": "cost"},
    {"step": "Other Amazon fees", "amount": r2(-fees_other), "kind": "cost"},
    {"step": "Refunds", "amount": r2(x.refund_cost.sum()), "kind": "cost"},
    {"step": "Advertising", "amount": r2(-x.ad_spend.sum()), "kind": "cost"},
    {"step": "Reimbursements", "amount": r2(-x.cogs_total.sum()), "kind": "gain"},
    {"step": "Product cost (not uploaded)", "amount": 0.0, "kind": "cost"},
    {"step": "Profit before product cost", "amount": r2(x.profit.sum()), "kind": "total"},
]
assert abs(sum(w["amount"] for w in wf[:-1]) - wf[-1]["amount"]) < 0.05, "waterfall does not reconcile"
write("waterfall", wf, "DataDoe amazon_profit_by_date, 1–15 Nov",
      "Each step is the period sum of its column; they add up to DataDoe's profit. FBA fees include a £499 charge on 7 Nov, "
      "most likely the monthly storage fee (October's, on 7 Oct, was £260). No product costs are uploaded, so profit is before product cost.")
storage_charge = float(window(daily, ("2026-11-07", "2026-11-07")).fba_fees.sum())

# SKU profit table with unallocated line
xs = window(sku, NOV).groupby("child_asin").agg(sales=("sales_sum", "sum"), units=("units_sum", "sum"),
                                                 ad_spend=("ad_spend_sum", "sum"), fees=("fees_sum", "sum"), profit=("profit_sum", "sum"))
xs = xs[(xs.sales != 0) | (xs.profit != 0) | (xs.ad_spend != 0)].sort_values("sales", ascending=False)
prof = [{"asin": a, "product": NAMES.get(a, a), "sales": r2(r.sales), "units": int(r.units), "fees": r2(r.fees),
         "ad_spend": r2(r.ad_spend), "profit": r2(r.profit)} for a, r in xs.iterrows()]
unalloc = {k: r2(x[c].sum() - xs[k].sum()) for k, c in [("sales", "total_sales"), ("ad_spend", "ad_spend"), ("profit", "profit")]}
unalloc_fees = r2(x.total_fees.sum() - xs.fees.sum())
prof.append({"asin": "unallocated", "product": "Unallocated (account-level fees and ads)", "sales": unalloc["sales"],
             "units": int(x.total_units_sold.sum() - xs.units.sum()), "fees": unalloc_fees, "ad_spend": unalloc["ad_spend"], "profit": unalloc["profit"]})
write("sku_profit", prof, "DataDoe amazon_profit_by_sku_and_date and amazon_profit_by_date, 1–15 Nov",
      "Per-product sums. The unallocated line is the account total minus the product rows, so the table adds up to the account. "
      "It holds storage and other account-level fees and ad spend Amazon doesn't tie to a product.")

# Advertising
a = window(ads, NOV)
ao = window(ads, OCT)
bytype = []
for t, g in a.groupby("ad_campaign_type"):
    go = ao[ao.ad_campaign_type == t]
    bytype.append({"type": t.replace("SPONSORED_", "Sponsored ").title().replace("Sponsored ", "Sponsored "),
                   "spend": r2(g.spend_sum.sum()), "ad_sales": r2(g.ad_sales_sum.sum()),
                   "acos": r2(g.spend_sum.sum() / g.ad_sales_sum.sum() * 100) if g.ad_sales_sum.sum() else None,
                   "spend_oct": r2(go.spend_sum.sum()), "ad_sales_oct": r2(go.ad_sales_sum.sum())})
write("ads_by_type", bytype, "DataDoe amazon_ads_performance_by_campaign_by_date",
      "Spend and attributed ad sales by campaign type, 1–15 Nov and 1–15 Oct. ACoS = spend ÷ ad sales.")
c = a.groupby(["ad_campaign_type", "ad_campaign_name"])[["spend_sum", "ad_sales_sum", "ad_orders_sum", "clicks_sum"]].sum().reset_index()
c = c[c.spend_sum > 0]
c["acos"] = c.spend_sum / c.ad_sales_sum.replace(0, float("nan")) * 100
c["sort"] = c.acos.fillna(1e9)
c = c.sort_values(["sort", "spend_sum"], ascending=[False, False]).head(10)
worst = [{"campaign": r.ad_campaign_name, "type": r.ad_campaign_type.replace("SPONSORED_", "").title(), "spend": r2(r.spend_sum),
          "ad_sales": r2(r.ad_sales_sum), "orders": int(r.ad_orders_sum), "clicks": int(r.clicks_sum),
          "acos": r2(r.acos), "wasted": r2(r.spend_sum if r.ad_sales_sum == 0 else 0)} for r in c.itertuples()]
write("worst_campaigns", worst, "DataDoe amazon_ads_performance_by_campaign_by_date, 1–15 Nov",
      "The ten campaigns with the highest ACoS among those that spent; no sales sorts first. Wasted = spend on a campaign with no attributed sales in the period.")

# Search share
sm = pd.read_csv(HERE / "sqp_money.csv")
sm = sm[sm.vol_recent > 0]
write("search_money", [{"query": r.query, "volume_recent": int(r.vol_recent), "imp_prior": r2(r.imp_prior * 100), "imp_recent": r2(r.imp_recent * 100),
                        "click_recent": r2(r.clk_recent * 100), "purchase_recent": r2(r.pur_recent * 100), "status": r.status}
                       for r in sm.itertuples()],
      "DataDoe amazon_child_product_organic_search_ranks_per_week (SQP), weeks of 18 Oct – 14 Nov",
      "Money keywords = queries where Vital ASINs had 2+ purchases over 6 weeks, ranked by volume × purchase share. Shares add up "
      "Vital's ASINs per query. Recent = weeks starting 1 and 8 Nov; prior = weeks starting 18 and 25 Oct. Slipping/rising = impression share down/up 25%+. "
      "SQP shares don't separate organic from sponsored visibility.")
em = pd.read_csv(HERE / "sqp_emerging.csv")
em = em[em.search_query.isin(["sugar free drinks", "energy drinks"])]
write("search_emerging", [{"query": r.search_query, "volume_prior": int(r.vp), "volume_recent": int(r.vr), "growth": r2(r.growth * 100), "share": r2(r.share * 100)}
                          for r in em.itertuples()],
      "DataDoe SQP weekly", "Relevant queries whose volume grew 30%+ between the two-week windows where Vital's impression share is under 5%.")

# Stock (lead time 20 days)
LEAD = 20
today = pd.Timestamp("2026-11-24")
stock = []
for r in inv.sort_values("units_30d", ascending=False).itertuples():
    daily_rate = r.units_30d / 30
    reorder = (today + pd.Timedelta(days=max(r.days_cover - LEAD, 0))).strftime("%Y-%m-%d") if daily_rate > 0 and r.days_cover < 365 else ""
    status = "red" if (r.units_30d > 0 and r.days_cover < LEAD) or (r.available == 0 and r.units_30d > 0) else (
        "amber" if r.level in ("red", "amber") else "green")
    stock.append({"sku": r.sku, "asin": r.asin, "product": NAMES.get(r.asin, r.product), "available": int(r.available), "inbound": int(r.inbound),
                  "units_30d": int(r.units_30d), "days_cover": int(r.days_cover), "reorder_by": reorder, "flag": r.flag,
                  "storage_next_month": r2(r.storage_next_month), "status": status})
pz = pd.DataFrame(json.load(open(HERE / "price.json")))
sold30 = {"B0HDCXNW2V": 1}  # units sold 26 Oct–24 Nov per DataDoe cogs_missing_list
for r in pz[(pz.available == 0) & ~pz.child_asin.isin([s["asin"] for s in stock]) & ~pz.child_asin.isin(["B0HN5HKYNL", "B0HN5FS4MZ"])].itertuples():
    stock.append({"sku": r.sku, "asin": r.child_asin, "product": NAMES.get(r.child_asin, r.child_asin), "available": 0, "inbound": 0,
                  "units_30d": sold30.get(r.child_asin, 0), "days_cover": 0, "reorder_by": "", "flag": "Out of stock",
                  "storage_next_month": 0.0, "status": "red" if sold30.get(r.child_asin, 0) else "amber"})
write("stock", stock, "DataDoe amazon_fba_inventory_health snapshot 23 Nov, flagged with scripts/inventory_flags.py",
      f"Reorder by = today + days of cover − {LEAD}-day lead time. Red = inside lead time or out of stock while selling. "
      "Days of cover count units already inbound; 366 means a year or more.")

# Health
write("health", [
    {"gate": "Account Health Rating", "value": "220", "target": "200+", "status": "GREAT"},
    {"gate": "Order defect rate (FBA)", "value": "0%", "target": "under 1%", "status": "GOOD"},
    {"gate": "Late shipment rate", "value": "0%", "target": "Amazon target", "status": "GOOD"},
    {"gate": "Cancellation rate", "value": "0%", "target": "Amazon target", "status": "GOOD"},
    {"gate": "Policy violations (all 11 categories, 6 months)", "value": "0", "target": "0", "status": "GOOD"},
    {"gate": "Active policy warnings", "value": "0", "target": "0", "status": "GOOD"},
], "DataDoe amazon_seller_performance, snapshot 23 Nov 2026",
    "Scored as in DataDoe's Daily Account Health Check skill: each metric's own status and target. Seller-fulfilled metrics don't apply (FBA only).")

# Competitors / Buy Box
pj = pd.DataFrame(json.load(open(HERE / "price.json")))
pj = pj[(pj.available > 0) & (pj.your_price > 0)]
bbn = N.bb
comp = []
for r in pj.itertuples():
    comp.append({"sku": r.sku, "asin": r.child_asin, "product": NAMES.get(r.child_asin, r.child_asin), "your_price": r2(r.your_price),
                 "featured_offer": r2(r.featuredoffer_price), "gap": r2(r.your_price - r.featuredoffer_price),
                 "buybox_nov": r2(bbn.get(r.child_asin)), "sessions_nov": int(N.sessions.get(r.child_asin, 0))})
comp.sort(key=lambda z: -z["sessions_nov"])
write("competitors", comp, "DataDoe amazon_fba_inventory_health 15 Nov (prices) and amazon_profit_by_sku_and_date (Buy Box, 1–15 Nov)",
      "Price gap = your price − featured offer price on 15 Nov, in-stock FBA SKUs. Buy Box weighted by page views. Following DataDoe's Buy Box "
      "Loss Root Cause skill, below 95% is sharing and below 80% a loss, only with 20+ page views.")

summary = {
    "storage_charge_nov7": r2(storage_charge),
    "profit_ex_storage": r2(x.profit.sum() + storage_charge),
    "storage_charge_oct7": r2(window(daily, ("2026-10-07", "2026-10-07")).fba_fees.sum()),
    "oct_profit_ex_storage": r2(window(daily, OCT).profit.sum() + window(daily, ("2026-10-07", "2026-10-07")).fba_fees.sum()),
    "cover_days": r2(cover_days),
}
write("facts", [summary], "Derived from the datasets above", "Single values used in sentences on the page.")
print(json.dumps(summary), file=sys.stderr)
print("datasets:", sorted(p.name for p in OUT.glob("*.json")))
