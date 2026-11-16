"""Lifecycle Stage Audit for HubSpot portal 45059701 (White Label Storage). READ-ONLY.

Makes only GET requests and read-only search/batch-read POSTs. It never writes to HubSpot.

Rules (v2, agreed 10 Nov 2026):
  1. Every company is Customer (companies are only created once a deal is Closed won).
  2. A contact associated to any company is Customer.
  3. A contact associated to a White Label Storage SALES deal is Opportunity,
     or Customer if that deal is Closed won.
  4. Every other contact is Lead.
Ignored: companies whose name contains "demo" (demo facilities), and contacts linked only to them.

Usage:
  HUBSPOT_ACCESS_TOKEN=... python3 run_audit.py OUT_DIR
Writes OUT_DIR/audit.html (the report page), OUT_DIR/results.json (flagged records and counts),
and the raw pulls under OUT_DIR/data/.
"""
import collections
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
WLS = "79187488"          # White Label Storage SALES pipeline
CW = "150102819"          # Closed won (exists only in the WLS SALES pipeline)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "lifecycle-audit-out")
DATA = os.path.join(OUT, "data")
os.makedirs(DATA, exist_ok=True)
CPROPS = ["firstname", "lastname", "email", "lifecyclestage", "hubspot_owner_id", "num_associated_deals", "createdate"]


def req(method, path, body=None):
    for attempt in range(8):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(BASE + path, data=data, method=method,
                                   headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                time.sleep(2 * (attempt + 1)); continue
            raise RuntimeError(f"{e.code} {path}: {e.read()[:300]}")
        except urllib.error.URLError:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("retries exhausted " + path)


def search(obj, filter_groups, props):
    """Search with hs_object_id windows so result sets above 10k are fully read."""
    out, last_id = [], 0
    while True:
        after, n = None, 0
        fgs = [{"filters": g["filters"] + [{"propertyName": "hs_object_id", "operator": "GT", "value": str(last_id)}]} for g in filter_groups]
        while True:
            body = {"filterGroups": fgs, "properties": props, "limit": 200,
                    "sorts": [{"propertyName": "hs_object_id", "direction": "ASCENDING"}]}
            if after:
                body["after"] = after
            res = req("POST", f"/crm/v3/objects/{obj}/search", body)
            out.extend(res["results"]); n += len(res["results"])
            after = res.get("paging", {}).get("next", {}).get("after")
            time.sleep(0.25)
            if not after or n >= 9800:
                break
        if not after:
            return out
        last_id = int(out[-1]["id"])


def list_all(obj, props):
    out, after = [], None
    while True:
        res = req("GET", f"/crm/v3/objects/{obj}?limit=100&properties={','.join(props)}" + (f"&after={after}" if after else ""))
        out.extend(res["results"])
        after = res.get("paging", {}).get("next", {}).get("after")
        if not after:
            return out


def assoc(frm, to, ids):
    m, ids = {}, list(ids)
    for i in range(0, len(ids), 1000):
        res = req("POST", f"/crm/v4/associations/{frm}/{to}/batch/read", {"inputs": [{"id": str(x)} for x in ids[i:i + 1000]]})
        for r in res.get("results", []):
            m[str(r["from"]["id"])] = [str(t["toObjectId"]) for t in r["to"]]
        time.sleep(0.2)
    return m


def batch_read(obj, ids, props, history=None):
    out, ids = [], list(ids)
    step = 50 if history else 100
    for i in range(0, len(ids), step):
        body = {"inputs": [{"id": str(x)} for x in ids[i:i + step]], "properties": props}
        if history:
            body["propertiesWithHistory"] = history
        out.extend(req("POST", f"/crm/v3/objects/{obj}/batch/read", body)["results"]); time.sleep(0.2)
    return out


def save(name, obj):
    json.dump(obj, open(os.path.join(DATA, name + ".json"), "w"))
    print(f"  {name}: {len(obj)}", flush=True)
    return obj


# ---------- pull ----------
started = datetime.datetime.now(datetime.timezone.utc)
print("Pulling HubSpot data (read-only)...", flush=True)
pipelines = save("pipelines", req("GET", "/crm/v3/pipelines/deals")["results"])
owners, after = [], None
while True:
    res = req("GET", "/crm/v3/owners?limit=100" + (f"&after={after}" if after else ""))
    owners += res["results"]; after = res.get("paging", {}).get("next", {}).get("after")
    if not after:
        break
owners += req("GET", "/crm/v3/owners?limit=100&archived=true")["results"]
save("owners", owners)
deals_raw = save("deals", search("deals", [{"filters": [{"propertyName": "pipeline", "operator": "HAS_PROPERTY"}]}], ["dealname", "pipeline", "dealstage"]))
deal_contacts = save("deal_contacts", assoc("deals", "contacts", [d["id"] for d in deals_raw]))
companies_raw = save("companies", list_all("companies", ["name", "domain", "lifecyclestage", "hubspot_owner_id"]))
deal_companies = save("deal_companies", assoc("deals", "companies", [d["id"] for d in deals_raw]))
company_contacts = save("company_contacts", assoc("companies", "contacts", [c["id"] for c in companies_raw]))
contacts_raw = search("contacts", [{"filters": [{"propertyName": "lifecyclestage", "operator": "IN", "values": ["opportunity", "customer"]}]},
                                   {"filters": [{"propertyName": "lifecyclestage", "operator": "NOT_HAS_PROPERTY"}]}], CPROPS)
have = {c["id"] for c in contacts_raw}
linked = {c for v in deal_contacts.values() for c in v} | {c for v in company_contacts.values() for c in v}
contacts_raw += batch_read("contacts", linked - have, CPROPS)
save("contacts", contacts_raw)

# ---------- evaluate ----------
stage_lbl = {s["id"]: (p["label"], s["label"]) for p in pipelines for s in p["stages"]}
deals = {d["id"]: d["properties"] for d in deals_raw}
owner_name = {str(o["id"]): (o.get("firstName", "") + " " + o.get("lastName", "")).strip() or o.get("email", "") for o in owners}
companies = {c["id"]: c["properties"] for c in companies_raw}
DEMO = {c for c, p in companies.items() if "demo" in (p.get("name") or "").lower()}
c2d = collections.defaultdict(list)
for d, cs in deal_contacts.items():
    for c in cs:
        c2d[c].append(d)
co2d = collections.defaultdict(list)
for d, cos in deal_companies.items():
    for co in cos:
        co2d[co].append(d)
c2co, demo_contacts = collections.defaultdict(list), set()
for co, cs in company_contacts.items():
    for c in cs:
        (demo_contacts.add(c) if co in DEMO else c2co[c].append(co))
LAB = {"customer": "Customer", "opportunity": "Opportunity", "lead": "Lead", "": "(blank)"}


def dsum(ids):
    return [[d, deals[d].get("dealname") or "(no name)", *stage_lbl.get(deals[d]["dealstage"], ("?", "?"))] for d in ids if d in deals]


def expected_contact(cid):
    wls = [d for d in c2d.get(cid, []) if deals.get(d, {}).get("pipeline") == WLS]
    if c2co.get(cid):
        return "customer", "Associated to a company"
    if any(deals[d]["dealstage"] == CW for d in wls):
        return "customer", "Closed won WLS deal"
    if wls:
        return "opportunity", "WLS deal, not Closed won"
    return "lead", "No company, no WLS deal"


contacts = {c["id"]: c["properties"] for c in contacts_raw}
skipped = 0
flag_c, stats = [], collections.Counter()
for cid, p in contacts.items():
    if cid in demo_contacts and not c2co.get(cid):
        skipped += 1
        continue
    cur = p.get("lifecyclestage") or ""
    exp, why = expected_contact(cid)
    stats[f"{cur or 'blank'}>{exp}"] += 1
    if cur != exp:
        flag_c.append({"id": cid, "n": ((p.get("firstname") or "") + " " + (p.get("lastname") or "")).strip() or "(no name)",
                       "e": p.get("email") or "", "o": owner_name.get(p.get("hubspot_owner_id") or "", ""),
                       "cur": LAB[cur], "exp": LAB[exp], "why": why, "cat": f"{cur or 'blank'}>{exp}",
                       "d": dsum(c2d.get(cid, [])), "co": [[c, companies.get(c, {}).get("name") or "(no name)"] for c in c2co.get(cid, [])]})

# A blank stage is usually a contact partway through the lifecycle workflow (it clears, waits 1 minute, then sets).
# Re-read blank contacts after 3 minutes and keep only those still wrong.
blank_ids = [c["id"] for c in flag_c if c["cur"] == "(blank)"]
if blank_ids:
    print(f"Re-checking {len(blank_ids)} blank-stage contacts in 3 minutes...", flush=True)
    time.sleep(180)
    now_stage = {o["id"]: o["properties"].get("lifecyclestage") or "" for o in batch_read("contacts", blank_ids, ["lifecyclestage"])}
    keep = []
    for c in flag_c:
        if c["id"] in now_stage:
            cur = now_stage[c["id"]]
            if LAB.get(cur, cur) == c["exp"]:
                continue
            c["cur"] = LAB.get(cur, cur); c["cat"] = f"{cur or 'blank'}>{c['exp'].lower()}"
            if not cur:
                c["why"] += " · still blank after re-check"
        keep.append(c)
    flag_c = keep

flag_k = []
for cid, p in companies.items():
    cur = p.get("lifecyclestage") or ""
    if cid in DEMO or cur == "customer":
        continue
    flag_k.append({"id": cid, "n": p.get("name") or "(no name)", "e": p.get("domain") or "",
                   "o": owner_name.get(p.get("hubspot_owner_id") or "", ""), "cur": LAB.get(cur, cur), "exp": "Customer",
                   "cat": f"{cur or 'blank'}>customer", "d": dsum(co2d.get(cid, []))})

page = {"C": flag_c, "K": flag_k, "n_contacts": len(contacts) - skipped, "n_companies": len(companies) - len(DEMO),
        "stats": dict(stats)}
json.dump({**page, "run_utc": started.isoformat(), "demo_companies": len(DEMO), "demo_only_contacts": skipped},
          open(os.path.join(OUT, "results.json"), "w"), indent=1)

sast = started.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
html = open(os.path.join(HERE, "template.html")).read()
html = (html.replace("__RUNTIME__", sast.strftime("%-d %b %Y, %H:%M SAST"))
            .replace("__DEMO_CO__", str(len(DEMO))).replace("__DEMO_C__", str(skipped))
            .replace("__DATA__", json.dumps(page, separators=(",", ":")).replace("</", "<\\/")))
open(os.path.join(OUT, "audit.html"), "w").write(html)

print(f"\nDone. Contacts checked: {page['n_contacts']}, flagged: {len(flag_c)} {dict(collections.Counter(c['cat'] for c in flag_c))}")
print(f"Companies checked: {page['n_companies']}, flagged: {len(flag_k)} {dict(collections.Counter(c['cat'] for c in flag_k))}")
print(f"Ignored: {len(DEMO)} demo companies, {skipped} demo-only contacts")
print(f"Report: {os.path.join(OUT, 'audit.html')}")
