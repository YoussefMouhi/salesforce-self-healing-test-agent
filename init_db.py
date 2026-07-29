import sqlite3

conn = sqlite3.connect("test_runs.db")
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    overall_status TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    step_index INTEGER NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS failures (
    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    step_index INTEGER NOT NULL,
    error_detail TEXT,
    debug_screenshot_path TEXT
);
""")

conn.commit()
conn.close()
print("Initialized test_runs.db with runs/steps/failures tables.")
