# -*- coding: utf-8 -*-
import overlay


def test_level_mapping_is_clamped_and_monotonic():
    assert overlay.level_to_unit(0.0) == 0.0
    assert overlay.level_to_unit(1.0) == 1.0
    room, speech = overlay.level_to_unit(0.006), overlay.level_to_unit(0.05)
    assert room < 0.15 < 0.4 < speech < 1.0


def test_meter_scrolls_and_rises_faster_than_it_falls():
    m = overlay.Meter(bars=5)
    m.push(0.1)
    assert m.values[:-1] == [0.0] * 4 and m.values[-1] > 0
    up = m.values[-1]
    m.push(0.0)
    assert 0 < m.values[-1] < up  # decays instead of dropping to zero
    assert up - m.values[-1] < up * 0.5
    m.reset()
    assert m.values == [0.0] * 5


def test_wave_stays_in_range():
    for t in (0.0, 0.3, 1.7):
        assert all(0.0 < v <= 1.0 for v in overlay.wave(t))
