# LLM Provider Decision — Week 2 Agent Framework

## Context

The agent framework needs an LLM that can: (1) generate persona-grounded
opinions, (2) reliably call **tools/functions** — required, since Week 1's
retrieval system is exposed as a Neo4j tool (`query_knowledge_base(topic)`),
and (3) stay affordable at multi-agent scale (Week 3 multiplies calls
across agents and turns).

---

## Comparison

### 1. Anthropic (Claude)

**Pros:** first-class, well-documented tool-use API; strong persona
adherence and instruction-following; large context window; single stable
SDK, easy to debug.

**Cons:** single-vendor lock-in; ~$5/$25 per M tokens (input/output) —
meaningfully pricier than open-weight options at scale.

### 2. OpenRouter (gateway to Claude/GPT/Llama/etc.)

**Pros:** one API/key for many models; OpenAI-compatible `tools` schema;
easy to swap models later without touching the agent code.

**Cons:** extra network hop; reliability/latency depends on whichever
model is routed to; pricing is just a pass-through of the underlying
model, so no inherent savings.

### 3. xAI Grok (grok-3 / grok-4)

**Pros:** supports function calling with an OpenAI-compatible `tools`
schema; low reported latency; 128K context.

**Cons:** ~$3/$15 per M tokens — comparable to or pricier than Claude;
smaller tool-calling ecosystem; less predictable availability during
rollout phases.

### 4. DeepSeek V3 (via OpenRouter)

**Pros:** function calling officially supported (OpenAI-style
`tools`/`tool_choice`); very low cost (~$0.27/M input, $0.07/M on cache
hit, ~$1.10/M output — 5–20x cheaper than Claude/Grok); competitive
quality (benchmarks near Claude 3.5 Sonnet/GPT-4o); 128K context; routed
through OpenRouter for easy model-swapping later.

**Cons:** tool-calling less reliable than first-party Claude/OpenAI APIs
(DeepSeek Reasoner silently drops to Chat mode when `tools` is used);
extra OpenRouter hop/markup; default routing may hit Chinese-hosted
infrastructure (data-residency/content-filtering considerations unless a
provider preference is set); smaller cookbook/tutorial ecosystem; latency
depends on whichever backend OpenRouter selects.

---

## Decision

**Chosen: OpenRouter → `deepseek/deepseek-chat` (DeepSeek V3)**

**Why:**
- **Cost** is the deciding factor — DeepSeek V3 is roughly 5–20x cheaper
  than Claude or Grok, which matters once Week 3 multiplies calls across
  many agents and turns.
- **Tool calling works** via the standard `tools`/`tool_choice` schema,
  covering the Neo4j retrieval requirement, though it's less reliable
  than Claude's first-party tool use — mitigated by validating tool-call
  JSON before executing it and re-prompting on malformed calls.
- **OpenRouter routing** keeps a single OpenAI-compatible interface, so
  swapping to Claude/Grok/another model later is a one-line config change,
  not a rewrite.
- **Quality/context** are sufficient: DeepSeek-V3 benchmarks competitively
  with Claude 3.5 Sonnet, and 128K context comfortably fits persona +
  memory + retrieved chunks.
- **Trade-off accepted:** we prioritize cost and flexibility over Claude's
  marginally higher tool-calling reliability.