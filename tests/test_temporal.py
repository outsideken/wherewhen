"""
Tests for wherewhen.temporal — datetime, timezone, and solar/lunar utilities.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from shapely.geometry import Point

from tests.conftest import LONDON_PT


def _daylight_by_sampling(lonlat, day, tz_name, step_s=10):
    """Hours the sun's centre spends above -0.833° in the local *day*, by sampling.

    Uses ephem's sun position only (refraction off), not its rise/set search.
    """
    import math
    from zoneinfo import ZoneInfo
    import ephem
    tz = ZoneInfo(tz_name)
    nxt = day + timedelta(days=1)
    start = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(timezone.utc)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz).astimezone(timezone.utc)
    obs = ephem.Observer()
    obs.lat, obs.lon, obs.pressure = str(lonlat[1]), str(lonlat[0]), 0
    sun = ephem.Sun()
    up = 0
    for i in range(int((end - start).total_seconds() // step_s)):
        when = start + timedelta(seconds=step_s * i + step_s / 2)
        obs.date = ephem.Date(when.replace(tzinfo=None))
        sun.compute(obs)
        up += math.degrees(sun.alt) > -0.833
    return up * step_s / 3600


class TestISO8601:
    """ISO8601 writes microseconds and reads 1-6 fractional digits (#26)."""

    def test_strftime_writes_six_fractional_digits(self):
        from wherewhen.temporal import ISO8601
        dt = datetime(2026, 1, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
        assert dt.strftime(ISO8601) == "2026-01-01T12:30:45.123456Z"
        assert datetime(2026, 1, 1, tzinfo=timezone.utc).strftime(ISO8601) == "2026-01-01T00:00:00.000000Z"

    @pytest.mark.parametrize("text, microsecond", [
        ("2026-01-01T12:30:45.123Z", 123000),      # JEMA milliseconds
        ("2026-01-01T12:30:45.123456Z", 123456),   # what strftime writes
        ("2026-01-01T12:30:45.1Z", 100000),
    ])
    def test_strptime_reads_one_to_six_digits(self, text, microsecond):
        from wherewhen.temporal import ISO8601
        assert datetime.strptime(text, ISO8601).microsecond == microsecond

    def test_strptime_gives_a_naive_datetime_that_ensure_utc_fixes(self):
        from wherewhen.temporal import ISO8601, ensure_utc
        parsed = datetime.strptime("2026-01-01T12:30:45.123Z", ISO8601)
        assert parsed.tzinfo is None
        assert ensure_utc(parsed) == datetime(2026, 1, 1, 12, 30, 45, 123000, tzinfo=timezone.utc)

    def test_round_trip(self):
        from wherewhen.temporal import ISO8601, ensure_utc
        dt = datetime(2026, 4, 24, 8, 0, 0, 987654, tzinfo=timezone.utc)
        assert ensure_utc(datetime.strptime(dt.strftime(ISO8601), ISO8601)) == dt

    def test_docstring_no_longer_claims_milliseconds(self):
        import wherewhen.temporal as t
        block = t.__doc__.split("ISO8601 : str", 1)[1].split("TWILIGHT_DEPRESSION_ANGLES", 1)[0]
        assert "millisecond precision" not in block
        assert "microseconds" in block


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
        # Midnight UTC on the 24th is still the 23rd in Honolulu.  A naive
        # datetime keeps the date written; an aware UTC one is converted.
        naive = self._solar(self.HONOLULU, datetime(2026, 4, 24))
        assert naive["Evaluation Date"].isoformat() == "2026-04-24"
        assert naive["Day Length (Hours)"] == pytest.approx(12.816, abs=0.01)
        aware = self._solar(self.HONOLULU, datetime(2026, 4, 24, tzinfo=timezone.utc))
        assert aware["Evaluation Date"].isoformat() == "2026-04-23"
        assert aware["Sunrise"].date().isoformat() == "2026-04-23"
        assert aware["Day Length (Hours)"] == pytest.approx(12.797, abs=0.01)

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

    # Days next to a polar period, where the sun can set just after midnight
    # and rise again.  Expected hours come from _daylight_by_sampling, which
    # counts 10-second steps above the horizon and shares no code with the
    # crossing search.
    @pytest.mark.parametrize("lonlat, month_day, rise_first", [
        (TROMSO, (5, 17), False),     # polar day starts: ~00:03 set, ~01:17 rise, no evening set
        (TROMSO, (7, 27), True),      # polar day ends: ~00:15 set, rise, evening set
        (SVALBARD, (8, 25), True),    # polar day ends, as Tromsø
        (MCMURDO, (2, 20), False),    # ~01:30 set, ~02:46 rise, up at midnight
        (TROMSO, (11, 27), True),     # last day before polar night: ~20 minutes
        (MCMURDO, (8, 20), True),     # first day after polar night (astral missed this rise)
    ])
    def test_day_length_counts_every_hour_the_sun_is_up(self, lonlat, month_day, rise_first):
        day = datetime(2026, *month_day)
        s = self._solar(lonlat, day)
        expected = _daylight_by_sampling(lonlat, day.date(), s["Timezone Name"])
        assert s["Day Length (Hours)"] == pytest.approx(expected, abs=0.01)
        assert s["Sunrise"].date() == s["Sunset"].date() == day.date()
        # Sunrise is the first rise of the day and Sunset the last set.
        assert (s["Sunrise"] < s["Sunset"]) is rise_first

    def test_polar_day_end_keeps_the_morning_daylight(self):
        # Tromsø 2026-07-27: up at midnight, sets ~00:15, rises ~01:29, sets
        # ~23:59.  Rise-to-set alone (22.5 h) would drop the first 15 minutes.
        s = self._solar(self.TROMSO, datetime(2026, 7, 27))
        rise_to_set = (s["Sunset"] - s["Sunrise"]).total_seconds() / 3600
        assert s["Day Length (Hours)"] > rise_to_set + 0.2

    def test_events_agree_with_ephem(self):
        ephem = pytest.importorskip("ephem")
        from zoneinfo import ZoneInfo
        lat, lon = 51.5074, -0.1278
        s = self._solar((lon, lat), datetime(2026, 9, 1))
        obs = ephem.Observer()
        obs.lat, obs.lon, obs.pressure = str(lat), str(lon), 0
        obs.horizon = "-0:49:59"   # -0.833°
        start = datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/London")).astimezone(timezone.utc)
        obs.date = start.strftime("%Y/%m/%d %H:%M:%S")
        for key, fn in (("Sunrise", obs.next_rising), ("Sunset", obs.next_setting)):
            expected = fn(ephem.Sun(), use_center=True).datetime().replace(tzinfo=timezone.utc)
            assert abs((s[key] - expected).total_seconds()) < 10, key

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

    def test_twilight_brackets_sunrise_and_sunset(self):
        s = self._solar((-0.1278, 51.5074), datetime(2026, 9, 1))
        order = [s["Astronomical"]["Dawn"], s["Nautical"]["Dawn"], s["Civil"]["Dawn"],
                 s["Sunrise"], s["Solar Noon"], s["Sunset"],
                 s["Civil"]["Dusk"], s["Nautical"]["Dusk"], s["Astronomical"]["Dusk"]]
        assert order == sorted(order)

    def test_raised_observer_sees_the_sun_earlier(self):
        from shapely.geometry import Point
        from wherewhen.temporal import get_solar_data
        pt = Point(7.7, 46.0)
        sea = get_solar_data(pt, datetime(2026, 9, 1))
        high = get_solar_data(pt, datetime(2026, 9, 1), elevation=2000.0)
        # Horizon dip at 2 000 m is ~1.4°: sunrise roughly 8-9 minutes earlier.
        earlier = (sea["Sunrise"] - high["Sunrise"]).total_seconds() / 60
        assert 6 < earlier < 11

    def test_lunar_data_uses_the_local_date(self):
        from shapely.geometry import Point
        from wherewhen.temporal import get_lunar_data
        jst = timezone(timedelta(hours=9))
        m = get_lunar_data(Point(*self.TOKYO), datetime(2026, 4, 24, 8, 0, tzinfo=jst))
        assert m["Evaluation Date"].isoformat() == "2026-04-24"


class TestLunarData:
    """get_lunar_data comes from ephem: exact illumination, age in days, local-day rise/set."""

    LONDON = (-0.1278, 51.5074)

    @staticmethod
    def _lunar(lonlat, dt, **kwargs):
        from shapely.geometry import Point
        from wherewhen.temporal import get_lunar_data
        return get_lunar_data(Point(*lonlat), dt, **kwargs)

    def test_illumination_and_age_match_ephem_at_local_noon(self):
        import ephem
        m = self._lunar(self.LONDON, datetime(2026, 4, 24))
        noon_utc = ephem.Date("2026/4/24 11:00")   # 12:00 BST
        assert m["Illumination (%)"] == pytest.approx(ephem.Moon(noon_utc).phase, abs=0.1)
        assert m["Moon Age (Days)"] == pytest.approx(noon_utc - ephem.previous_new_moon(noon_utc), abs=0.1)
        # astral's estimate was 56.9 % for this day.
        assert 50 < m["Illumination (%)"] < 58

    def test_phase_names_follow_the_principal_phases(self):
        # 2026-04-24 02:32 UTC first quarter; 2026-05-01 17:23 UTC full moon.
        assert self._lunar(self.LONDON, datetime(2026, 4, 24))["Phase Name"] == "First Quarter"
        assert self._lunar(self.LONDON, datetime(2026, 4, 22))["Phase Name"] == "Waxing Crescent"
        assert self._lunar(self.LONDON, datetime(2026, 4, 27))["Phase Name"] == "Waxing Gibbous"
        assert self._lunar(self.LONDON, datetime(2026, 5, 1))["Phase Name"] == "Full Moon"
        assert self._lunar(self.LONDON, datetime(2026, 5, 4))["Phase Name"] == "Waning Gibbous"

    def test_lunation_fraction_matches_ephem(self):
        import ephem
        m = self._lunar(self.LONDON, datetime(2026, 4, 24))
        noon_utc = ephem.Date("2026/4/24 11:00")   # 12:00 BST
        previous_new = ephem.previous_new_moon(noon_utc)
        expected = (noon_utc - previous_new) / (ephem.next_new_moon(noon_utc) - previous_new)
        assert m["Lunation (Fraction)"] == pytest.approx(expected, abs=1e-4)
        assert m["Is Waxing"] is True
        assert m["Lunation (Fraction)"] == pytest.approx(0.25, abs=0.02)   # first quarter
        # A full moon is not exactly half way through a lunation.
        full = self._lunar(self.LONDON, datetime(2026, 5, 1))
        assert full["Lunation (Fraction)"] == pytest.approx(0.5, abs=0.04)

    def test_lunation_fraction_wraps_to_zero_just_before_new_moon(self):
        # London noon 2026-02-17 is ~0.99997 through the lunation; rounded to
        # four places that was 1.0 (Cursor, #24).  New moon 12:01 UTC.
        m = self._lunar(self.LONDON, datetime(2026, 2, 17))
        assert m["Phase Name"] == "New Moon"
        assert m["Lunation (Fraction)"] == 0.0

    def test_lunation_fraction_stays_in_range_all_year(self):
        for i in range(365):
            m = self._lunar(self.LONDON, datetime(2026, 1, 1) + timedelta(days=i))
            assert 0.0 <= m["Lunation (Fraction)"] < 1.0
            assert 0.0 <= m["Moon Age (Days)"] < 30.0

    def test_removed_keys_are_gone(self):
        m = self._lunar(self.LONDON, datetime(2026, 4, 24))
        assert "Phase Number" not in m
        assert "Ephem Available" not in m

    def test_moonrise_and_moonset_are_on_the_local_day(self):
        for day in range(1, 31):
            m = self._lunar(self.LONDON, datetime(2026, 4, day))
            for key in ("Moonrise", "Moonset"):
                if m[key] is not None:
                    assert m[key].date().isoformat() == f"2026-04-{day:02d}", key

    def test_a_day_without_a_moonset_reports_none(self):
        # London 2026-04-20: the moon set at 23:5x on the 19th and next at
        # 01:03 on the 21st.  Before, the 21st's moonset was reported.
        m = self._lunar(self.LONDON, datetime(2026, 4, 20))
        assert m["Moonrise"] is not None and m["Moonset"] is None

    def test_include_riseset_false_skips_rise_and_set(self):
        m = self._lunar(self.LONDON, datetime(2026, 4, 24), include_riseset=False)
        assert m["Moonrise"] is None and m["Moonset"] is None


class TestWithoutAstral:
    """astral is no longer used: solar and lunar data work with it blocked."""

    def test_solar_and_lunar_run_without_astral(self):
        import subprocess
        import sys
        import textwrap
        code = textwrap.dedent("""
            import sys
            sys.modules['astral'] = None  # make any astral import fail
            from datetime import datetime
            from shapely.geometry import Point
            from wherewhen.temporal import get_solar_data, get_lunar_data, TWILIGHT_DEPRESSION_ANGLES
            s = get_solar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
            m = get_lunar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
            print(round(s["Day Length (Hours)"]), m["Phase Name"], sorted(TWILIGHT_DEPRESSION_ANGLES))
        """)
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-1] == (
            "14 First Quarter ['Astronomical', 'Civil', 'Nautical']"
        )

    def test_old_constant_name_is_gone(self):
        import wherewhen
        import wherewhen.temporal as temporal
        assert not hasattr(temporal, "ASTRAL_DEPRESSION_ANGLES")
        assert not hasattr(wherewhen, "ASTRAL_DEPRESSION_ANGLES")


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


class TestPassSearch:
    """_crossings_of keeps going when ephem can place neither a crossing nor an antitransit."""

    def test_unplaceable_antitransit_moves_on_half_a_day(self):
        import ephem
        from wherewhen.temporal import _crossings_of

        calls = []

        class Observer:
            def next_rising(self, body, start, use_center):
                calls.append(("rising", float(start)))
                raise ephem.AlwaysUpError("no crossing in this pass")

            def next_antitransit(self, body, start):
                calls.append(("antitransit", float(start)))
                raise ephem.CircumpolarError("cannot place it")

        start = datetime(2026, 6, 21, tzinfo=timezone.utc)
        found = _crossings_of(Observer(), object(), start, start + timedelta(days=1),
                              rising=True, use_center=True)
        assert found == []
        rising_starts = [s for kind, s in calls if kind == "rising"]
        assert [round(b - a, 6) for a, b in zip(rising_starts, rising_starts[1:])] == [0.5]


# ── Time features (#36) ──────────────────────────────────────────────────────

_INSTANT = datetime(2024, 5, 5, 23, 6, 40, 123456, tzinfo=timezone.utc)
_INSTANT_S = 1714950400        # _INSTANT without the fraction


class TestEpochUnits:
    """epoch_to_datetime reads s, ms, µs and ns by size."""

    @pytest.mark.parametrize("scale", [1, 10**3, 10**6, 10**9])
    def test_every_unit_gives_the_same_moment(self, scale):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(_INSTANT_S * scale) == _INSTANT.replace(microsecond=0)

    def test_microseconds_and_nanoseconds_are_exact(self):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(1714950400123456) == _INSTANT
        assert epoch_to_datetime(1714950400123456789) == _INSTANT   # ns cut to µs

    def test_boundaries(self):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(9_999_999_999).year == 2286          # last seconds value
        assert epoch_to_datetime(10_000_000_000) == datetime(1970, 4, 26, 17, 46, 40, tzinfo=timezone.utc)
        assert epoch_to_datetime(9_999_999_999_999).year == 2286      # last ms value
        assert epoch_to_datetime(10**13).year == 1970                 # first µs value
        assert epoch_to_datetime(10**16).year == 1970                 # first ns value

    def test_negative_values_use_their_size(self):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(-_INSTANT_S * 10**3) == epoch_to_datetime(-_INSTANT_S)
        assert epoch_to_datetime(-1) == datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        assert epoch_to_datetime(-1_500_000).year == 1969            # below 1e10: seconds

    def test_floats_divide_by_the_unit(self):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(1714950400123.0) == _INSTANT.replace(microsecond=123000)
        assert epoch_to_datetime(1714950400123456.0).replace(microsecond=0) == _INSTANT.replace(microsecond=0)

    def test_int_and_float_seconds_agree(self):
        from wherewhen.temporal import epoch_to_datetime
        assert epoch_to_datetime(_INSTANT_S) == epoch_to_datetime(float(_INSTANT_S))


class TestFormatISO8601:

    def test_default_is_milliseconds(self):
        from wherewhen.temporal import format_iso8601
        assert format_iso8601(_INSTANT) == "2024-05-05T23:06:40.123Z"

    @pytest.mark.parametrize("digits, expected", [
        (0, "2024-05-05T23:06:40Z"),
        (1, "2024-05-05T23:06:40.1Z"),
        (2, "2024-05-05T23:06:40.12Z"),
        (3, "2024-05-05T23:06:40.123Z"),
        (4, "2024-05-05T23:06:40.1234Z"),
        (5, "2024-05-05T23:06:40.12345Z"),
        (6, "2024-05-05T23:06:40.123456Z"),
    ])
    def test_digits(self, digits, expected):
        from wherewhen.temporal import format_iso8601
        assert format_iso8601(_INSTANT, digits=digits) == expected

    def test_cuts_never_rounds(self):
        from wherewhen.temporal import format_iso8601
        last = datetime(2026, 12, 31, 23, 59, 59, 999999)
        assert format_iso8601(last) == "2026-12-31T23:59:59.999Z"
        assert format_iso8601(last, digits=0) == "2026-12-31T23:59:59Z"

    def test_naive_is_utc_and_aware_is_converted(self):
        from wherewhen.temporal import format_iso8601
        tokyo = timezone(timedelta(hours=9))
        assert format_iso8601(datetime(2026, 1, 1, 8, 0, tzinfo=tokyo)) == "2025-12-31T23:00:00.000Z"
        assert format_iso8601(datetime(2026, 1, 1, 8, 0)) == "2026-01-01T08:00:00.000Z"

    def test_reads_back_with_the_iso8601_constant(self):
        from wherewhen.temporal import ISO8601, ensure_utc, format_iso8601
        for digits in range(1, 7):
            text = format_iso8601(_INSTANT, digits=digits)
            back = ensure_utc(datetime.strptime(text, ISO8601))
            cut = 10 ** (6 - digits)
            assert back == _INSTANT.replace(microsecond=_INSTANT.microsecond // cut * cut)

    def test_matches_the_jema_millisecond_format(self):
        # jematools' _fmt_temporal_dt: strftime seconds + '.%03d' ms + 'Z'.
        from wherewhen.temporal import format_iso8601
        for dt in (_INSTANT, datetime(2026, 4, 23), datetime(2026, 5, 1, 23, 59, 59, 999999)):
            u = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            jema = f"{u.strftime('%Y-%m-%dT%H:%M:%S')}.{u.microsecond // 1000:03d}Z"
            assert format_iso8601(dt) == jema

    def test_years_below_1000_are_padded(self):
        from wherewhen.temporal import format_iso8601
        assert format_iso8601(datetime(999, 1, 2, 3, 4, 5)) == "0999-01-02T03:04:05.000Z"


class TestToLocalTime:

    def test_tokyo(self):
        from wherewhen.temporal import to_local_time
        local = to_local_time(datetime(2026, 7, 1, 12, tzinfo=timezone.utc), Point(139.6917, 35.6895))
        assert (local.hour, str(local.tzinfo)) == (21, "Asia/Tokyo")

    def test_london_summer_and_winter(self):
        from wherewhen.temporal import to_local_time
        assert to_local_time(datetime(2026, 7, 1, 12), LONDON_PT).hour == 13   # BST, naive = UTC
        assert to_local_time(datetime(2026, 1, 1, 12), LONDON_PT).hour == 12   # GMT

    def test_same_moment(self):
        from wherewhen.temporal import to_local_time
        dt = datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc)   # the night London changes clocks
        assert to_local_time(dt, LONDON_PT) == dt

    def test_agrees_with_point_to_tz_offset_and_shift_tz_by_name(self):
        from wherewhen.temporal import point_to_tz_offset, shift_tz_by_name, to_local_time
        dt = datetime(2026, 11, 15, 6, tzinfo=timezone.utc)
        for pt in (LONDON_PT, Point(36.8219, -1.2921), Point(-74.006, 40.7128), Point(-30.0, 0.0)):
            name, offset = point_to_tz_offset(pt, dt)
            local = to_local_time(dt, pt)
            assert local == shift_tz_by_name(dt, name)
            assert local.utcoffset() == timedelta(hours=offset)


class TestSunPosition:

    def test_keys_and_ranges(self):
        from wherewhen.temporal import sun_position
        pos = sun_position(LONDON_PT, datetime(2026, 6, 21, 9, 0))
        assert set(pos) == {"Altitude (Degrees)", "Azimuth (Degrees)"}
        assert -90 <= pos["Altitude (Degrees)"] <= 90
        assert 0 <= pos["Azimuth (Degrees)"] < 360

    def test_london_solar_noon_is_due_south_and_at_its_highest(self):
        from wherewhen.temporal import get_solar_data, sun_position
        noon = get_solar_data(LONDON_PT, datetime(2026, 6, 21))["Solar Noon"]
        pos = sun_position(LONDON_PT, noon)
        assert pos["Azimuth (Degrees)"] == pytest.approx(180.0, abs=0.05)
        # 90 - latitude + declination (23.44°) on the June solstice.
        assert pos["Altitude (Degrees)"] == pytest.approx(90 - 51.5074 + 23.44, abs=0.05)
        for minutes in (-10, 10):
            assert sun_position(LONDON_PT, noon + timedelta(minutes=minutes))["Altitude (Degrees)"] < pos["Altitude (Degrees)"]

    def test_morning_sun_is_in_the_east(self):
        from wherewhen.temporal import sun_position
        az = sun_position(LONDON_PT, datetime(2026, 3, 20, 7, 0))["Azimuth (Degrees)"]
        assert 60 < az < 120

    def test_aware_and_naive_utc_agree(self):
        from wherewhen.temporal import sun_position
        naive = datetime(2026, 6, 21, 9, 0)
        paris = naive.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=2)))
        assert sun_position(LONDON_PT, naive) == sun_position(LONDON_PT, paris)

    def test_needs_no_timezonefinder(self):
        result = TestWithoutTimezonefinder()._run_blocked("""
            from datetime import datetime
            from shapely.geometry import Point
            import wherewhen.temporal as t
            pt, when = Point(-0.1278, 51.5074), datetime(2026, 6, 21, 12)
            print(t.is_daylight(pt, when), t.sun_position(pt, when)["Altitude (Degrees)"] > 0)
        """)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-1] == "True True"


class TestIsDaylight:

    def test_flips_at_sunrise_and_sunset(self):
        from wherewhen.temporal import get_solar_data, is_daylight
        for pt in (LONDON_PT, Point(36.8219, -1.2921), Point(151.2093, -33.8688)):
            data = get_solar_data(pt, datetime(2026, 11, 15))
            second = timedelta(seconds=1)
            assert not is_daylight(pt, data["Sunrise"] - second)
            assert is_daylight(pt, data["Sunrise"] + second)
            assert is_daylight(pt, data["Sunset"] - second)
            assert not is_daylight(pt, data["Sunset"] + second)

    def test_elevation_brings_sunrise_earlier(self):
        from wherewhen.temporal import get_solar_data, is_daylight
        sea = get_solar_data(LONDON_PT, datetime(2026, 11, 15))["Sunrise"]
        high = get_solar_data(LONDON_PT, datetime(2026, 11, 15), elevation=3000.0)["Sunrise"]
        between = high + (sea - high) / 2
        assert not is_daylight(LONDON_PT, between)
        assert is_daylight(LONDON_PT, between, elevation=3000.0)

    def test_polar_night_and_polar_day(self):
        from wherewhen.temporal import is_daylight
        tromso = Point(18.9553, 69.6492)
        assert not any(is_daylight(tromso, datetime(2026, 12, 21, h)) for h in range(24))
        assert all(is_daylight(tromso, datetime(2026, 6, 21, h)) for h in range(24))

    def test_twilight_is_not_daylight(self):
        from wherewhen.temporal import TWILIGHT_DEPRESSION_ANGLES, get_solar_data, is_daylight, sun_position
        civil_dawn = get_solar_data(LONDON_PT, datetime(2026, 11, 15))["Civil"]["Dawn"]
        later = civil_dawn + timedelta(minutes=5)
        assert not is_daylight(LONDON_PT, later)
        assert sun_position(LONDON_PT, later)["Altitude (Degrees)"] > -TWILIGHT_DEPRESSION_ANGLES["Civil"]


LONGYEARBYEN_PT = Point(15.6, 78.2)


class TestMoonPosition:

    def test_keys_and_ranges(self):
        from wherewhen.temporal import moon_position
        pos = moon_position(LONDON_PT, datetime(2026, 12, 21, 20, 0))
        assert set(pos) == {"Altitude (Degrees)", "Azimuth (Degrees)"}
        assert -90 <= pos["Altitude (Degrees)"] <= 90
        assert 0 <= pos["Azimuth (Degrees)"] < 360

    def test_matches_ephem_directly(self):
        import math
        import ephem
        from wherewhen.temporal import moon_position
        when = datetime(2026, 12, 21, 20, 0)
        obs = ephem.Observer()
        obs.lat, obs.lon, obs.pressure, obs.date = str(LONDON_PT.y), str(LONDON_PT.x), 0, ephem.Date(when)
        moon = ephem.Moon(obs)
        pos = moon_position(LONDON_PT, when)
        assert pos["Altitude (Degrees)"] == pytest.approx(math.degrees(moon.alt), abs=1e-9)
        assert pos["Azimuth (Degrees)"] == pytest.approx(math.degrees(moon.az), abs=1e-9)

    def test_aware_and_naive_utc_agree(self):
        from wherewhen.temporal import moon_position
        naive = datetime(2026, 12, 21, 20, 0)
        tehran = naive.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=3, minutes=30)))
        assert moon_position(LONDON_PT, naive) == moon_position(LONDON_PT, tehran)


class TestIsMoonUp:

    def test_flips_at_moonrise_and_moonset(self):
        from wherewhen.temporal import get_lunar_data, is_moon_up
        for pt in (LONDON_PT, Point(49.6779, 34.0880), Point(151.2093, -33.8688)):
            data = get_lunar_data(pt, datetime(2026, 12, 21))
            second = timedelta(seconds=1)
            for rise in [data["Moonrise"]] if data["Moonrise"] else []:
                assert not is_moon_up(pt, rise - second) and is_moon_up(pt, rise + second)
            for moonset in [data["Moonset"]] if data["Moonset"] else []:
                assert is_moon_up(pt, moonset - second) and not is_moon_up(pt, moonset + second)

    def test_up_all_day_when_there_is_no_rise_or_set(self):
        # 21 Dec 2026 at 78.2°N: polar night, and the moon never sets.
        from wherewhen.temporal import get_lunar_data, is_moon_up
        data = get_lunar_data(LONGYEARBYEN_PT, datetime(2026, 12, 21))
        assert data["Moonrise"] is None and data["Moonset"] is None
        start = datetime(2026, 12, 21, 0, tzinfo=timezone(timedelta(hours=1)))
        assert all(is_moon_up(LONGYEARBYEN_PT, start + timedelta(minutes=m)) for m in range(0, 24 * 60, 10))

    def test_elevation_brings_moonrise_earlier(self):
        from wherewhen.temporal import get_lunar_data, is_moon_up
        sea = get_lunar_data(LONDON_PT, datetime(2026, 12, 21))["Moonrise"]
        high = get_lunar_data(LONDON_PT, datetime(2026, 12, 21), elevation=3000.0)["Moonrise"]
        between = high + (sea - high) / 2
        assert not is_moon_up(LONDON_PT, between)
        assert is_moon_up(LONDON_PT, between, elevation=3000.0)

    def test_needs_no_timezonefinder(self):
        result = TestWithoutTimezonefinder()._run_blocked("""
            from datetime import datetime
            from shapely.geometry import Point
            import wherewhen.temporal as t
            pt, when = Point(15.6, 78.2), datetime(2026, 12, 21, 12)
            print(t.is_moon_up(pt, when), t.moon_position(pt, when)["Altitude (Degrees)"] > 0,
                  t.get_lunar_month(when)["Full Moon"].day)
        """)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().splitlines()[-1] == "True True 24"


class TestLunarMonth:

    def test_december_2026(self):
        from wherewhen.temporal import get_lunar_month
        month = get_lunar_month(datetime(2026, 12, 21))
        assert [month[k].strftime("%Y-%m-%d %H:%M") for k in
                ("New Moon", "First Quarter", "Full Moon", "Last Quarter", "Next New Moon")] == [
            "2026-12-09 00:51", "2026-12-17 05:42", "2026-12-24 01:28", "2026-12-30 18:59", "2027-01-07 20:24",
        ]
        assert month["Length (Days)"] == pytest.approx(29.8143, abs=1e-4)
        assert all(month[k].tzinfo == timezone.utc for k in month if k != "Length (Days)")

    def test_phases_are_in_order_and_bracket_the_moment(self):
        from wherewhen.temporal import get_lunar_month
        for day in range(1, 366, 17):
            when = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
            m = get_lunar_month(when)
            times = [m[k] for k in ("New Moon", "First Quarter", "Full Moon", "Last Quarter", "Next New Moon")]
            assert times == sorted(times)
            assert m["New Moon"] <= when < m["Next New Moon"]

    def test_exactly_at_a_new_moon_starts_that_lunation(self):
        from wherewhen.temporal import get_lunar_month
        new = get_lunar_month(datetime(2026, 12, 21))["New Moon"]
        # ephem's dates are floats: a round trip moves the moment by microseconds.
        assert abs(get_lunar_month(new)["New Moon"] - new) < timedelta(milliseconds=1)
        assert abs(get_lunar_month(new - timedelta(seconds=1))["Next New Moon"] - new) < timedelta(milliseconds=1)

    def test_agrees_with_get_lunar_data_age(self):
        from wherewhen.temporal import get_lunar_data, get_lunar_month
        data = get_lunar_data(LONDON_PT, datetime(2026, 12, 21))
        noon = datetime(2026, 12, 21, 12, tzinfo=timezone.utc)   # London is on UTC in December
        age = (noon - get_lunar_month(noon)["New Moon"]).total_seconds() / 86400
        assert age == pytest.approx(data["Moon Age (Days)"], abs=0.05)


ARAK_PT = Point(49.678, 34.088)


class TestMoonIlluminance:

    def test_the_lux_constant_gives_the_sun_above_the_air(self):
        # Allen: the sun (V = -26.74) gives about 1.27e5 lux outside the atmosphere.
        from wherewhen.temporal import _LUX_AT_MAGNITUDE_ZERO
        assert _LUX_AT_MAGNITUDE_ZERO * 10 ** (0.4 * 26.74) == pytest.approx(1.27e5, rel=0.02)

    def test_airmass(self):
        from wherewhen.temporal import _airmass
        assert _airmass(90.0) == pytest.approx(1.0, abs=1e-3)
        assert _airmass(30.0) == pytest.approx(1.995, abs=0.01)
        assert 35 < _airmass(0.0) < 40

    def test_full_moon_high_in_the_sky(self):
        from wherewhen.temporal import moon_illuminance, moon_position
        when = datetime(2026, 12, 23, 20, 30)          # 00:00 in Tehran, full moon 24 Dec
        assert moon_position(ARAK_PT, when)["Altitude (Degrees)"] > 75
        assert 0.22 < moon_illuminance(ARAK_PT, when) < 0.32

    def test_zero_while_the_moon_is_down(self):
        from wherewhen.temporal import moon_illuminance, moon_position
        for hour in range(0, 24, 3):
            when = datetime(2026, 12, 18, hour)
            down = moon_position(ARAK_PT, when)["Altitude (Degrees)"] <= 0
            assert (moon_illuminance(ARAK_PT, when) == 0.0) == down

    def test_a_quarter_moon_is_far_dimmer_than_half_a_full_one(self):
        # Brightness does not follow the lit fraction: per unit of sin(altitude)
        # the first quarter (50 % lit) gives about a tenth of the full moon.
        import math
        from wherewhen.temporal import moon_illuminance, moon_position
        full, quarter = datetime(2026, 12, 23, 20, 30), datetime(2026, 12, 17, 15, 0)

        def per_sine(when):
            alt = moon_position(ARAK_PT, when)["Altitude (Degrees)"]
            return moon_illuminance(ARAK_PT, when) / math.sin(math.radians(alt))

        assert per_sine(quarter) < 0.15 * per_sine(full)

    def test_naive_means_utc(self):
        from zoneinfo import ZoneInfo
        from wherewhen.temporal import moon_illuminance
        naive = datetime(2026, 12, 23, 20, 30)
        tehran = datetime(2026, 12, 24, 0, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        assert moon_illuminance(ARAK_PT, naive) == moon_illuminance(ARAK_PT, tehran)


class TestNightMoonlight:

    def test_full_moon_night_in_arak(self):
        from wherewhen.temporal import get_night_moonlight, moon_illuminance
        night = get_night_moonlight(ARAK_PT, datetime(2026, 12, 23))
        assert night["Evaluation Date"].isoformat() == "2026-12-23"
        assert night["Timezone Name"] == "Asia/Tehran"
        assert 0.22 < night["Peak Moonlight (Lux)"] < 0.32
        assert f"{night['Peak Time']:%Y-%m-%d %H:%M}" == "2026-12-24 00:00"
        assert night["Peak Moonlight (Lux)"] == moon_illuminance(ARAK_PT, night["Peak Time"])
        # Civil dusk 17:33 to civil dawn 06:45, on a 10-minute grid.
        assert night["Dark Sky (Hours)"] == pytest.approx(13.2, abs=0.2)

    def test_summer_full_moon_is_dimmer(self):
        # The June full moon rides low over short nights.
        from wherewhen.temporal import get_night_moonlight
        winter = get_night_moonlight(ARAK_PT, datetime(2026, 12, 23))["Peak Moonlight (Lux)"]
        summer = get_night_moonlight(ARAK_PT, datetime(2026, 6, 29))["Peak Moonlight (Lux)"]
        assert summer < winter / 2

    def test_new_moon_night_has_next_to_none(self):
        from wherewhen.temporal import get_night_moonlight
        assert get_night_moonlight(ARAK_PT, datetime(2026, 12, 9))["Peak Moonlight (Lux)"] < 0.001

    def test_polar_day_has_no_dark_sky(self):
        from wherewhen.temporal import get_night_moonlight
        night = get_night_moonlight(Point(18.96, 69.65), datetime(2026, 6, 21))
        assert night["Dark Sky (Hours)"] == 0.0
        assert night["Peak Moonlight (Lux)"] == 0.0 and night["Peak Time"] is None

    def test_an_aware_moment_picks_its_local_day(self):
        from zoneinfo import ZoneInfo
        from wherewhen.temporal import get_night_moonlight
        early = datetime(2026, 12, 23, 23, 0, tzinfo=timezone.utc)       # 02:30 on the 24th in Tehran
        assert get_night_moonlight(ARAK_PT, early)["Evaluation Date"].isoformat() == "2026-12-24"
        assert get_night_moonlight(ARAK_PT, datetime(2026, 12, 23, 23, 0))["Evaluation Date"].isoformat() == \
            "2026-12-23"   # naive: its own date


class TestMoonPhases:

    def test_december_2026_matches_get_lunar_month(self):
        from wherewhen.temporal import get_lunar_month, get_moon_phases
        phases = get_moon_phases(datetime(2026, 12, 7), datetime(2027, 1, 5))
        month = get_lunar_month(datetime(2026, 12, 21))
        assert [p["Phase"] for p in phases] == ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]
        for p in phases:
            assert abs(p["Time"] - month[p["Phase"]]) < timedelta(milliseconds=1)
            assert p["Time"].tzinfo == timezone.utc

    def test_start_is_included_and_end_is_not(self):
        # ephem finds the same phase a few microseconds apart from different
        # starting points, so the boundaries hold to within a millisecond.
        from wherewhen.temporal import get_lunar_month, get_moon_phases
        full = get_lunar_month(datetime(2026, 12, 21))["Full Moon"]
        ms = timedelta(milliseconds=1)
        assert [p["Phase"] for p in get_moon_phases(full - ms, full + timedelta(days=1))] == ["Full Moon"]
        assert get_moon_phases(full - timedelta(days=1), full - ms) == []
        assert get_moon_phases(full + ms, full + timedelta(days=1)) == []

    def test_a_year_has_each_phase_twelve_or_thirteen_times(self):
        from collections import Counter
        from wherewhen.temporal import get_moon_phases
        phases = get_moon_phases(datetime(2026, 1, 1), datetime(2027, 1, 1))
        assert set(Counter(p["Phase"] for p in phases).values()) <= {12, 13}
        times = [p["Time"] for p in phases]
        assert times == sorted(times)

    def test_end_before_start_raises(self):
        from wherewhen.temporal import get_moon_phases
        with pytest.raises(ValueError, match=r"\[get_moon_phases\]"):
            get_moon_phases(datetime(2027, 1, 1), datetime(2026, 1, 1))


class TestSkyData:

    def test_parts_agree_with_the_functions_it_composes(self):
        from wherewhen.temporal import get_lunar_data, get_lunar_month, get_sky_data, get_solar_data
        pt, day = Point(49.6779, 34.0880), datetime(2026, 12, 21)
        sky = get_sky_data(pt, day)
        assert sky["Solar"] == get_solar_data(pt, day)
        assert sky["Lunar"] == get_lunar_data(pt, day)
        # Same instant, found from a different moment: ephem's floats differ by microseconds.
        assert abs(sky["Lunar Month"]["Full Moon"] - get_lunar_month(day)["Full Moon"]) < timedelta(milliseconds=1)
        assert str(sky["Lunar Month"]["Full Moon"].tzinfo) == "Asia/Tehran"

    def test_day_timeline_matches_the_events(self):
        from wherewhen.temporal import get_sky_data
        pt = Point(49.6779, 34.0880)
        sky = get_sky_data(pt, datetime(2026, 12, 21))
        times, alt, up = sky["Day"]["Times"], sky["Day"]["Sun Altitude (Degrees)"], sky["Day"]["Moon Up"]
        assert len(times) == len(alt) == len(up) == 288
        assert times[0].hour == 0 and str(times[0].tzinfo) == "Asia/Tehran"
        noon = times.index(min(times, key=lambda t: abs(t - sky["Solar"]["Solar Noon"])))
        assert alt[noon] == max(alt)
        # Moon down before moonrise (14:20) and up after it.
        rise = sky["Lunar"]["Moonrise"]
        before = max(i for i, t in enumerate(times) if t < rise)
        assert not up[before] and up[before + 1]

    def test_moons_are_centred_on_the_day(self):
        from wherewhen.temporal import get_night_moonlight, get_sky_data
        pt, day = Point(15.6, 78.2), datetime(2026, 12, 21)
        sky = get_sky_data(pt, day)
        moons = sky["Moons"]
        assert [m["Date"] for m in moons] == [day.date() + timedelta(days=k) for k in range(-14, 15)]
        assert "Month Moons" not in sky
        full = next(m for m in moons if m["Date"] == sky["Lunar Month"]["Full Moon"].date())
        assert full["Illumination (%)"] > 98
        assert all(sky["Day"]["Moon Up"])          # polar night, moon never sets
        for m in (moons[0], moons[14], moons[-1]):
            night = get_night_moonlight(pt, datetime(m["Date"].year, m["Date"].month, m["Date"].day))
            assert {k: m[k] for k in night if k in m} == {k: night[k] for k in night if k in m}
        assert moons[14]["Dark Sky (Hours)"] == 24.0   # polar night: dark from noon to noon

    def test_moon_phases_cover_the_moons_window_on_the_local_clock(self):
        from zoneinfo import ZoneInfo
        from wherewhen.temporal import get_moon_phases, get_sky_data
        sky = get_sky_data(Point(49.6779, 34.0880), datetime(2026, 12, 21))
        tehran = ZoneInfo("Asia/Tehran")
        first, last = sky["Moons"][0]["Date"], sky["Moons"][-1]["Date"]
        expected = get_moon_phases(datetime(first.year, first.month, first.day, tzinfo=tehran),
                                   datetime(last.year, last.month, last.day, tzinfo=tehran) + timedelta(days=1))
        assert [p["Phase"] for p in sky["Moon Phases"]] == [p["Phase"] for p in expected] == [
            "New Moon", "First Quarter", "Full Moon", "Last Quarter"]
        assert [p["Time"] for p in sky["Moon Phases"]] == [p["Time"] for p in expected]
        assert all(str(p["Time"].tzinfo) == "Asia/Tehran" for p in sky["Moon Phases"])

    def test_year_grid_shape_and_polar_seasons(self):
        from wherewhen.temporal import get_sky_data
        sky = get_sky_data(Point(15.6, 78.2), datetime(2026, 12, 21))
        year = sky["Year"]
        assert len(year["Hours"]) == 48 and len(year["Dates"]) == 183
        assert all(len(row) == 183 for row in year["Sun Altitude (Degrees)"])
        june = year["Dates"].index(next(d for d in year["Dates"] if d.month == 6 and d.day >= 20))
        assert min(row[june] for row in year["Sun Altitude (Degrees)"]) > 0      # polar day
        assert max(row[-6] for row in year["Sun Altitude (Degrees)"]) < -0.833   # polar night

    def test_clock_change_days_are_23_and_25_hours(self):
        # London: clocks go forward on 29 Mar 2026 and back on 25 Oct 2026.
        from wherewhen.temporal import get_sky_data
        for day, hours in ((datetime(2026, 3, 29), 23), (datetime(2026, 10, 25), 25), (datetime(2026, 6, 21), 24)):
            times = get_sky_data(LONDON_PT, day)["Day"]["Times"]
            utc = [t.astimezone(timezone.utc) for t in times]
            assert len(times) == hours * 12
            assert len(set(utc)) == len(utc)
            assert all(b - a == timedelta(minutes=5) for a, b in zip(utc, utc[1:]))
            assert times[0].hour == 0 and times[0].minute == 0
            assert (times[-1] + timedelta(minutes=5)).astimezone(timezone.utc) == \
                datetime(day.year, day.month, day.day + 1, tzinfo=times[0].tzinfo).astimezone(timezone.utc)
