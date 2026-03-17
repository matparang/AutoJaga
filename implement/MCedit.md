✅ SCOPE PROMPT: Fix Monte Carlo & Add Visualizations

---

```markdown
# SCOPE: Standardize Monte Carlo & Add Visualizations to Jagabot

## CONTEXT
Testing shows Jagabot's Monte Carlo probability (24.69%) differs from Colab calculation (17.2%) - a 7.5% gap. Both use same input data but different parameters. Need to standardize AND add visual dashboards.

## PART 1: FIX MONTE CARLO STANDARDIZATION

### The Problem
```

Source          Probability    Volatility Used
Google Colab    17.2%          VIX=58 (annual 58%)
Jagabot         24.69%         Unknown parameters
Expected        92.8%          Wrong expectation!

```

### Root Cause
We expected 92.8% based on historical CV=0.55, but actual market uses VIX=58 (58% annual vol) which gives ~17-25% probability. **Both Colab and Jagabot are correct** - just using different volatility sources.

### The Fix: Standardize on VIX-based volatility
```python
def standard_monte_carlo(current_price, target_price, vix, days=30, n_simulations=10000):
    """
    STANDARD Monte Carlo implementation for ALL Jagabot tools
    
    Args:
        current_price: Current WTI price (e.g., 52.80)
        target_price: Target threshold (e.g., 45)
        vix: VIX value (e.g., 58 for 58% annual vol)
        days: Forecast horizon (default 30)
        n_simulations: Number of paths (default 10000)
    
    Returns:
        dict with probability, confidence intervals, and price distribution
    """
    # 1. Set seed for reproducibility
    np.random.seed(42)
    
    # 2. Convert VIX to daily volatility
    annual_vol = vix / 100  # VIX=58 → 0.58
    daily_vol = annual_vol / np.sqrt(252)  # ~0.0365 for VIX=58
    
    # 3. GBM parameters
    dt = 1
    mu = -0.001  # slight negative drift for crisis
    
    # 4. Run simulation
    prices = []
    for _ in range(n_simulations):
        price = current_price
        for _ in range(days):
            price *= np.exp((mu - 0.5 * daily_vol**2) + daily_vol * np.random.normal())
        prices.append(price)
    
    # 5. Calculate statistics
    prices = np.array(prices)
    prob_below = np.mean(prices < target_price) * 100
    
    # 6. Confidence interval
    n_below = np.sum(prices < target_price)
    ci_lower, ci_upper = stats.beta.interval(0.95, n_below + 1, n_simulations - n_below + 1)
    
    return {
        'probability': prob_below,
        'ci_95': [ci_lower*100, ci_upper*100],
        'mean_price': np.mean(prices),
        'median_price': np.median(prices),
        'percentile_5': np.percentile(prices, 5),
        'percentile_95': np.percentile(prices, 95),
        'all_prices': prices.tolist()  # For visualization
    }
```

Update ALL Monte Carlo calls to use this standard function:

· In monte_carlo.py tool
· In billing_agent.py subagent
· In any strategy calculations
· In Colab test scripts

---

PART 2: ADD VISUALIZATION DASHBOARD

Option A: Base64 PNG Charts (For Colab/Notebooks)

```python
def generate_dashboard_base64(prices, current_price, target_price, probability, loss_scenarios):
    """
    Generate 4-panel dashboard as base64 PNG
    """
    import matplotlib.pyplot as plt
    import base64
    from io import BytesIO
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('🚨 JAGABOT CRISIS DASHBOARD', fontsize=18, fontweight='bold')
    
    # Panel 1: Monte Carlo Distribution
    ax1 = axes[0, 0]
    ax1.hist(prices, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
    ax1.axvline(target_price, color='red', linestyle='--', linewidth=2, label=f'Target ${target_price}')
    ax1.axvline(current_price, color='orange', linestyle='--', linewidth=2, label=f'Now ${current_price}')
    ax1.axvline(np.percentile(prices, 5), color='purple', linestyle=':', label='5th Percentile')
    ax1.set_title('Price Distribution (30 days)', fontsize=12)
    ax1.set_xlabel('WTI Price ($)')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Add probability annotation
    ax1.text(0.02, 0.98, f'P < ${target_price}: {probability:.1f}%', 
             transform=ax1.transAxes, fontsize=12, fontweight='bold',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Panel 2: Loss Scenarios
    ax2 = axes[0, 1]
    scenarios = list(loss_scenarios.keys())
    losses = [loss_scenarios[s]['loss_mm'] for s in scenarios]
    colors = ['orange' if l < 2 else 'red' if l < 3 else 'darkred' for l in losses]
    bars = ax2.bar(scenarios, losses, color=colors, alpha=0.7)
    ax2.set_title('Loss Scenarios (Million USD)', fontsize=12)
    ax2.set_ylabel('Loss ($M)')
    ax2.axhline(y=2.67, color='blue', linestyle='--', label='Current Loss')
    for bar, loss in zip(bars, losses):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'${loss}M', ha='center', fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Risk Gauge
    ax3 = axes[1, 0]
    # Create a semi-circle gauge
    theta = np.linspace(0, np.pi, 100)
    r = 1.0
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    
    # Fill based on probability
    fill_theta = np.linspace(0, np.pi * (1 - probability/100), 50)
    fill_x = r * np.cos(fill_theta)
    fill_y = r * np.sin(fill_theta)
    
    ax3.fill_between(fill_x, 0, fill_y, color='lightcoral', alpha=0.5, label=f'{probability:.1f}%')
    ax3.fill_between(x, 0, y, where=(x < 0), color='lightgreen', alpha=0.3, label='Safe')
    ax3.plot(x, y, 'k-', linewidth=3)
    ax3.plot([-1, 1], [0, 0], 'k-', linewidth=2)
    
    # Add needle
    angle = np.pi * (1 - probability/200)  # Center at 50% = straight up
    needle_length = 0.8
    ax3.plot([0, needle_length * np.cos(angle)], [0, needle_length * np.sin(angle)], 
             'r-', linewidth=3, label='Risk Level')
    
    ax3.annotate(f'{probability:.1f}%', xy=(0, 0.3), fontsize=20, ha='center', fontweight='bold')
    ax3.set_title('Probability Below $45', fontsize=12)
    ax3.set_xlim(-1.2, 1.2)
    ax3.set_ylim(-0.2, 1.2)
    ax3.axis('off')
    ax3.legend(loc='lower right')
    
    # Panel 4: Action Matrix
    ax4 = axes[1, 1]
    actions = ['Cut Loss', 'Hedge', 'Add Margin', 'Do Nothing']
    ev = [-2.1, -0.045, -0.5, -2.98]  # Expected value in $M
    risk = [1, 3, 4, 5]  # 1=low, 5=extreme
    
    colors = ['green', 'yellow', 'orange', 'red']
    sizes = [500, 500, 500, 500]
    
    scatter = ax4.scatter(ev, risk, s=sizes, c=colors, alpha=0.7, edgecolors='black')
    
    for i, action in enumerate(actions):
        ax4.annotate(action, (ev[i], risk[i]), fontsize=10, ha='center', va='center', 
                    fontweight='bold', bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    ax4.set_xlabel('Expected Value ($M)')
    ax4.set_ylabel('Risk Level (1=Low, 5=Extreme)')
    ax4.set_title('Strategy Risk-Return Matrix')
    ax4.axhline(y=3, color='orange', linestyle='--', alpha=0.5)
    ax4.axvline(x=-1, color='orange', linestyle='--', alpha=0.5)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return image_base64
```

Option B: ASCII Chart (For CLI/Terminal)

```python
def generate_ascii_dashboard(prices, current_price, target_price, probability):
    """
    Generate text-based ASCII chart for terminal display
    """
    # Create histogram bins
    hist, bins = np.histogram(prices, bins=30)
    max_count = max(hist)
    
    chart = f"""
╔══════════════════════════════════════════════════════════════╗
║                    JAGABOT CRISIS DASHBOARD                  ║
╠══════════════════════════════════════════════════════════════╣
║  Price Distribution (30 days):                               ║
║  ┌────────────────────────────────────────────────────────┐ ║
"""
    
    # Create 10-row ASCII histogram
    for level in range(10, 0, -1):
        line = "║  │"
        threshold = max_count * level / 10
        for count in hist:
            if count >= threshold:
                line += "█"
            elif count >= threshold/2:
                line += "▓"
            elif count >= threshold/4:
                line += "▒"
            else:
                line += "░"
        line += "│"
        chart += line + "\n"
    
    # Add price axis
    chart += f"""║  └────────────────────────────────────────────────────────┘ ║
║    ${min(bins):.0f}                                         ${max(bins):.0f}       ║
║                                                                  ║
║  Key Metrics:                                                   ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │  Current Price: ${current_price:<6.2f} {'🔴' if current_price < target_price else '🟢'}                           │ ║
║  │  Target:       ${target_price:<6.2f}                                      │ ║
║  │  Probability:  {probability:<6.2f}% {'🔴' if probability > 30 else '🟡' if probability > 15 else '🟢'}                           │ ║
║  │  Risk Level:   {'🔴 CRITICAL' if probability > 30 else '🟡 HIGH' if probability > 15 else '🟢 MODERATE'}            │ ║
║  └────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
"""
    return chart
```

Option C: Markdown Tables with Visual Indicators

```python
def generate_markdown_dashboard(probability, equity, loss, scenarios):
    """
    Generate markdown tables with visual indicators
    """
    
    # Create probability bar
    bar_length = 30
    filled = int(probability * bar_length / 100)
    empty = bar_length - filled
    
    # Color based on probability
    if probability > 30:
        color = "🔴"
    elif probability > 15:
        color = "🟡"
    else:
        color = "🟢"
    
    dashboard = f"""
# 🚨 JAGABOT CRISIS ANALYSIS

## Current Status
| Metric | Value | Status |
|--------|-------|--------|
| Equity | ${equity:,.0f} | {'🔴 MARGIN CALL' if equity < 0 else '🟢 SAFE'} |
| Current Loss | ${loss:,.0f} | 🔴 CRITICAL |
| Probability < $45 | {probability:.1f}% | {color} |

## Probability Gauge
```

Below $45: [{'█' * filled}{'░' * empty}] {probability:.1f}%
{probability:.1f}% chance of breach

```

## Loss Scenarios
| Scenario | Impact | Probability | Visual |
|----------|--------|-------------|--------|
"""
    for name, data in scenarios.items():
        # Create impact bar
        impact = data['loss_mm']
        filled = int(impact * 10 / 5)  # Scale to 0-10
        filled = min(filled, 10)
        
        dashboard += f"| **{name}** | ${impact}M | {data['prob']}% | {'█' * filled}{'░' * (10-filled)} |\n"
    
    # Add strategy recommendation
    dashboard += f"""
## Recommended Action
```

╔════════════════════════════════════════════════════╗
║  ✅ CUT LOSS IMMEDIATELY                            ║
║  Expected Loss: $2.67M                              ║
║  Risk Level: LOW (once position closed)             ║
║  Next: Add margin or hedge remaining exposure       ║
╚════════════════════════════════════════════════════╝

```
"""
    return dashboard
```

INTEGRATION IN AGENT

```python
class JagabotAgent:
    def __init__(self, visualization_mode="base64"):
        self.viz_mode = visualization_mode  # "base64", "ascii", "markdown", "none"
    
    def analyze_with_visuals(self, query, portfolio, market):
        # 1. Run standard analysis
        analysis = self.run_analysis(query, portfolio, market)
        
        # 2. Get Monte Carlo results using STANDARD function
        mc_results = standard_monte_carlo(
            current_price=market['current']['WTI'],
            target_price=45,
            vix=market['current']['VIX']
        )
        
        # 3. Generate visualization based on mode
        if self.viz_mode == "base64":
            # For Colab/Notebooks
            chart = generate_dashboard_base64(
                prices=mc_results['all_prices'],
                current_price=52.80,
                target_price=45,
                probability=mc_results['probability'],
                loss_scenarios=self.loss_scenarios
            )
            visual = f"![Jagabot Dashboard](data:image/png;base64,{chart})"
            
        elif self.viz_mode == "ascii":
            # For terminal/CLI
            visual = generate_ascii_dashboard(
                prices=mc_results['all_prices'],
                current_price=52.80,
                target_price=45,
                probability=mc_results['probability']
            )
            
        elif self.viz_mode == "markdown":
            # For text-based responses
            visual = generate_markdown_dashboard(
                probability=mc_results['probability'],
                equity=analysis['equity'],
                loss=analysis['loss'],
                scenarios=self.loss_scenarios
            )
        else:
            visual = ""
        
        # 4. Combine with analysis text
        return f"""
{visual}

## 📊 Analysis Summary
{analysis['summary']}

## 🎯 Recommended Action
{analysis['recommendation']}
"""
```

TESTING REQUIREMENTS

After implementation, verify:

1. Monte Carlo Consistency
   · Same inputs → same outputs (seed=42)
   · Colab and Jagabot give same probability (±1%)
   · VIX=58 → probability ~17-25%
2. Visualization Working
   · Base64 images render in Colab
   · ASCII charts display properly in terminal
   · Markdown tables show correctly
3. Integration
   · Agent calls standard function automatically
   · Visualization mode configurable
   · No performance degradation

SUCCESS CRITERIA

✅ Monte Carlo probability difference < 2% between Colab and Agent
✅ All visualizations generate without errors
✅ Dashboard shows all key metrics (probability, loss scenarios, risk matrix)
✅ Agent includes visual in response when requested
✅ Can switch between visualization modes via config

OUTPUT FILES TO MODIFY

1. jagabot/agent/tools/monte_carlo.py - Replace with standard function
2. jagabot/subagents/billing_agent.py - Update Monte Carlo calls
3. jagabot/agent/tools/visualization.py - NEW file with all chart functions
4. jagabot/core/orchestrator.py - Add visualization integration
5. jagabot/cli/agent.py - Add visualization mode option
6. Update Colab test script to use same standard function

```

---

This SCOPE prompt covers:
1. **Standardizing Monte Carlo** across all components
2. **Adding 3 visualization options** (base64, ASCII, markdown)
3. **Integration into agent workflow**
4. **Testing requirements**
