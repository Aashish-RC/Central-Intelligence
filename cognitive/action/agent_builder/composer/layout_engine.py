"""Layout Engine: Synthesizes, validates, and renders responsive visual component layouts for composed applications."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LayoutType(str, Enum):
    SPLIT_HORIZONTAL = "split_horizontal"
    SPLIT_VERTICAL = "split_vertical"
    GRID = "grid"
    TABS = "tabs"
    HERO_STACK = "hero_stack"
    PANEL = "panel"


class ComponentWidget(str, Enum):
    CHAT_WINDOW = "chat_window"
    CANVAS_PREVIEW = "canvas_preview"
    CODE_EDITOR = "code_editor"
    DATA_TABLE = "data_table"
    METRIC_CARD = "metric_card"
    INSPECTOR_PANEL = "inspector_panel"
    INPUT_FORM = "input_form"


class LayoutNode(BaseModel):
    """A node in the responsive visual component layout tree."""

    node_id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:6]}")
    layout_type: LayoutType = LayoutType.PANEL
    widget_type: Optional[ComponentWidget] = None
    title: str = "Component Panel"
    flex_weight: float = 1.0
    props: Dict[str, Any] = Field(default_factory=dict)
    children: List["LayoutNode"] = Field(default_factory=list)


class LayoutTree(BaseModel):
    """Complete layout specification for a composed application."""

    layout_id: str = Field(default_factory=lambda: f"layout_{uuid.uuid4().hex[:8]}")
    app_id: str = "default_app"
    title: str = "Application Layout"
    root: LayoutNode
    created_at: datetime = Field(default_factory=utc_now)


class LayoutEngine:
    """Synthesizes, validates, and generates responsive layouts for composed apps."""

    def synthesize_layout(
        self,
        app_id: str,
        title: str,
        domain: str = "general",
        plugins: Optional[List[str]] = None,
    ) -> LayoutTree:
        """Synthesizes an optimal layout hierarchy based on application domain and active plugins."""
        plugins = plugins or []
        domain_lower = domain.lower()

        if "code" in domain_lower or "dev" in domain_lower or any("code" in p for p in plugins):
            # Split view: Code editor on left, Live Canvas Preview and Chat on right
            root = LayoutNode(
                layout_type=LayoutType.SPLIT_HORIZONTAL,
                title="IDE Workspace",
                children=[
                    LayoutNode(
                        layout_type=LayoutType.PANEL,
                        widget_type=ComponentWidget.CODE_EDITOR,
                        title="Code Editor",
                        flex_weight=1.2,
                    ),
                    LayoutNode(
                        layout_type=LayoutType.SPLIT_VERTICAL,
                        title="Execution Surface",
                        flex_weight=1.0,
                        children=[
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.CANVAS_PREVIEW,
                                title="Live Canvas Preview",
                                flex_weight=1.0,
                            ),
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.CHAT_WINDOW,
                                title="Agent Copilot",
                                flex_weight=1.0,
                            ),
                        ],
                    ),
                ],
            )
        elif "data" in domain_lower or "sql" in domain_lower or "analytics" in domain_lower:
            # Dashboard view: Top metrics + bottom split (Query input vs Data table)
            root = LayoutNode(
                layout_type=LayoutType.SPLIT_VERTICAL,
                title="Analytics Dashboard",
                children=[
                    LayoutNode(
                        layout_type=LayoutType.GRID,
                        title="Summary Metrics",
                        flex_weight=0.4,
                        children=[
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.METRIC_CARD,
                                title="Primary KPI",
                                props={"metric": "Total Queries", "value": "1,420"},
                            ),
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.METRIC_CARD,
                                title="System Latency",
                                props={"metric": "P95 Latency", "value": "24ms"},
                            ),
                        ],
                    ),
                    LayoutNode(
                        layout_type=LayoutType.SPLIT_HORIZONTAL,
                        title="Query & Results",
                        flex_weight=1.6,
                        children=[
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.CHAT_WINDOW,
                                title="Query Assistant",
                                flex_weight=0.8,
                            ),
                            LayoutNode(
                                layout_type=LayoutType.PANEL,
                                widget_type=ComponentWidget.DATA_TABLE,
                                title="Result Grid",
                                flex_weight=1.2,
                            ),
                        ],
                    ),
                ],
            )
        else:
            # Standard conversational copilot layout
            root = LayoutNode(
                layout_type=LayoutType.SPLIT_HORIZONTAL,
                title="Conversational Workspace",
                children=[
                    LayoutNode(
                        layout_type=LayoutType.PANEL,
                        widget_type=ComponentWidget.CHAT_WINDOW,
                        title="Main Conversation",
                        flex_weight=1.4,
                    ),
                    LayoutNode(
                        layout_type=LayoutType.PANEL,
                        widget_type=ComponentWidget.INSPECTOR_PANEL,
                        title="Context & Tools Inspector",
                        flex_weight=0.6,
                    ),
                ],
            )

        return LayoutTree(
            app_id=app_id,
            title=title,
            root=root,
        )

    def validate_layout(self, tree: LayoutTree) -> bool:
        """Validates that all nodes have valid types and non-empty children where applicable."""
        def _check_node(node: LayoutNode) -> bool:
            if node.layout_type in (LayoutType.SPLIT_HORIZONTAL, LayoutType.SPLIT_VERTICAL, LayoutType.GRID, LayoutType.TABS):
                if not node.children:
                    return False
                return all(_check_node(child) for child in node.children)
            elif node.layout_type == LayoutType.PANEL:
                return node.widget_type is not None
            return True

        return _check_node(tree.root)

    def render_html_skeleton(self, tree: LayoutTree) -> str:
        """Renders an HTML/CSS flexbox and grid skeleton representing the synthesized layout."""
        def _render_node(node: LayoutNode) -> str:
            if node.layout_type == LayoutType.SPLIT_HORIZONTAL:
                inner = "".join(_render_node(c) for c in node.children)
                return f'<div class="layout-split-h" style="display:flex; flex-direction:row; flex:{node.flex_weight}; gap:12px;">{inner}</div>'
            elif node.layout_type == LayoutType.SPLIT_VERTICAL:
                inner = "".join(_render_node(c) for c in node.children)
                return f'<div class="layout-split-v" style="display:flex; flex-direction:column; flex:{node.flex_weight}; gap:12px;">{inner}</div>'
            elif node.layout_type == LayoutType.GRID:
                inner = "".join(_render_node(c) for c in node.children)
                return f'<div class="layout-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); flex:{node.flex_weight}; gap:12px;">{inner}</div>'
            else:
                widget_name = node.widget_type.value if node.widget_type else "panel"
                return (
                    f'<div class="layout-panel" data-widget="{widget_name}" style="flex:{node.flex_weight}; '
                    f'background:rgba(17,24,39,0.8); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:12px;">'
                    f'<h4 style="color:#c7d2fe; margin-bottom:8px;">{node.title}</h4>'
                    f'<div class="widget-content">[{widget_name.replace("_", " ").title()}]</div>'
                    f'</div>'
                )

        skeleton_inner = _render_node(tree.root)
        return (
            f'<div class="composed-app-layout" data-layout-id="{tree.layout_id}" style="display:flex; width:100%; height:100%;">'
            f'{skeleton_inner}'
            f'</div>'
        )
