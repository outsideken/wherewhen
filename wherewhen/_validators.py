"""
wherewhen._validators
=====================
Internal validation helpers shared across all wherewhen modules and consumed
by dependent libraries (jematools, h3tools).

Every function raises on invalid input and returns ``None`` on success,
so call sites can use them as simple guard clauses without inspecting a
return value.  Error messages use ``⚠️ [validator_name] …`` via
:mod:`wherewhen._messages`.

Re-exported internally by :mod:`jematools._validators` and
:mod:`h3tools._validators` so dependent modules can validate without
duplicating logic.  Application code should not import this module.

.. note::
   Private to wherewhen.  Use the public API in ``geometry``, ``temporal``,
   or ``crs`` instead.
"""

import re
from datetime import datetime

from shapely.geometry import Point, Polygon

from wherewhen._messages import warn as _warn


# PostGIS BOX format — shared by :func:`wherewhen.geometry.box_to_polygon` and
# jematools CV/bounding-box parsing.
_BOX_PATTERN = re.compile(
    r"BOX\s*\(\s*([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s*\)",
    re.IGNORECASE,
)


# ── Coordinates ───────────────────────────────────────────────────────────────

def _validate_latitude(latitude: float) -> None:
    """
    Raise ``ValueError`` if *latitude* is not a valid WGS-84 latitude.
    """
    if not isinstance(latitude, (int, float)):
        raise ValueError(
            _warn(
                "validate_latitude",
                f"Latitude must be a number, got {type(latitude).__name__}.",
            )
        )
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(
            _warn(
                "validate_latitude",
                f"Latitude must be in [-90, 90], got {latitude}.",
            )
        )


def _validate_longitude(longitude: float) -> None:
    """
    Raise ``ValueError`` if *longitude* is not a valid WGS-84 longitude.
    """
    if not isinstance(longitude, (int, float)):
        raise ValueError(
            _warn(
                "validate_longitude",
                f"Longitude must be a number, got {type(longitude).__name__}.",
            )
        )
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(
            _warn(
                "validate_longitude",
                f"Longitude must be in [-180, 180], got {longitude}.",
            )
        )


def _validate_point(point: Point) -> None:
    """
    Raise if *point* is not a valid, non-empty, in-bounds Shapely ``Point``.
    """
    if not isinstance(point, Point):
        raise TypeError(
            _warn(
                "validate_point",
                f"Expected shapely.geometry.Point, got {type(point).__name__}.",
            )
        )
    if point.is_empty:
        raise ValueError(
            _warn("validate_point", "Cannot use an empty Point.")
        )
    if not (-180 <= point.x <= 180 and -90 <= point.y <= 90):
        raise ValueError(
            _warn(
                "validate_point",
                f"Point coordinates out of WGS-84 bounds: x={point.x}, y={point.y}.",
            )
        )


def _validate_polygon(polygon: Polygon) -> None:
    """
    Raise ``TypeError`` if *polygon* is not a Shapely ``Polygon``.
    """
    if not isinstance(polygon, Polygon):
        raise TypeError(
            _warn(
                "validate_polygon",
                f"Expected shapely.geometry.Polygon, got {type(polygon).__name__}.",
            )
        )


# ── MGRS ──────────────────────────────────────────────────────────────────────

def _validate_mgrs(mgrs_str: str) -> None:
    """
    Raise if *mgrs_str* is not a structurally valid MGRS coordinate string.
    """
    if not isinstance(mgrs_str, str) or not mgrs_str.strip():
        raise TypeError(
            _warn(
                "validate_mgrs",
                f"MGRS coordinate must be a non-empty string, "
                f"got {type(mgrs_str).__name__}.",
            )
        )
    cleaned = re.sub(r"\s+", "", mgrs_str.strip().upper())
    if len(cleaned) < 3:
        raise ValueError(
            _warn(
                "validate_mgrs",
                f"MGRS string too short (got {len(cleaned)} chars): {mgrs_str!r}",
            )
        )
    if not re.match(r"^\d{1,2}[C-X][A-Z]{2}(\d{0,10})$", cleaned):
        raise ValueError(
            _warn(
                "validate_mgrs",
                f"Invalid MGRS format (wrong structure or forbidden letters): "
                f"{mgrs_str!r}",
            )
        )
    zone = int(re.match(r"^(\d{1,2})", cleaned).group(1))
    if not (1 <= zone <= 60):
        raise ValueError(
            _warn(
                "validate_mgrs",
                f"Invalid UTM zone {zone} (must be 1–60).",
            )
        )


def _validate_mgrs_precision(precision: int) -> None:
    """
    Raise if *precision* is not a valid MGRS precision level.
    """
    if not isinstance(precision, int):
        raise TypeError(
            _warn(
                "validate_mgrs_precision",
                f"MGRS precision must be an integer, got {type(precision).__name__}.",
            )
        )
    if not (0 <= precision <= 5):
        raise ValueError(
            _warn(
                "validate_mgrs_precision",
                f"MGRS precision must be in [0, 5], got {precision}.",
            )
        )


# ── DMS / DDM ─────────────────────────────────────────────────────────────────

def _validate_dms(dms_str: str) -> None:
    """
    Perform basic structural validation on a DMS lat/lon pair string.
    """
    if not isinstance(dms_str, str):
        raise TypeError(
            _warn(
                "validate_dms",
                f"DMS string must be str, got {type(dms_str).__name__}.",
            )
        )
    if not dms_str.strip():
        raise ValueError(
            _warn("validate_dms", "DMS string cannot be empty or whitespace.")
        )
    scrubbed = re.sub(r"[°˚º′''″\"˝¨:\s]", "", dms_str).upper()
    ns = len(re.findall(r"[NS]", scrubbed))
    ew = len(re.findall(r"[EW]", scrubbed))
    if ns != 1:
        raise ValueError(
            _warn(
                "validate_dms",
                f"DMS pair must contain exactly one N/S direction, found {ns}.",
            )
        )
    if ew != 1:
        raise ValueError(
            _warn(
                "validate_dms",
                f"DMS pair must contain exactly one E/W direction, found {ew}.",
            )
        )
    if not re.search(r"\d", dms_str):
        raise ValueError(
            _warn("validate_dms", "DMS string must contain at least one digit.")
        )


def _validate_ddm_pair(ddm_str: str) -> None:
    """
    Perform basic structural validation on a DDM lat/lon pair string.
    """
    if not isinstance(ddm_str, str):
        raise TypeError(
            _warn(
                "validate_ddm_pair",
                f"DDM string must be str, got {type(ddm_str).__name__}.",
            )
        )
    if not ddm_str.strip():
        raise ValueError(
            _warn("validate_ddm_pair", "DDM string cannot be empty.")
        )
    scrubbed = re.sub(r"[^NSEW0-9.\s]", "", ddm_str.upper())
    ns = len(re.findall(r"[NS]", scrubbed))
    ew = len(re.findall(r"[EW]", scrubbed))
    if ns != 1:
        raise ValueError(
            _warn(
                "validate_ddm_pair",
                f"DDM pair must contain exactly one N/S direction, found {ns}.",
            )
        )
    if ew != 1:
        raise ValueError(
            _warn(
                "validate_ddm_pair",
                f"DDM pair must contain exactly one E/W direction, found {ew}.",
            )
        )
    if not re.search(r"\d", ddm_str):
        raise ValueError(
            _warn(
                "validate_ddm_pair",
                f"DDM string must contain numeric values: {ddm_str!r}",
            )
        )


# ── Datetime ──────────────────────────────────────────────────────────────────

def _validate_datetime(dt) -> None:
    """
    Raise ``TypeError`` if *dt* is not a :class:`datetime.datetime` object.
    """
    if not isinstance(dt, datetime):
        raise TypeError(
            _warn(
                "validate_datetime",
                f"Expected datetime, got {type(dt).__name__}.",
            )
        )


# ── String ────────────────────────────────────────────────────────────────────

def _validate_string(value: str) -> None:
    """
    Raise if *value* is not a non-empty ``str``.
    """
    if not isinstance(value, str):
        raise TypeError(
            _warn(
                "validate_string",
                f"Expected str, got {type(value).__name__}.",
            )
        )
    if not value:
        raise ValueError(
            _warn("validate_string", "String must be non-empty.")
        )