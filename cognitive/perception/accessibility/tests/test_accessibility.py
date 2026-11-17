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


def test_synthetic_device_abstraction_full_execution_cycle():
    """
    Acceptance: When operating in synthetic/virtual mode, device drivers
    provide full functional execution cycles without physical hardware dependencies.
    """
    # 1. Eye tracking synthetic calibration and gaze polling
    eye = EyeTrackingDriver(tracker_model="virtual_eye_5c", mode="synthetic")
    calib = eye.calibrate()
    assert calib["status"] == "calibrated"
    assert calib["points_calibrated"] == 9
    assert calib["accuracy"] >= 0.98
    assert eye.is_calibrated is True

    eye.simulate_gaze(x=500.0, y=400.0)
    gaze = eye.get_gaze_point()
    assert isinstance(gaze, GazePoint)
    assert gaze.screen_x == 500.0
    assert gaze.screen_y == 400.0

    # 2. Sign language video recognition stream and frame processing
    sign = SignLanguageRecognizer(supported_languages=["ASL", "BSL"], mode="synthetic")
    stream_res = sign.recognize_video_stream("camera_virtual_0")
    assert stream_res["status"] == "active"
    assert stream_res["fps"] == 30.0

    gloss_result = sign.process_frame("HELP")
    assert isinstance(gloss_result, SignGloss)
    assert gloss_result.gloss == "HELP"
    assert gloss_result.landmarks_tracked == 21

    # 3. Switch access driver connection and polling
    switch = SwitchAccessDriver(port="virtual_com", mode="synthetic")
    conn = switch.connect("virtual_switch_port")
    assert conn["status"] == "connected"

    switch.simulate_event(action=SwitchAction.STEP_SCAN, switch_id="sip_puff_1")
    polled = switch.poll_events()
    assert len(polled) == 1
    assert polled[0].action == SwitchAction.STEP_SCAN
    assert polled[0].switch_id == "sip_puff_1"


