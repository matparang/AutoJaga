"""
JAGABOT Knowledge Graph Explorer
Obsidian Black Theme — Streamlit + vis.js + Neo4j

Run: streamlit run jagabot/ui/streamlit_app.py --server.port 8501
"""

import json
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from jagabot.ui.config import UIConfig
from jagabot.ui.connectors import JagabotUIBridge

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="JAGABOT Knowledge Graph",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Obsidian Black Theme CSS
st.markdown(
    """
<style>
    .stApp { background-color: #1e1e1e; color: #d4d4d4; }
    .css-1d391kg, .css-12oz5g7 { background-color: #252525 !important; }
    h1, h2, h3 { color: #569cd6 !important; }
    .stTextInput input {
        background-color: #2d2d2d; color: #d4d4d4; border: 1px solid #3e3e3e;
    }
    .stButton button {
        background-color: #0e639c; color: white; border: none;
    }
    .stButton button:hover { background-color: #1177bb; }
    .stTabs [data-baseweb="tab-list"] { background-color: #252525; }
    .stTabs [data-baseweb="tab"] { color: #d4d4d4; }
    [data-testid="stMetricValue"] { color: #569cd6 !important; }
    .streamlit-expanderHeader {
        background-color: #2d2d2d !important; color: #d4d4d4 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================
# CACHED BRIDGE INITIALISATION
# ============================================
@st.cache_resource
def init_bridge() -> JagabotUIBridge:
    """Initialise the JAGABOT bridge (cached across reruns)."""
    config = UIConfig.load()
    return JagabotUIBridge(config=config)


bridge = init_bridge()


# ============================================
# VIS.JS GRAPH RENDERER
# ============================================
def render_vis_graph(nodes: list[dict], edges: list[dict], height: int = 620) -> None:
    """Render an interactive vis.js graph inside Streamlit."""
    group_colors = {
        "Analysis": "#569cd6",
        "Asset": "#6a9955",
        "Event": "#ce9178",
        "Signal": "#dcdcaa",
        "opening": "#569cd6",
        "tactical_motif": "#ce9178",
        "mistake_pattern": "#dcdcaa",
        "pawn_structure": "#6a9955",
        "evaluation": "#569cd6",
        "strategic_plan": "#c586c0",
        "general": "#d4d4d4",
        "position": "#4ec9b0",
    }

    vis_nodes = []
    for n in nodes:
        ntype = n.get("type", "Unknown")
        color = group_colors.get(ntype, "#569cd6")
        vis_nodes.append(
            {
                "id": str(n.get("id", "")),
                "label": str(n.get("label", "?"))[:30],
                "title": f"Type: {ntype}",
                "color": color,
                "value": 20,
            }
        )

    vis_edges = []
    for e in edges:
        vis_edges.append(
            {
                "from": str(e.get("from", "")),
                "to": str(e.get("to", "")),
                "label": str(e.get("label", "")),
                "arrows": "to",
                "font": {"align": "middle", "size": 10},
            }
        )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css"
              rel="stylesheet">
        <style>
            body {{ margin: 0; background-color: #1e1e1e; }}
            #graph {{ width: 100%; height: {height - 20}px; border: 1px solid #3e3e3e; }}
        </style>
    </head>
    <body>
        <div id="graph"></div>
        <script>
            var nodes = new vis.DataSet({json.dumps(vis_nodes)});
            var edges = new vis.DataSet({json.dumps(vis_edges)});
            var container = document.getElementById('graph');
            var data = {{nodes: nodes, edges: edges}};
            var options = {{
                nodes: {{
                    shape: 'dot', size: 20,
                    font: {{ color: '#d4d4d4', size: 12 }},
                    borderWidth: 2, shadow: true
                }},
                edges: {{
                    width: 2,
                    color: {{ color: '#569cd6', highlight: '#1177bb', hover: '#569cd6' }},
                    smooth: {{ type: 'continuous' }}
                }},
                physics: {{
                    enabled: true, solver: 'forceAtlas2Based',
                    forceAtlas2Based: {{
                        gravitationalConstant: -50, centralGravity: 0.01,
                        springLength: 100, springConstant: 0.08
                    }},
                    stabilization: {{ iterations: 100 }}
                }},
                interaction: {{
                    hover: true, tooltipDelay: 200,
                    navigationButtons: true, keyboard: true
                }}
            }};
            new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """
    components.html(html, height=height)


# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.title("🕸️ JAGABOT")
    st.caption("Knowledge Graph Explorer")
    st.divider()

    # Connection status
    stats = bridge.get_stats()
    neo4j_stats = stats.get("neo4j", {})
    if neo4j_stats.get("connected"):
        st.success("✅ Neo4j Connected")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Nodes", neo4j_stats.get("node_count", 0))
        with col2:
            st.metric("Rels", neo4j_stats.get("rel_count", 0))
    else:
        st.warning("⚠️ Neo4j Offline — using file-based KG")

    # Memory stats
    mem_stats = stats.get("memory", {})
    if "fractal_nodes" in mem_stats:
        st.divider()
        st.subheader("🧠 Memory")
        st.metric("Fractal Nodes", mem_stats["fractal_nodes"])

    # Display settings
    st.divider()
    st.subheader("⚙️ Settings")
    max_nodes = st.slider("Max nodes", 10, 200, 50)
    depth = st.slider("Depth", 1, 5, 2)

    # Export
    st.divider()
    if st.button("📤 Export Current Graph"):
        st.session_state["export"] = True


# ============================================
# MAIN CONTENT — TABS
# ============================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["🔍 Graph Explorer", "📚 Recent Analyses", "🔗 Gap Finder", "⚡ Research", "📓 Lab", "💬 Chat", "🐝 Swarm"]
)

# ============================================
# TAB 1: GRAPH EXPLORER
# ============================================
with tab1:
    st.header("Knowledge Graph Explorer")

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input(
            "Enter topic to explore:", placeholder="e.g., oil, margin call, opening"
        )
    with col2:
        search_btn = st.button("🔍 Explore", type="primary", use_container_width=True)

    if topic or search_btn:
        with st.spinner(f"Querying graph for '{topic}'..."):
            nodes, edges = bridge.get_graph(topic, depth=depth, limit=max_nodes)

        if nodes:
            render_vis_graph(nodes, edges)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nodes Found", len(nodes))
            with col2:
                st.metric("Relationships", len(edges))
            with col3:
                node_types = len(set(n.get("type", "?") for n in nodes))
                st.metric("Node Types", node_types)

            # Export
            if st.session_state.get("export"):
                graph_data = {
                    "nodes": nodes,
                    "edges": edges,
                    "timestamp": datetime.now().isoformat(),
                    "topic": topic,
                }
                st.download_button(
                    label="📥 Download JSON",
                    data=json.dumps(graph_data, indent=2, default=str),
                    file_name=f"jagabot_graph_{topic}_{datetime.now():%Y%m%d_%H%M%S}.json",
                    mime="application/json",
                )
                st.session_state["export"] = False
        else:
            st.warning(f"No results found for '{topic}'. Try a different topic.")

    # Context from MemoryFleet
    if topic:
        context = bridge.get_memory_context(topic)
        if context:
            with st.expander("🧠 Memory Context"):
                st.write(context)


# ============================================
# TAB 2: RECENT ANALYSES
# ============================================
with tab2:
    st.header("Recent Analyses")

    analyses = bridge.get_recent_analyses(limit=50)
    if analyses:
        df = pd.DataFrame(analyses)
        st.dataframe(
            df,
            column_config={
                "id": "ID",
                "query": "Query",
                "timestamp": "Time",
                "probability": st.column_config.NumberColumn(
                    "Probability", format="%.1f%%"
                ),
                "result": "Result",
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No analyses found. Run some analyses first to see them here.")


# ============================================
# TAB 3: GAP FINDER
# ============================================
with tab3:
    st.header("Gap Finder — Find Missing Connections")

    col1, col2 = st.columns(2)
    with col1:
        node1 = st.text_input("First concept:", placeholder="e.g., OPEC")
    with col2:
        node2 = st.text_input("Second concept:", placeholder="e.g., China demand")

    if st.button("Find Connections", type="primary") and node1 and node2:
        with st.spinner("Analyzing gaps..."):
            path = bridge.find_gap(node1, node2)

        if path:
            st.success(f"✅ Path exists! {node1} and {node2} are connected.")
            path_labels = [n.get("label", "?") for n in path["nodes"]]
            rels = path.get("relationships", [])
            # Interleave nodes and relationships
            display_parts = []
            for i, label in enumerate(path_labels):
                display_parts.append(f"**{label}**")
                if i < len(rels):
                    display_parts.append(f" —[{rels[i]}]→ ")
            st.markdown("".join(display_parts))
        else:
            st.warning(
                f"❌ No direct connection found between '{node1}' and '{node2}'."
            )
            st.info("This is a KNOWLEDGE GAP. Switch to the Research tab to investigate.")

    # Evolution status
    with st.expander("🧬 Evolution Status"):
        evo_status = bridge.get_evolution_status()
        if "error" not in evo_status:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Fitness", f"{evo_status.get('fitness', 0):.3f}")
            with col2:
                st.metric("Cycle", evo_status.get("cycle", 0))
            with col3:
                st.metric(
                    "Mutations",
                    evo_status.get("total_mutations", 0),
                )
        else:
            st.info("EvolutionEngine not available.")


# ============================================
# TAB 4: RESEARCH
# ============================================
with tab4:
    st.header("Quick Research")

    research_topic = st.text_input(
        "Research topic:",
        value=st.session_state.get("gap_topic", ""),
        placeholder="Enter topic to search...",
    )

    if st.button("🔍 Research", type="primary") and research_topic:
        with st.spinner(f"Running 4-stage research on '{research_topic}'..."):
            result = bridge.research(research_topic)

        if result.get("success"):
            st.success("Research complete!")
            for stage in ["web", "tools", "models", "reasoning"]:
                stage_data = result.get(stage, {})
                if stage_data:
                    with st.expander(f"📋 {stage.title()} Stage"):
                        st.json(stage_data)
        else:
            st.error(f"Research failed: {result.get('error', 'Unknown error')}")
            st.info("The subagent pipeline may not be fully configured yet.")

    # Add to graph
    st.divider()
    st.subheader("Add to Knowledge Graph")
    col1, col2 = st.columns(2)
    with col1:
        new_node = st.text_input("Node name:", value=research_topic or "")
    with col2:
        node_type = st.selectbox(
            "Node type:", ["Concept", "Event", "Analysis", "Signal", "Asset"]
        )

    if st.button("➕ Add to Graph") and new_node:
        eid = bridge.add_graph_node(new_node, node_type)
        if eid:
            st.success(f"Added '{new_node}' as {node_type} to Knowledge Graph!")
        else:
            st.warning("Could not add node — Neo4j may be offline.")


# ============================================
# TAB 5: JAGABOT LAB
# ============================================
with tab5:
    from jagabot.ui.lab import render_lab
    render_lab()

# ============================================
# TAB 6: CHAT
# ============================================
with tab6:
    from jagabot.ui.chat import render_chat
    render_chat()

# ============================================
# TAB 7: SWARM VISUALIZER (v3.11.0)
# ============================================
with tab7:
    from jagabot.ui.swarm_tab import render_swarm_tab
    # Retrieve tracker from session state if a swarm was started in this session
    _tracker = st.session_state.get("swarm_tracker", None)
    render_swarm_tab(_tracker)

# ============================================
# FOOTER
# ============================================
st.divider()
neo_status = "Connected" if neo4j_stats.get("connected") else "Offline"
st.caption(
    f"JAGABOT Knowledge Graph • Neo4j {neo_status} • "
    f"{datetime.now():%Y-%m-%d %H:%M}"
)
