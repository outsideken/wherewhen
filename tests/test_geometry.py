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
        with pytest.raises(TypeError):
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


class TestDmsDdmParsing:
    """Each part is read whole: no silent misreads of degrees, minutes or seconds."""

    @pytest.mark.parametrize("text, lat, lon", [
        ('90°0\'0" N 0°0\'0" E', 90.0, 0.0),             # North Pole was read as 0
        ('90°0\'0" S 180°0\'0" W', -90.0, -180.0),
        ('51°30\'26.5"N 0°7\'40.25"W', 51 + 30 / 60 + 26.5 / 3600, -(7 / 60 + 40.25 / 3600)),
        ("51 30 26 N 0 7 40 W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),
        ("51:30:26N 000:07:40W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),
        ("513026N 0000740W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),   # packed DDMMSS / DDDMMSS
        ("513026N0000740W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),
        ("5130N 00007W", 51.5, -7 / 60),                    # packed DDMM / DDDMM
        ("51.5N 0.1W", 51.5, -0.1),                         # was read as 51°5'
        ("51°30.5'N 0°7.5'W", 51 + 30.5 / 60, -7.5 / 60),   # decimal minutes
        ('51°30\'26"N,0°7\'40"W', 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),  # comma separators
        ("51 30 26 N, 0 7 40 W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),
        ("51 30 26, N 0 7 40 W", 51 + 30 / 60 + 26 / 3600, -(7 / 60 + 40 / 3600)),
    ])
    def test_dms_reads_each_part_whole(self, text, lat, lon):
        from wherewhen.geometry import dms_to_point
        got_lat, got_lon = dms_to_point(text, return_latlon=True)
        assert got_lat == pytest.approx(lat)
        assert got_lon == pytest.approx(lon)

    @pytest.mark.parametrize("text, lat, lon", [
        ("51°30.440'N 0°07.667'W", 51 + 30.44 / 60, -7.667 / 60),
        ("51 30 N 0 7 W", 51.5, -7 / 60),
        ("90°0.0'N 0°0.0'E", 90.0, 0.0),
        ("5130.440N 00007.667W", 51 + 30.44 / 60, -7.667 / 60),   # packed DDMM.mmm / DDDMM.mmm
    ])
    def test_ddm_reads_each_part_whole(self, text, lat, lon):
        from wherewhen.geometry import ddm_to_point
        got_lat, got_lon = ddm_to_point(text, return_latlon=True)
        assert got_lat == pytest.approx(lat)
        assert got_lon == pytest.approx(lon)

    @pytest.mark.parametrize("text, message", [
        ('95°0\'0" N 0°0\'0" E', "Latitude must be in"),     # was read as 5
        ('90°0\'1" N 0°0\'0" E', "Latitude must be in"),
        ('89°59\'60" N 0°0\'0" E', "seconds must be in"),     # was read as 59.1
        ('51°75\'0" N 0°0\'0" E', "minutes must be in"),      # was read as 75
        ('51.5°30\'0" N 0°0\'0" E', "only the last part"),
        ('0°0\'0" N 181°0\'0" E', "Longitude must be in"),
        ('180°0\'0" E 0°0\'0" N', "Expected 1-3 numbers"),    # longitude first
        ("N51 30 26 W0 7 40", "Expected 1-3 numbers"),        # hemisphere first
        ("1 2 3 4 N 0 W", "Expected 1-3 numbers"),
        ("513N 0W", "Latitude must be in"),                   # 3 digits is not a packed latitude
        (".5N 0.25W", "Can't read '.5'"),                     # was read as 5
        ("0,5N 0W", "Can't read '0,5'"),                      # was read as 0°5'
        ("-51 30 N 0 7 W", "Can't read '-51'"),               # sign was dropped
        ("\u221251 30 N 0 7 W", "Can't read"),                # Unicode minus
        ("+51N 0W", "Can't read '\\+51'"),
        ("51 30. N 0 7 W", "Can't read '30.'"),
        ("1.2.3N 0W", "Can't read '1.2.3'"),
    ])
    def test_dms_rejects_what_it_used_to_misread(self, text, message):
        from wherewhen.geometry import dms_to_point
        with pytest.raises(ValueError, match=message):
            dms_to_point(text)

    @pytest.mark.parametrize("text, message", [
        ("51°75.0'N 0°7.0'W", "minutes must be in"),        # was read as 52.25
        ("51.5N 0.1W", "2 parts"),                          # was read as 51°5'
        ("51 30 26 N 0 7 40 W", "2 parts"),                 # that is DMS
        ("1234 30.0N 0 7W", "Latitude must be in"),
        ("51 0,5N 0 7W", "Can't read '0,5'"),
    ])
    def test_ddm_rejects_what_it_used_to_misread(self, text, message):
        from wherewhen.geometry import ddm_to_point
        with pytest.raises(ValueError, match=message):
            ddm_to_point(text)

    @pytest.mark.parametrize("lon, lat", [
        (-0.1277777, 51.4999999),      # seconds round to 60.00
        (-0.99999999, 10.0),           # minutes round to 60.000
        (-104.4499999, -65.1833333),
        (180.0, 90.0), (-180.0, -90.0), (0.0, 0.0),
    ])
    def test_formatters_carry_rounding_and_round_trip(self, lon, lat):
        from wherewhen.geometry import ddm_to_point, dms_to_point, point_to_ddm, point_to_dms
        pt = Point(lon, lat)
        dms = " ".join(point_to_dms(pt))
        ddm = " ".join(point_to_ddm(pt))
        assert '60.00"' not in dms and "60.000'" not in ddm
        for back in (dms_to_point(dms), ddm_to_point(ddm)):
            assert back.y == pytest.approx(lat, abs=1e-4)
            assert back.x == pytest.approx(lon, abs=1e-4)


class TestCoordinateBricks:

    def test_split_hemisphere_pair(self):
        from wherewhen.geometry import _split_hemisphere_pair
        assert _split_hemisphere_pair("51 30 26 N, 0 7 40 W", "f") == (
            (["51", "30", "26"], "N"), (["0", "7", "40"], "W"))

    @pytest.mark.parametrize("numbers, digits, expected", [
        (["513026"], 2, ["51", "30", "26"]),
        (["5130.44"], 2, ["51", "30.44"]),
        (["0000740"], 3, ["000", "07", "40"]),
        (["51.5"], 2, ["51.5"]),                 # plain degrees: unchanged
        (["51", "30"], 2, ["51", "30"]),         # already split: unchanged
        (["513"], 2, ["513"]),                   # not a packed width: unchanged
    ])
    def test_unpack_packed_group(self, numbers, digits, expected):
        from wherewhen.geometry import _unpack_packed_group
        assert _unpack_packed_group(numbers, digits) == expected

    @pytest.mark.parametrize("numbers, expected", [
        (["51"], 51.0), (["51", "30"], 51.5), (["51", "30", "36"], 51.51), (["51", "30.6"], 51.51),
    ])
    def test_sexagesimal_to_degrees(self, numbers, expected):
        from wherewhen.geometry import _sexagesimal_to_degrees
        assert _sexagesimal_to_degrees(numbers, "f", "Latitude") == pytest.approx(expected)

    @pytest.mark.parametrize("numbers", [[], ["1", "2", "3", "4"], ["51", "60"], ["51", "0", "60"], ["51.5", "30"]])
    def test_sexagesimal_to_degrees_rejects(self, numbers):
        from wherewhen.geometry import _sexagesimal_to_degrees
        with pytest.raises(ValueError, match=r"\[f\]"):
            _sexagesimal_to_degrees(numbers, "f", "Latitude")


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


# ── Single-member simplification ──────────────────────────────────────────────

from shapely import wkt as _wkt  # noqa: E402

from wherewhen._validators import _validate_geometry  # noqa: E402
from wherewhen.geometry import demote_single_multi, unwrap_single_collection  # noqa: E402


def _same(geom, text):
    """Same type and coordinates as *text*.  Compares geometries, not WKT text:
    older shapely (Python 3.9) writes MULTIPOINT (1 1) for MULTIPOINT ((1 1))."""
    expected = _wkt.loads(text)
    return geom.geom_type == expected.geom_type and geom.equals(expected)


class TestUnwrapSingleCollection:

    @pytest.mark.parametrize("text, expected", [
        ("GEOMETRYCOLLECTION (POINT (1 10))", "POINT (1 10)"),
        ("GEOMETRYCOLLECTION (LINESTRING (0 0, 1 1))", "LINESTRING (0 0, 1 1)"),
        ("GEOMETRYCOLLECTION (POLYGON ((0 0, 1 0, 1 1, 0 0)))", "POLYGON ((0 0, 1 0, 1 1, 0 0))"),
        ("GEOMETRYCOLLECTION (GEOMETRYCOLLECTION (POINT (1 10)))", "POINT (1 10)"),
        ("GEOMETRYCOLLECTION (MULTIPOINT ((1 1)))", "MULTIPOINT ((1 1))"),
    ])
    def test_one_member_is_unwrapped(self, text, expected):
        assert _same(unwrap_single_collection(_wkt.loads(text)), expected)

    @pytest.mark.parametrize("text", [
        "GEOMETRYCOLLECTION (POINT (1 10), POINT (2 3))",
        "GEOMETRYCOLLECTION (GEOMETRYCOLLECTION (POINT (1 10), POINT (2 3)))",
        "GEOMETRYCOLLECTION EMPTY",
        "MULTIPOINT ((1 1))",
        "POINT (5 5)",
    ])
    def test_anything_else_is_unchanged(self, text):
        geom = _wkt.loads(text)
        result = unwrap_single_collection(geom)
        if text.startswith("GEOMETRYCOLLECTION (GEOMETRYCOLLECTION"):
            # One wrapper removed: the inner collection has two members.
            assert _same(result, "GEOMETRYCOLLECTION (POINT (1 10), POINT (2 3))")
        else:
            assert result is geom

    def test_none_stays_none(self):
        assert unwrap_single_collection(None) is None

    def test_rejects_a_non_geometry(self):
        with pytest.raises(TypeError, match=r"\[unwrap_single_collection\]"):
            unwrap_single_collection("GEOMETRYCOLLECTION (POINT (1 10))")


class TestDemoteSingleMulti:

    @pytest.mark.parametrize("text, expected", [
        ("MULTIPOINT ((1 1))", "POINT (1 1)"),
        ("MULTILINESTRING ((0 0, 1 1))", "LINESTRING (0 0, 1 1)"),
        ("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)))", "POLYGON ((0 0, 1 0, 1 1, 0 0))"),
    ])
    def test_one_part_is_demoted(self, text, expected):
        assert _same(demote_single_multi(_wkt.loads(text)), expected)

    @pytest.mark.parametrize("text", [
        "MULTIPOINT ((1 1), (2 2))",
        "MULTIPOINT EMPTY",
        "GEOMETRYCOLLECTION (POINT (1 10))",
        "POLYGON ((0 0, 1 0, 1 1, 0 0))",
    ])
    def test_anything_else_is_unchanged(self, text):
        geom = _wkt.loads(text)
        assert demote_single_multi(geom) is geom

    def test_none_stays_none(self):
        assert demote_single_multi(None) is None

    def test_rejects_a_non_geometry(self):
        with pytest.raises(TypeError, match=r"\[demote_single_multi\]"):
            demote_single_multi(12345)


def test_bricks_compose_unwrap_first():
    geom = _wkt.loads("GEOMETRYCOLLECTION (MULTIPOINT ((1 1)))")
    assert _same(demote_single_multi(unwrap_single_collection(geom)), "POINT (1 1)")


def test_bricks_map_over_a_column():
    gpd = pytest.importorskip("geopandas")
    column = gpd.GeoSeries.from_wkt(
        ["GEOMETRYCOLLECTION (POINT (1 10))", None, "MULTIPOINT ((1 1))"]
    )
    out = column.map(unwrap_single_collection).map(demote_single_multi)
    assert _same(out.iloc[0], "POINT (1 10)")
    assert out.iloc[1] is None
    assert _same(out.iloc[2], "POINT (1 1)")


class TestValidateGeometry:

    @pytest.mark.parametrize("geom", [
        Point(0, 0), Polygon(), _wkt.loads("GEOMETRYCOLLECTION EMPTY"),
    ])
    def test_accepts_any_geometry_including_empty(self, geom):
        assert _validate_geometry(geom, func_name="caller") is None

    @pytest.mark.parametrize("value", [None, "POINT (0 0)", 1, (0, 0)])
    def test_rejects_anything_else_naming_the_caller(self, value):
        with pytest.raises(TypeError, match=r"\[caller\] Expected a shapely geometry"):
            _validate_geometry(value, func_name="caller")

