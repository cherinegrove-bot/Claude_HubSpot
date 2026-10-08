#!/usr/bin/env python3
"""MRR Rebuild, Phase 2: fill the fee rows of the MRR Rebuild workbook from
HubSpot invoice line items.

For every facility block on the "MRR Rebuild" sheet (header row + Management /
Marketing / Bookkeeping / Other Fee rows), pulls the Company's invoices and
their line items and writes monthly totals into the fee rows. The header-row
SUM formulas are left in place.

Rules
  * Category from line item name: "management" -> Management Fee,
    "marketing" -> Marketing Fee, "bookkeep" -> Bookkeeping Fee, everything
    else (reimbursements, StorageReach, Sparefoot, AI Lean, ...) -> Other Fee.
  * Service month: "<Month> <YYYY>" in the line item name when present,
    otherwise the invoice date (America/New_York), falling back to the
    invoice create date.
  * Voided and draft invoices are skipped.
  * Amount = line item `amount` (net of discounts). An invoice associated
    with several facilities on the sheet (one bill for sister sites) is
    split evenly across them, so it is counted once in total.

An "Line Item Detail" sheet lists every line item used, and a "Not Placed"
sheet lists anything that could not be put on the grid (month outside
Jan-23..Dec-26, company not found, ...), so totals can be audited.

Requires HUBSPOT_ACCESS_TOKEN with scopes: crm.objects.companies.read,
crm.objects.invoices.read, crm.objects.line_items.read.

Usage: populate_fees.py INPUT.xlsx OUTPUT.xlsx
"""
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import openpyxl
import requests

API = "https://api.hubapi.com"
SHEET = "MRR Rebuild"
FIRST_MONTH_COL = 8  # column H
FEE_ROWS = ["Management Fee", "Marketing Fee", "Bookkeeping Fee", "Other Fee"]
SKIP_STATUSES = {"voided", "draft"}
EASTERN = ZoneInfo("America/New_York")

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9
MONTH_RE = re.compile(
    r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?,?\s+(20\d\d)\b", re.I)

session = requests.Session()
session.headers["Authorization"] = f"Bearer {os.environ['HUBSPOT_ACCESS_TOKEN']}"


def call(method, path, **kw):
    for attempt in range(6):
        r = session.request(method, API + path, timeout=60, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code >= 400:
            sys.exit(f"HubSpot {r.status_code} on {path}: {r.text[:500]}")
        return r.json()
    sys.exit(f"HubSpot kept failing on {path}")


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def associations(from_type, to_type, ids):
    """{from_id: [to_id, ...]} via the v4 batch associations API."""
    out = defaultdict(list)
    for batch in chunks(list(ids), 1000):
        inputs = [{"id": str(i)} for i in batch]
        while inputs:
            data = call("POST", f"/crm/v4/associations/{from_type}/{to_type}/batch/read",
                        json={"inputs": inputs})
            inputs = []
            for res in data.get("results", []):
                fid = res["from"]["id"]
                out[fid].extend(t["toObjectId"] for t in res.get("to", []))
                after = res.get("paging", {}).get("next", {}).get("after")
                if after:
                    inputs.append({"id": fid, "after": after})
    return {k: [str(v) for v in vs] for k, vs in out.items()}


def batch_read(object_type, ids, props):
    out = {}
    for batch in chunks(list(ids), 100):
        data = call("POST", f"/crm/v3/objects/{object_type}/batch/read",
                    json={"properties": props, "inputs": [{"id": i} for i in batch]})
        for res in data.get("results", []):
            out[res["id"]] = res["properties"]
    return out


def parse_ts(value):
    if not value:
        return None
    if value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def category(name):
    n = (name or "").lower()
    if "management" in n:
        return "Management Fee"
    if "marketing" in n:
        return "Marketing Fee"
    if "bookkeep" in n:
        return "Bookkeeping Fee"
    return "Other Fee"


def service_month(li_name, invoice):
    m = MONTH_RE.search(li_name or "")
    if m:
        return (int(m.group(2)), MONTHS[m.group(1).lower()]), "line item name"
    for prop, label in (("hs_invoice_date", "invoice date"), ("hs_createdate", "invoice create date")):
        ts = parse_ts(invoice.get(prop))
        if ts:
            local = ts.astimezone(EASTERN)
            return (local.year, local.month), label
    return None, "no date"


def main(src, dst):
    wb = openpyxl.load_workbook(src)
    ws = wb[SHEET]

    month_cols = {}
    for col in range(FIRST_MONTH_COL, ws.max_column + 1):
        hdr = ws.cell(1, col).value
        if hdr is None:
            continue
        d = hdr if isinstance(hdr, datetime) else datetime.strptime(str(hdr), "%b-%y")
        month_cols[(d.year, d.month)] = col

    facilities = {}  # company id -> {fee name: row}
    for row in range(2, ws.max_row + 1):
        cid = ws.cell(row, 2).value
        if cid is None:
            continue
        cid = str(int(cid))
        rows = {}
        for off in range(1, 5):
            label = ws.cell(row + off, 1).value
            if label in FEE_ROWS:
                rows[label] = row + off
        facilities[cid] = {"name": ws.cell(row, 1).value, "rows": rows}
    print(f"{len(facilities)} facilities on sheet")

    comp_inv = associations("companies", "invoices", facilities)
    inv_ids = sorted({i for v in comp_inv.values() for i in v})
    print(f"{len(inv_ids)} invoices associated")
    invoices = batch_read("invoices", inv_ids, [
        "hs_number", "hs_title", "hs_invoice_date", "hs_createdate",
        "hs_invoice_status", "hs_currency", "hs_amount_billed"])
    live_inv = [i for i in inv_ids
                if (invoices.get(i, {}).get("hs_invoice_status") or "").lower() not in SKIP_STATUSES]
    print(f"{len(live_inv)} invoices after skipping voided/draft")

    inv_li = associations("invoices", "line_items", live_inv)
    li_ids = sorted({i for v in inv_li.values() for i in v})
    print(f"{len(li_ids)} line items")
    line_items = batch_read("line_items", li_ids, [
        "name", "description", "amount", "quantity", "price", "hs_line_item_currency_code"])

    inv_companies = defaultdict(set)
    for cid, inv_list in comp_inv.items():
        for inv_id in inv_list:
            inv_companies[inv_id].add(cid)

    totals = defaultdict(float)  # (cid, fee, (y, m)) -> amount
    detail, not_placed = [], []
    seen_li = set()
    for cid, inv_list in comp_inv.items():
        fac = facilities[cid]
        for inv_id in inv_list:
            inv = invoices.get(inv_id, {})
            if inv_id not in live_inv:
                continue
            share = len(inv_companies[inv_id])
            for li_id in inv_li.get(inv_id, []):
                li = line_items.get(li_id, {})
                full_amount = float(li.get("amount") or 0)
                amount = round(full_amount / share, 2)
                fee = category(li.get("name"))
                ym, source = service_month(li.get("name"), inv)
                inv_ts = parse_ts(inv.get("hs_invoice_date")) or parse_ts(inv.get("hs_createdate"))
                rec = [fac["name"], cid, inv.get("hs_number"), inv_id, inv.get("hs_invoice_status"),
                       inv_ts.astimezone(EASTERN).date() if inv_ts else None,
                       li_id, li.get("name"), li.get("description"), amount,
                       li.get("hs_line_item_currency_code"), fee,
                       f"{ym[0]}-{ym[1]:02d}" if ym else None, source,
                       f"1/{share} of {full_amount:,.2f}" if share > 1 else None]
                if (cid, li_id) in seen_li:
                    not_placed.append(rec + ["duplicate association, skipped"])
                    continue
                seen_li.add((cid, li_id))
                if ym not in month_cols:
                    not_placed.append(rec + ["service month outside sheet range"])
                    continue
                if fee not in fac["rows"]:
                    not_placed.append(rec + ["fee row missing on sheet"])
                    continue
                totals[(cid, fee, ym)] += amount
                detail.append(rec)

    for cid, fac in facilities.items():
        for fee, row in fac["rows"].items():
            for ym, col in month_cols.items():
                val = round(totals.get((cid, fee, ym), 0.0), 2)
                ws.cell(row, col).value = val if val else None
                ws.cell(row, col).number_format = '#,##0.00'

    headers = ["Facility", "Company ID", "Invoice #", "Invoice ID", "Invoice Status", "Invoice Date",
               "Line Item ID", "Line Item Name", "Description", "Amount", "Currency", "Fee Row",
               "Service Month", "Month Source", "Shared Invoice Split"]
    for title, rows, extra in (("Line Item Detail", detail, []),
                               ("Not Placed", not_placed, ["Reason"])):
        if title in wb.sheetnames:
            del wb[title]
        sh = wb.create_sheet(title)
        sh.append(headers + extra)
        for r in rows:
            sh.append(r)
        sh.freeze_panes = "A2"

    wb.save(dst)
    no_inv = [f["name"] for c, f in facilities.items() if not comp_inv.get(c)]
    print(f"placed {len(detail)} line items, {len(not_placed)} not placed, "
          f"{len(no_inv)} facilities with no invoices")
    print(f"saved {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
