# NLI Stance Grader — Optimization Notes

This document records every inference-time optimization applied to the
local NLI stance grader, across two files:

- `backend/src/orchestration/nli_grader.py` — `DebertaStanceGrader`
  (PyTorch backend, always available, no extra dependencies).
- `backend/src/orchestration/nli_onnx_grader.py` — `ONNXStanceGrader`
  (ONNX Runtime backend, optional, requires a **separate Python
  environment** — see Section 2.1a for why it can't share a `uv`-managed
  environment with the rest of this project).

And one script:

- `backend/src/scripts/benchmark_nli_backends.py` — measures latency
  and cross-backend consistency, so any decision to switch backends is
  based on a number, not on general reputation.

Scope: this covers **inference-time optimizations only**, not the
model choice itself (`cross-encoder/nli-deberta-v3-large`) — that
decision and its benchmarking are documented in
`docs/Influence-Tracking.md` (Section 3, Implementation Notes).

---

## 1. Optimizations implemented in `DebertaStanceGrader` (PyTorch)

### 1.1 `torch.inference_mode()` instead of `torch.no_grad()`

Strictly stronger than `no_grad()` — also skips autograd's
version-counter bookkeeping. No downside for pure inference; free win.

### 1.2 Batched inference (single forward pass per call)

PRO/ANTI hypothesis pairs for a statement, and (via `evaluate_batch()`)
every statement in a whole discussion round, go through the model in
one padded batch instead of one forward pass per hypothesis/agent.
Matters more with `-large` (~435M params) than it would with a lighter
model — the forward pass count, not the tokenizer/padding overhead, is
the bottleneck being cut.

### 1.3 FP16 on GPU, auto-enabled

`torch_dtype` defaults to `torch.float16` when `torch.cuda.is_available()`,
and `torch.float32` on CPU (where FP16 matmul isn't accelerated, so
there'd be a conversion cost for no benefit). This is the one
"quantization-adjacent" optimization enabled **by default**, because
unlike INT8/ONNX below it:
- needs no export step, no new dependency, and no separate model
  artifact to keep in sync with the HF checkpoint,
- is a long-established, low-risk technique for encoder classification
  models (unlike DeBERTa's disentangled-attention export/INT8-quantization
  risk profile — see Section 2),
- and the final softmax always runs on logits upcast to `float32`
  (`.logits.float()`), so FP16 only affects the matmul-heavy internals,
  not the precision-sensitive final probability computation.

Pass `dtype=torch.float32` explicitly to disable it (e.g. while
debugging a suspected precision issue).

### 1.6 Python `logging` instead of `print`

Standard `logging.getLogger(__name__)`, level-filterable and
container/production-log-aggregation friendly, unlike `print`.

### 1.7 Langfuse `evaluator`-typed tracing with span metadata

`@observe(as_type="evaluator", capture_input=False)` on both
`evaluate_stance()` and `evaluate_batch()`. `evaluator` is a real,
documented Langfuse observation type for "functions that assess
relevance/correctness of outputs" — distinct from the `generation` type
already used by `OpinionGrader`'s LLM call, correctly reflecting that
this grader isn't an LLM generation. Each call attaches `model`,
`device`, `pro_probability`, `anti_probability`, `current_stance_score`,
`shift_magnitude`, `latency_seconds` (plus `batch_size` and a per-agent
score summary for the batch variant) via a **single**
`get_client().update_current_span(...)` call right before returning —
not incrementally, since Langfuse's `@observe` decorator is known, in
some SDK versions, to drop or overwrite earlier mid-function
`update_current_span()`/`update_current_observation()` calls
(`langfuse/langfuse#7030`).

**Known risk to verify manually**: a separate Langfuse issue
(`langfuse-python#1676`) shows that combining `as_type=...` with
`capture_output=False` can silently downgrade the observation to
`type=span`. This code uses `capture_input=False` (not
`capture_output`), so the specific reported combination doesn't apply
directly — but this hasn't been confirmed against our pinned `langfuse`
version. Check the Langfuse UI after deployment that traces actually
show up typed `evaluator`.

---

## 2. ONNX export + dynamic INT8 quantization — now implemented, opt-in

Earlier drafts of this document deferred both entirely. They're now
implemented as a **separate, opt-in class** (`ONNXStanceGrader`), not
folded into `DebertaStanceGrader` or enabled by default. This section
explains what that means concretely and how to decide whether to
actually use it.

### 2.1 What's implemented

- `ONNXStanceGrader.__init__` exports `cross-encoder/nli-deberta-v3-large`
  to ONNX via `optimum.onnxruntime.ORTModelForSequenceClassification`
  (`export=True`) on first run, caches the result under
  `models/onnx/nli-deberta-v3-large/`, and reloads the cached artifact
  on subsequent runs instead of re-exporting.
- `quantize=True` (the default) applies **dynamic INT8 quantization**
  on top of the export, via `optimum.onnxruntime.ORTQuantizer` with
  `AutoQuantizationConfig.avx2(is_static=False, per_channel=False)` —
  the broadly-compatible default for x86 CPUs. `quantize=False` runs
  the exported FP32 ONNX graph as-is, which can still be faster than
  PyTorch on CPU from graph-level optimizations alone, with zero
  quantization accuracy risk.
- It reuses `DebertaStanceGrader._find_label_indices()` for label
  discovery, so both backends agree on which logit index means
  "entailment"/"contradiction" for this model — no duplicated lookup
  logic to drift out of sync.

### 2.1a Why this needs a separate environment (found the hard way)

`optimum[onnxruntime]` was originally added as a
`[project.optional-dependencies]` extra in this project's
`pyproject.toml`. That does not work, and had to be reverted:

- Every published version of `optimum[onnxruntime]` (1.23 through the
  current 2.x line, checked at the time of writing) pins
  `transformers<4.58` or tighter.
- This project's `sentence-transformers>=6.0.0` requires
  `transformers>=5.0.0`.
- Those two constraints are mutually exclusive — no version of
  `optimum[onnxruntime]` can currently be installed alongside
  `sentence-transformers>=6.0.0` in the same environment, full stop.
- Worse: `uv` resolves a *universal* lockfile covering every declared
  extra, so simply having an unsatisfiable `onnx` extra in
  `pyproject.toml` broke `uv sync` for the **entire project**, even for
  someone who never requested `--extra onnx`. This is not a corner case
  to work around; it had to be removed from `pyproject.toml` entirely.

**The fix**: `ONNXStanceGrader` and `benchmark_nli_backends.py` are run
from a completely separate Python environment (a plain `venv`, not
managed by this project's `uv`/`pyproject.toml` at all), installed with
plain `pip install torch transformers optimum[onnxruntime] langfuse` —
nothing else from this project's dependency list, since neither file
imports `sentence-transformers` or anything else that would reintroduce
the conflict. See the project's setup notes for the exact commands.

This is also *why* `ONNXStanceGrader` was written as a fully
self-contained file that only imports `nli_grader.py` (for
`DEFAULT_NLI_MODEL` and the shared `_find_label_indices` staticmethod)
and `stance_utils.py` — not anything from `src.rag` or other modules
that pull in `sentence-transformers` transitively.

### 2.2 Why it's opt-in, not the default

- **Export/quantization correctness risk is model-specific, not
  generic.** DeBERTa-v2/v3's disentangled attention mechanism uses
  custom ops that have historically been more finicky to export and
  quantize cleanly than a standard BERT-style encoder. "ONNX export
  usually works" is true in general and is not itself evidence that it
  produces the same entailment probabilities *for this model* — that
  has to be checked, not assumed.
- **Whether it's actually faster depends on the deployment target**,
  which still isn't fixed: `DebertaStanceGrader` was only wired into
  `DiscussionEngine` behind the `STANCE_GRADER_ENGINE` flag recently,
  and nothing has been deployed yet to know if it runs on CPU or GPU in
  practice. ONNX Runtime's main advantage is CPU inference; on GPU,
  Section 1.5's FP16 path is usually competitive or better with far
  less integration risk.
- **INT8 quantization trades numerical precision for speed by
  definition** — the question isn't "is INT8 fast" (yes), it's "is the
  resulting entailment-probability drift small enough that
  `stance_utils.compute_stance_score` still produces materially the
  same stance score and shift for real statements." That's a measured
  question, not a theoretical one.

### 2.3 How to actually decide: `benchmark_nli_backends.py`

```bash
# In a SEPARATE venv, not this project's uv-managed one -- see Section 2.1a.
pip install torch transformers "optimum[onnxruntime]" langfuse
# Then, from backend/, with that separate venv active:
python -m src.scripts.benchmark_nli_backends
```

The script loads whichever of these backends are available —
PyTorch FP32 (baseline), PyTorch auto-precision (FP16 on CUDA / FP32 on
CPU), ONNX FP32, ONNX INT8 — runs a small set of representative pro /
anti / hedged statements through each (with warmup runs excluded from
timing), and reports, per backend:

- average per-statement latency (ms), and
- max absolute difference in entailment probability vs. the PyTorch
  FP32 baseline, across all test statements.

**Decision rule**: only make a non-baseline backend the actual default
(via `STANCE_GRADER_ENGINE`/swapping which grader `DiscussionEngine`
instantiates) if, on the real target deployment hardware, it is
*meaningfully* faster **and** its max probability difference is small
enough that `stance_utils.compute_stance_score` would round to the same
`current_stance_score` for these statements. A faster backend with a
large probability difference isn't a free win — it's a different,
unvalidated stance signal wearing the same interface.

If ONNX/INT8 turns out not to help (e.g. the grader ends up running on
GPU, where FP16 already covers the same ground with less risk), that's
a valid, evidence-based outcome of running the benchmark — not a reason
to have skipped building it.

### 2.3a Results (RTX 3050, 4GB VRAM, driver CUDA 13.0)

Actual `benchmark_nli_backends.py` output on real target hardware:

| Backend | Avg latency/stmt | Max prob diff vs. baseline |
|---|---|---|
| `pytorch_fp32` (baseline, GPU) | 49.45 ms | — |
| `pytorch_auto` (FP16, GPU) | 51.12 ms | 0.0020 |
| `onnx_fp32` (CPU) | 163.31 ms | 0.0000 |
| `onnx_int8` (CPU) | 154.23 ms | **0.3899** |

**Conclusion for this hardware: do not adopt ONNX or INT8. Keep the
PyTorch/GPU backend as the live engine.**

- `pytorch_auto` (FP16) is numerically safe (0.002 diff — negligible)
  but is not measurably faster here (in fact marginally slower on this
  small model/batch size). Its only real benefit on this hardware is
  lower VRAM usage, relevant given the 4GB card, not latency.
- Both ONNX backends run ~3x slower than the GPU backends simply
  because they're CPU-bound while a working GPU is available — ONNX's
  CPU-latency advantage never gets a chance to matter here.
- `onnx_int8`'s 0.3899 max probability difference **confirms, not just
  theorizes, the DeBERTa disentangled-attention quantization risk**
  flagged in Section 2.2 — a difference that large can flip which side
  (pro/anti) a statement scores toward, or swing
  `stance_utils.compute_stance_score` by multiple points. This is
  exactly the "faster backend, unvalidated signal" failure mode the
  decision rule exists to catch, and it did.

This result is specific to this hardware/workload (small batches, a
GPU with enough VRAM headroom for FP16). It doesn't mean ONNX/INT8 are
never worth it elsewhere — a CPU-only deployment with no GPU at all
would be a genuinely different comparison — but it does mean neither
should be adopted here, on this project's actual current hardware,
based on this measurement.

### 2.4 Not implemented

- **Static (calibration-based) quantization.** Dynamic quantization
  needs no calibration dataset and is the standard first thing to try
  for encoder classification models. Static quantization is a further,
  riskier step with its own calibration-set-selection questions — not
  worth adding until the benchmark shows dynamic quantization is
  insufficient.
- **Re-benchmarking the model choice itself** (`-large` vs. other
  checkpoints). Out of scope here — see `Influence-Tracking.md`.

---
