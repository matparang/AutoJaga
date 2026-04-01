#!/bin/bash
# seed_databases.sh
# Seeds domain knowledge databases after OpenBLAS fix
# Run once after fixing BLAS to prime calibration data

echo "🌱 Seeding AutoJaga domain databases..."
echo ""

# ── Financial domain ───────────────────────────────────────────────────
echo "📊 Seeding financial domain..."
echo "Research CVaR timing accuracy and margin call prediction methods" | \
    OPENBLAS_NUM_THREADS=1 jagabot chat --no-stream 2>/dev/null
echo "✅ Financial done"
echo ""

# ── Healthcare domain ──────────────────────────────────────────────────
echo "🏥 Seeding healthcare domain..."
echo "Analyze LLM applications in clinical note summarization for hospitals" | \
    OPENBLAS_NUM_THREADS=1 jagabot chat --no-stream 2>/dev/null
echo "✅ Healthcare done"
echo ""

# ── Causal domain ─────────────────────────────────────────────────────
echo "🔬 Seeding causal domain..."
echo "Explain inverse probability weighting for treatment effect estimation" | \
    OPENBLAS_NUM_THREADS=1 jagabot chat --no-stream 2>/dev/null
echo "✅ Causal done"
echo ""

# ── Research domain ───────────────────────────────────────────────────
echo "📚 Seeding research domain..."
echo "Research quantum computing applications in drug discovery" | \
    OPENBLAS_NUM_THREADS=1 jagabot chat --no-stream 2>/dev/null
echo "✅ Research done"
echo ""

# ── Verify databases populated ────────────────────────────────────────
echo "🔍 Verifying database population..."
echo ""

# Check self_model.db
DB_PATH="$HOME/.jagabot/workspace/memory/self_model.db"
if [ -f "$DB_PATH" ]; then
    DOMAIN_COUNT=$(sqlite3 "$DB_PATH" \
        "SELECT COUNT(*) FROM domain_knowledge;" 2>/dev/null)
    echo "✅ self_model.db: $DOMAIN_COUNT domain(s) recorded"
else
    echo "⚠️  self_model.db not found — check workspace path"
fi

# Check brier.db
BRIER_DB="$HOME/.jagabot/workspace/memory/brier.db"
if [ -f "$BRIER_DB" ]; then
    BRIER_COUNT=$(sqlite3 "$BRIER_DB" \
        "SELECT COUNT(*) FROM brier_outcomes;" 2>/dev/null)
    echo "✅ brier.db: $BRIER_COUNT outcome(s) recorded"
else
    echo "⏳ brier.db not yet created (needs verdict data)"
fi

# Check curiosity.db
CUR_DB="$HOME/.jagabot/workspace/memory/curiosity.db"
if [ -f "$CUR_DB" ]; then
    GAP_COUNT=$(sqlite3 "$CUR_DB" \
        "SELECT COUNT(*) FROM curiosity_targets;" 2>/dev/null)
    echo "✅ curiosity.db: $GAP_COUNT gap(s) detected"
else
    echo "⏳ curiosity.db not yet created (needs session data)"
fi

# Check HISTORY.md for reliability logs
HISTORY="$HOME/.jagabot/workspace/memory/HISTORY.md"
if [ -f "$HISTORY" ]; then
    REL_COUNT=$(grep -c "RELIABILITY_LOG" "$HISTORY" 2>/dev/null || echo 0)
    echo "✅ HISTORY.md: $REL_COUNT reliability log(s)"
else
    echo "⏳ HISTORY.md not yet populated"
fi

echo ""
echo "🏁 Seeding complete."
echo ""
echo "Next steps:"
echo "  1. Give verdicts: jagabot chat → /pending"
echo "  2. Check status:  jagabot chat → /status"
echo "  3. See curiosity: jagabot chat (first message triggers suggestions)"
