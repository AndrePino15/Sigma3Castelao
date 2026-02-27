from server import messages


def test_build_clock_sync():
    """Clock sync builder should emit schema/versioned payload fields."""

    msg = messages.build_clock_sync(seq=2, show_time_ms=1234, server_unix_ms=999)
    assert msg["type"] == "clock_sync"
    assert msg["payload"]["schema"] == "show.clock.v1"
    assert msg["payload"]["seq"] == 2
    assert msg["payload"]["show_time_ms"] == 1234
    assert msg["payload"]["server_unix_ms"] == 999


def test_build_led_cue_start_stop():
    """Cue start/stop builders should emit expected command payloads."""

    start = messages.build_led_cue_start(
        cue_id="c1",
        animation_id="traveling_wave",
        start_time_show_ms=1000,
        duration_ms=2000,
        loop=False,
        section_id=3,
        params={"dx": 1.0, "dy": 0.0},
    )
    assert start["type"] == "led"
    assert start["payload"]["schema"] == "led.cue.v1"
    assert start["payload"]["cmd"] == "CUE_START"
    assert start["payload"]["scope"]["section_id"] == 3

    stop = messages.build_led_cue_stop("c1")
    assert stop["payload"]["cmd"] == "CUE_STOP"
    assert stop["payload"]["cue_id"] == "c1"
