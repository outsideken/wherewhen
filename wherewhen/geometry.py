"""
wherewhen.geometry
=================
Coordinate conversion, bounding-box, and aspect-ratio utilities.

Covers:

* ``(lat, lon)`` tuple → Shapely ``Point``
* DMS and DDM string → Shapely ``Point``
* MGRS string → Shapely ``Point``
* Shapely ``Point`` → DMS / DDM string pair
* Shapely ``Point`` → MGRS string
* Shapely ``Point`` → ``(lat, lon)`` tuple (:func:`point_to_latlon`)
* Longitude / lat-lon normalization with pole-crossing rules
  (:func:`normalize_longitude`, :func:`normalize_latlon`)
* Antimeridian detection (:func:`segment_crosses_antimeridian`)
* Great-circle distance between two points (:func:`point_distance`, ``units='km'`` default)
* Initial bearing between two points (:func:`point_bearing`, degrees clockwise from north)
* Destination along bearing + distance (:func:`point_at_distance`)
* Spherical weighted centroid (:func:`spherical_weighted_centroid`)
* PostGIS ``BOX(…)`` string → Shapely ``Polygon`` (:func:`box_to_polygon`)
* Unified dispatcher :func:`coordinate_to_point` that auto-detects format
* Shapely geometry → PostGIS BOX string or envelope ``Polygon``
* Aspect-ratio utilities: :func:`get_ratio`, :func:`get_bounds`, :func:`get_polygon`

Non-WGS-84 coordinate system conversions (GCJ-02, BD-09, SK-42) are in
:mod:`wherewhen.crs`.  The ``mgrs`` package is required for MGRS conversions.

Functions
---------
latlon_to_point
    Convert a ``(lat, lon)`` tuple to a Shapely ``Point``.
point_to_latlon
    Convert a Shapely ``Point`` to a ``(lat, lon)`` tuple.
normalize_longitude
    Wrap a longitude value to ``[-180, 180]`` or ``[0, 360)``.
normalize_latlon
    Canonicalize ``(lat, lon)`` with pole reflection and longitude wrap.
segment_crosses_antimeridian
    Return whether the shortest path between two longitudes crosses ±180°.
point_distance
    Great-circle distance between two WGS-84 points (``units`` selects output measure).
point_distance_km
    Convenience wrapper — :func:`point_distance` with ``units='km'``.
point_bearing
    Initial forward azimuth from one WGS-84 point to another (0–360°, clockwise from north).
point_at_distance
    Destination point along a bearing and great-circle distance.
spherical_weighted_centroid
    Weighted geographic centre on the sphere (antimeridian-safe).
mgrs_to_point
    Convert an MGRS string to a Shapely ``Point``.
dms_to_point
    Parse a DMS lat/lon pair string to a Shapely ``Point``.
ddm_to_point
    Parse a DDM lat/lon pair string to a Shapely ``Point``.
coordinate_to_point
    Unified dispatcher: any supported coordinate format → Shapely ``Point``.
point_to_dms
    Return a Shapely ``Point`` as a (lat, lon) DMS string pair.
point_to_ddm
    Return a Shapely ``Point`` as a (lat, lon) DDM string pair.
point_to_mgrs
    Return a Shapely ``Point`` as an MGRS coordinate string.
geometry_to_box
    Convert a Shapely geometry to a PostGIS BOX string or its envelope Polygon.
box_to_polygon
    Parse a PostGIS ``BOX(…)`` string to a Shapely ``Polygon``.
get_ratio
    Compute the aspect ratio (width / height) of a geometry's bounding box.
get_bounds
    Return adjusted bounding-box bounds to match a target aspect ratio.
get_polygon
    Return a rectangular Polygon with a target aspect ratio.

Toolkit
-------
Part of the ``wherewhen`` package (successor to ``geocore``).  Import from
this module directly — not re-exported by :mod:`jematools`.  Validation
errors raise with ``⚠️ [function_name] …`` via :mod:`wherewhen._messages`.
"""

import math
import re
from typing import Literal, Sequence, Tuple, Union

import mgrs as mgrs_lib
from shapely.geometry import Point, Polygon, box as shapely_box
from shapely.geometry.base import BaseGeometry

from wherewhen._messages import warn as _warn
from wherewhen._validators import (
    _BOX_PATTERN,
    _validate_latitude,
    _validate_longitude,
    _validate_mgrs,
    _validate_mgrs_precision,
    _validate_point,
    _validate_dms,
    _validate_ddm_pair,
)

__all__ = [
    "EARTH_RADIUS_M",
    "METRES_PER_UNIT",
    "SUPPORTED_DISTANCE_UNITS",
    "latlon_to_point",
    "point_to_latlon",
    "normalize_longitude",
    "normalize_latlon",
    "segment_crosses_antimeridian",
    "point_distance",
    "point_distance_km",
    "point_bearing",
    "point_at_distance",
    "spherical_weighted_centroid",
    "mgrs_to_point",
    "dms_to_point",
    "ddm_to_point",
    "coordinate_to_point",
    "point_to_dms",
    "point_to_ddm",
    "point_to_mgrs",
    "geometry_to_box",
    "box_to_polygon",
    "get_ratio",
    "get_bounds",
    "get_polygon",
]

# ── Constants ─────────────────────────────────────────────────────────────────

# Shared MGRS converter instance — avoids re-instantiation on every call
_MGRS_INSTANCE = mgrs_lib.MGRS()

# WGS-84 mean Earth radius (metres) for Haversine great-circle distance
EARTH_RADIUS_M: float = 6_371_008.8

# Metres per one unit of each named distance measure
METRES_PER_UNIT: dict[str, float] = {
    "m":  1.0,
    "km": 1_000.0,
    "nm": 1_852.0,       # international nautical mile
    "mi": 1_609.344,     # international statute mile
}

SUPPORTED_DISTANCE_UNITS = frozenset(METRES_PER_UNIT)

# Compiled coordinate-parsing patterns — hoisted to avoid re-compilation per call
_DMS_PATTERN = re.compile(
    r"""
    (?P<lat_deg>[0-8]?\d)      \s*[^\d]*\s*
    (?P<lat_min>[0-5]?\d)?     \s*[^\d]*\s*
    (?P<lat_sec>[0-5]?\d(?:\.\d+)?)? \s*[^\d]*\s*
    (?P<lat_dir>[NSns])
    .*?
    (?P<lon_deg>[01]?\d{1,2})  \s*[^\d]*\s*
    (?P<lon_min>[0-5]?\d)?     \s*[^\d]*\s*
    (?P<lon_sec>[0-5]?\d(?:\.\d+)?)? \s*[^\d]*\s*
    (?P<lon_dir>[EWew])
    """,
    re.VERBOSE | re.IGNORECASE,
)

_DDM_PATTERN = re.compile(
    r"""
    (?P<lat_deg>\d{1,3}) \s*[^\d]*\s*
    (?P<lat_min>\d{1,2}(?:\.\d+)?) \s*[^\d]*\s*
    (?P<lat_dir>[NSns])
    .*?
    (?P<lon_deg>\d{1,3}) \s*[^\d]*\s*
    (?P<lon_min>\d{1,2}(?:\.\d+)?) \s*[^\d]*\s*
    (?P<lon_dir>[EWew])
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Detection patterns used by coordinate_to_point
_MGRS_DETECT  = re.compile(r"^\d{1,2}[C-X]", re.IGNORECASE)
_DMS_SYMBOLS  = re.compile(r"[°'\"]")
_NSEW         = re.compile(r"[NSEWnsew]")
_DDM_DETECT   = re.compile(r"\d+\.?\d*\s*[′']?\s*[NSEWnsew]")


# ── Private helpers ───────────────────────────────────────────────────────────

def _scrub_dms(text: str) -> str:
    """Strip DMS symbols and normalise whitespace for regex parsing."""
    symbols = r"°˚º′''″\"˝¨:"
    text = re.sub(rf"[{symbols}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _dd_to_dms(dd: float, is_lat: bool) -> str:
    """Format a decimal-degree value as a DMS string (e.g. ``51°30'26.16"N``)."""
    direction = ("N" if dd >= 0 else "S") if is_lat else ("E" if dd >= 0 else "W")
    dd = abs(dd)
    degrees = int(dd)
    minutes_float = (dd - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60.0
    return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"


def _dd_to_ddm(dd: float, is_lat: bool) -> str:
    """Format a decimal-degree value as a DDM string (e.g. ``51°30.436'N``)."""
    direction = ("N" if dd >= 0 else "S") if is_lat else ("E" if dd >= 0 else "W")
    dd = abs(dd)
    degrees = int(dd)
    minutes = (dd - degrees) * 60.0
    return f"{degrees}°{minutes:06.3f}'{direction}"


def normalize_longitude(
    lon: float,
    *,
    lon_range: Literal["[-180,180]", "[0,360)"] = "[-180,180]",
) -> float:
    """
    Wrap a longitude value to a canonical meridian range.

    Does not change which meridian the value represents.  Use at ingest when
    sources emit longitudes outside ``[-180, 180]`` or in ``[0, 360)`` form.
    Strict :func:`~wherewhen._validators._validate_longitude` is unchanged —
    call this explicitly when normalization is intended.

    Parameters
    ----------
    lon : float
        Longitude in decimal degrees (any real value).
    lon_range : ``'[-180,180]'`` or ``'[0,360)'``, optional
        Target range.  Default is ``'[-180,180]'`` (antimeridian at ±180°).

    Returns
    -------
    float
        Canonical longitude in the requested range.

    Raises
    ------
    TypeError
        If *lon* is not a number.
    ValueError
        If *lon_range* is not supported.

    See Also
    --------
    normalize_latlon : Pole reflection plus longitude wrap for a coordinate pair.
    segment_crosses_antimeridian : Detect shortest-path crossing of ±180°.

    Examples
    --------
    >>> normalize_longitude(190)
    -170.0
    >>> normalize_longitude(-190)
    170.0
    >>> normalize_longitude(190, lon_range="[0,360)")
    190.0
    >>> normalize_longitude(-170, lon_range="[0,360)")
    190.0
    """
    if not isinstance(lon, (int, float)):
        raise TypeError(
            _warn(
                "normalize_longitude",
                f"Longitude must be a number, got {type(lon).__name__}.",
            )
        )
    if lon_range == "[-180,180]":
        wrapped = math.fmod(float(lon) + 180.0, 360.0)
        if wrapped < 0.0:
            wrapped += 360.0
        return wrapped - 180.0
    if lon_range == "[0,360)":
        wrapped = math.fmod(float(lon), 360.0)
        if wrapped < 0.0:
            wrapped += 360.0
        return wrapped
    raise ValueError(
        _warn(
            "normalize_longitude",
            f"lon_range must be '[-180,180]' or '[0,360)', got {lon_range!r}.",
        )
    )


def normalize_latlon(
    lat: float,
    lon: float,
    *,
    lon_range: Literal["[-180,180]", "[0,360)"] = "[-180,180]",
) -> Tuple[float, float]:
    """
    Canonicalize a ``(lat, lon)`` pair with pole reflection and longitude wrap.

    When ``|lat| > 90``, reflects across the nearer pole and shifts longitude
    by 180° until ``|lat| ≤ 90``.  Longitude is then passed through
    :func:`normalize_longitude`.  Handles multiple pole crossings in one call.

    At ``lat = ±90`` (the poles), longitude is arbitrary; the input longitude
    is preserved aside from wrapping.

    Parameters
    ----------
    lat, lon : float
        Latitude and longitude in decimal degrees (any real values).
    lon_range : ``'[-180,180]'`` or ``'[0,360)'``, optional
        Target longitude range — forwarded to :func:`normalize_longitude`.

    Returns
    -------
    tuple of float
        ``(latitude, longitude)`` in canonical WGS-84 form.

    Raises
    ------
    TypeError
        If *lat* or *lon* is not a number.

    See Also
    --------
    normalize_longitude : Longitude-only wrap.
    segment_crosses_antimeridian : Antimeridian detection on canonical longitudes.

    Examples
    --------
    >>> normalize_latlon(51.5, -0.1)
    (51.5, -0.1)
    >>> normalize_latlon(95, 10)
    (85.0, -170.0)
    >>> normalize_latlon(-95, 10)
    (-85.0, -170.0)
    >>> normalize_latlon(45, 190)
    (45.0, -170.0)
    """
    if not isinstance(lat, (int, float)):
        raise TypeError(
            _warn(
                "normalize_latlon",
                f"Latitude must be a number, got {type(lat).__name__}.",
            )
        )
    if not isinstance(lon, (int, float)):
        raise TypeError(
            _warn(
                "normalize_latlon",
                f"Longitude must be a number, got {type(lon).__name__}.",
            )
        )

    lat_f = float(lat)
    lon_f = float(lon)

    while lat_f > 90.0:
        lat_f = 180.0 - lat_f
        lon_f += 180.0
    while lat_f < -90.0:
        lat_f = -180.0 - lat_f
        lon_f += 180.0

    return lat_f, normalize_longitude(lon_f, lon_range=lon_range)


def segment_crosses_antimeridian(lon1: float, lon2: float) -> bool:
    """
    Return whether the shortest great-circle path crosses the antimeridian (±180°).

    Both longitudes are canonicalized via :func:`normalize_longitude` before
    comparison.  Equivalent to ``abs(Δlon) > 180°`` on the normalized values.

    Parameters
    ----------
    lon1, lon2 : float
        Endpoint longitudes in decimal degrees.

    Returns
    -------
    bool
        ``True`` when the shortest path between the meridians crosses ±180°.

    See Also
    --------
    normalize_longitude, normalize_latlon
    point_distance : Uses shortest-path longitude delta internally.

    Examples
    --------
    >>> segment_crosses_antimeridian(10, 20)
    False
    >>> segment_crosses_antimeridian(179, -179)
    True
    >>> segment_crosses_antimeridian(170, -170)
    True
    """
    a = normalize_longitude(lon1)
    b = normalize_longitude(lon2)
    return abs(a - b) > 180.0


def _delta_longitude(lon1: float, lon2: float) -> float:
    """Shortest signed longitude difference in degrees."""
    a = normalize_longitude(lon1)
    b = normalize_longitude(lon2)
    d_lon = b - a
    if d_lon > 180.0:
        d_lon -= 360.0
    elif d_lon < -180.0:
        d_lon += 360.0
    return d_lon


def _haversine_m(
    pt_a: Point,
    pt_b: Point,
    *,
    radius_m: float = EARTH_RADIUS_M,
) -> float:
    """Great-circle distance between two WGS-84 points in metres."""
    lat1, lon1 = pt_a.y, pt_a.x
    lat2, lon2 = pt_b.y, pt_b.x
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(_delta_longitude(lon1, lon2))
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _initial_bearing_deg(pt_a: Point, pt_b: Point) -> float:
    """Forward azimuth from *pt_a* to *pt_b* in degrees [0, 360)."""
    lat1 = math.radians(pt_a.y)
    lat2 = math.radians(pt_b.y)
    d_lon = math.radians(_delta_longitude(pt_a.x, pt_b.x))

    y = math.sin(d_lon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    )
    bearing = math.degrees(math.atan2(y, x))
    return bearing % 360.0


def _distance_from_metres(distance_m: float, units: str) -> float:
    """Convert a metre distance to *units* using :data:`METRES_PER_UNIT`."""
    factor = METRES_PER_UNIT.get(units)
    if factor is None:
        supported = ", ".join(sorted(METRES_PER_UNIT))
        raise ValueError(
            _warn(
                "point_distance",
                f"units must be one of ({supported}), got {units!r}.",
            )
        )
    return distance_m / factor


def _distance_to_metres(distance: float, units: str, *, func_name: str) -> float:
    """Convert a distance in *units* to metres."""
    factor = METRES_PER_UNIT.get(units)
    if factor is None:
        supported = ", ".join(sorted(METRES_PER_UNIT))
        raise ValueError(
            _warn(
                func_name,
                f"units must be one of ({supported}), got {units!r}.",
            )
        )
    return distance * factor


# ── Point conversions ─────────────────────────────────────────────────────────

def latlon_to_point(latlon: tuple) -> Point:
    """
    Convert a ``(lat, lon)`` tuple to a Shapely ``Point(lon, lat)``.

    Shapely uses ``(x, y)`` ordering, which corresponds to
    ``(longitude, latitude)``.  This function handles the axis swap and
    validates coordinate bounds.

    Parameters
    ----------
    latlon : tuple of float
        ``(latitude, longitude)`` in decimal degrees.
        Latitude must be in [-90, 90]; longitude in [-180, 180].

    Returns
    -------
    shapely.geometry.Point
        Point with ``x = longitude`` and ``y = latitude``.

    Raises
    ------
    ValueError
        If latitude is outside [-90, 90] or longitude is outside [-180, 180].

    Examples
    --------
    >>> pt = latlon_to_point((51.5074, -0.1278))
    >>> pt.x, pt.y
    (-0.1278, 51.5074)
    """
    latitude, longitude = latlon
    _validate_latitude(float(latitude))
    _validate_longitude(float(longitude))
    return Point(longitude, latitude)


def point_to_latlon(pt: Point) -> Tuple[float, float]:
    """
    Convert a Shapely ``Point`` to a ``(lat, lon)`` decimal-degree tuple.

    Inverse of :func:`latlon_to_point`.  Shapely stores ``(x, y)`` as
    ``(longitude, latitude)``; this function returns the conventional
    ``(latitude, longitude)`` ordering.

    Parameters
    ----------
    pt : shapely.geometry.Point
        Point with ``x = longitude`` and ``y = latitude``.

    Returns
    -------
    tuple of float
        ``(latitude, longitude)`` in decimal degrees.

    Raises
    ------
    TypeError
        If *pt* is not a Shapely ``Point``.
    ValueError
        If the point coordinates are outside WGS-84 bounds.

    See Also
    --------
    latlon_to_point : Tuple → Point conversion.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> point_to_latlon(Point(-0.1278, 51.5074))
    (51.5074, -0.1278)
    """
    _validate_point(pt)
    return (pt.y, pt.x)


def point_distance(
    pt_a: Point,
    pt_b: Point,
    units: Literal["m", "km", "nm", "mi"] = "km",
) -> float:
    """
    Great-circle distance between two WGS-84 points.

    Uses the Haversine formula with :data:`EARTH_RADIUS_M` and converts the
    result via :data:`METRES_PER_UNIT`.  Longitude delta follows the shortest
    arc (antimeridian-safe).

    Parameters
    ----------
    pt_a, pt_b : shapely.geometry.Point
        Points with ``x = longitude`` and ``y = latitude``.
    units : {'m', 'km', 'nm', 'mi'}, optional
        Output distance unit.  Default is ``'km'``.

    Returns
    -------
    float
        Distance in the requested unit (≥ 0).

    Raises
    ------
    TypeError
        If either argument is not a Shapely ``Point``.
    ValueError
        If either point has coordinates outside WGS-84 bounds, or if *units*
        is not a key in :data:`METRES_PER_UNIT`.

    See Also
    --------
    point_distance_km : Same call with ``units='km'``.
    point_bearing : Initial forward azimuth between the same two points.
    latlon_to_point, point_to_latlon : Coordinate conversion helpers.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> london = Point(-0.1278, 51.5074)
    >>> paris = Point(2.3522, 48.8566)
    >>> dist = point_distance(london, paris)
    >>> 300 < dist < 400
    True
    >>> point_distance(london, paris, units="m") > 300_000
    True
    """
    _validate_point(pt_a)
    _validate_point(pt_b)
    return _distance_from_metres(_haversine_m(pt_a, pt_b), units)


def point_distance_km(pt_a: Point, pt_b: Point) -> float:
    """
    Great-circle distance between two WGS-84 points in kilometres.

    Thin wrapper around :func:`point_distance` with ``units='km'``.

    Parameters
    ----------
    pt_a, pt_b : shapely.geometry.Point
        Points with ``x = longitude`` and ``y = latitude``.

    Returns
    -------
    float
        Distance in kilometres (≥ 0).

    See Also
    --------
    point_distance : General distance primitive with ``units=`` selection.
    """
    return point_distance(pt_a, pt_b, units="km")


def point_bearing(pt_a: Point, pt_b: Point) -> float:
    """
    Initial forward azimuth from *pt_a* to *pt_b*.

    Returns the great-circle bearing at the departure point: degrees clockwise
    from true north, in ``[0, 360)``.  Uses the shortest-path longitude delta
    (antimeridian-safe), consistent with :func:`point_distance`.

    Parameters
    ----------
    pt_a, pt_b : shapely.geometry.Point
        Points with ``x = longitude`` and ``y = latitude``.

    Returns
    -------
    float
        Bearing in degrees from north (≥ 0, < 360).

    Raises
    ------
    TypeError
        If either argument is not a Shapely ``Point``.
    ValueError
        If either point has coordinates outside WGS-84 bounds, or if *pt_a* and
        *pt_b* are the same location (bearing undefined).

    See Also
    --------
    point_distance : Great-circle distance between the same two points.
    segment_crosses_antimeridian : Whether the shortest path crosses ±180°.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> london = Point(-0.1278, 51.5074)
    >>> paris = Point(2.3522, 48.8566)
    >>> 140 < point_bearing(london, paris) < 170
    True
    >>> point_bearing(Point(0, 0), Point(1, 0))  # due east at equator
    90.0
    """
    _validate_point(pt_a)
    _validate_point(pt_b)
    if pt_a.equals(pt_b):
        raise ValueError(
            _warn(
                "point_bearing",
                "Bearing is undefined when both points are the same location.",
            )
        )
    return _initial_bearing_deg(pt_a, pt_b)


def point_at_distance(
    pt: Point,
    distance: float,
    bearing: float,
    units: Literal["m", "km", "nm", "mi"] = "km",
) -> Point:
    """
    Return the destination point along a bearing and great-circle distance.

    Uses the spherical Earth model with :data:`EARTH_RADIUS_M`.  The result is
    normalised via :func:`normalize_latlon` so pole crossings and longitude
    wraps produce valid WGS-84 coordinates.

    Parameters
    ----------
    pt : shapely.geometry.Point
        Departure point with ``x = longitude`` and ``y = latitude``.
    distance : float
        Distance to travel along *bearing*.  Must be ≥ 0.
    bearing : float
        Initial forward azimuth in degrees clockwise from true north.
        Values outside ``[0, 360)`` are wrapped with modulo arithmetic.
    units : {'m', 'km', 'nm', 'mi'}, optional
        Unit for *distance*.  Default is ``'km'``.

    Returns
    -------
    shapely.geometry.Point
        Destination point in WGS-84.

    Raises
    ------
    TypeError
        If *pt* is not a Shapely ``Point``.
    ValueError
        If *pt* coordinates are out of bounds, if *distance* is negative, if
        *bearing* is not numeric, or if *units* is unsupported.

    See Also
    --------
    point_distance : Great-circle distance between two points.
    point_bearing : Bearing between two points.
    normalize_latlon : Canonicalizes the computed destination.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> origin = Point(0, 0)
    >>> dest = point_at_distance(origin, 111.32, 90, units="km")
    >>> 0 < dest.x < 2
    True
    >>> point_at_distance(origin, 0, 90) == origin
    True
    """
    _validate_point(pt)
    if isinstance(distance, bool) or not isinstance(distance, (int, float)) or distance < 0:
        raise ValueError(
            _warn(
                "point_at_distance",
                f"distance must be a non-negative number, got {distance!r}.",
            )
        )
    if isinstance(bearing, bool) or not isinstance(bearing, (int, float)):
        raise ValueError(
            _warn(
                "point_at_distance",
                f"bearing must be a real number, got {bearing!r}.",
            )
        )
    if distance == 0:
        return Point(pt.x, pt.y)

    distance_m = _distance_to_metres(distance, units, func_name="point_at_distance")
    bearing_deg = float(bearing) % 360.0

    lat1 = math.radians(pt.y)
    lon1 = math.radians(pt.x)
    brng = math.radians(bearing_deg)
    angular = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular)
        + math.cos(lat1) * math.sin(angular) * math.cos(brng)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )

    lat_deg, lon_deg = normalize_latlon(math.degrees(lat2), math.degrees(lon2))
    _validate_latitude(lat_deg)
    _validate_longitude(lon_deg)
    return Point(lon_deg, lat_deg)


def spherical_weighted_centroid(
    points: Sequence[Point],
    weights: Sequence[float],
) -> Point:
    """
    Return the weighted geographic centre of WGS-84 points on the sphere.

    Converts each point to a unit Cartesian vector, forms the weighted sum,
    normalises, and converts back to latitude/longitude.  This avoids the
    antimeridian and polar errors of a plain lat/lon arithmetic mean.

    Parameters
    ----------
    points : sequence of shapely.geometry.Point
        Points with ``x = longitude`` and ``y = latitude``.
    weights : sequence of float
        Non-negative weight per point.  Must be the same length as *points*.
        Zero weights are ignored.  The sum must be positive.

    Returns
    -------
    shapely.geometry.Point
        Weighted centroid in WGS-84.

    Raises
    ------
    TypeError
        If any element of *points* is not a Shapely ``Point``.
    ValueError
        If *points* and *weights* differ in length, if no points are given,
        if any weight is negative, or if the total weight is zero.

    See Also
    --------
    point_distance : Great-circle distance between two points.
    normalize_latlon : Canonicalizes the computed centroid.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pts = [Point(-0.1278, 51.5074), Point(2.3522, 48.8566)]
    >>> c = spherical_weighted_centroid(pts, [1.0, 1.0])
    >>> isinstance(c, Point)
    True

    >>> # Antimeridian: Euclidean mean would land near 0°; spherical stays at ±180°
    >>> antimeridian = spherical_weighted_centroid(
    ...     [Point(179, 0), Point(-179, 0)], [1.0, 1.0]
    ... )
    >>> abs(abs(antimeridian.x) - 180) < 1
    True
    """
    if len(points) != len(weights):
        raise ValueError(
            _warn(
                "spherical_weighted_centroid",
                f"points and weights must have the same length, got "
                f"{len(points)} and {len(weights)}.",
            )
        )
    if not points:
        raise ValueError(
            _warn(
                "spherical_weighted_centroid",
                "At least one point is required.",
            )
        )

    x_sum = y_sum = z_sum = 0.0
    total_weight = 0.0
    for pt, weight in zip(points, weights):
        _validate_point(pt)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError(
                _warn(
                    "spherical_weighted_centroid",
                    f"Each weight must be a real number, got {weight!r}.",
                )
            )
        if weight < 0:
            raise ValueError(
                _warn(
                    "spherical_weighted_centroid",
                    f"Weights must be non-negative, got {weight!r}.",
                )
            )
        if weight == 0:
            continue

        lat = math.radians(pt.y)
        lon = math.radians(pt.x)
        cos_lat = math.cos(lat)
        x_sum += weight * cos_lat * math.cos(lon)
        y_sum += weight * cos_lat * math.sin(lon)
        z_sum += weight * math.sin(lat)
        total_weight += weight

    if total_weight == 0:
        raise ValueError(
            _warn(
                "spherical_weighted_centroid",
                "Total weight is zero — cannot compute weighted centroid.",
            )
        )

    norm = math.sqrt(x_sum * x_sum + y_sum * y_sum + z_sum * z_sum)
    if norm == 0.0:
        raise ValueError(
            _warn(
                "spherical_weighted_centroid",
                "Weighted vector sum is zero — points may cancel exactly.",
            )
        )

    x = x_sum / norm
    y = y_sum / norm
    z = z_sum / norm
    lat_deg, lon_deg = normalize_latlon(math.degrees(math.asin(z)), math.degrees(math.atan2(y, x)))
    _validate_latitude(lat_deg)
    _validate_longitude(lon_deg)
    return Point(lon_deg, lat_deg)


def mgrs_to_point(mgrs_str: str, return_latlon: bool = False):
    """
    Convert an MGRS coordinate string to a Shapely ``Point``.

    Parameters
    ----------
    mgrs_str : str
        MGRS coordinate string, e.g. ``"18TWL8396007450"`` or
        ``"30UXC0529398803"``.
    return_latlon : bool, optional
        If ``True``, return a raw ``(lat, lon)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` tuple when *return_latlon* is ``True``.

    Raises
    ------
    TypeError
        If *mgrs_str* is not a non-empty ``str``.
    ValueError
        If *mgrs_str* does not conform to the MGRS structural pattern.

    See Also
    --------
    point_to_mgrs : Reverse conversion — Shapely ``Point`` → MGRS string.
    coordinate_to_point : Unified dispatcher that auto-detects format.

    Examples
    --------
    >>> pt = mgrs_to_point("30UXC0529398803")
    >>> round(pt.y, 4), round(pt.x, 4)
    (51.5074, -0.1277)
    """
    _validate_mgrs(mgrs_str)
    lat_dd, lon_dd = _MGRS_INSTANCE.toLatLon(mgrs_str)
    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def dms_to_point(
    dms_str: str,
    return_latlon: bool = False,
    debug: bool = False,
) -> Point:
    """
    Parse a DMS lat/lon pair string to a Shapely ``Point``.

    Accepts a wide variety of degree/minute/second separators and Unicode
    symbols (``°``, ``˚``, ``′``, ``'``, ``″``, ``"``, spaces, colons, …).
    Both ``N``/``S`` and ``E``/``W`` hemisphere suffixes are required.

    Parameters
    ----------
    dms_str : str
        DMS coordinate pair string.  Examples of accepted formats:

        * ``"39°48'18\\" N 089°38'42\\" W"``
        * ``"51:30:26N 000:07:40W"``
        * ``"51 30 26 N 0 07 40 W"``
    return_latlon : bool, optional
        If ``True``, return ``(lat_dd, lon_dd)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.
    debug : bool, optional
        If ``True``, print the scrubbed input and parsed regex groups to
        stdout for troubleshooting.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` decimal-degree tuple when
          *return_latlon* is ``True``.

    Raises
    ------
    TypeError
        If *dms_str* is not a ``str``.
    ValueError
        If the string is empty, lacks proper N/S and E/W indicators,
        cannot be parsed by the regex, or produces out-of-bounds coordinates.

    See Also
    --------
    ddm_to_point : Parse Degrees Decimal Minutes format instead.
    point_to_dms : Reverse conversion — Shapely ``Point`` → DMS string pair.
    coordinate_to_point : Unified dispatcher that auto-detects format.

    Examples
    --------
    >>> pt = dms_to_point("51°30'26\\" N 0°7'40\\" W")
    >>> round(pt.y, 4), round(pt.x, 4)
    (51.5072, -0.1278)
    """
    _validate_dms(dms_str)
    scrubbed = _scrub_dms(dms_str)

    if debug:
        print(f"[dms_to_point] scrubbed → {scrubbed!r}")

    match = _DMS_PATTERN.search(scrubbed)
    if not match:
        raise ValueError(
            _warn(
                "dms_to_point",
                f"Could not parse DMS pair. Input: {dms_str!r} "
                f"(scrubbed: {scrubbed!r})",
            )
        )

    g = match.groupdict()
    if debug:
        print(f"[dms_to_point] groups → {g}")

    lat_deg = float(g["lat_deg"])
    lat_min = float(g["lat_min"]) if g["lat_min"] else 0.0
    lat_sec = float(g["lat_sec"]) if g["lat_sec"] else 0.0
    lat_sign = 1.0 if g["lat_dir"].upper() == "N" else -1.0
    lat_dd = lat_sign * (lat_deg + lat_min / 60.0 + lat_sec / 3600.0)

    lon_deg = float(g["lon_deg"])
    lon_min = float(g["lon_min"]) if g["lon_min"] else 0.0
    lon_sec = float(g["lon_sec"]) if g["lon_sec"] else 0.0
    lon_sign = 1.0 if g["lon_dir"].upper() == "E" else -1.0
    lon_dd = lon_sign * (lon_deg + lon_min / 60.0 + lon_sec / 3600.0)

    if not (-90 <= lat_dd <= 90):
        raise ValueError(
            _warn("dms_to_point", f"Latitude out of range: {lat_dd}")
        )
    if not (-180 <= lon_dd <= 180):
        raise ValueError(
            _warn("dms_to_point", f"Longitude out of range: {lon_dd}")
        )

    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


def ddm_to_point(ddm_str: str, return_latlon: bool = False) -> Point:
    """
    Parse a Degrees Decimal Minutes (DDM) lat/lon pair string to a Shapely ``Point``.

    DDM format expresses coordinates as integer degrees plus decimal minutes,
    e.g. ``"51 30.4 N 0 7.7 W"``, without a separate seconds component.

    Parameters
    ----------
    ddm_str : str
        DDM coordinate pair string.  Expected structure:
        ``<deg> <decimal_min> <N|S>  <deg> <decimal_min> <E|W>``.
        Various separators and symbols are tolerated.
    return_latlon : bool, optional
        If ``True``, return ``(lat_dd, lon_dd)`` tuple instead of a
        Shapely ``Point``.  Default is ``False``.

    Returns
    -------
    shapely.geometry.Point or tuple of float
        * ``Point(longitude, latitude)`` when *return_latlon* is ``False``.
        * ``(latitude, longitude)`` decimal-degree tuple when
          *return_latlon* is ``True``.

    Raises
    ------
    ValueError
        If *ddm_str* is empty, lacks proper N/S and E/W indicators,
        cannot be parsed, or produces out-of-bounds coordinates.

    See Also
    --------
    dms_to_point : Parse Degrees Minutes Seconds format instead.
    point_to_ddm : Reverse conversion — Shapely ``Point`` → DDM string pair.
    coordinate_to_point : Unified dispatcher that auto-detects format.

    Examples
    --------
    >>> pt = ddm_to_point("51 30.4 N 0 7.7 W")
    >>> round(pt.y, 4), round(pt.x, 4)
    (51.5067, -0.1283)
    """
    _validate_ddm_pair(ddm_str)

    match = _DDM_PATTERN.search(ddm_str)
    if not match:
        raise ValueError(
            _warn("ddm_to_point", f"Could not parse DDM pair: {ddm_str!r}")
        )

    g = match.groupdict()
    lat_dd = (1.0 if g["lat_dir"].upper() == "N" else -1.0) * (
        float(g["lat_deg"]) + float(g["lat_min"]) / 60.0
    )
    lon_dd = (1.0 if g["lon_dir"].upper() == "E" else -1.0) * (
        float(g["lon_deg"]) + float(g["lon_min"]) / 60.0
    )

    if not (-90.0 <= lat_dd <= 90.0):
        raise ValueError(
            _warn("ddm_to_point", f"Latitude out of range: {lat_dd}")
        )
    if not (-180.0 <= lon_dd <= 180.0):
        raise ValueError(
            _warn("ddm_to_point", f"Longitude out of range: {lon_dd}")
        )

    return (lat_dd, lon_dd) if return_latlon else Point(lon_dd, lat_dd)


# ── Unified coordinate dispatcher ─────────────────────────────────────────────

def coordinate_to_point(coord_input) -> Point:
    """
    Convert any supported coordinate format to a Shapely ``Point``.

    The input format is auto-detected in the following order:

    1. ``(lat, lon)`` numeric tuple or list → decimal degrees.
    2. MGRS string (starts with 1–2 digits then a C–X band letter).
    3. DMS string (contains ``°``, ``'``, ``"`` symbols or two
       ``N``/``S``/``E``/``W`` direction letters with digits).
    4. DDM string (decimal-minutes pattern).

    Parameters
    ----------
    coord_input : tuple, list, or str
        Supported formats:

        * ``(latitude, longitude)`` numeric tuple or list.
        * DMS string — ``"39°48'18\\" N 089°38'42\\" W"``
        * DDM string — ``"39 48.3 N 089 38.7 W"``
        * MGRS string — ``"18TWL8396007450"``

    Returns
    -------
    shapely.geometry.Point
        Point with ``x = longitude``, ``y = latitude`` in WGS-84.

    Raises
    ------
    TypeError
        If *coord_input* is not a ``str``, ``tuple``, or ``list``.
    ValueError
        If the string does not match any recognised coordinate format.

    See Also
    --------
    dms_to_point : Parse DMS format directly.
    ddm_to_point : Parse DDM format directly.
    mgrs_to_point : Parse MGRS format directly.

    Examples
    --------
    >>> pt = coordinate_to_point((51.5074, -0.1278))
    >>> round(pt.x, 4)
    -0.1278

    >>> pt = coordinate_to_point("51°30'26\\" N 0°7'40\\" W")
    >>> round(pt.y, 2)
    51.51

    >>> pt = coordinate_to_point("30UXC0529398803")
    >>> isinstance(pt, Point)
    True
    """
    if isinstance(coord_input, (tuple, list)) and len(coord_input) == 2:
        return latlon_to_point(coord_input)

    if isinstance(coord_input, str):
        cleaned = coord_input.strip()
        if _MGRS_DETECT.match(cleaned.upper()):
            return mgrs_to_point(cleaned)
        if _DMS_SYMBOLS.search(cleaned) or (
            len(_NSEW.findall(cleaned)) == 2
            and re.search(r"\d", cleaned)
        ):
            return dms_to_point(cleaned)
        if _DDM_DETECT.search(cleaned):
            return ddm_to_point(cleaned)
        raise ValueError(
            _warn(
                "coordinate_to_point",
                f"Unrecognised coordinate string: {coord_input!r}",
            )
        )

    raise TypeError(
        _warn(
            "coordinate_to_point",
            f"Received unsupported type {type(coord_input).__name__}. "
            "Expected str or (lat, lon) tuple.",
        )
    )


# ── Point formatters ──────────────────────────────────────────────────────────

def point_to_dms(pt: Point) -> Tuple[str, str]:
    """
    Return a Shapely ``Point`` as a (lat, lon) DMS string pair.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 point (``x = longitude``, ``y = latitude``).

    Returns
    -------
    tuple of (str, str)
        ``(lat_dms, lon_dms)`` where each string uses the format
        ``{deg}°{min:02d}'{sec:05.2f}"{N|S|E|W}``, for example
        ``("51°30'26.16\\"N", "0°07'40.08\\"W")``.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    dms_to_point : Reverse conversion — DMS string → Shapely ``Point``.
    point_to_ddm : Return the point in DDM format instead.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> lat_dms, lon_dms = point_to_dms(Point(-0.1278, 51.5074))
    >>> lat_dms.endswith("N")
    True
    >>> lon_dms.endswith("W")
    True
    """
    _validate_point(pt)
    return _dd_to_dms(pt.y, is_lat=True), _dd_to_dms(pt.x, is_lat=False)


def point_to_ddm(pt: Point) -> Tuple[str, str]:
    """
    Return a Shapely ``Point`` as a (lat, lon) DDM string pair.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 point (``x = longitude``, ``y = latitude``).

    Returns
    -------
    tuple of (str, str)
        ``(lat_ddm, lon_ddm)`` where each string uses the format
        ``{deg}°{min:06.3f}'{N|S|E|W}``, for example
        ``("51°30.444'N", "0°07.668'W")``.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    ddm_to_point : Reverse conversion — DDM string → Shapely ``Point``.
    point_to_dms : Return the point in DMS format instead.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> lat_ddm, lon_ddm = point_to_ddm(Point(-0.1278, 51.5074))
    >>> lat_ddm.endswith("N")
    True
    >>> lon_ddm.endswith("W")
    True
    """
    _validate_point(pt)
    return _dd_to_ddm(pt.y, is_lat=True), _dd_to_ddm(pt.x, is_lat=False)


def point_to_mgrs(pt: Point, precision: int = 5) -> str:
    """
    Return a Shapely ``Point`` as an MGRS coordinate string.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 point (``x = longitude``, ``y = latitude``).
    precision : int, optional
        MGRS precision level in [0, 5].  Controls the number of
        easting/northing digit pairs:

        =========  ====================
        Precision  Approximate accuracy
        =========  ====================
        0          100 km
        1          10 km
        2          1 km
        3          100 m
        4          10 m
        5          1 m  *(default)*
        =========  ====================

    Returns
    -------
    str
        MGRS coordinate string, e.g. ``"30UXC0529398803"``.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or *precision*
        is not an ``int``.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds, or *precision*
        falls outside [0, 5].

    See Also
    --------
    mgrs_to_point : Reverse conversion — MGRS string → Shapely ``Point``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> mgrs = point_to_mgrs(Point(-0.1278, 51.5074))
    >>> isinstance(mgrs, str) and len(mgrs) > 0
    True
    """
    _validate_point(pt)
    _validate_mgrs_precision(precision)
    return _MGRS_INSTANCE.toMGRS(pt.y, pt.x, MGRSPrecision=precision)


# ── Box conversion ────────────────────────────────────────────────────────────

def geometry_to_box(geometry: BaseGeometry, as_polygon: bool = False) -> Union[str, Polygon]:
    """
    Convert a Shapely geometry to its axis-aligned bounding box.

    Computes the bounding box from *geometry* and returns it either as a
    PostGIS ``BOX(...)`` string (default) or as a Shapely ``Polygon`` via
    the geometry's :attr:`~shapely.geometry.base.BaseGeometry.envelope`
    property.  ``Point`` geometries are rejected because a single point
    has coincident bounds and cannot form a meaningful bounding box or
    polygon.

    Parameters
    ----------
    geometry : shapely.geometry.base.BaseGeometry
        Any Shapely geometry except ``Point`` — e.g. ``LineString``,
        ``Polygon``, ``MultiPolygon``, ``GeometryCollection``.
    as_polygon : bool, optional
        Controls the return type:

        * ``False`` (default) — return a PostGIS BOX string of the form
          ``"BOX(minx miny, maxx maxy)"``, suitable for storage or database
          queries.
        * ``True`` — return the bounding box as a Shapely ``Polygon``
          using the geometry's :attr:`envelope` property, suitable for
          spatial operations.

    Returns
    -------
    str
        PostGIS BOX string when *as_polygon* is ``False``.
    shapely.geometry.Polygon
        Axis-aligned rectangular polygon when *as_polygon* is ``True``.

    Raises
    ------
    TypeError
        If *geometry* is not a Shapely geometry object.
        If *as_polygon* is not a ``bool``.
    ValueError
        If *geometry* is a ``Point`` (degenerate zero-area bounding box).

    Examples
    --------
    >>> from shapely.geometry import Polygon
    >>> poly = Polygon([(-0.14, 51.49), (-0.11, 51.49), (-0.11, 51.52), (-0.14, 51.52)])
    >>> geometry_to_box(poly)
    'BOX(-0.14 51.49,-0.11 51.52)'

    >>> envelope = geometry_to_box(poly, as_polygon=True)
    >>> isinstance(envelope, Polygon)
    True
    >>> envelope.bounds == poly.bounds
    True
    """
    if not isinstance(geometry, BaseGeometry):
        raise TypeError(
            _warn(
                "geometry_to_box",
                f"Expected a Shapely geometry, got {type(geometry).__name__}.",
            )
        )
    if isinstance(geometry, Point):
        raise ValueError(
            _warn(
                "geometry_to_box",
                "Does not accept Point geometries — a single point has coincident "
                "bounds and cannot form a meaningful bounding box.",
            )
        )
    if not isinstance(as_polygon, bool):
        raise TypeError(
            _warn(
                "geometry_to_box",
                f"as_polygon must be a bool, got {type(as_polygon).__name__}.",
            )
        )

    if as_polygon:
        return geometry.envelope

    minx, miny, maxx, maxy = geometry.bounds
    return f"BOX({minx} {miny},{maxx} {maxy})"


def box_to_polygon(box_str: str) -> Polygon:
    """
    Parse a PostGIS ``BOX(minx miny, maxx maxy)`` string to a Shapely ``Polygon``.

    PostGIS BOX format is not standard WKT and cannot be parsed by
    :func:`shapely.wkt.loads` directly.  This function extracts the two
    corner coordinates and constructs an axis-aligned rectangular
    ``Polygon`` via :func:`shapely.geometry.box`.

    Parameters
    ----------
    box_str : str
        PostGIS BOX string, e.g. ``"BOX(-0.14 51.49, -0.11 51.52)"``.
        Whitespace around values is tolerated.

    Returns
    -------
    shapely.geometry.Polygon
        Axis-aligned rectangular polygon for the bounding box.

    Raises
    ------
    TypeError
        If *box_str* is not a ``str``.
    ValueError
        If *box_str* does not match the expected BOX format, or if the
        extracted coordinates are outside WGS-84 bounds.

    See Also
    --------
    geometry_to_box : Geometry → BOX string (inverse direction).

    Examples
    --------
    >>> poly = box_to_polygon("BOX(-0.14 51.49, -0.11 51.52)")
    >>> poly.bounds
    (-0.14, 51.49, -0.11, 51.52)
    """
    if not isinstance(box_str, str):
        raise TypeError(
            _warn(
                "box_to_polygon",
                f"Expected a str, got {type(box_str).__name__}.",
            )
        )
    match = _BOX_PATTERN.search(box_str.strip())
    if not match:
        raise ValueError(
            _warn(
                "box_to_polygon",
                f"Could not parse BOX string: {box_str!r}. "
                "Expected format: BOX(minx miny, maxx maxy)",
            )
        )
    minx, miny, maxx, maxy = (float(match.group(i)) for i in range(1, 5))
    _validate_longitude(minx)
    _validate_latitude(miny)
    _validate_longitude(maxx)
    _validate_latitude(maxy)
    return shapely_box(minx, miny, maxx, maxy)


# ── Aspect-ratio utilities ────────────────────────────────────────────────────

def get_ratio(geom: BaseGeometry, tolerance: float = 1e-8) -> float:
    """
    Compute the aspect ratio (width / height) of a Shapely geometry's bounding box.

    Parameters
    ----------
    geom : BaseGeometry
        Any non-empty Shapely geometry with non-degenerate bounds.
    tolerance : float, default 1e-8
        Minimum dimension size; smaller values raise ValueError.

    Returns
    -------
    float
        Width divided by height.
        >1.0 → landscape, =1.0 → square, <1.0 → portrait.

    Raises
    ------
    ValueError
        If the geometry is empty or has degenerate (near-zero) dimensions.

    Examples
    --------
    >>> from shapely.geometry import box
    >>> get_ratio(box(0, 0, 16, 9))
    1.7777...
    """
    if geom.is_empty:
        raise ValueError(
            _warn("get_ratio", "Cannot compute aspect ratio of empty geometry.")
        )

    minx, miny, maxx, maxy = geom.bounds
    width  = maxx - minx
    height = maxy - miny

    if width < tolerance or height < tolerance:
        raise ValueError(
            _warn(
                "get_ratio",
                f"Geometry has degenerate bounding box "
                f"(width={width:.6g}, height={height:.6g}).",
            )
        )

    return width / height


def get_bounds(
    geom: BaseGeometry,
    target_aspect: float,
    fit_mode: Literal["contain", "cover", "fit-width", "fit-height"] = "contain",
    tolerance: float = 1e-8,
) -> Tuple[float, float, float, float]:
    """
    Return adjusted bounding-box bounds (minx, miny, maxx, maxy) to match a
    target aspect ratio.

    The centre of the bounding box is preserved in all modes.  Which dimension
    is held fixed and which is adjusted depends on fit_mode.

    Parameters
    ----------
    geom : BaseGeometry
        Any non-empty Shapely geometry with non-degenerate bounds.
    target_aspect : float
        Desired width/height ratio (must be > 0).
    fit_mode : {"contain", "cover", "fit-width", "fit-height"}, default "contain"
        How the bounding box is resized to reach the target ratio:

        "contain"    — Expand the short dimension so the entire geometry fits
                       inside the new box.  Nothing is cropped.
                       Equivalent to CSS ``object-fit: contain``.
        "cover"      — Shrink the long dimension so the new box fills the
                       target ratio exactly.  Edges may be cropped.
                       Equivalent to CSS ``object-fit: cover``.
        "fit-width"  — Hold width fixed; derive height from target_aspect.
                       Use when the slide placeholder has a fixed column width.
        "fit-height" — Hold height fixed; derive width from target_aspect.
                       Use when the slide placeholder has a fixed row height.
    tolerance : float, default 1e-8
        Minimum dimension size; smaller values raise ValueError.

    Returns
    -------
    tuple[float, float, float, float]
        Adjusted bounds as (minx, miny, maxx, maxy).

    Raises
    ------
    ValueError
        If the geometry is empty, has degenerate dimensions, or inputs are invalid.

    Examples
    --------
    >>> from shapely.geometry import box
    >>> geom = box(0, 0, 10, 6)         # current aspect ≈ 1.667
    >>> get_bounds(geom, 16/9)           # target ≈ 1.778 → expand width
    (-0.333..., 0.0, 10.333..., 6.0)

    >>> get_bounds(geom, 16/9, fit_mode="cover")   # shrink height
    (0.0, 0.5625, 10.0, 5.4375)

    >>> get_bounds(geom, 16/9, fit_mode="fit-width")   # fix width, adjust height
    (0.0, 0.9375, 10.0, 5.0625)

    >>> get_bounds(geom, 16/9, fit_mode="fit-height")  # fix height, adjust width
    (-0.333..., 0.0, 10.333..., 6.0)
    """
    if geom.is_empty:
        raise ValueError(
            _warn("get_bounds", "Cannot adjust aspect ratio of empty geometry.")
        )
    if target_aspect <= 0:
        raise ValueError(
            _warn(
                "get_bounds",
                f"target_aspect must be positive, got {target_aspect}.",
            )
        )
    if fit_mode not in ("contain", "cover", "fit-width", "fit-height"):
        raise ValueError(
            _warn(
                "get_bounds",
                f"fit_mode must be 'contain', 'cover', 'fit-width', or "
                f"'fit-height', got {fit_mode!r}.",
            )
        )

    minx, miny, maxx, maxy = geom.bounds
    width  = maxx - minx
    height = maxy - miny

    if width < tolerance or height < tolerance:
        raise ValueError(
            _warn(
                "get_bounds",
                f"Geometry has degenerate bounding box "
                f"(width={width:.6g}, height={height:.6g}).",
            )
        )

    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    current_aspect = width / height

    if fit_mode == "contain":
        if current_aspect > target_aspect:
            # Too wide → expand height
            half_h = (width / target_aspect) / 2
            return (minx, cy - half_h, maxx, cy + half_h)
        else:
            # Too tall (or square) → expand width
            half_w = (height * target_aspect) / 2
            return (cx - half_w, miny, cx + half_w, maxy)

    elif fit_mode == "cover":
        if current_aspect > target_aspect:
            # Too wide → shrink width
            half_w = (height * target_aspect) / 2
            return (cx - half_w, miny, cx + half_w, maxy)
        else:
            # Too tall (or square) → shrink height
            half_h = (width / target_aspect) / 2
            return (minx, cy - half_h, maxx, cy + half_h)

    elif fit_mode == "fit-width":
        # Width is fixed; derive height from target_aspect
        half_h = (width / target_aspect) / 2
        return (minx, cy - half_h, maxx, cy + half_h)

    else:  # "fit-height"
        # Height is fixed; derive width from target_aspect
        half_w = (height * target_aspect) / 2
        return (cx - half_w, miny, cx + half_w, maxy)


def get_polygon(
    geom: BaseGeometry,
    target_aspect: float,
    fit_mode: Literal["contain", "cover", "fit-width", "fit-height"] = "contain",
    tolerance: float = 1e-8,
) -> Polygon:
    """
    Return a rectangular Polygon with the target aspect ratio, centred on the
    input geometry's bounding box.

    A thin wrapper around :func:`get_bounds` that returns a Shapely ``Polygon``
    instead of raw bounds.  Suitable for geometry operations, masking, and
    clipping plots before export to PowerPoint.

    Parameters
    ----------
    geom : BaseGeometry
        Input geometry (must be non-empty with non-degenerate bounds).
    target_aspect : float
        Desired width/height ratio (must be > 0).
    fit_mode : {"contain", "cover", "fit-width", "fit-height"}, default "contain"
        See :func:`get_bounds` for a full description of each mode.
    tolerance : float, default 1e-8
        Forwarded to :func:`get_bounds`.

    Returns
    -------
    Polygon
        Axis-aligned rectangle matching the target aspect ratio.

    Examples
    --------
    >>> from shapely.geometry import box
    >>> poly = get_polygon(box(0, 0, 10, 6), 16/9)
    >>> round(poly.area, 4)
    64.0
    """
    return shapely_box(
        *get_bounds(
            geom=geom,
            target_aspect=target_aspect,
            fit_mode=fit_mode,
            tolerance=tolerance,
        )
    )
