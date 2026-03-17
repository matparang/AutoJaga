#!/bin/bash
# fix_openblas.sh
# Run this BEFORE starting jagabot, OR add to ~/.bashrc

# ── Fix OpenBLAS memory allocation error ──────────────────────────────
# Forces single-threaded BLAS — safe for agent workloads
# (agents don't do massive matrix ops that need parallelism)

export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "✅ BLAS thread limits set"
echo "   OPENBLAS_NUM_THREADS=1"
echo "   OMP_NUM_THREADS=1"
echo ""
echo "Starting jagabot..."
exec jagabot "$@"
