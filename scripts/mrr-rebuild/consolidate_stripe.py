#!/usr/bin/env python3
"""MRR Rebuild, Phase 3: add Stripe and build a consolidated view.

Starting from the MRR Rebuild template (facility blocks, no fees), writes a workbook with:

  HubSpot          fee grid from HubSpot invoice line items (same as populate_fees.py)
  Stripe           fee grid from a Stripe invoice line item export
  Consolidated     HubSpot + Stripe, with Stripe-synced HubSpot invoices removed
  Synced Duplicates  the HubSpot invoices dropped because they are copies of Stripe invoices
  Stripe Mapping   which facility each Stripe customer was put on, and how
  Stripe Not Placed  Stripe lines that could not be put on a facility
  Checks           monthly reconciliation of the three grids
  HubSpot Detail / Stripe Detail  line-by-line audit lists

Duplicates
  Stripe syncs invoices into HubSpot (hs_invoice_source = data_sync). A HubSpot invoice is treated
  as a copy of a Stripe invoice when it is a data_sync invoice with the same invoice number and the
  same total. Native HubSpot invoices are never dropped: their numbers collide with Stripe's
  INV-xxxx series but they are different invoices.

Stripe rules
  * Void, draft and uncollectible invoices are skipped.
  * Amount = line_amount - line_discount (matches invoice_total on every invoice).
  * Fee row uses the same rule as HubSpot (populate_fees.category); the month is the
    Stripe invoice date.
  * Facility, first match wins:
      1. the synced HubSpot copy of the same invoice -> that invoice's facilities
      2. the facilities the customer's other synced invoices sit on (most frequent)
      3. customer email -> HubSpot contact -> associated facilities
      4. customer name equals a facility name
    When more than one facility remains, names in the customer name are used to narrow it down;
    otherwise the amount is split evenly across them, as for shared HubSpot invoices.

Usage: consolidate_stripe.py TEMPLATE.xlsx STRIPE.csv OUTPUT.xlsx
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date

import openpyxl

import populate_fees as hs

SKIP_STRIPE_STATUSES = {"void", "draft", "uncollectible"}
GENERIC_WORDS = {"storage", "self", "mini", "the", "llc", "inc", "and", "of", "storages", "center",
                 "centers", "co", "rv", "boat", "units"}


def norm(name):
    name = re.sub(r"\(.*?\)", " ", (name or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name)).strip()


def tokens(name):
    return {t for t in norm(name).split() if t not in GENERIC_WORDS and len(t) > 1}


def narrow_by_name(customer_name, candidates, facilities):
    """Pick the candidate facilities whose distinctive name words best match the customer name."""
    if len(candidates) <= 1:
        return candidates
    cust = tokens(customer_name)
    scores = {c: len(cust & tokens(facilities[c]["name"])) for c in candidates}
    best = max(scores.values())
    if best == 0:
        return candidates
    return sorted(c for c, s in scores.items() if s == best)


def read_stripe(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    for r in rows:
        r["net"] = round(float(r["line_amount"] or 0) - float(r["line_discount"] or 0), 2)
        r["invoice_total"] = float(r["invoice_total"] or 0)
        r["customer_email"] = (r["customer_email"] or "").strip().lower()
    return rows


def lookup_email_companies(emails):
    found = {}
    for batch in hs.chunks(sorted(emails), 100):
        data = hs.call("POST", "/crm/v3/objects/contacts/batch/read",
                       json={"idProperty": "email", "properties": ["email"],
                             "inputs": [{"id": e} for e in batch]})
        for r in data.get("results", []):
            found[(r["properties"].get("email") or "").lower()] = r["id"]
    contact_cos = hs.associations("contacts", "companies", list(found.values())) if found else {}
    return {e: contact_cos.get(cid, []) for e, cid in found.items()}


def match_synced(hs_lines, stripe_rows):
    """{hubspot invoice id: stripe invoice id} for data_sync copies of Stripe invoices."""
    stripe_by_number = defaultdict(list)
    for r in stripe_rows:
        stripe_by_number[r["invoice_number"]].append(r)
    matches = {}
    for ln in hs_lines:
        if ln["invoice_source"] != "data_sync" or ln["invoice_id"] in matches:
            continue
        for r in stripe_by_number.get(ln["invoice_number"], []):
            if abs(r["invoice_total"] - ln["invoice_total"]) < 0.02:
                matches[ln["invoice_id"]] = r["invoice_id"]
                break
    return matches


def map_customers(stripe_rows, hs_lines, synced, facilities, email_cos):
    """Returns ({stripe invoice id: [cids]}, {customer id: (cids, method)})."""
    hs_inv_cids = defaultdict(set)
    for ln in hs_lines:
        hs_inv_cids[ln["invoice_id"]].add(ln["cid"])
    stripe_inv_cids = {}
    for hs_id, st_id in synced.items():
        stripe_inv_cids[st_id] = sorted(hs_inv_cids[hs_id])

    customers = {}
    cust_counts = defaultdict(Counter)
    for r in stripe_rows:
        customers[r["customer_id"]] = r
        for cid in stripe_inv_cids.get(r["invoice_id"], []):
            cust_counts[r["customer_id"]][cid] += 1
    names = defaultdict(list)
    for cid, fac in facilities.items():
        names[norm(fac["name"])].append(cid)

    customer_map = {}
    for cust_id, r in customers.items():
        name = r["customer_name"]
        if cust_counts[cust_id]:
            top = max(cust_counts[cust_id].values())
            cids = sorted(c for c, n in cust_counts[cust_id].items() if n == top)
            method = "customer's synced invoices"
        elif [c for c in email_cos.get(r["customer_email"], []) if c in facilities]:
            cids = sorted(c for c in email_cos[r["customer_email"]] if c in facilities)
            method = "contact email"
        elif norm(name) in names:
            cids = names[norm(name)]
            method = "name match"
        else:
            customer_map[cust_id] = ([], "no match")
            continue
        customer_map[cust_id] = (narrow_by_name(name, cids, facilities), method)
    return stripe_inv_cids, customer_map


def stripe_lines(stripe_rows, stripe_inv_cids, customer_map, facilities):
    lines, unmatched, skipped = [], [], []
    for r in stripe_rows:
        if r["invoice_status"] in SKIP_STRIPE_STATUSES:
            skipped.append(r)
            continue
        if r["invoice_id"] in stripe_inv_cids:
            cids, method = stripe_inv_cids[r["invoice_id"]], "synced invoice"
        else:
            cids, method = customer_map[r["customer_id"]]
        if not cids:
            unmatched.append(r)
            continue
        inv_date = date.fromisoformat(r["invoice_date"]) if r["invoice_date"] else None
        if inv_date:
            ym, source = (inv_date.year, inv_date.month), "invoice date"
        else:
            ym, source = None, "no date"
        for cid in cids:
            lines.append({
                "cid": cid, "facility": facilities[cid]["name"],
                "customer": r["customer_name"], "customer_id": r["customer_id"], "map_method": method,
                "invoice_number": r["invoice_number"], "invoice_id": r["invoice_id"],
                "invoice_status": r["invoice_status"], "invoice_date": inv_date,
                "line_id": r["line_item_id"], "line_name": r["line_item"],
                "amount": round(r["net"] / len(cids), 2), "full_amount": r["net"], "share": len(cids),
                "currency": r["currency"], "fee": hs.category(r["line_item"]), "ym": ym,
                "month_source": source,
            })
    return lines, unmatched, skipped


def copy_grid(wb, template_ws, title):
    ws = wb.copy_worksheet(template_ws)
    ws.title = title
    ws.freeze_panes = template_ws.freeze_panes
    for key, dim in template_ws.column_dimensions.items():
        ws.column_dimensions[key].width = dim.width
    return ws


def ym_label(ym):
    return f"{ym[0]}-{ym[1]:02d}" if ym else None


def main(template, stripe_csv, dst):
    wb = openpyxl.load_workbook(template)
    base = wb[hs.SHEET]
    hs.extend_months(base)
    month_cols = hs.month_columns(base)
    facilities = hs.read_facilities(base)
    print(f"{len(facilities)} facilities on sheet")
    for name, (old, new) in hs.refresh_lost_dates(base, facilities).items():
        print(f"Lost Date changed for {name}: {old} -> {new}")

    hs_all, no_inv = hs.fetch_hubspot_lines(facilities)
    stripe_rows = read_stripe(stripe_csv)
    print(f"{len(stripe_rows)} Stripe lines on {len({r['invoice_id'] for r in stripe_rows})} invoices")

    synced = match_synced(hs_all, stripe_rows)
    unmatched_sync = {ln["invoice_id"] for ln in hs_all
                      if ln["invoice_source"] == "data_sync" and ln["invoice_id"] not in synced}
    print(f"{len(synced)} HubSpot invoices are Stripe copies; {len(unmatched_sync)} data_sync without a match")

    email_cos = lookup_email_companies({r["customer_email"] for r in stripe_rows if r["customer_email"]})
    stripe_inv_cids, customer_map = map_customers(stripe_rows, hs_all, synced, facilities, email_cos)
    st_all, st_unmatched, st_skipped = stripe_lines(stripe_rows, stripe_inv_cids, customer_map, facilities)

    hs_dupes = [ln for ln in hs_all if ln["invoice_id"] in synced]
    hs_native = [ln for ln in hs_all if ln["invoice_id"] not in synced]

    hs_tot, hs_placed, hs_np = hs.place(hs_all, facilities, month_cols)
    st_tot, st_placed, st_np = hs.place(st_all, facilities, month_cols)
    dup_tot, dup_placed, _ = hs.place(hs_dupes, facilities, month_cols)
    con_tot, con_placed, con_np = hs.place(hs_native + st_all, facilities, month_cols)

    base.title = "HubSpot"
    grids = {"HubSpot": base}
    for title in ("Stripe", "Consolidated", "Synced Duplicates"):
        grids[title] = copy_grid(wb, base, title)
    hs.write_grid(grids["HubSpot"], facilities, month_cols, hs_tot)
    hs.write_grid(grids["Stripe"], facilities, month_cols, st_tot)
    hs.write_grid(grids["Consolidated"], facilities, month_cols, con_tot)
    hs.write_grid(grids["Synced Duplicates"], facilities, month_cols, dup_tot)

    # Mapping and exceptions
    cust_amount, cust_lines = Counter(), Counter()
    for r in stripe_rows:
        if r["invoice_status"] not in SKIP_STRIPE_STATUSES:
            cust_amount[r["customer_id"]] += r["net"]
            cust_lines[r["customer_id"]] += 1
    seen_cust = {}
    for r in stripe_rows:
        seen_cust.setdefault(r["customer_id"], r)
    mapping_rows = []
    for cust_id, r in sorted(seen_cust.items(), key=lambda kv: kv[1]["customer_name"].lower()):
        cids, method = customer_map[cust_id]
        mapping_rows.append([r["customer_name"], r["customer_email"], cust_id,
                             "; ".join(facilities[c]["name"] for c in cids), "; ".join(cids), method,
                             cust_lines[cust_id], round(cust_amount[cust_id], 2)])
    hs.write_table(wb, "Stripe Mapping",
                   ["Stripe Customer", "Email", "Customer ID", "Facility", "Company ID", "Matched By",
                    "Lines (billable)", "Amount (billable)"], mapping_rows)

    not_placed_rows = [[r["customer_name"], r["customer_email"], r["invoice_number"], r["invoice_status"],
                        r["invoice_date"], r["line_item"], r["net"], "no facility match"] for r in st_unmatched]
    not_placed_rows += [[ln["customer"], "", ln["invoice_number"], ln["invoice_status"], ln["invoice_date"],
                         ln["line_name"], ln["amount"], why] for ln, why in st_np]
    hs.write_table(wb, "Stripe Not Placed",
                   ["Stripe Customer", "Email", "Invoice #", "Status", "Invoice Date", "Line Item",
                    "Amount", "Reason"], not_placed_rows)

    stripe_by_invoice = defaultdict(list)
    for r in stripe_rows:
        stripe_by_invoice[r["invoice_id"]].append(r)
    dupe_lines = defaultdict(list)
    for ln in hs_dupes:
        dupe_lines[ln["invoice_id"]].append(ln)
    dupe_rows = []
    for hs_id, st_id in sorted(synced.items()):
        lns, srs = dupe_lines[hs_id], stripe_by_invoice[st_id]
        hs_amount = round(sum(ln["amount"] for ln in lns), 2)
        hs_count = len({ln["line_id"] for ln in lns})
        discount = round(sum(float(r["line_discount"] or 0) for r in srs), 2)
        if abs(hs_amount - srs[0]["invoice_total"]) <= 1:
            note = ""
        elif hs_count < len(srs):
            note = f"HubSpot copy has {hs_count} of {len(srs)} line items (sync drops lines past 10)"
        elif discount:
            note = "Stripe discount not carried onto HubSpot line items"
        else:
            note = "unexplained difference"
        dupe_rows.append([lns[0]["invoice_number"], hs_id, st_id, "; ".join(sorted({ln["facility"] for ln in lns})),
                          srs[0]["invoice_status"], hs_count, len(srs), hs_amount, srs[0]["invoice_total"],
                          discount, note])
    hs.write_table(wb, "Duplicate Invoices",
                   ["Invoice #", "HubSpot Invoice ID", "Stripe Invoice ID", "Facility", "Stripe Status",
                    "HubSpot Lines", "Stripe Lines", "HubSpot Amount (placed)", "Stripe Invoice Total",
                    "Stripe Discount", "Note"], dupe_rows)

    hs.write_table(wb, "HubSpot Detail", hs.HS_DETAIL_HEADERS + ["Invoice Source", "Stripe Copy"],
                   [hs.hs_detail_row(ln) + [ln["invoice_source"], "yes" if ln["invoice_id"] in synced else ""]
                    for ln in hs_placed])
    hs.write_table(wb, "Stripe Detail",
                   ["Facility", "Company ID", "Stripe Customer", "Matched By", "Invoice #", "Stripe Invoice ID",
                    "Status", "Invoice Date", "Line Item ID", "Line Item", "Amount", "Currency", "Fee Row",
                    "Service Month", "Month Source", "Shared Split"],
                   [[ln["facility"], ln["cid"], ln["customer"], ln["map_method"], ln["invoice_number"],
                     ln["invoice_id"], ln["invoice_status"], ln["invoice_date"], ln["line_id"], ln["line_name"],
                     ln["amount"], ln["currency"], ln["fee"], ym_label(ln["ym"]), ln["month_source"],
                     f"1/{ln['share']} of {ln['full_amount']:,.2f}" if ln["share"] > 1 else None]
                    for ln in st_placed])

    # Monthly reconciliation (values; the Google Sheet version recomputes the grid totals with formulas)
    def by_month(lines):
        out = Counter()
        for ln in lines:
            out[ln["ym"]] += ln["amount"]
        return out
    hs_m, dup_m, st_m, con_m = (by_month(x) for x in (hs_placed, dup_placed, st_placed, con_placed))
    st_synced_m = by_month([ln for ln in st_placed if ln["map_method"] == "synced invoice"])
    check_rows = []
    for ym in sorted(month_cols):
        h, d, s_syn, s, c = (round(m[ym], 2) for m in (hs_m, dup_m, st_synced_m, st_m, con_m))
        check_rows.append([ym_label(ym), h, d, s_syn, round(d - s_syn, 2), s, c, round(h - d + s - c, 2)])
    hs.write_table(wb, "Checks",
                   ["Month", "HubSpot", "Synced copies (HubSpot version)", "Same invoices (Stripe version)",
                    "Copy vs original", "Stripe", "Consolidated", "Consolidated - (HubSpot - copies + Stripe)"],
                   check_rows)

    wb.save(dst)

    summary = {
        "hubspot_lines": len(hs_placed), "hubspot_total": round(sum(ln["amount"] for ln in hs_placed), 2),
        "duplicate_invoices": len(synced), "duplicate_total": round(sum(ln["amount"] for ln in dup_placed), 2),
        "unmatched_data_sync": len(unmatched_sync),
        "stripe_lines_billable": len(stripe_rows) - len(st_skipped),
        "stripe_lines_skipped": len(st_skipped),
        "stripe_lines_unmatched": len(st_unmatched),
        "stripe_unmatched_total": round(sum(r["net"] for r in st_unmatched), 2),
        "stripe_placed_total": round(sum(ln["amount"] for ln in st_placed), 2),
        "consolidated_total": round(sum(ln["amount"] for ln in con_placed), 2),
        "customers_by_method": Counter(m for _, m in customer_map.values()),
    }
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"saved {dst}")
    return summary


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
