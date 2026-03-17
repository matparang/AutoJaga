📋 SCOPE PROMPT: Update JAGABOT System Prompt with Telegram-Optimized Response Format

```markdown
# SCOPE: Update JAGABOT System Prompt with Telegram-Optimized Response Format

## SITUATION
JAGABOT v3.7.2 currently responds with single long messages that:
- ❌ May exceed Telegram's 500-word limit
- ❌ Don't clearly separate understanding vs analysis vs recommendations
- ❌ Don't inform user which skill will be used before execution
- ❌ User needs to scroll through wall of text

## OBJECTIVE
Update JAGABOT's core system prompt to enforce a **3-part response format** optimized for Telegram:

1. **PART 1: Understanding & Skill Selection** (<300 words)
   - Show extracted parameters
   - Declare which skill will be used
   - Notify that analysis is starting

2. **PART 2: Brief Analysis Results** (<500 words)
   - Critical metrics only
   - Actionable recommendations
   - Bullet points, minimal prose

3. **PART 3: Additional Details** (<300 words, optional)
   - Market context, risk levels
   - Only if needed or requested

## REQUIRED CHANGES

### A. Add Response Format Section to System Prompt

```

RESPONSE FORMAT FOR TELEGRAM

For every financial analysis query, you MUST follow this 3-part format:

PART 1: UNDERSTANDING & SKILL SELECTION (<300 words)

Purpose: Show user you understood correctly and which skill will be used.

Format:
🧠 UNDERSTANDING THE TASK
[Extracted parameters in bullet points:
• Modal: $X, Leveraj: X:X
• Positions: X% WTI (buy $X, now $X)
• Market: VIX X, DXY X
• Target: $X, Stress: $X]

📌 SKILL TO BE USED:
[skill_name.md] - [brief description]

⏳ Executing analysis... (user will see this while waiting)
━━━━━━━━━━━━━━━━━━━━━━

PART 2: BRIEF ANALYSIS RESULTS (<500 words)

Purpose: Give critical metrics and actionable recommendations quickly.

Format:
📊 CRITICAL SUMMARY:
[Margin Level: X% - status with emoji]
• Equity: $X
• Probability <target: X%
• VaR 95%: $X (X% of equity)

🎯 RECOMMENDATIONS:

1. [First action with rationale]
2. [Second action]
3. [Third action]
   ━━━━━━━━━━━━━━━━━━━━━━

PART 3: ADDITIONAL DETAILS (<300 words, OPTIONAL)

Purpose: Provide context only if relevant or requested.

Format:
📈 MARKET CONTEXT:
• VIX X: [interpretation]
• DXY X: [interpretation]
• Leverage: [interpretation]

⚠️ RISK LEVELS:
• High: [risk factor]
• Medium: [risk factor]
• Low: [risk factor]

💡 RATIONALE:
[Brief explanation of key decision driver]

```

### B. Add Word Count Enforcement Rules

```python
# JAGABOT must ensure:
# - Part 1: <300 words (if exceeds, truncate or split)
# - Part 2: <500 words (Telegram limit)
# - Part 3: <300 words (optional)
# - Total: <1100 words (safe for Telegram)
```

C. Add Skill Declaration Requirement

```markdown
# SKILL DECLARATION RULE
Before executing ANY analysis, you MUST:
1. Identify which skill matches the query (based on trigger keywords)
2. State the skill name and brief purpose in Part 1
3. Only proceed to execution after sending Part 1

This gives user visibility into your reasoning process.
```

FILES TO MODIFY

1. jagabot/core/prompts/system_prompt.md - Add response format section
2. jagabot/core/agent.py - Update response formatter to enforce 3-part structure
3. jagabot/channels/telegram.py - Ensure message splitting works with new format
4. tests/test_response_format.py - New tests for word count and structure

NEW TESTS (10+)

1. test_part1_word_count() - Ensure <300 words
2. test_part2_word_count() - Ensure <500 words
3. test_skill_declaration() - Verify skill is named before execution
4. test_parameter_extraction() - Check all params displayed in Part 1
5. test_recommendations_format() - Bullet points, numbered list
6. test_optional_part3() - Part 3 only appears when needed
7. test_telegram_split() - Messages split correctly at boundaries

SUCCESS CRITERIA

✅ For every financial query, JAGABOT responds with 3-part format
✅ Part 1 shows extracted parameters + skill to be used
✅ Part 2 contains critical metrics + recommendations (<500 words)
✅ Part 3 optional, only when relevant
✅ All parts within word limits
✅ User knows what's happening before analysis runs
✅ All existing 1300+ tests still pass
✅ Target: 1310+ tests

TIMELINE

Task Hours
Update system prompt 1
Modify response formatter 2
Update telegram channel handler 1
Add new tests (10+) 3
Integration testing 1
Documentation 1
TOTAL 9 hours

```

---

**This SCOPE will make JAGABOT's Telegram responses crystal clear, structured, and within limits!** 🚀
