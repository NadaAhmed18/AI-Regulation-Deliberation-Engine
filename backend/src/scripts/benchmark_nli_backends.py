# Run from backend/: python -m src.scripts.benchmark_nli_backends
#
# Compares the available NLI stance-grading backends on latency and
# entailment-probability consistency, so that switching
# STANCE_GRADER_ENGINE (or adopting ONNXStanceGrader) is a decision
# based on measurement, not on general reputation ("INT8 is faster",
# "ONNX is faster on CPU") in the abstract.
#
# See docs/NLI-Grader-Optimizations.md for how to read this script's
# output and the recommended decision rule.

import time
from typing import Any, Dict, List, Optional, Tuple

from src.orchestration.nli_grader import DEFAULT_NLI_MODEL, DebertaStanceGrader
import torch
# A small, deliberately varied set of test statements: clearly pro,
# clearly anti, and one hedged/mixed statement, so consistency is
# checked across the range of confidence levels the real grader will
# actually see -- not just easy, high-confidence cases.
TEST_STATEMENTS: List[Tuple[str, str]] = [
    (
        "mandatory licensing for high-compute AI models",
        "We cannot allow unrestricted open weights when national security risks "
        "are real. Strict oversight, licensing, and compliance protocols must be "
        "mandatory.",
    ),
    (
        "mandatory licensing for high-compute AI models",
        "Licensing regimes like this just entrench incumbents and slow down "
        "the open-source ecosystem that actually drives safety research forward.",
    ),
    (
        "mandatory licensing for high-compute AI models",
        "There are reasonable arguments on both sides here, and I think it "
        "depends heavily on how the compute threshold is actually set.",
    ),
]

HYPO_PRO_TEMPLATE = "The speaker is in favor of {topic}."
HYPO_ANTI_TEMPLATE = "The speaker is opposed to {topic}."

WARMUP_RUNS = 2
TIMED_RUNS = 5


def _time_backend(name: str, score_fn) -> Optional[Dict[str, Any]]:
    """
    Run `score_fn(topic, statement) -> (prob_pro, prob_anti)` over
    every entry in TEST_STATEMENTS, `WARMUP_RUNS` untimed passes first
    (JIT / cudnn autotune / ORT session warmup), then `TIMED_RUNS` timed
    passes averaged per statement.
    """
    try:
        for _ in range(WARMUP_RUNS):
            for topic, statement in TEST_STATEMENTS:
                score_fn(topic, statement)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any backend failure just gets skipped
        print(f"[SKIPPED] {name}: failed during warmup ({type(exc).__name__}: {exc})")
        return None

    per_statement_probs: List[Tuple[float, float]] = []
    latencies_ms: List[float] = []

    try:
        for topic, statement in TEST_STATEMENTS:
            start = time.perf_counter()
            for _ in range(TIMED_RUNS):
                prob_pro, prob_anti = score_fn(topic, statement)
            elapsed_ms = (time.perf_counter() - start) / TIMED_RUNS * 1000
            latencies_ms.append(elapsed_ms)
            per_statement_probs.append((prob_pro, prob_anti))
    except Exception as exc:  # noqa: BLE001
        print(f"[SKIPPED] {name}: failed during timed run ({type(exc).__name__}: {exc})")
        return None

    return {
        "name": name,
        "avg_latency_ms": sum(latencies_ms) / len(latencies_ms),
        "per_statement_probs": per_statement_probs,
    }


def _max_prob_diff(baseline_probs, other_probs) -> float:
    """Max absolute difference in either pro or anti probability, across all test statements."""
    diffs = []
    for (b_pro, b_anti), (o_pro, o_anti) in zip(baseline_probs, other_probs):
        diffs.append(abs(b_pro - o_pro))
        diffs.append(abs(b_anti - o_anti))
    return max(diffs)


def run_benchmark() -> None:
    results: List[Dict[str, Any]] = []

    # --- Backend 1: PyTorch FP32 (the accuracy baseline) ---
    print("\n[*] Loading PyTorch FP32 backend (baseline)...")
    pt_fp32 = DebertaStanceGrader(model_name=DEFAULT_NLI_MODEL, dtype=torch.float32)    
    res = _time_backend(
        "pytorch_fp32",
        lambda topic, statement: pt_fp32._score_pairs(
            premises=[statement, statement],
            hypotheses=[
                HYPO_PRO_TEMPLATE.format(topic=topic),
                HYPO_ANTI_TEMPLATE.format(topic=topic),
            ],
        ),
    )
    if res:
        results.append(res)
    baseline = res  # everything else is compared against this, if it loaded

    # --- Backend 2: PyTorch auto (FP16 on CUDA, FP32 on CPU) ---
    print("\n[*] Loading PyTorch auto-precision backend...")
    pt_auto = DebertaStanceGrader(model_name=DEFAULT_NLI_MODEL)
    res = _time_backend(
        f"pytorch_auto (dtype={pt_auto.dtype}, device={pt_auto.device})",
        lambda topic, statement: pt_auto._score_pairs(
            premises=[statement, statement],
            hypotheses=[
                HYPO_PRO_TEMPLATE.format(topic=topic),
                HYPO_ANTI_TEMPLATE.format(topic=topic),
            ],
        ),
    )
    if res:
        results.append(res)

    # --- Backend 3 & 4: ONNX (FP32 and INT8), only if `optimum` is installed ---
    try:
        from src.orchestration.nli_onnx_grader import ONNXStanceGrader

        print("\n[*] Loading ONNX FP32 backend (export may take a minute on first run)...")
        onnx_fp32 = ONNXStanceGrader(model_name=DEFAULT_NLI_MODEL, quantize=False)
        res = _time_backend(
            "onnx_fp32",
            lambda topic, statement: onnx_fp32._score_pairs(
                premises=[statement, statement],
                hypotheses=[
                    HYPO_PRO_TEMPLATE.format(topic=topic),
                    HYPO_ANTI_TEMPLATE.format(topic=topic),
                ],
            ),
        )
        if res:
            results.append(res)

        print("\n[*] Loading ONNX INT8 (dynamic quantized) backend...")
        onnx_int8 = ONNXStanceGrader(model_name=DEFAULT_NLI_MODEL, quantize=True)
        res = _time_backend(
            "onnx_int8",
            lambda topic, statement: onnx_int8._score_pairs(
                premises=[statement, statement],
                hypotheses=[
                    HYPO_PRO_TEMPLATE.format(topic=topic),
                    HYPO_ANTI_TEMPLATE.format(topic=topic),
                ],
            ),
        )
        if res:
            results.append(res)
    except ImportError:
        print(
            "\n[SKIPPED] ONNX backends: 'optimum[onnxruntime]' not installed. "
            "Install with `uv sync --extra onnx` to include them in this comparison."
        )

    # --- Report ---
    print("\n" + "=" * 78)
    print(" NLI BACKEND COMPARISON ".center(78, "="))
    print("=" * 78)
    print(f"{'Backend':<45}{'Avg latency/stmt (ms)':>20}{'Max prob diff':>13}")
    print("-" * 78)
    for r in results:
        if baseline and r["name"] != baseline["name"]:
            diff = _max_prob_diff(baseline["per_statement_probs"], r["per_statement_probs"])
            diff_str = f"{diff:.4f}"
        else:
            diff_str = "baseline"
        print(f"{r['name']:<45}{r['avg_latency_ms']:>20.2f}{diff_str:>13}")
    print("=" * 78)

    print(
        "\nDecision rule: only adopt a non-baseline backend as the default if it "
        "is meaningfully faster on YOUR target hardware AND its max prob diff is "
        "small enough that stance_utils.compute_stance_score would round to the "
        "same current_stance_score for these statements. A faster backend with a "
        "large prob diff is not a free win -- it's a different (and unvalidated) "
        "stance signal."
    )


if __name__ == "__main__":
    run_benchmark()
