📋 SCOPE PROMPT: JAGABOT v3.6 - Chat Tab in Streamlit UI

```markdown
# SCOPE: JAGABOT v3.6 - Add Chat Tab to Streamlit UI

## CURRENT STATE
✅ v3.5 complete:
- 1216 tests passing
- 5 Streamlit tabs (Graph, Recent, Gaps, Research, Lab)
- Auto-scaling worker pools (2-32 workers)
- Neo4j KnowledgeGraph connected

⏳ TARGET: Add 6th tab "💬 Chat" for interactive conversation

## OBJECTIVE
Add a chat interface to the existing Streamlit app that allows users to:

1. CHAT with JAGABOT naturally (like ChatGPT)
2. ASK financial questions (portfolio, risk, etc.)
3. SEE results as dashboards inline
4. VIEW tool execution progress
5. ACCESS conversation history
6. FOLLOW-UP with new questions

## NEW COMPONENTS

### 1. ChatTab Class
```python
# jagabot/ui/chat.py

import streamlit as st
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional

from jagabot.core.agent import JAGABOT
from jagabot.lab.parallel import ParallelLab
from jagabot.ui.lab.code_generator import CodePreview

class ChatTab:
    """
    Chat interface for JAGABOT - 6th tab in Streamlit
    """
    
    def __init__(self):
        self.agent = JAGABOT()
        self.lab = ParallelLab(auto_scale=True)
        
        # Initialize session state
        if 'chat_messages' not in st.session_state:
            st.session_state.chat_messages = []
            self._add_system_message("👋 Hi! Saya JAGABOT, Financial Guardian. Ada apa yang saya boleh bantu?")
        
        if 'chat_context' not in st.session_state:
            st.session_state.chat_context = {}
    
    def render(self):
        """Main render method for chat tab"""
        st.header("💬 Chat dengan JAGABOT")
        
        # Display chat messages
        self._display_chat_history()
        
        # Chat input
        self._chat_input()
        
        # Sidebar with chat info
        with st.sidebar:
            st.subheader("💬 Chat Info")
            st.metric("Messages", len(st.session_state.chat_messages))
            
            if st.button("🧹 Clear Chat"):
                st.session_state.chat_messages = []
                self._add_system_message("👋 Chat cleared. Ada apa yang saya boleh bantu?")
                st.rerun()
    
    def _display_chat_history(self):
        """Display all messages with proper formatting"""
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg['role']):
                # Message content
                st.markdown(msg['content'])
                
                # Show dashboard if present
                if 'dashboard' in msg:
                    st.markdown("---")
                    st.markdown(msg['dashboard'])
                
                # Show tool executions if present
                if 'tools' in msg:
                    with st.expander("🔧 Tool Executions", expanded=False):
                        for tool in msg['tools']:
                            status = "✅" if tool['success'] else "❌"
                            st.text(f"{status} {tool['name']}: {tool['duration']:.2f}s")
                
                # Timestamp
                st.caption(f"🕒 {msg['time'].strftime('%H:%M:%S')}")
    
    def _chat_input(self):
        """Handle user input and response"""
        prompt = st.chat_input("Tanya JAGABOT apa-ada...")
        
        if prompt:
            # Add user message
            self._add_user_message(prompt)
            
            # Get response
            with st.chat_message("assistant"):
                with st.spinner("JAGABOT sedang berfikir..."):
                    response = self._process_query(prompt)
                    
                    # Display response
                    st.markdown(response['message'])
                    
                    if 'dashboard' in response:
                        st.markdown("---")
                        st.markdown(response['dashboard'])
                    
                    if 'tools' in response:
                        with st.expander("🔧 Tool Executions", expanded=False):
                            for tool in response['tools']:
                                status = "✅" if tool['success'] else "❌"
                                st.text(f"{status} {tool['name']}: {tool['duration']:.2f}s")
                    
                    # Add to history
                    self._add_assistant_message(
                        response['message'],
                        response.get('dashboard'),
                        response.get('tools')
                    )
    
    def _process_query(self, query: str) -> Dict:
        """
        Process user query and return response
        """
        start_time = time.time()
        
        # Step 1: Classify query type
        query_type = self._classify_query(query)
        
        # Step 2: Check memory for context
        context = self._get_context(query)
        
        # Step 3: Execute appropriate workflow
        if query_type == 'portfolio':
            result = self._analyze_portfolio(query, context)
        elif query_type == 'risk':
            result = self._analyze_risk(query, context)
        elif query_type == 'fund_manager':
            result = self._check_fund_manager(query, context)
        elif query_type == 'general':
            result = self._general_chat(query, context)
        else:
            result = self._default_response(query)
        
        result['execution_time'] = time.time() - start_time
        return result
    
    def _classify_query(self, query: str) -> str:
        """Determine query type using keywords"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['portfolio', 'posisi', 'modal', 'equity']):
            return 'portfolio'
        elif any(word in query_lower for word in ['risk', 'risiko', 'var', 'cvar', 'stress']):
            return 'risk'
        elif any(word in query_lower for word in ['fund manager', 'advisor', 'broker']):
            return 'fund_manager'
        elif any(word in query_lower for word in ['hello', 'hi', 'thank', 'help']):
            return 'general'
        else:
            return 'unknown'
    
    def _analyze_portfolio(self, query: str, context: dict) -> dict:
        """Run portfolio analysis with parallel tools"""
        
        # Extract parameters from query
        params = self._extract_params(query)
        
        # Prepare parallel tasks
        tasks = [
            {'tool': 'portfolio_analyzer', 'params': params, 'priority': 10},
            {'tool': 'monte_carlo', 'params': params, 'priority': 9},
            {'tool': 'var', 'params': params, 'priority': 8},
            {'tool': 'stress_test', 'params': params, 'priority': 7}
        ]
        
        # Execute in parallel
        batch_id = asyncio.run(self.lab.submit_tasks(tasks))
        results = asyncio.run(self.lab.get_results(batch_id))
        
        # Generate dashboard
        dashboard = self._generate_dashboard(results)
        
        # Track tool executions
        tools = []
        for r in results['results']:
            tools.append({
                'name': r['task']['tool'],
                'success': r['success'],
                'duration': r.get('execution_time', 0)
            })
        
        return {
            'message': "✅ Analisis portfolio selesai. Berikut dashboard ringkasan:",
            'dashboard': dashboard,
            'tools': tools
        }
    
    def _add_system_message(self, content: str):
        """Add system message to history"""
        st.session_state.chat_messages.append({
            'role': 'assistant',
            'content': content,
            'time': datetime.now()
        })
    
    def _add_user_message(self, content: str):
        """Add user message to history"""
        st.session_state.chat_messages.append({
            'role': 'user',
            'content': content,
            'time': datetime.now()
        })
    
    def _add_assistant_message(self, content: str, dashboard: Optional[str] = None, tools: Optional[List] = None):
        """Add assistant message to history"""
        msg = {
            'role': 'assistant',
            'content': content,
            'time': datetime.now()
        }
        if dashboard:
            msg['dashboard'] = dashboard
        if tools:
            msg['tools'] = tools
        
        st.session_state.chat_messages.append(msg)
```

2. Update Streamlit App

```python
# jagabot/ui/streamlit_app.py (updated)

import streamlit as st
from jagabot.ui.chat import ChatTab

# ... existing tabs ...

# Add Chat tab
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Graph Explorer",
    "📚 Recent Analyses",
    "🔗 Gap Finder",
    "⚡ Research",
    "📓 Lab",
    "💬 Chat"  # NEW
])

with tab6:
    chat = ChatTab()
    chat.render()
```

3. Example Chat Flows

```yaml
FLOW 1: Portfolio Query
🧑: "Check portfolio minyak saya dengan modal 1.5M, leveraj 2.5, VIX 52"
🤖: "✅ Analisis portfolio selesai. Berikut dashboard:"
    [Dashboard muncul dengan equity, margin call, probability]

FLOW 2: Follow-up
🧑: "Kalau VIX naik ke 60, apa jadi?"
🤖: "Saya akan run stress test dengan VIX 60..."
    [Updated dashboard dengan scenario baru]

FLOW 3: Fund Manager Check
🧑: "Fund manager saya kata risiko sederhana. Betul ke?"
🤖: "JAGABOT analysis tunjuk VIX 52 = EXTREME PANIK"
    [Red flags + report card]
```

4. Tests

```python
# tests/test_chat_tab.py

import pytest
from jagabot.ui.chat import ChatTab

def test_chat_initialization():
    chat = ChatTab()
    assert len(chat.session_state.chat_messages) > 0
    assert "Hi!" in chat.session_state.chat_messages[0]['content']

def test_query_classification():
    chat = ChatTab()
    assert chat._classify_query("Check portfolio saya") == 'portfolio'
    assert chat._classify_query("Apa risiko?"') == 'risk'
    assert chat._classify_query("Fund manager kata") == 'fund_manager'
    assert chat._classify_query("Hello") == 'general'

def test_analyze_portfolio():
    chat = ChatTab()
    result = chat._analyze_portfolio("modal 1.5M, vix 52", {})
    assert 'dashboard' in result
    assert 'tools' in result
    assert len(result['tools']) > 0
```

NEW FILES TO CREATE

1. jagabot/ui/chat.py - ChatTab class
2. tests/test_chat_tab.py - 15+ tests

FILES TO MODIFY

1. jagabot/ui/streamlit_app.py - Add 6th tab
2. CHANGELOG.md - v3.6 entry

SUCCESS CRITERIA

✅ 6th tab "💬 Chat" appears in Streamlit UI
✅ Chat history works (messages persist)
✅ User can ask portfolio questions
✅ Dashboard appears inline in chat
✅ Tool executions visible
✅ Follow-up questions work
✅ Context preserved across messages
✅ Clear chat button works
✅ 15+ new tests passing
✅ Total tests: 1231+

TIMELINE

Task Hours
ChatTab class 4
Message history 2
Query classification 2
Portfolio analysis integration 3
Dashboard rendering 2
Tool execution display 2
Tests (15+) 3
TOTAL 18 hours

```

---

**v3.6 will give JAGABOT a ChatGPT-like interface in the same Streamlit app!** 🚀
