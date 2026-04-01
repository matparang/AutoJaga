"""Result stitcher — assembles worker results into a formatted dashboard."""

from __future__ import annotations

import json
from typing import Any

from jagabot.swarm.worker_pool import TaskResult


_LOCALE_HEADERS = {
    "en": {
        "title": "JAGABOT SWARM ANALYSIS",
        "risk": "Risk Metrics",
        "decision": "Decision Engine",
        "education": "Education",
        "accountability": "Accountability",
        "research": "Research",
        "content": "Content & Alerts",
        "summary": "Summary",
        "workers": "Workers Used",
        "elapsed": "Total Time",
    },
    "ms": {
        "title": "ANALISIS SWARM JAGABOT",
        "risk": "Metrik Risiko",
        "decision": "Enjin Keputusan",
        "education": "Pendidikan",
        "accountability": "Akauntabiliti",
        "research": "Penyelidikan",
        "content": "Kandungan & Amaran",
        "summary": "Ringkasan",
        "workers": "Pekerja Digunakan",
        "elapsed": "Jumlah Masa",
    },
}


class ResultStitcher:
    """Template-based assembler that turns worker results into a markdown dashboard."""

    def __init__(self, locale: str = "en"):
        self.locale = locale
        self.h = _LOCALE_HEADERS.get(locale, _LOCALE_HEADERS["en"])

    def stitch(self, results: list[TaskResult], query: str = "") -> str:
        """Stitch all results into a formatted markdown report."""
        sections: list[str] = []
        sections.append(self._header(query, results))

        risk_section = self._risk_section(results)
        if risk_section:
            sections.append(risk_section)

        decision_section = self._decision_section(results)
        if decision_section:
            sections.append(decision_section)

        edu_section = self._education_section(results)
        if edu_section:
            sections.append(edu_section)

        acc_section = self._accountability_section(results)
        if acc_section:
            sections.append(acc_section)

        research_section = self._research_section(results)
        if research_section:
            sections.append(research_section)

        content_section = self._content_section(results)
        if content_section:
            sections.append(content_section)

        sections.append(self._footer(results))
        return "\n\n".join(sections)

    def _header(self, query: str, results: list[TaskResult]) -> str:
        total_time = sum(r.elapsed_s for r in results)
        ok = sum(1 for r in results if r.success)
        lines = [
            f"# 📊 {self.h['title']}",
            "",
            f"> **Query:** {query}" if query else "",
            f"> **{self.h['workers']}:** {ok}/{len(results)} | "
            f"**{self.h['elapsed']}:** {total_time:.2f}s",
            "",
            "---",
        ]
        return "\n".join(line for line in lines if line is not None)

    def _risk_section(self, results: list[TaskResult]) -> str | None:
        risk_tools = {"monte_carlo", "var", "cvar", "stress_test",
                      "correlation", "recovery_time", "financial_cv", "early_warning"}
        risk_results = [r for r in results if r.tool_name in risk_tools and r.success]
        if not risk_results:
            return None

        lines = [f"## 📉 {self.h['risk']}", ""]
        for r in risk_results:
            data = r.data if isinstance(r.data, dict) else {}
            label = f"**{r.tool_name}** ({r.method})" if r.method and r.method != "__direct__" else f"**{r.tool_name}**"
            lines.append(f"### {label}")
            lines.append(f"*{r.elapsed_s:.2f}s*")
            lines.append("")
            lines.append(_format_dict(data))
            lines.append("")
        return "\n".join(lines)

    def _decision_section(self, results: list[TaskResult]) -> str | None:
        dec_results = [r for r in results if r.tool_name == "decision_engine" and r.success]
        if not dec_results:
            return None

        lines = [f"## 🎯 {self.h['decision']}", ""]
        for r in dec_results:
            data = r.data if isinstance(r.data, dict) else {}
            perspective = data.get("perspective", r.method)
            verdict = data.get("verdict", "N/A")
            confidence = data.get("confidence", "N/A")
            emoji = {"bull": "🐂", "bear": "🐻", "buffet": "🧓"}.get(perspective, "📊")
            lines.append(f"| {emoji} {perspective.title()} | {verdict} | Confidence: {confidence}% |")
        lines.insert(2, "| Perspective | Verdict | Confidence |")
        lines.insert(3, "|------------|---------|------------|")
        return "\n".join(lines)

    def _education_section(self, results: list[TaskResult]) -> str | None:
        edu_results = [r for r in results if r.tool_name == "education" and r.success]
        if not edu_results:
            return None

        lines = [f"## 📚 {self.h['education']}", ""]
        for r in edu_results:
            data = r.data if isinstance(r.data, dict) else {}
            title = data.get("title", r.method)
            explanation = data.get("explanation", str(data)[:200])
            lines.append(f"**{title}**")
            lines.append(explanation[:300])
            lines.append("")
        return "\n".join(lines)

    def _accountability_section(self, results: list[TaskResult]) -> str | None:
        acc_results = [r for r in results if r.tool_name == "accountability" and r.success]
        if not acc_results:
            return None

        lines = [f"## 🚩 {self.h['accountability']}", ""]
        for r in acc_results:
            data = r.data if isinstance(r.data, dict) else {}
            if "red_flags" in data:
                count = data.get("count", 0)
                lines.append(f"Red flags detected: **{count}**")
            elif "questions" in data:
                total = data.get("total", 0)
                lines.append(f"Accountability questions: **{total}**")
            else:
                lines.append(_format_dict(data))
            lines.append("")
        return "\n".join(lines)

    def _footer(self, results: list[TaskResult]) -> str:
        tools_used = sorted(set(r.tool_name for r in results))
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        lines = [
            "---",
            f"*Powered by Jagabot Swarm — {ok} tasks completed"
            + (f", {fail} failed" if fail else "")
            + f" across {len(tools_used)} tools*",
        ]
        return "\n".join(lines)

    def _research_section(self, results: list[TaskResult]) -> str | None:
        res = [r for r in results if r.tool_name == "researcher" and r.success]
        if not res:
            return None
        lines = [f"## 🔬 {self.h['research']}", ""]
        for r in res:
            data = r.data if isinstance(r.data, dict) else {}
            if r.method == "scan_trends":
                direction = data.get("direction", "?")
                strength = data.get("strength", 0)
                lines.append(f"**Trend:** {direction} (strength: {strength})")
            elif r.method == "detect_anomalies":
                total = data.get("total", 0)
                lines.append(f"**Anomalies detected:** {total}")
            else:
                lines.append(_format_dict(data))
            lines.append("")
        return "\n".join(lines)

    def _content_section(self, results: list[TaskResult]) -> str | None:
        content_tools = {"copywriter", "self_improver"}
        res = [r for r in results if r.tool_name in content_tools and r.success]
        if not res:
            return None
        lines = [f"## 📝 {self.h['content']}", ""]
        for r in res:
            data = r.data if isinstance(r.data, dict) else {}
            if r.tool_name == "copywriter":
                if "alert" in data:
                    lines.append(data["alert"])
                elif "summary" in data:
                    lines.append(data["summary"])
                else:
                    lines.append(_format_dict(data))
            elif r.tool_name == "self_improver":
                suggestions = data.get("suggestions", [])
                lines.append(f"**Improvement suggestions:** {len(suggestions)}")
                for s in suggestions[:3]:
                    lines.append(f"- [{s.get('priority', '?')}] {s.get('suggestion', '')[:200]}")
            lines.append("")
        return "\n".join(lines)


def _format_dict(data: dict[str, Any], indent: int = 0) -> str:
    """Format a dict as readable key-value lines."""
    if not data:
        return "_No data_"
    lines = []
    prefix = "  " * indent
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}- **{k}:**")
            lines.append(_format_dict(v, indent + 1))
        elif isinstance(v, list) and len(v) > 5:
            lines.append(f"{prefix}- **{k}:** [{len(v)} items]")
        elif isinstance(v, float):
            lines.append(f"{prefix}- **{k}:** {v:.4f}")
        else:
            lines.append(f"{prefix}- **{k}:** {v}")
    return "\n".join(lines)
