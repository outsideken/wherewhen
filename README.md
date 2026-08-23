# wherewhen

![Version](https://img.shields.io/badge/version-0.2.4-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-108%20passing-brightgreen)

Shared **where** and **when** primitives for the JEMA toolkit ecosystem.

`wherewhen` is the bottom layer of the toolkit stack: coordinate parsing,
geometry helpers, datetime/timezone utilities, and CRS conversions.  It has
**no dependency** on `jematools`, `h3tools`, `viztools`, or `tabtools`.

Successor to **`geocore`** (renamed in Phase 1, 2026).  Versions
independently of every other package — see [CHANGELOG.md](CHANGELOG.md) and
the workspace [COMPATIBILITY.md](../COMPATIBILITY.md).

---

## Role in the toolkit

```
wherewhen          ← you are here (where / when primitives)
 ├── jematools     ← JEMA platform I/O and CV glue only
 ├── h3tools       ← H3 geospatial helpers
 ├── viztools      ← plot styling and ColorBrewer palettes
 └── tabtools      ← tabular profiling and anomaly scoring
```

| Need | Import from |
|---|---|
| Lat/lon, MGRS, DMS, DDM parsing | `wherewhen.geometry` |
| Datetime, timezone, solar/lunar | `wherewhen.temporal` |
| GCJ-02, BD-09, SK-42 conversions | `wherewhen.crs` |
| JEMA `load_table`, CV types, file I/O | `jematools` |
| PostGIS `BOX(…)` parsing | `wherewhen.geometry` (`box_to_polygon`) |
| JEMA `temporalRange` pipe strings | `jematools` (`parse_temporal_range`) |

**Rule:** import wherewhen directly for primitives; use jematools only for
platform-specific glue.

---

## Installation

```bash
pip install -e "/path/to/wherewhen"
```

With jematools (typical JEMA stack):

```bash
pip install -e "/path/to/wherewhen"
pip install -e "/path/to/jema-tools"
```

---

## Quick start

```python
import wherewhen   # ℹ️ [wherewhen] v<version> loaded.

from wherewhen.geometry import coordinate_to_point, latlon_to_point
from wherewhen.temporal import ensure_utc, convert_to_datetime, get_solar_data

# Any supported coordinate format → Shapely Point
pt = coordinate_to_point((51.5074, -0.1278))
pt = coordinate_to_point('51°30\'26"N 0°7\'40"W')

# Datetime and solar data
dt = ensure_utc(convert_to_datetime("2026-04-24T12:00:00"))
solar = get_solar_data(pt, dt)
print(solar["Timezone Name"])
```

Browse the API:

```python
wherewhen.list_functions()
print(wherewhen.__version__)
```

---

## Modules

### `wherewhen.geometry`

Coordinate conversion, bounding boxes, aspect-ratio utilities, and spherical
normalization (poles and antimeridian).

```python
from wherewhen.geometry import (
    latlon_to_point,       # (lat, lon) tuple → Point
    point_to_latlon,       # Point → (lat, lon) tuple
    normalize_longitude,   # wrap lon to [-180,180] or [0,360)
    normalize_latlon,      # pole reflection + lon wrap for (lat, lon)
    segment_crosses_antimeridian,  # shortest path crosses ±180°?
    point_distance,        # great-circle distance (units='km'|'m'|'nm'|'mi')
    point_distance_km,     # shorthand for units='km'
    point_bearing,         # initial azimuth 0–360° clockwise from north
    mgrs_to_point,         # MGRS string → Point
    dms_to_point,          # DMS pair string → Point
    ddm_to_point,          # DDM pair string → Point
    coordinate_to_point,   # auto-detect format → Point
    point_to_dms,          # Point → DMS string pair
    point_to_ddm,
    point_to_mgrs,
    geometry_to_box,       # geometry → PostGIS BOX or envelope Polygon
    box_to_polygon,        # PostGIS BOX string → Polygon
    get_ratio, get_bounds, get_polygon,
)
```

**Poles and antimeridian:** `normalize_latlon` reflects across the poles when
`|lat| > 90` and shifts longitude by 180°; `normalize_longitude` wraps meridians
to `[-180, 180]` or `[0, 360)`. `point_distance` and `point_bearing` use the
shortest-path longitude delta (safe across ±180°). Strict `_validate_*` bounds
are unchanged — normalize explicitly at ingest when sources emit unwrapped coordinates.

```python
from wherewhen.geometry import normalize_latlon, segment_crosses_antimeridian

normalize_latlon(95, 10)                    # (85.0, -170.0) — north-pole crossing
segment_crosses_antimeridian(179, -179)     # True
```

### `wherewhen.temporal`

Datetime parsing, timezone lookup, and solar/lunar events.

```python
from wherewhen.temporal import (
    ISO8601,
    epoch_to_datetime,
    convert_to_datetime,
    ensure_utc,
    is_dt_naive,
    start_of_day,
    end_of_day,
    shift_tz_by_name,
    point_to_tz_offset,
    get_solar_data,
    get_lunar_data,
)
```

### `wherewhen.crs`

Datum conversions for China (GCJ-02, BD-09) and Russia (SK-42).

```python
from wherewhen.crs import (
    convert_crs,
    wgs84_to_cn_gcj02,
    cn_gcj02_to_wgs84,
    wgs84_to_cn_bd09,
    cn_bd09_to_wgs84,
    wgs84_to_ru_sk42,
    ru_sk42_to_wgs84,
)
```

---

## Notification conventions

### Import-time load notice

Printed once when the package is first imported:

```
ℹ️ [wherewhen] v<version> loaded.
```

Implemented via `wherewhen._messages.loaded()` — shared across all toolkit
packages.

### Errors and status

| Emoji | Meaning | Example |
|---|---|---|
| ⚠️ | Validation error or invalid input | `⚠️ [validate_latitude] Latitude must be in [-90, 90], got 91.0.` |
| ℹ️ | Informational notice | `ℹ️ [wherewhen] v<version> loaded.` |
| ❌ | Skipped or unsupported | `❌ [convert_crs] pyproj required for SK-42 conversions.` |
| ✏️ | Configuration note | *(reserved for future use)* |
| ✅ | Success (verbose logging) | *(reserved for future use)* |

Every raised exception opens with `⚠️ [function_name]` so the source is visible
in the traceback.

---

## Project structure

```
wherewhen/
├── wherewhen/
│   ├── __init__.py      # Public API + list_functions()
│   ├── _version.py      # Single source of truth for version string
│   ├── _messages.py     # Emoji notification helpers (+ loaded())
│   ├── _validators.py   # Internal validators (private)
│   ├── geometry.py
│   ├── temporal.py
│   └── crs.py
├── tests/
│   ├── test_geometry.py
│   ├── test_temporal.py
│   ├── test_crs.py
│   └── test_package.py
├── CHANGELOG.md
├── pyproject.toml
└── README.md
```

Private modules (`_validators`, `_messages`) are for internal use and for
dependent libraries (`jematools`, `h3tools`).  Application code should import
from `wherewhen.geometry`, `wherewhen.temporal`, or `wherewhen.crs`.

---

## Versioning

- Runtime version: `wherewhen.__version__` (from `_version.py`)
- Packaging version: `pyproject.toml`
- Bump both together on release; tag `wherewhen-vX.Y.Z` in git
- `jematools` declares `wherewhen>=0.2.0` — a wherewhen
  minor release does **not** require a jematools release unless jematools starts
  calling new APIs.  See workspace [COMPATIBILITY.md](../COMPATIBILITY.md).

---

## Dependencies

| Package | Used by |
|---|---|
| `shapely` | All geometry modules |
| `mgrs` | MGRS conversions |
| `python-dateutil` | Flexible datetime parsing |
| `timezonefinder` | `point_to_tz_offset` |
| `astral` | `get_solar_data` |
| `ephem` | `get_lunar_data` |
| `pyproj` | SK-42 CRS conversions only |

---

## Tests

```bash
cd /path/to/wherewhen
pytest tests/ -q
```

| File | Coverage |
|---|---|
| `tests/test_geometry.py` | Coordinates, MGRS, DMS, DDM, `geometry_to_box` |
| `tests/test_temporal.py` | Datetime helpers, timezone, solar/lunar |
| `tests/test_crs.py` | GCJ-02, BD-09, SK-42, `convert_crs` |
| `tests/test_package.py` | Version string, notification helpers |

`jematools/tests/` covers JEMA-only helpers (`points_from_columns`,
`parse_temporal_range`, etc.) separately.

---

## License

MIT