"""Generate synthetic REDCap governance data with seeded defects and an answer key.

All people, emails, projects and alerts are invented. Deterministic (seeded).
Run: python3 scripts/generate_data.py
Writes data/*.csv, data/redcap_audit.db (SQLite) and data/answer_key.csv.
"""
import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(2026)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
AS_OF = date(2026, 3, 31)

FIRST = ["Avery", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Quinn", "Jamie", "Reese", "Drew",
         "Skyler", "Cameron", "Rowan", "Emerson", "Hayden", "Kendall", "Logan", "Parker", "Sage", "Blake"]
LAST = ["Ellison", "Marsh", "Okafor", "Brandt", "Castillo", "Whitfield", "Nakamura", "Delgado", "Holloway",
        "Pruitt", "Abernathy", "Coleman", "Vance", "Sorensen", "Iverson", "Tran", "Mercer", "Lindqvist"]
UNITS = ["Surveillance", "Epidemiology", "Immunization", "Lab Liaison", "Informatics", "Program Evaluation"]
ROLES = ["Epidemiologist", "Data Analyst", "Program Coordinator", "Data Entry Specialist", "Informatics Lead"]
DOMAIN = "example-health.org"


def d(days_ago):
    return (AS_OF - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------- staff + users (clean baseline)
staff, users, used = [], [], set()
for i in range(1, 181):
    while True:
        fn, ln = random.choice(FIRST), random.choice(LAST)
        un = f"{fn[0]}{ln}".lower() + (str(i) if f"{fn[0]}{ln}".lower() in used else "")
        if un not in used:
            used.add(un)
            break
    emp = f"E{1000 + i}"
    email = f"{un}@{DOMAIN}"
    staff.append(dict(employee_id=emp, full_name=f"{fn} {ln}", email=email, unit=random.choice(UNITS),
                      job_role=random.choice(ROLES), status="Active", separation_date=""))
    users.append(dict(username=un, email=email, employee_id=emp, last_login=d(random.randint(0, 60)),
                      account_status="active"))

key = []  # (check_id, entity_key, description)

# ---------------------------------------------------------------- projects (clean)
PURPOSES = ["Case surveillance", "Outbreak investigation", "Program evaluation", "Vaccine follow-up",
            "Lab result intake", "Quality improvement", "Survey"]
projects = []
owners = random.sample(users[:120], 40)
for i in range(1, 41):
    projects.append(dict(project_id=100 + i, title=f"{random.choice(PURPOSES)} {2023 + i % 4}-{i:02d}",
                         status=random.choice(["Production"] * 3 + ["Development", "Analysis/Cleanup"]),
                         owner_username=owners[i - 1]["username"], has_documentation="Y"))

# ---------------------------------------------------------------- user rights (clean, least privilege)
rights = []
for p in projects:
    rights.append(dict(project_id=p["project_id"], username=p["owner_username"], role="Owner",
                       data_export="Full", design=1, user_rights_admin=1, expiration_date=""))
    others = random.sample([u for u in users[:150] if u["username"] != p["owner_username"]], random.randint(4, 10))
    for u in others:
        role = random.choice(["Data Entry", "Data Entry", "Analyst", "Viewer"])
        export = {"Data Entry": "None", "Analyst": random.choice(["Full", "De-identified"]),
                  "Viewer": "De-identified"}[role]
        exp = "" if random.random() < 0.7 else (AS_OF + timedelta(days=random.randint(30, 300))).isoformat()
        rights.append(dict(project_id=p["project_id"], username=u["username"], role=role, data_export=export,
                           design=0, user_rights_admin=0, expiration_date=exp))

# ---------------------------------------------------------------- alerts (clean)
active_emails = [u["email"] for u in users[:150]]
alerts = []
for i in range(1, 61):
    alerts.append(dict(alert_id=f"AL-{i:03d}", project_id=random.choice(projects)["project_id"],
                       alert_title=random.choice(["New case submitted", "Lab result received", "Follow-up due",
                                                  "Survey complete", "Missing required field"]),
                       recipient_email=random.choice(active_emails), active=1))

users_by = {u["username"]: u for u in users}
staff_by = {s["employee_id"]: s for s in staff}
non_owner = [r for r in rights if r["role"] != "Owner"]
owner_set = {p["owner_username"] for p in projects}
alert_emails = {a["recipient_email"] for a in alerts}

# Pool of users safe to mutate: not owners, not alert recipients
pool = [u for u in users[:150] if u["username"] not in owner_set and u["email"] not in alert_emails
        and any(r["username"] == u["username"] for r in rights)]
random.shuffle(pool)

# C01: separated staff whose REDCap account is still active (6)
for u in pool[:6]:
    s = staff_by[u["employee_id"]]
    s["status"], s["separation_date"] = "Separated", d(random.randint(20, 120))
    key.append(("C01", u["username"], "Separated staff, REDCap account still active"))

# C02: active staff, no login in 90+ days, still holding project rights (8)
for u in pool[6:14]:
    u["last_login"] = d(random.randint(95, 300))
    key.append(("C02", u["username"], "No login in 90+ days but still has project rights"))

# C03: identifiable (Full) export granted to Data Entry or Viewer role (5)
c3 = [r for r in non_owner if r["role"] in ("Data Entry", "Viewer") and r["username"] in
      {u["username"] for u in pool[14:]}]
for r in random.sample(c3, 5):
    r["data_export"] = "Full"
    key.append(("C03", f'{r["project_id"]}|{r["username"]}', "Full export on a Data Entry/Viewer role"))

# C04: production projects whose owner account is suspended (staff separated) (3)
prod = [p for p in projects if p["status"] == "Production"]
for p in random.sample(prod, 3):
    u = users_by[p["owner_username"]]
    u["account_status"] = "suspended"
    staff_by[u["employee_id"]]["status"] = "Separated"
    staff_by[u["employee_id"]]["separation_date"] = d(random.randint(30, 90))
    key.append(("C04", str(p["project_id"]), "Production project owned by a suspended account"))
suspended_emails = {users_by[p["owner_username"]]["email"] for p in projects
                    if users_by[p["owner_username"]]["account_status"] == "suspended"}

# C05: active alerts sending to addresses that aren't active staff (4)
bad_emails = [f"former.staff{i}@{DOMAIN}" for i in range(1, 3)] + [f"student.intern@{DOMAIN}",
                                                                    "personal.inbox@mail-example.com"]
for a, e in zip(random.sample(alerts, 4), bad_emails):
    a["recipient_email"] = e
    key.append(("C05", a["alert_id"], "Active alert sends to a non-staff address"))
# Follow-on defects: alerts that still route to the separated owners from C04
for a in alerts:
    if a["recipient_email"] in suspended_emails:
        key.append(("C05", a["alert_id"], "Follow-on from C04: alert still routes to a separated owner"))

# C06: rights past their expiration date still in place (5)
c6 = [r for r in non_owner if r["expiration_date"] == "" and r["username"] in {u["username"] for u in pool[14:]}
      and f'{r["project_id"]}|{r["username"]}' not in {k[1] for k in key}]
for r in random.sample(c6, 5):
    r["expiration_date"] = d(random.randint(10, 150))
    key.append(("C06", f'{r["project_id"]}|{r["username"]}', "User right past its expiration date"))

# C07: production projects with no documentation on file (4)
c7 = [p for p in prod if str(p["project_id"]) not in {k[1] for k in key if k[0] == "C04"}]
for p in random.sample(c7, 4):
    p["has_documentation"] = "N"
    key.append(("C07", str(p["project_id"]), "Production project with no documentation on file"))


# ---------------------------------------------------------------- write CSVs + SQLite
def write(name, rows):
    with open(DATA / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


tables = dict(staff_roster=staff, redcap_users=users, projects=projects, user_rights=rights, alerts=alerts)
for n, rows in tables.items():
    write(n, rows)
write("answer_key", [dict(check_id=c, entity_key=k, seeded_defect=t) for c, k, t in sorted(key)])

db = DATA / "redcap_audit.db"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
con.executescript((ROOT / "sql" / "schema.sql").read_text())
for n, rows in tables.items():
    cols = list(rows[0].keys())
    con.executemany(f"INSERT INTO {n} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [[None if r[c] == "" else r[c] for c in cols] for r in rows])
con.commit()
con.close()
print({n: len(r) for n, r in tables.items()}, "seeded defects:", len(key))
