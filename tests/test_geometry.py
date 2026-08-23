"""
Tests for wherewhen.geometry — coordinate conversion and bounding-box utilities.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from tests.conftest import LONDON_LAT, LONDON_LON, LONDON_PT


class TestLatLonToPoint:

    def test_returns_point(self):
        from wherewhen.geometry import latlon_to_point
        assert isinstance(latlon_to_point((LONDON_LAT, LONDON_LON)), Point)

    def test_coordinates_correct(self):
        from wherewhen.geometry import latlon_to_point
        pt = latlon_to_point((LONDON_LAT, LONDON_LON))
        assert pt.x == pytest.approx(LONDON_LON, abs=1e-6)
        assert pt.y == pytest.approx(LONDON_LAT, abs=1e-6)

    def test_invalid_latitude_raises(self):
        from wherewhen.geometry import latlon_to_point
        with pytest.raises(ValueError, match="⚠️"):
            latlon_to_point((91.0, 0.0))

    def test_invalid_longitude_raises(self):
        from wherewhen.geometry import latlon_to_point
        with pytest.raises(ValueError, match="⚠️"):
            latlon_to_point((0.0, 181.0))

    def test_non_sequence_raises(self):
        from wherewhen.geometry import latlon_to_point
        with pytest.raises((TypeError, ValueError)):
            latlon_to_point("51.5, -0.1")


class TestMgrsToPoint:

    LONDON_MGRS = "30UXC9878011841"

    def test_returns_point(self):
        from wherewhen.geometry import mgrs_to_point
        assert isinstance(mgrs_to_point(self.LONDON_MGRS), Point)

    def test_coordinates_near_london(self):
        from wherewhen.geometry import mgrs_to_point
        pt = mgrs_to_point(self.LONDON_MGRS)
        assert abs(pt.x - LONDON_LON) < 0.05
        assert abs(pt.y - LONDON_LAT) < 0.05

    def test_invalid_mgrs_raises(self):
        from wherewhen.geometry import mgrs_to_point
        with pytest.raises((ValueError, Exception), match="⚠️"):
            mgrs_to_point("NOT_MGRS")

    def test_non_string_raises(self):
        from wherewhen.geometry import mgrs_to_point
        with pytest.raises(TypeError, match="⚠️"):
            mgrs_to_point(12345)


class TestDmsToPoint:

    LONDON_DMS = '51°30\'26"N 0°7\'40"W'

    def test_returns_point(self):
        from wherewhen.geometry import dms_to_point
        assert isinstance(dms_to_point(self.LONDON_DMS), Point)

    def test_coordinates_near_london(self):
        from wherewhen.geometry import dms_to_point
        pt = dms_to_point(self.LONDON_DMS)
        assert abs(pt.y - LONDON_LAT) < 0.05
        assert abs(pt.x - LONDON_LON) < 0.05

    def test_southern_hemisphere(self):
        from wherewhen.geometry import dms_to_point
        pt = dms_to_point('1°17\'32"S 36°49\'19"E')
        assert pt.y < 0

    def test_western_hemisphere(self):
        from wherewhen.geometry import dms_to_point
        pt = dms_to_point('40°42\'46"N 74°0\'21"W')
        assert pt.x < 0

    def test_invalid_string_raises(self):
        from wherewhen.geometry import dms_to_point
        with pytest.raises((ValueError, Exception)):
            dms_to_point("not coordinates")

    def test_non_string_raises(self):
        from wherewhen.geometry import dms_to_point
        with pytest.raises(TypeError, match="⚠️"):
            dms_to_point(51.5074)


class TestDdmToPoint:

    LONDON_DDM = "51°30.440'N 0°07.667'W"

    def test_returns_point(self):
        from wherewhen.geometry import ddm_to_point
        assert isinstance(ddm_to_point(self.LONDON_DDM), Point)

    def test_coordinates_near_london(self):
        from wherewhen.geometry import ddm_to_point
        pt = ddm_to_point(self.LONDON_DDM)
        assert abs(pt.y - LONDON_LAT) < 0.05
        assert abs(pt.x - LONDON_LON) < 0.05

    def test_invalid_string_raises(self):
        from wherewhen.geometry import ddm_to_point
        with pytest.raises((ValueError, Exception)):
            ddm_to_point("not ddm")

    def test_non_string_raises(self):
        from wherewhen.geometry import ddm_to_point
        with pytest.raises(TypeError, match="⚠️"):
            ddm_to_point(51.5)


class TestCoordinateToPoint:

    def test_latlon_tuple(self):
        from wherewhen.geometry import coordinate_to_point
        pt = coordinate_to_point((LONDON_LAT, LONDON_LON))
        assert isinstance(pt, Point)

    def test_dms_string(self):
        from wherewhen.geometry import coordinate_to_point
        pt = coordinate_to_point('51°30\'26"N 0°7\'40"W')
        assert abs(pt.y - LONDON_LAT) < 0.05

    def test_unsupported_type_raises(self):
        from wherewhen.geometry import coordinate_to_point
        with pytest.raises((TypeError, ValueError), match="⚠️"):
            coordinate_to_point(12345)

    def test_point_object_raises(self):
        from wherewhen.geometry import coordinate_to_point
        with pytest.raises(TypeError, match="⚠️"):
            coordinate_to_point(LONDON_PT)


class TestPointToLatlon:

    def test_round_trip(self):
        from wherewhen.geometry import latlon_to_point, point_to_latlon
        latlon = (LONDON_LAT, LONDON_LON)
        assert point_to_latlon(latlon_to_point(latlon)) == pytest.approx(latlon)

    def test_returns_tuple(self):
        from wherewhen.geometry import point_to_latlon
        result = point_to_latlon(LONDON_PT)
        assert isinstance(result, tuple)
        assert result[0] == pytest.approx(LONDON_LAT, abs=1e-6)
        assert result[1] == pytest.approx(LONDON_LON, abs=1e-6)

    def test_invalid_point_raises(self):
        from wherewhen.geometry import point_to_latlon
        with pytest.raises(ValueError, match="⚠️"):
            point_to_latlon(Point(0.0, 91.0))


class TestNormalizeLongitude:

    def test_wraps_positive_overflow(self):
        from wherewhen.geometry import normalize_longitude
        assert normalize_longitude(190) == pytest.approx(-170.0)

    def test_wraps_negative_overflow(self):
        from wherewhen.geometry import normalize_longitude
        assert normalize_longitude(-190) == pytest.approx(170.0)

    def test_zero_to_three_sixty_range(self):
        from wherewhen.geometry import normalize_longitude
        assert normalize_longitude(-170, lon_range="[0,360)") == pytest.approx(190.0)
        assert normalize_longitude(370, lon_range="[0,360)") == pytest.approx(10.0)

    def test_non_numeric_raises(self):
        from wherewhen.geometry import normalize_longitude
        with pytest.raises(TypeError, match="⚠️"):
            normalize_longitude("not a number")


class TestNormalizeLatlon:

    def test_unchanged_in_range(self):
        from wherewhen.geometry import normalize_latlon
        assert normalize_latlon(51.5, -0.1) == pytest.approx((51.5, -0.1))

    def test_north_pole_crossing(self):
        from wherewhen.geometry import normalize_latlon
        assert normalize_latlon(95, 10) == pytest.approx((85.0, -170.0))

    def test_south_pole_crossing(self):
        from wherewhen.geometry import normalize_latlon
        assert normalize_latlon(-95, 10) == pytest.approx((-85.0, -170.0))

    def test_longitude_only_wrap(self):
        from wherewhen.geometry import normalize_latlon
        assert normalize_latlon(45, 190) == pytest.approx((45.0, -170.0))

    def test_multiple_pole_crossings(self):
        from wherewhen.geometry import normalize_latlon
        lat, lon = normalize_latlon(185, 0)
        assert lat == pytest.approx(-5.0)
        assert lon == pytest.approx(-180.0)

    def test_pole_endpoint_preserves_longitude(self):
        from wherewhen.geometry import normalize_latlon
        assert normalize_latlon(90, 45) == pytest.approx((90.0, 45.0))


class TestSegmentCrossesAntimeridian:

    def test_same_hemisphere(self):
        from wherewhen.geometry import segment_crosses_antimeridian
        assert segment_crosses_antimeridian(10, 20) is False

    def test_near_antimeridian_short_arc(self):
        from wherewhen.geometry import segment_crosses_antimeridian
        assert segment_crosses_antimeridian(179, -179) is True

    def test_wide_pacific_crossing(self):
        from wherewhen.geometry import segment_crosses_antimeridian
        assert segment_crosses_antimeridian(170, -170) is True


class TestPointDistance:

    def test_zero_for_same_point(self):
        from wherewhen.geometry import point_distance
        assert point_distance(LONDON_PT, LONDON_PT) == pytest.approx(0.0)

    def test_london_to_paris_km(self):
        from wherewhen.geometry import point_distance
        paris = Point(2.3522, 48.8566)
        dist = point_distance(LONDON_PT, paris)
        assert 300 < dist < 400

    def test_antimeridian_short_arc_km(self):
        from wherewhen.geometry import point_distance
        west = Point(179.0, 0.0)
        east = Point(-179.0, 0.0)
        dist = point_distance(west, east, units="km")
        assert dist == pytest.approx(222.4, rel=0.01)

    def test_metres_via_unit_dict(self):
        from wherewhen.geometry import METRES_PER_UNIT, point_distance
        paris = Point(2.3522, 48.8566)
        km = point_distance(LONDON_PT, paris, units="km")
        metres = point_distance(LONDON_PT, paris, units="m")
        assert metres == pytest.approx(km * METRES_PER_UNIT["km"])

    def test_nautical_miles(self):
        from wherewhen.geometry import METRES_PER_UNIT, point_distance
        paris = Point(2.3522, 48.8566)
        km = point_distance(LONDON_PT, paris, units="km")
        nm = point_distance(LONDON_PT, paris, units="nm")
        assert nm == pytest.approx(km * METRES_PER_UNIT["km"] / METRES_PER_UNIT["nm"])

    def test_invalid_unit_raises(self):
        from wherewhen.geometry import point_distance
        with pytest.raises(ValueError, match="⚠️"):
            point_distance(LONDON_PT, LONDON_PT, units="ft")

    def test_non_point_raises(self):
        from wherewhen.geometry import point_distance
        with pytest.raises(TypeError, match="⚠️"):
            point_distance("not a point", LONDON_PT)


class TestPointBearing:

    def test_london_to_paris_southeast(self):
        from wherewhen.geometry import point_bearing
        paris = Point(2.3522, 48.8566)
        assert 140 < point_bearing(LONDON_PT, paris) < 170

    def test_due_east_at_equator(self):
        from wherewhen.geometry import point_bearing
        assert point_bearing(Point(0, 0), Point(1, 0)) == pytest.approx(90.0)

    def test_due_north(self):
        from wherewhen.geometry import point_bearing
        assert point_bearing(Point(0, 0), Point(0, 1)) == pytest.approx(0.0)

    def test_same_point_raises(self):
        from wherewhen.geometry import point_bearing
        with pytest.raises(ValueError, match="⚠️"):
            point_bearing(LONDON_PT, LONDON_PT)

    def test_antimeridian_short_path(self):
        from wherewhen.geometry import point_bearing
        west = Point(179.0, 0.0)
        east = Point(-179.0, 0.0)
        assert point_bearing(west, east) == pytest.approx(90.0, abs=0.5)


class TestPointAtDistance:

    def test_zero_distance_returns_origin(self):
        from wherewhen.geometry import point_at_distance
        origin = Point(0, 0)
        assert point_at_distance(origin, 0, 90) == origin

    def test_round_trip_distance(self):
        from wherewhen.geometry import point_at_distance, point_distance
        origin = Point(-0.1278, 51.5074)
        dest = point_at_distance(origin, 5.0, 45.0, units="km")
        assert point_distance(origin, dest, units="km") == pytest.approx(5.0, rel=1e-3)

    def test_due_east_at_equator(self):
        from wherewhen.geometry import point_at_distance
        dest = point_at_distance(Point(0, 0), 111.32, 90, units="km")
        assert dest.x == pytest.approx(1.0, abs=0.05)
        assert dest.y == pytest.approx(0.0, abs=0.05)

    def test_negative_distance_raises(self):
        from wherewhen.geometry import point_at_distance
        with pytest.raises(ValueError, match="⚠️"):
            point_at_distance(Point(0, 0), -1.0, 0)

    def test_invalid_units_raises(self):
        from wherewhen.geometry import point_at_distance
        with pytest.raises(ValueError, match="⚠️"):
            point_at_distance(Point(0, 0), 1.0, 0, units="ft")


class TestSphericalWeightedCentroid:

    def test_single_point(self):
        from wherewhen.geometry import spherical_weighted_centroid
        pt = Point(-0.1278, 51.5074)
        result = spherical_weighted_centroid([pt], [5.0])
        assert result.x == pytest.approx(pt.x, abs=1e-9)
        assert result.y == pytest.approx(pt.y, abs=1e-9)

    def test_two_point_midpoint(self):
        from wherewhen.geometry import spherical_weighted_centroid
        a = Point(0, 0)
        b = Point(2, 0)
        c = spherical_weighted_centroid([a, b], [1.0, 1.0])
        assert c.y == pytest.approx(0.0, abs=1e-9)
        assert c.x == pytest.approx(1.0, abs=0.01)

    def test_antimeridian_not_euclidean_mean(self):
        from wherewhen.geometry import spherical_weighted_centroid
        west = Point(179.0, 0.0)
        east = Point(-179.0, 0.0)
        c = spherical_weighted_centroid([west, east], [1.0, 1.0])
        assert c.y == pytest.approx(0.0, abs=1e-6)
        assert abs(abs(c.x) - 180.0) < 1.0

    def test_zero_total_weight_raises(self):
        from wherewhen.geometry import spherical_weighted_centroid
        with pytest.raises(ValueError, match="⚠️"):
            spherical_weighted_centroid([Point(0, 0)], [0.0])

    def test_length_mismatch_raises(self):
        from wherewhen.geometry import spherical_weighted_centroid
        with pytest.raises(ValueError, match="⚠️"):
            spherical_weighted_centroid([Point(0, 0), Point(1, 0)], [1.0])


class TestPointDistanceKm:

    def test_matches_point_distance(self):
        from wherewhen.geometry import point_distance, point_distance_km
        paris = Point(2.3522, 48.8566)
        assert point_distance_km(LONDON_PT, paris) == pytest.approx(
            point_distance(LONDON_PT, paris, units="km")
        )


class TestBoxToPolygon:

    BOX_STR = "BOX(-0.14 51.49, -0.11 51.52)"

    def test_returns_polygon(self):
        from wherewhen.geometry import box_to_polygon
        assert isinstance(box_to_polygon(self.BOX_STR), Polygon)

    def test_bounds_match(self):
        from wherewhen.geometry import box_to_polygon
        poly = box_to_polygon(self.BOX_STR)
        assert poly.bounds == pytest.approx((-0.14, 51.49, -0.11, 51.52))

    def test_round_trip_with_geometry_to_box(self):
        from wherewhen.geometry import box_to_polygon, geometry_to_box
        poly = Polygon([(-0.14, 51.49), (-0.11, 51.49), (-0.11, 51.52), (-0.14, 51.52)])
        box_str = geometry_to_box(poly)
        restored = box_to_polygon(box_str)
        assert restored.bounds == pytest.approx(poly.bounds)

    def test_invalid_string_raises(self):
        from wherewhen.geometry import box_to_polygon
        with pytest.raises(ValueError, match="⚠️"):
            box_to_polygon("not a box")

    def test_non_string_raises(self):
        from wherewhen.geometry import box_to_polygon
        with pytest.raises(TypeError, match="⚠️"):
            box_to_polygon(12345)


class TestGeometryToBox:

    POLY = Polygon([(-0.14, 51.49), (-0.11, 51.49), (-0.11, 51.52), (-0.14, 51.52)])

    def test_default_returns_box_string(self):
        from wherewhen.geometry import geometry_to_box
        result = geometry_to_box(self.POLY)
        assert isinstance(result, str)
        assert result.startswith("BOX(")

    def test_envelope_polygon_bounds_match(self):
        from wherewhen.geometry import geometry_to_box
        envelope = geometry_to_box(self.POLY, as_polygon=True)
        assert isinstance(envelope, Polygon)
        assert envelope.bounds == pytest.approx(self.POLY.bounds)

    def test_as_polygon_true_returns_polygon(self):
        from wherewhen.geometry import geometry_to_box
        result = geometry_to_box(self.POLY, as_polygon=True)
        assert isinstance(result, Polygon)

    def test_linestring_geometry(self):
        from wherewhen.geometry import geometry_to_box
        ls = LineString([(-0.14, 51.49), (-0.11, 51.52)])
        result = geometry_to_box(ls)
        assert isinstance(result, str) and result.startswith("BOX(")

    def test_multipolygon_geometry(self):
        from wherewhen.geometry import geometry_to_box
        p1 = Polygon([(-0.14, 51.49), (-0.11, 51.49), (-0.11, 51.52), (-0.14, 51.52)])
        p2 = Polygon([(2.78, 48.86), (2.80, 48.86), (2.80, 48.88), (2.78, 48.88)])
        mp = MultiPolygon([p1, p2])
        result = geometry_to_box(mp)
        assert isinstance(result, str) and result.startswith("BOX(")

    def test_point_geometry_raises(self):
        from wherewhen.geometry import geometry_to_box
        with pytest.raises(ValueError, match="⚠️"):
            geometry_to_box(LONDON_PT)

    def test_non_geometry_raises(self):
        from wherewhen.geometry import geometry_to_box
        with pytest.raises(TypeError, match="⚠️"):
            geometry_to_box("POLYGON(...)")

    def test_non_bool_as_polygon_raises(self):
        from wherewhen.geometry import geometry_to_box
        with pytest.raises(TypeError, match="⚠️"):
            geometry_to_box(self.POLY, as_polygon=1)