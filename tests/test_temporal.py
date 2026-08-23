"""
Tests for wherewhen.temporal — datetime, timezone, and solar/lunar utilities.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from tests.conftest import LONDON_PT


class TestDatetimeHelpers:

    def test_ensure_utc_naive_input(self):
        from wherewhen.temporal import ensure_utc
        aware = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        assert aware.tzinfo is not None

    def test_ensure_utc_preserves_point_in_time(self):
        from wherewhen.temporal import ensure_utc
        bst = timezone(timedelta(hours=1))
        aware_bst = datetime(2026, 4, 24, 13, 0, 0, tzinfo=bst)
        assert ensure_utc(aware_bst).hour == 12

    def test_start_of_day(self):
        from wherewhen.temporal import start_of_day
        sod = start_of_day(datetime(2026, 4, 24, 15, 30, 45))
        assert sod.hour == sod.minute == sod.second == sod.microsecond == 0

    def test_end_of_day(self):
        from wherewhen.temporal import end_of_day
        eod = end_of_day(datetime(2026, 4, 24))
        assert eod.hour == 23 and eod.minute == 59 and eod.microsecond == 999_999

    def test_convert_to_datetime_string(self):
        from wherewhen.temporal import convert_to_datetime
        dt = convert_to_datetime("2026-04-24T12:00:00")
        assert isinstance(dt, datetime)

    def test_convert_to_datetime_passthrough(self):
        from wherewhen.temporal import convert_to_datetime
        original = datetime(2026, 4, 24)
        assert convert_to_datetime(original) is original

    def test_convert_to_datetime_force_utc_attaches_tzinfo(self):
        from wherewhen.temporal import convert_to_datetime
        dt = convert_to_datetime("2026-04-24", force_utc=True)
        assert dt.tzinfo is not None

    def test_convert_to_datetime_invalid_raises(self):
        from wherewhen.temporal import convert_to_datetime
        with pytest.raises(ValueError, match="⚠️"):
            convert_to_datetime("not-a-date")

    def test_convert_to_datetime_wrong_type_raises(self):
        from wherewhen.temporal import convert_to_datetime
        with pytest.raises(TypeError, match="⚠️"):
            convert_to_datetime(20260424)

    def test_convert_to_datetime_float_raises(self):
        from wherewhen.temporal import convert_to_datetime
        with pytest.raises(TypeError, match="⚠️"):
            convert_to_datetime(1714950400.0)

    def test_epoch_to_datetime_seconds(self):
        from wherewhen.temporal import epoch_to_datetime
        dt = epoch_to_datetime(1714950400)
        assert dt.year == 2024
        assert dt.tzinfo is not None

    def test_epoch_to_datetime_milliseconds(self):
        from wherewhen.temporal import epoch_to_datetime
        dt = epoch_to_datetime(1714950400000)
        assert dt.year == 2024

    def test_epoch_to_datetime_float(self):
        from wherewhen.temporal import epoch_to_datetime
        dt = epoch_to_datetime(1714950400.5)
        assert dt.year == 2024

    def test_epoch_to_datetime_wrong_type_raises(self):
        from wherewhen.temporal import epoch_to_datetime
        with pytest.raises(TypeError, match="⚠️"):
            epoch_to_datetime("1714950400")

    def test_epoch_to_datetime_bool_raises(self):
        from wherewhen.temporal import epoch_to_datetime
        with pytest.raises(TypeError, match="⚠️"):
            epoch_to_datetime(True)

    def test_shift_tz_by_name_london_to_nairobi(self):
        from wherewhen.temporal import shift_tz_by_name, ensure_utc
        utc_noon = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        nairobi = shift_tz_by_name(utc_noon, "Africa/Nairobi")
        assert nairobi.hour == 15

    def test_shift_tz_by_name_naive_localises(self):
        from wherewhen.temporal import shift_tz_by_name
        result = shift_tz_by_name(datetime(2026, 4, 24, 12, 0, 0), "Africa/Nairobi")
        assert result.tzinfo is not None


class TestSolarLunar:

    def test_point_to_tz_offset_london(self):
        from wherewhen.temporal import ensure_utc, point_to_tz_offset
        dt = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        tz_name, offset = point_to_tz_offset(LONDON_PT, dt)
        assert isinstance(tz_name, str)
        assert isinstance(offset, (int, float))

    def test_get_solar_data_returns_dict(self):
        from wherewhen.temporal import ensure_utc, get_solar_data
        dt = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        solar = get_solar_data(LONDON_PT, dt)
        assert isinstance(solar, dict)
        assert "Timezone Name" in solar

    def test_get_lunar_data_returns_dict(self):
        from wherewhen.temporal import ensure_utc, get_lunar_data
        dt = ensure_utc(datetime(2026, 4, 24, 12, 0, 0))
        lunar = get_lunar_data(LONDON_PT, dt)
        assert isinstance(lunar, dict)