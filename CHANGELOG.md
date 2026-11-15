# Changelog

All notable changes to wherewhen will be documented here.

This package versions **independently** of jematools, h3tools, viztools, and
tabtools.  Dependents declare a minimum compatible version (e.g.
``wherewhen>=0.2.0``) rather than sharing a release number.

---

## [Unreleased]

### Added
- ``wherewhen Overview.pdf`` (#39): a two-page overview in the same style as the
  jematools and h3tools ones, built by ``scripts/build_overview_pdf.py``.
  The version, test count and function counts are read from the checkout
  and a live test run, and every number on it (China offsets, sun and moon
  times, coordinate round trips, code results) is measured when it is
  built, each with a labelled source line. ``tests/test_tracked_pdfs.py``
  fails if a release bumps the version without rebuilding it.
- ``moon_position(pt, when)``: the moon's altitude and azimuth at a moment,
  the moon's counterpart of ``sun_position`` (geometric, centre of the disc).
- ``is_moon_up(pt, when)``: whether the moon is up, by the same definition
  as ``get_lunar_data``'s moonrise and moonset (upper edge above -34',
  less the horizon dip), so it flips at the reported times and a day with
  neither is up or down throughout.
- ``get_lunar_month(when)``: the new, first-quarter, full and last-quarter
  moons of the lunation around *when*, and the next new moon, in UTC, with
  the lunation's length in days.
- ``get_sky_data(pt, eval_dt)``: one local day's ``get_solar_data`` and
  ``get_lunar_data`` with context — the lunation (``get_lunar_month`` on the
  local clock), a phase per day of it, a 5-minute day timeline of sun
  altitude and moon-up, and a year of sun altitudes (every 2nd day,
  half-hourly). Enough to draw a sky summary for any place; h3tools' cell
  card is built on it.

``moon_position``, ``is_moon_up`` and ``get_lunar_month`` need ``ephem``
only; ``get_sky_data`` also needs ``timezonefinder``. ``scripts/build_overview_pdf.py`` lists them
under "sun & moon"; the tracked overview's function count updates when the
next release rebuilds it.

---

## [0.5.0] — 2026-11-15

Minor release: four new time functions (``sun_position``, ``is_daylight``,
``to_local_time``, ``format_iso8601``) and microsecond / nanosecond epochs.
**One reading changes:** ``epoch_to_datetime`` now reads integer or float
timestamps from 1e13 up as microseconds or nanoseconds, so a millisecond
timestamp after the year 2286 gives a 1970s date. Seconds and ordinary
millisecond timestamps give the same datetime as on 0.4.2. See Changed.

### Added
- ``sun_position(pt, when, elevation=0.0)`` (#36): the sun's altitude and azimuth
  in degrees at a moment (geometric altitude of the centre, as
  ``get_solar_data`` uses). Needs ``ephem`` only.
- ``is_daylight(pt, when, elevation=0.0)`` (#36): ``True`` between sunrise and
  sunset as ``get_solar_data`` defines them (centre above -0.833°, less the
  horizon dip). Twilight is not daylight. Needs ``ephem`` only.
- ``to_local_time(dt, pt)`` (#36): convert a datetime to the local time at a
  point. At sea that is timezonefinder's nautical zone (e.g. ``Etc/GMT+2``
  at 30° W on the equator); UTC only where it finds no zone. Needs
  ``timezonefinder``.
- ``format_iso8601(dt, digits=3)`` (#36): UTC ISO 8601 string ending in ``Z``,
  milliseconds by default. Extra digits are cut, never rounded, so a time
  never rolls into the next second or day. ``digits`` is 0 to 6.

### Changed
- ``epoch_to_datetime`` (#36) now reads **microsecond** (from 1e13) and
  **nanosecond** (from 1e16) timestamps; on 0.4.2 they raised
  ``ValueError`` or gave the wrong date. Seconds (below 1e10) and
  milliseconds (from 1e10) are unchanged, except millisecond timestamps
  after the year 2286, which are now read as microseconds. Integer
  timestamps are converted exactly, except that nanoseconds are rounded
  down to the microsecond (a negative one can land 1 µs earlier than
  dropping digits). Integer milliseconds are now exact too: on 0.4.2 the
  last millisecond value (``9_999_999_999_999``) came out 1 µs off.
- ``point_to_tz_offset``: the missing-``timezonefinder`` error now uses the
  same wording as the solar and lunar functions. Its docstring now says
  sea points get timezonefinder's nautical zone, not UTC.

---

## [0.4.2] — 2026-11-15

Patch release. **GCJ-02 and BD-09 now apply only in mainland China, Hong
Kong and Macau.** On 0.4.1 they also offset points in Korea, Taiwan,
northern Vietnam and Mongolia (330–480 m), and BD-09 shifted points
anywhere in the world (Moscow 775 m), so check results from those
conversions outside China. Pass ``skip_region_check=True`` for data you
know was offset there too. ``convert_crs`` now converts between any two
supported CRS. See Added and Fixed.

### Added
- ``skip_region_check`` keyword on ``wgs84_to_cn_gcj02``, ``cn_gcj02_to_wgs84``,
  ``wgs84_to_cn_bd09``, ``cn_bd09_to_wgs84`` and ``convert_crs`` (#33),
  default ``False``. ``True`` applies the GCJ-02 / BD-09 conversion wherever
  the point is, for data you know is offset outside China too (e.g. from
  software that used the older rectangle). Anything but ``True`` or ``False``
  raises ``⚠️ [func] skip_region_check must be True or False, got int.``; a
  forced result outside WGS-84 bounds (only near the poles or ±180°) raises
  a labelled ``ValueError``.
- ``scripts/build_china_region.py``, which builds ``wherewhen/_china_region.py``
  from Natural Earth (see Fixed).

### Fixed
- GCJ-02 and BD-09 now apply only in mainland China, Hong Kong and Macau
  (#33), as the docstrings promised. The region was a rectangle
  (72.004–137.8347°E, 0.8293–55.8271°N) that also offset Seoul, Taipei,
  Hanoi, Pyongyang and Ulaanbaatar by 330–480 m. It is now the Natural Earth
  5.1.1 1:10m outline of the three, with a 0.2° (about 20 km) sea margin
  that stops at other countries' land, simplified to about 1 km. Taiwan,
  Kinmen included, is outside.
- BD-09 applies only inside that region too (#33). Baidu's +0.0065°/+0.006°
  step was added or removed everywhere, so e.g.
  ``wgs84_to_cn_bd09(moscow)`` moved Moscow 775 m; points outside
  are now returned unchanged by all four Chinese conversions.
- ``cn_gcj02_to_wgs84`` and ``cn_bd09_to_wgs84`` decide inside/outside on
  their WGS-84 result, so every point the forward conversion offset comes
  back, including near the border (#33).
- ``convert_crs`` converts between any two of WGS84, GCJ02, BD09 and SK42
  (#31). It knew only the six pairs to or from WGS-84, so ``"GCJ02"`` to
  ``"BD09"``, SK42 to GCJ02 / BD09 and their reverses raised "Unsupported
  CRS conversion"; they now go through WGS-84 (the extra leg adds no
  measurable error). The same CRS on both sides, e.g. ``"WGS84"`` to
  ``"WGS84"``, returns the point unchanged instead of raising, so code that
  picks the CRS at run time needs no special case. An unknown name raises
  ``⚠️ [convert_crs] Unsupported CRS 'EPSG:4326'. Supported: WGS84, GCJ02,
  BD09, SK42 (any case).``

---

## [0.4.1] — 2026-11-14

Patch release. **MGRS written with spaces now gives the right point.** On
0.4.0 any space after the 100 km square was silently read as that square's
south-west corner (about 84 km off for ``18TWL…``), so check results from
spaced MGRS input. Compact MGRS input is unchanged. See Fixed.

### Fixed
- The ``ISO8601`` docstring said it gives millisecond precision. It doesn't:
  ``strftime`` writes six fractional digits (microseconds), and has no
  millisecond code (#26). The docstring now says so, and that ``strptime``
  reads one to six digits (so JEMA's ``.mmmZ`` parses) and returns a naive
  datetime because the ``Z`` is matched as text. The constant is unchanged:
  jematools re-exports it as part of its frozen API.
- ``mgrs_to_point`` (and ``coordinate_to_point``, and h3tools'
  ``mgrs_to_h3``) read MGRS written with spaces, as on maps (#28). The
  validator stripped the spaces but the ``mgrs`` library got the original
  string. With a space after the 100 km square (``"18TWL 83960 07450"``,
  ``"18TWL 8396007450"``) the library read only ``18TWL`` and returned the
  square's south-west corner, (-75.00000, 40.65086), with no error; with a
  space between band and square (``"18T WL 83960 07450"``) it raised its
  own ``MGRSError``. All of these now give (-74.00598, 40.71369), the same
  as ``"18TWL8396007450"``.
- A split that can't be read unambiguously raises instead of being misread:
  ``"18TWL 8396 007450"`` (4-digit easting, 6-digit northing) also returned
  the square corner. Easting and northing written apart must now have the
  same number of digits; run together, the digits must be an even count of
  at most 10. Whitespace is accepted only between the four groups (zone and
  band, 100 km square, easting, northing).
- MGRS band and square letters ``I`` / ``O``, and references the library
  can't place (such as a square letter past ``V``), raise a labelled
  ``ValueError`` instead of the library's ``MGRSError``.
  ``_validate_mgrs`` does the same checks, so h3tools' ``mgrs_to_h3`` and
  ``geometry_to_h3`` and jematools get them too.

---

## [0.4.0] — 2026-11-14

Minor version because some results and names change: ``get_lunar_data``
drops the ``'Phase Number'`` and ``'Ephem Available'`` keys and
``ASTRAL_DEPRESSION_ANGLES`` is removed (see Removed), astral is no longer
a dependency, and ``get_solar_data`` reports a different (correct) day away
from UTC. See Changed, Removed and Fixed.

### Changed
- ``get_solar_data`` and ``get_lunar_data`` use ephem only; **astral is no
  longer a dependency** (#23). ephem was already required for moonrise and
  moonset. Sunrise, sunset and twilight come from ephem's rise/set search,
  stepped through the whole local day so every crossing is found; solar
  noon is the sun's transit. Compared with 0.3.0, sunrise and sunset move
  by up to about a minute (astral's ran 10–60 s from ephem's).
- ``TWILIGHT_DEPRESSION_ANGLES`` replaces ``ASTRAL_DEPRESSION_ANGLES``
  (same values; the old name is removed, see Removed).
- The horizon dip for a raised observer uses the mean Earth radius
  (6 371 008.8 m, as ``geometry.EARTH_RADIUS_M``) in place of astral's
  6 356 900 m; the difference is under a second of sunrise at 2 000 m.
- ``get_lunar_data``:
  - ``Illumination (%)`` is ephem's lit share of the disc. It was estimated
    from astral's phase number with a 27-day cycle, and ran up to about
    8 points off (56.9 % on 2026-04-24 where the moon was 48.9 % lit at
    00:00 UTC).
  - ``Moon Age (Days)`` is days since the last new moon (0–29.9). It was
    astral's 0–28 phase number, not days.
  - New ``Lunation (Fraction)``: how far through the current lunation (new
    moon to next new moon) the moment is, in [0, 1) — 0 new, about 0.25
    first quarter, 0.5 full, 0.75 last quarter. Replaces ``Phase Number``.
  - ``Phase Name`` gives New Moon, First Quarter, Full Moon or Last Quarter
    within 12 hours of that moment, otherwise crescent or gibbous (under or
    over half lit), waxing or waning. ``Is Waxing`` is true from new moon
    to full moon.
  - Phase, age and illumination are for local noon on the day (astral's
    phase was for the date at 00:00 UTC).
  - ``Moonrise`` / ``Moonset`` are the first rise and last set of the
    moon's upper edge during the local day, with 34' of refraction. They
    were the next rise and set after local midnight with no refraction, so
    a day without a moonrise or moonset reported the next day's; it is now
    ``None``.

### Removed
These go rather than stay as compatibility shims; nothing in the toolkit
read them except h3tools' range test (updated in outsideken/h3-tools#73).
- ``ASTRAL_DEPRESSION_ANGLES``: use ``TWILIGHT_DEPRESSION_ANGLES``.
- ``get_lunar_data`` key ``'Phase Number'`` (astral's 0–28 scale): use
  ``'Lunation (Fraction)'``, or ``'Moon Age (Days)'`` for days.
- ``get_lunar_data`` key ``'Ephem Available'``: ephem is required, so it
  was always ``True``.

### Fixed
- ``get_solar_data`` now reports the local day at the point. It used the UTC
  date and computed in UTC, so away from UTC sunrise and sunset came from
  different days: Tokyo on 2026-04-24 at 08:00 local gave a Day Length of
  -10.6 h, Honolulu -11.2 h (now 13.4 h and 12.8 h). Events are on the local
  calendar date. An aware ``eval_dt`` is converted to the location's
  timezone before its date is taken. A naive one still picks the date as
  written, but its times and day length change with this fix.
- ``get_solar_data`` no longer raises astral's ``ValueError`` during polar
  day or polar night. ``Sunrise`` / ``Sunset`` (and any twilight the sun
  never reaches) are ``None``, and ``Day Length (Hours)`` is the whole local
  day (normally 24.0) or 0.0.
- ``Day Length (Hours)`` counts every hour the sun is up in the local day.
  Next to a polar period the sun can set just after midnight and rise
  again, and those early-morning minutes were dropped or miscounted
  (Tromsø 2026-07-27 is 22.72 h). ``Sunrise`` is the first rise of the day
  and ``Sunset`` the last set, so on such days ``Sunset`` can be earlier
  than ``Sunrise``. Day length is measured in UTC, so a DST change that day
  is counted.
- Sunrise, sunset and twilight no longer come from astral's ``sunrise`` /
  ``sunset`` / ``dawn`` / ``dusk``, which skipped some events whose local
  day spans two UTC days (McMurdo's sunrise on 2026-08-20) and ran 10–60 s
  from ephem. A raised observer (``elevation``) lowers the horizon by the
  dip angle, added to the standard -0.833°; astral also shrank its
  refraction allowance below the horizon, so at 2 000 m sunrise is now
  about 2 minutes earlier than astral gave.
- ``get_lunar_data`` uses the same local date, so moonrise and moonset are
  for the local day.

---

## [0.3.0] — 2026-11-07

Minor version because some calls that worked before now raise: a wrong-type
number argument raises ``TypeError`` (was ``ValueError``), ``True``/``False``
are no longer numbers, and DMS/DDM strings that used to be misread now raise
``ValueError``. See Changed and Fixed.

### Added
- ``geometry.unwrap_single_collection`` and ``geometry.demote_single_multi``:
  two single-job bricks that return the only member of a one-member
  GeometryCollection, or the only part of a one-part MultiPoint,
  MultiLineString or MultiPolygon. Anything else comes back unchanged. Mainly
  for smaller files; compose them as needed.
- ``_validators._validate_geometry``: checks that a value is a Shapely geometry.
  ``geometry_to_box``, ``get_ratio`` and ``get_bounds`` / ``get_polygon`` use it
  in place of their own copies of that check. Same errors as before, except
  ``geometry_to_box`` now says "shapely" in lower case like the others.
- ``_validators._validate_number`` and ``_validate_integer``: type checks
  that reject ``bool`` (Python counts ``True`` as the integer 1).

### Changed
- A wrong-type argument now raises ``TypeError`` wherever wherewhen checks for
  a number, as agreed on #5 (``TypeError`` = wrong type, ``ValueError`` = bad
  value). Before, the latitude and longitude validators, ``point_at_distance``
  (``distance``, ``bearing``) and ``spherical_weighted_centroid`` (weights)
  raised ``ValueError``.
- ``True`` / ``False`` are no longer accepted as numbers by the latitude,
  longitude and MGRS-precision validators, ``normalize_longitude`` or
  ``normalize_latlon``.
- Hand-written checks now use the shared validators: the number checks above
  and in ``epoch_to_datetime`` use ``_validate_number``; ``box_to_polygon``
  uses ``_validate_string`` (an empty string now says so); and
  ``dms_to_point`` / ``ddm_to_point`` check parsed coordinates with
  ``_validate_latitude`` / ``_validate_longitude`` ("Latitude must be in
  [-90, 90], got 95.0." in place of "Latitude out of range: 95.0").
- The version is typed in one place, ``wherewhen/_version.py`` (#9).
  ``pyproject.toml`` reads it (``dynamic = ["version"]``); the README's version
  and test-count badges are replaced by the CI badge; notebook 01's title no
  longer states a version. ``tests/test_one_version.py`` replaces the check that
  ``pyproject.toml`` and ``_version.py`` agree, and fails if a copy comes back.

### Fixed
- ``dms_to_point`` / ``ddm_to_point`` (and ``coordinate_to_point``) no longer
  misread coordinates without an error. The regexes were unanchored and
  limited latitude degrees to 0–89, so ``90°0'0" N`` (the North Pole) read
  as latitude 0, ``95°`` as 5, ``89°59'60"`` as 59.1, ``51°75'`` as 75 and
  ``51.5N`` as 51°5'; DDM accepted 75 minutes. The pair is now read as
  numbers and hemisphere letters by three small helpers
  (``_split_hemisphere_pair``, ``_unpack_packed_group``,
  ``_sexagesimal_to_degrees``). Each part is read whole, only the last part
  may have a decimal, minutes and seconds must be below 60, and anything
  that doesn't fit raises ``ValueError``, including a sign (``-51``), a
  leading dot (``.5``) or a decimal comma (``0,5``), which were silently
  dropped or split; N/S and E/W give the sign. Packed forms (``513026N
  0000740W``) still work; ``ddm_to_point`` now also reads packed DDM
  (``5130.440N 00007.667W``).
- ``point_to_dms`` / ``point_to_ddm`` no longer print ``60.00"`` or
  ``60.000'``: they round to the printed precision first and carry, so
  their output always parses back.

---

## [0.2.10] — 2026-10-03

### Fixed
- A fresh install of wherewhen by itself could not be imported:
  ``ModuleNotFoundError: No module named 'packaging'`` from ``mgrs``, which
  imports ``packaging`` without declaring it.  wherewhen now declares
  ``packaging``, and a new CI job installs wherewhen alone into a fresh venv and
  imports every module (#13).

### Added
- ``named_errors`` in ``wherewhen._messages``: the one copy of the decorator
  that points a toolkit error's ``[label]`` at the public function the user
  called. h3tools, jematools and viztools still carry their own copies until
  they switch (#10).

---

## [0.2.9] — 2026-10-03

### Changed
- A missing optional package (pyproj, astral, timezonefinder) now raises
  ``ImportError: ⚠️ [<function>] …`` instead of ``❌ [<function>] …``, so every
  error the toolkit raises starts with ⚠️. ❌ is kept for printed "skipped"
  notices. Affects ``ru_sk42_to_wgs84``, ``wgs84_to_ru_sk42``,
  ``get_solar_data``, ``get_lunar_data``, ``point_to_tz_offset`` and
  ``shift_tz_by_name`` (no zoneinfo). Exception class and text are unchanged.

---

## [0.2.8] — 2026-10-02

Errors name the public function the user called, and every ``_validate_*``
accepts ``func_name``.  **h3tools and jematools pass ``func_name`` to these
validators, so they need wherewhen >= 0.2.8** (on 0.2.7 they raise
``TypeError: … unexpected keyword argument 'func_name'``).

### Changed
- **Errors name the public function the user called** (#4).  Messages used to
  name an internal validator (``⚠️ [validate_point] …`` from ``point_to_mgrs``)
  or another public function (``[normalize_longitude]`` from
  ``segment_crosses_antimeridian``, ``[get_bounds]`` from ``get_polygon``).
  Every ``_validate_*`` now takes an optional ``func_name`` (default unchanged,
  so dependents keep working) and all 37 public functions pass their own name.
  Delegation keeps the caller's name: ``coordinate_to_point`` → the coordinate
  parsers, ``cn_bd09_to_wgs84`` → the GCJ-02 step, and ``convert_crs`` → every
  converter go through private helpers that take ``func_name``.
  ``tests/test_error_names.py`` checks every exported function, and lists every
  public→public call that is allowed (with the reason) so new ones get reviewed.

### Fixed
- Raw Python errors are now labelled, and exception classes follow Python's
  definitions (``TypeError`` = wrong type, ``ValueError`` = right type, bad value;
  agreed with Cursor on #5).  **Class changes:**
  ``get_ratio`` / ``get_bounds`` / ``get_polygon`` on a non-geometry and
  ``convert_crs`` with a non-string CRS: ``AttributeError`` → ``TypeError``;
  ``latlon_to_point`` with a bare ``str`` / ``bytes`` / ``bytearray`` /
  ``memoryview``: ``ValueError`` →
  ``TypeError``; ``epoch_to_datetime`` out of range: ``OverflowError`` (or
  ``OSError``, platform-dependent) → ``ValueError`` on every platform.
- ``latlon_to_point("12")`` silently returned ``POINT (2 1)`` (and ``b"12"``
  returned ``POINT (50 49)``) because a two-character string unpacks as a pair.
  Bare ``str``, ``bytes``, ``bytearray`` and ``memoryview`` are now rejected.
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