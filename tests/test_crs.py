"""
Tests for wherewhen.crs — coordinate reference system transforms.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Point

from tests.conftest import BEIJING_PT, LONDON_PT, MOSCOW_PT

_TOL = 0.0001


class TestGcj02:

    def test_wgs84_to_gcj02_returns_point(self):
        from wherewhen.crs import wgs84_to_cn_gcj02
        assert isinstance(wgs84_to_cn_gcj02(BEIJING_PT), Point)

    def test_wgs84_to_gcj02_moves_point(self):
        from wherewhen.crs import wgs84_to_cn_gcj02
        shifted = wgs84_to_cn_gcj02(BEIJING_PT)
        assert shifted.x != BEIJING_PT.x or shifted.y != BEIJING_PT.y

    def test_gcj02_roundtrip(self):
        from wherewhen.crs import cn_gcj02_to_wgs84, wgs84_to_cn_gcj02
        shifted = wgs84_to_cn_gcj02(BEIJING_PT)
        recovered = cn_gcj02_to_wgs84(shifted)
        assert abs(recovered.x - BEIJING_PT.x) < _TOL
        assert abs(recovered.y - BEIJING_PT.y) < _TOL

    def test_non_point_raises(self):
        from wherewhen.crs import wgs84_to_cn_gcj02
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            wgs84_to_cn_gcj02((39.9, 116.4))

    def test_outside_china_returns_unchanged(self):
        from wherewhen.crs import wgs84_to_cn_gcj02
        result = wgs84_to_cn_gcj02(LONDON_PT)
        assert abs(result.x - LONDON_PT.x) < _TOL
        assert abs(result.y - LONDON_PT.y) < _TOL


class TestBd09:

    def test_wgs84_to_bd09_returns_point(self):
        from wherewhen.crs import wgs84_to_cn_bd09
        assert isinstance(wgs84_to_cn_bd09(BEIJING_PT), Point)

    def test_wgs84_to_bd09_moves_point(self):
        from wherewhen.crs import wgs84_to_cn_bd09
        shifted = wgs84_to_cn_bd09(BEIJING_PT)
        assert shifted.x != BEIJING_PT.x or shifted.y != BEIJING_PT.y

    def test_bd09_roundtrip(self):
        from wherewhen.crs import cn_bd09_to_wgs84, wgs84_to_cn_bd09
        shifted = wgs84_to_cn_bd09(BEIJING_PT)
        recovered = cn_bd09_to_wgs84(shifted)
        assert abs(recovered.x - BEIJING_PT.x) < _TOL
        assert abs(recovered.y - BEIJING_PT.y) < _TOL

    def test_non_point_raises(self):
        from wherewhen.crs import wgs84_to_cn_bd09
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            wgs84_to_cn_bd09((39.9, 116.4))


class TestSk42:

    def test_wgs84_to_sk42_returns_point(self):
        from wherewhen.crs import wgs84_to_ru_sk42
        assert isinstance(wgs84_to_ru_sk42(MOSCOW_PT), Point)

    def test_wgs84_to_sk42_moves_point(self):
        from wherewhen.crs import wgs84_to_ru_sk42
        shifted = wgs84_to_ru_sk42(MOSCOW_PT)
        assert shifted.x != MOSCOW_PT.x or shifted.y != MOSCOW_PT.y

    def test_sk42_roundtrip(self):
        from wherewhen.crs import ru_sk42_to_wgs84, wgs84_to_ru_sk42
        shifted = wgs84_to_ru_sk42(MOSCOW_PT)
        recovered = ru_sk42_to_wgs84(shifted)
        assert abs(recovered.x - MOSCOW_PT.x) < _TOL
        assert abs(recovered.y - MOSCOW_PT.y) < _TOL

    def test_non_point_raises(self):
        from wherewhen.crs import wgs84_to_ru_sk42
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            wgs84_to_ru_sk42((55.75, 37.62))


class TestConvertCrs:

    def test_wgs84_to_gcj02_via_dispatcher(self):
        from wherewhen.crs import convert_crs, wgs84_to_cn_gcj02
        result = convert_crs(BEIJING_PT, "WGS84", "GCJ02")
        expected = wgs84_to_cn_gcj02(BEIJING_PT)
        assert abs(result.x - expected.x) < 1e-9

    def test_gcj02_to_wgs84_via_dispatcher(self):
        from wherewhen.crs import convert_crs, wgs84_to_cn_gcj02
        gcj = wgs84_to_cn_gcj02(BEIJING_PT)
        result = convert_crs(gcj, "GCJ02", "WGS84")
        assert abs(result.x - BEIJING_PT.x) < _TOL

    def test_wgs84_to_bd09_via_dispatcher(self):
        from wherewhen.crs import convert_crs, wgs84_to_cn_bd09
        result = convert_crs(BEIJING_PT, "WGS84", "BD09")
        expected = wgs84_to_cn_bd09(BEIJING_PT)
        assert abs(result.x - expected.x) < 1e-9

    def test_wgs84_to_sk42_via_dispatcher(self):
        from wherewhen.crs import convert_crs, wgs84_to_ru_sk42
        result = convert_crs(MOSCOW_PT, "WGS84", "SK42")
        expected = wgs84_to_ru_sk42(MOSCOW_PT)
        assert abs(result.x - expected.x) < 1e-9

    @pytest.mark.parametrize("crs", ["WGS84", "GCJ02", "BD09", "SK42", "bd09", "Gcj02"])
    def test_same_crs_returns_the_point_unchanged(self, crs):
        # Was "Unsupported CRS conversion" (#31).
        from wherewhen.crs import convert_crs
        assert convert_crs(BEIJING_PT, crs, crs.upper()) is BEIJING_PT

    def test_gcj02_to_bd09_goes_through_wgs84(self):
        from wherewhen.crs import cn_gcj02_to_wgs84, convert_crs, wgs84_to_cn_bd09, wgs84_to_cn_gcj02
        gcj = wgs84_to_cn_gcj02(BEIJING_PT)
        result = convert_crs(gcj, "GCJ02", "BD09")
        assert result.equals(wgs84_to_cn_bd09(cn_gcj02_to_wgs84(gcj)))
        # and lands where BD-09 of the original WGS-84 point is (GCJ-02's
        # inverse iterates to well under a millimetre)
        assert abs(result.x - wgs84_to_cn_bd09(BEIJING_PT).x) < 1e-8
        assert abs(result.y - wgs84_to_cn_bd09(BEIJING_PT).y) < 1e-8

    def test_bd09_to_gcj02_goes_through_wgs84(self):
        from wherewhen.crs import cn_bd09_to_wgs84, convert_crs, wgs84_to_cn_bd09, wgs84_to_cn_gcj02
        bd = wgs84_to_cn_bd09(BEIJING_PT)
        result = convert_crs(bd, "BD09", "GCJ02")
        assert result.equals(wgs84_to_cn_gcj02(cn_bd09_to_wgs84(bd)))
        assert abs(result.x - wgs84_to_cn_gcj02(BEIJING_PT).x) < _TOL

    @pytest.mark.parametrize("source, target", [
        (a, b) for a in ("WGS84", "GCJ02", "BD09", "SK42")
        for b in ("WGS84", "GCJ02", "BD09", "SK42") if a != b
    ])
    def test_every_pair_converts_and_comes_back(self, source, target):
        from wherewhen.crs import convert_crs
        there = convert_crs(BEIJING_PT, source, target)
        back = convert_crs(there, target, source)
        assert abs(back.x - BEIJING_PT.x) < _TOL and abs(back.y - BEIJING_PT.y) < _TOL

    @pytest.mark.parametrize("source, target, bad", [
        ("WGS84", "EPSG:4326", "EPSG:4326"),
        ("UNKNOWN_CRS", "WGS84", "UNKNOWN_CRS"),
    ])
    def test_unsupported_crs_is_named_with_the_supported_list(self, source, target, bad):
        from wherewhen.crs import convert_crs
        with pytest.raises(ValueError, match=rf"^⚠️ \[convert_crs\] Unsupported CRS '{bad}'\. Supported: WGS84, GCJ02, BD09, SK42"):
            convert_crs(LONDON_PT, source, target)

    def test_non_point_raises(self):
        from wherewhen.crs import convert_crs
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            convert_crs((51.5, -0.1), "WGS84", "GCJ02")

# ── Region where GCJ-02 and BD-09 apply (#33) ──────────────────────────────────

_INSIDE = {
    "Beijing": (116.3912, 39.9073), "Shanghai": (121.4737, 31.2304),
    "Urumqi": (87.6168, 43.8256), "Kashgar": (75.9898, 39.4704),
    "Harbin": (126.535, 45.8038), "Sanya": (109.5119, 18.2528),
    "Lhasa": (91.1172, 29.6475), "Hong Kong": (114.1694, 22.3193),
    "Victoria Harbour": (114.17, 22.29), "Macau": (113.5439, 22.1987),
    "Off Shanghai": (122.0, 31.0), "Hekou": (103.9393, 22.5296),
    "Dandong": (124.3545, 40.0002),
}
# Taipei, Seoul, Hanoi and Ulaanbaatar were offset by the old rectangle.
_OUTSIDE = {
    "Taipei": (121.5654, 25.033), "Kinmen": (118.3171, 24.4321),
    "Seoul": (126.978, 37.5665), "Pyongyang": (125.7625, 39.0392),
    "Sinuiju": (124.398, 40.1), "Hanoi": (105.8342, 21.0278),
    "Lao Cai": (103.97, 22.49), "Ulaanbaatar": (106.9057, 47.8864),
    "Bangkok": (100.5018, 13.7563), "Vladivostok": (131.8869, 43.1155),
    "Moscow": (37.6173, 55.7558), "London": (-0.1278, 51.5074),
}
_FORWARD = ("wgs84_to_cn_gcj02", "wgs84_to_cn_bd09")
_PAIRS = (("wgs84_to_cn_gcj02", "cn_gcj02_to_wgs84"), ("wgs84_to_cn_bd09", "cn_bd09_to_wgs84"))
# Baidu's published inverse is about 0.2 m off; GCJ-02's iterates to well under 1 mm.
_BACK_TOL = 1e-5


def _crs(name):
    import wherewhen.crs
    return getattr(wherewhen.crs, name)


class TestChinaRegion:

    @pytest.mark.parametrize("name", sorted(_INSIDE))
    @pytest.mark.parametrize("forward", _FORWARD)
    def test_inside_is_offset(self, name, forward):
        pt = Point(*_INSIDE[name])
        shifted = _crs(forward)(pt)
        assert abs(shifted.x - pt.x) > 0.001 or abs(shifted.y - pt.y) > 0.001

    @pytest.mark.parametrize("name", sorted(_OUTSIDE))
    @pytest.mark.parametrize("func", [f for pair in _PAIRS for f in pair])
    def test_outside_is_returned_unchanged(self, name, func):
        pt = Point(*_OUTSIDE[name])
        assert _crs(func)(pt) is pt

    def test_bd09_no_longer_moves_moscow(self):
        # Was 775 m: Baidu's offset was added everywhere.
        from wherewhen.crs import convert_crs
        moscow = Point(*_OUTSIDE["Moscow"])
        assert convert_crs(moscow, "WGS84", "BD09") is moscow

    @pytest.mark.parametrize("name", sorted(_INSIDE))
    @pytest.mark.parametrize("forward, reverse", _PAIRS)
    def test_inside_round_trips(self, name, forward, reverse):
        pt = Point(*_INSIDE[name])
        back = _crs(reverse)(_crs(forward)(pt))
        assert abs(back.x - pt.x) < _BACK_TOL and abs(back.y - pt.y) < _BACK_TOL

    @pytest.mark.parametrize("forward, reverse", _PAIRS)
    def test_every_inside_point_on_a_grid_round_trips(self, forward, reverse):
        # The reverse decides on its WGS-84 result, so nothing the forward
        # conversion offset is left offset on the way back.
        from wherewhen.crs import _in_china
        fwd, rev = _crs(forward), _crs(reverse)
        checked = 0
        for i in range(73 * 4, 136 * 4):
            for j in range(15 * 4, 54 * 4):
                lon, lat = i / 4, j / 4
                if not _in_china(lon, lat):
                    continue
                pt = Point(lon, lat)
                back = rev(fwd(pt))
                assert abs(back.x - lon) < _BACK_TOL and abs(back.y - lat) < _BACK_TOL, (lon, lat)
                checked += 1
        assert checked > 10000

    @pytest.mark.parametrize("name", ["Seoul", "Moscow", "London"])
    @pytest.mark.parametrize("forward, reverse", _PAIRS)
    def test_skip_region_check_offsets_anywhere_and_comes_back(self, name, forward, reverse):
        pt = Point(*_OUTSIDE[name])
        shifted = _crs(forward)(pt, skip_region_check=True)
        assert abs(shifted.x - pt.x) > 0.001 or abs(shifted.y - pt.y) > 0.001
        back = _crs(reverse)(shifted, skip_region_check=True)
        assert abs(back.x - pt.x) < _BACK_TOL and abs(back.y - pt.y) < _BACK_TOL

    @pytest.mark.parametrize("forward", _FORWARD)
    def test_skip_region_check_matches_inside(self, forward):
        pt = Point(*_INSIDE["Beijing"])
        assert _crs(forward)(pt, skip_region_check=True).equals(_crs(forward)(pt))

    @pytest.mark.parametrize("source, target", [("WGS84", "GCJ02"), ("WGS84", "BD09"), ("SK42", "BD09")])
    def test_convert_crs_passes_the_switch(self, source, target):
        from wherewhen.crs import convert_crs
        seoul = Point(*_OUTSIDE["Seoul"])
        if source == "WGS84":
            assert convert_crs(seoul, source, target) is seoul
        moved = convert_crs(seoul, source, target, skip_region_check=True)
        assert abs(moved.x - seoul.x) > 0.001 or abs(moved.y - seoul.y) > 0.001

    def test_convert_crs_switch_has_no_effect_on_sk42(self):
        from wherewhen.crs import convert_crs
        assert convert_crs(MOSCOW_PT, "WGS84", "SK42", skip_region_check=True).equals(
            convert_crs(MOSCOW_PT, "WGS84", "SK42")
        )

    @pytest.mark.parametrize("bad", [1, 0, None, "True"])
    @pytest.mark.parametrize("func", [f for pair in _PAIRS for f in pair])
    def test_non_bool_switch_raises(self, bad, func):
        with pytest.raises(TypeError, match=rf"^⚠️ \[{func}\] skip_region_check must be True or False, got "):
            _crs(func)(BEIJING_PT, skip_region_check=bad)

    def test_convert_crs_non_bool_switch_raises(self):
        from wherewhen.crs import convert_crs
        with pytest.raises(TypeError, match=r"^⚠️ \[convert_crs\] skip_region_check must be True or False, got int\."):
            convert_crs(BEIJING_PT, "WGS84", "GCJ02", skip_region_check=1)

    def test_region_module_matches_its_source(self):
        # Built by scripts/build_china_region.py; a valid shape around China only.
        from shapely import wkt
        from wherewhen._china_region import CHINA_REGION_WKT
        region = wkt.loads(CHINA_REGION_WKT)
        assert region.is_valid
        minx, miny, maxx, maxy = region.bounds
        assert 73 < minx < 74 and 15 < miny < 16 and 134 < maxx < 135.5 and 53 < maxy < 54

    @pytest.mark.parametrize("func", ["wgs84_to_cn_bd09", "convert_crs"])
    def test_switch_result_outside_wgs84_bounds_raises(self, func):
        # Baidu's +0.0065° pushes lon 180 past the bound.
        args = (Point(180, 0), "WGS84", "BD09") if func == "convert_crs" else (Point(180, 0),)
        with pytest.raises(ValueError, match=rf"^⚠️ \[{func}\]"):
            _crs(func)(*args, skip_region_check=True)
