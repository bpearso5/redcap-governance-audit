"""Build the REDCap request tracker and audit corrective-action workbook.

Reads data/audit_findings.csv (from run_checks.py). Synthetic data only.
Run: python3 scripts/build_workbook.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

random.seed(7)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "workbook" / "REDCap_Request_Tracker_and_Access_Audit.xlsx"
AS_OF = date(2026, 3, 31)
MAX = 200

FONT = "Arial"
thin = Side(style="thin", color="808080")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEAD_FILL, HEAD_FONT = PatternFill("solid", fgColor="000000"), Font(name=FONT, bold=True, color="FFFFFF", size=10)
BODY = Font(name=FONT, size=10)
GRAY = PatternFill("solid", fgColor="D9D9D9")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top", wrap_text=True)

wb = Workbook()


def title(ws, t, sub):
    ws["A1"], ws["A2"] = t, sub
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    ws["A2"].font = Font(name=FONT, italic=True, size=9, color="595959")


def table(ws, headers, widths, rows, formulas=None, center=()):
    formulas = formulas or {}
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        x = ws.cell(row=4, column=c, value=h)
        x.font, x.fill, x.border = HEAD_FONT, HEAD_FILL, BORDER
        x.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[4].height = 30
    for r in range(5, 5 + MAX):
        data = rows[r - 5] if r - 5 < len(rows) else None
        for c in range(1, len(headers) + 1):
            x = ws.cell(row=r, column=c)
            if c in formulas:
                x.value = formulas[c](r)
                x.fill = GRAY
            elif data is not None and c - 1 < len(data):
                x.value = data[c - 1]
            x.font, x.border = BODY, BORDER
            x.alignment = CENTER if (c in center or c in formulas) else WRAP
            if isinstance(x.value, date):
                x.number_format = "dd-mmm-yy"
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{4 + len(rows)}"


def dropdown(ws, col, opts):
    dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{col}5:{col}{4 + MAX}")


def datefmt(ws, cols):
    for col in cols:
        for r in range(5, 5 + MAX):
            ws[f"{col}{r}"].number_format = "dd-mmm-yy"


# ---------------------------------------------------------------- Read Me
ws = wb.active
ws.title = "Read Me"
title(ws, "REDCap Request Tracker & Access Audit", "Synthetic work sample. All people, projects, and data are invented.")
guide = [
    ("What this is", "Two working tools for a REDCap administration team: an intake-to-resolution request "
                     "tracker with service-level targets, and a corrective-action tracker for findings from the "
                     "SQL access audit (sql/access_audit_checks.sql)."),
    ("As-of date", "Summary!B4. Open-request ageing and overdue flags calculate from it."),
    ("Cells you edit", "White cells. Use the dropdowns for request type, priority, status, and finding status."),
    ("Cells you don't edit", "Gray columns are formulas (business days, SLA target, SLA met, age, overdue). "
                             "They extend to row 204."),
    ("SLA targets", "Set per request type on the SLA Targets tab. Change a target there and every request "
                    "re-scores."),
    ("Audit findings", "Each row is one record flagged by a SQL check. Findings close only when the fix is "
                       "verified by re-running the check."),
    ("Example row", "REQ-001 on the Requests tab shows the expected level of detail."),
]
ws["A4"], ws["B4"] = "Topic", "Guidance"
for c in ("A4", "B4"):
    ws[c].font, ws[c].fill, ws[c].border = HEAD_FONT, HEAD_FILL, BORDER
for i, (k, v) in enumerate(guide, 5):
    ws.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True, size=10)
    ws.cell(row=i, column=2, value=v).font = BODY
    for c in (1, 2):
        ws.cell(row=i, column=c).border, ws.cell(row=i, column=c).alignment = BORDER, WRAP
ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 22, 95
ws.sheet_view.showGridLines = False

# ---------------------------------------------------------------- SLA Targets
sla = wb.create_sheet("SLA Targets")
title(sla, "SLA Targets", "Business days from received to resolved, by request type.")
TYPES = [("New project setup", 5), ("Add user / change rights", 2), ("Remove user (offboarding)", 1),
         ("Move to production", 3), ("Alert or survey setup", 3), ("Data export request", 2),
         ("Training / how-to", 3), ("Bug or error report", 2)]
table(sla, ["Request type", "Target (business days)", "Why this target"], [30, 14, 60],
      [(t, n, w) for (t, n), w in zip(TYPES, [
          "Requires design review and a documentation check before build.",
          "Blocks the requester's work; rights follow the role matrix.",
          "Security control: access must end within 1 business day of separation.",
          "Requires a pre-production checklist and owner sign-off.",
          "Routing must be tested with the project owner.",
          "Identifiable exports need owner approval.",
          "Usually answered with an existing guide or walkthrough.",
          "Triage within 1 day; most resolve with configuration fixes."])],
      center=(2,))
sla.freeze_panes = "A5"
sla.auto_filter.ref = None

# ---------------------------------------------------------------- Requests
rq = wb.create_sheet("Requests")
title(rq, "Request Tracker", "Intake to resolution. Business days and SLA status are formulas.")
UNITS = ["Surveillance", "Epidemiology", "Immunization", "Lab Liaison", "Informatics", "Program Evaluation"]
NOTES = {
    "New project setup": "Reviewed data dictionary; built in Development; owner trained.",
    "Add user / change rights": "Rights set per role matrix; owner approval on file.",
    "Remove user (offboarding)": "Account suspended; rights removed on all projects; alerts re-routed.",
    "Move to production": "Pre-production checklist complete; owner sign-off received.",
    "Alert or survey setup": "Alert built and test message confirmed by owner.",
    "Data export request": "De-identified export approved by project owner.",
    "Training / how-to": "Sent knowledge-base article and Scribe walkthrough.",
    "Bug or error report": "Branching logic error corrected; owner confirmed fix.",
}
reqs = []
start = date(2026, 1, 5)
for i in range(1, 49):
    t, target = random.choice(TYPES)
    recv = start + timedelta(days=random.randint(0, 80))
    while recv.weekday() > 4:
        recv += timedelta(days=1)
    pr = random.choice(["High", "Normal", "Normal", "Low"]) if not t.startswith("Remove") else "High"
    took = max(0, target + random.choice([-1, -1, 0, 0, 0, 1, 2, 4]))
    resolved = recv
    added = 0
    while added < took:
        resolved += timedelta(days=1)
        if resolved.weekday() < 5:
            added += 1
    status = "Resolved" if resolved <= AS_OF - timedelta(days=2) else random.choice(["In Progress", "Waiting on Requester"])
    reqs.append([f"REQ-{i:03d}", recv, random.choice(UNITS), t, pr,
                 random.choice(["Admin A", "Admin B", "Admin C"]), status,
                 resolved if status == "Resolved" else None, NOTES[t] if status == "Resolved" else "In progress.",
                 None, None, None, None])
reqs.sort(key=lambda r: r[1])
for i, r in enumerate(reqs, 1):
    r[0] = f"REQ-{i:03d}"
headers = ["Request ID", "Received", "Unit", "Request type", "Priority", "Assigned to", "Status", "Resolved",
           "Resolution notes", "Business days", "SLA target", "SLA met?", "Overdue (open)?"]
table(rq, headers, [10, 11, 16, 26, 9, 12, 16, 11, 48, 10, 9, 9, 11], reqs,
      formulas={
          10: lambda r: f'=IF(B{r}="","",IF(H{r}<>"",NETWORKDAYS(B{r},H{r})-1,NETWORKDAYS(B{r},Summary!$B$4)-1))',
          11: lambda r: f"=IF(D{r}=\"\",\"\",IFERROR(INDEX('SLA Targets'!$B$5:$B$12,"
                        f"MATCH(D{r},'SLA Targets'!$A$5:$A$12,0)),\"\"))",
          12: lambda r: f'=IF(OR(H{r}="",K{r}=""),"",IF(J{r}<=K{r},"Yes","No"))',
          13: lambda r: f'=IF(OR(B{r}="",G{r}="Resolved",K{r}=""),"",IF(J{r}>K{r},"Overdue",""))'},
      center=(1, 2, 5, 7, 8))
dropdown(rq, "D", [t for t, _ in TYPES])
dropdown(rq, "E", ["High", "Normal", "Low"])
dropdown(rq, "G", ["New", "In Progress", "Waiting on Requester", "Resolved"])
datefmt(rq, "BH")
for col, val in (("L", "No"), ("M", "Overdue")):
    rq.conditional_formatting.add(f"{col}5:{col}{4 + MAX}", FormulaRule(
        formula=[f'{col}5="{val}"'], font=Font(bold=True, color="FFFFFF"), fill=PatternFill("solid", fgColor="000000")))

# ---------------------------------------------------------------- Audit Findings
af = wb.create_sheet("Audit Findings")
title(af, "Access Audit: Corrective Actions",
      "One row per record flagged by sql/access_audit_checks.sql. Close only after the check re-runs clean.")
ACTION = {
    "C01": ("Suspend account; remove rights on all projects; confirm with HR roster", "Admin A"),
    "C02": ("Confirm need with project owner; remove rights if not needed", "Admin B"),
    "C03": ("Reduce export to De-identified or None; owner approves exceptions in writing", "Admin B"),
    "C04": ("Assign a new owner with supervisor approval before next data cycle", "Admin C"),
    "C05": ("Re-route alert to an active staff recipient; test with owner", "Admin A"),
    "C06": ("Remove expired right or renew with owner approval", "Admin B"),
    "C07": ("Owner completes data dictionary and project summary from template", "Admin C"),
}
with open(ROOT / "data" / "audit_findings.csv") as f:
    found = list(csv.DictReader(f))
rows = []
for i, fd in enumerate(found, 1):
    act, owner = ACTION[fd["check_id"]]
    due = AS_OF + timedelta(days=5 if fd["check_id"] in ("C01", "C05") else 14)
    st = random.choice(["Open", "In Progress", "Verified Closed"]) if fd["check_id"] != "C01" else random.choice(
        ["In Progress", "Verified Closed"])
    rows.append([f"F-{i:02d}", fd["check_id"], fd["check"].split(":")[0], fd["entity_key"], fd["detail"], act,
                 owner, AS_OF, due, st, None])
table(af, ["Finding ID", "Check", "Category", "Record", "Detail from query", "Corrective action", "Owner",
           "Found", "Due", "Status", "Overdue?"], [9, 7, 18, 20, 44, 44, 10, 11, 11, 15, 10], rows,
      formulas={11: lambda r: f'=IF(OR(I{r}="",J{r}="Verified Closed"),"",IF(Summary!$B$4>I{r},"Overdue",""))'},
      center=(1, 2, 7, 8, 9, 10))
dropdown(af, "J", ["Open", "In Progress", "Verified Closed"])
datefmt(af, "HI")
af.conditional_formatting.add(f"A5:K{4 + MAX}", FormulaRule(
    formula=['$J5="Verified Closed"'], font=Font(color="808080"), fill=PatternFill("solid", fgColor="F2F2F2")))

# ---------------------------------------------------------------- Summary
sm = wb.create_sheet("Summary", 1)
title(sm, "Summary", "All figures are formulas. Change the as-of date to re-age open items.")
sm["A4"], sm["B4"] = "As-of date", AS_OF
sm["A4"].font = sm["B4"].font = Font(name=FONT, bold=True, size=10)
sm["B4"].number_format = "dd-mmm-yyyy"
sm["B4"].border = Border(*(Side("medium"),) * 4)
sm["C4"] = "<- edit this date"
sm["C4"].font = Font(name=FONT, italic=True, size=9, color="595959")
R, F = "Requests!", "'Audit Findings'!"


def head(row, cols):
    for i, h in enumerate(cols):
        x = sm.cell(row=row, column=1 + i, value=h)
        x.font, x.fill, x.border = HEAD_FONT, HEAD_FILL, BORDER
        x.alignment = Alignment(horizontal="center", wrap_text=True)


def line(row, vals, fmt=None):
    for i, v in enumerate(vals):
        x = sm.cell(row=row, column=1 + i, value=v)
        x.font, x.border = BODY, BORDER
        if i:
            x.alignment = Alignment(horizontal="center")
            if fmt and i in fmt:
                x.number_format = fmt[i]


head(6, ["Requests", "Value"])
line(7, ["Total requests", f'=COUNTA({R}$A$5:$A$204)'])
line(8, ["Resolved", f'=COUNTIF({R}$G$5:$G$204,"Resolved")'])
line(9, ["Open", "=B7-B8"])
line(10, ["Open and overdue", f'=COUNTIF({R}$M$5:$M$204,"Overdue")'])
line(11, ["SLA met (resolved requests)",
          f'=IFERROR(COUNTIF({R}$L$5:$L$204,"Yes")/COUNTIF({R}$G$5:$G$204,"Resolved"),0)'], {1: "0%"})
line(12, ["Avg business days to resolve",
          f'=IFERROR(AVERAGEIF({R}$G$5:$G$204,"Resolved",{R}$J$5:$J$204),0)'], {1: "0.0"})

head(14, ["Request type", "Count", "SLA target", "Avg days (resolved)", "SLA met %"])
for i, (t, _) in enumerate(TYPES):
    r = 15 + i
    line(r, [t, f'=COUNTIF({R}$D$5:$D$204,A{r})',
             f"=INDEX('SLA Targets'!$B$5:$B$12,MATCH(A{r},'SLA Targets'!$A$5:$A$12,0))",
             f'=IFERROR(AVERAGEIFS({R}$J$5:$J$204,{R}$D$5:$D$204,A{r},{R}$G$5:$G$204,"Resolved"),"-")',
             f'=IFERROR(COUNTIFS({R}$D$5:$D$204,A{r},{R}$L$5:$L$204,"Yes")/'
             f'COUNTIFS({R}$D$5:$D$204,A{r},{R}$G$5:$G$204,"Resolved"),"-")'], {3: "0.0", 4: "0%"})

head(24, ["Audit check", "Findings", "Verified closed", "Open + in progress", "Overdue"])
CHECKS = [("C01", "Offboarding gap"), ("C02", "Stale access"), ("C03", "Least privilege"),
          ("C04", "Orphaned project"), ("C05", "Alert routing"), ("C06", "Expired rights"), ("C07", "Documentation")]
for i, (cid, name) in enumerate(CHECKS):
    r = 25 + i
    sm.cell(row=r, column=7, value=cid)  # helper key
    sm.cell(row=r, column=7).font = Font(name=FONT, size=8, color="FFFFFF")
    line(r, [f"{cid} {name}", f'=COUNTIF({F}$B$5:$B$204,G{r})',
             f'=COUNTIFS({F}$B$5:$B$204,G{r},{F}$J$5:$J$204,"Verified Closed")', f"=B{r}-C{r}",
             f'=COUNTIFS({F}$B$5:$B$204,G{r},{F}$K$5:$K$204,"Overdue")'])
line(32, ["Total", "=SUM(B25:B31)", "=SUM(C25:C31)", "=SUM(D25:D31)", "=SUM(E25:E31)"])
for c in range(1, 6):
    sm.cell(row=32, column=c).font = Font(name=FONT, bold=True, size=10)
for col, w in zip("ABCDE", (34, 12, 14, 18, 12)):
    sm.column_dimensions[col].width = w
sm.sheet_view.showGridLines = False

for s in wb.worksheets:
    s.sheet_properties.tabColor = "000000" if s.title in ("Read Me", "Summary") else "808080"
    s.page_setup.orientation = "landscape"
    s.sheet_properties.pageSetUpPr.fitToPage = True
    s.page_setup.fitToWidth, s.page_setup.fitToHeight = 1, 0
OUT.parent.mkdir(exist_ok=True)
wb.save(OUT)
print(OUT, len(reqs), "requests,", len(rows), "findings")
