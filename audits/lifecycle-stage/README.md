# Lifecycle Stage Audit

Read-only audit of HubSpot contact and company lifecycle stages (portal 45059701). It never writes to HubSpot.

## Rules (v2, agreed 10 Nov 2026)

1. Every company is **Customer**. Companies are only created once a deal is Closed won.
2. A contact associated to any company is **Customer**.
3. A contact associated to a White Label Storage SALES deal is **Opportunity**, or **Customer** if the deal is Closed won.
4. Every other contact is **Lead**.

Ignored: companies whose name contains "demo" (demo facilities), and contacts linked only to them.

## Run

```bash
HUBSPOT_ACCESS_TOKEN=... python3 -I audits/lifecycle-stage/run_audit.py OUT_DIR
```

Output:
- `OUT_DIR/audit.html` is the report page that gets published to the Lifecycle Stage Audit artifact.
- `OUT_DIR/results.json` holds the flagged records and counts.
- `OUT_DIR/data/` holds the raw pulls.

A blank lifecycle stage is usually a contact partway through the "Set Lifecycle Stage on Contact" workflow, which clears the stage, waits a minute, then sets it. The script re-reads blank contacts after 3 minutes and keeps only those still wrong.

Schedule: monthly on the 1st at 07:33 SAST (scheduled task "Monthly Lifecycle Stage Audit").
