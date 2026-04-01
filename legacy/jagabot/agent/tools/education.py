"""Education tool — concept explainers, bilingual glossary, result interpretation."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


_CONCEPTS = {
    "monte_carlo": {
        "en": {
            "title": "Monte Carlo Simulation",
            "explanation": (
                "Monte Carlo simulation uses random sampling to estimate the probability of different outcomes. "
                "In finance, we simulate thousands of possible price paths using Geometric Brownian Motion (GBM). "
                "Each path follows: S(t+1) = S(t) × exp((μ − ½σ²)Δt + σ√Δt × Z), where Z is a random normal variable. "
                "The result tells us the probability of a price falling below (or above) a threshold."
            ),
            "key_insight": "More simulations = more accurate probability. We use 10,000 paths by default.",
        },
        "ms": {
            "title": "Simulasi Monte Carlo",
            "explanation": (
                "Simulasi Monte Carlo menggunakan pensampelan rawak untuk menganggar kebarangkalian hasil yang berbeza. "
                "Dalam kewangan, kita mensimulasikan beribu-ribu laluan harga menggunakan Gerakan Brown Geometri (GBM). "
                "Hasilnya memberitahu kita kebarangkalian harga jatuh di bawah (atau naik di atas) paras tertentu."
            ),
            "key_insight": "Lebih banyak simulasi = kebarangkalian lebih tepat. Kita gunakan 10,000 laluan.",
        },
    },
    "cv": {
        "en": {
            "title": "Coefficient of Variation (CV)",
            "explanation": (
                "CV = Standard Deviation / Mean. It measures relative volatility — "
                "how much an asset's price varies compared to its average. "
                "CV < 0.3 is low risk, 0.3-0.5 is moderate, > 0.5 is high risk. "
                "Unlike standard deviation alone, CV allows comparing risk across different price levels."
            ),
            "key_insight": "CV normalises risk — a RM1 stock with RM0.30 std is riskier (CV=0.3) than a RM100 stock with RM20 std (CV=0.2).",
        },
        "ms": {
            "title": "Pekali Variasi (CV)",
            "explanation": (
                "CV = Sisihan Piawai / Min. Ia mengukur turun naik relatif — "
                "berapa banyak harga aset berubah berbanding puratanya. "
                "CV < 0.3 risiko rendah, 0.3-0.5 sederhana, > 0.5 tinggi."
            ),
            "key_insight": "CV menormalkan risiko — membolehkan perbandingan antara aset berlainan harga.",
        },
    },
    "var": {
        "en": {
            "title": "Value at Risk (VaR)",
            "explanation": (
                "VaR answers: 'What is the maximum I could lose in a day/week/month, with X% confidence?' "
                "For example, '95% VaR of RM5,000' means there is only a 5% chance of losing more than RM5,000. "
                "It does NOT tell you how much worse it could get beyond that threshold — that's what CVaR does."
            ),
            "key_insight": "VaR is a minimum worst-case, not maximum. The tail beyond VaR can be much worse.",
        },
        "ms": {
            "title": "Nilai Berisiko (VaR)",
            "explanation": (
                "VaR menjawab: 'Berapa maksimum kerugian saya dalam sehari/seminggu/sebulan, dengan keyakinan X%?' "
                "Contoh: '95% VaR RM5,000' bermaksud hanya 5% peluang rugi lebih dari RM5,000."
            ),
            "key_insight": "VaR adalah kerugian minimum kes terburuk, bukan maksimum.",
        },
    },
    "cvar": {
        "en": {
            "title": "Conditional Value at Risk (CVaR / Expected Shortfall)",
            "explanation": (
                "CVaR measures the AVERAGE loss in the worst cases beyond the VaR threshold. "
                "If 95% VaR is RM5,000, CVaR tells you: 'In the worst 5% of cases, you lose RM8,000 on average.' "
                "CVaR is always >= VaR and is considered a more conservative risk measure."
            ),
            "key_insight": "CVaR captures tail risk — the severity of extreme losses, not just their probability.",
        },
        "ms": {
            "title": "Nilai Berisiko Bersyarat (CVaR)",
            "explanation": (
                "CVaR mengukur PURATA kerugian dalam kes-kes terburuk melebihi ambang VaR. "
                "CVaR sentiasa >= VaR dan dianggap ukuran risiko yang lebih konservatif."
            ),
            "key_insight": "CVaR menangkap risiko ekor — keterukan kerugian melampau.",
        },
    },
    "bayesian": {
        "en": {
            "title": "Bayesian Analysis",
            "explanation": (
                "Bayesian analysis updates probability estimates as new evidence arrives. "
                "Start with a prior belief (e.g. 30% chance of crisis), then update with new data "
                "(e.g. VIX spike, margin call) using Bayes' theorem: P(A|B) = P(B|A) × P(A) / P(B). "
                "Each piece of evidence strengthens or weakens the probability."
            ),
            "key_insight": "Bayesian thinking is rational: update beliefs with evidence, don't ignore new data.",
        },
        "ms": {
            "title": "Analisis Bayesian",
            "explanation": (
                "Analisis Bayesian mengemaskini anggaran kebarangkalian apabila bukti baru tiba. "
                "Bermula dengan kepercayaan awal, kemudian kemas kini dengan data baru menggunakan teorem Bayes."
            ),
            "key_insight": "Pemikiran Bayesian: kemas kini kepercayaan dengan bukti, jangan abaikan data baru.",
        },
    },
    "vix": {
        "en": {
            "title": "VIX — The Fear Index",
            "explanation": (
                "VIX measures expected market volatility over the next 30 days. "
                "VIX < 15: calm market (low fear). VIX 15-25: normal uncertainty. "
                "VIX 25-35: elevated fear. VIX > 35: crisis-level panic. "
                "We use VIX to set the volatility parameter in Monte Carlo simulations. "
                "VIX 58 means the market expects 58% annualised volatility."
            ),
            "key_insight": "When VIX is high, option prices are expensive and price swings are expected.",
        },
        "ms": {
            "title": "VIX — Indeks Ketakutan",
            "explanation": (
                "VIX mengukur turun naik pasaran yang dijangka dalam 30 hari akan datang. "
                "VIX < 15: pasaran tenang. VIX 15-25: ketidakpastian biasa. "
                "VIX > 35: panik tahap krisis."
            ),
            "key_insight": "VIX tinggi = harga opsyen mahal, ayunan harga besar dijangka.",
        },
    },
    "ci": {
        "en": {
            "title": "Confidence Interval (CI)",
            "explanation": (
                "A 95% confidence interval means: if we repeated the analysis 100 times, "
                "the true value would fall within this range 95 times. "
                "Wider CI = more uncertainty. Narrow CI = more precision. "
                "In Monte Carlo, CI tells us the range of likely prices."
            ),
            "key_insight": "CI is about precision, not probability of a single outcome.",
        },
        "ms": {
            "title": "Selang Keyakinan (CI)",
            "explanation": (
                "Selang keyakinan 95% bermaksud: jika analisis diulang 100 kali, "
                "nilai sebenar akan berada dalam julat ini 95 kali."
            ),
            "key_insight": "CI tentang ketepatan, bukan kebarangkalian satu hasil.",
        },
    },
}


# 50-term bilingual glossary
_GLOSSARY = {
    "asset": {"en": "Asset — anything of value (stocks, bonds, property)", "ms": "Aset — apa-apa yang bernilai (saham, bon, hartanah)"},
    "bear_market": {"en": "Bear Market — market declining 20%+ from peak", "ms": "Pasaran Beruang — pasaran jatuh 20%+ dari puncak"},
    "beta": {"en": "Beta — sensitivity of asset returns to market returns", "ms": "Beta — sensitiviti pulangan aset terhadap pasaran"},
    "bull_market": {"en": "Bull Market — sustained market uptrend", "ms": "Pasaran Lembu Jantan — pasaran naik berterusan"},
    "capital_gain": {"en": "Capital Gain — profit from selling an asset above purchase price", "ms": "Keuntungan Modal — untung dari menjual aset melebihi harga beli"},
    "correlation": {"en": "Correlation — degree to which two assets move together (-1 to +1)", "ms": "Korelasi — tahap dua aset bergerak bersama (-1 hingga +1)"},
    "cv": {"en": "CV (Coefficient of Variation) — stddev/mean, measures relative risk", "ms": "CV (Pekali Variasi) — sisihan piawai/min, ukur risiko relatif"},
    "cvar": {"en": "CVaR (Conditional VaR) — average loss beyond VaR threshold", "ms": "CVaR — purata kerugian melebihi ambang VaR"},
    "default": {"en": "Default — failure to repay a debt obligation", "ms": "Mungkir — kegagalan membayar balik hutang"},
    "diversification": {"en": "Diversification — spreading investments to reduce risk", "ms": "Kepelbagaian — merebak pelaburan untuk kurangkan risiko"},
    "dividend": {"en": "Dividend — company profit distributed to shareholders", "ms": "Dividen — keuntungan syarikat diagihkan kepada pemegang saham"},
    "drawdown": {"en": "Drawdown — decline from peak to trough", "ms": "Kejatuhan — penurunan dari puncak ke dasar"},
    "equity": {"en": "Equity — ownership value = assets minus liabilities", "ms": "Ekuiti — nilai pemilikan = aset tolak liabiliti"},
    "expected_return": {"en": "Expected Return — weighted average of possible returns", "ms": "Pulangan Jangkaan — purata berwajaran pulangan mungkin"},
    "gbm": {"en": "GBM (Geometric Brownian Motion) — model for stock price movement", "ms": "GBM — model pergerakan harga saham"},
    "hedge": {"en": "Hedge — investment to offset potential losses", "ms": "Lindung Nilai — pelaburan untuk mengimbangi kerugian"},
    "inflation": {"en": "Inflation — general increase in price levels", "ms": "Inflasi — kenaikan umum tahap harga"},
    "intrinsic_value": {"en": "Intrinsic Value — true worth of an asset based on fundamentals", "ms": "Nilai Intrinsik — nilai sebenar aset berdasarkan asas"},
    "leverage": {"en": "Leverage — using borrowed money to amplify returns", "ms": "Leveraj — gunakan wang pinjaman untuk meningkatkan pulangan"},
    "liability": {"en": "Liability — financial obligation or debt", "ms": "Liabiliti — obligasi kewangan atau hutang"},
    "liquidity": {"en": "Liquidity — ease of converting an asset to cash", "ms": "Kecairan — kemudahan menukar aset kepada tunai"},
    "margin_call": {"en": "Margin Call — demand to deposit more collateral", "ms": "Panggilan Margin — tuntutan menambah cagaran"},
    "margin_of_safety": {"en": "Margin of Safety — buffer between price and intrinsic value", "ms": "Margin Keselamatan — penampan antara harga dan nilai intrinsik"},
    "market_cap": {"en": "Market Cap — total market value of company shares", "ms": "Modal Pasaran — jumlah nilai pasaran saham syarikat"},
    "monte_carlo": {"en": "Monte Carlo — simulation using random sampling", "ms": "Monte Carlo — simulasi menggunakan pensampelan rawak"},
    "nav": {"en": "NAV (Net Asset Value) — fund value per unit", "ms": "NAV — nilai aset bersih per unit"},
    "p_e_ratio": {"en": "P/E Ratio — price per share / earnings per share", "ms": "Nisbah P/E — harga sesaham / pendapatan sesaham"},
    "portfolio": {"en": "Portfolio — collection of investments", "ms": "Portfolio — koleksi pelaburan"},
    "principal": {"en": "Principal — original amount invested or loaned", "ms": "Prinsipal — jumlah asal yang dilaburkan atau dipinjamkan"},
    "probability": {"en": "Probability — likelihood of an event (0-100%)", "ms": "Kebarangkalian — kemungkinan sesuatu berlaku (0-100%)"},
    "rebalancing": {"en": "Rebalancing — adjusting portfolio weights to target allocation", "ms": "Pengimbangan Semula — laraskan wajaran portfolio"},
    "recovery_time": {"en": "Recovery Time — days/months to return to pre-loss level", "ms": "Masa Pemulihan — hari/bulan untuk kembali ke paras sebelum rugi"},
    "return": {"en": "Return — gain or loss on an investment", "ms": "Pulangan — untung atau rugi pelaburan"},
    "risk": {"en": "Risk — uncertainty of returns; possibility of losing money", "ms": "Risiko — ketidakpastian pulangan; kemungkinan rugi"},
    "risk_free_rate": {"en": "Risk-Free Rate — return on zero-risk investment (e.g. government bonds)", "ms": "Kadar Bebas Risiko — pulangan pelaburan tanpa risiko"},
    "roi": {"en": "ROI (Return on Investment) — profit relative to cost", "ms": "ROI — pulangan berbanding kos"},
    "sharpe_ratio": {"en": "Sharpe Ratio — excess return per unit of risk", "ms": "Nisbah Sharpe — pulangan lebihan per unit risiko"},
    "short_selling": {"en": "Short Selling — selling borrowed shares, hoping to buy back cheaper", "ms": "Jualan Pendek — menjual saham pinjaman, harap beli balik lebih murah"},
    "standard_deviation": {"en": "Standard Deviation — measure of price dispersion from the mean", "ms": "Sisihan Piawai — ukuran penyebaran harga dari min"},
    "stop_loss": {"en": "Stop Loss — automatic sell order to limit losses", "ms": "Henti Rugi — pesanan jual automatik untuk hadkan kerugian"},
    "stress_test": {"en": "Stress Test — simulation of extreme market scenarios", "ms": "Ujian Tekanan — simulasi senario pasaran melampau"},
    "var": {"en": "VaR (Value at Risk) — maximum expected loss at a confidence level", "ms": "VaR — kerugian maksimum dijangka pada tahap keyakinan"},
    "vix": {"en": "VIX — CBOE Volatility Index, the 'fear gauge'", "ms": "VIX — Indeks Turun Naik CBOE, 'pengukur ketakutan'"},
    "volatility": {"en": "Volatility — degree of price variation over time", "ms": "Turun Naik — darjah variasi harga sepanjang masa"},
    "volume": {"en": "Volume — number of shares traded in a period", "ms": "Volum — bilangan saham diniagakan dalam tempoh"},
    "yield": {"en": "Yield — income return on investment (dividends/interest)", "ms": "Hasil — pulangan pendapatan pelaburan (dividen/faedah)"},
    "zero_sum": {"en": "Zero-Sum — one party's gain equals another's loss", "ms": "Sifar Jumlah — keuntungan satu pihak = kerugian pihak lain"},
    "blue_chip": {"en": "Blue Chip — well-established, financially stable company", "ms": "Cip Biru — syarikat mantap dan stabil kewangan"},
    "basis_point": {"en": "Basis Point (bps) — 1/100th of a percentage point", "ms": "Titik Asas (bps) — 1/100 daripada satu mata peratusan"},
    "compound_interest": {"en": "Compound Interest — interest earned on interest", "ms": "Faedah Kompaun — faedah atas faedah"},
}


def explain_concept(concept: str, locale: str = "en") -> dict:
    """Explain a financial concept in plain language.

    Args:
        concept: Concept key (monte_carlo, cv, var, cvar, bayesian, vix, ci).
        locale: Language code (en, ms).

    Returns:
        dict with title, explanation, key_insight.
    """
    loc = locale if locale in ("en", "ms") else "en"
    if concept not in _CONCEPTS:
        available = list(_CONCEPTS.keys())
        return {"error": f"Unknown concept: {concept}. Available: {available}"}
    return _CONCEPTS[concept].get(loc, _CONCEPTS[concept]["en"])


def get_glossary(locale: str = "en", filter_terms: list[str] | None = None) -> dict:
    """Get the bilingual financial glossary.

    Args:
        locale: Language code (en, ms). Returns both if not specified.
        filter_terms: Optional list of term keys to filter.

    Returns:
        dict with terms.
    """
    loc = locale if locale in ("en", "ms") else "en"
    terms = {}
    source = filter_terms if filter_terms else list(_GLOSSARY.keys())
    for key in source:
        if key in _GLOSSARY:
            terms[key] = _GLOSSARY[key].get(loc, _GLOSSARY[key]["en"])
    return {"locale": loc, "terms": terms, "count": len(terms)}


def explain_result(tool_name: str, result: dict, locale: str = "en") -> dict:
    """Provide plain-language interpretation of a tool's output.

    Args:
        tool_name: Name of the tool that produced the result.
        result: The tool's output dict.
        locale: Language code.

    Returns:
        dict with interpretation and recommendation.
    """
    interpretation = []
    recommendation = ""

    if tool_name == "monte_carlo":
        prob = result.get("probability", 0)
        if prob > 50:
            interpretation.append(f"High risk: {prob}% chance of price dropping below target." if locale == "en"
                                  else f"Risiko tinggi: {prob}% peluang harga jatuh di bawah sasaran.")
            recommendation = "Consider reducing position or hedging." if locale == "en" else "Pertimbangkan mengurangkan posisi atau lindung nilai."
        else:
            interpretation.append(f"Moderate/low risk: only {prob}% chance of dropping below target." if locale == "en"
                                  else f"Risiko sederhana/rendah: hanya {prob}% peluang jatuh di bawah sasaran.")
            recommendation = "Position appears manageable." if locale == "en" else "Kedudukan kelihatan terurus."

    elif tool_name == "var":
        var_pct = result.get("var_pct", 0)
        interpretation.append(f"Maximum expected loss is {var_pct}% at {result.get('confidence', 0.95)*100:.0f}% confidence." if locale == "en"
                              else f"Kerugian maksimum dijangka {var_pct}% pada keyakinan {result.get('confidence', 0.95)*100:.0f}%.")

    elif tool_name == "early_warning":
        signals = result.get("signals", [])
        if signals:
            interpretation.append(f"{len(signals)} warning signal(s) detected." if locale == "en"
                                  else f"{len(signals)} isyarat amaran dikesan.")
        else:
            interpretation.append("No warning signals — situation appears stable." if locale == "en"
                                  else "Tiada isyarat amaran — keadaan kelihatan stabil.")

    elif tool_name == "decision_engine":
        verdict = result.get("final_verdict", "")
        interpretation.append(f"Final recommendation: {verdict}" if locale == "en"
                              else f"Cadangan akhir: {verdict}")

    else:
        interpretation.append(f"Results from {tool_name} tool." if locale == "en"
                              else f"Keputusan dari alat {tool_name}.")

    return {
        "tool": tool_name,
        "interpretation": interpretation,
        "recommendation": recommendation,
        "locale": locale,
    }


class EducationTool(Tool):
    """Financial education — explainers, glossary, result interpretation."""

    name = "education"
    description = (
        "Financial education tool — explains concepts in plain language (English + Malay). "
        "CALL THIS TOOL when the user asks 'what is VaR?', 'explain Monte Carlo', "
        "or needs help understanding tool output.\n\n"
        "Methods:\n"
        "- explain_concept: Plain-language explanation of MC, CV, VaR, CVaR, Bayesian, VIX, CI\n"
        "- get_glossary: 50-term bilingual glossary (en + ms). Can filter by terms.\n"
        "- explain_result: Interpret any tool's output in simple language\n\n"
        "Chain: Call after any analysis tool to provide user-friendly explanations. "
        "Pass locale='ms' for Malay explanations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["explain_concept", "get_glossary", "explain_result"],
                "description": (
                    "explain_concept: needs {concept: 'monte_carlo'|'cv'|'var'|'cvar'|'bayesian'|'vix'|'ci', locale?}. "
                    "get_glossary: needs {locale?, filter_terms?: ['var','cvar']}. "
                    "explain_result: needs {tool_name: 'monte_carlo', result: {...}, locale?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "explain_concept: {\"concept\": \"monte_carlo\", \"locale\": \"ms\"}\n"
                    "get_glossary: {\"locale\": \"ms\", \"filter_terms\": [\"var\", \"cvar\", \"vix\"]}\n"
                    "explain_result: {\"tool_name\": \"monte_carlo\", \"result\": {\"probability\": 29}, \"locale\": \"en\"}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "explain_concept": explain_concept,
        "get_glossary": get_glossary,
        "explain_result": explain_result,
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
