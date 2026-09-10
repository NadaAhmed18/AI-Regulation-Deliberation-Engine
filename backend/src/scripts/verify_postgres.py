# Run from backend/: python -m src.scripts.verify_postgres
from typing import Any, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import DATABASE_URL


def verify_simulation_data(sim_id: str = "test_sim_912179") -> None:
    print("\n" + "=" * 65)
    print(f"🔍 VERIFYING POSTGRESQL DATA FOR: {sim_id}".center(65))
    print("=" * 65)

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            # 1. Check Table: simulations
            cur.execute(
                "SELECT simulation_id, topic, memory_strategy, personas, status, created_at "
                "FROM simulations WHERE simulation_id = %s",
                (sim_id,),
            )
            raw_sim = cur.fetchone()

            if not raw_sim:
                print(f"[-] ❌ Simulation '{sim_id}' NOT found in 'simulations' table!")

                # List recent simulations so you can pick a valid ID
                cur.execute(
                    "SELECT simulation_id, topic, created_at FROM simulations "
                    "ORDER BY created_at DESC LIMIT 5"
                )
                recent_rows = cur.fetchall()
                if recent_rows:
                    print("\nRecent simulations found in DB:")
                    for r in recent_rows:
                        row_dict: Dict[str, Any] = dict(r)
                        topic_preview = str(row_dict.get("topic", ""))[:40]
                        print(f"  - ID: {row_dict.get('simulation_id')} | Topic: {topic_preview}... | Date: {row_dict.get('created_at')}")
                return

            sim: Dict[str, Any] = dict(raw_sim)
            personas_list: List[Any] = sim.get("personas") or []

            print("[+] ✅ Found in 'simulations' table:")
            print(f"    - ID: {sim.get('simulation_id')}")
            print(f"    - Topic: {sim.get('topic')}")
            print(f"    - Status: {sim.get('status')}")
            print(f"    - Personas Count: {len(personas_list)}")
            print(f"    - Memory Strategy: {sim.get('memory_strategy')}")
            print(f"    - Created At: {sim.get('created_at')}")

            # 2. Check Table: discussion_history
            cur.execute(
                """
                SELECT id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources, created_at
                FROM discussion_history 
                WHERE simulation_id = %s 
                ORDER BY round_number ASC, id ASC
                """,
                (sim_id,),
            )
            raw_turns = cur.fetchall()
            turns: List[Dict[str, Any]] = [dict(t) for t in raw_turns]

            print(f"\n[+] ✅ Found {len(turns)} recorded turns in 'discussion_history':")
            print("-" * 65)

            for t in turns:
                opinion: Dict[str, Any] = t.get("opinion_snapshot") or {}
                sources: List[Any] = t.get("retrieved_sources") or []

                print(f"Round {t.get('round_number')} | Speaker: {t.get('agent_name')} ({t.get('role')})")
                print(f"  Time: {t.get('created_at')}")
                print(f"  Statement: \"{t.get('content')}\"")
                print(
                    f"  Stance Score: {opinion.get('current_stance_score')} "
                    f"(Shift: {opinion.get('shift_magnitude')})"
                )
                print(f"  Opinion Reason: {opinion.get('reasoning')}")
                print(f"  Sources Cited: {len(sources)} source(s) {sources}")
                print("-" * 65)

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    target_id = sys.argv[1] if len(sys.argv) > 1 else "test_sim_912179"
    verify_simulation_data(target_id)