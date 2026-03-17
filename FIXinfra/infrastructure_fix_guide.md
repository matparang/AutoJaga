# Infrastructure Fix Guide
# Resolves OpenBLAS + primes engine databases

---

## The Problem

```
OpenBLAS memory allocation error
→ numpy/scipy import fails
→ curiosity_engine + confidence_engine crash on import
→ agent sees "not wired" when actually wired correctly

Root cause:
OpenBLAS defaults to spawning threads for ALL CPU cores
In Docker/VM/container → hits memory limit → crashes
```

---

## Fix 1 — Immediate (30 seconds)

Run this in terminal before starting jagabot:

```bash
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
jagabot chat
```

Test it worked:
```bash
python3 -c "import numpy; import scipy; print('✅ numpy + scipy OK')"
```

---

## Fix 2 — Permanent (add to ~/.bashrc)

```bash
# Add to bottom of ~/.bashrc:
echo "" >> ~/.bashrc
echo "# AutoJaga — BLAS thread limits" >> ~/.bashrc
echo "export OPENBLAS_NUM_THREADS=1" >> ~/.bashrc
echo "export OMP_NUM_THREADS=1" >> ~/.bashrc
echo "export MKL_NUM_THREADS=1" >> ~/.bashrc
echo "export VECLIB_MAXIMUM_THREADS=1" >> ~/.bashrc
echo "export NUMEXPR_NUM_THREADS=1" >> ~/.bashrc

# Apply now:
source ~/.bashrc
```

---

## Fix 3 — Nuclear option (if Fix 1+2 don't work)

Reinstall BLAS libraries:
```bash
sudo apt-get update
sudo apt-get install --reinstall libopenblas-base libopenblas-dev
```

If still failing — switch to netlib BLAS (slower but always works):
```bash
sudo update-alternatives --set libblas.so.3 \
    /usr/lib/x86_64-linux-gnu/blas/libblas.so.3
```

---

## After BLAS Fixed — Seed the Databases

Run the seeding script:
```bash
bash seed_databases.sh
```

Or manually:
```bash
# One command per domain — each seeds that domain's data
OPENBLAS_NUM_THREADS=1 jagabot chat <<< \
    "Research CVaR timing in financial risk"

OPENBLAS_NUM_THREADS=1 jagabot chat <<< \
    "Analyze LLM in clinical note summarization"

OPENBLAS_NUM_THREADS=1 jagabot chat <<< \
    "Explain IPW for causal inference"
```

---

## Verify Everything Working

```bash
# 1. Check BLAS
python3 -c "
import numpy as np
import scipy.stats as st
x = np.random.normal(0, 1, 1000)
ci = st.t.interval(0.95, len(x)-1, loc=np.mean(x), scale=st.sem(x))
print(f'✅ numpy + scipy working: CI = [{ci[0]:.3f}, {ci[1]:.3f}]')
"

# 2. Check domain databases
sqlite3 ~/.jagabot/workspace/memory/self_model.db \
    "SELECT domain, session_count, reliability FROM domain_knowledge;"

# 3. Check curiosity engine
sqlite3 ~/.jagabot/workspace/memory/curiosity.db \
    "SELECT topic, gap_type, base_priority FROM curiosity_targets;"

# 4. Check confidence engine
sqlite3 ~/.jagabot/workspace/memory/confidence.db \
    "SELECT COUNT(*) as claim_count FROM claim_outcomes;"

# 5. Check reliability logs in HISTORY.md
grep "RELIABILITY_LOG\|CURIOSITY\|CONFIDENCE" \
    ~/.jagabot/workspace/memory/HISTORY.md | tail -10
```

---

## Expected output after seeding (4 domains)

```
# self_model.db
domain       session_count  reliability
financial    1              0.5
healthcare   1              0.5
causal       1              0.5
research     1              0.5

# curiosity.db  
topic                  gap_type       priority
financial+healthcare   bridge         0.5
causal+research        bridge         0.5
quantum                knowledge_gap  0.5

# HISTORY.md
RELIABILITY_LOG | financial | session_count=1 | quality=0.72
RELIABILITY_LOG | healthcare | session_count=1 | quality=0.68
```

---

## Why This Is Infrastructure Not Wiring

```
Wiring  = code connecting components together  ← DONE ✅
Infrastructure = system environment working     ← BROKEN ❌
Data    = real usage populating databases       ← EMPTY ⏳

The analogy:
  Wiring    = electrical cables connected ✅
  Infrastructure = power supply working   ❌ (BLAS = power supply)
  Data      = electricity flowing         ⏳ (sessions = electricity)

Fix the power supply → electricity flows → everything works
```

---

## Performance Note

Setting OPENBLAS_NUM_THREADS=1 does NOT meaningfully slow down AutoJaga.

Your scipy calls are:
  confidence_interval() → 1000-10000 samples
  brier_score calc      → simple arithmetic
  
These are microsecond operations whether single or multi-threaded.
The threading overhead was actually making them SLOWER.
Single-threaded is the right choice for agent workloads.

