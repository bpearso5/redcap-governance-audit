"""Run every audit check against the synthetic SQLite database and score it against the answer key.

Run: python3 scripts/run_checks.py
Writes data/audit_findings.csv and exits non-zero if any check misses a seeded defect
or flags a clean record.
"""
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = (ROOT / "sql" / "access_audit_checks.sql").read_text()
con = sqlite3.connect(ROOT / "data" / "redcap_audit.db")
con.row_factory = sqlite3.Row

blocks = re.split(r"^-- @check ", SQL, flags=re.M)[1:]
findings = []
for block in blocks:
    header, body = block.split("\n", 1)
    check_id, title = header.split(" ", 1)
    query = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
    for row in con.execute(query):
        r = dict(row)
        ek = r.get("entity_key") or f'{r["project_id"]}|{r["username"]}'
        detail = "; ".join(f"{k}={v}" for k, v in r.items() if k not in ("check_id", "entity_key"))
        findings.append(dict(check_id=check_id, check=title, entity_key=str(ek), detail=detail))

with open(ROOT / "data" / "answer_key.csv") as f:
    expected = {(r["check_id"], r["entity_key"]) for r in csv.DictReader(f)}
found = {(f["check_id"], f["entity_key"]) for f in findings}

with open(ROOT / "data" / "audit_findings.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["check_id", "check", "entity_key", "detail"])
    w.writeheader()
    w.writerows(sorted(findings, key=lambda x: (x["check_id"], x["entity_key"])))

counts = Counter(c for c, _ in found)
for block in blocks:
    cid, title = block.split("\n", 1)[0].split(" ", 1)
    exp = sum(1 for c, _ in expected if c == cid)
    print(f"{cid}  {title:<75} flagged {counts.get(cid, 0):>2} / seeded {exp:>2}")

missed, false_pos = expected - found, found - expected
print(f"\nTotal flagged: {len(found)} | seeded: {len(expected)} | missed: {len(missed)} | false positives: {len(false_pos)}")
if missed or false_pos:
    print("MISSED:", sorted(missed), "\nFALSE POSITIVES:", sorted(false_pos))
    sys.exit(1)
print("All seeded defects caught; no clean records flagged.")
