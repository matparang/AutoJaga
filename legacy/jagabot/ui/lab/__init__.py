"""JAGABOT Lab — interactive tool workbench (Streamlit 5th tab).

v3.3: Tool browser, parameter UI, code preview, sandbox execution,
ground truth comparison, notebook save/load.
"""

from jagabot.ui.lab.tool_registry import LabToolRegistry
from jagabot.ui.lab.parameter_form import ParameterForm
from jagabot.ui.lab.code_generator import CodeGenerator
from jagabot.ui.lab.ground_truth import GroundTruth
from jagabot.ui.lab.notebook_manager import NotebookManager

__all__ = [
    "LabToolRegistry",
    "ParameterForm",
    "CodeGenerator",
    "GroundTruth",
    "NotebookManager",
    "render_lab",
]


def render_lab() -> None:
    """Render the JAGABOT Lab tab inside Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        return

    registry = LabToolRegistry()
    form = ParameterForm()
    codegen = CodeGenerator()
    gt = GroundTruth()
    notebook = NotebookManager()

    st.header("📓 JAGABOT Lab")
    st.caption("Interactive tool workbench — browse, configure, execute, compare.")

    left, right = st.columns([1, 3])

    # --- Left: Tool browser ---
    with left:
        st.subheader("🧰 Tools")
        search_q = st.text_input("Search tools", placeholder="e.g. monte carlo")
        categories = registry.get_categories()

        selected_tool = st.session_state.get("lab_selected_tool")

        for cat, tool_names in sorted(categories.items()):
            if search_q:
                tool_names = [
                    n for n in tool_names
                    if search_q.lower() in n.lower()
                    or search_q.lower() in registry.get_tool_info(n).get("description", "").lower()
                ]
                if not tool_names:
                    continue

            with st.expander(f"**{cat.title()}** ({len(tool_names)})", expanded=bool(search_q)):
                for tn in sorted(tool_names):
                    info = registry.get_tool_info(tn)
                    if st.button(
                        f"{'🔹' if tn != selected_tool else '▶️'} {tn}",
                        key=f"lab_btn_{tn}",
                        use_container_width=True,
                    ):
                        st.session_state["lab_selected_tool"] = tn
                        st.session_state.pop("lab_result", None)
                        st.rerun()

    # --- Right: Workbench ---
    with right:
        if not selected_tool or selected_tool not in registry.get_tools():
            st.info("← Select a tool from the browser to get started.")
            return

        info = registry.get_tool_info(selected_tool)
        st.subheader(f"🔧 {selected_tool}")
        st.markdown(info.get("description", ""))

        methods = info.get("methods", [])
        selected_method = None
        if methods:
            selected_method = st.selectbox("Method", methods, key="lab_method")

        # Parameter form
        st.markdown("**Parameters**")
        params = form.render(
            selected_tool,
            info.get("parameters", {}),
            method=selected_method,
        )

        # Action buttons
        b1, b2, b3 = st.columns(3)
        with b1:
            run_btn = st.button("▶️ Run", type="primary", use_container_width=True)
        with b2:
            preview_btn = st.button("👁️ Preview Code", use_container_width=True)
        with b3:
            save_btn = st.button("💾 Save to Notebook", use_container_width=True)

        # Code preview
        if preview_btn:
            code = codegen.generate(selected_tool, params, method=selected_method)
            st.code(code, language="python")

        # Execute
        if run_btn:
            import asyncio

            tool = info.get("tool")
            if tool:
                with st.spinner("Running..."):
                    try:
                        if selected_method:
                            result = asyncio.run(
                                tool.execute(method=selected_method, params=params)
                            )
                        else:
                            result = asyncio.run(tool.execute(**params))
                        st.session_state["lab_result"] = str(result)
                    except Exception as exc:
                        st.session_state["lab_result"] = f"Error: {exc}"

        result = st.session_state.get("lab_result")
        if result:
            st.markdown("**Result**")
            st.code(result, language="json")

            # Ground truth comparison
            comparison = gt.compare(selected_tool, params, result)
            if comparison:
                if comparison["matches"]:
                    st.success(f"✅ Matches ground truth: {comparison['expected']}")
                else:
                    st.warning(
                        f"⚠️ Differs from ground truth.\n"
                        f"Expected: {comparison['expected']}\n"
                        f"Actual: {comparison['actual']}"
                    )

        # Save to notebook
        if save_btn and result:
            nb_name = st.session_state.get("lab_notebook_name", "default")
            code = codegen.generate(selected_tool, params, method=selected_method)
            notebook.save_cell(nb_name, selected_tool, params, code, result)
            st.success(f"Saved to notebook '{nb_name}'")

        # Notebook section
        st.divider()
        st.markdown("**📓 Notebooks**")
        nb_col1, nb_col2 = st.columns(2)
        with nb_col1:
            nb_name = st.text_input(
                "Notebook name", value="default", key="lab_notebook_name"
            )
        with nb_col2:
            if st.button("📂 Load"):
                cells = notebook.load_notebook(nb_name)
                if cells:
                    for i, cell in enumerate(cells):
                        with st.expander(f"Cell {i+1}: {cell.get('tool', '?')}"):
                            st.code(cell.get("code", ""), language="python")
                            st.text(cell.get("result", ""))
                else:
                    st.info("Notebook is empty or not found.")
