"""
OPINION SHIFT PROTOTYPE — Fixed Text, No LLM (Lexicon-Based Stance Scoring)

STATUS: Research prototype / proof of concept only.
    This is NOT the Week 4 "Opinion Shift Tracker" (tracker.py per the
    project architecture diagram). It exists to validate the underlying
    analytics concept -- "can we detect and quantify opinion shift across
    a multi-round discussion?" -- using a hand-written, fixed transcript
    and zero API/model calls, before wiring the real thing up to a live
    Week 3 discussion engine and/or an LLM-based classifier.

Method (lexicon-based stance scoring, distinct from generic sentiment
analysis):
    Stance detection asks "is this text for or against a specific
    target?" (here: an EU-style AI regulation), which is a different
    question from sentiment analysis ("is this text positive or
    negative in tone?"). Each message is scored on a scale from -1.0
    (fully Pro-Innovation) to +1.0 (fully Pro-Regulation) by counting
    stance-specific lexicon words, the same core technique lexicon-based
    sentiment tools (VADER, TextBlob) use for generic polarity:

        score = (pro_reg_hits - pro_innov_hits) / (pro_reg_hits + pro_innov_hits)

    A separate list of hedging/concession phrases ("you raise a good
    point", "on reflection") is matched per message too -- reported as
    human-readable evidence of *why* a shift happened, not scored
    numerically.

Known limitation (by design, for a proof of concept):
    This is naive word-counting: it does not handle negation, sarcasm,
    or context (e.g. "the safeguards should be smaller" still counts
    "safeguards" as a pro-regulation hit). This is a known, documented
    weakness of lexicon-based methods in general, not specific to this
    prototype. A production version should add negation handling (words
    like "not", "less", "reduce" preceding a lexicon word should flip or
    dampen its contribution) or move to an LLM/classifier-based stance
    judgment for real discussion transcripts.

How this maps to the real Week 4 pipeline:

    transcript (from the Week 3 discussion engine)
           |
           v
    score_message() per message   <-- this file's core function
           |
           v
    opinion_history[agent] = [scores across rounds]
           |
           v
    shift_magnitude = |final_score - initial_score|
           |
           v
    visualization (line chart of stance over rounds)

Run as: python -m src.research.opinion_shift_prototype
"""

# ---------------------------------------------------------------------------
# 1. LEXICON — stance-specific word/phrase lists (not generic sentiment words)
# ---------------------------------------------------------------------------

PRO_REGULATION_WORDS = [
    "oversight", "accountability", "safeguard", "safeguards", "protect",
    "protection", "risk", "risks", "harm", "harms", "regulate", "regulation",
    "regulatory", "mandatory", "enforce", "enforcement", "transparency",
    "public trust", "safety", "rights", "discrimination",
    "audit", "compliance requirement",
    # NOTE: "human oversight" and "high-risk" were intentionally removed.
    # They are redundant supersets of "oversight" and "risk" respectively:
    # word-boundary matching (see _count_lexicon_hits) already counts
    # "oversight" inside "human oversight" and "risk" inside "high-risk"
    # (a hyphen is a word-boundary character), so keeping both the root
    # word and the compound phrase double-counted a single occurrence.
]

PRO_INNOVATION_WORDS = [
    "burden", "cost", "costs", "innovation", "startup", "startups",
    "compliance overhead", "stifle", "stifles", "flexibility", "market",
    "competitive", "competitiveness", "slow down", "slows down",
    "small teams", "small team", "proportionate", "proportionality",
    "red tape", "bureaucracy", "overregulation", "entrench", "incumbents",
]

# Phrases that signal a speaker is updating/conceding/softening their
# position -- reported as qualitative evidence, not scored numerically.
SHIFT_MARKER_PHRASES = [
    "you raise a good point", "i hadn't considered", "that said",
    "however, i", "on reflection", "i'm willing to concede",
    "i still maintain", "i remain convinced", "fair point",
    "i take your point", "which changes my thinking",
    "i'm now more open to", "i concede",
]


import re


def _assert_no_lexicon_overlaps(lexicon: list[str]) -> None:
    """
    Guard against reintroducing a double-counting bug: raise if any entry
    is a whole-word substring of another entry in the same lexicon (e.g.
    "oversight" inside "human oversight", or "risk" inside "high-risk" --
    a hyphen counts as a word boundary, so word-boundary matching alone
    does not prevent this class of overlap).
    """
    for a in lexicon:
        for b in lexicon:
            if a != b and re.search(r"\b" + re.escape(a) + r"\b", b):
                raise ValueError(
                    f"Lexicon overlap: '{a}' is a whole-word substring of "
                    f"'{b}', which would double-count a single occurrence. "
                    f"Remove one of the two entries."
                )


_assert_no_lexicon_overlaps(PRO_REGULATION_WORDS)
_assert_no_lexicon_overlaps(PRO_INNOVATION_WORDS)


def _count_lexicon_hits(lowered_text: str, lexicon: list[str]) -> int:
    """
    Count lexicon word/phrase occurrences using word-boundary regex matching
    instead of naive substring counting.

    Naive `text.count(word)` double-counts overlapping entries -- e.g. the
    single phrase "high-risk" would match both the "risk" entry AND the
    "high-risk" entry in PRO_REGULATION_WORDS, counting one occurrence as
    two hits. `\\b...\\b` word boundaries prevent a short entry from also
    matching inside a longer one it's a substring of.
    """
    return sum(
        len(re.findall(r"\b" + re.escape(term) + r"\b", lowered_text))
        for term in lexicon
    )


def score_message(text: str) -> dict:
    """
    Score a single message on the Pro-Innovation (-1) <-> Pro-Regulation
    (+1) axis using lexicon word-counting, plus detect any shift-marker
    phrases present.

    Returns:
        {
            "score": float | None,   # None if no stance words found at all
            "pro_reg_hits": int,
            "pro_innov_hits": int,
            "shift_markers_found": list[str],
        }
    """
    lowered = text.lower()

    pro_reg_hits = _count_lexicon_hits(lowered, PRO_REGULATION_WORDS)
    pro_innov_hits = _count_lexicon_hits(lowered, PRO_INNOVATION_WORDS)

    total = pro_reg_hits + pro_innov_hits
    score = None if total == 0 else (pro_reg_hits - pro_innov_hits) / total

    shift_markers_found = [p for p in SHIFT_MARKER_PHRASES if p in lowered]

    return {
        "score": score,
        "pro_reg_hits": pro_reg_hits,
        "pro_innov_hits": pro_innov_hits,
        "shift_markers_found": shift_markers_found,
    }


# ---------------------------------------------------------------------------
# 2. FIXED TRANSCRIPT — hand-written, no LLM involved.
#    Same personas/topic as the existing Week 2 demo (personas/persona_a.yaml,
#    personas/persona_b.yaml), extended into a 3-round discussion matching
#    the Week 3 shape (initial -> Round 1 -> Round 2 -> Round 3).
# ---------------------------------------------------------------------------

TOPIC = "Classifying Open Source Models under the EU AI Act"

TRANSCRIPT = {
    "Dr. Elena Kovac": {
        "initial": (
            "Open-source GPAI models must still face the same risk-based "
            "obligations as closed models. Without mandatory oversight and "
            "transparency requirements, we cannot protect the public from "
            "downstream harm just because a model's weights are public."
        ),
        "round_1": (
            "Marcus, I understand the cost burden concern, but safety cannot "
            "be optional. A high-risk classification triggers mandatory "
            "safeguards precisely because the risk of harm doesn't disappear "
            "just because the license is open."
        ),
        "round_2": (
            "You raise a good point about small teams lacking compliance "
            "staff. I'm willing to concede that a proportionate, "
            "tiered compliance requirement for smaller open-source "
            "maintainers could preserve accountability without the full "
            "enterprise-grade audit burden."
        ),
        "round_3": (
            "On reflection, a lighter-touch oversight tier for small "
            "open-source teams, combined with mandatory transparency "
            "reporting, protects the public while remaining proportionate. "
            "I still maintain that some baseline safeguard is non-negotiable."
        ),
    },
    "Marcus Chen": {
        "initial": (
            "Treating open-source GPAI models like commercial products "
            "ignores the reality that small teams like mine can't absorb "
            "enterprise-grade compliance overhead. This kind of red tape "
            "entrenches incumbents and stifles innovation."
        ),
        "round_1": (
            "Elena, the cost isn't hypothetical -- a full compliance audit "
            "could cost more than my startup's entire runway. Overregulation "
            "here just slows down small teams while large competitors absorb "
            "the burden easily."
        ),
        "round_2": (
            "I hadn't considered that a tiered system could separate "
            "genuinely high-risk deployments from small research releases. "
            "That said, the safeguards still need to be proportionate to "
            "team size, not just risk category."
        ),
        "round_3": (
            "I take your point that some baseline transparency reporting "
            "is reasonable -- that's a lot more workable than a full audit. "
            "I remain convinced the enforcement mechanism has to scale down "
            "for small teams, but a lighter oversight tier is a fair compromise."
        ),
    },
}

STAGES = ["initial", "round_1", "round_2", "round_3"]
STAGE_LABELS = ["Initial", "Round 1", "Round 2", "Round 3"]


# ---------------------------------------------------------------------------
# 3. SHIFT CLASSIFICATION
# ---------------------------------------------------------------------------

NO_SHIFT_THRESHOLD = 0.05  # deltas smaller than this count as noise, not a real move


def classify_shift(previous_score: float, current_score: float) -> str:
    """
    Classify a single round-over-round score change into one of four
    categories, independent of the lexicon-scoring mechanism itself:

        NO_SHIFT      -- change is within the no-shift threshold
        REVERSAL      -- crossed from positive to negative (or vice versa)
        STRENGTHENING -- moved further from 0 without crossing it
        WEAKENING     -- moved closer to 0 without crossing it
    """
    delta = current_score - previous_score
    if abs(delta) < NO_SHIFT_THRESHOLD:
        return "NO_SHIFT"
    if previous_score == 0:
        return "STRENGTHENING" if current_score > 0 else "WEAKENING"
    crossed_zero = (previous_score > 0) != (current_score > 0) and current_score != 0
    if crossed_zero:
        return "REVERSAL"
    moved_away_from_zero = abs(current_score) > abs(previous_score)
    return "STRENGTHENING" if moved_away_from_zero else "WEAKENING"


# ---------------------------------------------------------------------------
# 4. RUN THE ANALYSIS
# ---------------------------------------------------------------------------

def run_demo() -> dict:
    """Score the fixed transcript and print a per-agent opinion-shift report,
    including round-by-round deltas and shift classification.

    Returns a dict of {agent_name: [score_initial, score_r1, score_r2, score_r3]}
    for reuse (e.g. by a plotting script).
    """
    results = {}

    print("=" * 78)
    print(f"TOPIC: {TOPIC}")
    print("=" * 78)

    for agent, stages in TRANSCRIPT.items():
        print(f"\n--- {agent} ---")
        agent_scores = []
        agent_markers = []
        for stage_key, stage_label in zip(STAGES, STAGE_LABELS):
            text = stages[stage_key]
            result = score_message(text)
            agent_scores.append(result["score"])
            agent_markers.append(result["shift_markers_found"])

        print(f"{'Stage':10s} | {'Score':>7s} | {'Delta':>7s} | {'Classification':14s} | Markers present this round")
        for i, (stage_label, score) in enumerate(zip(STAGE_LABELS, agent_scores)):
            if i == 0:
                print(f"{stage_label:10s} | {score:+7.2f} | {'—':>7s} | {'(baseline)':14s} | "
                      f"{', '.join(agent_markers[i]) or '(none)'}")
            else:
                delta = score - agent_scores[i - 1]
                shift_type = classify_shift(agent_scores[i - 1], score)
                # Markers present in this round are reported alongside the
                # delta as a possible qualitative explanation for it -- the
                # score itself is computed purely from lexicon word counts,
                # NOT from the presence of these phrases. This is a
                # correlational annotation, not the scoring mechanism.
                print(f"{stage_label:10s} | {score:+7.2f} | {delta:+7.2f} | {shift_type:14s} | "
                      f"{', '.join(agent_markers[i]) or '(none)'}")

        results[agent] = agent_scores

    print("\n" + "=" * 78)
    print("OPINION SHIFT SUMMARY")
    print("=" * 78)
    for agent, scores in results.items():
        initial, final = scores[0], scores[-1]
        magnitude = abs(final - initial)
        direction = (
            "moved toward Pro-Innovation" if final < initial
            else "moved toward Pro-Regulation" if final > initial
            else "no net change"
        )
        deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
        max_shift_round = STAGE_LABELS[1 + deltas.index(max(deltas, key=abs))]
        print(
            f"{agent}: {initial:+.2f} -> {final:+.2f}  "
            f"(net shift = {magnitude:.2f}, {direction}; "
            f"largest single-round change occurred in {max_shift_round})"
        )

    return results


if __name__ == "__main__":
    run_demo()
