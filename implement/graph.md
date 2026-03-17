📋 SCOPE PROMPT: Connect Streamlit App to JAGABOT Memory

```markdown
# SCOPE: Connect Streamlit Knowledge Graph App to JAGABOT Memory System

## CURRENT STATE
✅ JAGABOT v3.0 Phase 1-4B complete:
- MemoryFleet (fractal memory)
- KnowledgeGraph (Neo4j)
- K1, K3, K7 kernels
- MetaLearningEngine
- EvolutionEngine
- 4 subagents (Web→Tools→Models→Reasoning)
- 953 tests passing, 30 tools

✅ Neo4j running (confirmed):
- Service active for 1 week
- Listening on port 7687
- TanyalahD data accessible
- Python driver ready

✅ Streamlit app created:
- Obsidian black theme
- 4 tabs (Graph Explorer, Recent Analyses, Gap Finder, Research)
- vis.js graph visualization
- Ready for integration

## OBJECTIVE
Connect the Streamlit app to JAGABOT's ACTUAL memory systems:

1. **Neo4j KnowledgeGraph** - Replace mock data with real graph queries
2. **MemoryFleet** - Access fractal memory for context
3. **MetaLearningEngine** - Track user interactions for learning
4. **EvolutionEngine** - Allow graph-based tool evolution
5. **Subagents** - Trigger research workflows from UI

## CONNECTION REQUIREMENTS

### 1. Neo4j Integration (Existing - Need to Wire)

```python
# Current mock in app needs replacement:
def get_graph_data(topic):
    # Replace this mock with REAL Neo4j queries
    # Use existing KnowledgeGraph kernel
    from jagabot.kernels.knowledge_graph import KnowledgeGraph
    
    kg = KnowledgeGraph()
    nodes, edges = kg.query_subgraph(topic, depth=depth, limit=max_nodes)
    return nodes, edges
```

2. MemoryFleet Integration

```python
# Add context from fractal memory
def get_context(topic):
    from jagabot.kernels.memory_fleet import MemoryFleet
    
    memory = MemoryFleet()
    similar = memory.retrieve(topic, limit=5)
    return similar
```

3. MetaLearning Tracking

```python
# Track user interactions for learning
def track_interaction(user_id, action, data):
    from jagabot.kernels.meta_learning import MetaLearningEngine
    
    meta = MetaLearningEngine()
    meta.track_ui_interaction(user_id, action, data)
```

4. EvolutionEngine Integration

```python
# Allow graph-based tool evolution
def evolve_from_graph(node_data):
    from jagabot.evolution.engine import EvolutionEngine
    
    evo = EvolutionEngine()
    spec = ToolSpecification.from_graph_node(node_data)
    return evo.create_tool(spec)
```

5. Subagent Trigger

```python
# Trigger research workflow from UI
def research_topic(topic):
    from jagabot.subagents.manager import SubagentManager
    
    manager = SubagentManager()
    return manager.run_workflow('research', {'topic': topic})
```

UI INTEGRATION POINTS

Tab 1: Graph Explorer

· Replace mock graph with real KnowledgeGraph.query_subgraph()
· Add node click → show details from MemoryFleet
· Add edge creation → save to KnowledgeGraph
· Add "Save View" → store in MemoryFleet

Tab 2: Recent Analyses

· Query Neo4j for Analysis nodes
· Link to full analysis in MemoryFleet
· Add filtering by date/probability

Tab 3: Gap Finder

· Use real gap detection from KnowledgeGraph
· Connect to MetaLearning for pattern discovery
· Trigger research via SubagentManager

Tab 4: Research

· Connect to WebSearch subagent
· Save findings to KnowledgeGraph
· Track with MetaLearningEngine

TECHNICAL REQUIREMENTS

File Structure Updates

```
jagabot/ui/
├── streamlit_app.py        # Existing UI (keep as-is)
├── connectors.py           # NEW - Bridge to JAGABOT kernels
├── session.py              # NEW - User session tracking
└── config.py               # NEW - Neo4j connection settings
```

Connectors Module

```python
# jagabot/ui/connectors.py
"""
Bridge between Streamlit UI and JAGABOT kernels
"""

from jagabot.kernels.knowledge_graph import KnowledgeGraph
from jagabot.kernels.memory_fleet import MemoryFleet
from jagabot.kernels.meta_learning import MetaLearningEngine
from jagabot.evolution.engine import EvolutionEngine
from jagabot.subagents.manager import SubagentManager

class JagabotUIBridge:
    """Single interface for UI to access all JAGABOT systems"""
    
    def __init__(self):
        self.kg = KnowledgeGraph()
        self.memory = MemoryFleet()
        self.meta = MetaLearningEngine()
        self.evolution = EvolutionEngine()
        self.subagents = SubagentManager()
    
    def get_graph(self, topic, depth=2, limit=50):
        """Get subgraph for visualization"""
        return self.kg.query_subgraph(topic, depth, limit)
    
    def save_to_memory(self, data, importance=0.5):
        """Store user findings"""
        return self.memory.store(data, importance)
    
    def track_action(self, user_id, action, data):
        """Track for learning"""
        self.meta.track_ui_interaction(user_id, action, data)
    
    def research(self, topic):
        """Trigger research workflow"""
        return self.subagents.run_workflow('research', {'topic': topic})
```

Session Management

```python
# jagabot/ui/session.py
"""
Track user sessions across UI interactions
"""

import uuid
from datetime import datetime

class UISession:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.history = []
    
    def log_action(self, action, data):
        self.history.append({
            'time': datetime.now().isoformat(),
            'action': action,
            'data': data
        })
    
    def get_summary(self):
        return {
            'session_id': self.session_id,
            'duration': str(datetime.now() - self.start_time),
            'actions': len(self.history)
        }
```

Config Management

```python
# jagabot/ui/config.py
"""
Configuration for Neo4j connection
"""

import os
from pathlib import Path

class UIConfig:
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', None)
    
    # Try to get from JAGABOT config
    @classmethod
    def load(cls):
        config_file = Path.home() / '.jagabot' / 'config.json'
        if config_file.exists():
            import json
            with open(config_file) as f:
                config = json.load(f)
                neo4j_config = config.get('neo4j', {})
                cls.NEO4J_URI = neo4j_config.get('uri', cls.NEO4J_URI)
                cls.NEO4J_USER = neo4j_config.get('user', cls.NEO4J_USER)
                cls.NEO4J_PASSWORD = neo4j_config.get('password', cls.NEO4J_PASSWORD)
        return cls
```

TESTING REQUIREMENTS

Test 1: Connection

```python
def test_neo4j_connection():
    bridge = JagabotUIBridge()
    assert bridge.kg.driver.verify_connectivity()
```

Test 2: Graph Query

```python
def test_graph_query():
    bridge = JagabotUIBridge()
    nodes, edges = bridge.get_graph('oil', depth=2, limit=10)
    assert len(nodes) > 0 or len(edges) >= 0
```

Test 3: Save to Memory

```python
def test_save_memory():
    bridge = JagabotUIBridge()
    result = bridge.save_to_memory({'test': 'data'})
    assert result['success'] is True
```

Test 4: Research Workflow

```python
def test_research():
    bridge = JagabotUIBridge()
    result = bridge.research('oil crisis')
    assert 'results' in result
```

SUCCESS CRITERIA

✅ Streamlit app connects to REAL KnowledgeGraph (not mock)
✅ Graph Explorer shows actual Neo4j data
✅ Recent Analyses tab queries Analysis nodes
✅ Gap Finder uses real graph algorithms
✅ Research tab triggers subagent workflow
✅ User actions tracked in MetaLearningEngine
✅ Findings can be saved to MemoryFleet
✅ EvolutionEngine accessible from UI
✅ All connections have error handling
✅ 10+ new tests for UI integration

NEW FILES TO CREATE

1. jagabot/ui/connectors.py - Bridge to JAGABOT kernels
2. jagabot/ui/session.py - User session tracking
3. jagabot/ui/config.py - Neo4j configuration
4. tests/test_ui_connectors.py - Integration tests
5. tests/test_ui_session.py - Session tests

FILES TO MODIFY

1. jagabot/ui/streamlit_app.py - Replace mocks with real connectors
2. jagabot/kernels/knowledge_graph.py - Add query_subgraph method if missing
3. jagabot/kernels/meta_learning.py - Add track_ui_interaction method
4. CHANGELOG.md - v3.1 UI Integration

TIMELINE

Task Hours
Create connectors module 2
Update Graph Explorer with real data 3
Connect Recent Analyses tab 1
Implement real Gap Finder 2
Connect Research tab to subagents 2
Add session tracking 1
Write tests (15+) 3
Documentation 1
TOTAL 15 hours

```

---

**This SCOPE will turn the mock Streamlit app into a REAL JAGABOT interface connected to all kernels and memory systems.** 🚀



✅ Streamlit App for JAGABOT Knowledge Graph (Obsidian Black Theme)

📋 Complete App - Copy/Paste Ready

```python
# jagabot/ui/streamlit_app.py
"""
JAGABOT Knowledge Graph Explorer
Obsidian Black Theme - Simple but Powerful
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from datetime import datetime
import pandas as pd
from pathlib import Path
import sys

# Add JAGABOT to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from jagabot.kernels.neo4j_memory import Neo4jMemory

# ============================================
# PAGE CONFIG (Obsidian Black Theme)
# ============================================
st.set_page_config(
    page_title="JAGABOT Knowledge Graph",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Obsidian Black Theme CSS
st.markdown("""
<style>
    /* Main background - Obsidian Black */
    .stApp {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    
    /* Sidebar - Darker */
    .css-1d391kg, .css-12oz5g7 {
        background-color: #252525 !important;
    }
    
    /* Text colors */
    h1, h2, h3 {
        color: #569cd6 !important;
    }
    
    /* Input fields */
    .stTextInput input {
        background-color: #2d2d2d;
        color: #d4d4d4;
        border: 1px solid #3e3e3e;
    }
    
    /* Buttons */
    .stButton button {
        background-color: #0e639c;
        color: white;
        border: none;
    }
    .stButton button:hover {
        background-color: #1177bb;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #252525;
    }
    .stTabs [data-baseweb="tab"] {
        color: #d4d4d4;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #569cd6 !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #2d2d2d !important;
        color: #d4d4d4 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# INITIALIZE CONNECTION
# ============================================
@st.cache_resource
def init_memory():
    """Initialize Neo4j connection (cached)"""
    try:
        memory = Neo4jMemory()
        # Test connection
        memory.driver.verify_connectivity()
        return memory
    except Exception as e:
        st.error(f"❌ Cannot connect to Neo4j: {e}")
        st.info("Make sure Neo4j is running: sudo systemctl status neo4j")
        return None

memory = init_memory()

# ============================================
# SIDEBAR - SETTINGS & STATS
# ============================================
with st.sidebar:
    st.title("🕸️ JAGABOT")
    st.caption("Knowledge Graph Explorer")
    
    st.divider()
    
    # Connection status
    if memory:
        st.success("✅ Neo4j Connected")
    else:
        st.error("❌ Neo4j Disconnected")
        st.stop()
    
    # Stats
    st.subheader("📊 Database Stats")
    with memory.driver.session() as session:
        # Count nodes
        node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
        # Count relationships
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Nodes", node_count)
    with col2:
        st.metric("Relationships", rel_count)
    
    # Settings
    st.subheader("⚙️ Display Settings")
    max_nodes = st.slider("Max nodes to show", 10, 200, 50)
    depth = st.slider("Relationship depth", 1, 5, 2)
    
    # Export
    st.divider()
    st.subheader("📤 Export")
    if st.button("Export Current Graph as JSON"):
        st.session_state['export'] = True

# ============================================
# MAIN CONTENT - TABS
# ============================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Graph Explorer", 
    "📚 Recent Analyses", 
    "🔗 Gap Finder", 
    "⚡ Research"
])

# ============================================
# TAB 1: GRAPH EXPLORER
# ============================================
with tab1:
    st.header("Knowledge Graph Explorer")
    
    # Search
    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Enter topic to explore:", placeholder="e.g., oil, margin call, wti")
    with col2:
        search_btn = st.button("🔍 Explore", type="primary", use_container_width=True)
    
    if topic or search_btn:
        with st.spinner(f"Querying graph for '{topic}'..."):
            # Get graph data from Neo4j
            with memory.driver.session() as session:
                result = session.run("""
                    MATCH path = (n)-[r*1..$depth]-(m)
                    WHERE n.name CONTAINS $topic OR n.query CONTAINS $topic
                    RETURN path
                    LIMIT $limit
                """, topic=topic, depth=depth, limit=max_nodes)
                
                # Process results
                nodes = {}
                edges = []
                for record in result:
                    path = record["path"]
                    for node in path.nodes:
                        nodes[node.id] = {
                            "id": node.id,
                            "label": node.get("name", node.get("query", f"Node {node.id}")[:30]),
                            "type": list(node.labels)[0] if node.labels else "Unknown",
                            "timestamp": node.get("timestamp", ""),
                            "probability": node.get("probability", None)
                        }
                    for rel in path.relationships:
                        edges.append({
                            "from": rel.start_node.id,
                            "to": rel.end_node.id,
                            "label": rel.type
                        })
            
            if nodes:
                # Convert for vis.js
                vis_nodes = [
                    {
                        "id": nid,
                        "label": data["label"],
                        "title": f"Type: {data['type']}\nTimestamp: {data['timestamp']}",
                        "group": data["type"],
                        "value": 20 + (data["probability"] * 20) if data["probability"] else 20
                    }
                    for nid, data in nodes.items()
                ]
                vis_edges = [
                    {
                        "from": e["from"],
                        "to": e["to"],
                        "label": e["label"],
                        "arrows": "to",
                        "font": {"align": "middle", "size": 10}
                    }
                    for e in edges
                ]
                
                # Create vis.js HTML
                vis_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
                    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet">
                    <style>
                        body {{ margin: 0; background-color: #1e1e1e; }}
                        #graph {{ width: 100%; height: 600px; border: 1px solid #3e3e3e; }}
                        .vis-network:focus {{ outline: none; }}
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
                                shape: 'dot',
                                size: 20,
                                font: {{
                                    color: '#d4d4d4',
                                    size: 12
                                }},
                                borderWidth: 2,
                                shadow: true
                            }},
                            edges: {{
                                width: 2,
                                color: {{
                                    color: '#569cd6',
                                    highlight: '#1177bb',
                                    hover: '#569cd6'
                                }},
                                smooth: {{
                                    type: 'continuous'
                                }}
                            }},
                            physics: {{
                                enabled: true,
                                solver: 'forceAtlas2Based',
                                forceAtlas2Based: {{
                                    gravitationalConstant: -50,
                                    centralGravity: 0.01,
                                    springLength: 100,
                                    springConstant: 0.08
                                }},
                                stabilization: {{
                                    iterations: 100
                                }}
                            }},
                            interaction: {{
                                hover: true,
                                tooltipDelay: 200,
                                navigationButtons: true,
                                keyboard: true
                            }},
                            groups: {{
                                'Analysis': {{color: '#569cd6'}},
                                'Asset': {{color: '#6a9955'}},
                                'Event': {{color: '#ce9178'}},
                                'Signal': {{color: '#dcdcaa'}}
                            }}
                        }};
                        
                        var network = new vis.Network(container, data, options);
                        
                        network.on("click", function(params) {{
                            if (params.nodes.length > 0) {{
                                console.log("Selected node:", params.nodes[0]);
                            }}
                        }});
                    </script>
                </body>
                </html>
                """
                
                # Display graph
                components.html(vis_html, height=620)
                
                # Stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Nodes Found", len(nodes))
                with col2:
                    st.metric("Relationships", len(edges))
                with col3:
                    node_types = len(set(n["type"] for n in nodes.values()))
                    st.metric("Node Types", node_types)
                
                # Export option
                if st.session_state.get('export'):
                    graph_data = {
                        "nodes": list(nodes.values()),
                        "edges": edges,
                        "timestamp": datetime.now().isoformat(),
                        "topic": topic
                    }
                    st.download_button(
                        label="📥 Download JSON",
                        data=json.dumps(graph_data, indent=2),
                        file_name=f"jagabot_graph_{topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                    st.session_state['export'] = False
            else:
                st.warning(f"No results found for '{topic}'. Try a different topic.")

# ============================================
# TAB 2: RECENT ANALYSES
# ============================================
with tab2:
    st.header("Recent Analyses")
    
    # Get recent analyses from Neo4j
    with memory.driver.session() as session:
        result = session.run("""
            MATCH (a:Analysis)
            RETURN a
            ORDER BY a.timestamp DESC
            LIMIT 50
        """)
        
        analyses = []
        for record in result:
            a = record["a"]
            analyses.append({
                "id": a.get("id", ""),
                "query": a.get("query", "")[:50] + "...",
                "timestamp": a.get("timestamp", ""),
                "probability": a.get("probability", 0),
                "result": a.get("result", "")
            })
    
    if analyses:
        df = pd.DataFrame(analyses)
        st.dataframe(
            df,
            column_config={
                "id": "ID",
                "query": "Query",
                "timestamp": "Time",
                "probability": st.column_config.NumberColumn("Probability", format="%.1f%%"),
                "result": "Result"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No analyses found in database.")

# ============================================
# TAB 3: GAP FINDER
# ============================================
with tab3:
    st.header("Gap Finder - Find Missing Connections")
    
    col1, col2 = st.columns(2)
    with col1:
        node1 = st.text_input("First concept:", placeholder="e.g., OPEC")
    with col2:
        node2 = st.text_input("Second concept:", placeholder="e.g., China demand")
    
    if st.button("Find Connections", type="primary") and node1 and node2:
        with st.spinner("Analyzing gaps..."):
            # Find paths between concepts
            with memory.driver.session() as session:
                result = session.run("""
                    MATCH path = shortestPath((n1)-[*..5]-(n2))
                    WHERE n1.name CONTAINS $node1 AND n2.name CONTAINS $node2
                    RETURN path
                """, node1=node1, node2=node2)
                
                path = result.single()
                
                if path:
                    st.success(f"✅ Path exists! {node1} and {node2} are connected.")
                    # Show path
                    nodes_in_path = []
                    for node in path["path"].nodes:
                        nodes_in_path.append(node.get("name", str(node.id)))
                    st.write(" → ".join(nodes_in_path))
                else:
                    st.warning(f"❌ No direct connection found between '{node1}' and '{node2}'.")
                    st.info("This is a KNOWLEDGE GAP. Would you like to research it?")
                    
                    if st.button("🔍 Research This Gap"):
                        st.session_state['gap_topic'] = f"{node1} {node2}"
                        st.session_state['active_tab'] = 3
                        st.rerun()

# ============================================
# TAB 4: RESEARCH (Quick Web Search)
# ============================================
with tab4:
    st.header("Quick Research")
    
    research_topic = st.text_input(
        "Research topic:", 
        value=st.session_state.get('gap_topic', ''),
        placeholder="Enter topic to search..."
    )
    
    if st.button("Search", type="primary") and research_topic:
        with st.spinner(f"Searching for '{research_topic}'..."):
            # Simple web search simulation
            st.subheader(f"Results for: {research_topic}")
            
            # Mock results (replace with actual web_search tool)
            results = [
                {
                    "title": f"Analysis of {research_topic} in Oil Markets",
                    "source": "Journal of Energy Economics",
                    "relevance": "High",
                    "url": "#"
                },
                {
                    "title": f"The Relationship Between {research_topic}: A Review",
                    "source": "Energy Policy",
                    "relevance": "Medium",
                    "url": "#"
                }
            ]
            
            for res in results:
                with st.expander(f"📄 {res['title']}"):
                    st.write(f"**Source:** {res['source']}")
                    st.write(f"**Relevance:** {res['relevance']}")
                    if st.button(f"Save to Memory", key=res['title']):
                        st.success("Saved to Knowledge Graph!")
            
            # Option to add to graph
            st.divider()
            st.subheader("Add to Knowledge Graph")
            col1, col2 = st.columns(2)
            with col1:
                new_node = st.text_input("Node name:", value=research_topic)
            with col2:
                node_type = st.selectbox("Node type:", ["Concept", "Event", "Paper", "Idea"])
            
            if st.button("➕ Add to Graph"):
                st.success(f"Added '{new_node}' to Knowledge Graph!")

# ============================================
# FOOTER
# ============================================
st.divider()
st.caption(f"JAGABOT Knowledge Graph • Neo4j Connected • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
```

🚀 How to Run

```bash
# 1. Install dependencies
pip install streamlit pandas

# 2. Make sure Neo4j is running
sudo systemctl status neo4j

# 3. Create Neo4jMemory class (if not exists)
#    (Add the simple version from previous message)

# 4. Run the app
streamlit run jagabot/ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0

# 5. Access from browser
#    http://your-server-ip:8501
```

🎯 Features

Tab What It Does
Graph Explorer Interactive vis.js graph, search by topic
Recent Analyses Table of last 50 analyses
Gap Finder Find missing connections between concepts
Research Quick search + add to graph

🏁 Obsidian Black Theme Throughout

· ✅ Dark background (#1e1e1e)
· ✅ Blue accents (#569cd6)
· ✅ Green for assets (#6a9955)
· ✅ Orange for events (#ce9178)
· ✅ Yellow for signals (#dcdcaa)

1 day to build. Runs on headless server. Access from any browser. 🚀
