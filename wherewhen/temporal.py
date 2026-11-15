"""
wherewhen.temporal
=================
Datetime, timezone, and solar/lunar event utilities.

Provides helpers for parsing and normalising datetime objects, looking up
IANA timezone names and UTC offsets from geographic points, and computing
solar and lunar events for any location on a given date.

Soft dependencies — ``ephem`` (sun and moon positions) and
``timezonefinder`` (timezone from coordinates) — are detected at import
time.  Functions that require them raise :class:`ImportError` with an
installation hint if they are unavailable.

Module Attributes
-----------------
ISO8601 : str
    ``strftime``/``strptime`` format string for UTC ISO 8601 timestamps
    with a literal ``Z`` suffix: ``"%Y-%m-%dT%H:%M:%S.%fZ"``.

    * ``strftime`` writes **microseconds** (six digits), e.g.
      ``2026-01-01T00:00:00.000000Z``; ``strftime`` has no millisecond
      code, so for ``.mmmZ`` trim three digits (as jematools' temporal-range
      formatter does).
    * ``strptime`` reads one to six fractional digits, so millisecond
      strings such as ``2026-01-01T00:00:00.123Z`` parse too.
    * The ``Z`` is matched as text, so ``strptime`` returns a **naive**
      datetime; pass it through :func:`ensure_utc`, and convert aware
      datetimes to UTC before formatting.
TWILIGHT_DEPRESSION_ANGLES : dict
    Solar depression angles in degrees for the three recognised twilight
    phases: ``'Civil'`` (6°), ``'Nautical'`` (12°), and
    ``'Astronomical'`` (18°).

Functions
---------
epoch_to_datetime
    Convert a numeric Unix timestamp (s, ms, µs or ns) to a UTC datetime.
convert_to_datetime
    Parse a string or pass-through a datetime object.
ensure_utc
    Make a datetime timezone-aware and convert it to UTC.
is_dt_naive
    Check whether a datetime lacks timezone information.
start_of_day
    Truncate a datetime to midnight (00:00:00.000000).
end_of_day
    Set a datetime to the last microsecond of the day (23:59:59.999999).
format_iso8601
    Format a datetime as a UTC ISO 8601 string (milliseconds by default).
shift_tz_by_name
    Convert a datetime to a named IANA timezone.
point_to_tz_offset
    Return the IANA timezone name and UTC offset (hours) for a location.
to_local_time
    Convert a datetime to the local time at a location.
sun_position
    The sun's altitude and azimuth at a moment, from a location.
is_daylight
    Whether the sun is up at a location at a moment.
get_solar_data
    Compute solar events and twilight phases for a location on a given date.
get_lunar_data
    Return moon phase, illumination percentage, and rise/set times for a
    location on a given date.

Toolkit
-------
Part of the ``wherewhen`` package (successor to ``geocore``).  Import from
this module directly — not re-exported by :mod:`jematools`.  JEMA
``temporalRange`` pipe strings are handled by
:mod:`jematools.jema_temporal`, not here.  Validation errors raise with
``⚠️ [function_name] …`` via :mod:`wherewhen._messages`.
"""

import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Dict, Optional, Tuple, Union

from dateutil import parser as dateutil_parser
from shapely.geometry import Point

from wherewhen._messages import warn as _warn
from wherewhen.geometry import EARTH_RADIUS_M
from wherewhen._validators import (
    _validate_datetime,
    _validate_integer,
    _validate_number,
    _validate_point,
    _validate_string,
)

__all__ = [
    "ISO8601",
    "TWILIGHT_DEPRESSION_ANGLES",
    "epoch_to_datetime",
    "convert_to_datetime",
    "is_dt_naive",
    "ensure_utc",
    "start_of_day",
    "end_of_day",
    "format_iso8601",
    "shift_tz_by_name",
    "point_to_tz_offset",
    "to_local_time",
    "sun_position",
    "is_daylight",
    "get_solar_data",
    "get_lunar_data",
]

# ── Optional-dependency guards ────────────────────────────────────────────────
try:
    import ephem as _ephem
    _EPHEM_AVAILABLE = True
except ImportError:
    _EPHEM_AVAILABLE = False

# zoneinfo (stdlib, Python 3.9+) is all that named-timezone conversion needs;
# timezonefinder is only for looking a timezone up from coordinates.
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    _ZONEINFO_AVAILABLE = True
except ImportError:
    _ZONEINFO_AVAILABLE = False

try:
    from timezonefinder import TimezoneFinder as _TF
    _TF_INSTANCE = _TF()
    _TZ_AVAILABLE = _ZONEINFO_AVAILABLE
except ImportError:
    _TZ_AVAILABLE = False

# ── Constants ─────────────────────────────────────────────────────────────────
# Writes microseconds (%f is six digits); reads 1-6 fractional digits.
ISO8601: str = "%Y-%m-%dT%H:%M:%S.%fZ"

TWILIGHT_DEPRESSION_ANGLES: Dict[str, float] = {
    "Civil": 6.0,
    "Nautical": 12.0,
    "Astronomical": 18.0,
}

# Sun's centre at sunrise/sunset: -0.833° = refraction (34') + the sun's
# radius (16'), measured with refraction switched off (pressure 0).
_SUN_HORIZON_DEG: float = -0.833

# Moon's upper edge at moonrise/moonset: -34' of refraction.  ephem already
# includes the moon's parallax (topocentric position).
_MOON_HORIZON_DEG: float = -34.0 / 60.0

# Mean synodic month (new moon to new moon), in days.
_SYNODIC_MONTH_DAYS: float = 29.530588853

# A principal phase (new, first quarter, full, last quarter) is named when
# the evaluation moment is within this many hours of it.
_PRINCIPAL_PHASE_WINDOW_H: float = 12.0

# When ephem cannot place the next antitransit, the pass search moves on by
# this many days instead.  A pass lasts about a day, so half a day never
# skips one.
_PASS_FALLBACK_STEP_DAYS: float = 0.5


# ── Private helpers ───────────────────────────────────────────────────────────

def _require_astro_deps(caller: str) -> None:
    """Raise ImportError, naming *caller*, if ephem or timezonefinder is missing."""
    _require_ephem(caller)
    _require_tz(caller)


def _require_ephem(caller: str) -> None:
    """Raise ImportError, naming *caller*, if ephem is missing."""
    if not _EPHEM_AVAILABLE:
        raise ImportError(
            _warn(
                caller,
                "ephem is required for solar/lunar calculations. "
                "Install with: pip install ephem",
            )
        )


def _require_tz(caller: str) -> None:
    """Raise ImportError, naming *caller*, if timezonefinder is missing."""
    if not _TZ_AVAILABLE:
        raise ImportError(
            _warn(
                caller,
                "timezonefinder is required to find the location's local timezone. "
                "Install with: pip install timezonefinder",
            )
        )


def _tz_name_at(pt: Point) -> str:
    """IANA timezone name at *pt*, or ``'UTC'`` outside every mapped zone."""
    return _TF_INSTANCE.timezone_at(lng=pt.x, lat=pt.y) or "UTC"


def _local_date(eval_dt: datetime, local_tz):
    """Return the calendar date *eval_dt* falls on at the location.

    A naive datetime's own date is used as written; an aware one is first
    converted to *local_tz*, so 08:00 in Tokyo is that Tokyo day, not the
    previous UTC day.
    """
    if is_dt_naive(eval_dt):
        return eval_dt.date()
    return eval_dt.astimezone(local_tz).date()


def _astro_context(pt: Point, eval_dt: datetime):
    """Return (eval_dt_utc, tz_name, tz_offset, local_tz, target_date) for astro calculations."""
    eval_dt_utc = ensure_utc(eval_dt)
    tz_name, tz_offset = point_to_tz_offset(pt, eval_dt_utc)
    local_tz = ZoneInfo(tz_name)
    target_date = _local_date(eval_dt, local_tz)
    return eval_dt_utc, tz_name, tz_offset, local_tz, target_date


def _local_day_bounds(target_date, local_tz) -> Tuple[datetime, datetime]:
    """Return the local midnights that start and end *target_date*."""
    next_day = target_date + timedelta(days=1)
    return (
        datetime(target_date.year, target_date.month, target_date.day, tzinfo=local_tz),
        datetime(next_day.year, next_day.month, next_day.day, tzinfo=local_tz),
    )


def _horizon_dip_deg(elevation_m: float) -> float:
    """Degrees the horizon drops for an observer *elevation_m* above sea level."""
    if elevation_m <= 0:
        return 0.0
    return math.degrees(math.acos(EARTH_RADIUS_M / (EARTH_RADIUS_M + elevation_m)))


def _to_ephem_date(when: datetime):
    """Return an aware datetime as an ``ephem.Date`` (ephem works in UTC)."""
    return _ephem.Date(when.astimezone(timezone.utc).replace(tzinfo=None))


def _from_ephem_date(value, local_tz) -> datetime:
    """Return an ``ephem.Date`` as an aware datetime in *local_tz*."""
    return value.datetime().replace(tzinfo=timezone.utc).astimezone(local_tz)


def _ephem_observer(pt: Point, elevation: float, horizon_deg: float):
    """Return an ephem Observer at *pt* with refraction off and the given horizon."""
    obs = _ephem.Observer()
    obs.lat = str(pt.y)
    obs.lon = str(pt.x)
    obs.elevation = elevation
    obs.pressure = 0          # refraction is in the horizon angle instead
    obs.horizon = math.radians(horizon_deg)
    return obs


def _altitude_deg(obs, body, when: datetime) -> float:
    """Height of *body* in degrees for *obs* at *when*."""
    obs.date = _to_ephem_date(when)
    body.compute(obs)
    return math.degrees(body.alt)


def _crossings_of(obs, body, day_start: datetime, day_end: datetime, rising: bool,
                  use_center: bool) -> list:
    """Return every time *body* rises (or sets) through ``obs.horizon`` in the day.

    ephem searches one pass across the sky at a time (antitransit to
    antitransit).  A pass with no crossing raises a circumpolar error, so the
    search then jumps to the next antitransit and carries on until the end of
    the day.  If ephem cannot place that antitransit either, the search moves
    on half a day, which still lands inside the next pass at the latest.
    """
    find = obs.next_rising if rising else obs.next_setting
    start, end = _to_ephem_date(day_start), _to_ephem_date(day_end)
    found = []
    cursor = start
    for _ in range(8):   # a day holds at most two passes
        try:
            when = find(body, start=cursor, use_center=use_center)
        except _ephem.CircumpolarError:
            when = None
        if when is not None:
            if when >= end:
                break
            found.append(when)
            cursor = _ephem.Date(when + _ephem.second)
            continue
        try:
            cursor = _ephem.Date(obs.next_antitransit(body, start=cursor) + _ephem.second)
        except _ephem.CircumpolarError:
            cursor = _ephem.Date(cursor + _PASS_FALLBACK_STEP_DAYS)
        if cursor >= end:
            break
    return found


def _day_crossings(obs, body, day_start: datetime, day_end: datetime, local_tz,
                   use_center: bool) -> list:
    """Return every ``(time, rising)`` horizon crossing of *body* in the local day, in order."""
    events = [
        (when, rising)
        for rising in (True, False)
        for when in _crossings_of(obs, body, day_start, day_end, rising, use_center)
    ]
    return [(_from_ephem_date(when, local_tz), rising) for when, rising in sorted(events)]


def _first_rise(crossings: list) -> Optional[datetime]:
    """Return the first upward crossing, or None."""
    return next((when for when, rising in crossings if rising), None)


def _last_set(crossings: list) -> Optional[datetime]:
    """Return the last downward crossing, or None."""
    return next((when for when, rising in reversed(crossings) if not rising), None)


def _hours_between(a: datetime, b: datetime) -> float:
    """Elapsed hours from *a* to *b*, counted in UTC so DST changes are honoured."""
    return (b.astimezone(timezone.utc) - a.astimezone(timezone.utc)).total_seconds() / 3600


def _hours_above(start_above: bool, day_start: datetime, day_end: datetime,
                 crossings: list) -> float:
    """Hours in the local day a body spends above the horizon, over every stretch.

    *start_above* says whether it was above at *day_start*; *crossings* come
    from :func:`_day_crossings`.
    """
    above = start_above
    total, since = 0.0, day_start
    for when, rising in crossings:
        if not rising:
            total += _hours_between(since, when)
        since = when
        above = rising
    if above:
        total += _hours_between(since, day_end)
    return round(total, 3)


def _moon_age_days(when) -> float:
    """Days since the last new moon at ephem date *when*."""
    return float(when - _ephem.previous_new_moon(when))


def _lunation_fraction(when) -> float:
    """How far through this lunation (new moon to next new moon) *when* is, in [0, 1)."""
    previous_new = _ephem.previous_new_moon(when)
    return float((when - previous_new) / (_ephem.next_new_moon(when) - previous_new))


def _is_waxing(when) -> bool:
    """True if the next full moon comes before the next new moon."""
    return _ephem.next_full_moon(when) < _ephem.next_new_moon(when)


def _moon_phase_name(when, age_days: float, illumination: float, waxing: bool) -> str:
    """Name the moon's phase at ephem date *when*.

    A principal phase is named within 12 hours of its exact moment; otherwise
    crescent or gibbous (under or over half lit), waxing or waning.  The age
    picks which principal phase is nearest (they are about 7.4 days apart),
    and only that one is looked up.
    """
    principal = (
        ("New Moon",      _ephem.previous_new_moon,           _ephem.next_new_moon),
        ("First Quarter", _ephem.previous_first_quarter_moon, _ephem.next_first_quarter_moon),
        ("Full Moon",     _ephem.previous_full_moon,          _ephem.next_full_moon),
        ("Last Quarter",  _ephem.previous_last_quarter_moon,  _ephem.next_last_quarter_moon),
    )
    nearest = int(round(age_days / (_SYNODIC_MONTH_DAYS / 4))) % 4
    name, previous_fn, next_fn = principal[nearest]
    window = _PRINCIPAL_PHASE_WINDOW_H / 24.0
    if min(when - previous_fn(when), next_fn(when) - when) <= window:
        return name
    shape = "Crescent" if illumination < 50.0 else "Gibbous"
    return ("Waxing " if waxing else "Waning ") + shape


# ── Datetime helpers ──────────────────────────────────────────────────────────

# Epoch unit by size.  1e10 seconds is the year 2286, so each step up
# (x1000) is the first value that would be after 2286 in the smaller unit.
# (upper bound, units per second); anything from 1e16 up is nanoseconds.
_EPOCH_UNITS: Tuple[Tuple[float, int], ...] = (
    (1e10, 1),                 # seconds
    (1e13, 1_000),             # milliseconds
    (1e16, 1_000_000),         # microseconds
)
_EPOCH_NS_PER_SECOND: int = 1_000_000_000

_UNIX_EPOCH: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

# format_iso8601: datetime holds at most six fractional digits.
_ISO_MAX_DIGITS: int = 6


def epoch_to_datetime(value: Union[int, float]) -> datetime:
    """
    Convert a numeric Unix timestamp to a UTC-aware datetime.

    The unit is read from the size of the value (its absolute value):

    ==================  ============
    Size                Read as
    ==================  ============
    below 1e10          seconds
    1e10 to below 1e13  milliseconds
    1e13 to below 1e16  microseconds
    1e16 and above      nanoseconds
    ==================  ============

    1e10 seconds is the year 2286, so each boundary is the first value that
    would land after 2286 in the smaller unit.  A millisecond timestamp
    after 2286 is therefore read as microseconds.

    Integers are converted exactly, except that nanoseconds are rounded
    down to the microsecond (a datetime holds no finer).  Down means
    towards the earlier time, so a negative nanosecond value can land 1 µs
    earlier than simply dropping the last three digits.  Floats are divided
    by the unit first.

    Parameters
    ----------
    value : int or float
        Unix timestamp in seconds, milliseconds, microseconds or
        nanoseconds.

    Returns
    -------
    datetime
        A UTC-aware :class:`datetime` object.

    Raises
    ------
    TypeError
        If *value* is not an ``int`` or ``float`` (``bool`` included).

    See Also
    --------
    convert_to_datetime : Parse strings or pass through datetime objects.

    Examples
    --------
    >>> epoch_to_datetime(1714950400).year
    2024

    >>> epoch_to_datetime(1714950400000).year   # milliseconds
    2024

    >>> epoch_to_datetime(1714950400123456789).microsecond   # nanoseconds
    123456
    """
    _validate_number(value, "epoch_to_datetime", "Epoch")
    per_second = _EPOCH_NS_PER_SECOND
    for bound, units in _EPOCH_UNITS:
        if abs(value) < bound:
            per_second = units
            break
    try:
        if isinstance(value, int):
            # Exact: whole microseconds, rounded down (as // does for ns).
            micros = value * 1_000_000 // per_second
            return _UNIX_EPOCH + timedelta(microseconds=micros)
        return datetime.fromtimestamp(value / per_second, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        # fromtimestamp raises OverflowError or OSError depending on the platform;
        # an out-of-range argument is a ValueError (as datetime(10000, 1, 1) is).
        raise ValueError(
            _warn(
                "epoch_to_datetime",
                f"Timestamp {value!r} is outside the range a datetime can represent.",
            )
        ) from None


def convert_to_datetime(dt_input, force_utc: bool = False) -> datetime:
    """
    Parse a date/time string or pass through a datetime object.

    Parameters
    ----------
    dt_input : str or datetime
        The value to convert.

        * :class:`datetime` — returned as-is (subject to *force_utc*).
        * :class:`str` — parsed with :func:`dateutil.parser.parse`, which
          accepts ISO 8601, RFC 2822, and many natural-language formats.
    force_utc : bool, optional
        If ``True``, a *naive* datetime (one with no ``tzinfo``) is
        assumed to represent UTC and is made timezone-aware by attaching
        :data:`datetime.timezone.utc`.  Aware datetimes are returned
        unchanged.  Default is ``False``.

    Returns
    -------
    datetime
        A :class:`datetime` object.  May be naive or aware depending on
        the input and *force_utc*.

    Raises
    ------
    TypeError
        If *dt_input* is not a ``str`` or ``datetime``.
    ValueError
        If the string cannot be parsed as a recognisable date/time.

    See Also
    --------
    epoch_to_datetime : Convert a numeric Unix timestamp to a UTC datetime.
    ensure_utc : Convert any datetime to a UTC-aware datetime.
    is_dt_naive : Check whether a datetime lacks timezone information.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = convert_to_datetime("2026-04-24T12:00:00")
    >>> isinstance(dt, datetime)
    True

    >>> dt_utc = convert_to_datetime("2026-04-24", force_utc=True)
    >>> dt_utc.tzinfo is not None
    True

    >>> convert_to_datetime(datetime(2026, 4, 24))
    datetime.datetime(2026, 4, 24, 0, 0)
    """
    if isinstance(dt_input, datetime):
        dt = dt_input
    elif isinstance(dt_input, str):
        try:
            dt = dateutil_parser.parse(dt_input)
        except (ValueError, OverflowError):
            raise ValueError(
                _warn(
                    "convert_to_datetime",
                    f"Invalid date format: {dt_input!r}. "
                    "Ensure the string contains a recognisable date/time value.",
                )
            )
    else:
        raise TypeError(
            _warn(
                "convert_to_datetime",
                f"Unsupported input type: {type(dt_input).__name__}. "
                "Accepts str or datetime; for numeric timestamps use "
                "epoch_to_datetime().",
            )
        )

    if force_utc and is_dt_naive(dt):
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def is_dt_naive(dt: datetime) -> bool:
    """
    Return ``True`` if *dt* has no timezone information.

    A datetime is considered naive if its ``tzinfo`` attribute is ``None``
    or if ``dt.tzinfo.utcoffset(dt)`` returns ``None``.

    Parameters
    ----------
    dt : datetime
        The datetime object to inspect.

    Returns
    -------
    bool
        ``True`` if *dt* is naive (no timezone); ``False`` if it is
        timezone-aware.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    ensure_utc : Attach UTC timezone info to a naive datetime.
    convert_to_datetime : Parse strings into datetime objects.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> is_dt_naive(datetime(2026, 1, 1))
    True
    >>> is_dt_naive(datetime(2026, 1, 1, tzinfo=timezone.utc))
    False
    """
    _validate_datetime(dt, func_name="is_dt_naive")
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None


def ensure_utc(dt: datetime) -> datetime:
    """
    Return a timezone-aware :class:`datetime` in UTC.

    If *dt* is naive, it is assumed to represent UTC and ``tzinfo`` is
    attached.  If *dt* is already timezone-aware, it is converted to UTC.

    Parameters
    ----------
    dt : datetime
        The datetime to make UTC-aware.  May be naive or aware.

    Returns
    -------
    datetime
        A timezone-aware datetime in UTC (``tzinfo == timezone.utc``).

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    is_dt_naive : Check whether a datetime lacks timezone information.
    shift_tz_by_name : Convert a datetime to a different named timezone.

    Examples
    --------
    >>> from datetime import datetime
    >>> naive = datetime(2026, 4, 24, 12, 0, 0)
    >>> aware = ensure_utc(naive)
    >>> aware.tzinfo is not None
    True

    >>> from datetime import timezone, timedelta
    >>> aware_bst = datetime(2026, 4, 24, 13, 0, 0,
    ...                      tzinfo=timezone(timedelta(hours=1)))
    >>> ensure_utc(aware_bst).hour
    12
    """
    _validate_datetime(dt, func_name="ensure_utc")
    if is_dt_naive(dt):
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def start_of_day(dt: datetime) -> datetime:
    """
    Return *dt* with the time component set to midnight (``00:00:00.000000``).

    Preserves the ``tzinfo`` of the input datetime unchanged.

    Parameters
    ----------
    dt : datetime
        The reference datetime.  May be naive or timezone-aware.

    Returns
    -------
    datetime
        A copy of *dt* with ``hour=0``, ``minute=0``, ``second=0``,
        and ``microsecond=0``.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    end_of_day : Return the last microsecond of the same day.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = datetime(2026, 4, 24, 15, 30, 45, 123456)
    >>> start_of_day(dt)
    datetime.datetime(2026, 4, 24, 0, 0)
    """
    _validate_datetime(dt, func_name="start_of_day")
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """
    Return *dt* with the time component set to ``23:59:59.999999``.

    Preserves the ``tzinfo`` of the input datetime unchanged.

    Parameters
    ----------
    dt : datetime
        The reference datetime.  May be naive or timezone-aware.

    Returns
    -------
    datetime
        A copy of *dt* with ``hour=23``, ``minute=59``, ``second=59``,
        and ``microsecond=999999``.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime` instance.

    See Also
    --------
    start_of_day : Return midnight of the same day.

    Examples
    --------
    >>> from datetime import datetime
    >>> dt = datetime(2026, 4, 24, 0, 0, 0)
    >>> eod = end_of_day(dt)
    >>> eod.hour, eod.minute, eod.second, eod.microsecond
    (23, 59, 59, 999999)
    """
    _validate_datetime(dt, func_name="end_of_day")
    return dt.replace(hour=23, minute=59, second=59, microsecond=999_999)


def format_iso8601(dt: datetime, digits: int = 3) -> str:
    """
    Format *dt* as a UTC ISO 8601 string ending in ``Z``.

    The datetime is converted to UTC first (naive = UTC, as in
    :func:`ensure_utc`).  The fraction of a second is **cut** to *digits*,
    never rounded, so ``23:59:59.9999`` stays in the same second (and day).

    Parameters
    ----------
    dt : datetime
        The datetime to format.  May be naive (assumed UTC) or aware.
    digits : int, optional
        Fractional-second digits, ``0`` to ``6``.  Default ``3``
        (milliseconds, e.g. ``2026-11-15T12:00:00.123Z``).  ``0`` writes no
        fraction and no decimal point (``2026-11-15T12:00:00Z``).

    Returns
    -------
    str
        ``YYYY-MM-DDTHH:MM:SS[.f…]Z``.  With *digits* 1 to 6 it reads back
        with ``datetime.strptime(text, ISO8601)``.

    Raises
    ------
    TypeError
        If *dt* is not a :class:`datetime`, or *digits* is not an ``int``.
    ValueError
        If *digits* is outside ``0`` to ``6``.

    See Also
    --------
    ISO8601 : ``strftime``/``strptime`` format (writes six digits).
    ensure_utc : Convert a datetime to UTC.

    Examples
    --------
    >>> from datetime import datetime
    >>> format_iso8601(datetime(2026, 11, 15, 12, 0, 0, 123456))
    '2026-11-15T12:00:00.123Z'
    >>> format_iso8601(datetime(2026, 11, 15, 12, 0, 0, 123456), digits=6)
    '2026-11-15T12:00:00.123456Z'
    >>> format_iso8601(datetime(2026, 11, 15, 12, 0, 0, 999999), digits=0)
    '2026-11-15T12:00:00Z'
    """
    _validate_datetime(dt, func_name="format_iso8601")
    _validate_integer(digits, func_name="format_iso8601", name="digits")
    if not 0 <= digits <= _ISO_MAX_DIGITS:
        raise ValueError(
            _warn(
                "format_iso8601",
                f"digits must be 0 to {_ISO_MAX_DIGITS}, got {digits}.",
            )
        )
    u = ensure_utc(dt)
    # Written by hand: strftime's %Y does not pad years below 1000 everywhere.
    text = (
        f"{u.year:04d}-{u.month:02d}-{u.day:02d}"
        f"T{u.hour:02d}:{u.minute:02d}:{u.second:02d}"
    )
    if digits:
        text += "." + f"{u.microsecond:06d}"[:digits]
    return text + "Z"


def shift_tz_by_name(dt: datetime, tz_name: str) -> datetime:
    """
    Convert *dt* to the named IANA timezone.

    The datetime is first anchored to UTC (via :func:`ensure_utc`), then
    converted to the target timezone, ensuring the absolute point-in-time
    is preserved regardless of the input timezone.

    Parameters
    ----------
    dt : datetime
        The datetime to convert.  May be naive (assumed UTC) or
        timezone-aware.
    tz_name : str
        A valid IANA timezone name string, e.g. ``'America/New_York'``,
        ``'Asia/Tehran'``, ``'Europe/London'``.

    Returns
    -------
    datetime
        A timezone-aware datetime in the target IANA timezone.

    Raises
    ------
    ImportError
        If ``zoneinfo`` is not available.  ``timezonefinder`` is not needed.
    TypeError
        If *dt* is not a :class:`datetime` instance, or *tz_name* is not
        a ``str``.
    ValueError
        If *tz_name* is an empty string.
    ZoneInfoNotFoundError
        If *tz_name* is not a recognised IANA timezone identifier.

    See Also
    --------
    point_to_tz_offset : Look up the IANA timezone name from a location.
    ensure_utc : Convert a datetime to UTC without changing the point in time.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> utc_dt = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)
    >>> local = shift_tz_by_name(utc_dt, "America/New_York")
    >>> local.hour   # UTC-4 in April (EDT)
    8
    """
    if not _ZONEINFO_AVAILABLE:
        raise ImportError(
            _warn(
                "shift_tz_by_name",
                "zoneinfo is required (standard library, Python 3.9+).",
            )
        )
    _validate_datetime(dt, func_name="shift_tz_by_name")
    _validate_string(tz_name, func_name="shift_tz_by_name")
    dt_utc = ensure_utc(dt)
    try:
        return dt_utc.astimezone(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        raise ZoneInfoNotFoundError(
            _warn(
                "shift_tz_by_name",
                f"Timezone {tz_name!r} not recognised. "
                "Use a valid IANA name such as 'Europe/London' or 'Asia/Tehran'.",
            )
        )


# ── Timezone lookup ───────────────────────────────────────────────────────────

def point_to_tz_offset(pt: Point, eval_dt: datetime) -> Tuple[str, float]:
    """
    Return the IANA timezone name and UTC offset (hours) for a location.

    The offset is DST-adjusted: it reflects the actual civil time offset
    in effect at *eval_dt*, not a fixed standard-time offset.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    eval_dt : datetime
        Reference datetime used to determine whether DST is in effect.
        Naive datetimes are assumed to be UTC.

    Returns
    -------
    tuple of (str, float)
        * ``iana_timezone_name`` : str — e.g. ``'Europe/London'``.
        * ``offset_in_hours`` : float — UTC offset in hours (e.g. ``1.0``
          for BST, ``-5.0`` for EST).

        At sea ``timezonefinder`` gives the nautical zone (e.g.
        ``'Etc/GMT+2'`` at 30° W on the equator).  If it finds no zone at
        all, the result is ``('UTC', 0.0)``.

    Raises
    ------
    ImportError
        If ``timezonefinder`` is not installed.
    TypeError
        If *pt* is not a :class:`shapely.geometry.Point`, or *eval_dt* is
        not a :class:`datetime`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    shift_tz_by_name : Convert a datetime to a timezone name you already know.
    get_solar_data : Full solar event report (uses this function internally).

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> tz_name, offset = point_to_tz_offset(
    ...     Point(-0.1278, 51.5074), datetime(2026, 4, 24)
    ... )
    >>> tz_name
    'Europe/London'
    >>> offset   # BST in April: UTC+1
    1.0
    """
    _require_tz("point_to_tz_offset")
    _validate_point(pt, func_name="point_to_tz_offset")
    _validate_datetime(eval_dt, func_name="point_to_tz_offset")

    tz_name = _tz_name_at(pt)
    local_dt = ensure_utc(eval_dt).astimezone(ZoneInfo(tz_name))
    offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    return tz_name, offset_hours


def to_local_time(dt: datetime, pt: Point) -> datetime:
    """
    Convert *dt* to the local time at *pt*.

    Looks up the IANA timezone at *pt* (as :func:`point_to_tz_offset`
    does) and converts *dt* to it, keeping the same moment.  Daylight
    saving is the rule in effect at *dt*.  At sea ``timezonefinder`` gives
    the nautical zone (e.g. ``Etc/GMT+2`` at 30° W on the equator); if it
    finds no zone at all, UTC is used.

    Parameters
    ----------
    dt : datetime
        The moment to convert.  May be naive (assumed UTC) or aware.
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).

    Returns
    -------
    datetime
        A timezone-aware datetime in the location's timezone.

    Raises
    ------
    ImportError
        If ``timezonefinder`` is not installed.
    TypeError
        If *dt* is not a :class:`datetime`, or *pt* is not a
        :class:`shapely.geometry.Point`.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    shift_tz_by_name : Convert to a timezone name you already know.
    point_to_tz_offset : The timezone name and UTC offset at a location.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> from shapely.geometry import Point
    >>> noon_utc = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    >>> local = to_local_time(noon_utc, Point(139.6917, 35.6895))   # Tokyo
    >>> local.hour, str(local.tzinfo)
    (21, 'Asia/Tokyo')
    """
    _require_tz("to_local_time")
    _validate_datetime(dt, func_name="to_local_time")
    _validate_point(pt, func_name="to_local_time")
    return ensure_utc(dt).astimezone(ZoneInfo(_tz_name_at(pt)))


# ── Sun position ──────────────────────────────────────────────────────────────

def _sun_altitude_azimuth(pt: Point, when: datetime, elevation: float) -> Tuple[float, float]:
    """Geometric altitude and azimuth (degrees) of the sun's centre at *when*."""
    obs = _ephem_observer(pt, elevation, 0.0)
    sun = _ephem.Sun()
    altitude = _altitude_deg(obs, sun, when)
    return altitude, math.degrees(sun.az)


def _check_sun_inputs(pt: Point, when: datetime, elevation, caller: str) -> None:
    _require_ephem(caller)
    _validate_point(pt, func_name=caller)
    _validate_datetime(when, func_name=caller)
    _validate_number(elevation, func_name=caller, name="elevation")


def sun_position(pt: Point, when: datetime, elevation: float = 0.0) -> dict:
    """
    Return where the sun is in the sky at a moment, seen from a location.

    Uses ``ephem``.  The altitude is the **geometric** height of the sun's
    centre, without refraction: the same height :func:`get_solar_data`
    and :func:`is_daylight` measure against (sunrise is at -0.833°, which
    already allows for refraction and the sun's radius).

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    when : datetime
        The moment.  May be naive (assumed UTC) or aware.
    elevation : float, optional
        Observer elevation above sea level in metres.  Default ``0.0``.
        It moves the position by far less than a degree.

    Returns
    -------
    dict
        * ``'Altitude (Degrees)'`` : float — ``-90`` to ``90``; above
          ``0`` the centre is above the true horizon.
        * ``'Azimuth (Degrees)'`` : float — ``0`` to ``360``, clockwise
          from true north (``90`` = east).

    Raises
    ------
    ImportError
        If ``ephem`` is not installed.  ``timezonefinder`` is not needed.
    TypeError
        If *pt* is not a Point, *when* is not a datetime, or *elevation*
        is not a number.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    is_daylight : Whether the sun is up at a moment.
    get_solar_data : Sunrise, sunset and twilight for a day.
    TWILIGHT_DEPRESSION_ANGLES : Compare the altitude with ``-angle``.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> from shapely.geometry import Point
    >>> pos = sun_position(Point(0.0, 0.0), datetime(2026, 3, 20, 12, 7, tzinfo=timezone.utc))
    >>> pos["Altitude (Degrees)"] > 89
    True
    """
    _check_sun_inputs(pt, when, elevation, "sun_position")
    altitude, azimuth = _sun_altitude_azimuth(pt, ensure_utc(when), elevation)
    return {"Altitude (Degrees)": altitude, "Azimuth (Degrees)": azimuth}


def is_daylight(pt: Point, when: datetime, elevation: float = 0.0) -> bool:
    """
    Return ``True`` if the sun is up at *pt* at the moment *when*.

    "Up" means between sunrise and sunset as :func:`get_solar_data`
    defines them: the sun's centre is above -0.833° (refraction plus the
    sun's radius), less the horizon dip for *elevation*.  Twilight counts
    as not daylight; for twilight, compare
    ``sun_position(...)['Altitude (Degrees)']`` with
    ``-TWILIGHT_DEPRESSION_ANGLES[name]``.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    when : datetime
        The moment.  May be naive (assumed UTC) or aware.
    elevation : float, optional
        Observer elevation above sea level in metres.  Default ``0.0``.

    Returns
    -------
    bool

    Raises
    ------
    ImportError
        If ``ephem`` is not installed.  ``timezonefinder`` is not needed.
    TypeError
        If *pt* is not a Point, *when* is not a datetime, or *elevation*
        is not a number.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    See Also
    --------
    sun_position : The sun's altitude and azimuth.
    get_solar_data : Sunrise, sunset and twilight for a day.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> from shapely.geometry import Point
    >>> london = Point(-0.1278, 51.5074)
    >>> is_daylight(london, datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc))
    True
    >>> is_daylight(london, datetime(2026, 6, 21, 0, 0, tzinfo=timezone.utc))
    False
    """
    _check_sun_inputs(pt, when, elevation, "is_daylight")
    altitude, _ = _sun_altitude_azimuth(pt, ensure_utc(when), elevation)
    return altitude > _SUN_HORIZON_DEG - _horizon_dip_deg(elevation)


# ── Solar data ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def get_solar_data(
    pt: Point,
    eval_dt: datetime,
    elevation: float = 0.0,
    include_twilight: bool = True,
) -> dict:
    """
    Compute solar events and twilight phases for a location on a given date.

    Identifies the local IANA timezone for *pt*, then calculates sunrise,
    sunset, solar noon, day length, and all three standard twilight phases
    (Civil, Nautical, Astronomical) with ``ephem``.  All times are
    localised to the geographic timezone of *pt*.

    Events are for the *local* calendar day at *pt*.  Sunrise is the sun's
    centre rising through -0.833° (refraction plus the sun's radius), less
    the horizon dip for *elevation*; twilight uses the depression angle.
    Solar noon is the sun's transit (highest point) on that day.

    * **Polar day / night.**  If the sun never crosses a height that day, the
      matching values are ``None``.  ``'Day Length (Hours)'`` is then the
      length of the local day (normally ``24.0``) or ``0.0``.
    * **More than one sunrise or sunset.**  Near the start or end of a polar
      period the sun can set just after midnight and rise again, or set and
      not rise.  ``'Sunrise'`` is the first rise of the day and ``'Sunset'``
      the last set, so ``'Sunset'`` can be *earlier* than ``'Sunrise'``
      (``Sunset - Sunrise`` is then negative).  ``'Day Length (Hours)'``
      counts every hour the sun is up, wherever in the day.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    eval_dt : datetime
        Reference datetime; picks the day.  An aware datetime is converted
        to the location's timezone and that local date is used (08:00 in
        Tokyo is that Tokyo day).  A naive datetime's date is used as
        written.  The UTC offset reported is the one in effect at *eval_dt*
        (naive = UTC).
    elevation : float, optional
        Observer elevation above sea level in metres.  Default ``0.0``.
    include_twilight : bool, optional
        If ``False``, twilight phase keys are returned as ``None``.
        Default ``True``.

    Returns
    -------
    dict
        Keys: ``'Locality Point'``, ``'Evaluation Date'``,
        ``'Timezone Name'``, ``'Timezone Offset (Hours)'``,
        ``'Elevation (m)'``, ``'Sunrise'``, ``'Sunset'``,
        ``'Solar Noon'``, ``'Day Length (Hours)'``,
        ``'Civil'``, ``'Nautical'``, ``'Astronomical'``.

        Each twilight key maps to a dict with ``'Dawn'``, ``'Dusk'``,
        and ``'Depression'``, or ``None`` if *include_twilight* is ``False``.

    Raises
    ------
    ImportError
        If ``ephem`` or ``timezonefinder`` is not installed.
    TypeError
        If *pt* or *eval_dt* are wrong types.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    Notes
    -----
    Results are cached up to 512 unique argument combinations via
    :func:`functools.lru_cache`.  Do not mutate the returned dictionary.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> data = get_solar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
    >>> data["Timezone Name"]
    'Europe/London'
    >>> data["Day Length (Hours)"] > 0
    True
    """
    _require_astro_deps("get_solar_data")
    _validate_point(pt, func_name="get_solar_data")
    _validate_datetime(eval_dt, func_name="get_solar_data")

    eval_dt_utc, tz_name, tz_offset, local_tz, target_date = _astro_context(pt, eval_dt)
    # A higher observer sees further round the Earth: the horizon dips.
    dip = _horizon_dip_deg(elevation)
    day_start, day_end = _local_day_bounds(target_date, local_tz)
    sun = _ephem.Sun()

    def crossings_at(height_deg):
        obs = _ephem_observer(pt, elevation, height_deg)
        found = _day_crossings(obs, sun, day_start, day_end, local_tz, use_center=True)
        return obs, found

    obs, sun_crossings = crossings_at(_SUN_HORIZON_DEG - dip)
    rise = _first_rise(sun_crossings)
    set_ = _last_set(sun_crossings)
    start_above = _altitude_deg(obs, sun, day_start) > _SUN_HORIZON_DEG - dip
    day_length = _hours_above(start_above, day_start, day_end, sun_crossings)
    solar_noon = _from_ephem_date(
        obs.next_transit(sun, start=_to_ephem_date(day_start)), local_tz
    )

    if include_twilight:
        twilights = {}
        for name, angle in TWILIGHT_DEPRESSION_ANGLES.items():
            _, crossings = crossings_at(-angle - dip)
            twilights[name] = {
                "Dawn":       _first_rise(crossings),
                "Dusk":       _last_set(crossings),
                "Depression": angle,
            }
    else:
        twilights = {name: None for name in TWILIGHT_DEPRESSION_ANGLES}

    return {
        "Locality Point":          pt,
        "Evaluation Date":         target_date,
        "Timezone Name":           tz_name,
        "Timezone Offset (Hours)": tz_offset,
        "Elevation (m)":           elevation,
        "Sunrise":                 rise,
        "Sunset":                  set_,
        "Solar Noon":              solar_noon,
        "Day Length (Hours)":      day_length,
        **twilights,
    }


# ── Lunar data ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def get_lunar_data(
    pt: Point,
    eval_dt: datetime,
    elevation: float = 0.0,
    include_riseset: bool = True,
) -> dict:
    """
    Return lunar phase, illumination, and rise/set times for a location.

    Computed with ``ephem``.  Phase, age and illumination are for local
    noon on the day.  Moonrise and moonset are the first rise and last set
    of the moon's upper edge (with 34' of refraction) during the local day;
    the moon skips a rise or a set about once a month, and that value is
    then ``None``.

    Parameters
    ----------
    pt : shapely.geometry.Point
        WGS-84 location (``x = longitude``, ``y = latitude``).
    eval_dt : datetime
        Reference datetime; picks the local day at *pt*, as in
        :func:`get_solar_data` (aware → converted to the location's
        timezone first; naive → its date as written).
    elevation : float, optional
        Observer elevation in metres.  Default ``0.0``.
    include_riseset : bool, optional
        If ``False``, moonrise/moonset computation is skipped.
        Default ``True``.

    Returns
    -------
    dict
        Keys: ``'Locality Point'``, ``'Evaluation Date'``,
        ``'Timezone Name'``, ``'Timezone Offset (Hours)'``,
        ``'Elevation (m)'``, ``'Lunation (Fraction)'``, ``'Phase Name'``,
        ``'Moon Age (Days)'``, ``'Is Waxing'``, ``'Illumination (%)'``,
        ``'Moonrise'``, ``'Moonset'``.

        * ``'Lunation (Fraction)'`` — how far through this lunation (new
          moon to next new moon) the moment is, in [0, 1): 0 = new moon,
          about 0.25 = first quarter, 0.5 = full, 0.75 = last quarter.
          Comparable across months of different lengths.
        * ``'Moon Age (Days)'`` — days since the last new moon (0–29.9).
        * ``'Phase Name'`` — ``'New Moon'``, ``'First Quarter'``,
          ``'Full Moon'`` or ``'Last Quarter'`` within 12 hours of that
          moment, otherwise ``'Waxing Crescent'``, ``'Waxing Gibbous'``,
          ``'Waning Gibbous'`` or ``'Waning Crescent'``.
        * ``'Illumination (%)'`` — share of the disc lit.

    Raises
    ------
    ImportError
        If ``ephem`` or ``timezonefinder`` is not installed.
    TypeError
        If *pt* or *eval_dt* are wrong types.
    ValueError
        If *pt* coordinates are outside WGS-84 bounds.

    Notes
    -----
    Results are cached up to 512 unique argument combinations via
    :func:`functools.lru_cache`.  Do not mutate the returned dictionary.

    Examples
    --------
    >>> from shapely.geometry import Point
    >>> from datetime import datetime
    >>> data = get_lunar_data(Point(-0.1278, 51.5074), datetime(2026, 4, 24))
    >>> 0.0 <= data["Lunation (Fraction)"] < 1.0
    True
    >>> 0.0 <= data["Illumination (%)"] <= 100.0
    True
    """
    _require_astro_deps("get_lunar_data")
    _validate_point(pt, func_name="get_lunar_data")
    _validate_datetime(eval_dt, func_name="get_lunar_data")

    eval_dt_utc, tz_name, tz_offset, local_tz, target_date = _astro_context(pt, eval_dt)

    day_start, day_end = _local_day_bounds(target_date, local_tz)
    local_noon = datetime(target_date.year, target_date.month, target_date.day, 12,
                          tzinfo=local_tz)
    when = _to_ephem_date(local_noon)
    moon = _ephem.Moon(when)
    illumination = moon.phase          # percent of the disc lit
    age = _moon_age_days(when)
    waxing = _is_waxing(when)

    moonrise = moonset = None
    if include_riseset:
        obs = _ephem_observer(pt, elevation, _MOON_HORIZON_DEG - _horizon_dip_deg(elevation))
        crossings = _day_crossings(obs, _ephem.Moon(), day_start, day_end, local_tz,
                                   use_center=False)
        moonrise, moonset = _first_rise(crossings), _last_set(crossings)

    return {
        "Locality Point":          pt,
        "Evaluation Date":         target_date,
        "Timezone Name":           tz_name,
        "Timezone Offset (Hours)": tz_offset,
        "Elevation (m)":           elevation,
        # Wrap after rounding: just before a new moon 0.99997 would round to
        # 1.0, which is the next lunation's 0.0.
        "Lunation (Fraction)":     round(_lunation_fraction(when), 4) % 1.0,
        "Phase Name":              _moon_phase_name(when, age, illumination, waxing),
        "Moon Age (Days)":         round(age, 1),
        "Is Waxing":               waxing,
        "Illumination (%)":        round(illumination, 1),
        "Moonrise":                moonrise,
        "Moonset":                 moonset,
    }
