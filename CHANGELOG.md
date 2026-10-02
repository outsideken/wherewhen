# Changelog

All notable changes to wherewhen will be documented here.

This package versions **independently** of jematools, h3tools, viztools, and
tabtools.  Dependents declare a minimum compatible version (e.g.
``wherewhen>=0.2.0``) rather than sharing a release number.

---

## [Unreleased]

### Changed
- **Errors name the public function the user called** (#4).  Messages used to
  name an internal validator (``⚠️ [validate_point] …`` from ``point_to_mgrs``)
  or another public function (``[normalize_longitude]`` from
  ``segment_crosses_antimeridian``, ``[get_bounds]`` from ``get_polygon``).
  Every ``_validate_*`` now takes an optional ``func_name`` (default unchanged,
  so dependents keep working) and all 37 public functions pass their own name.
  ``tests/test_error_names.py`` checks every exported function.

### Fixed
- Raw Python errors are now labelled: ``get_ratio`` / ``get_bounds`` /
  ``get_polygon`` on a non-geometry (``AttributeError``), ``latlon_to_point`` on a
  non-pair (unpacking ``ValueError``), ``epoch_to_datetime`` out of range
  (``OverflowError``), ``convert_crs`` with a non-string CRS (``AttributeError``).
  ``convert_crs`` validates its own point instead of the inner converter's.
- ``geometry_to_box`` on an empty geometry raised nothing and returned
  ``'BOX(nan nan,nan nan)'`` (or an empty point); it now raises ``ValueError``.
- ``shift_tz_by_name`` no longer requires ``timezonefinder``.  It only uses the
  standard library's ``zoneinfo``, but was gated on the flag that is ``True`` only
  when ``timezonefinder`` imports, so without it the conversion raised
  ``ImportError``.  ``zoneinfo`` is now imported and tracked on its own;
  ``point_to_tz_offset`` and the solar/lunar helpers still require
  ``timezonefinder`` (#2)
- ``get_solar_data`` / ``get_lunar_data``: a missing ``timezonefinder`` (or
  ``astral``) now reports the function the caller used, e.g.
  ``❌ [get_lunar_data] timezonefinder is required to find the location's local
  timezone``, instead of the internal ``[point_to_tz_offset]`` (or always
  ``[get_solar_data]`` for astral)

---

## [0.2.7] — 2026-09-30

### Added
- ``notebooks/00 data/wherewhen_crs_demo_*.csv`` — tiny China (GCJ/BD) and
  Russia (SK-42) landmark samples for ``01 CRS China and Russia.ipynb``

### Changed
- README — version/test badges synced to **0.2.7** / **147** tests; geometry
  catalogue includes ``point_at_distance`` and ``spherical_weighted_centroid``;
  added **What this is not**, portable install wording, and repo-local
  [COMPATIBILITY.md](COMPATIBILITY.md) for GitHub-only clones
- COMPATIBILITY.md updated for the **0.8.0b1** toolkit freeze row

### Fixed
- ``wherewhen._messages`` no longer uses ``from __future__ import annotations``.
  The JEMA sandbox bans ``__future__``, and jematools imports this module
  (outsideken/JEMA-Tools#2)
- ``tests/test_jema_runtime_rules.py`` — checks every module for Python 3.9 syntax,
  no ``__future__`` / ``os`` / ``sys`` / ``pathlib`` imports, and no ``X | Y``
  annotations, so jematools' dependency stays JEMA-safe

---

## [0.2.6] — 2026-06-24

### Added
- ``wherewhen.geometry.spherical_weighted_centroid`` — weighted geographic
  centre on the sphere (Cartesian vector sum; antimeridian-safe)

---

## [0.2.5] — 2026-06-24

### Added
- ``wherewhen.geometry.point_at_distance`` — destination point along bearing +
  great-circle distance (spherical Earth; ``normalize_latlon`` on output)

---

## [0.2.4] — 2026-06-24

### Added
- ``wherewhen.geometry.point_bearing`` — initial forward azimuth between two
  WGS-84 points (0–360°, clockwise from north; antimeridian-safe)

---

## [0.2.3] — 2026-06-24

### Added
- ``wherewhen.geometry.normalize_longitude`` — wrap longitudes to ``[-180, 180]``
  or ``[0, 360)``
- ``wherewhen.geometry.normalize_latlon`` — pole reflection plus longitude
  canonicalization for ``(lat, lon)`` pairs
- ``wherewhen.geometry.segment_crosses_antimeridian`` — detect shortest-path
  crossing of ±180°

### Changed
- ``_haversine_m`` — uses shortest-path longitude delta (antimeridian-safe
  great-circle distance)

---

## [0.2.2] — 2026-06-24

### Added
- ``wherewhen.geometry.point_to_latlon`` — Shapely ``Point`` → ``(lat, lon)``
  tuple (inverse of ``latlon_to_point``)
- ``wherewhen.geometry.point_distance`` — Haversine great-circle distance with
  ``units=`` selection (`m`, `km`, `nm`, `mi`) via module-level
  ``METRES_PER_UNIT`` dictionary
- ``wherewhen.geometry.point_distance_km`` — convenience wrapper for
  ``point_distance(..., units='km')``
- ``EARTH_RADIUS_M``, ``SUPPORTED_DISTANCE_UNITS`` — shared distance constants
- ``wherewhen.geometry.box_to_polygon`` — PostGIS ``BOX(…)`` string → Shapely
  ``Polygon`` (moved up from ``jematools``; jematools re-exports for compat)
- ``wherewhen._validators._BOX_PATTERN`` — shared BOX regex for dependent libs

---

## [0.2.1] — 2026-06-17

### Changed
- README — toolkit diagram lists ``viztools`` and ``tabtools`` as shipped (not
  planned); ``jematools`` dependency note updated to **0.5.8**
- ``tests/test_package.py`` — version string expectations updated to **0.2.1**

---

## [0.2.0] — 2026-06-07

First release under the **wherewhen** name (successor to `geocore`).

### Added
- `wherewhen._messages` — shared emoji-prefixed notification helpers:
  `⚠️` validation errors, `ℹ️` informational, `❌` skipped, `✏️` notes, `✅` success
- `wherewhen._version` — single source of truth for runtime version string
- `list_functions()` — catalogue of public API grouped by module

### Changed
- Package renamed from `geocore` → `wherewhen`
- All validators and public functions raise/type errors with
  `⚠️ [function_name] description` format (aligned with jematools)
- Module layout unchanged: `geometry`, `temporal`, `crs`, `_validators`

### Modules
- `wherewhen.geometry` — coordinate parsing, bounds, aspect ratio
- `wherewhen.temporal` — datetime, timezone, solar/lunar
- `wherewhen.crs` — datum / CRS conversions (GCJ-02, BD-09, SK-42)

---

## [0.1.0] — 2026-05-02

Released as **geocore** (pre-rename).  Same primitive surface; consumed
internally before the toolkit split and notification standardisation.