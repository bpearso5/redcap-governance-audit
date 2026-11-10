-- REDCap access & governance audit checks
-- Portable SQL: runs unchanged in MySQL 8 and SQLite 3.
-- As-of date for this audit: 2026-03-31. The 90-day inactivity cutoff is 2025-12-31.
-- Each check returns check_id, entity_key, and the detail a reviewer needs to act.

-- @check C01 Offboarding gap: separated staff whose REDCap account is still active
SELECT 'C01' AS check_id, u.username AS entity_key,
       s.full_name, s.separation_date, u.last_login
FROM redcap_users u
JOIN staff_roster s ON s.employee_id = u.employee_id
WHERE s.status = 'Separated'
  AND u.account_status = 'active';

-- @check C02 Stale access: active account, no login in 90+ days, still holds project rights
SELECT 'C02' AS check_id, u.username AS entity_key,
       u.last_login, COUNT(r.project_id) AS projects_with_rights
FROM redcap_users u
JOIN staff_roster s ON s.employee_id = u.employee_id
JOIN user_rights r ON r.username = u.username
WHERE u.account_status = 'active'
  AND s.status = 'Active'
  AND u.last_login < '2025-12-31'
GROUP BY u.username, u.last_login;

-- @check C03 Least privilege: identifiable (Full) export on a Data Entry or Viewer role
-- entity key = project_id|username (built by the runner; string concatenation differs by dialect)
SELECT 'C03' AS check_id, project_id, username, role, data_export
FROM user_rights
WHERE role IN ('Data Entry', 'Viewer')
  AND data_export = 'Full';

-- @check C04 Orphaned project: Production project whose owner account is suspended or missing
SELECT 'C04' AS check_id, CAST(p.project_id AS CHAR) AS entity_key,
       p.title, p.owner_username, u.account_status
FROM projects p
LEFT JOIN redcap_users u ON u.username = p.owner_username
WHERE p.status = 'Production'
  AND (u.username IS NULL OR u.account_status <> 'active');

-- @check C05 Alert routing: active alert sends to an address that is not an active staff member
SELECT 'C05' AS check_id, a.alert_id AS entity_key,
       a.project_id, a.alert_title, a.recipient_email
FROM alerts a
LEFT JOIN staff_roster s ON s.email = a.recipient_email AND s.status = 'Active'
WHERE a.active = 1
  AND s.employee_id IS NULL;

-- @check C06 Expired rights: user right past its expiration date still in place
-- entity key = project_id|username (built by the runner)
SELECT 'C06' AS check_id, project_id, username, expiration_date
FROM user_rights
WHERE expiration_date IS NOT NULL
  AND expiration_date < '2026-03-31';

-- @check C07 Documentation: Production project with no documentation on file
SELECT 'C07' AS check_id, CAST(project_id AS CHAR) AS entity_key, title, owner_username
FROM projects
WHERE status = 'Production'
  AND has_documentation = 'N';
