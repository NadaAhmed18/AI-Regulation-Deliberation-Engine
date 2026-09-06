import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
class DiscussionStore:
    def __init__(self, db_path: str = "data/discussion_history.sqlite"):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discussion_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round INTEGER NOT NULL,
                    agent_id TEXT NOT NULL,
                    message TEXT,
                    retrieved_sources TEXT,
                    opinion_snapshot TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_turn(self,round_num: int,agent_id: str,message: str, retrieved_sources: Optional[List[str]] = None,
                  opinion_snapshot: Optional[Dict[str, Any]] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO discussion_history
                   (round, agent_id, message, retrieved_sources, opinion_snapshot, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    round_num,
                    agent_id,
                    message,
                    json.dumps(retrieved_sources or []),
                    json.dumps(opinion_snapshot or {}),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def get_history(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if agent_id:
                rows = conn.execute(
                    "SELECT * FROM discussion_history WHERE agent_id = ? ORDER BY round ASC",
                    (agent_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM discussion_history ORDER BY round ASC, id ASC"
                ).fetchall()
        return [dict(row) for row in rows]

    def export_json(self, path: str = "outputs/discussion_run_sample.json") -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.get_history(), f, indent=2, ensure_ascii=False)
        print(f"[Discussion Store] 💾 Exported to: {out_path}")


if __name__ == "__main__":
    store = DiscussionStore()
    store.save_turn(1, "Persona_A", "Test message", ["https://example.com"], {"stance": "Supportive"})
    for row in store.get_history():
        print(row)