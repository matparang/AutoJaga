"""
KnowledgeGraph tool — visualize memory as interactive graph, show stats, query nodes.

Wraps an adapted KnowledgeGraphViewer (from nanobot/soul/knowledge_graph.py)
as a Tool ABC compliant tool for the agent loop.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool

# ---------------------------------------------------------------------------
# Color palette (dark theme)
# ---------------------------------------------------------------------------
_GROUP_COLORS: dict[str, str] = {
    "risk":         "#ff3333",
    "portfolio":    "#ff9900",
    "simulation":   "#33cc33",
    "equity":       "#3399ff",
    "code":         "#cc33ff",
    "memory":       "#ffdd00",
    "learning":     "#00cccc",
    "task":         "#ff6699",
    "error":        "#ff4444",
    "note":         "#aaaaaa",
    "permanent":    "#ffd700",
    "default":      "#888888",
}

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "risk":       ["risk", "var", "cvar", "stress", "drawdown", "volatility",
                   "correlation", "recovery", "margin", "loss"],
    "portfolio":  ["portfolio", "equity", "capital", "leverage", "position",
                   "asset", "allocation", "weight", "exposure"],
    "simulation": ["monte carlo", "simulation", "scenario", "probability",
                   "distribution", "percentile", "confidence"],
    "code":       ["python", "code", "function", "class", "import", "error",
                   "bug", "fix", "script"],
    "learning":   ["learn", "lesson", "study", "understand", "remember", "note"],
    "task":       ["task", "todo", "need to", "should", "must"],
}


class KnowledgeGraphViewer:
    """Generates an interactive HTML knowledge graph from fractal memory."""

    def __init__(self, workspace_path: str | Path):
        self.workspace = Path(workspace_path).expanduser()
        self.fractal_path = self.workspace / "memory" / "fractal_index.json"
        self.memory_path = self.workspace / "memory" / "MEMORY.md"
        self._nodes: list[dict[str, Any]] = []
        self._edges: list[dict[str, Any]] = []

    def load(self) -> "KnowledgeGraphViewer":
        """Load fractal nodes and MEMORY.md consolidated entries."""
        self._nodes = []
        self._edges = []
        self._load_fractal_nodes()
        self._load_memory_md()
        self._find_connections()
        return self

    def _load_fractal_nodes(self) -> None:
        if not self.fractal_path.exists():
            return
        try:
            with open(self.fractal_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Handle corrupt or unreadable file gracefully
            self._nodes = []
            return

        raw_nodes = data.get("nodes", [])
        for node in raw_nodes:
            label = self._extract_label(node)
            group = self._detect_group(node)
            self._nodes.append({
                "id":           node.get("id", ""),
                "label":        label[:30],
                "full_summary": node.get("summary", node.get("content", ""))[:200],
                "tags":         node.get("tags", []),
                "content_type": node.get("content_type", "conversation"),
                "group":        group,
                "size":         max(1, node.get("uses", 1)),
                "timestamp":    node.get("timestamp", "")[:16],
                "important":    node.get("important", False),
                "consolidated": node.get("consolidated", False),
                "source":       "fractal",
            })

    def _load_memory_md(self) -> None:
        """Parse consolidated lessons from MEMORY.md as permanent nodes."""
        if not self.memory_path.exists():
            return
        text = self.memory_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"^- \[(\d{4}-\d{2}-\d{2}[^\]]*)\]\s*\(([^)]*)\)\s*(.+)$",
            re.MULTILINE,
        )
        for i, m in enumerate(pattern.finditer(text)):
            ts, tags_str, summary = m.group(1), m.group(2), m.group(3).strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            node_id = f"mem_{i}"
            self._nodes.append({
                "id":           node_id,
                "label":        summary[:30],
                "full_summary": summary[:200],
                "tags":         tags,
                "content_type": "consolidated",
                "group":        "permanent",
                "size":         3,
                "timestamp":    ts,
                "important":    True,
                "consolidated": True,
                "source":       "memory",
            })

    def _find_connections(self) -> None:
        """Create edges between nodes that share keywords or tags."""
        all_kws: list[str] = []
        for group_keywords in _DOMAIN_KEYWORDS.values():
            all_kws.extend(group_keywords)

        keyword_sets: list[set[str]] = []
        for node in self._nodes:
            kws: set[str] = set(node.get("tags", []))
            text = (node.get("full_summary", "") + " " + node["label"]).lower()
            for word in all_kws:
                if word in text:
                    kws.add(word.strip())
            keyword_sets.append(kws)

        for i in range(len(self._nodes)):
            for j in range(i + 1, len(self._nodes)):
                shared = keyword_sets[i] & keyword_sets[j]
                if shared:
                    self._edges.append({
                        "from":     self._nodes[i]["id"],
                        "to":       self._nodes[j]["id"],
                        "label":    ", ".join(list(shared)[:2]),
                        "strength": len(shared),
                    })

    def get_stats(self) -> dict[str, Any]:
        """Return statistics dict."""
        types: dict[str, int] = {}
        for n in self._nodes:
            t = n.get("group", "default")
            types[t] = types.get(t, 0) + 1

        most_connected: list[dict] = []
        if self._edges:
            conn: dict[str, int] = {}
            for e in self._edges:
                conn[e["from"]] = conn.get(e["from"], 0) + 1
                conn[e["to"]] = conn.get(e["to"], 0) + 1
            top = sorted(conn.items(), key=lambda x: -x[1])[:5]
            id_map = {n["id"]: n for n in self._nodes}
            for nid, cnt in top:
                node = id_map.get(nid)
                if node:
                    most_connected.append({"label": node["label"], "connections": cnt})

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "groups": types,
            "most_connected": most_connected,
        }

    def query_nodes(self, keyword: str, limit: int = 10) -> list[dict]:
        """Search nodes by keyword in label/summary/tags."""
        kw = keyword.lower()
        results = []
        for n in self._nodes:
            text = (n.get("full_summary", "") + " " + n["label"] + " " + " ".join(n.get("tags", []))).lower()
            if kw in text:
                results.append({
                    "id": n["id"],
                    "label": n["label"],
                    "summary": n["full_summary"],
                    "group": n["group"],
                    "tags": n["tags"],
                    "timestamp": n["timestamp"],
                })
                if len(results) >= limit:
                    break
        return results

    def generate_html(self, output_name: str = "knowledge_graph.html") -> Path:
        """Generate an interactive HTML graph. Returns the output path."""
        vis_nodes = []
        for n in self._nodes:
            color = _GROUP_COLORS.get(n["group"], _GROUP_COLORS["default"])
            border = "#ffd700" if n.get("important") else color
            vis_nodes.append({
                "id":           n["id"],
                "label":        n["label"],
                "title":        f"{n['full_summary']}\n\nTags: {', '.join(n['tags']) or 'none'}\n"
                                f"Type: {n['content_type']}\n{n['timestamp']}",
                "group":        n["group"],
                "value":        n["size"],
                "color": {
                    "background": color,
                    "border":     border,
                    "highlight":  {"background": "#ffffff", "border": border},
                },
            })

        vis_edges = []
        for e in self._edges:
            vis_edges.append({
                "from":  e["from"],
                "to":    e["to"],
                "title": e["label"],
                "width": e["strength"],
            })

        legend_items = "".join(
            f'<div class="legend-item"><span class="dot" style="background:{c}"></span>{g}</div>'
            for g, c in _GROUP_COLORS.items()
            if any(n["group"] == g for n in self._nodes)
        )

        total_nodes = len(self._nodes)
        total_edges = len(self._edges)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        html = _HTML_TEMPLATE.format(
            nodes_json=json.dumps(vis_nodes, indent=2),
            edges_json=json.dumps(vis_edges, indent=2),
            legend_items=legend_items,
            total_nodes=total_nodes,
            total_edges=total_edges,
            generated_at=generated_at,
        )

        output_path = self.workspace / output_name
        output_path.write_text(html, encoding="utf-8")
        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_label(self, node: dict) -> str:
        tags = node.get("tags", [])
        if tags:
            return tags[0]
        summary = node.get("summary", node.get("content", ""))
        words = summary.split()[:5]
        return " ".join(words) or node.get("id", "node")

    def _detect_group(self, node: dict) -> str:
        tags = set(node.get("tags", []))
        text = (node.get("summary", "") + " " + node.get("content", "")).lower()

        for group, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in tags or kw in text for kw in keywords):
                return group

        if tags:
            t = next(iter(tags))
            return t if t in _GROUP_COLORS else "default"
        return "default"


class KnowledgeGraphTool(Tool):
    """Tool ABC wrapper for KnowledgeGraph visualization and querying."""

    @property
    def name(self) -> str:
        return "knowledge_graph"

    @property
    def description(self) -> str:
        return (
            "Visualize memory as an interactive knowledge graph, "
            "show graph statistics, or query nodes by keyword."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["stats", "generate", "query"],
                    "description": (
                        "stats: return node/edge counts and group breakdown. "
                        "generate: create interactive HTML graph file. "
                        "query: search nodes by keyword."
                    ),
                },
                "keyword": {
                    "type": "string",
                    "description": "Search keyword (for 'query' action).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results for query (default 10).",
                },
                "workspace": {
                    "type": "string",
                    "description": "Workspace path (default: ~/.jagabot/workspace).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "stats")
        workspace = kwargs.get("workspace", str(Path.home() / ".jagabot" / "workspace"))
        viewer = KnowledgeGraphViewer(workspace).load()

        if action == "stats":
            return json.dumps(viewer.get_stats())

        elif action == "generate":
            path = viewer.generate_html()
            stats = viewer.get_stats()
            return json.dumps({
                "generated": str(path),
                "nodes": stats["total_nodes"],
                "edges": stats["total_edges"],
            })

        elif action == "query":
            keyword = kwargs.get("keyword", "")
            if not keyword:
                return json.dumps({"error": "keyword required for query action"})
            limit = kwargs.get("limit", 10)
            results = viewer.query_nodes(keyword, limit=limit)
            return json.dumps({"keyword": keyword, "matches": len(results), "nodes": results})

        else:
            return json.dumps({"error": f"Unknown action: {action}. Use stats|generate|query."})


# ---------------------------------------------------------------------------
# HTML template (vis.js interactive graph)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Jagabot Knowledge Graph</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
  <link  href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #111; color: #eee; font-family: 'Segoe UI', sans-serif; }}
    #graph {{ width: 100vw; height: 100vh; }}
    #sidebar {{
      position: absolute; top: 0; right: 0; width: 320px; height: 100vh;
      background: rgba(20,20,20,0.92); padding: 20px;
      border-left: 1px solid #333; overflow-y: auto;
      display: flex; flex-direction: column; gap: 12px;
    }}
    #sidebar h2 {{ font-size: 14px; color: #ffd700; letter-spacing: 1px; text-transform: uppercase; }}
    #node-title {{ font-size: 16px; font-weight: bold; color: #fff; }}
    #node-summary {{ font-size: 13px; color: #aaa; line-height: 1.5; }}
    #node-meta {{ font-size: 11px; color: #666; }}
    .tag {{
      display: inline-block; background: #333; color: #ccc;
      border-radius: 3px; padding: 2px 6px; font-size: 10px; margin: 2px;
    }}
    .legend {{ margin-top: auto; padding-top: 16px; border-top: 1px solid #333; }}
    .legend h3 {{ font-size: 11px; color: #666; margin-bottom: 8px; text-transform: uppercase; }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 12px; margin: 3px 0; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    #stats {{ font-size: 11px; color: #555; }}
    #hint {{ font-size: 11px; color: #444; font-style: italic; }}
    .badge {{
      display: inline-block; padding: 2px 8px; border-radius: 12px;
      font-size: 10px; font-weight: bold; background: #333; color: #aaa;
    }}
    .badge.important {{ background: #ffd700; color: #111; }}
    .badge.permanent {{ background: #ff9900; color: #111; }}
  </style>
</head>
<body>

<div id="graph"></div>

<div id="sidebar">
  <h2>🧠 Jagabot Knowledge Graph</h2>
  <div id="stats">{total_nodes} nodes &nbsp;·&nbsp; {total_edges} edges &nbsp;·&nbsp; {generated_at}</div>
  <div id="hint">Click a node to inspect it</div>

  <div id="node-title" style="display:none"></div>
  <div id="node-tags"></div>
  <div id="node-summary"></div>
  <div id="node-meta"></div>

  <div class="legend">
    <h3>Legend</h3>
    {legend_items}
  </div>
</div>

<script>
  var nodesData = {nodes_json};
  var edgesData = {edges_json};

  var nodes = new vis.DataSet(nodesData);
  var edges = new vis.DataSet(edgesData);

  var container = document.getElementById('graph');
  var network = new vis.Network(container, {{ nodes: nodes, edges: edges }}, {{
    physics: {{
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {{ gravitationalConstant: -60, springLength: 100 }},
      stabilization: {{ iterations: 150 }}
    }},
    nodes: {{
      shape: 'dot',
      scaling: {{ min: 8, max: 28 }},
      font: {{ color: '#ddd', size: 11 }},
      borderWidth: 2,
    }},
    edges: {{
      smooth: {{ type: 'continuous' }},
      arrows: {{ to: {{ enabled: false }} }},
      color: {{ color: '#333', highlight: '#ff9900', opacity: 0.6 }},
      scaling: {{ min: 1, max: 5 }},
    }},
    interaction: {{
      hover: true,
      tooltipDelay: 200,
    }},
  }});

  network.on('click', function(params) {{
    if (params.nodes.length === 0) return;
    var node = nodes.get(params.nodes[0]);

    document.getElementById('node-title').style.display = 'block';
    document.getElementById('node-title').textContent = node.label;

    var tags = (node.tags || []).map(t => '<span class="tag">' + t + '</span>').join('');
    var badges = '';
    if (node.important) badges += '<span class="badge important">⭐ important</span> ';
    if (node.source === 'memory') badges += '<span class="badge permanent">💾 permanent</span> ';
    document.getElementById('node-tags').innerHTML = badges + tags;

    document.getElementById('node-summary').textContent = node.full_summary || 'No summary available.';
    document.getElementById('node-meta').textContent =
      node.timestamp + '  ·  ' + (node.content_type || 'conversation');

    document.getElementById('hint').style.display = 'none';
  }});
</script>
</body>
</html>
"""
