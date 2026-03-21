# jagabot/agent/context_builder.py
"""
ContextBuilder — Dynamic context assembly.
Replaces static bloated system prompt with
layered, query-relevant context injection.

Principle: Sharp > Comprehensive
  - Layer 1: core identity    (~300 tokens, ALWAYS)
  - Layer 2: relevant memory  (~200 tokens, topic-matched)
  - Layer 3: relevant tools   (~200 tokens, query-matched)
  - Layer 4: pending outcomes (~100 tokens, domain-matched)
  Total target: ~800 tokens vs current ~3000+

Wire into loop.py __init__:
    from jagabot.agent.context_builder import ContextBuilder
    self.ctx_builder = ContextBuilder(workspace, agents_md_path)

Wire into loop.py _process_message BEFORE LLM call:
    system_prompt = self.ctx_builder.build(
        query=msg.content,
        session_key=session.key,
        tools_available=list(self.tool_registry.keys()),
    )
    # Use system_prompt instead of static self.system_prompt
"""

import re
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Token estimates (conservative) ─────────────────────────────────
TARGET_LAYER1 = 350    # core identity
TARGET_LAYER2 = 250    # relevant memory
TARGET_LAYER3 = 200    # relevant tools
TARGET_LAYER4 = 120    # pending outcomes
TARGET_TOTAL  = 920    # total budget


# ── Tool relevance map ──────────────────────────────────────────────
# Maps query signals to likely tools needed
TOOL_RELEVANCE = {
    "financial": [
        "financial_cv", "monte_carlo", "var", "cvar", "yahoo_finance",
        "portfolio_analyzer", "early_warning", "stress_test",
        "decision_engine", "visualization",
    ],
    "stock": [  # Added for stock price queries
        "yahoo_finance", "decision_engine", "financial_cv",
    ],
    "research": [
        "web_search", "web_fetch", "researcher",
        "tri_agent", "quad_agent", "debate",
        "web_search_mcp",  # Real-time web search via MCP
    ],
    "memory": [
        "memory_fleet", "fuzzy_search", "knowledge_graph", "inference",
    ],
    "learning": [
        "meta_learning", "k1_bayesian", "k3_perspective",
        "evolution", "evaluate_result",
    ],
    "causal": [
        "statistical_engine", "bayesian_reasoner",
        "counterfactual_sim", "exec", "inference",
    ],
    "ideas": [
        "tri_agent", "quad_agent", "debate",
        "tri_agent", "quad_agent", "debate",
        "k3_perspective", "meta_learning",
    ],
    "code": [
        "exec", "write_file", "read_file",
        "edit_file", "shell",
    ],
    "healthcare": [
        "web_search", "researcher", "tri_agent",
        "accountability", "education",
    ],
    "spawn": [
        "spawn", "subagent",
    ],
    "parallel": [
        "spawn", "subagent",
    ],
    "reasoning": [
        "inference", "knowledge_graph", "fuzzy_search",
    ],
}

# Maps query signals to topics
SIGNAL_TO_TOPIC = {
    "financial": ["stock", "portfolio", "var", "cvar", "margin", "ticker", "aapl", "nvda", "msft", "tsla", "nasdaq", "nyse", "shares",
                  "equity", "monte carlo", "risk", "volatility",
                  "vix", "price", "fund", "investment"],
    "research":  ["research", "hypothesis", "study", "paper",
                  "quantum", "literature", "experiment"],
    "causal":    ["ipw", "causal", "confounder", "ate",
                  "propensity", "regression", "inference", "logical"],
    "healthcare":["hospital", "patient", "clinical", "hipaa",
                  "counselor", "mental health", "therapy"],
    "ideas":     ["idea", "brainstorm", "creative", "novel",
                  "strategy", "innovative", "suggest"],
    "code":      ["code", "script", "python", "function",
                  "calculate", "compute", "run", "exec"],
    "memory":    ["remember", "recall", "history", "past",
                  "previous", "memory", "what did", "find in", "search", "fact"],
    "research":  ["fuzzy_search", "web_search", "web_fetch", "researcher",
                  "study", "investigate", "analyze", "research", "infer", "derive"],
    "learning":  ["calibration", "accuracy", "improve",
                  "self-improvement", "loop", "outcome"],
    "reasoning": ["inference", "logical", "chain", "implies", "causes",
                  "deduce", "reasoning chain", "multi-hop", "fact"],
}

# Export for tool_filter.py
__all__ = ['TOOL_RELEVANCE', 'SIGNAL_TO_TOPIC', 'ContextBuilder']


class ContextBuilder:
    """
    Builds dynamic, query-relevant system context.
    Keeps the most important instructions sharpest.
    """

    def __init__(
        self,
        workspace: Path,
        agents_md_path: Optional[Path] = None,
    ) -> None:
        self.workspace      = Path(workspace)
        self.memory_dir     = self.workspace / "memory"
        self.agents_md_path = agents_md_path or Path("/root/.jagabot/AGENTS.md")
        self._core_identity = self._load_core_identity()

    # ── Public API ──────────────────────────────────────────────────

    def build(
        self,
        query:            str,
        session_key:      str       = "",
        tools_available:  list      = None,
        include_pending:  bool      = True,
    ) -> str:
        """
        Build system prompt for this specific query.
        Returns layered context string ready to inject.
        """
        topic   = self._detect_topic(query)
        parts   = []
        tokens  = 0

        # ── Layer 1: Core identity (always) ────────────────────────
        layer1 = self._core_identity
        parts.append(layer1)
        tokens += self._estimate_tokens(layer1)
        logger.debug(f"Context L1: {tokens} tokens (core identity)")

        # ── Layer 2: Relevant memory ────────────────────────────────
        if tokens < TARGET_TOTAL - TARGET_LAYER2:
            layer2 = self._load_relevant_memory(topic, query)
            if layer2:
                parts.append(layer2)
                tokens += self._estimate_tokens(layer2)
                logger.debug(f"Context L2: +{self._estimate_tokens(layer2)} tokens (memory)")

        # ── Layer 3: Relevant tools ─────────────────────────────────
        if tokens < TARGET_TOTAL - TARGET_LAYER3:
            layer3 = self._get_relevant_tools(
                topic, query, tools_available or []
            )
            if layer3:
                parts.append(layer3)
                tokens += self._estimate_tokens(layer3)
                logger.debug(f"Context L3: +{self._estimate_tokens(layer3)} tokens (tools)")

        # ── Layer 4: Pending outcomes ───────────────────────────────
        if include_pending and tokens < TARGET_TOTAL - TARGET_LAYER4:
            layer4 = self._load_pending_outcomes(topic)
            if layer4:
                parts.append(layer4)
                tokens += self._estimate_tokens(layer4)
                logger.debug(f"Context L4: +{self._estimate_tokens(layer4)} tokens (pending)")

        total_context = "\n\n---\n\n".join(parts)
        logger.debug(
            f"Context built: ~{tokens} tokens | "
            f"topic={topic} | layers={len(parts)}"
        )
        return total_context

    def get_stats(self) -> dict:
        """Return context budget stats."""
        return {
            "target_tokens": TARGET_TOTAL,
            "layer1_budget": TARGET_LAYER1,
            "layer2_budget": TARGET_LAYER2,
            "layer3_budget": TARGET_LAYER3,
            "layer4_budget": TARGET_LAYER4,
            "core_identity_tokens": self._estimate_tokens(
                self._core_identity
            ),
        }

    # ── Internal helpers ────────────────────────────────────────────

    def _load_core_identity(self) -> str:
        """
        Load core identity from core_identity.md.
        Falls back to minimal inline identity if file missing.
        """
        # Check multiple locations
        candidates = [
            Path("/root/.jagabot/core_identity.md"),
            Path("/root/nanojaga/core_identity.md"),
            self.workspace / "core_identity.md",
        ]
        for path in candidates:
            if path.exists():
                content = path.read_text(encoding="utf-8")
                logger.debug(f"Loaded core identity from {path}")
                return content

        # Inline fallback — minimal but functional
        logger.warning(
            "core_identity.md not found — using inline fallback"
        )
        return """# jagabot
Truthful executor. JAGA = guard/protect (Malay).
Never present inference as fact.
Call tool FIRST, then report its output.
Label illustrative numbers: [e.g. 0.72]
Explain questions → NLP only, no exec.
Calculation questions → exec to verify."""

    def _detect_topic(self, text: str) -> str:
        """Detect primary topic from query text."""
        text_lower = text.lower()
        scores     = {}
        for topic, signals in SIGNAL_TO_TOPIC.items():
            scores[topic] = sum(
                1 for s in signals if s in text_lower
            )
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _load_relevant_memory(self, topic: str, query: str) -> str:
        """
        Load topic-relevant snippets from MEMORY.md.
        Returns empty string if nothing relevant found.
        """
        memory_file = self.memory_dir / "MEMORY.md"
        if not memory_file.exists():
            return ""

        try:
            content  = memory_file.read_text(encoding="utf-8")
            lines    = content.split("\n")
            relevant = []
            # Find lines containing topic keywords
            keywords = SIGNAL_TO_TOPIC.get(topic, []) + query.lower().split()[:5]

            current_section = []
            in_relevant     = False

            for line in lines:
                line_lower = line.lower()
                if any(kw in line_lower for kw in keywords):
                    in_relevant = True
                if in_relevant:
                    current_section.append(line)
                    if len(current_section) >= 5:
                        relevant.extend(current_section)
                        current_section = []
                        in_relevant = False
                        if len(relevant) >= 20:
                            break

            if not relevant:
                return ""

            snippet = "\n".join(relevant[:15])
            return f"## Relevant Memory\n\n{snippet}"

        except Exception as e:
            logger.debug(f"Memory load skipped: {e}")
            return ""

    def _get_relevant_tools(
        self,
        topic:           str,
        query:           str,
        tools_available: list,
    ) -> str:
        """
        Return short list of likely-needed tools for this query.
        Much shorter than full tool documentation.
        """
        relevant = set()

        # Topic-based tools
        for t in TOOL_RELEVANCE.get(topic, []):
            if t in tools_available:
                relevant.add(t)

        # Query-specific overrides
        q_lower = query.lower()
        if any(w in q_lower for w in ["idea", "brainstorm", "creative"]):
            relevant.update(["tri_agent", "quad_agent"])
        if any(w in q_lower for w in ["calculate", "compute", "run"]):
            relevant.update(["exec", "write_file"])
        if any(w in q_lower for w in ["search", "research", "find"]):
            relevant.update(["web_search", "researcher"])

        # Cap at 8 tools
        tool_list = sorted(relevant)[:8]

        if not tool_list:
            return ""

        lines = ["## Available Tools (relevant to this query)"]
        for t in tool_list:
            lines.append(f"- {t}")

        return "\n".join(lines)

    def _load_pending_outcomes(self, topic: str) -> str:
        """
        Load pending outcomes relevant to current topic.
        Reminds agent what's waiting for verification.
        """
        pending_file = self.memory_dir / "pending_outcomes.json"
        if not pending_file.exists():
            return ""

        try:
            import json
            data    = json.loads(
                pending_file.read_text(encoding="utf-8")
            )
            pending = data if isinstance(data, list) else []

            # Filter to topic-relevant pending items
            relevant = [
                p for p in pending
                if p.get("status") == "pending"
                and (
                    topic == "general"
                    or topic in p.get("topic_tag", "")
                    or any(
                        kw in p.get("conclusion", "").lower()
                        for kw in SIGNAL_TO_TOPIC.get(topic, [])
                    )
                )
            ][:3]  # max 3 pending shown in context

            if not relevant:
                return ""

            lines = [f"## ⚠️ Pending Outcomes ({len(relevant)} unverified)"]
            for p in relevant:
                age = self._days_ago(p.get("created_at", ""))
                lines.append(
                    f"- [{age}] {p.get('conclusion', '')[:60]}..."
                )
            lines.append(
                "Tell me if any of these were correct, "
                "wrong, or partially right."
            )

            return "\n".join(lines)

        except Exception as e:
            logger.debug(f"Pending outcomes load skipped: {e}")
            return ""

    def _days_ago(self, iso: str) -> str:
        """Format ISO date as days ago."""
        try:
            from datetime import datetime
            dt   = datetime.fromisoformat(iso)
            days = (datetime.now() - dt).days
            return f"{days}d ago" if days > 0 else "today"
        except Exception:
            return "?"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4
