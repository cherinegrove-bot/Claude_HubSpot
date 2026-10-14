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
  * Month: the invoice date (America/New_York, as HubSpot shows it), falling
    back to the invoice create date. Every line on an invoice counts in the
    invoice's month, whatever month its name mentions.
  * Voided and draft invoices are skipped.
  * Amount = line item `amount` (net of discounts). An invoice associated
    with several facilities on the sheet (one bill for sister sites) is
    split evenly across them, so it is counted once in total.

An "Line Item Detail" sheet lists every line item used, and a "Not Placed"
sheet lists anything that could not be put on the grid (month outside
the sheet's columns, ...), so totals can be audited. Month columns are
extended back to FIRST_MONTH if the template starts later.

Requires HUBSPOT_ACCESS_TOKEN with scopes: crm.objects.companies.read,
crm.objects.invoices.read, crm.objects.line_items.read.

Usage: populate_fees.py INPUT.xlsx OUTPUT.xlsx
"""
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import openpyxl
import openpyxl.worksheet.cell_range
from openpyxl.formatting.formatting import ConditionalFormattingList
import requests
from openpyxl.utils import get_column_letter

API = "https://api.hubapi.com"
SHEET = "MRR Rebuild"
FIRST_MONTH_COL = 8  # column H
FIRST_MONTH = (2022, 11)  # earliest Stripe invoice
FEE_ROWS = ["Management Fee", "Marketing Fee", "Bookkeeping Fee", "Other Fee", "Setup Fee", "Reimbursements"]
BLOCK = len(FEE_ROWS) + 1  # facility header row + one row per fee type
SKIP_STATUSES = {"voided", "draft"}
EASTERN = ZoneInfo("America/New_York")
# Companies billed by WLS that are not in the template's facility list. Each gets its own
# block at the bottom, in this order. Storage of America Corporate holds the single
# invoice for all 29 SOA sites; the rest were found missing in the Oct-2026 billing audit.
EXTRA_COMPANIES = {
    "35011152532": "Storage of America Corporate",
    "37546862173": "Cedar Ridge Storage",
    "51746202741": "Jeffersonville Self Storage",
    "29898594177": "Owl - Columbia, I-70",
    "26153654402": "Owl - Columbia, MO",
    "26153654411": "Owl - Eldon, MO",
    "26153654421": "Owl - Kankakee, IL",
    "30378020928": "Owl - Kansas City - E210",
    "26153654433": "Owl - Laurie, MO",
    "26154927786": "Owl - Macomb, IL",
    "30378020940": "Owl - Park City - Broadway",
    "30378020946": "Owl - Rose Hill - Berry",
    "30379620984": "Owl - Rose Hill - Rosewood",
    "40708349233": "Pope Storage - Pangborn Blvd",
    "55595327037": "River Town Storage",
    "26154884974": "Sam's Storage",
}

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


# Pass-through costs billed back to the facility. Checked after the management /
# marketing / bookkeeping / setup words, so "Mgmt Fee (...net tenant protection)" stays
# a management fee, but before Other Fee, which is for WLS revenue only.
REIMBURSEMENT_RE = re.compile(r"""reimb|burkholder|sparefoot|storage\s*reach|ai\s*lean|auction|lockerfox
    |davinci|\block(s|box)?\b|hasps|sign|flag\ order|\bbog\b|boots\ on
    |payroll|jordan|ring\s*central|aircall|phone|comcast|wix|godaddy|domain|siteground|hosting
    |google\ ads|workspace|business\ email|landscap|mowing|septic|dumpster|equipment\ rental|supplies
    |packaging|amazon|sherwin|storable|opentech|checkr|background\ check|spiderdoor|city\ of
    |citypay|fire\ marshall|door\ repair|site\ work|photos|air\ comfort|palmetto|ender\ services
    |loomis|printing|on-?\s*site\ service|eddm|maintenance|micro\ deposit|payment\ (re)?capture""", re.I | re.X)


def category(name):
    """Fee row for a line item name. Other Fee is WLS revenue that is not management,
    marketing, bookkeeping or setup (website fees, call center, Insight PG, referral fees,
    late fees, Tenant Protection revenue share); costs passed through to the facility go to
    Reimbursements."""
    n = (name or "").lower()
    if "reimb" in n or "burkholder" in n:
        return "Reimbursements"
    if re.search(r"set\s*-?\s*up", n):
        return "Setup Fee"
    if re.search(r"management|mgmt|mgmnt", n):
        return "Management Fee"
    if re.search(r"marketing|mkting", n):
        return "Marketing Fee"
    if re.search(r"bookkeep|\bbooks\b|\bbk fee|accounting", n):
        return "Bookkeeping Fee"
    if REIMBURSEMENT_RE.search(n):
        return "Reimbursements"
    return "Other Fee"


def local_day(ts):
    """Calendar day a HubSpot invoice date stands for. Two storage styles occur:
    a plain date as midnight UTC (2026-04-01T00:00:00Z = Apr 1), and midnight Eastern
    minus 1 ms (2026-04-01T03:59:59.999Z = Apr 1, not Mar 31 23:59). Other timestamps
    are read in Eastern time."""
    if ts.hour == ts.minute == ts.second == ts.microsecond == 0 and ts.utcoffset().total_seconds() == 0:
        return ts.date()
    return (ts + timedelta(milliseconds=1)).astimezone(EASTERN).date()


def invoice_day(invoice):
    for prop, label in (("hs_invoice_date", "invoice date"), ("hs_createdate", "invoice create date")):
        ts = parse_ts(invoice.get(prop))
        if ts:
            return local_day(ts), label
    return None, "no date"


def invoice_month(invoice):
    day, label = invoice_day(invoice)
    return ((day.year, day.month) if day else None), label


def expand_blocks(ws):
    """Give every facility block one row per FEE_ROWS entry: rows missing from an older
    template (Setup Fee, Reimbursements) are inserted under the block's last fee row,
    styled like it. Header-row highlight rules and dropdowns are re-pointed at the new
    block size."""
    headers = [r for r in range(2, ws.max_row + 1) if ws.cell(r, 2).value is not None]
    for top in reversed(headers):
        labels = []
        r = top + 1
        while r <= ws.max_row and ws.cell(r, 2).value is None and ws.cell(r, 1).value in FEE_ROWS:
            labels.append(ws.cell(r, 1).value)
            r += 1
        missing = [f for f in FEE_ROWS if f not in labels]
        if not missing:
            continue
        last = top + len(labels)
        ws.insert_rows(last + 1, len(missing))
        for i, label in enumerate(missing, 1):
            for col in range(1, ws.max_column + 1):
                ws.cell(last + i, col)._style = ws.cell(last, col)._style
            ws.cell(last + i, 1, label)
    headers = [r for r in range(2, ws.max_row + 1) if ws.cell(r, 2).value is not None]
    old_cf, ws.conditional_formatting = ws.conditional_formatting, ConditionalFormattingList()
    for cf in old_cf:
        for rule in cf.rules:
            rule.formula = [re.sub(r"MOD\(ROW\(\)-2,\d+\)", f"MOD(ROW()-2,{BLOCK})", f) for f in rule.formula]
            ws.conditional_formatting.add(re.sub(r"\d+$", str(ws.max_row), str(cf.sqref)), rule)
    for dv in ws.data_validations.dataValidation:
        col = str(dv.sqref).split()[0].rstrip("0123456789")
        dv.sqref = openpyxl.worksheet.cell_range.MultiCellRange(" ".join(f"{col}{r}" for r in headers))


def add_company_blocks(ws, companies=EXTRA_COMPANIES):
    """Append a facility block for each {company id: name} not already on the sheet,
    styled like the last block. Header-row SUM formulas come from extend_months."""
    on_sheet = {str(int(v)) for v in (ws.cell(r, 2).value for r in range(2, ws.max_row + 1)) if v}
    for cid, name in companies.items():
        if cid in on_sheet:
            continue
        top = ws.max_row + 1
        for off in range(BLOCK):
            for col in range(1, ws.max_column + 1):
                ws.cell(top + off, col)._style = ws.cell(top - BLOCK + off, col)._style
        ws.cell(top, 1, name)
        ws.cell(top, 2, int(cid))
        for off, label in enumerate(FEE_ROWS, 1):
            ws.cell(top + off, 1, label)


def extend_months(ws, first=FIRST_MONTH):
    """Insert month columns in front of the first one so the grid starts at `first`,
    and (re)write every header-row SUM formula."""
    hdr = ws.cell(1, FIRST_MONTH_COL).value
    start = hdr if isinstance(hdr, datetime) else datetime.strptime(str(hdr), "%b-%y")
    missing = (start.year - first[0]) * 12 + start.month - first[1]
    if missing > 0:
        ws.insert_cols(FIRST_MONTH_COL, missing)
        for i in range(missing):
            y, m = divmod(first[1] - 1 + i, 12)
            cell = ws.cell(1, FIRST_MONTH_COL + i, datetime(first[0] + y, m + 1, 1))
            cell._style = ws.cell(1, FIRST_MONTH_COL + missing)._style
            cell.number_format = "mmm-yy"
    for row in range(2, ws.max_row + 1):
        if ws.cell(row, 2).value is None:
            continue
        for col in range(FIRST_MONTH_COL, ws.max_column + 1):
            letter = get_column_letter(col)
            ws.cell(row, col).value = f"=SUM({letter}{row + 1}:{letter}{row + len(FEE_ROWS)})"
            ws.cell(row, col)._style = ws.cell(row, FIRST_MONTH_COL + max(missing, 0))._style


def refresh_lost_dates(ws, facilities):
    """Column G (Lost Date) <- the Company's System Lost Date. Returns {name: (old, new)} for changes."""
    props = batch_read("companies", list(facilities), ["system_lost_date"])
    changes = {}
    for cid, fac in facilities.items():
        raw = (props.get(cid) or {}).get("system_lost_date")
        new = datetime.strptime(raw[:10], "%Y-%m-%d") if raw else None
        cell = ws.cell(fac["row"], 7)
        old = cell.value
        if (old.date() if old else None) != (new.date() if new else None):
            changes[fac["name"]] = (old.date() if old else None, new.date() if new else None)
        cell.value = new
        cell.number_format = "yyyy-mm-dd"
    return changes


def month_columns(ws):
    month_cols = {}
    for col in range(FIRST_MONTH_COL, ws.max_column + 1):
        hdr = ws.cell(1, col).value
        if hdr is None:
            continue
        d = hdr if isinstance(hdr, datetime) else datetime.strptime(str(hdr), "%b-%y")
        month_cols[(d.year, d.month)] = col
    return month_cols


def read_facilities(ws):
    """{company id: {"name": ..., "row": header row, "rows": {fee name: row}}}"""
    facilities = {}
    for row in range(2, ws.max_row + 1):
        cid = ws.cell(row, 2).value
        if cid is None:
            continue
        rows = {}
        for off in range(1, len(FEE_ROWS) + 1):
            label = ws.cell(row + off, 1).value
            if label in FEE_ROWS:
                rows[label] = row + off
        facilities[str(int(cid))] = {"name": ws.cell(row, 1).value, "row": row, "rows": rows}
    return facilities


def fetch_hubspot_lines(facilities):
    """Every line item on the facilities' live invoices, one record per (facility, line item).

    An invoice associated with several facilities is split evenly across them.
    """
    comp_inv = associations("companies", "invoices", facilities)
    inv_ids = sorted({i for v in comp_inv.values() for i in v})
    print(f"{len(inv_ids)} invoices associated")
    invoices = batch_read("invoices", inv_ids, [
        "hs_number", "hs_title", "hs_invoice_date", "hs_createdate",
        "hs_invoice_status", "hs_currency", "hs_amount_billed", "hs_invoice_source", "hs_exchange_rate"])
    live_inv = {i for i in inv_ids
                if (invoices.get(i, {}).get("hs_invoice_status") or "").lower() not in SKIP_STATUSES}
    print(f"{len(live_inv)} invoices after skipping voided/draft")

    inv_li = associations("invoices", "line_items", sorted(live_inv))
    li_ids = sorted({i for v in inv_li.values() for i in v})
    print(f"{len(li_ids)} line items")
    line_items = batch_read("line_items", li_ids, [
        "name", "description", "amount", "quantity", "price", "hs_line_item_currency_code"])

    inv_companies = defaultdict(set)
    for cid, inv_list in comp_inv.items():
        for inv_id in inv_list:
            inv_companies[inv_id].add(cid)

    lines, seen = [], set()
    for cid, inv_list in comp_inv.items():
        for inv_id in inv_list:
            if inv_id not in live_inv:
                continue
            inv = invoices.get(inv_id, {})
            share = len(inv_companies[inv_id])
            inv_day, _ = invoice_day(inv)
            for li_id in inv_li.get(inv_id, []):
                if (cid, li_id) in seen:
                    continue
                seen.add((cid, li_id))
                li = line_items.get(li_id, {})
                rate = usd_rate(inv)
                full_amount = round(float(li.get("amount") or 0) * rate, 2)
                ym, source = invoice_month(inv)
                lines.append({
                    "cid": cid, "facility": facilities[cid]["name"],
                    "invoice_number": inv.get("hs_number"), "invoice_id": inv_id,
                    "invoice_status": inv.get("hs_invoice_status"),
                    "invoice_source": inv.get("hs_invoice_source"),
                    "invoice_total": round(float(inv.get("hs_amount_billed") or 0) * rate, 2),
                    "invoice_date": inv_day,
                    "line_id": li_id, "line_name": li.get("name"), "description": li.get("description"),
                    "amount": round(full_amount / share, 2), "full_amount": full_amount, "share": share,
                    "currency": "USD" if rate == 1 else f"USD (from {inv.get('hs_currency')} at {rate})",
                    "fee": category(li.get("name")), "ym": ym, "month_source": source,
                })
    lines += invoice_adjustments(lines)
    no_inv = [f["name"] for c, f in facilities.items() if not comp_inv.get(c)]
    return lines, no_inv


def usd_rate(invoice):
    """Factor that turns an invoice's amounts into USD: 1 for USD invoices; for others
    (Simple Storage Moncton and Bouctouche bill in CAD) HubSpot's own exchange rate on the
    invoice, the same one it uses for 'amount billed in company currency'."""
    if (invoice.get("hs_currency") or "USD").upper() == "USD":
        return 1.0
    return float(invoice["hs_exchange_rate"])


def invoice_adjustments(lines):
    """One extra line per facility for invoices whose billed total differs from the sum of
    their line items: order-level discounts (negative) and fees such as late fees (positive)
    sit on the invoice, not on a line. A discount whose label names a fee type ("AI Lean
    Refund") goes to that row; any other discount goes to the Management Fee row when the
    invoice has one (else the row of its largest line). Fees go to Other Fee."""
    by_inv = defaultdict(list)
    for ln in lines:
        by_inv[ln["invoice_id"]].append(ln)
    labels = {}
    ids = [i for i, ls in by_inv.items() if abs(_gap(ls)) > 0.005]
    for kind in ("discounts", "fees"):
        assoc = associations("invoices", kind, ids) if ids else {}
        objs = batch_read(kind, sorted({o for v in assoc.values() for o in v}), ["hs_label"])
        for inv_id, obj_ids in assoc.items():
            labels.setdefault((inv_id, kind), []).extend(objs.get(o, {}).get("hs_label") or kind for o in obj_ids)
    out = []
    for inv_id in ids:
        ls = by_inv[inv_id]
        gap = _gap(ls)
        if gap < 0:
            kind, objs = "Invoice discount", "discounts"
            named = {category(lbl) for lbl in labels.get((inv_id, objs), [])} - {"Other Fee"}
            fees = {ln["fee"] for ln in ls}
            if len(named) == 1:  # e.g. "AI Lean Refund", "Marketing Fee Refund"
                fee = named.pop()
            else:
                fee = "Management Fee" if "Management Fee" in fees else max(ls, key=lambda x: x["full_amount"])["fee"]
        else:
            fee, kind, objs = "Other Fee", "Invoice fee", "fees"
        name = f"{kind}: {', '.join(labels.get((inv_id, objs), [])) or 'not itemised'}"
        for cid in sorted({ln["cid"] for ln in ls}):
            first = next(ln for ln in ls if ln["cid"] == cid)
            out.append({**first, "line_id": f"adj-{inv_id}", "line_name": name, "description": None,
                        "amount": round(gap / first["share"], 2), "full_amount": gap, "fee": fee})
    return out


def _gap(invoice_lines):
    """Billed total minus the sum of the invoice's line items (each line counted once)."""
    seen = {ln["line_id"]: ln["full_amount"] for ln in invoice_lines}
    return round(invoice_lines[0]["invoice_total"] - sum(seen.values()), 2)


def write_grid(ws, facilities, month_cols, totals):
    """Fill the fee rows from {(cid, fee, (y, m)): amount}; header-row formulas are untouched."""
    for cid, fac in facilities.items():
        for fee, row in fac["rows"].items():
            for ym, col in month_cols.items():
                val = round(totals.get((cid, fee, ym), 0.0), 2)
                ws.cell(row, col).value = val if val else None
                ws.cell(row, col).number_format = '#,##0.00'


def place(lines, facilities, month_cols):
    """Sum lines onto the grid. Returns (totals, placed, not_placed[(line, reason)])."""
    totals = defaultdict(float)
    placed, not_placed = [], []
    for ln in lines:
        if ln["ym"] not in month_cols:
            not_placed.append((ln, "service month outside sheet range"))
        elif ln["fee"] not in facilities[ln["cid"]]["rows"]:
            not_placed.append((ln, "fee row missing on sheet"))
        else:
            totals[(ln["cid"], ln["fee"], ln["ym"])] += ln["amount"]
            placed.append(ln)
    return totals, placed, not_placed


def write_table(wb, title, headers, rows):
    if title in wb.sheetnames:
        del wb[title]
    sh = wb.create_sheet(title)
    sh.append(headers)
    for r in rows:
        sh.append(r)
    sh.freeze_panes = "A2"
    return sh


HS_DETAIL_HEADERS = ["Facility", "Company ID", "Invoice #", "Invoice ID", "Invoice Status", "Invoice Date",
                     "Line Item ID", "Line Item Name", "Description", "Amount", "Currency", "Fee Row",
                     "Service Month", "Month Source", "Shared Invoice Split"]


def hs_detail_row(ln):
    ym = ln["ym"]
    return [ln["facility"], ln["cid"], ln["invoice_number"], ln["invoice_id"], ln["invoice_status"],
            ln["invoice_date"], ln["line_id"], ln["line_name"], ln["description"], ln["amount"],
            ln["currency"], ln["fee"], f"{ym[0]}-{ym[1]:02d}" if ym else None, ln["month_source"],
            f"1/{ln['share']} of {ln['full_amount']:,.2f}" if ln["share"] > 1 else None]


def main(src, dst):
    wb = openpyxl.load_workbook(src)
    ws = wb[SHEET]
    expand_blocks(ws)
    add_company_blocks(ws)
    extend_months(ws)
    month_cols = month_columns(ws)
    facilities = read_facilities(ws)
    print(f"{len(facilities)} facilities on sheet")

    lines, no_inv = fetch_hubspot_lines(facilities)
    totals, placed, not_placed = place(lines, facilities, month_cols)
    write_grid(ws, facilities, month_cols, totals)
    write_table(wb, "Line Item Detail", HS_DETAIL_HEADERS, [hs_detail_row(ln) for ln in placed])
    write_table(wb, "Not Placed", HS_DETAIL_HEADERS + ["Reason"],
                [hs_detail_row(ln) + [why] for ln, why in not_placed])

    wb.save(dst)
    print(f"placed {len(placed)} line items, {len(not_placed)} not placed, "
          f"{len(no_inv)} facilities with no invoices")
    print(f"saved {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
