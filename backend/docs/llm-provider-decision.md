# LLM Provider Decision — Week 2 Agent Framework

## Context
Need an LLM that: generates persona-grounded opinions, reliably calls tools
(Neo4j `query_knowledge_base(topic)`), and stays affordable at multi-agent
scale, since Week 3 is going to multiply calls across agents and turns pretty
fast.

---

## Comparison

### 1. Local Hugging Face (Qwen2.5, via vLLM/TGI)
**Pros:** zero per-token cost once it's running, everything stays on our own
infra so no data leaves, no rate limits to worry about.
**Cons:** need to actually provision and babysit GPUs, tool-calling depends
on the chat template and isn't as solid as a first-party API, and scaling up
means more hardware, not just a config change.

### 2. DeepSeek V3 (via OpenRouter)
**Pros:** supports the standard `tools`/`tool_choice` schema, extremely
cheap (~$0.27 input / $1.10 output per M tokens), 128K context is plenty
for persona + memory + retrieved chunks, and swapping models later is just
a one-line change.

**Cons:** tool calls aren't as reliable as a first-party implementation
(needs validation + retry), there's an extra network hop through
OpenRouter, and default routing can land on Chinese-hosted infra unless we
set a provider preference.

### 3. Llama 3.1/3.3 (via Groq)
**Pros:** genuinely fast inference thanks to Groq's hardware, still uses
the OpenAI-style tools schema, weights are open so we're not locked into
Groq specifically, pricing is decent too.
**Cons:** Groq only serves a limited set of models, their tool-calling
support for Llama is newer and less battle-tested, and rate limits are
tighter than what we'd get from bigger providers.

---

## Decision
**Chosen: DeepSeek V3 (via OpenRouter)**

**Why:**
- Cost is really the deciding factor here — DeepSeek V3 is dramatically
  cheaper than the alternatives, and that matters a lot once Week 3 starts
  multiplying calls across every agent and turn.
- Tool calling does the job for the Neo4j retrieval requirement, as long as
  we validate the JSON and retry on malformed calls — a safety net we'd
  need with Groq or local hosting anyway.
- Going through OpenRouter means switching to Llama, Groq, or a local model
  later is just a config change, not a rewrite of the agent code.
- We're accepting a tradeoff here: giving up Groq's raw speed and the local
  setup's full data locality, in exchange for the best balance of cost and
  flexibility for where the project is right now.