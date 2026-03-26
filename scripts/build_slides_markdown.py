#!/usr/bin/env python3
"""
Build copy-paste markdown for Google Slides from saved JSON + live API (optional).

Prereqs:
  - reports/batch_2026_12.json  from GET /api/batch/all-metrics?base_week=2026-12&num_weeks=8
  - reports/mtd_2026_12.json    from GET /api/metrics/table1-mtd?base_week=2026-12
  - Top products (optional; else script curls localhost:8000):
      reports/top_products_new_2026_12.json
      reports/top_products_returning_2026_12.json

Usage:
  python scripts/build_slides_markdown.py
  python scripts/build_slides_markdown.py 2026-12 http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=600) as r:
        return json.loads(r.read().decode())


def sek_k(v):
    if v is None:
        return "–"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{round(x / 1000):,}".replace(",", " ")


def pct(v, nd=1):
    try:
        return f"{float(v):.{nd}f}%"
    except (TypeError, ValueError):
        return "–"


def n_int(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "–"


def n_sek_plain(v):
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "–"


def yoy(cur, prev):
    try:
        c, p = float(cur), float(prev)
        if p == 0:
            return "–"
        return f"{round((c - p) / p * 100):+d}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return "–"


def cat_lines(cats: dict, topn=8):
    items = sorted(cats.items(), key=lambda kv: -float(kv[1]))
    lines = []
    for name, rev in items[:topn]:
        lines.append(f"• {name}: {sek_k(rev)} tSEK gross")
    return "\n".join(lines)


def prod_lines(products, n=5):
    lines = []
    for p in products[:n]:
        lines.append(
            f"• #{p['rank']} {p['product']} ({p['color']}) — {sek_k(p['gross_revenue'])} tSEK, qty {int(p['sales_qty'])}"
        )
    return "\n".join(lines)


def main():
    week = sys.argv[1] if len(sys.argv) > 1 else "2026-12"
    api = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else None

    batch_path = REPORTS / f"batch_{week.replace('-', '_')}.json"
    if not batch_path.exists():
        batch_path = REPORTS / "batch_2026_12.json"

    mtd_path = REPORTS / f"mtd_{week.replace('-', '_')}.json"
    if not mtd_path.exists():
        mtd_path = REPORTS / "mtd_2026_12.json"

    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    mtd = json.loads(mtd_path.read_text(encoding="utf-8"))

    week_us = week.replace("-", "_")
    tp_new_path = REPORTS / f"top_products_new_{week_us}.json"
    tp_ret_path = REPORTS / f"top_products_returning_{week_us}.json"
    if not tp_new_path.exists():
        alt = REPORTS / f"top_products_new_{week}.json"
        if alt.exists():
            tp_new_path = alt
    if not tp_ret_path.exists():
        alt = REPORTS / f"top_products_returning_{week}.json"
        if alt.exists():
            tp_ret_path = alt
    if api:
        if not tp_new_path.exists():
            tp_new_path.write_text(
                json.dumps(
                    fetch_json(
                        f"{api}/api/top-products?base_week={week}&num_weeks=1&top_n=10&customer_type=new"
                    )
                ),
                encoding="utf-8",
            )
        if not tp_ret_path.exists():
            tp_ret_path.write_text(
                json.dumps(
                    fetch_json(
                        f"{api}/api/top-products?base_week={week}&num_weeks=1&top_n=10&customer_type=returning"
                    )
                ),
                encoding="utf-8",
            )
    tp_new = json.loads(tp_new_path.read_text(encoding="utf-8"))
    tp_ret = json.loads(tp_ret_path.read_text(encoding="utf-8"))

    metrics = batch["metrics"]
    act, lw, ly = metrics["actual"], metrics["last_week"], metrics["last_year"]

    markets = sorted(batch["markets"], key=lambda r: -float(r.get("average") or 0))
    contrib = next((c for c in batch["contribution"] if c["week"] == week), batch["contribution"][-1])
    men_w = next((x for x in batch["men_category_sales"] if x["week"] == week), batch["men_category_sales"][-1])
    women_w = next((x for x in batch["women_category_sales"] if x["week"] == week), batch["women_category_sales"][-1])
    pg = batch["products_gender"]
    men_p = next((x for x in pg["men"] if x["week"] == week), pg["men"][-1])
    women_p = next((x for x in pg["women"] if x["week"] == week), pg["women"][-1])

    kpis = batch["kpis"]
    k = next((x for x in kpis if x["week"] == week), kpis[-1])
    newC, retC = int(k["new_customers"]), int(k["returning_customers"])
    totC = newC + retC
    total_aov = (newC * k["aov_new_customer"] + retC * k["aov_returning_customer"]) / totC if totC else 0
    aud = {
        "total_aov": round(total_aov),
        "total_customers": totC,
        "total_orders": int(round(k["total_orders"])),
        "new_customers": newC,
        "returning_customers": retC,
        "return_rate_pct": k["return_rate_pct"],
        "cos_pct": k["cos"],
        "cac": round(k["new_customer_cac"]),
        "sessions": int(k["sessions"]),
        "conversion_rate": k["conversion_rate"],
        "marketing_spend": k["marketing_spend"],
    }

    mp = mtd["periods"]
    mtd_act, mtd_ly = mp["mtd_actual"], mp["mtd_last_year"]
    mtd_bud = mp.get("mtd_budget", {})

    dr_info = mtd["date_ranges"]["actual"]["display"]
    lines = [
        "# Weekly report — copy into Google Slides",
        f"**ISO week {week.split('-')[1]} · {week.split('-')[0]} (Summary actual week: {dr_info})**",
        "",
        "Values match the app: **tSEK** = thousands SEK unless full SEK is stated.",
        "",
        "## Slide 1 — Summary",
        f"- **Online gross revenue:** {sek_k(act['online_gross_revenue'])} tSEK  |  LW {sek_k(lw['online_gross_revenue'])}  |  YoY {yoy(act['online_gross_revenue'], ly['online_gross_revenue'])}",
        f"- **Online net revenue:** {sek_k(act['online_net_revenue'])} tSEK  |  LW {sek_k(lw['online_net_revenue'])}  |  YoY {yoy(act['online_net_revenue'], ly['online_net_revenue'])}",
        f"- **Returns:** {sek_k(act['returns'])} tSEK  |  **Return rate:** {pct(act['return_rate_pct'])}",
        f"- **Total net revenue (all channels):** {sek_k(act['total_net_revenue'])} tSEK",
        f"- **Retail net:** {sek_k(act['retail_net_revenue'])} tSEK  |  **Wholesale net:** {sek_k(act['wholesale_net_revenue'])} tSEK",
        f"- **New customers:** {n_int(act['new_customers'])}  |  **Returning:** {n_int(act['returning_customers'])}",
        f"- **Marketing spend:** {sek_k(act['marketing_spend'])} tSEK  |  **Online CoS:** {pct(act['online_cost_of_sale_3'])}  |  **aMER:** {float(act['emer']):.1f}",
        "",
        "## Slide 2 — Summary MTD",
        f"- **MTD window:** {mtd['date_ranges']['mtd_actual']['display']}",
        f"- **Online gross (MTD):** {sek_k(mtd_act['online_gross_revenue'])} tSEK  |  LY {sek_k(mtd_ly['online_gross_revenue'])}  |  YoY {yoy(mtd_act['online_gross_revenue'], mtd_ly['online_gross_revenue'])}",
        f"- **Online net (MTD):** {sek_k(mtd_act['online_net_revenue'])} tSEK  |  LY {sek_k(mtd_ly['online_net_revenue'])}",
        f"- **Return rate (MTD):** {pct(mtd_act['return_rate_pct'])}  (LY {pct(mtd_ly['return_rate_pct'])})",
        f"- **Total net revenue (MTD):** {sek_k(mtd_act['total_net_revenue'])} tSEK  |  LY {sek_k(mtd_ly['total_net_revenue'])}",
        f"- **New (MTD):** {n_int(mtd_act['new_customers'])}  |  **Returning:** {n_int(mtd_act['returning_customers'])}  |  LY {n_int(mtd_ly['new_customers'])}/{n_int(mtd_ly['returning_customers'])}",
        f"- **Marketing spend (MTD):** {sek_k(mtd_act['marketing_spend'])} tSEK  |  LY {sek_k(mtd_ly['marketing_spend'])}",
        f"- **Online CoS (MTD):** {pct(mtd_act['online_cost_of_sale_3'])}  |  **aMER:** {float(mtd_act['emer']):.1f}",
    ]
    if mtd_bud:
        lines.append(
            f"- **Budget (MTD):** online gross {sek_k(mtd_bud.get('online_gross_revenue'))} tSEK  |  online net {sek_k(mtd_bud.get('online_net_revenue'))}  |  total net {sek_k(mtd_bud.get('total_net_revenue'))}"
        )
    lines.append("")
    lines.append("## Slide 3 — Top markets & contribution")
    lines.append("### Top markets (8-week avg online gross · latest week tSEK)")
    lines.append("| Market | Avg tSEK | Latest week |")
    lines.append("|--------|----------|-------------|")
    for row in markets[:10]:
        wk = row["weeks"].get(week, 0)
        lines.append(f"| {row['country']} | {sek_k(row['average'])} | {sek_k(wk)} |")
    lines.append("")
    lines.append(f"### Contribution — week {contrib['week']}")
    lines.append(f"- **Gross new / returning:** {n_sek_plain(contrib['gross_revenue_new'])} / {n_sek_plain(contrib['gross_revenue_returning'])} SEK")
    lines.append(f"- **Contribution new / returning / total:** {n_sek_plain(contrib['contribution_new'])} / {n_sek_plain(contrib['contribution_returning'])} / {n_sek_plain(contrib['contribution_total'])} SEK")
    if contrib.get("last_year"):
        lines.append(f"- **LY contribution total:** {n_sek_plain(contrib['last_year'].get('contribution_total', 0))} SEK")
    lines.append("")
    lines.append("## Slide 4 — Men category sales (week)")
    lines.append(f"- **Week:** {men_w['week']}")
    lines.append(cat_lines(men_w["categories"]))
    lines.append("")
    lines.append("## Slide 5 — Women category sales (week)")
    lines.append(f"- **Week:** {women_w['week']}")
    lines.append(cat_lines(women_w["categories"]))
    lines.append("")
    lines.append("## Slide 6 — Products new & returning (top 10)")
    for title, tp, ctype in [
        ("New customers", tp_new, "new"),
        ("Returning customers", tp_ret, "returning"),
    ]:
        wk = tp["top_products"][0]
        tt, gt = wk["top_total"], wk["grand_total"]
        lines.append(f"### {title}")
        lines.append(
            f"- **Top 10 share:** {float(tt['sob']):.0f}% of {ctype} gross ({sek_k(tt['gross_revenue'])} tSEK of {sek_k(gt['gross_revenue'])} tSEK)"
        )
        lines.append(prod_lines(wk["products"], 10))
        lines.append("")
    lines.append("## Slide 7 — Products by gender (top 5)")
    lines.append("### Men")
    lines.append(prod_lines(men_p["products"], 5))
    lines.append("### Women")
    lines.append(prod_lines(women_p["products"], 5))
    lines.append("")
    lines.append("## Slide 8 — Audience total (online KPIs)")
    lines.append(f"- **Blended AOV:** {aud['total_aov']} SEK")
    lines.append(f"- **Customers / orders:** {n_int(aud['total_customers'])} / {n_int(aud['total_orders'])}")
    lines.append(f"- **New / returning:** {n_int(aud['new_customers'])} / {n_int(aud['returning_customers'])}")
    lines.append(f"- **Sessions / conversion:** {n_int(aud['sessions'])} / {float(aud['conversion_rate']):.2f}%")
    lines.append(f"- **Return rate / CoS / nCAC:** {pct(aud['return_rate_pct'])} / {pct(aud['cos_pct'])} / {n_int(aud['cac'])} SEK")
    lines.append(f"- **Marketing spend:** {n_sek_plain(aud['marketing_spend'])} SEK")
    if k.get("last_year"):
        lk = k["last_year"]
        lines.append(
            f"- **LY same week:** orders {n_int(lk['total_orders'])}  |  new/ret {n_int(lk['new_customers'])}/{n_int(lk['returning_customers'])}  |  sessions {n_int(lk['sessions'])}"
        )
    lines.append("")
    lines.append("---")
    lines.append("*Regenerate: `python scripts/build_slides_markdown.py`*")

    out = REPORTS / f"slides_week_{week}_GOOGLE_SLIDES_COPY_PASTE.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
