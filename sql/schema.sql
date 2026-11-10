-- REDCap governance audit: synthetic schema (runs in MySQL 8 and SQLite 3)

CREATE TABLE staff_roster (
    employee_id      VARCHAR(10) PRIMARY KEY,
    full_name        VARCHAR(80) NOT NULL,
    email            VARCHAR(120) NOT NULL,
    unit             VARCHAR(40),
    job_role         VARCHAR(40),
    status           VARCHAR(12) NOT NULL,   -- Active | Separated
    separation_date  DATE
);

CREATE TABLE redcap_users (
    username        VARCHAR(40) PRIMARY KEY,
    email           VARCHAR(120) NOT NULL,
    employee_id     VARCHAR(10),
    last_login      DATE,
    account_status  VARCHAR(12) NOT NULL    -- active | suspended
);

CREATE TABLE projects (
    project_id         INT PRIMARY KEY,
    title              VARCHAR(120) NOT NULL,
    status             VARCHAR(20) NOT NULL, -- Development | Production | Analysis/Cleanup
    owner_username     VARCHAR(40),
    has_documentation  CHAR(1) NOT NULL      -- Y | N
);

CREATE TABLE user_rights (
    project_id         INT NOT NULL,
    username           VARCHAR(40) NOT NULL,
    role               VARCHAR(20) NOT NULL, -- Owner | Analyst | Data Entry | Viewer
    data_export        VARCHAR(16) NOT NULL, -- Full | De-identified | None
    design             INT NOT NULL,
    user_rights_admin  INT NOT NULL,
    expiration_date    DATE,
    PRIMARY KEY (project_id, username)
);

CREATE TABLE alerts (
    alert_id         VARCHAR(10) PRIMARY KEY,
    project_id       INT NOT NULL,
    alert_title      VARCHAR(80),
    recipient_email  VARCHAR(120) NOT NULL,
    active           INT NOT NULL
);
