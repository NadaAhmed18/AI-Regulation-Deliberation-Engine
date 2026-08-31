# LLM Provider Decision — Week 2 Agent Framework

## Comparison 

### 1. Local Qwen2.5 (self-hosted via vLLM/TGI)
**Pros:** zero per-token cost once it's running, everything stays on our own
infra so no data leaves, no rate limits to worry about.
**Cons:** need to actually provision and babysit GPUs, tool-calling depends
on the chat template and isn't as solid as a first-party hosted API, and
scaling up means more hardware, not just a config change.

### 2. Llama 3.1 8B Instruct
**Pros:** by far the cheapest token price of anything here — about
**$0.02 / M input, $0.04 / M output** — and open weights mean no
provider lock-in.
**Cons:** the default OpenRouter endpoint for this model **does not accept
`tools` / `tool_choice`** — function calling is unavailable on it. That's
disqualifying on its own for our Neo4j retrieval requirement unless we route
to a specific provider (e.g. Groq's hosted endpoint) that adds tool support,
which reintroduces the reliability/rate-limit tradeoffs of a smaller
provider. An 8B model is also a real capability step down for
persona-grounded reasoning, independent of tooling.

### 3. Llama 3.3 70B Instruct
**Pros:** solid, well-tested tool-calling support (`tools`/`tool_choice`),
open weights, 131K context, reasonable pricing at **$0.10 / M input,
$0.32 / M output**.
**Cons:** meaningfully more expensive than DeepSeek V4 Flash below, and a
70B dense model is slower per-token than the MoE options.


### 4. DeepSeek V4 Flash 0423
**Pros:** cheapest model that still has solid, documented tool-calling
support — **$0.068 / M input, $0.168 / M output** — a 1,048,576-token
context window (plenty of headroom for persona + memory + retrieved
chunks), and explicit `tools`/`tool_choice` + JSON-schema structured
output support on OpenRouter.
**Cons:** it's a newer model with less real-world track record than Llama,
default routing can land on a mix of providers so it's worth pinning a
provider preference for consistency, and as a MoE "flash" model it may trade
a bit of raw reasoning depth for speed/cost compared to a larger dense model
like Llama 3.3 70B.

*(Note: the older DeepSeek V3 — ~$0.27 input / $1.10 output per M tokens —
is no longer the right reference point; V4 Flash supersedes it and is
roughly 4-6x cheaper.)*

---

## Decision
**Chosen: DeepSeek V4 Flash 0423 (via OpenRouter)**

**Why:**
- It's the cheapest model on the list that still has reliable, documented
  tool-calling support. Llama 3.1 8B is cheaper on paper, but its default
  endpoint can't call tools at all, which rules it out for the Neo4j
  retrieval requirement.
- Compared to the other tool-capable options (Llama 3.3 70B, Qwen2.5 72B),
  it's meaningfully cheaper on both input and output tokens — this matters
  a lot once Week 3 starts multiplying calls across every agent and turn.
- The 1M-token context window gives us far more headroom than Qwen2.5 72B's
  32K ceiling for stuffing persona + memory + retrieved chunks into a
  single call.
- We're accepting a tradeoff: less production track record than Llama, and
  a "flash" model may not match a large dense model's reasoning depth on
  the hardest cases. We'll validate/retry on malformed tool calls as a
  safety net regardless of which model we pick.
- Because everything routes through OpenRouter, switching to Llama 3.3 70B,
  Qwen, or a self-hosted model later is a config change, not a rewrite of
  the agent code.

**Fallback:** if DeepSeek V4 Flash's tool-calling reliability turns out to
be shakier in practice than advertised, Llama 3.3 70B is the next-best pick
— proven tool support, still open weights, at roughly 1.5-2x the cost.

---
