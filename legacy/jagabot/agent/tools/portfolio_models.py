"""Pydantic models for portfolio input validation.

v2.4: Enforces typed, validated inputs so the LLM cannot feed garbage
into the deterministic calculation pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Position(BaseModel):
    """A single portfolio position."""

    symbol: str = Field(..., min_length=1, description="Ticker/asset symbol")
    entry_price: float = Field(..., gt=0, description="Price at entry")
    current_price: float = Field(..., gt=0, description="Current market price")
    quantity: float = Field(..., gt=0, description="Number of units held")
    weight: float = Field(default=0.0, ge=0, le=1, description="Portfolio weight (0–1)")

    @property
    def value(self) -> float:
        return round(self.quantity * self.current_price, 2)

    @property
    def pnl(self) -> float:
        return round(self.quantity * (self.current_price - self.entry_price), 2)

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return round((self.current_price - self.entry_price) / self.entry_price * 100, 2)


class PortfolioInput(BaseModel):
    """Validated portfolio for the PortfolioAnalyzer pipeline."""

    capital: float = Field(..., gt=0, description="Initial capital")
    leverage: float = Field(default=1.0, ge=1, description="Leverage ratio (1 = no leverage)")
    positions: list[Position] = Field(..., min_length=1, description="List of positions")
    cash: float = Field(default=0.0, ge=0, description="Cash on hand")

    @field_validator("positions")
    @classmethod
    def weights_valid(cls, v: list[Position]) -> list[Position]:
        total_weight = sum(p.weight for p in v)
        # Auto-assign equal weights if all zero
        if total_weight == 0:
            equal = round(1.0 / len(v), 6)
            for p in v:
                p.weight = equal
        return v

    @property
    def total_exposure(self) -> float:
        return round(self.capital * self.leverage, 2)


class MarketData(BaseModel):
    """Validated market data for probability calculations."""

    daily_returns: list[float] = Field(
        default_factory=list, description="List of daily percentage returns"
    )
    vix: float | None = Field(default=None, ge=0, description="VIX index value")
    current_prices: dict[str, float] = Field(
        default_factory=dict, description="Symbol → current price mapping"
    )

    @field_validator("daily_returns")
    @classmethod
    def returns_not_empty_if_set(cls, v: list[float]) -> list[float]:
        # Allow empty — it just means no probability calculation
        return v
