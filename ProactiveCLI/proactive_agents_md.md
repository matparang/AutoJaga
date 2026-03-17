## PROACTIVE RESPONSE PROTOCOL
# Add this section to AGENTS.md immediately.
# This is the fastest fix — no code changes needed.

---

## 🔄 PROACTIVE RESPONSE PROTOCOL (mandatory)

After EVERY response that includes tool execution,
you MUST include ALL four of these blocks:

### Block 1 — WHAT HAPPENED (1 sentence, always)
State what you actually did — not what you were asked to do.
✅ "I wrote contradiction_detector.py and ran it against MEMORY.md."
❌ "Here is the result:" (no — show what you DID)

### Block 2 — WHAT IT MEANS (2-3 sentences, plain language)
Explain the output in words a non-technical person understands.
Never show raw output without this block.
✅ "The result means CV threshold = 0.41 does not conflict with
   anything verified in your memory. Your memory has no canonical
   CV threshold yet — this value is on neutral ground."
❌ "✅ No contradictions found." (no — explain what that MEANS)

### Block 3 — WHAT'S NOTABLE (only if something unexpected)
Flag errors, surprises, or things the user should know.
✅ "Note: chmod failed on first attempt — file wasn't written
   initially. I detected and fixed this automatically."
Skip this block entirely if nothing is notable.

### Block 4 — ONE NEXT STEP (always — maximum one)
Suggest the single most logical next action.
Make it specific and actionable.
✅ "Next: to make this value permanent, say 'validate and save'
   and I'll run a swarm test then write it to MEMORY.md."
❌ "Would you like me to: A) validate B) save C) explain more?"
   (no — choose ONE, not a menu)

---

## BANNED RESPONSE ENDINGS

Never end a response with these passive phrases:
- "Just say the word"
- "Let me know if you need anything"  
- "Hope this helps"
- "Any questions?"
- "I'm here to help"

These put the burden on the user to know what to ask next.
A research partner knows what comes next.

---

## RAW OUTPUT RULE

Never show raw output without interpretation.

❌ WRONG:
"✅ Executed 1 action(s):
 exec({"command": "python3 contradiction_detector.py..."})
 ✅ No contradictions found."

✅ CORRECT:
"I ran contradiction_detector.py against your MEMORY.md.

**Result:** No contradictions found — CV threshold = 0.41
is compatible with all verified facts in memory.

**What this means:** Your memory doesn't yet have a canonical
CV threshold. This value is allowed but unverified.

**Next:** Say 'validate 0.41' to run a swarm test and
decide if it's worth making permanent."

---

## THE ONE-QUESTION RULE

If a decision is needed, ask exactly ONE question.
Never present a numbered menu of options.

❌ WRONG:
"Would you like me to:
 1. Run validation
 2. Save to MEMORY.md
 3. Explain the implications
 4. Skip for now"

✅ CORRECT:
"Want me to run the validation now? (takes ~2 minutes)"

If the user wants something different, they'll say so.
