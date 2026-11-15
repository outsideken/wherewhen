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
from functools import lru_cache
from typing import Tuple

from shapely import wkt as _wkt
from shapely.geometry import Point
from shapely.prepared import prep as _prep

from wherewhen._china_region import CHINA_REGION_WKT as _CHINA_REGION_WKT
from wherewhen._messages import warn as _warn
from wherewhen._validators import _validate_bool, _validate_point, _validate_string

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


@lru_cache(maxsize=1)
def _china_region():
    """The GCJ-02/BD-09 region as a prepared geometry, parsed on first use."""
    return _prep(_wkt.loads(_CHINA_REGION_WKT))


def _in_china(lon: float, lat: float) -> bool:
    """
    Return True if a WGS-84 coordinate is where GCJ-02 and BD-09 apply.

    That is mainland China, Hong Kong or Macau, or within the 0.2° sea
    margin around them (see :mod:`wherewhen._china_region`).  Taiwan and
    every other country are outside.
    """
    return _china_region().intersects(Point(lon, lat))


def _gcj02_forward(lon: float, lat: float) -> Tuple[float, float]:
    """WGS-84 → GCJ-02 offset, applied wherever the point is."""
    dlon, dlat = _gcj02_offset(lon - 105.0, lat - 35.0)
    return lon + dlon, lat + dlat


def _gcj02_inverse(lon: float, lat: float) -> Tuple[float, float]:
    """GCJ-02 → WGS-84 by fixed-point iteration (well under a millimetre)."""
    wgs_lon, wgs_lat = lon, lat
    for _ in range(5):
        dlon, dlat = _gcj02_offset(wgs_lon - 105.0, wgs_lat - 35.0)
        wgs_lon = lon - dlon
        wgs_lat = lat - dlat
    return wgs_lon, wgs_lat


def _bd09_from_gcj02(x: float, y: float) -> Tuple[float, float]:
    """GCJ-02 → BD-09: Baidu's further offset."""
    z = math.sqrt(x * x + y * y) + 0.00002 * math.sin(y * _BD_PI)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * _BD_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def _bd09_to_gcj02(x: float, y: float) -> Tuple[float, float]:
    """BD-09 → GCJ-02: Baidu's published inverse (about 0.2 m off)."""
    x, y = x - 0.0065, y - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _BD_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _BD_PI)
    return z * math.cos(theta), z * math.sin(theta)


def _check_inputs(pt: Point, skip_region_check: bool, func_name: str) -> None:
    """Validate the arguments every Chinese conversion takes."""
    _validate_point(pt, func_name=func_name)
    _validate_bool(skip_region_check, func_name=func_name, name="skip_region_check")


def _converted(coords: Tuple[float, float], func_name: str) -> Point:
    """The converted Point; raises if it left WGS-84 bounds (only near the poles or ±180°)."""
    out = Point(*coords)
    _validate_point(out, func_name=func_name)
    return out


# ── Chinese coordinate conversions ────────────────────────────────────────────
#
# GCJ-02 and BD-09 apply only in mainland China, Hong Kong and Macau (see
# _in_china).  Forward conversions decide on the WGS-84 input; reverse
# conversions decide on the WGS-84 result, so every point inside the region
# converts there and back exactly.  skip_region_check=True applies the
# conversion wherever the point is.

def _wgs84_to_cn_gcj02(
    pt: Point, *, skip_region_check: bool = False, func_name: str = "wgs84_to_cn_gcj02"
) -> Point:
    """Body of :func:`wgs84_to_cn_gcj02`; errors name *func_name*."""
    _check_inputs(pt, skip_region_check, func_name)
    if not skip_region_check and not _in_china(pt.x, pt.y):
        return pt
    return _converted(_gcj02_forward(pt.x, pt.y), func_name)


def wgs84_to_cn_gcj02(pt: Point, *, skip_region_check: bool = False) -> Point:
    """
    Convert a WGS-84 point to GCJ-02 (China national standard / Mars Coordinates).

    GCJ-02 is a coordinate obfuscation system mandated by the Chinese
    government for all official maps published in China.  It applies a
    non-linear offset to WGS-84 coordinates based on the Krassovsky
    ellipsoid.  The offset applies only in mainland China, Hong Kong and
    Macau, including about 20 km of coastal waters; other points, Taiwan
    included, are returned unchanged.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    skip_region_check : bool, default False
        ``True`` applies the offset wherever *pt* is.  Use it when you know
        the coordinates are offset outside the region too, for example
        because the producing software used the older rectangle around
        China, which also covers Korea, Taiwan, northern Vietnam and
        Mongolia.

    Returns
    -------
    shapely.geometry.Point
        GCJ-02 location.  Points outside the region are returned as-is
        (the same object).

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or
        *skip_region_check* is not ``True`` or ``False``.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds, or the converted
        point would be (possible only with *skip_region_check* near the
        poles or ±180°).

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
    >>> wgs84_to_cn_gcj02(Point(126.978, 37.5665)).x   # Seoul: outside
    126.978
    """
    return _wgs84_to_cn_gcj02(
        pt=pt, skip_region_check=skip_region_check, func_name="wgs84_to_cn_gcj02"
    )


def _cn_gcj02_to_wgs84(
    pt: Point, *, skip_region_check: bool = False, func_name: str = "cn_gcj02_to_wgs84"
) -> Point:
    """Body of :func:`cn_gcj02_to_wgs84`; errors name *func_name*."""
    _check_inputs(pt, skip_region_check, func_name)
    wgs = _gcj02_inverse(pt.x, pt.y)
    if not skip_region_check and not _in_china(*wgs):
        return pt
    return _converted(wgs, func_name)


def cn_gcj02_to_wgs84(pt: Point, *, skip_region_check: bool = False) -> Point:
    """
    Convert a GCJ-02 (China national standard) point to WGS-84.

    Applies an iterative correction to reverse the GCJ-02 obfuscation
    offset; it converges to well under a millimetre.  The point is
    converted only if the WGS-84 result is in mainland China, Hong Kong or
    Macau (with about 20 km of coastal waters), so every point
    :func:`wgs84_to_cn_gcj02` offset comes back exactly.

    Parameters
    ----------
    pt : shapely.geometry.Point
        GCJ-02 location (``x = longitude``, ``y = latitude``).
    skip_region_check : bool, default False
        ``True`` removes the offset wherever *pt* is.  Use it when you know
        the coordinates are offset outside the region too (see
        :func:`wgs84_to_cn_gcj02`).

    Returns
    -------
    shapely.geometry.Point
        WGS-84 location.  Points outside the region are returned as-is
        (the same object).

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or
        *skip_region_check* is not ``True`` or ``False``.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds, or the converted
        point would be (possible only with *skip_region_check* near the
        poles or ±180°).

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
    return _cn_gcj02_to_wgs84(
        pt=pt, skip_region_check=skip_region_check, func_name="cn_gcj02_to_wgs84"
    )


def _wgs84_to_cn_bd09(
    pt: Point, *, skip_region_check: bool = False, func_name: str = "wgs84_to_cn_bd09"
) -> Point:
    """Body of :func:`wgs84_to_cn_bd09`; errors name *func_name*."""
    _check_inputs(pt, skip_region_check, func_name)
    if not skip_region_check and not _in_china(pt.x, pt.y):
        return pt
    return _converted(_bd09_from_gcj02(*_gcj02_forward(pt.x, pt.y)), func_name)


def wgs84_to_cn_bd09(pt: Point, *, skip_region_check: bool = False) -> Point:
    """
    Convert a WGS-84 point to BD-09 (Baidu coordinate system).

    BD-09 is Baidu's proprietary coordinate system, which applies a
    further obfuscation offset on top of GCJ-02.  The conversion is
    performed in two steps: WGS-84 → GCJ-02 → BD-09.  Like GCJ-02 it
    applies only in mainland China, Hong Kong and Macau (with about 20 km
    of coastal waters); other points are returned unchanged.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    skip_region_check : bool, default False
        ``True`` applies both offsets wherever *pt* is.  Use it when you
        know the coordinates are offset outside the region too (see
        :func:`wgs84_to_cn_gcj02`).

    Returns
    -------
    shapely.geometry.Point
        BD-09 location.  Points outside the region are returned as-is
        (the same object).

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or
        *skip_region_check* is not ``True`` or ``False``.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds, or the converted
        point would be (possible only with *skip_region_check* near the
        poles or ±180°).

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
    return _wgs84_to_cn_bd09(
        pt=pt, skip_region_check=skip_region_check, func_name="wgs84_to_cn_bd09"
    )


def _cn_bd09_to_wgs84(
    pt: Point, *, skip_region_check: bool = False, func_name: str = "cn_bd09_to_wgs84"
) -> Point:
    """Body of :func:`cn_bd09_to_wgs84`; errors name *func_name*."""
    _check_inputs(pt, skip_region_check, func_name)
    wgs = _gcj02_inverse(*_bd09_to_gcj02(pt.x, pt.y))
    if not skip_region_check and not _in_china(*wgs):
        return pt
    return _converted(wgs, func_name)


def cn_bd09_to_wgs84(pt: Point, *, skip_region_check: bool = False) -> Point:
    """
    Convert a BD-09 (Baidu) point to WGS-84.

    The conversion is performed in two steps: BD-09 → GCJ-02 → WGS-84.
    The point is converted only if the WGS-84 result is in mainland China,
    Hong Kong or Macau (with about 20 km of coastal waters).  Baidu's
    inverse is about 0.2 m off.

    Parameters
    ----------
    pt : shapely.geometry.Point
        BD-09 location (``x = longitude``, ``y = latitude``).
    skip_region_check : bool, default False
        ``True`` removes both offsets wherever *pt* is.  Use it when you
        know the coordinates are offset outside the region too (see
        :func:`wgs84_to_cn_gcj02`).

    Returns
    -------
    shapely.geometry.Point
        WGS-84 location.  Points outside the region are returned as-is
        (the same object).

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or
        *skip_region_check* is not ``True`` or ``False``.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds, or the converted
        point would be (possible only with *skip_region_check* near the
        poles or ±180°).

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
    return _cn_bd09_to_wgs84(
        pt=pt, skip_region_check=skip_region_check, func_name="cn_bd09_to_wgs84"
    )


# ── Russian coordinate conversions ────────────────────────────────────────────

def _ru_sk42_to_wgs84(pt: Point, *, func_name: str = "ru_sk42_to_wgs84") -> Point:
    """Body of :func:`ru_sk42_to_wgs84`; errors name *func_name*."""
    if not _PYPROJ_AVAILABLE:
        raise ImportError(
            _warn(
                func_name,
                "pyproj is required for SK-42 conversions. "
                "Install with: pip install pyproj",
            )
        )
    _validate_point(pt, func_name=func_name)
    lon, lat = _SK42_TO_WGS84.transform(pt.x, pt.y)
    return Point(lon, lat)


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
    return _ru_sk42_to_wgs84(pt=pt, func_name="ru_sk42_to_wgs84")


def _wgs84_to_ru_sk42(pt: Point, *, func_name: str = "wgs84_to_ru_sk42") -> Point:
    """Body of :func:`wgs84_to_ru_sk42`; errors name *func_name*."""
    if not _PYPROJ_AVAILABLE:
        raise ImportError(
            _warn(
                func_name,
                "pyproj is required for SK-42 conversions. "
                "Install with: pip install pyproj",
            )
        )
    _validate_point(pt, func_name=func_name)
    lon, lat = _WGS84_TO_SK42.transform(pt.x, pt.y)
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
    return _wgs84_to_ru_sk42(pt=pt, func_name="wgs84_to_ru_sk42")


# ── Dispatcher ────────────────────────────────────────────────────────────────

# Each supported CRS's conversion to and from WGS-84. convert_crs routes any
# other pair through WGS-84; the extra leg adds no measurable error (GCJ-02's
# inverse iterates to well under a millimetre).
_TO_WGS84 = {
    "GCJ02": _cn_gcj02_to_wgs84,
    "BD09":  _cn_bd09_to_wgs84,
    "SK42":  _ru_sk42_to_wgs84,
}
_FROM_WGS84 = {
    "GCJ02": _wgs84_to_cn_gcj02,
    "BD09":  _wgs84_to_cn_bd09,
    "SK42":  _wgs84_to_ru_sk42,
}
_SUPPORTED_CRS = ("WGS84",) + tuple(_TO_WGS84)
_REGION_CRS = ("GCJ02", "BD09")   # the conversions that take skip_region_check


def _leg(table, crs: str, pt: Point, skip_region_check: bool) -> Point:
    """One convert_crs step to or from WGS-84, passing the switch where it applies."""
    kwargs = {"skip_region_check": skip_region_check} if crs in _REGION_CRS else {}
    return table[crs](pt=pt, func_name="convert_crs", **kwargs)


def convert_crs(pt: Point, from_crs: str, to_crs: str, *, skip_region_check: bool = False) -> Point:
    """
    Convert a Point from one coordinate reference system to another.

    A single entry point for all supported CRS conversions, between any two
    of ``"WGS84"``, ``"GCJ02"``, ``"BD09"`` and ``"SK42"`` (case-insensitive).
    The same CRS on both sides returns *pt* unchanged; any pair not involving
    WGS-84 goes through it (e.g. GCJ-02 to BD-09 is GCJ-02 -> WGS-84 -> BD-09).

    Parameters
    ----------
    pt : shapely.geometry.Point
        Input location (``x = longitude``, ``y = latitude``).
    from_crs : str
        Source CRS identifier.  Supported values: ``"WGS84"``, ``"GCJ02"``,
        ``"BD09"``, ``"SK42"``.
    to_crs : str
        Target CRS identifier.  Same set of values as *from_crs*.
    skip_region_check : bool, default False
        Passed to every GCJ-02 or BD-09 step: ``True`` applies those
        offsets wherever the point is (see :func:`wgs84_to_cn_gcj02`).
        It has no effect on SK-42 and WGS-84 steps.

    Returns
    -------
    shapely.geometry.Point
        Converted location in the target CRS.

    Raises
    ------
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or
        *skip_region_check* is not ``True`` or ``False``.
    ValueError
        If *from_crs* or *to_crs* is not a supported CRS, or a converted
        coordinate falls outside WGS-84 bounds.
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

    >>> convert_crs(pt, "wgs84", "WGS84") is pt
    True
    >>> pt_bd = convert_crs(pt_gcj, "GCJ02", "BD09")   # via WGS-84
    """
    _validate_point(pt, func_name="convert_crs")
    _validate_string(from_crs, func_name="convert_crs")
    _validate_string(to_crs, func_name="convert_crs")
    _validate_bool(skip_region_check, func_name="convert_crs", name="skip_region_check")
    source, target = from_crs.upper(), to_crs.upper()
    for name, given in ((source, from_crs), (target, to_crs)):
        if name not in _SUPPORTED_CRS:
            raise ValueError(
                _warn(
                    "convert_crs",
                    f"Unsupported CRS {given!r}. "
                    f"Supported: {', '.join(_SUPPORTED_CRS)} (any case).",
                )
            )
    if source == target:
        return pt
    wgs = pt if source == "WGS84" else _leg(_TO_WGS84, source, pt, skip_region_check)
    return wgs if target == "WGS84" else _leg(_FROM_WGS84, target, wgs, skip_region_check)
