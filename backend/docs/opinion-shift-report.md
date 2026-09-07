# Opinion Shift Analytics — Research & Prototype

## 1. Status

This document and `src/research/opinion_shift_prototype.py` are **research
prep for Week 4**, not the final "Opinion Shift Tracker" (`tracker.py` per
the project architecture diagram). The goal was to validate the underlying
analytics concept — can opinion shift across a multi-round discussion be
detected and quantified? — using a hand-written, fixed transcript and zero
API/model calls, before wiring the real thing up to a live Week 3
discussion engine.

## 2. Sentiment Analysis vs. Stance Detection

These are frequently confused but answer different questions:

| | Question it answers |
|---|---|
| **Sentiment analysis** | Is this text positive or negative in tone? |
| **Stance detection** | Is this text for or against a *specific target*? |

Opinion shift tracking for this project needs **stance**, not sentiment:
what matters is whether an agent is moving toward "Pro-Regulation" or
"Pro-Innovation" on a specific topic, not whether its tone is upbeat or
downbeat.

## 3. Methods Surveyed

| Method | Approach | Requires LLM/ML? |
|---|---|---|
| Stance classification per message | Classify each message as pro/con/neutral toward a target | Usually (BERT/LLM) |
| Stance-change classifier | Classify each consecutive message pair as agree/disagree/same | Usually LLM |
| Numeric stance score trajectory | A -1..+1 score per message, tracked over time | Can be done without either |
| **Lexicon-based scoring (used here)** | Count target-specific words per side, compute a ratio | No — a fixed word list |

Lexicon-based scoring is the same core technique lexicon-based sentiment
tools (VADER, TextBlob) use for generic polarity — applied here to a
stance-specific lexicon instead of a positive/negative one.

## 4. Method Used in This Prototype

Each message is scored from **-1.0 (fully Pro-Innovation)** to **+1.0
(fully Pro-Regulation)**:

```
score = (pro_reg_hits - pro_innov_hits) / (pro_reg_hits + pro_innov_hits)
```

`pro_reg_hits` / `pro_innov_hits` count occurrences of words from two
fixed lexicons (`PRO_REGULATION_WORDS`, `PRO_INNOVATION_WORDS`) in
`src/research/opinion_shift_prototype.py`, using **word-boundary regex
matching** (`_count_lexicon_hits`) rather than naive substring counting.
Naive substring counting (`text.count(word)`) double-counts whenever one
lexicon entry is contained inside another — e.g. a single occurrence of
"high-risk" would match both a "risk" entry and a "high-risk" entry. Word
boundaries fix this for suffix cases (e.g. "safeguard" vs. "safeguards")
but *not* for compound phrases where a hyphen or space separates a
shorter entry from a longer one that contains it (e.g. "oversight" is
still a separate word inside "human oversight"). The lexicon is therefore
also pruned to remove any entry that is a whole-word substring of another
entry in the same list, and `_assert_no_lexicon_overlaps()` runs
automatically at import time to catch a reintroduced overlap immediately
rather than silently double-counting again.

A separate list of hedging/concession phrases (`SHIFT_MARKER_PHRASES` —
e.g. "you raise a good point", "on reflection", "I'm willing to concede")
is matched per message and reported **alongside** the numeric score as
qualitative, correlational evidence — it plays no role in computing the
score itself (see the precision note in Section 6).

### 4a. Shift Classification

Each round-over-round score change is classified by `classify_shift()`
into one of four categories, independent of the scoring mechanism:

| Category | Meaning |
|---|---|
| `NO_SHIFT` | Change is below a small threshold (treated as noise) |
| `REVERSAL` | Score crossed from positive to negative, or vice versa |
| `STRENGTHENING` | Moved further from 0 without crossing it |
| `WEAKENING` | Moved closer to 0 without crossing it |

This distinguishes "opinion strength" changes (e.g. Strongly-Pro →
Moderately-Pro) from an actual reversal of position — a distinction
conversational stance-detection research treats as meaningfully
different phenomena (see References).

## 5. Fixed Transcript Used

A hand-written, 3-round discussion between the two existing Week 2
personas (`personas/persona_a.yaml` — Dr. Elena Kovac, Pro-Regulation;
`personas/persona_b.yaml` — Marcus Chen, Pro-Innovation) on the same
topic as the existing Week 2 demo output: *"Classifying Open Source
Models under the EU AI Act."* No LLM or API call is involved — every
message is written directly in the script.

## 6. Result (verified against actual script output — see Section 9)

| Agent | Initial | Round 1 | Round 2 | Round 3 | Net Shift | Direction |
|---|---|---|---|---|---|---|
| Dr. Elena Kovac | +1.00 | +0.50 | +0.00 | +0.60 | 0.40 | Net move toward Pro-Innovation |
| Marcus Chen | -1.00 | -0.75 | +0.50 | +0.60 | 1.60 | Net move toward Pro-Regulation |

Round-by-round classification (`classify_shift()` — see Section 4a):

| Agent | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| Dr. Elena Kovac | WEAKENING (Δ -0.50) | WEAKENING (Δ -0.50) | STRENGTHENING (Δ +0.60) |
| Marcus Chen | WEAKENING (Δ +0.25) | **REVERSAL** (Δ +1.25) | STRENGTHENING (Δ +0.10) |

Marcus's Round 2 message is the single largest move in the transcript and
is classified as a **reversal** (his score crosses from negative to
positive), not just a large weakening.

**Important precision note:** the score itself is computed purely from
lexicon word counts (Section 4) — it does not use the shift-marker phrases
at all. The shift-marker phrases found in Round 2 for both agents ("you
raise a good point", "i hadn't considered") are reported *alongside* the
score as a **correlational, qualitative annotation** — a plausible
explanation for why the score moved — not as part of the scoring
mechanism itself. Presenting these two things as if one caused the other
would overstate what the lexicon scorer actually does.

## 7. Known Limitation

This is naive word-counting: it does not handle **negation or context**.
For example, Marcus's Round 2 message ("the safeguards still need to be
proportionate...") still counts "safeguards" as a Pro-Regulation hit even
though he is qualifying, not endorsing, it. This is a well-documented
weakness of lexicon-based methods in general (see references), not
specific to this prototype.

For a production version, two paths forward:

1. Add negation handling: words like "not", "less", "reduce" preceding a
   lexicon word should flip or dampen its contribution.
2. Move to an LLM/classifier-based stance judgment for real discussion
   transcripts, once Week 3's discussion engine produces real messages.

## 8. How This Maps to the Real Week 4 Pipeline

```
transcript (from the Week 3 discussion engine)
       │
       ▼
score_message() per message   ← this prototype's core function
       │
       ▼
opinion_history[agent] = [scores across rounds]
       │
       ▼
classify_shift() per round-over-round pair   ← NO_SHIFT / WEAKENING /
       │                                        STRENGTHENING / REVERSAL
       ▼
shift_magnitude = |final_score - initial_score|
       │
       ▼
visualization (line chart of stance over rounds)
```

The real `tracker.py` will consume actual discussion output (real
messages generated by real agents across real rounds) instead of the
fixed transcript here, and can either keep this lexicon approach (with
negation handling added) or upgrade to an LLM-based stance classifier if
accuracy on real, less-scripted text proves insufficient.

## 9. Running This Prototype

```bash
cd backend
python -m src.research.opinion_shift_prototype
```

No environment variables, API keys, or live services are required — the
transcript, lexicon, and scoring logic are all self-contained in the
script.

## 10. References

1. Hutto, C., & Gilbert, E. (2014). *VADER: A Parsimonious Rule-Based
   Model for Sentiment Analysis of Social Media Text.* Proceedings of
   the International AAAI Conference on Web and Social Media, 8(1),
   216–225. https://doi.org/10.1609/icwsm.v8i1.14550
   — Source for the lexicon-based scoring formula pattern (sum/count of
   matched lexicon terms) adapted here from generic sentiment polarity
   to stance-specific polarity.

2. Ding, Y., He, K., Li, B., Zheng, L., He, H., Li, F., Teng, C., & Ji, D.
   (2025). *Zero-Shot Conversational Stance Detection: Dataset and
   Approaches.* Findings of the Association for Computational
   Linguistics: ACL 2025, 3221–3235.
   https://aclanthology.org/2025.findings-acl.168/
   — Source for treating conversational stance as something that evolves
   across turns rather than being fixed per isolated message.

3. Niu, F., Yang, M., Li, A., Zhang, B., Peng, X., & Zhang, B. (2024).
   *A Challenge Dataset and Effective Models for Conversational Stance
   Detection.* Proceedings of LREC-COLING 2024, 122–132.
   — Source for multi-turn conversational stance detection as a distinct
   task from single-utterance stance classification.

4. *A survey of stance detection on social media: New directions and
   perspectives in the era of large language models.* Expert Systems
   with Applications, 283 (2025), Article 127790.
   — General survey distinguishing stance detection from sentiment
   analysis, and cross-target/zero-shot stance detection approaches.

5. Niu, F., Dai, G., Lu, Y., Liao, J., Li, X., Huang, H., & Zhang, B.
   (2025). *MT2-CSD: A new dataset and multi-semantic knowledge fusion
   method for conversational stance detection.* arXiv:2506.21053.
   — Source for multi-turn, multi-target stance dynamics and the
   observation that stance can be "expressed, negotiated, and sometimes
   reversed through interaction."

Negation/context handling as the primary accuracy limitation of
lexicon-based methods in general (Section 7) is a widely repeated
observation across the lexicon-based sentiment analysis literature
building on Hutto & Gilbert (2014) above, rather than a single
citable claim.
