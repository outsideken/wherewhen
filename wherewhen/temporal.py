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
    ``strftime``/``strptime`` format string for ISO 8601 timestamps with
    millisecond precision and literal Z suffix:
    ``"%Y-%m-%dT%H:%M:%S.%fZ"``.
TWILIGHT_DEPRESSION_ANGLES : dict
    Solar depression angles in degrees for the three recognised twilight
    phases: ``'Civil'`` (6°), ``'Nautical'`` (12°), and
    ``'Astronomical'`` (18°).  ``ASTRAL_DEPRESSION_ANGLES`` is the same
    dict under its old name, kept for existing callers.

Functions
---------
epoch_to_datetime
    Convert a numeric Unix timestamp (seconds or milliseconds) to a UTC datetime.
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
shift_tz_by_name
    Convert a datetime to a named IANA timezone.
point_to_tz_offset
    Return the IANA timezone name and UTC offset (hours) for a location.
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
from wherewhen._validators import (
    _validate_datetime,
    _validate_number,
    _validate_point,
    _validate_string,
)

__all__ = [
    "ISO8601",
    "TWILIGHT_DEPRESSION_ANGLES",
    "ASTRAL_DEPRESSION_ANGLES",
    "epoch_to_datetime",
    "convert_to_datetime",
    "is_dt_naive",
    "ensure_utc",
    "start_of_day",
    "end_of_day",
    "shift_tz_by_name",
    "point_to_tz_offset",
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
ISO8601: str = "%Y-%m-%dT%H:%M:%S.%fZ"

TWILIGHT_DEPRESSION_ANGLES: Dict[str, float] = {
    "Civil": 6.0,
    "Nautical": 12.0,
    "Astronomical": 18.0,
}

# Old name, from when astral did the solar maths.  Same dict.
ASTRAL_DEPRESSION_ANGLES: Dict[str, float] = TWILIGHT_DEPRESSION_ANGLES

# Sun's centre at sunrise/sunset: -0.833° = refraction (34') + the sun's
# radius (16'), measured with refraction switched off (pressure 0).
_SUN_HORIZON_DEG: float = -0.833

# Moon's upper edge at moonrise/moonset: -34' of refraction.  ephem already
# includes the moon's parallax (topocentric position).
_MOON_HORIZON_DEG: float = -34.0 / 60.0

# Mean synodic month (new moon to new moon), in days.
_SYNODIC_MONTH_DAYS: float = 29.530588853

# "Phase Number" keeps the 0-28 scale astral used (0 = new, about 7 = first
# quarter, 14 = full, 21 = last quarter): the share of this lunation gone, × 28.
_PHASE_NUMBER_SCALE: float = 28.0

# A principal phase (new, first quarter, full, last quarter) is named when
# the evaluation moment is within this many hours of it.
_PRINCIPAL_PHASE_WINDOW_H: float = 12.0

# Earth radius for the horizon dip of a raised observer (mean radius).
_EARTH_RADIUS_M: float = 6_371_008.8


# ── Private helpers ───────────────────────────────────────────────────────────

def _require_astro_deps(caller: str) -> None:
    """Raise ImportError, naming *caller*, if ephem or timezonefinder is missing."""
    if not _EPHEM_AVAILABLE:
        raise ImportError(
            _warn(
                caller,
                "ephem is required for solar/lunar calculations. "
                "Install with: pip install ephem",
            )
        )
    if not _TZ_AVAILABLE:
        raise ImportError(
            _warn(
                caller,
                "timezonefinder is required to find the location's local timezone. "
                "Install with: pip install timezonefinder",
            )
        )


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
    return math.degrees(math.acos(_EARTH_RADIUS_M / (_EARTH_RADIUS_M + elevation_m)))


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
    the day.
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
        cursor = _ephem.Date(obs.next_antitransit(body, start=cursor) + _ephem.second)
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

# Epoch values above this threshold are treated as milliseconds.
# 1e10 seconds ≈ year 2286, so any value larger is almost certainly ms.
_EPOCH_MS_THRESHOLD: int = 10_000_000_000


def epoch_to_datetime(value: Union[int, float]) -> datetime:
    """
    Convert a numeric Unix timestamp to a UTC-aware datetime.

    Values ≥ 10 000 000 000 are assumed to be **milliseconds** and are divided
    by 1 000 before conversion; smaller values are treated as **seconds**.

    Parameters
    ----------
    value : int or float
        Unix timestamp in seconds or milliseconds.

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
    """
    _validate_number(value, "epoch_to_datetime", "Epoch")
    seconds = value / 1000.0 if abs(value) >= _EPOCH_MS_THRESHOLD else value
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
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

        For locations outside all mapped timezone polygons (e.g. open
        ocean), falls back to ``('UTC', 0.0)``.

    Raises
    ------
    ImportError
        If ``timezonefinder`` or ``zoneinfo`` is not installed.
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
    if not _TZ_AVAILABLE:
        raise ImportError(
            _warn(
                "point_to_tz_offset",
                "timezonefinder is required. "
                "Install with: pip install timezonefinder",
            )
        )
    _validate_point(pt, func_name="point_to_tz_offset")
    _validate_datetime(eval_dt, func_name="point_to_tz_offset")

    tz_name = _TF_INSTANCE.timezone_at(lng=pt.x, lat=pt.y)
    if not tz_name:
        return "UTC", 0.0

    local_dt = ensure_utc(eval_dt).astimezone(ZoneInfo(tz_name))
    offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    return tz_name, offset_hours


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
        ``'Elevation (m)'``, ``'Phase Number'``, ``'Phase Name'``,
        ``'Moon Age (Days)'``, ``'Is Waxing'``, ``'Illumination (%)'``,
        ``'Moonrise'``, ``'Moonset'``, ``'Ephem Available'``.

        * ``'Moon Age (Days)'`` — days since the last new moon (0–29.5).
        * ``'Phase Number'`` — the share of this lunation (new moon to
          next new moon) gone, on astral's old 0–28 scale: 0 = new, about
          7 = first quarter, 14 = full, 21 = last quarter.  Always below 28.
        * ``'Phase Name'`` — ``'New Moon'``, ``'First Quarter'``,
          ``'Full Moon'`` or ``'Last Quarter'`` within 12 hours of that
          moment, otherwise ``'Waxing Crescent'``, ``'Waxing Gibbous'``,
          ``'Waning Gibbous'`` or ``'Waning Crescent'``.
        * ``'Illumination (%)'`` — share of the disc lit.
        * ``'Ephem Available'`` — always ``True`` (kept for existing
          callers; ephem is now required).

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
    >>> 0 <= data["Phase Number"] <= 28
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
        "Phase Number":            round(_lunation_fraction(when) * _PHASE_NUMBER_SCALE, 2),
        "Phase Name":              _moon_phase_name(when, age, illumination, waxing),
        "Moon Age (Days)":         round(age, 1),
        "Is Waxing":               waxing,
        "Illumination (%)":        round(illumination, 1),
        "Moonrise":                moonrise,
        "Moonset":                 moonset,
        "Ephem Available":         _EPHEM_AVAILABLE,
    }
