"""Tests for L17 Release Channel Manager."""

from platform_infra.release.channels.channel_manager import ReleaseChannelManager


def test_app_a_stable_and_app_b_beta_scoped_components():
    mgr = ReleaseChannelManager()
    mgr.publish_to_channel("stable", "L1_perception", "1.4.0")
    mgr.publish_to_channel("stable", "L3_knowledge", "1.2.0")
    mgr.publish_to_channel("stable", "L6_output", "1.1.0")

    mgr.publish_to_channel("beta", "L1_perception", "1.5.0-rc1")
    mgr.publish_to_channel("beta", "L3_knowledge", "1.3.0-beta.2")
    mgr.publish_to_channel("beta", "L6_output", "1.2.0-beta.1")

    mgr.register_app("app-a", channel="stable", used_components={"L1_perception", "L3_knowledge"})
    mgr.register_app("app-b", channel="beta", used_components={"L3_knowledge", "L6_output"})

    m_a = mgr.resolve_manifest("app-a")
    m_b = mgr.resolve_manifest("app-b")

    assert m_a.channel == "stable"
    assert m_a.component_versions == {"L1_perception": "1.4.0", "L3_knowledge": "1.2.0"}
    assert "L6_output" not in m_a.component_versions

    assert m_b.channel == "beta"
    assert m_b.component_versions == {"L3_knowledge": "1.3.0-beta.2", "L6_output": "1.2.0-beta.1"}
    assert "L1_perception" not in m_b.component_versions

