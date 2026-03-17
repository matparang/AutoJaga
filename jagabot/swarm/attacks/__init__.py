"""Pluggable attack registry for Level-4 offline swarm tests."""
from __future__ import annotations

from jagabot.swarm.attacks.base import AttackBase, RepairLog
from jagabot.swarm.attacks.negative_spoof import NegativeSpoofAttack
from jagabot.swarm.attacks.nan_injection import NaNInjectionAttack
from jagabot.swarm.attacks.zero_divide import ZeroDivideAttack
from jagabot.swarm.attacks.duplicate_block import DuplicateBlockAttack

ALL_ATTACKS: list[type[AttackBase]] = [
    NegativeSpoofAttack,
    NaNInjectionAttack,
    ZeroDivideAttack,
    DuplicateBlockAttack,
]

__all__ = [
    "AttackBase",
    "RepairLog",
    "ALL_ATTACKS",
    "NegativeSpoofAttack",
    "NaNInjectionAttack",
    "ZeroDivideAttack",
    "DuplicateBlockAttack",
]
