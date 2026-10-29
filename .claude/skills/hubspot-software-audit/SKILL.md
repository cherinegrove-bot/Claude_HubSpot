---
name: hubspot-software-audit
description: Monthly HubSpot Software Audit. Checks that a Deal's "Current Mgmt Software" agrees with its "Prior Software", that a Company's "Current Software (at onboarding)" agrees with its "Prior Software", and that each Company's Prior Software matches its associated Deals' Prior Software, then delivers an XLSX of mismatches and blanks. Use this whenever the user asks to run, rerun or schedule the software audit, or to check/verify/compare prior software, current software, management software or FMS fields between deals and companies in HubSpot, even if they don't call it an "audit".
---

# HubSpot Software Audit

Three checks, all read-only in HubSpot:

1. **Deal check**: Deal `current_mgmt_software` (free text, label "Current Mgmt Software") vs Deal `prior_software` (dropdown, label "Prior Software").
2. **Company check**: Company `previous_software` (free text, label "Current Software (at onboarding)", which the team calls "Software at Onboard") vs Company `prior_software` (dropdown).
3. **Company vs Deal**: Company `prior_software` vs the `prior_software` of each associated Deal (both dropdowns, so it's an exact compare).

The text fields are free-form ("storedge", "Storable Edge", "ESS", "n/a"), so they have to be mapped to the dropdown options before comparing. `scripts/software_audit.py` holds that mapping, along with the parsing and the workbook build, so every month is judged by the same rules. Don't redo the matching by hand. If you think the rules are wrong, change the script.

## Steps

### 1. Confirm the property names still exist
Run `search_properties` on COMPANY and DEAL for `prior_software`, `previous_software` and `current_mgmt_software`. If one has been renamed or removed, stop and tell the user rather than guessing. Also run `get_properties` on `prior_software` and compare its options to the `VENDORS` list in the script. If a new dropdown option has been added (a new vendor), add a pattern for it to `VENDORS` before running. Otherwise the new vendor's text will be classed as "Other" and show up as false mismatches.

### 2. Pull the field values with `search_crm_objects` (live)
**Don't take field values from `query_crm_data` (SQL).** It reads a copy of the CRM that can be hours behind. On 2026-10-29 it still showed 986 deals with empty Prior Software after the team had filled in about 500 of them. `search_crm_objects` reads the live records.

Deals: two filter groups (OR), sorted so the pages don't shift:
```
objectType: DEAL, limit: 200, offset: 0, 200, 400, ...
filterGroups: [{filters:[{propertyName:"current_mgmt_software", operator:"HAS_PROPERTY"}]},
               {filters:[{propertyName:"prior_software", operator:"HAS_PROPERTY"}]}]
properties: ["dealname","pipeline","dealstage","current_mgmt_software","prior_software"]
sorts: [{propertyName:"hs_object_id", direction:"ASCENDING"}]
```
Companies: the same with `objectType: COMPANY`, `previous_software` in place of `current_mgmt_software`, and `properties: ["name","previous_software","prior_software"]`.

- Every page reports `total`. Keep paging until offset + 200 ≥ total, and pass the totals to the script as `--expect-deals` / `--expect-companies`. If it loads fewer, it warns you, so a missing page can't pass for a clean result.
- A full page is saved to a file automatically (the message gives the path), and that path is the script input. The **last, short page usually comes back inline instead**. Rather than retyping it, request a full 200-row page that ends at the total (offset = total − 200). It overlaps the previous page, which is fine because the script removes duplicates by ID.

### 3. Pull the deal–company links with `query_crm_data`
Call `tool_guidance` for `query_crm_data` first if it hasn't been called this session, because the tool requires it. Search doesn't return associations, so get them, plus pipeline and stage names, from one SQL join (verbosityLevel LOW):
```sql
SELECT hs_object_id, dealname, dealstage, pipeline, COMPANY.hs_object_id FROM DEAL
WHERE current_mgmt_software IS NOT NULL OR prior_software IS NOT NULL LIMIT 2000
```
This returns one row per deal–company pair; last time that was about 1,400 rows, all returned. Because the SQL copy lags, very new deals or links may be missing; the script warns how many deals it couldn't find here. Don't add `COMPANY.prior_software` to this query: its column would have the same header as the deal's Prior Software, and the two would be indistinguishable.

### 4. Run the script
```bash
python3 scripts/software_audit.py \
  --companies <company search page files> --deals <deal search page files> \
  --deal-links <SQL join file> \
  --expect-companies <company total> --expect-deals <deal total> \
  --out <outputs dir>/Software_Audit_<YYYY-MM-DD>.xlsx
```
It needs `openpyxl` (`pip install openpyxl` if missing). It prints a JSON summary with counts per check, a breakdown by pipeline, any records containing logins, and warnings. If there are warnings, resolve them (usually by pulling the missing page) before reporting.

If the user says records have been fixed but the report still shows them as wrong, read a few of them directly with `get_crm_objects` and compare. A difference means some input came from a delayed source.

Save the workbook to the user's outputs folder or scratchpad, **not inside a git repository**. It contains customer data, and committing it would spread that data.

### 5. Report
Send the XLSX with the file-delivery tool. Then give a short chat summary:
- A table for each check: Match / Mismatch / Close / Review / blanks. Bold the mismatches.
- The biggest problem area, e.g. which pipeline holds most of the blank Prior Software.
- The most common mismatch pattern (look at the Interpreted As vs Prior Software columns in the Mismatch rows).
- **Login details**: if `records_with_logins` isn't empty, list those records and tell the user that passwords are typed into HubSpot fields and should be moved to the password manager. Never repeat the credential values anywhere: not in chat, not in the workbook, not in a summary. The script already redacts them in the file.
- If last month's numbers are available (e.g. the user shares the last report), note whether mismatches and blanks went up or down.

## The workbook
- **Summary**: counts for each check, the records with logins, and how text was matched.
- **1 Deal Check**, **2 Company Check**, **3 Company vs Deal**: one row per record or pair. Problems are sorted first and the Result cell is colour-coded. Each sheet has filters and frozen headers.

## How results are judged (and why)
- **Match / Mismatch**: the interpreted text equals or differs from the dropdown value.
- **Close**: Tenant Inc vs Hummingbird. Hummingbird is Tenant Inc's product, so this is usually a labelling choice, not a data error.
- **Review**: the text is "unknown", a bare "Storable" (that could be StorEDGE, Sitelink or ESS), or names several softwares. A person has to decide which is right, so these aren't counted as mismatches.
- **Blank**: one side is empty. These are often the biggest problem in absolute numbers, so report them; don't skip them.
- Future plans ("will be StorEdge", "moving to StorEDGE") are stripped before matching, so the software the facility is using now is what gets compared.
- Excel, pen and paper, "n/a" and "new build" count as **None**. Software that isn't a dropdown option (Storage Commander, Syrasoft, 6Storage, CubeSmart, etc.) counts as **Other**.
