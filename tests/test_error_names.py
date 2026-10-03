"""
Every public function's errors name that function (#4).

An error should tell the user where it happened: the function they called,
not an internal validator or helper. Each public function gets one bad input
and the message must contain ``[<function name>]``.
"""
from datetime import datetime

import pytest
from shapely.geometry import Point, Polygon

import wherewhen.crs as crs
import wherewhen.geometry as geometry
import wherewhen.temporal as temporal

ORIGIN = Point(0.0, 0.0)
WHEN = datetime(2024, 6, 1, 12, 0)

# function name -> (function, bad positional arguments)
BAD_CALLS = {
    # geometry
    "latlon_to_point": (geometry.latlon_to_point, ((95.0, 0.0),)),
    "point_to_latlon": (geometry.point_to_latlon, ("not a point",)),
    "normalize_longitude": (geometry.normalize_longitude, ("x",)),
    "normalize_latlon": (geometry.normalize_latlon, ("x", 0.0)),
    "segment_crosses_antimeridian": (geometry.segment_crosses_antimeridian, ("x", 0.0)),
    "point_distance": (geometry.point_distance, ("not a point", ORIGIN)),
    "point_distance_km": (geometry.point_distance_km, ("not a point", ORIGIN)),
    "point_bearing": (geometry.point_bearing, ("not a point", ORIGIN)),
    "point_at_distance": (geometry.point_at_distance, ("not a point", 1.0, 0.0)),
    "spherical_weighted_centroid": (geometry.spherical_weighted_centroid, (["not a point"], [1.0])),
    "mgrs_to_point": (geometry.mgrs_to_point, ("NOTMGRS",)),
    "dms_to_point": (geometry.dms_to_point, ("garbage",)),
    "ddm_to_point": (geometry.ddm_to_point, ("garbage",)),
    "coordinate_to_point": (geometry.coordinate_to_point, ("garbage",)),
    "point_to_dms": (geometry.point_to_dms, ("not a point",)),
    "point_to_ddm": (geometry.point_to_ddm, ("not a point",)),
    "point_to_mgrs": (geometry.point_to_mgrs, ("not a point",)),
    "geometry_to_box": (geometry.geometry_to_box, ("not a geometry",)),
    "box_to_polygon": (geometry.box_to_polygon, ("garbage",)),
    "get_ratio": (geometry.get_ratio, ("not a geometry",)),
    "get_bounds": (geometry.get_bounds, ("not a geometry", 1.0)),
    "get_polygon": (geometry.get_polygon, ("not a geometry", 1.0)),
    # temporal
    "epoch_to_datetime": (temporal.epoch_to_datetime, ("x",)),
    "convert_to_datetime": (temporal.convert_to_datetime, ("not a date",)),
    "is_dt_naive": (temporal.is_dt_naive, ("x",)),
    "ensure_utc": (temporal.ensure_utc, ("x",)),
    "start_of_day": (temporal.start_of_day, ("x",)),
    "end_of_day": (temporal.end_of_day, ("x",)),
    "shift_tz_by_name": (temporal.shift_tz_by_name, ("x", "Europe/London")),
    "point_to_tz_offset": (temporal.point_to_tz_offset, ("not a point", WHEN)),
    "get_solar_data": (temporal.get_solar_data, ("not a point", WHEN)),
    "get_lunar_data": (temporal.get_lunar_data, ("not a point", WHEN)),
    # crs
    "convert_crs": (crs.convert_crs, ("not a point", "EPSG:4326", "EPSG:3857")),
    "wgs84_to_cn_gcj02": (crs.wgs84_to_cn_gcj02, ("not a point",)),
    "cn_gcj02_to_wgs84": (crs.cn_gcj02_to_wgs84, ("not a point",)),
    "wgs84_to_cn_bd09": (crs.wgs84_to_cn_bd09, ("not a point",)),
    "cn_bd09_to_wgs84": (crs.cn_bd09_to_wgs84, ("not a point",)),
    "ru_sk42_to_wgs84": (crs.ru_sk42_to_wgs84, ("not a point",)),
    "wgs84_to_ru_sk42": (crs.wgs84_to_ru_sk42, ("not a point",)),
}


def _public_functions():
    names = set()
    for module in (geometry, temporal, crs):
        names.update(n for n in module.__all__ if callable(getattr(module, n)))
    return names


def test_every_public_function_is_covered():
    assert set(BAD_CALLS) == _public_functions()


@pytest.mark.parametrize("name", sorted(BAD_CALLS))
def test_error_names_the_function_called(name):
    func, args = BAD_CALLS[name]
    with pytest.raises(Exception) as excinfo:
        func(*args)
    assert f"[{name}]" in str(excinfo.value), (
        f"{name} raised {type(excinfo.value).__name__}: {excinfo.value}"
    )


# Errors from later arguments, and inputs that used to escape as raw Python
# errors (no label) or pass silently.


def _triangle():
    return Polygon([(0, 0), (1, 0), (1, 1)])


MORE_BAD_CALLS = [
    ("normalize_longitude", lambda: geometry.normalize_longitude(10.0, lon_range="bogus")),
    ("normalize_latlon", lambda: geometry.normalize_latlon(10.0, 10.0, lon_range="bogus")),
    ("point_distance", lambda: geometry.point_distance(ORIGIN, Point(1, 1), units="parsecs")),
    ("point_at_distance", lambda: geometry.point_at_distance(ORIGIN, 1.0, "x")),
    ("spherical_weighted_centroid", lambda: geometry.spherical_weighted_centroid([ORIGIN, ORIGIN], [1.0])),
    ("point_to_mgrs", lambda: geometry.point_to_mgrs(ORIGIN, precision=9)),
    ("latlon_to_point", lambda: geometry.latlon_to_point("x")),
    ("latlon_to_point", lambda: geometry.latlon_to_point(("a", "b"))),
    ("geometry_to_box", lambda: geometry.geometry_to_box(Polygon())),
    ("get_bounds", lambda: geometry.get_bounds(_triangle(), -1.0)),
    ("get_polygon", lambda: geometry.get_polygon(_triangle(), 1.0, fit_mode="bogus")),
    ("epoch_to_datetime", lambda: temporal.epoch_to_datetime(1e30)),
    ("shift_tz_by_name", lambda: temporal.shift_tz_by_name(WHEN, "Not/AZone")),
    ("point_to_tz_offset", lambda: temporal.point_to_tz_offset(ORIGIN, "x")),
    ("get_solar_data", lambda: temporal.get_solar_data(Point(38.77, 48.53), "x")),
    ("get_lunar_data", lambda: temporal.get_lunar_data(Point(38.77, 48.53), "x")),
    ("convert_crs", lambda: crs.convert_crs(ORIGIN, "EPSG:4326", 123)),
    ("convert_crs", lambda: crs.convert_crs("not a point", "WGS84", "GCJ02")),
    # Delegation (Cursor's review of #5): the error must name the function called.
    ("coordinate_to_point", lambda: geometry.coordinate_to_point((95.0, 0.0))),
    ("coordinate_to_point", lambda: geometry.coordinate_to_point(("a", "b"))),
    ("coordinate_to_point", lambda: geometry.coordinate_to_point("1C")),
    ("coordinate_to_point", lambda: geometry.coordinate_to_point("99XXX0000000000")),
    ("cn_bd09_to_wgs84", lambda: crs.cn_bd09_to_wgs84(Point(-180, -90))),
    ("convert_crs", lambda: crs.convert_crs(Point(-180, -90), "BD09", "WGS84")),
]


@pytest.mark.parametrize("name, call", MORE_BAD_CALLS, ids=[f"{n}-{i}" for i, (n, _) in enumerate(MORE_BAD_CALLS)])
def test_later_argument_errors_name_the_function_called(name, call):
    with pytest.raises(Exception) as excinfo:
        call()
    assert f"[{name}]" in str(excinfo.value), (
        f"{name} raised {type(excinfo.value).__name__}: {excinfo.value}"
    )


def test_latlon_to_point_still_accepts_numeric_strings_and_lists():
    assert geometry.latlon_to_point(("51.5", "-0.12")).equals(Point(-0.12, 51.5))
    assert geometry.latlon_to_point([51.5, -0.12]).equals(Point(-0.12, 51.5))


# Public functions may call other public functions only where the inner call
# cannot fail with its own label: the inputs were already validated under the
# caller's name, or are values the caller just computed.  Anything else must go
# through a private helper that takes ``func_name``.  Adding a pair here is a
# deliberate, reviewed decision.
ALLOWED_PUBLIC_CALLS = {
    ("point_distance_km", "point_distance"): "both points validated as point_distance_km; units fixed to 'km'",
    ("point_at_distance", "normalize_latlon"): "normalises the destination it just computed (floats, default range)",
    ("spherical_weighted_centroid", "normalize_latlon"): "normalises the centroid it just computed",
    ("convert_to_datetime", "is_dt_naive"): "called on the datetime it just produced",
    ("ensure_utc", "is_dt_naive"): "dt validated as ensure_utc first",
    ("shift_tz_by_name", "ensure_utc"): "dt validated as shift_tz_by_name first",
    ("point_to_tz_offset", "ensure_utc"): "eval_dt validated as point_to_tz_offset first",
}


def test_public_to_public_calls_are_reviewed():
    import ast
    import os

    public = _public_functions()
    found = set()
    pkg = os.path.dirname(geometry.__file__)
    for module in ("geometry", "temporal", "crs"):
        with open(os.path.join(pkg, f"{module}.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in public:
                for node in ast.walk(fn):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id in public and node.func.id != fn.name):
                        found.add((fn.name, node.func.id))
    assert found == set(ALLOWED_PUBLIC_CALLS), (
        f"unreviewed: {sorted(found - set(ALLOWED_PUBLIC_CALLS))}; "
        f"stale: {sorted(set(ALLOWED_PUBLIC_CALLS) - found)}"
    )


# Exception classes follow Python's definitions (agreed with Cursor on #5):
# TypeError = wrong type of argument, ValueError = right type, bad value.
EXCEPTION_CLASSES = [
    (TypeError, lambda: geometry.get_ratio("x")),
    (TypeError, lambda: geometry.get_bounds("x", 1.0)),
    (TypeError, lambda: geometry.get_polygon("x", 1.0)),
    (TypeError, lambda: crs.convert_crs(ORIGIN, "EPSG:4326", 123)),
    (TypeError, lambda: geometry.latlon_to_point(None)),
    (TypeError, lambda: geometry.latlon_to_point(5)),
    (TypeError, lambda: geometry.latlon_to_point("x")),
    (TypeError, lambda: geometry.latlon_to_point("33UXP0500144000")),
    (TypeError, lambda: geometry.latlon_to_point("12")),
    (TypeError, lambda: geometry.latlon_to_point(b"12")),
    (TypeError, lambda: geometry.latlon_to_point(bytearray(b"12"))),
    (TypeError, lambda: geometry.latlon_to_point(memoryview(b"12"))),
    (ValueError, lambda: geometry.latlon_to_point((1, 2, 3))),
    (ValueError, lambda: geometry.latlon_to_point([1])),
    (ValueError, lambda: geometry.latlon_to_point(("a", "b"))),
    (ValueError, lambda: temporal.epoch_to_datetime(1e30)),
    (ValueError, lambda: temporal.epoch_to_datetime(-1e30)),
]


@pytest.mark.parametrize("expected, call", EXCEPTION_CLASSES, ids=[str(i) for i in range(len(EXCEPTION_CLASSES))])
def test_exception_class_is_technically_correct(expected, call):
    with pytest.raises(Exception) as excinfo:
        call()
    assert type(excinfo.value) is expected, f"{type(excinfo.value).__name__}: {excinfo.value}"


def test_latlon_to_point_rejects_strings_that_would_unpack_as_pairs():
    # Before: "12" -> POINT (2 1); b"12", bytearray and memoryview -> POINT (50 49).
    for bad in ("12", "45", b"12", bytearray(b"12"), memoryview(b"12")):
        with pytest.raises(TypeError, match=r"\[latlon_to_point\]"):
            geometry.latlon_to_point(bad)


# A missing optional package is an error like any other: it starts with ⚠️ and
# names the function called.  ❌ is only for printed "skipped" notices.
MISSING_PACKAGE_CASES = [
    ("pyproj", "from wherewhen.crs import ru_sk42_to_wgs84 as f; f(Point(30.0, 50.0))", "ru_sk42_to_wgs84"),
    ("pyproj", "from wherewhen.crs import wgs84_to_ru_sk42 as f; f(Point(30.0, 50.0))", "wgs84_to_ru_sk42"),
    ("astral", "from wherewhen.temporal import get_solar_data as f; f(Point(30.0, 50.0), WHEN)", "get_solar_data"),
    ("timezonefinder", "from wherewhen.temporal import get_lunar_data as f; f(Point(30.0, 50.0), WHEN)", "get_lunar_data"),
    ("timezonefinder", "from wherewhen.temporal import point_to_tz_offset as f; f(Point(30.0, 50.0), WHEN)", "point_to_tz_offset"),
]


@pytest.mark.parametrize("package, call, name", MISSING_PACKAGE_CASES, ids=[c[2] for c in MISSING_PACKAGE_CASES])
def test_missing_package_errors_start_with_warning(package, call, name):
    import subprocess
    import sys

    code = (
        "import sys\n"
        f"sys.modules[{package!r}] = None  # make the import fail\n"
        "from datetime import datetime\n"
        "from shapely.geometry import Point\n"
        "WHEN = datetime(2024, 6, 1, 12)\n"
        "try:\n"
        f"    {call}\n"
        "except ImportError as exc:\n"
        "    print('MSG', exc)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    msg = result.stdout.strip().splitlines()[-1]
    assert msg.startswith(f"MSG ⚠️ [{name}] "), msg
    assert package in msg, msg


def test_no_raised_error_uses_the_skip_prefix():
    import ast
    import pathlib

    import wherewhen

    offenders = []
    for path in sorted(pathlib.Path(wherewhen.__file__).parent.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Raise) and node.exc is not None:
                for call in ast.walk(node.exc):
                    if isinstance(call, ast.Call) and getattr(call.func, "id", None) in ("skip", "_skip"):
                        offenders.append(f"{path.name}:{node.lineno}")
                    if isinstance(call, ast.Constant) and isinstance(call.value, str) and call.value.startswith("❌"):
                        offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []
