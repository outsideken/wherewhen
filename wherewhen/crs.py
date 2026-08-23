"""
wherewhen.crs
============
Non-WGS-84 coordinate reference system conversions.

Covers the Chinese national standard systems (GCJ-02 and BD-09) and the
Soviet/Russian SK-42 / Pulkovo 1942 system.  All functions accept and return
Shapely ``Point`` objects with coordinates in decimal degrees
(``x = longitude``, ``y = latitude``).

Use :func:`convert_crs` as a single entry point when the source and target
CRS are determined at runtime.  The individual conversion functions are also
available for direct use.

Soft dependency — ``pyproj`` — is required only for the SK-42 conversions
and is detected at import time.  Functions that need it raise
:class:`ImportError` with an installation hint if it is unavailable.

Module Attributes
-----------------
WGS84_A : float
    WGS-84 semi-major axis in metres (6 378 137.0).
WGS84_F : float
    WGS-84 flattening (1 / 298.257223563).

Functions
---------
convert_crs
    Convert a Point between any two supported CRS identifiers.
wgs84_to_cn_gcj02
    Convert a WGS-84 point to GCJ-02 (China national standard).
cn_gcj02_to_wgs84
    Convert a GCJ-02 point to WGS-84.
wgs84_to_cn_bd09
    Convert a WGS-84 point to BD-09 (Baidu).
cn_bd09_to_wgs84
    Convert a BD-09 point to WGS-84.
ru_sk42_to_wgs84
    Convert a SK-42 / Pulkovo 1942 point to WGS-84.
wgs84_to_ru_sk42
    Convert a WGS-84 point to SK-42 / Pulkovo 1942.

Toolkit
-------
Part of the ``wherewhen`` package (successor to ``geocore``).  Import from
this module directly.  SK-42 conversions require ``pyproj``; missing
dependency raises ``❌ [function_name] …`` via :mod:`wherewhen._messages`.
"""

import math
from typing import Dict, Tuple

from shapely.geometry import Point

from wherewhen._messages import skip as _skip, warn as _warn
from wherewhen._validators import _validate_point

# ── Optional-dependency guard ─────────────────────────────────────────────────
try:
    from pyproj import Transformer as _Transformer
    _PYPROJ_AVAILABLE = True
    _SK42_TO_WGS84 = _Transformer.from_crs("EPSG:4284", "EPSG:4326", always_xy=True)
    _WGS84_TO_SK42 = _Transformer.from_crs("EPSG:4326", "EPSG:4284", always_xy=True)
except ImportError:
    _PYPROJ_AVAILABLE = False
    _SK42_TO_WGS84 = None
    _WGS84_TO_SK42 = None

# ── Constants ─────────────────────────────────────────────────────────────────

# WGS-84 ellipsoid parameters (exposed for user reference)
WGS84_A: float = 6378137.0
WGS84_F: float = 1 / 298.257223563

# GCJ-02 uses the Krassovsky ellipsoid
_GCJ_A:  float = 6378245.0
_GCJ_EE: float = 0.00669342162296594323

# BD-09 applies a further obfuscation layer on top of GCJ-02
_BD_PI: float = math.pi * 3000.0 / 180.0

# Approximate bounding box for mainland China (used to skip the offset outside China)
_CN_LON_MIN, _CN_LON_MAX = 72.004, 137.8347
_CN_LAT_MIN, _CN_LAT_MAX = 0.8293, 55.8271

__all__ = [
    "WGS84_A",
    "WGS84_F",
    "convert_crs",
    "wgs84_to_cn_gcj02",
    "cn_gcj02_to_wgs84",
    "wgs84_to_cn_bd09",
    "cn_bd09_to_wgs84",
    "ru_sk42_to_wgs84",
    "wgs84_to_ru_sk42",
]


# ── Private helpers ───────────────────────────────────────────────────────────

def _gcj02_offset(lon: float, lat: float) -> Tuple[float, float]:
    """Return the (dlon, dlat) GCJ-02 obfuscation offset for a WGS-84 point."""
    dlat = (
        -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat
        + 0.1 * lon * lat + 0.2 * math.sqrt(abs(lon))
        + (20.0 * math.sin(6.0 * lon * math.pi)
           + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
        + (20.0 * math.sin(lat * math.pi)
           + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
        + (160.0 * math.sin(lat / 12.0 * math.pi)
           + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    )
    dlon = (
        300.0 + lon + 2.0 * lat + 0.1 * lon * lon
        + 0.1 * lon * lat + 0.1 * math.sqrt(abs(lon))
        + (20.0 * math.sin(6.0 * lon * math.pi)
           + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
        + (20.0 * math.sin(lon * math.pi)
           + 40.0 * math.sin(lon / 3.0 * math.pi)) * 2.0 / 3.0
        + (150.0 * math.sin(lon / 12.0 * math.pi)
           + 300.0 * math.sin(lon / 30.0 * math.pi)) * 2.0 / 3.0
    )
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _GCJ_EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * math.pi)
    dlon = (dlon * 180.0) / (_GCJ_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return dlon, dlat


def _in_china(lon: float, lat: float) -> bool:
    """Return True if the coordinate falls within the mainland China bounding box."""
    return _CN_LON_MIN <= lon <= _CN_LON_MAX and _CN_LAT_MIN <= lat <= _CN_LAT_MAX


# ── Chinese coordinate conversions ────────────────────────────────────────────

def wgs84_to_cn_gcj02(pt: Point) -> Point:
    """
    Convert a WGS-84 point to GCJ-02 (China national standard / Mars Coordinates).

    GCJ-02 is a coordinate obfuscation system mandated by the Chinese
    government for all official maps published in China.  It applies a
    non-linear offset to WGS-84 coordinates based on the Krassovsky
    ellipsoid.  All points outside mainland China are returned unchanged.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        GCJ-02 location.  Points outside mainland China are returned as-is.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    cn_gcj02_to_wgs84 : Reverse conversion.
    wgs84_to_cn_bd09 : Convert directly to Baidu BD-09.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "WGS84", "GCJ02")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_wgs = Point(116.3912, 39.9073)   # Beijing, WGS-84
    >>> pt_gcj = wgs84_to_cn_gcj02(pt_wgs)
    >>> abs(pt_gcj.x - pt_wgs.x) > 0.001   # offset applied
    True
    """
    _validate_point(pt)
    lon, lat = pt.x, pt.y
    if not _in_china(lon, lat):
        return pt
    dlon, dlat = _gcj02_offset(lon - 105.0, lat - 35.0)
    return Point(lon + dlon, lat + dlat)


def cn_gcj02_to_wgs84(pt: Point) -> Point:
    """
    Convert a GCJ-02 (China national standard) point to WGS-84.

    Applies an iterative correction to reverse the GCJ-02 obfuscation
    offset.  Converges to sub-metre accuracy within a few iterations.

    Parameters
    ----------
    pt : shapely.geometry.Point
        GCJ-02 location (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        WGS-84 location.  Points outside mainland China are returned as-is.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    wgs84_to_cn_gcj02 : Forward conversion.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "GCJ02", "WGS84")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_gcj = Point(116.3974, 39.9088)
    >>> pt_wgs = cn_gcj02_to_wgs84(pt_gcj)
    >>> abs(pt_wgs.x - pt_gcj.x) > 0.001
    True
    """
    _validate_point(pt)
    lon, lat = pt.x, pt.y
    if not _in_china(lon, lat):
        return pt
    wgs_lon, wgs_lat = lon, lat
    for _ in range(5):
        dlon, dlat = _gcj02_offset(wgs_lon - 105.0, wgs_lat - 35.0)
        wgs_lon = lon - dlon
        wgs_lat = lat - dlat
    return Point(wgs_lon, wgs_lat)


def wgs84_to_cn_bd09(pt: Point) -> Point:
    """
    Convert a WGS-84 point to BD-09 (Baidu coordinate system).

    BD-09 is Baidu's proprietary coordinate system, which applies a
    further obfuscation offset on top of GCJ-02.  The conversion is
    performed in two steps: WGS-84 → GCJ-02 → BD-09.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        BD-09 location.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    cn_bd09_to_wgs84 : Reverse conversion.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "WGS84", "BD09")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_bd = wgs84_to_cn_bd09(Point(116.3912, 39.9073))
    >>> isinstance(pt_bd, Point)
    True
    """
    _validate_point(pt)
    gcj = wgs84_to_cn_gcj02(pt)
    x, y = gcj.x, gcj.y
    z = math.sqrt(x * x + y * y) + 0.00002 * math.sin(y * _BD_PI)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * _BD_PI)
    return Point(z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006)


def cn_bd09_to_wgs84(pt: Point) -> Point:
    """
    Convert a BD-09 (Baidu) point to WGS-84.

    The conversion is performed in two steps: BD-09 → GCJ-02 → WGS-84.

    Parameters
    ----------
    pt : shapely.geometry.Point
        BD-09 location (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        WGS-84 location.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    wgs84_to_cn_bd09 : Forward conversion.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "BD09", "WGS84")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_wgs = cn_bd09_to_wgs84(Point(116.4040, 39.9150))
    >>> isinstance(pt_wgs, Point)
    True
    """
    _validate_point(pt)
    x = pt.x - 0.0065
    y = pt.y - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _BD_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _BD_PI)
    gcj = Point(z * math.cos(theta), z * math.sin(theta))
    return cn_gcj02_to_wgs84(gcj)


# ── Russian coordinate conversions ────────────────────────────────────────────

def ru_sk42_to_wgs84(pt: Point) -> Point:
    """
    Convert a SK-42 (Pulkovo 1942) geographic point to WGS-84.

    SK-42 is the geodetic coordinate system used on Soviet and Russian
    military maps.  It is based on the Krassovsky 1940 ellipsoid and the
    Pulkovo 1942 datum.  Conversion to WGS-84 requires a datum shift
    handled by ``pyproj``.

    Parameters
    ----------
    pt : shapely.geometry.Point
        SK-42 geographic location in decimal degrees
        (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).

    Raises
    ------
    ImportError
        If ``pyproj`` is not installed.  Install with: ``pip install pyproj``.
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside valid bounds.

    See Also
    --------
    wgs84_to_ru_sk42 : Reverse conversion.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "SK42", "WGS84")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_wgs = ru_sk42_to_wgs84(Point(37.618, 55.752))   # approx. Moscow
    >>> isinstance(pt_wgs, Point)
    True
    """
    if not _PYPROJ_AVAILABLE:
        raise ImportError(
            _skip(
                "ru_sk42_to_wgs84",
                "pyproj is required for SK-42 conversions. "
                "Install with: pip install pyproj",
            )
        )
    _validate_point(pt)
    lon, lat = _SK42_TO_WGS84.transform(pt.x, pt.y)
    return Point(lon, lat)


def wgs84_to_ru_sk42(pt: Point) -> Point:
    """
    Convert a WGS-84 point to SK-42 (Pulkovo 1942) geographic coordinates.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location in decimal degrees
        (``x = longitude``, ``y = latitude``).

    Returns
    -------
    shapely.geometry.Point
        SK-42 location in decimal degrees
        (``x = longitude``, ``y = latitude``).

    Raises
    ------
    ImportError
        If ``pyproj`` is not installed.  Install with: ``pip install pyproj``.
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    ru_sk42_to_wgs84 : Reverse conversion.
    convert_crs : Unified dispatcher — ``convert_crs(pt, "WGS84", "SK42")``.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt_sk42 = wgs84_to_ru_sk42(Point(37.618, 55.752))
    >>> isinstance(pt_sk42, Point)
    True
    """
    if not _PYPROJ_AVAILABLE:
        raise ImportError(
            _skip(
                "wgs84_to_ru_sk42",
                "pyproj is required for SK-42 conversions. "
                "Install with: pip install pyproj",
            )
        )
    _validate_point(pt)
    lon, lat = _WGS84_TO_SK42.transform(pt.x, pt.y)
    return Point(lon, lat)


# ── Dispatcher ────────────────────────────────────────────────────────────────

_CRS_CONVERSIONS: Dict[Tuple[str, str], object] = {
    ("WGS84", "GCJ02"): wgs84_to_cn_gcj02,
    ("GCJ02", "WGS84"): cn_gcj02_to_wgs84,
    ("WGS84", "BD09"):  wgs84_to_cn_bd09,
    ("BD09",  "WGS84"): cn_bd09_to_wgs84,
    ("SK42",  "WGS84"): ru_sk42_to_wgs84,
    ("WGS84", "SK42"):  wgs84_to_ru_sk42,
}

_SUPPORTED_PAIRS = ", ".join(f"{a}→{b}" for a, b in _CRS_CONVERSIONS)


def convert_crs(pt: Point, from_crs: str, to_crs: str) -> Point:
    """
    Convert a Point from one coordinate reference system to another.

    A single entry point for all supported CRS conversions.  CRS identifiers
    are case-insensitive strings.

    Parameters
    ----------
    pt : shapely.geometry.Point
        Input location (``x = longitude``, ``y = latitude``).
    from_crs : str
        Source CRS identifier.  Supported values: ``"WGS84"``, ``"GCJ02"``,
        ``"BD09"``, ``"SK42"``.
    to_crs : str
        Target CRS identifier.  Same set of values as *from_crs*.

    Returns
    -------
    shapely.geometry.Point
        Converted location in the target CRS.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`.
    ValueError
        If the *from_crs* / *to_crs* pair is not supported.
    ImportError
        If the conversion requires ``pyproj`` and it is not installed
        (SK-42 conversions only).

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> pt = Point(116.3912, 39.9073)
    >>> pt_gcj = convert_crs(pt, "WGS84", "GCJ02")
    >>> pt_back = convert_crs(pt_gcj, "GCJ02", "WGS84")
    >>> abs(pt_back.x - pt.x) < 0.0001
    True
    """
    key = (from_crs.upper(), to_crs.upper())
    fn = _CRS_CONVERSIONS.get(key)
    if fn is None:
        raise ValueError(
            _warn(
                "convert_crs",
                f"Unsupported CRS conversion: {from_crs!r} → {to_crs!r}. "
                f"Supported pairs: {_SUPPORTED_PAIRS}",
            )
        )
    return fn(pt)
