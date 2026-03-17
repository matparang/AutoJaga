"""Jagabot reasoning kernels — extracted from nanobot engine library."""

from jagabot.kernels.k1_bayesian import K1Bayesian, CalibrationStore

# Lazy import to avoid circular dependency (k3 imports from agent.tools.decision)


def __getattr__(name):
    if name == "K3MultiPerspective":
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        return K3MultiPerspective
    if name == "AccuracyTracker":
        from jagabot.kernels.k3_perspective import AccuracyTracker
        return AccuracyTracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "K1Bayesian",
    "CalibrationStore",
    "K3MultiPerspective",
    "AccuracyTracker",
]
