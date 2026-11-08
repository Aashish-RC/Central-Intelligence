"""Unit tests for Step 25: AppComposer runtime."""

from agent_builder.composer.app_composer import AppComposer, ComposedApp


def test_app_composer_creation():
    composer = AppComposer()
    app = composer.compose_app(
        prompt="Create an AI SQL analyst that analyzes sales figures and queries databases",
        name="Sales SQL Analyst",
        target_domain="database",
        plugin_ids=["sqlite_tools", "csv_exporter"],
        active_skills=["skill_sql_query"],
    )

    assert isinstance(app, ComposedApp)
    assert app.name == "Sales SQL Analyst"
    assert app.target_domain == "database"
    assert len(app.plugin_ids) == 2
    assert "sqlite_tools" in app.plugin_ids
    assert app.primary_agent is not None

    # Verify synthesized layout engine integration
    assert app.layout is not None
    assert app.html_skeleton is not None
    assert "composed-app-layout" in app.html_skeleton
    assert composer.layout_engine.validate_layout(app.layout) is True

    # Execute app
    exec_res = composer.execute_app(app, "Show top 5 sales agents")
    assert exec_res["status"] == "success"
    assert exec_res["app_name"] == "Sales SQL Analyst"
    assert "sqlite_tools" in exec_res["plugins_used"]

