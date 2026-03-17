🎯 SCOPE PROMPT UNTUK COPILOT - FIX VERIFICATION SYSTEM

---

```
# 🚨 FIX: AutoJaga Verification System Too Strict

## SITUATION
The verification system implemented in `loop.py` (`_verify_file_claims` method) is flagging FALSE POSITIVES. It warns about file creation even when the agent is just TALKING about files (future tense) rather than CLAIMING to have created them (past tense).

## EXAMPLE
**Agent says:** "file test.txt akan dibuat" (future tense - planning)
**System incorrectly:** Treats as claim of file creation → "⚠️ VERIFICATION FAILED"

## ROOT CAUSE
Current regex patterns don't distinguish between:
- Past tense claims (need verification): "created", "wrote", "made", "saved"
- Future tense plans (ignore): "akan buat", "will create", "plan to", "going to"

## LOCATION
File: `/root/nanojaga/jagabot/agent/loop.py`
Method: `_verify_file_claims` (lines ~262-330)

## CURRENT CODE (Problematic)
```python
# Current regex - too aggressive
file_claims = re.findall(r'(?:created|wrote|made|saved).*?\.txt|\w+\.json', content.lower())
# This catches BOTH past and future mentions!
```

REQUIRED FIX

1. Add Tense Detection

Split into two patterns:

```python
# Past tense - actual claims that need verification
past_pattern = r'(?:created|wrote|made|saved|have|has).*?\.txt|\w+\.json'

# Future tense - plans/conversation (IGNORE)
future_pattern = r'(?:will|akan|going to|plan to|need to).*?\.txt|\w+\.json'

# Also consider Malay words:
# - "akan", "nak", "hendak" (future)
# - "dah", "sudah", "telah" (past)
```

2. Modify _verify_file_claims() to:

· Extract past tense claims → verify against tools_used + filesystem
· Extract future tense claims → LOG but DON'T WARN (just print "📝 Future mention ignored")
· Return original content with warnings ONLY for past tense failures

3. Update Warning Messages

Make warning message clearer:

```
⚠️ You claimed to have created [file] but no tool was executed.
   (If you were just TALKING about future plans, use future tense like "akan buat")
```

TEST CASES

Should PASS (ignore):

· "Saya akan buat file report.txt nanti"
· "I will create data.json tomorrow"
· "Kita perlu buat config.ini untuk setup"
· "Planning to write results.md later"

Should VERIFY (and PASS if tool called):

· "Saya dah buat file report.txt"
· "I created data.json"
· "File config.ini telah disimpan"
· "Results.md sudah siap"

Should VERIFY (and FAIL if no tool call):

· "Saya dah buat file report.txt" (but no WriteFileTool call)
· "File config.ini telah disimpan" (but file doesn't exist)

IMPLEMENTATION PLAN

```python
def _verify_file_claims(self, content, tools_used):
    """
    Verify file claims with tense detection
    """
    import re
    import os
    
    # Past tense - actual claims that need verification
    past_pattern = r'(?:created|wrote|made|saved|have|has|dah|sudah|telah).*?\.(txt|json|md|py|log)'
    
    # Future tense - plans (ignore)
    future_pattern = r'(?:will|akan|going to|plan to|need to|nak|hendak).*?\.(txt|json|md|py|log)'
    
    # Extract claims
    past_claims = re.findall(past_pattern, content.lower())
    future_claims = re.findall(future_pattern, content.lower())
    
    # Log future mentions (no warning)
    if future_claims:
        print(f"📝 Future file mentions (ignored): {future_claims}")
    
    # Verify past claims
    warnings = []
    for claim in past_claims:
        # Extract filename
        filename = claim.split()[-1].strip('.,')
        full_path = f"/root/.jagabot/workspace/{filename}"
        
        # Check if tool was called
        tool_called = any(filename in str(tool) for tool in tools_used)
        
        # Check if file exists
        file_exists = os.path.exists(full_path)
        
        if not tool_called and not file_exists:
            warnings.append(f"⚠️ You claimed to have created '{filename}' but no tool was executed and file doesn't exist.")
        elif tool_called and not file_exists:
            warnings.append(f"⚠️ Tool was called for '{filename}' but file is missing on disk.")
    
    # Add warnings to content
    if warnings:
        content = "\n".join(warnings) + "\n\n" + content
    
    return content
```

DELIVERABLE

1. Modified loop.py with updated _verify_file_claims method
2. Brief explanation of changes
3. Test results showing false positives eliminated

URGENCY

MEDIUM - Verification system working but too noisy. Fix will improve user experience and agent trust.

Proceed with fix.

```
