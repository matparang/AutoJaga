#!/usr/bin/env python3
"""Decision Engine example — Bull/Bear/Buffet analysis."""

import asyncio
import json
from jagabot.agent.tools import DecisionTool, EducationTool, AccountabilityTool


async def main():
    dt = DecisionTool()
    et = EducationTool()
    at = AccountabilityTool()

    bull = json.loads(await dt.execute(method="bull_perspective", params={
        "probability_below_target": 25,
        "current_price": 4.50,
        "target_price": 3.80,
        "cv": 0.30,
        "recovery_months": 6,
    }))
    print(f"🐂 Bull: {bull['verdict']} (confidence {bull['confidence']}%)")

    bear = json.loads(await dt.execute(method="bear_perspective", params={
        "probability_below_target": 25,
        "current_price": 4.50,
        "target_price": 3.80,
        "var_pct": 8.5,
        "risk_level": "moderate",
    }))
    print(f"🐻 Bear: {bear['verdict']} (confidence {bear['confidence']}%)")

    buffet = json.loads(await dt.execute(method="buffet_perspective", params={
        "probability_below_target": 25,
        "current_price": 4.50,
        "target_price": 3.80,
        "intrinsic_value": 6.00,
        "recovery_months": 6,
    }))
    print(f"🧓 Buffet: {buffet['verdict']} (confidence {buffet['confidence']}%)")

    collapsed = json.loads(await dt.execute(method="collapse_perspectives", params={
        "bull": bull, "bear": bear, "buffet": buffet,
    }))
    print(f"\n🎯 Final: {collapsed['final_verdict']} ({collapsed['consensus']})")

    dashboard = await dt.execute(method="decision_dashboard", params={
        "bull": bull, "bear": bear, "buffet": buffet, "collapsed": collapsed,
    })
    print("\n" + dashboard)

    explanation = json.loads(await et.execute(method="explain_concept", params={
        "concept": "var", "locale": "en",
    }))
    print(f"\n📚 {explanation['title']}")
    print(explanation["explanation"][:200] + "...")

    flags = json.loads(await at.execute(method="detect_red_flags", params={
        "fund_manager_claims": [
            "I guarantee 15% annual returns with zero risk.",
            "This is a limited opportunity — invest today or miss out.",
        ],
    }))
    print(f"\n🚩 Red flags detected: {flags['count']}")
    for f in flags["red_flags"]:
        print(f"   [{f['severity']}] {f['flag']}: {f['detail']}")


if __name__ == "__main__":
    asyncio.run(main())
