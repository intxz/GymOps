PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_user_id INTEGER NOT NULL UNIQUE,
  username TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE workout_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'cancelled')),
  duration_seconds INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE exercises (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE set_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workout_session_id INTEGER NOT NULL,
  exercise_id INTEGER NOT NULL,
  weight REAL NOT NULL CHECK (weight >= 0),
  reps INTEGER NOT NULL CHECK (reps > 0),
  rpe REAL NOT NULL CHECK (rpe >= 0 AND rpe <= 10),
  is_warmup INTEGER NOT NULL CHECK (is_warmup IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (workout_session_id) REFERENCES workout_sessions(id),
  FOREIGN KEY (exercise_id) REFERENCES exercises(id)
);

CREATE UNIQUE INDEX uq_one_active_session_per_user
ON workout_sessions(user_id)
WHERE status = 'active';

CREATE INDEX idx_set_entries_session ON set_entries(workout_session_id);
CREATE INDEX idx_set_entries_exercise ON set_entries(exercise_id);
CREATE INDEX idx_workout_sessions_user ON workout_sessions(user_id);

