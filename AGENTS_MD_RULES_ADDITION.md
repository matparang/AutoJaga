# AGENTS.md ADDITION — Response Mode Rules

**Add this section to your existing `AGENTS.md` or `SOUL.md`.**

**Place it near the top — BEFORE any financial analysis rules.**

This immediately stops the exec-on-explain behavior without touching any code.

---

## 🧠 RESPONSE MODE — CRITICAL RULES

### When to EXPLAIN (never use exec)

If the user's message matches ANY of these patterns, respond in plain language ONLY. Never run exec. Never write files.

**Question patterns that mean EXPLAIN:**

- Starts with: "do you", "can you", "what is", "what are"
- Starts with: "how do", "how does", "how did", "how can"
- Starts with: "explain", "describe", "tell me", "show me how"
- Starts with: "why", "when", "where", "who"
- Contains: "don't execute", "just answer", "no code"
- Contains: "explain to me", "in plain language", "in english"
- About YOUR OWN capabilities: "do you have X", "can you do X"
- About YOUR OWN architecture: "how does your X work"

**For these questions:**

- ✅ Answer directly in structured NLP
- ✅ Use bullet points, tables, headers
- ✅ Reference tools by name without calling them
- ✅ Use illustrative examples with made-up numbers (label them clearly as "e.g." or "example:")
- ❌ NEVER call exec to verify a conceptual answer
- ❌ NEVER write files to prove a capability exists
- ❌ NEVER generate random numpy data to demonstrate a point

---

### When to EXECUTE (use exec + write_file)

Only use exec when the user provides REAL data to compute:

- Actual numbers, datasets, or file paths given by user
- Explicit request: "calculate", "compute", "run", "execute"
- Code that must produce verified numerical output
- File operations the user explicitly requested

**Examples:**

- ✅ "Calculate IPW for this dataset: [actual data]"
- ✅ "Run a monte carlo simulation with these parameters"
- ✅ "Execute this python script"
- ❌ "Do you support monte carlo?" → **EXPLAIN, don't run it**
- ❌ "How does IPW work?" → **EXPLAIN, don't demo it with random data**

---

### The Core Rule

> If you are answering a question ABOUT yourself or your capabilities, you do NOT need to prove it with code. Your explanation IS the answer. Running exec to verify a capability description adds zero value and often triggers safety guards or audit failures.

---

### Illustrative Numbers in Explanations

When explaining concepts, you may use example numbers. Always label them clearly so the epistemic auditor ignores them:

**✅ CORRECT:**

- "For example, if Bear accuracy improved from 0.61 → 0.79 (illustrative)"
- "e.g. confidence score of 0.82 (example value, not from actual run)"

**❌ WRONG:**

- "Bear accuracy improved from 0.61 → 0.79" (no label = auditor flags as unverified financial claim)

**This single habit eliminates most epistemic audit rejections on conceptual responses.**
