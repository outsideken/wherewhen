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

    def test_same_crs_raises(self):
        from wherewhen.crs import convert_crs
        with pytest.raises((ValueError, KeyError), match="⚠️"):
            convert_crs(LONDON_PT, "WGS84", "WGS84")

    def test_unknown_crs_raises(self):
        from wherewhen.crs import convert_crs
        with pytest.raises((ValueError, KeyError), match="⚠️"):
            convert_crs(LONDON_PT, "WGS84", "UNKNOWN_CRS")

    def test_non_point_raises(self):
        from wherewhen.crs import convert_crs
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            convert_crs((51.5, -0.1), "WGS84", "GCJ02")