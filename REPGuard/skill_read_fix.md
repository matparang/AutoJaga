## SKILL FILE READING RULE
# Add to AGENTS.md immediately.
# This fixes the "shows file instead of explaining" bug.

---

## 📖 SKILL FILE READING PROTOCOL

When you read a SKILL.md or any documentation file,
you MUST synthesise it into plain language.

NEVER show the raw file content as your response.
The file is your reference — not your answer.

### The Rule

After read_file on ANY .md file:
1. Read it internally (your reference)
2. Close the file mentally
3. Answer the user's question IN YOUR OWN WORDS
4. Never paste the file content back to the user

### Examples

❌ WRONG:
User: "check YOLO mode"
Agent: read_file(SKILL.md) → pastes raw markdown back

✅ CORRECT:
User: "check YOLO mode"  
Agent: read_file(SKILL.md) → synthesises → explains in plain words
"YOLO mode is AutoJaga's autonomous research mode.
 When you trigger it, I plan and execute a full research
 pipeline without asking for confirmation at each step..."

---

## 🔁 REPETITION DETECTION RULE

If you have already called a tool in this session
and the user asks a clarifying question — DO NOT
call the same tool again.

You already have the information. Use it.

### Examples

❌ WRONG:
Turn 1: User asks → Agent calls read_file(X)
Turn 2: User asks "explain" → Agent calls read_file(X) AGAIN
Turn 3: User asks "in words" → Agent calls read_file(X) AGAIN

✅ CORRECT:
Turn 1: User asks → Agent calls read_file(X) → explains
Turn 2: User asks "explain more" → Agent uses info already read
        DO NOT re-read the file
        DO NOT call any tool
        Just answer in plain language

### The Check

Before calling any tool, ask:
"Have I already called this tool with these same arguments
in this session?"

If YES → use the cached result, do not call again.
If NO  → call the tool.

---

## 📝 "EXPLAIN TO ME" PATTERN

When user says any of these after a tool call:
- "explain to me"
- "explain in words"  
- "what does that mean"
- "in plain language"
- "can you explain"
- "tell me what that says"

This means: synthesise what you already know into plain words.
DO NOT read any file again.
DO NOT call any tool.
Just explain using information you already have.

