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


class TestSolarLocalDay:
    """get_solar_data reports the local day at the point, everywhere on Earth."""

    TOKYO = (139.69, 35.69)
    HONOLULU = (-157.86, 21.31)
    AUCKLAND = (174.76, -36.85)
    SVALBARD = (15.6, 78.2)
    MCMURDO = (166.67, -77.85)
    TROMSO = (18.96, 69.65)

    @staticmethod
    def _solar(lonlat, dt):
        from shapely.geometry import Point
        from wherewhen.temporal import get_solar_data
        return get_solar_data(Point(*lonlat), dt)

    @pytest.mark.parametrize("lonlat", [TOKYO, HONOLULU, AUCKLAND, (-0.1278, 51.5074)])
    def test_events_fall_on_the_local_date_in_order(self, lonlat):
        s = self._solar(lonlat, datetime(2026, 4, 24))
        assert s["Evaluation Date"].isoformat() == "2026-04-24"
        for key in ("Sunrise", "Solar Noon", "Sunset"):
            assert s[key].date().isoformat() == "2026-04-24", key
        assert s["Sunrise"] < s["Solar Noon"] < s["Sunset"]
        assert 0 < s["Day Length (Hours)"] < 24
        civil = s["Civil"]
        assert civil["Dawn"] < s["Sunrise"] and s["Sunset"] < civil["Dusk"]

    def test_aware_datetime_uses_the_local_date(self):
        # 08:00 in Tokyo on the 24th is 23:00 UTC on the 23rd; the day is the 24th.
        jst = timezone(timedelta(hours=9))
        s = self._solar(self.TOKYO, datetime(2026, 4, 24, 8, 0, tzinfo=jst))
        assert s["Evaluation Date"].isoformat() == "2026-04-24"
        assert s["Sunrise"].date().isoformat() == "2026-04-24"
        assert 13 < s["Day Length (Hours)"] < 14

    def test_naive_datetime_uses_its_date_as_written(self):
        # Midnight UTC on the 24th is still the 23rd in Honolulu; the date
        # written is the one used.
        s = self._solar(self.HONOLULU, datetime(2026, 4, 24))
        assert s["Evaluation Date"].isoformat() == "2026-04-24"

    @pytest.mark.parametrize("lonlat, month_day, hours", [
        (SVALBARD, (6, 21), 24.0),    # polar day
        (SVALBARD, (12, 21), 0.0),    # polar night
        (MCMURDO, (6, 21), 0.0),      # southern polar night
        (MCMURDO, (12, 21), 24.0),    # southern polar day
        (TROMSO, (11, 28), 0.0),      # first day of polar night
    ])
    def test_polar_day_and_night_do_not_raise(self, lonlat, month_day, hours):
        s = self._solar(lonlat, datetime(2026, *month_day))
        assert s["Sunrise"] is None and s["Sunset"] is None
        assert s["Solar Noon"] is not None
        assert s["Day Length (Hours)"] == hours

    def test_day_after_polar_day_counts_from_midnight(self):
        # Tromsø 2026-05-17: the sun rises at about 01:20 and does not set.
        s = self._solar(self.TROMSO, datetime(2026, 5, 17))
        assert s["Sunrise"] is not None and s["Sunset"] is None
        assert 22 < s["Day Length (Hours)"] < 23

    def test_last_short_day_before_polar_night(self):
        # Tromsø 2026-11-27: the sun's centre clears -0.833° for about 20
        # minutes around noon.  astral reports no sunrise; before the fix
        # that day came out as 24 h of daylight.
        s = self._solar(self.TROMSO, datetime(2026, 11, 27))
        assert s["Sunrise"] < s["Solar Noon"] < s["Sunset"]
        assert 0 < s["Day Length (Hours)"] < 1

    def test_sunrise_astral_misses_is_still_found(self):
        # astral finds no McMurdo sunrise on 2026-08-20 (it falls across a
        # UTC day boundary); the sun does rise, at about 11:52 local.
        s = self._solar(self.MCMURDO, datetime(2026, 8, 20))
        assert s["Sunrise"] is not None
        assert s["Sunrise"].date().isoformat() == "2026-08-20"
        assert s["Sunrise"] < s["Solar Noon"] < s["Sunset"]
        assert 1.5 < s["Day Length (Hours)"] < 3

    @pytest.mark.parametrize("lonlat", [TOKYO, HONOLULU, AUCKLAND, SVALBARD, MCMURDO, TROMSO])
    def test_a_year_of_day_lengths_stays_in_range(self, lonlat):
        for i in range(0, 366, 3):
            day = datetime(2026, 1, 1) + timedelta(days=i)
            s = self._solar(lonlat, day)
            assert s["Evaluation Date"] == day.date()
            assert 0.0 <= s["Day Length (Hours)"] <= 24.0, day.date()
            for key in ("Sunrise", "Sunset"):
                if s[key] is not None:
                    assert s[key].date() == day.date(), (key, day.date())

    def test_lunar_data_uses_the_local_date(self):
        from shapely.geometry import Point
        from wherewhen.temporal import get_lunar_data
        jst = timezone(timedelta(hours=9))
        m = get_lunar_data(Point(*self.TOKYO), datetime(2026, 4, 24, 8, 0, tzinfo=jst))
        assert m["Evaluation Date"].isoformat() == "2026-04-24"


class TestWithoutTimezonefinder:
    """timezonefinder is a soft dependency: only coordinate lookups need it."""

    def _run_blocked(self, code: str):
        import subprocess
        import sys
        import textwrap
        prelude = "import sys\nsys.modules['timezonefinder'] = None  # make the import fail\n"
        return subprocess.run(
            [sys.executable, "-c", prelude + textwrap.dedent(code)],
            capture_output=True, text=True,
        )

    def test_shift_tz_by_name_needs_only_zoneinfo(self):
        result = self._run_blocked("""
            from datetime import datetime, timezone
            import wherewhen.temporal as t
            assert t._TZ_AVAILABLE is False
            local = t.shift_tz_by_name(datetime(2026, 4, 24, 12, tzinfo=timezone.utc), "America/New_York")
            print(local.hour, local.tzinfo)
        """)
        assert result.returncode == 0, result.stderr
        # Last line: the import prints wherewhen's load notice first.
        assert result.stdout.strip().splitlines()[-1].split() == ["8", "America/New_York"]

    def test_point_to_tz_offset_still_requires_timezonefinder(self):
        result = self._run_blocked("""
            from datetime import datetime
            from shapely.geometry import Point
            import wherewhen.temporal as t
            try:
                t.point_to_tz_offset(Point(-0.1278, 51.5074), datetime(2026, 4, 24, 12))
            except ImportError as exc:
                print("ImportError", "timezonefinder" in str(exc))
        """)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-1] == "ImportError True"

    def test_solar_and_lunar_errors_name_the_function_called(self):
        # The message must name what the user called, not an internal helper.
        result = self._run_blocked("""
            from datetime import datetime
            from shapely.geometry import Point
            import wherewhen.temporal as t
            for fn in (t.get_solar_data, t.get_lunar_data):
                try:
                    fn(Point(38.77, 48.53), datetime(2024, 6, 1, 12))
                except ImportError as exc:
                    msg = str(exc)
                    print(fn.__name__, f"[{fn.__name__}]" in msg, "timezonefinder" in msg,
                          "point_to_tz_offset" in msg)
        """)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-2:] == [
            "get_solar_data True True False",
            "get_lunar_data True True False",
        ]
