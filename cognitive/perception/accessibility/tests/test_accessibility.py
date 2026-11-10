"""
Unit tests for Physical Accessibility Device Drivers (Layer 1: Perception, Task 1.10).
"""

import pytest
from cognitive.perception.accessibility.eye_tracking import (
    EyeTrackingDriver,
    GazePoint,
)
from cognitive.perception.accessibility.sign_language import (
    SignGloss,
    SignLanguageRecognizer,
)
from cognitive.perception.accessibility.switch_driver import (
    SwitchAccessDriver,
    SwitchAction,
    SwitchEvent,
)


def test_switch_access_driver_interface_and_not_implemented():
    """
    Acceptance: Module exists with documented interfaces; returns 'not implemented' for actual device input.
    """
    driver = SwitchAccessDriver(port="COM3")

    conn_res = driver.connect("/dev/ttyUSB0")
    assert conn_res["status"] == "not implemented"
    assert "deferred to physical accessibility pack" in conn_res["message"]

    with pytest.raises(NotImplementedError, match="not implemented"):
        driver.poll_events()

    # Emulation helper
    sim = driver.simulate_event(action=SwitchAction.PRESS, switch_id="sw_left")
    assert isinstance(sim, SwitchEvent)
    assert sim.action == SwitchAction.PRESS
    assert sim.switch_id == "sw_left"


def test_eye_tracking_driver_interface_and_not_implemented():
    """
    Acceptance: Eye tracker calibration and polling return 'not implemented'.
    """
    driver = EyeTrackingDriver(tracker_model="tobii_5c")

    calib_res = driver.calibrate()
    assert calib_res["status"] == "not implemented"
    assert "deferred to physical accessibility pack" in calib_res["message"]

    with pytest.raises(NotImplementedError, match="not implemented"):
        driver.get_gaze_point()

    # Emulation helper
    sim_gaze = driver.simulate_gaze(x=1920.0, y=1080.0)
    assert isinstance(sim_gaze, GazePoint)
    assert sim_gaze.screen_x == 1920.0
    assert sim_gaze.screen_y == 1080.0


def test_sign_language_recognizer_interface_and_not_implemented():
    """
    Acceptance: Sign language video recognition returns 'not implemented'.
    """
    recognizer = SignLanguageRecognizer(supported_languages=["ASL", "BSL"])

    res = recognizer.recognize_video_stream("camera_0")
    assert res["status"] == "not implemented"
    assert "ASL" in res["supported_languages"]

    with pytest.raises(NotImplementedError, match="not implemented"):
        recognizer.process_frame(b"frame_bytes")

    # Emulation helper
    sim_sign = recognizer.simulate_sign(gloss="THANK_YOU", language="ASL")
    assert isinstance(sim_sign, SignGloss)
    assert sim_sign.gloss == "THANK_YOU"
    assert sim_sign.confidence == 0.99

