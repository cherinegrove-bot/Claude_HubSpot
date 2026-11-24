# Marketing Service Task Audit

Audit report (update this same artifact on every run, pass it as `url`):
https://claude.ai/artifact/L9dPacsR7oH9nGXdWRV6KS

Read-only. Never edit HubSpot or the Google Sheet from this audit.

## Inputs
- Workflows: 1892165928 (At Risk), 1892196753 (Improving), 1892197644 (Standalone),
  1892197744 (Google Ads PPC), 1934717342 (Suppression). Suppression list: 5466.
- Sheet: 1cy2Gme0RNjxOqB4d-a2HZRSWu_rd7R-C4gaYyIsn5Es (Task Matrix, Master & Subtasks,
  Checklist Detail, Legend & Ownership).
- Related: 1855066380 (stamps ticket last_review_date on task completion by title).

## Run
Needs HUBSPOT_ACCESS_TOKEN. Run from a scratch dir with these scripts copied in:
1. `python3 summ.py <flow>.json ...` – workflow tree summary (download via GET /automation/v4/flows/{id}).
2. `python3 -I step1.py` – existing review/PPC tasks, subtasks, associations -> existing_tasks.json
3. `python3 -I step2.py` – live companies, Marketing tickets, list 5466 -> companies.json
4. `python3 -I step3.py` – eligibility + data checks -> rows.json
5. `python3 -I build_report.py rows.json out.html template.html` – then publish to the URL above.
Findings text lives in template.html; update it and the Run history table each run.
