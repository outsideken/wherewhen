"""
wherewhen
=========
Shared *where* and *when* primitives for the JEMA toolkit ecosystem.

Bottom layer of the toolkit stack.  Provides:

* :mod:`wherewhen.geometry` — coordinate parsing, bounds, aspect ratio
* :mod:`wherewhen.temporal` — datetime, timezone, solar/lunar events
* :mod:`wherewhen.crs` — datum / CRS conversions (GCJ-02, BD-09, SK-42)

Consumed by ``jematools`` and ``h3tools`` for internal validation and
re-export in domain-specific wrappers.  Has **no dependency** on either.

Import primitives directly::

    from wherewhen.geometry import coordinate_to_point
    from wherewhen.temporal import ensure_utc

JEMA platform glue (``load_table``, ``parse_temporal_range``) lives in
:mod:`jematools`.  ``box_to_polygon`` is provided here; ``jematools`` re-exports
it for backward compatibility.

Versions independently of all other toolkit packages.  On first import prints
``ℹ️ [wherewhen] v<version> loaded.``  Validation errors use emoji-prefixed
messages via :mod:`wherewhen._messages`.  See the package README and
:func:`list_functions` for full API discovery.
"""

from wherewhen.geometry import (
    latlon_to_point,
    point_to_latlon,
    normalize_longitude,
    normalize_latlon,
    segment_crosses_antimeridian,
    point_distance,
    point_distance_km,
    point_bearing,
    point_at_distance,
    spherical_weighted_centroid,
    EARTH_RADIUS_M,
    METRES_PER_UNIT,
    SUPPORTED_DISTANCE_UNITS,
    mgrs_to_point,
    dms_to_point,
    ddm_to_point,
    coordinate_to_point,
    point_to_dms,
    point_to_ddm,
    point_to_mgrs,
    geometry_to_box,
    box_to_polygon,
    get_ratio,
    get_bounds,
    get_polygon,
)

from wherewhen.temporal import (
    ISO8601,
    ASTRAL_DEPRESSION_ANGLES,
    epoch_to_datetime,
    convert_to_datetime,
    is_dt_naive,
    ensure_utc,
    start_of_day,
    end_of_day,
    shift_tz_by_name,
    point_to_tz_offset,
    get_solar_data,
    get_lunar_data,
)

from wherewhen.crs import (
    WGS84_A,
    WGS84_F,
    convert_crs,
    wgs84_to_cn_gcj02,
    cn_gcj02_to_wgs84,
    wgs84_to_cn_bd09,
    cn_bd09_to_wgs84,
    ru_sk42_to_wgs84,
    wgs84_to_ru_sk42,
)

from wherewhen._messages import loaded as _loaded
from wherewhen._version import __version__

_loaded("wherewhen", __version__)


def list_functions() -> None:
    """
    Print a catalogue of all public wherewhen functions grouped by module.

    Each entry shows the function name and the first line of its docstring.
    Private helpers (names beginning with ``_``) and module constants are
    excluded.
    """
    import inspect
    from wherewhen import geometry, temporal, crs

    sections = [
        ("geometry", geometry),
        ("temporal", temporal),
        ("crs",      crs),
    ]

    for section_name, module in sections:
        names = getattr(module, "__all__", [])
        funcs = [
            (name, getattr(module, name))
            for name in names
            if inspect.isfunction(inspect.unwrap(getattr(module, name, None) or (lambda: None)))
        ]
        if not funcs:
            continue
        print(f"\n{'─' * 60}")
        print(f"  {section_name}")
        print(f"{'─' * 60}")
        for name, obj in funcs:
            doc = inspect.getdoc(obj) or ""
            summary = doc.split("\n")[0]
            print(f"  {name:<35} {summary}")