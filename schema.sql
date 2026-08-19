CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  org TEXT NOT NULL,
  category TEXT,
  title TEXT,
  source_url TEXT,
  discovered_at TEXT NOT NULL,
  content_hash TEXT,
  is_public_release INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  content_text TEXT,
  numbers_json TEXT,
  attachments_json TEXT,
  FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  level TEXT NOT NULL,
  score INTEGER NOT NULL,
  finding_json TEXT NOT NULL,
  UNIQUE(source_id, finding_json)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_source ON snapshots(source_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_level ON findings(level, score DESC);
