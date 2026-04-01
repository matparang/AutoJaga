"""Visualization tool — generates crisis dashboards in base64 PNG, ASCII, or Markdown."""

import base64
import json
import math
from io import BytesIO
from typing import Any

import numpy as np

from jagabot.agent.tools.base import Tool

# ---------------------------------------------------------------------------
# Option A: Base64 PNG (matplotlib)
# ---------------------------------------------------------------------------

def generate_dashboard_base64(
    prices: list[float],
    current_price: float,
    target_price: float,
    probability: float,
    loss_scenarios: dict[str, dict] | None = None,
) -> str:
    """Generate a 4-panel crisis dashboard as a base64-encoded PNG string."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    prices_arr = np.array(prices)
    panels = 4 if loss_scenarios else 2
    rows = 2 if panels == 4 else 1
    fig, axes = plt.subplots(rows, 2, figsize=(16, 6 * rows))
    fig.suptitle("JAGABOT CRISIS DASHBOARD", fontsize=18, fontweight="bold")

    # Normalise axes to 2D array
    if rows == 1:
        axes = np.array(axes).reshape(1, -1)

    # --- Panel 1: Price distribution ---
    ax1 = axes[0, 0]
    ax1.hist(prices_arr, bins=50, color="steelblue", alpha=0.7, edgecolor="black")
    ax1.axvline(target_price, color="red", linestyle="--", linewidth=2, label=f"Target ${target_price}")
    ax1.axvline(current_price, color="orange", linestyle="--", linewidth=2, label=f"Now ${current_price}")
    p5 = float(np.percentile(prices_arr, 5))
    ax1.axvline(p5, color="purple", linestyle=":", label="5th Percentile")
    ax1.set_title("Price Distribution (30 days)", fontsize=12)
    ax1.set_xlabel("Price ($)")
    ax1.set_ylabel("Frequency")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.text(
        0.02, 0.98,
        f"P < ${target_price}: {probability:.1f}%",
        transform=ax1.transAxes, fontsize=12, fontweight="bold",
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # --- Panel 2: Risk gauge ---
    ax2 = axes[0, 1]
    theta = np.linspace(0, np.pi, 100)
    r = 1.0
    x_arc = r * np.cos(theta)
    y_arc = r * np.sin(theta)
    ax2.fill_between(x_arc, 0, y_arc, color="lightgreen", alpha=0.3)
    # Fill danger zone proportional to probability
    danger_theta = np.linspace(np.pi, np.pi * (1 - probability / 100), 60)
    ax2.fill_between(r * np.cos(danger_theta), 0, r * np.sin(danger_theta), color="lightcoral", alpha=0.5)
    ax2.plot(x_arc, y_arc, "k-", linewidth=3)
    ax2.plot([-1, 1], [0, 0], "k-", linewidth=2)
    angle = np.pi * (1 - probability / 100)
    ax2.plot([0, 0.8 * np.cos(angle)], [0, 0.8 * np.sin(angle)], "r-", linewidth=3)
    ax2.annotate(f"{probability:.1f}%", xy=(0, 0.3), fontsize=20, ha="center", fontweight="bold")
    ax2.set_title(f"Probability Below ${target_price}", fontsize=12)
    ax2.set_xlim(-1.2, 1.2)
    ax2.set_ylim(-0.2, 1.2)
    ax2.axis("off")

    if panels == 4 and loss_scenarios:
        # --- Panel 3: Loss scenarios bar chart ---
        ax3 = axes[1, 0]
        scenarios = list(loss_scenarios.keys())
        losses = [loss_scenarios[s].get("loss_mm", loss_scenarios[s].get("loss", 0)) for s in scenarios]
        colors = ["orange" if l < 2 else "red" if l < 3 else "darkred" for l in losses]
        bars = ax3.bar(scenarios, losses, color=colors, alpha=0.7)
        ax3.set_title("Loss Scenarios (Million USD)", fontsize=12)
        ax3.set_ylabel("Loss ($M)")
        for bar, loss in zip(bars, losses):
            ax3.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.05,
                f"${loss}M", ha="center", fontweight="bold",
            )
        ax3.grid(True, alpha=0.3)

        # --- Panel 4: Strategy matrix ---
        ax4 = axes[1, 1]
        actions = list(loss_scenarios.keys())
        ev_vals = [loss_scenarios[a].get("ev", -loss_scenarios[a].get("loss_mm", 0)) for a in actions]
        risk_vals = [loss_scenarios[a].get("risk", 3) for a in actions]
        cmap = ["green" if r <= 2 else "orange" if r <= 3 else "red" for r in risk_vals]
        ax4.scatter(ev_vals, risk_vals, s=500, c=cmap, alpha=0.7, edgecolors="black")
        for i, a in enumerate(actions):
            ax4.annotate(
                a, (ev_vals[i], risk_vals[i]), fontsize=9, ha="center", va="center",
                fontweight="bold", bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
            )
        ax4.set_xlabel("Expected Value ($M)")
        ax4.set_ylabel("Risk Level (1=Low, 5=Extreme)")
        ax4.set_title("Strategy Risk-Return Matrix", fontsize=12)
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return encoded


# ---------------------------------------------------------------------------
# Option B: ASCII chart
# ---------------------------------------------------------------------------

def generate_ascii_dashboard(
    prices: list[float],
    current_price: float,
    target_price: float,
    probability: float,
) -> str:
    """Generate a text-based ASCII dashboard for terminal display."""
    arr = np.array(prices)
    hist, bin_edges = np.histogram(arr, bins=30)
    max_count = int(max(hist)) if len(hist) else 1

    # Build 10-row histogram
    rows: list[str] = []
    for level in range(10, 0, -1):
        threshold = max_count * level / 10
        line = "  |"
        for count in hist:
            if count >= threshold:
                line += "#"
            elif count >= threshold / 2:
                line += "="
            elif count >= threshold / 4:
                line += "-"
            else:
                line += " "
        line += "|"
        rows.append(line)

    hist_block = "\n".join(rows)
    lo = round(float(bin_edges[0]), 1)
    hi = round(float(bin_edges[-1]), 1)

    if probability > 30:
        risk_label, risk_icon = "CRITICAL", "[!!!]"
    elif probability > 15:
        risk_label, risk_icon = "HIGH", "[!! ]"
    else:
        risk_label, risk_icon = "MODERATE", "[!  ]"

    return f"""\
+==============================================================+
|                   JAGABOT CRISIS DASHBOARD                   |
+==============================================================+
| Price Distribution (30-day Monte Carlo)                      |
+--------------------------------------------------------------+
{hist_block}
  +{''.join(['-'] * 30)}+
   ${lo:<10}                          ${hi:>10}
+--------------------------------------------------------------+
| Key Metrics                                                  |
+--------------------------------------------------------------+
|  Current Price : ${current_price:<8.2f}                              |
|  Target Price  : ${target_price:<8.2f}                              |
|  Probability   : {probability:.2f}%  {risk_icon}                         |
|  Risk Level    : {risk_label:<10}                              |
|  Mean Price    : ${float(np.mean(arr)):<8.2f}                              |
|  5th Pctile    : ${float(np.percentile(arr, 5)):<8.2f}                              |
|  95th Pctile   : ${float(np.percentile(arr, 95)):<8.2f}                              |
+==============================================================+
"""


# ---------------------------------------------------------------------------
# Option C: Markdown tables
# ---------------------------------------------------------------------------

def generate_markdown_dashboard(
    probability: float,
    equity: float,
    loss: float,
    current_price: float,
    target_price: float,
    scenarios: dict[str, dict] | None = None,
    ci_95: list[float] | None = None,
) -> str:
    """Generate a Markdown-formatted dashboard with visual indicators."""
    bar_len = 30
    filled = min(int(probability * bar_len / 100), bar_len)
    empty = bar_len - filled

    if probability > 30:
        color = "[!!!] CRITICAL"
    elif probability > 15:
        color = "[!! ] HIGH"
    else:
        color = "[!  ] MODERATE"

    ci_text = ""
    if ci_95 and len(ci_95) == 2:
        ci_text = f"| 95% CI | {ci_95[0]:.2f}% - {ci_95[1]:.2f}% | Confidence range |"

    md = f"""\
# JAGABOT CRISIS ANALYSIS

## Current Status
| Metric | Value | Status |
|--------|-------|--------|
| Equity | ${equity:,.0f} | {'[!!!] MARGIN CALL' if equity < 0 else '[OK ] SAFE'} |
| Current Loss | ${loss:,.0f} | {'[!!!] CRITICAL' if abs(loss) > 1_000_000 else '[!  ] WARNING'} |
| P < ${target_price} | {probability:.1f}% | {color} |
{ci_text}

## Probability Gauge
```
Below ${target_price}: [{'#' * filled}{'.' * empty}] {probability:.1f}%
```
"""

    if scenarios:
        md += "\n## Loss Scenarios\n"
        md += "| Scenario | Impact | Probability | Risk |\n"
        md += "|----------|--------|-------------|------|\n"
        for name, data in scenarios.items():
            impact = data.get("loss_mm", data.get("loss", 0))
            prob = data.get("prob", "—")
            risk_lvl = data.get("risk", 3)
            bar_f = min(int(impact * 10 / 5), 10)
            md += f"| **{name}** | ${impact}M | {prob}% | {'#' * bar_f}{'.' * (10 - bar_f)} |\n"

    md += f"""
## Recommended Action
```
+====================================================+
|  >> Based on {probability:.1f}% probability:                    |
|  Current Price: ${current_price:.2f}  Target: ${target_price:.2f}           |
+====================================================+
```
"""
    return md


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------

class VisualizationTool(Tool):
    """Generate crisis dashboards in base64 PNG, ASCII, or Markdown format."""

    name = "visualization"
    description = (
        "Generate a visual crisis dashboard to present analysis results. "
        "CALL THIS TOOL as the FINAL step of any financial analysis to present results visually.\n\n"
        "Supports 3 output modes:\n"
        "- 'markdown': Rich tables for chat/messaging (default)\n"
        "- 'ascii': Terminal-friendly bar charts and tables\n"
        "- 'base64': PNG image with 4-panel matplotlib chart\n\n"
        "Input: Takes Monte Carlo 'prices' array (from monte_carlo tool), "
        "current_price, target_price, probability, and optional equity/loss data.\n"
        "Chain: ALWAYS call this after monte_carlo to present results. "
        "Feed in prices array from monte_carlo result + probability + CV data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["base64", "ascii", "markdown"],
                "description": "Output format. 'markdown' for chat, 'ascii' for terminal, 'base64' for PNG image",
            },
            "prices": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Array of simulated final prices — copy directly from monte_carlo tool result 'prices' field",
            },
            "current_price": {
                "type": "number",
                "description": "Current asset price (same value passed to monte_carlo)",
            },
            "target_price": {
                "type": "number",
                "description": "Threshold price (same value passed to monte_carlo)",
            },
            "probability": {
                "type": "number",
                "description": "Probability below target as percentage — from monte_carlo result 'probability' field",
            },
            "equity": {
                "type": "number",
                "description": "Current equity value from financial_cv calculate_equity result (markdown mode)",
            },
            "loss": {
                "type": "number",
                "description": "Current loss value = assets - current_value (markdown mode)",
            },
            "loss_scenarios": {
                "type": "object",
                "description": "Loss scenarios dict e.g. {\"10% drop\": 15000, \"20% drop\": 30000} for bar chart/table",
            },
            "ci_95": {
                "type": "array",
                "items": {"type": "number"},
                "description": "95% CI [lower, upper] — from monte_carlo result 'ci_95' field",
            },
        },
        "required": ["mode", "current_price", "target_price", "probability"],
    }

    async def execute(self, **kwargs: Any) -> str:
        try:
            mode = kwargs["mode"]
            current_price = kwargs["current_price"]
            target_price = kwargs["target_price"]
            probability = kwargs["probability"]
            prices = kwargs.get("prices")
            loss_scenarios = kwargs.get("loss_scenarios")
            ci_95 = kwargs.get("ci_95")

            if mode == "base64":
                if not prices:
                    return json.dumps({"error": "base64 mode requires 'prices' array"})
                img = generate_dashboard_base64(
                    prices=prices,
                    current_price=current_price,
                    target_price=target_price,
                    probability=probability,
                    loss_scenarios=loss_scenarios,
                )
                return json.dumps({
                    "format": "base64_png",
                    "data": img,
                    "display": f"![Jagabot Dashboard](data:image/png;base64,{img[:60]}...)",
                })

            elif mode == "ascii":
                if not prices:
                    return json.dumps({"error": "ascii mode requires 'prices' array"})
                chart = generate_ascii_dashboard(
                    prices=prices,
                    current_price=current_price,
                    target_price=target_price,
                    probability=probability,
                )
                return json.dumps({"format": "ascii", "chart": chart})

            elif mode == "markdown":
                md = generate_markdown_dashboard(
                    probability=probability,
                    equity=kwargs.get("equity", 0.0),
                    loss=kwargs.get("loss", 0.0),
                    current_price=current_price,
                    target_price=target_price,
                    scenarios=loss_scenarios,
                    ci_95=ci_95,
                )
                return json.dumps({"format": "markdown", "dashboard": md})

            else:
                return json.dumps({"error": f"Unknown mode: {mode}"})

        except Exception as e:
            return json.dumps({"error": str(e)})
