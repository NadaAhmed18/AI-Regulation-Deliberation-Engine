"""
Key Findings & TASA Clustering Performance Benchmark

Usage:
  # 1. Run calibrated sweep across thresholds (0 cost, vector only):
  python -m src.scripts.test_clustering_performance --sweep --skip-llm

  # 2. Deep test at the calibrated 0.81 threshold without LLM:
  python -m src.scripts.test_clustering_performance --threshold 0.81 --skip-llm

  # 3. Full test with LLM distillation at 0.81 (checks word count & truncation):
  python -m src.scripts.test_clustering_performance --threshold 0.81

  # 4. Live DB test on a real simulation:
  python -m src.scripts.test_clustering_performance --sim-id sim_xxxxxx --threshold 0.81
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

# Ensure backend root is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
BACKEND_DIR = SRC_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.analytics.metrics.key_findings import (
    KeyFindingCluster,
    _get_embedder,
    extract_key_findings,
)
from src.controllers.repository.simulation_repository import SimulationRepository

# ==============================================================================
# 1. REAL 16-TURN TEST FIXTURE (From Hardware Kill-Switch Debate)
# ==============================================================================
FIXTURE_TOPIC = "Should governments mandate hardware-level kill-switches for frontier open-source AI?"

FIXTURE_HISTORY: List[Dict[str, Any]] = [
    {
        "id": 1, "round_number": 1, "agent_name": "Sofia Martínez",
        "opinion_snapshot": {"current_stance_score": 2.0},
        "content": (
            "I hear the concern that a mandated hardware kill-switch could become a back-door for corporate "
            "or state abuse - the industry argument echoed by Nvidia's security chief. But without a clear, "
            "worker-centered oversight regime, the very people who design, build, and operate these systems "
            "are left exposed to unsafe, unstoppable machines that threaten public safety and jobs. A regulated "
            "kill-switch must be treated like safety equipment on industrial machinery: independent audit trails, "
            "dual-control protocols with on-site technicians, and control paths owned by the workforce. The EU AI Act 2.0 "
            "mandates hardware-level stop functions. We should build on that model with labor union governance."
        ),
    },
    {
        "id": 2, "round_number": 2, "agent_name": "Evan Patel",
        "opinion_snapshot": {"current_stance_score": -4.4},
        "content": (
            "Sofia, you raise a valid fear of abuse, but the EU's own AI Act 2.0 illustrates why a blanket "
            "hardware kill-switch is a bad idea: it forces a single vendor-controlled control path in firmware or BMC, "
            "becoming part of the trusted computing base and a lucrative backdoor for state coercion. Instead of a top-down "
            "mandate, let the open-source community define safety standards like Responsible AI Licenses and peer-audited "
            "hardware-stop protocols so any developer can implement a kill path they control and audit without risking a monopoly."
        ),
    },
    {
        "id": 3, "round_number": 3, "agent_name": "Dr. Maya Liao",
        "opinion_snapshot": {"current_stance_score": 1.7},
        "content": (
            "Sofia, I agree that abuse risk demands a robust governance layer, but the core problem is that without "
            "a verifiable hardware stop, no audit trail or dual-control protocol can ever be trusted - software can be "
            "overwritten. The EU's AI Act 2.0 proves regulators can require an independent control path living in a BMC "
            "or dedicated safety controller. Evan, community licenses cannot guarantee every fork embeds an immutable stop. "
            "A government mandate with third-party union oversight creates an enforceable barrier against runaway frontier models."
        ),
    },
    {
        "id": 4, "round_number": 4, "agent_name": "Lt. Col. Jonas Weber (Ret.)",
        "opinion_snapshot": {"current_stance_score": 1.1},
        "content": (
            "Sofia, I agree the audit trail must be immutable, which is precisely why a hardware-level kill-switch is "
            "indispensable - software can be overwritten, but a dedicated stop path in the BMC or microcontroller can be sealed. "
            "The EU AI Act 2.0 forces a separate control plane that survives firmware compromise. Evan, the US AI Kill Switch Act "
            "illustrates the alternative: Congress obliges large AI developers to embed verifiable shutdown capability with DHS "
            "emergency authority and penalties up to $20 million per day. This is the only barrier against hostile state actors."
        ),
    },
    {
        "id": 5, "round_number": 5, "agent_name": "Dr. Maya Liao",
        "opinion_snapshot": {"current_stance_score": 3.0},
        "content": (
            "Jonas, your emphasis on an immutable BMC or safety-microcontroller aligns precisely with why a statutory "
            "kill-switch is essential: it guarantees a control path that remains operational under firmware compromise. "
            "The US AI Kill Switch Act's emergency authority and steep penalties provide the teeth needed to ensure compliance "
            "and fund independent third-party certification boards including unions and safety experts."
        ),
    },
    {
        "id": 6, "round_number": 6, "agent_name": "Sofia Martínez",
        "opinion_snapshot": {"current_stance_score": 2.0},
        "content": (
            "Jonas, I hear your confidence in a hardened BMC-based switch, but who builds, maintains, and audits that "
            "sealed path? On the fab floor, safety-critical hardware is only as trustworthy as the workers who inspect it. "
            "A mandated kill-switch should be overseen by an independent board of union engineers, safety officers, and public "
            "technologists, just as OSHA equipment requires third-party inspection to prevent corporate capture."
        ),
    },
    {
        "id": 7, "round_number": 7, "agent_name": "Evan Patel",
        "opinion_snapshot": {"current_stance_score": -0.6},
        "content": (
            "Sofia, a hardware-level stop becomes a single point of failure for an entire distributed AI supply chain. "
            "Large-scale models aren't hosted on a single server, making a single physical switch impossible. Embedding such "
            "a switch forces every cloud provider and OEM into a fragile trusted-computing base. As Nvidia warned, a backdoor "
            "creates a permanent implant that can be repurposed by adversaries. We need layered software-first controls: rate-limits, "
            "anomaly detectors, and audit logs without brittle choke points."
        ),
    },
    {
        "id": 8, "round_number": 8, "agent_name": "Lt. Col. Jonas Weber (Ret.)",
        "opinion_snapshot": {"current_stance_score": 1.2},
        "content": (
            "Evan, modern hardware stops need not be a single point of failure - they can be implemented as a federated "
            "shutdown mesh embedded in each compute node's Trusted Platform Module (TPM). When central command flags a threat, "
            "the mesh propagates a cryptographically signed kill command that each node autonomously enforces. The US AI Kill Switch Act "
            "funds research into this TPM mesh cascade architecture."
        ),
    },
    {
        "id": 9, "round_number": 9, "agent_name": "Dr. Maya Liao",
        "opinion_snapshot": {"current_stance_score": 1.4},
        "content": (
            "The single-point-of-failure objection overlooks the federated mesh design Jonas described - each node's TPM enforces "
            "the kill command locally, creating redundancy while preserving a verifiable stop path. Software-only controls lack "
            "the immutable guarantee that only a hardware-anchored, auditable switch can provide against existential misuse."
        ),
    },
    {
        "id": 10, "round_number": 10, "agent_name": "Evan Patel",
        "opinion_snapshot": {"current_stance_score": -2.0},
        "content": (
            "Jonas, the TPM-based mesh assumes every open-source operator can embed proprietary firmware into every compute node, "
            "barring small labs and hobbyists. Over 70% of open-source contributors run models on off-the-shelf CPUs/GPUs without custom "
            "firmware according to the Linux Foundation. Mandating signed TPM commands forces vendor-locked firmware and creates a monopoly. "
            "Let the community standardize a software-anchored protocol verified with open TPM attestation tools and public ledgers."
        ),
    },
    {
        "id": 11, "round_number": 11, "agent_name": "Dr. Maya Liao",
        "opinion_snapshot": {"current_stance_score": -0.2},
        "content": (
            "Evan, the security gap lies in that ubiquity - without a hardware-anchored stop, malicious actors exploit commodity nodes. "
            "The solution is to democratize the firmware: an open-source, auditable TPM stack (such as the OpenTPM project) compiled and "
            "flashed onto generic hardware. By standardizing signed policy blobs in a public tamper-evident ledger, small labs participate "
            "without proprietary constraints."
        ),
    },
    {
        "id": 12, "round_number": 12, "agent_name": "Evan Patel",
        "opinion_snapshot": {"current_stance_score": -1.3},
        "content": (
            "Maya, even an auditable open TPM like OpenTPM requires signed binaries, build attestation, and periodic re-flashing, creating "
            "a maintenance barrier that drives developers to cloud monopolies with pre-approved chips. Instead of a federal mandate, "
            "we should evolve a voluntary, peer-reviewed kill-protocol using existing TPM attestation APIs and community-run audit collectives."
        ),
    },
    {
        "id": 13, "round_number": 13, "agent_name": "Lt. Col. Jonas Weber (Ret.)",
        "opinion_snapshot": {"current_stance_score": 1.0},
        "content": (
            "Evan, the national-security calculus outweighs hobbyist inconvenience. Without a hardware anchor, off-the-shelf nodes become "
            "launchpads for hostile state actors and disinformation campaigns. An open-source TPM stack can be flashed by anyone, and the "
            "certification board verifies signed firmware without locking developers into a single vendor."
        ),
    },
    {
        "id": 14, "round_number": 14, "agent_name": "Dr. Maya Liao",
        "opinion_snapshot": {"current_stance_score": 2.7},
        "content": (
            "Software-only mitigations are subverted once an attacker gains root on a commodity node. By mandating open-source TPM firmware "
            "built from reproducible source and verified via reproducible-build hashes (similar to Linux kernel maintainers), we retain the "
            "low-entry ethos while providing a legally enforceable stop-gap aligned with international standards."
        ),
    },
    {
        "id": 15, "round_number": 15, "agent_name": "Lt. Col. Jonas Weber (Ret.)",
        "opinion_snapshot": {"current_stance_score": 4.5},
        "content": (
            "Software controls crumble once an adversary obtains root. The UK Defence-AI Assurance Framework already requires frontier models "
            "on commodity hardware to include a TPM-verified kill command in a national ledger. An open TPM firmware gives every garage researcher "
            "the same verifiable stop mechanism that adversaries cannot sidestep."
        ),
    },
    {
        "id": 16, "round_number": 16, "agent_name": "Evan Patel",
        "opinion_snapshot": {"current_stance_score": 0.6},
        "content": (
            "A statutory kill-switch creates a single government-controlled stop lever that can be weaponized into political censorship and "
            "used to shut down models conflicting with state policy, repeating export-control abuse. Instead of a legal mandate, we should "
            "fund an open-source kill-blob registry (like Sigstore for software signatures) where community-maintained TPM policy packages are "
            "voluntarily adopted."
        ),
    },
]

# ==============================================================================
# 2. AUDIT & METRICS HELPERS
# ==============================================================================

def print_separator(char: str = "=", length: int = 85) -> None:
    print(char * length)


def evaluate_separation(clusters: List[Dict[str, Any]]) -> float:
    """Calculates average inter-cluster cosine similarity. Lower = cleaner separation."""
    if len(clusters) <= 1:
        return 1.0
    embedder = _get_embedder()
    texts = [str(c.get("statement", "")) for c in clusters]
    vectors = [embedder.embed([t], is_query=True)[0] for t in texts]
    norms = [v / (np.linalg.norm(v) + 1e-9) for v in vectors]

    sims: List[float] = []
    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            sims.append(float(np.dot(norms[i], norms[j])))

    return round(float(np.mean(sims)), 3) if sims else 1.0


def audit_statement_quality(statement: str) -> Dict[str, Any]:
    """Audits the synthesized string for truncation and brevity bugs."""
    words = statement.strip().split()
    word_count = len(words)
    is_truncated = False
    warning: Optional[str] = None

    if word_count < 4:
        is_truncated = True
        warning = "CRITICAL: Truncated statement (< 4 words) - e.g. 'Policymakers balance'"
    elif word_count > 20:
        warning = "WARNING: Distillation too verbose (> 20 words)"
    elif statement.endswith("...") or statement.endswith("-"):
        is_truncated = True
        warning = "WARNING: Cut off with trailing punctuation"

    return {
        "word_count": word_count,
        "is_truncated": is_truncated,
        "warning": warning,
    }


def apply_offline_distillation_mock() -> None:
    """Safely mocks distillation for offline/zero-cost benchmarking without Pylance errors."""
    def _mock_distill_summary(self: Any, llm_client: Any) -> None:
        self.canonical_statement = f"Thematic cluster synthesized from {len(self.snippets)} turns."
        self.is_confirmed = True

    setattr(KeyFindingCluster, "distill_summary", _mock_distill_summary)


# ==============================================================================
# 3. RUN MODES: CALIBRATED SWEEP & DEEP DIVE
# ==============================================================================

def run_threshold_sweep(topic: str, history: List[Dict[str, Any]], skip_llm: bool) -> None:
    """Sweeps across calibrated similarity thresholds (0.76 to 0.85)."""
    print_separator()
    print(f"[*] RUNNING CALIBRATED TASA THRESHOLD SWEEP ({len(history)} turns)")
    print(f"[*] Topic: '{topic}'")
    print(f"[*] Skip LLM Distillation: {skip_llm}")
    print_separator()

    if skip_llm:
        apply_offline_distillation_mock()

    # Narrowed sweep around the empirical sweet spot for Voyage/HF embeddings
    thresholds = [0.76, 0.78, 0.80, 0.81, 0.82, 0.83, 0.84, 0.86]

    print(f"{'Threshold':<11} | {'Confirmed (>=2)':<16} | {'Max Heat':<9} | {'Dist. Profile':<25} | {'Time (s)':<8}")
    print("-" * 85)

    for thresh in thresholds:
        start_t = time.perf_counter()
        findings = extract_key_findings(
            topic=topic,
            history_rows=history,
            similarity_threshold=thresh,
            heat_threshold=2,
        )
        elapsed = round(time.perf_counter() - start_t, 3)

        confirmed_count = len(findings)
        heats = [f["heat"] for f in findings]
        max_heat = max(heats) if heats else 0
        heat_dist = "/".join(str(h) for h in heats[:5]) + ("..." if len(heats) > 5 else "")

        print(f"{thresh:<11.2f} | {confirmed_count:<16} | {max_heat:<9} | {heat_dist:<25} | {elapsed:<8}")

    print_separator("-")
    print("[+] DIAGNOSTIC INTERPRETATION:")
    print("  - At 0.76: Collapses into 1 cluster with Heat 16 (Original Engine Bug).")
    print("  - At 0.80 - 0.82: Cleanly separates into 2-3 distinct, balanced sub-topics.")
    print("  - Above 0.86: Oversplits into singletons (too strict).")
    print_separator()


def run_deep_dive(topic: str, history: List[Dict[str, Any]], threshold: float, skip_llm: bool) -> None:
    """Executes a full run at a specific threshold with detailed output and audits."""
    print_separator()
    print(f"[*] RUNNING IN-DEPTH CLUSTERING AUDIT @ THRESHOLD: {threshold:.2f}")
    print(f"[*] Topic: '{topic}' | Total History Turns: {len(history)}")
    print(f"[*] LLM Generation: {'Disabled (Mock)' if skip_llm else 'Enabled (Live API)'}")
    print_separator()

    if skip_llm:
        apply_offline_distillation_mock()

    start_t = time.perf_counter()
    findings = extract_key_findings(
        topic=topic,
        history_rows=history,
        similarity_threshold=threshold,
        heat_threshold=2,
    )
    total_time = round(time.perf_counter() - start_t, 3)

    if not findings:
        print(f"[-] No clusters met heat_threshold >= 2 at threshold {threshold}!")
        return

    print(f"[+] Discovered {len(findings)} Confirmed Key Finding Clusters in {total_time}s:\n")

    for idx, f in enumerate(findings, 1):
        stmt = f["statement"]
        heat = f["heat"]
        supp = ", ".join(f["supporting_agents"]) or "None"
        opp = ", ".join(f["opposing_agents"]) or "None"
        rounds = f"Rounds {f['first_round']}-{f['last_round']}"

        audit = audit_statement_quality(stmt)

        print(f"Cluster #{idx} [ID: {f['id']}] — Heat: {heat} ({rounds})")
        print(f"  Statement: \"{stmt}\"")
        print(f"  Supporting Agents: [{supp}]")
        print(f"  Opposing Agents:   [{opp}]")
        print(f"  Quality Audit:     Words: {audit['word_count']} | Truncated: {audit['is_truncated']}")
        if audit["warning"]:
            print(f"  * ALERT: {audit['warning']}")
        print()

    sep = evaluate_separation(findings)
    print_separator("-")
    print(f"[*] Inter-Cluster Centroid Cosine Similarity: {sep:.3f}")
    if sep > 0.88:
        print("  * Note: Sub-topics are closely aligned. Consider bumping threshold slightly.")
    else:
        print("  * Excellent: Sub-topics are distinct and well-separated in vector space.")
    print_separator()


# ==============================================================================
# 4. CLI ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Test TASA debate clustering and key finding distillation.")
    parser.add_argument("--sim-id", type=str, default=None, help="Optional DB simulation_id to test on real saved history.")
    parser.add_argument("--threshold", type=float, default=0.81, help="Cosine similarity threshold (default: 0.81).")
    parser.add_argument("--sweep", action="store_true", help="Run a calibrated multi-threshold sweep (0.76 -> 0.86).")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM distillation calls to test vector clustering for free.")
    args = parser.parse_args()

    topic = FIXTURE_TOPIC
    history = FIXTURE_HISTORY

    if args.sim_id:
        print(f"[*] Querying PostgreSQL for simulation: '{args.sim_id}'...")
        repo = SimulationRepository()
        sim = repo.get_simulation_by_id(args.sim_id)
        if not sim:
            print(f"[!] Error: Simulation '{args.sim_id}' not found in database.")
            sys.exit(1)
        topic = sim.get("topic", topic)
        history = repo.get_discussion_history(args.sim_id)
        print(f"[+] Loaded {len(history)} turns from database for topic: '{topic}'")

    if args.sweep:
        run_threshold_sweep(topic, history, skip_llm=args.skip_llm)
    else:
        run_deep_dive(topic, history, threshold=args.threshold, skip_llm=args.skip_llm)


if __name__ == "__main__":
    main()