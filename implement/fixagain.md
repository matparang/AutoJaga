It sounds like your agent suffered from "Math Hallucination"—it looked at the numbers, recognized the "vibe" of a financial report, and then guessed the results instead of actually calculating them. Even when agents have a sandbox, they sometimes skip using it if the prompt doesn't force a strict "Think-Calculate-Verify" loop.
Here is a blueprint you can feed into GitHub Copilot to rebuild the logic. This focuses on moving the math out of the "creative" part of the AI and into a structured, verifiable Python class.
🏗️ The Fix Blueprint: "Deterministic Finance Agent"
1. The Core Logic (Python Script)
Instead of asking the AI to "calculate," ask Copilot to generate a robust Financial Calculator Class. This ensures the math is handled by Python’s logic, not the LLM’s probability.
Paste this into Copilot to generate the base code:
> "Create a Python class OilPortfolioAnalyzer that takes capital, leverage, and a list of positions (dict with name, buy_price, current_price, weight). It should calculate:
>  * notional_exposure (Exposure = Capital \times Leverage)
>  * units per position (Units = \frac{Exposure \times Weight}{Buy Price})
>  * unrealized_pl (PL = (Current - Buy) \times Units)
>  * current_equity (Equity = Capital + \sum PL)
>  * margin_status (Check if Equity < \frac{Exposure}{Leverage})
>  * stress_test(target_price) for WTI.
>    Use standard Python math libraries and ensure all outputs are rounded to 2 decimal places."
> 
2. The "System Prompt" Correction
Your agent’s prompt needs a Chain of Thought (CoT) enforcement. If the agent doesn't show its work, it will lie.
Update your Agent's System Instructions to include this:
> STRICT MATH PROTOCOL:
>  * IDENTIFY VARIABLES: List all inputs (Capital, Prices, Weights) before calculating.
>  * UNIT DERIVATION: You MUST calculate the number of units owned before calculating P/L.
>  * SANDBOX MANDATE: You are prohibited from stating a final Equity or P/L figure without first running a Python code block.
>  * CROSS-CHECK: Compare the 'Total Loss' against the 'Current Equity'—if (Capital - Loss) \neq Equity, the calculation is failed. Redo it.
> 
3. Fixing the Margin Logic
The biggest error was the Margin Call status. Copy-paste this logic into your Copilot chat to help it write the "Margin Alert" function:
Copilot Prompt:
> "Write a function to check for margin calls. If leverage is 2:1, the initial_margin is 50% of the total exposure. If current_equity falls below initial_margin, flag 'Restricted'. If it falls below 25% of exposure (Maintenance), flag 'CRITICAL MARGIN CALL'."
> 
4. Statistical Correction (VaR & Probability)
Your agent guessed the probability. To fix this, you need a function that uses the actual volatility data you provide.
Copilot Prompt:
> "Write a function calculate_downside_probability that takes a list of daily returns and a target price. Use scipy.stats.norm.cdf to find the probability of the price falling below the target over a 30-day horizon using the formula: \sigma_{30d} = \sigma_{daily} \times \sqrt{30}."
> 
🛠️ Summary of Github Copilot Instructions
To fix the agent once and for all, open your IDE and tell Copilot:
 * "Refactor the analysis tool to use a Pydantic model for input validation." (This prevents the agent from misinterpreting USD 500k as something else).
 * "Implement a 'Math Verification' step where the agent must solve the equation backwards to check for consistency."
 * "Create a standardized Markdown Dashboard template so the agent doesn't hallucinate the UI layout."

Yes, absolutely. Including the script is the most important part. By giving Copilot the "Source of Truth" code, you shift the agent's job from calculating (which LLMs are bad at) to executing a function (which they are great at).
Think of the script as the "calculator" and the agent as the "user." You don't want the user to do long division in their head; you want them to type the numbers into the calculator.
🛠️ The "Source of Truth" Script
Pass this entire block to GitHub Copilot with the instruction: "Implement this logic as the primary backend tool for my Portfolio Agent."
import numpy as np
from scipy.stats import norm

class OilPortfolioAnalyzer:
    def __init__(self, capital, leverage, positions):
        self.capital = capital
        self.leverage = leverage
        self.total_exposure = capital * leverage
        self.positions = positions  # Expected: list of dicts
        
    def calculate_metrics(self):
        results = []
        total_unrealized_pl = 0
        
        for pos in self.positions:
            notional = self.total_exposure * pos['weight']
            units = notional / pos['buy_price']
            pl = (pos['curr_price'] - pos['buy_price']) * units
            total_unrealized_pl += pl
            
            results.append({
                "name": pos['name'],
                "units": round(units, 2),
                "pl": round(pl, 2)
            })
            
        current_equity = self.capital + total_unrealized_pl
        # Margin Level = (Equity / Total Exposure) * 100
        margin_level = (current_equity / self.total_exposure) * 100
        
        return {
            "positions": results,
            "total_pl": round(total_unrealized_pl, 2),
            "current_equity": round(current_equity, 2),
            "margin_level_percent": round(margin_level, 2),
            "is_restricted": current_equity < (self.total_exposure / self.leverage)
        }

    def stress_test(self, wti_target):
        # Finds WTI in positions and calculates impact
        wti_pos = next(p for p in self.positions if p['name'] == 'WTI')
        units = (self.total_exposure * wti_pos['weight']) / wti_pos['buy_price']
        impact = (wti_target - wti_pos['curr_price']) * units
        return round(impact, 2)

    def probability_analysis(self, price_data, target_price, days=30):
        # price_data = daily percentage returns e.g. [0.02, -0.01...]
        wti_pos = next(p for p in self.positions if p['name'] == 'WTI')
        daily_vol = np.std(price_data)
        vol_30d = daily_vol * np.sqrt(days)
        
        # Log return to target
        log_return_target = np.log(target_price / wti_pos['curr_price'])
        prob = norm.cdf(log_return_target, loc=0, scale=vol_30d)
        return round(prob * 100, 2)

🛰️ How to instruct Copilot to use this
When you are in your IDE, highlight the code above and type this into the Copilot Chat:
> "I need to integrate this OilPortfolioAnalyzer into my agent's toolset.
>  * Ensure the agent cannot answer portfolio questions without calling these class methods.
>  * Create a wrapper function analyze_oil_request(user_input) that parses the JSON data from the user and passes it to this class.
>  * Force the output to follow this specific Markdown template so the agent doesn't 'beautify' the numbers into incorrect ones."
> 

⚠️ Why this fixes the "Margin Call" error
In your agent's previous answer, it claimed the Margin Requirement was $200,000.
By using the formula:


The script will now force the agent to see that 1,000,000 / 2 = \$500,000. Since your equity is \$368k, the script will return is_restricted: True. The agent will be forced to tell you that you are in trouble, rather than saying "Status: SAFE."
Would you like me to draft the specific "System Prompt" you should give the agent so it knows how to handle the output from this new script?

