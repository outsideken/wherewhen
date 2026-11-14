"""
Tests for wherewhen.temporal — datetime, timezone, and solar/lunar utilities.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

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
