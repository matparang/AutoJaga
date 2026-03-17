# ── Add this to ~/.bashrc ─────────────────────────────────────────────
# Permanently fixes OpenBLAS in all sessions
# Paste these lines at the bottom of ~/.bashrc

# AutoJaga — BLAS thread limits (prevents OpenBLAS memory error)
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# ── To apply immediately without restart ─────────────────────────────
# Run: source ~/.bashrc
