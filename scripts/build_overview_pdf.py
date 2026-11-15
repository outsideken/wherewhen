#!/usr/bin/env python3
"""
Build the wherewhen toolkit overview (2 pages, customer-facing).

Usage:
    python scripts/build_overview_pdf.py [output_path]

Default output: ~/Code/geo-toolkit/reports/wherewhen_overview_v<version>.pdf
The tracked copy is rebuilt in each release PR:
    ../.venv/bin/python scripts/build_overview_pdf.py "wherewhen Overview.pdf"

The version, test count and function counts come from scripts/_pdf_facts.py
(this checkout and a live test run). Every number on page 2 and every result
in the page 1 code is computed here, from this checkout, when the PDF is
built; each carries a labelled source line (Data · Functions · Test ·
Script). If a measured result stops matching what the text says about it,
the build stops.

Same look as the jematools and h3tools overviews. The status emoji are drawn
as images from Noto Color Emoji (SIL Open Font License 1.1), expected at
~/Code/geo-toolkit/_fonts/noto-color-emoji/. PDF fonts can't draw colour
emoji, and Apple's emoji aren't licensed for documents we hand out.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# ── Brand palette (matches the jematools and h3tools overviews) ───────────
INK = HexColor("#2b2b2b")
MUTED = HexColor("#525252")
SOFT = HexColor("#737373")
RULE = HexColor("#d0d0d0")
BG = HexColor("#f7f7f7")
CARD = HexColor("#ffffff")
ACCENT = HexColor("#cb181d")       # primary
ACCENT_2 = HexColor("#0570b0")     # info / secondary
ACCENT_3 = HexColor("#fd8d3c")     # caution
ACCENT_4 = HexColor("#41ab5d")     # success / stable
ACCENT_5 = HexColor("#807dba")     # platform / JEMA

import _pdf_facts as facts  # noqa: E402  (puts this checkout first on sys.path)
import wherewhen  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from wherewhen import crs as _crs  # noqa: E402

VERSION = wherewhen.__version__
import re as _re  # noqa: E402
_ci = (facts.REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
CI_PYTHONS = sorted(set(_re.findall(r'python-version:\s*"([0-9.]+)"', _ci)), key=lambda v: tuple(map(int, v.split("."))))
if not CI_PYTHONS or CI_PYTHONS[0] != "3.9":
    facts.fail(f"CI no longer tests Python 3.9 (found {CI_PYTHONS}); page 2 says it does.")
N_TESTS = facts.passing_tests()

# Areas and the functions in each. The counts are computed from these lists,
# and the build stops if the lists don't match the package's public functions.
SECTIONS = [
    ("coordinates", ["coordinate_to_point", "mgrs_to_point", "dms_to_point", "ddm_to_point",
                     "latlon_to_point", "point_to_latlon", "point_to_mgrs", "point_to_dms",
                     "point_to_ddm", "normalize_longitude", "normalize_latlon"],
     "Read MGRS, DMS and DDM strings (spaces allowed) into Shapely\nPoints, write them back out, normalise lat/lon"),
    ("distance", ["point_distance", "point_distance_km", "point_bearing", "point_at_distance",
                  "spherical_weighted_centroid", "segment_crosses_antimeridian"],
     "Great-circle distance in m / km / nm / mi, bearing, destination\npoint, weighted centroid, antimeridian crossings"),
    ("bounds", ["geometry_to_box", "box_to_polygon", "get_ratio", "get_bounds", "get_polygon",
                "unwrap_single_collection", "demote_single_multi"],
     "Bounding boxes, PostGIS BOX strings, padded bounds and\naspect ratio, tidy single-part geometries"),
    ("datetime", ["convert_to_datetime", "epoch_to_datetime", "ensure_utc", "is_dt_naive",
                  "start_of_day", "end_of_day", "format_iso8601"],
     "Parse strings and s / ms / µs / ns epochs, make UTC-aware,\nday bounds, ISO 8601 'Z' strings"),
    ("timezones", ["point_to_tz_offset", "to_local_time", "shift_tz_by_name"],
     "IANA timezone and DST-aware offset from a location,\nlocal time at a point or by zone name"),
    ("sun & moon", ["get_solar_data", "get_lunar_data", "sun_position", "is_daylight"],
     "Sunrise, sunset, twilight, polar day and night; moon phase,\nillumination, moonrise; sun position at any moment"),
    ("crs", ["convert_crs", "wgs84_to_cn_gcj02", "cn_gcj02_to_wgs84", "wgs84_to_cn_bd09",
             "cn_bd09_to_wgs84", "wgs84_to_ru_sk42", "ru_sk42_to_wgs84"],
     "China's GCJ-02 and BD-09 (applied only inside China),\nRussia's SK-42, any pair through convert_crs"),
]
_listed = [f for _, fns, _ in SECTIONS for f in fns]
_actual = facts.public_functions(wherewhen)
if len(_listed) != len(set(_listed)) or set(_listed) != _actual:
    facts.fail(
        "SECTIONS doesn't match wherewhen's public functions. "
        f"Missing: {sorted(_actual - set(_listed))}; not in the package: {sorted(set(_listed) - _actual)}."
    )
AREAS = [(name, len(fns), text) for name, fns, text in SECTIONS]
N_FUNCS = len(_listed)
MODULES = ("geometry", "temporal", "crs")
for _m in MODULES:
    __import__(f"wherewhen.{_m}")
N_MODULES = len(MODULES)
N_CRS = 1 + len(_crs._TO_WGS84)      # WGS-84 plus every CRS convert_crs routes through it

CORE_API = [
    ("coordinate_to_point", "One call for any supported coordinate string — MGRS, DMS or DDM — returning a "
                            "WGS-84 Shapely Point. Bad input raises a labelled error, never a silent guess."),
    ("point_distance", "Great-circle distance between two Points in metres, km, nautical miles or miles; "
                       "point_bearing and point_at_distance for the rest of the triangle."),
    ("get_solar_data", "Sunrise, sunset, solar noon, day length and all three twilights for the local "
                       "day at a Point, in that Point's own timezone; polar day and night included."),
    ("convert_crs", f"Convert a Point between any two of {N_CRS} CRS — WGS84, GCJ02, BD09, SK42. The "
                    "Chinese offsets apply only inside mainland China, Hong Kong and Macau."),
]


def _source(data=None, functions=(), test=None, script=None, notebook=None) -> str:
    """One labelled provenance line: ``Data: … · Notebook: … · Functions: … · Test: … · Script: …``.

    Every figure and demo carries one, and each part must name a real dataset,
    notebook section, public function, test or script in this repo.
    """
    for name in functions:
        if name not in _actual:
            facts.fail(f"source line names {name!r}, which is not a public wherewhen function.")
    for path in (test, script):
        if path and not (facts.REPO / path.split("::")[0]).exists():
            facts.fail(f"source line names {path!r}, which is not in this repo.")
    parts = []
    if data:
        parts.append(f"Data: {data}")
    if notebook:
        parts.append(f"Notebook: {notebook}")
    if functions:
        parts.append("Functions: " + ", ".join(functions))
    if test:
        parts.append(f"Test: {test}")
    if script:
        parts.append(f"Script: {script}")
    return "  ·  ".join(parts)


# ── Measurements (all computed now, from this checkout) ────────────────────

LIBERTY_DDM = "40°41.352'N 74°02.670'W"     # Statue of Liberty
HEATHROW_DDM = "51°28.200'N 0°27.250'W"
NOON_UTC = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)

LIBERTY = wherewhen.coordinate_to_point(LIBERTY_DDM)
HEATHROW = wherewhen.coordinate_to_point(HEATHROW_DDM)
LIBERTY_MGRS = wherewhen.point_to_mgrs(LIBERTY)
LIB_TO_LHR_KM = wherewhen.point_distance(LIBERTY, HEATHROW, units="km")
LIB_LOCAL = wherewhen.to_local_time(NOON_UTC, LIBERTY)
LIB_ISO = wherewhen.format_iso8601(NOON_UTC)
LIB_SUNRISE = wherewhen.get_solar_data(LIBERTY, NOON_UTC)["Sunrise"]

WHERE_SNIPPET = [
    "from wherewhen import (coordinate_to_point,",
    "                       point_to_mgrs, point_distance)",
    f'liberty = coordinate_to_point("{LIBERTY_DDM}")',
    "point_to_mgrs(liberty)",
    f"# → {LIBERTY_MGRS!r}",
    f'lhr = coordinate_to_point("{HEATHROW_DDM}")',
    "point_distance(liberty, lhr, units='km')",
    f"# → {LIB_TO_LHR_KM:,.1f}",
]
WHEN_SNIPPET = [
    "from datetime import datetime, timezone",
    "from wherewhen import (to_local_time, format_iso8601,",
    "                       get_solar_data)",
    "noon = datetime(2026, 6, 21, 12, tzinfo=timezone.utc)",
    "to_local_time(noon, liberty).strftime('%H:%M %Z')",
    f"# → {LIB_LOCAL.strftime('%H:%M %Z')!r}",
    "format_iso8601(noon)",
    f"# → {LIB_ISO!r}",
    "get_solar_data(liberty, noon)['Sunrise'].strftime('%H:%M')",
    f"# → {LIB_SUNRISE.strftime('%H:%M')!r}",
]
CODE_SOURCE = _source(functions=("coordinate_to_point", "point_to_mgrs", "point_distance",
                                 "to_local_time", "format_iso8601", "get_solar_data"))

# China CRS: how far each conversion moves a city, in metres.
CHINA_CITIES = [
    ("Beijing", Point(116.3912, 39.9073), True),
    ("Hong Kong", Point(114.1694, 22.3193), True),
    ("Seoul", Point(126.9780, 37.5665), False),
    ("Taipei", Point(121.5654, 25.0330), False),
    ("Hanoi", Point(105.8342, 21.0278), False),
    ("Moscow", Point(37.6173, 55.7558), False),
]


def _moved_m(pt, convert, **kw) -> float:
    return wherewhen.point_distance(pt, convert(pt, **kw), units="m")


CHINA_ROWS = []
for _name, _pt, _inside in CHINA_CITIES:
    _gcj = _moved_m(_pt, wherewhen.wgs84_to_cn_gcj02)
    _bd = _moved_m(_pt, wherewhen.wgs84_to_cn_bd09)
    _forced = _moved_m(_pt, wherewhen.wgs84_to_cn_bd09, skip_region_check=True)
    if _inside != (_gcj > 1.0 and _bd > 1.0):
        facts.fail(f"{_name}: GCJ-02 moved it {_gcj:.1f} m and BD-09 {_bd:.1f} m; page 2 says it is "
                   f"{'inside' if _inside else 'outside'} the region.")
    if _forced < 100:
        facts.fail(f"{_name}: skip_region_check=True moved it only {_forced:.1f} m.")
    CHINA_ROWS.append((_name, _gcj, _bd, _forced, _inside))
CHINA_SOURCE = _source(
    data="Natural Earth 1:10m Admin 0 (China, Hong Kong, Macau)",
    functions=("wgs84_to_cn_gcj02", "wgs84_to_cn_bd09", "point_distance"),
    test="tests/test_crs.py::TestChinaRegion",
    script="scripts/build_china_region.py",
)

# Sun: 21 June 2026, local times; is_daylight checked 1 s either side of each event.
SUN_DAY = datetime(2026, 6, 21)
SUN_PLACES = [
    ("London", Point(-0.1278, 51.5074)),
    ("Nairobi", Point(36.8219, -1.2921)),
    ("Sydney", Point(151.2093, -33.8688)),
]
_SECOND = timedelta(seconds=1)
SUN_ROWS = []
for _name, _pt in SUN_PLACES:
    _d = wherewhen.get_solar_data(_pt, SUN_DAY)
    _rise, _set = _d["Sunrise"], _d["Sunset"]
    _agrees = (not wherewhen.is_daylight(_pt, _rise - _SECOND) and wherewhen.is_daylight(_pt, _rise + _SECOND)
               and wherewhen.is_daylight(_pt, _set - _SECOND) and not wherewhen.is_daylight(_pt, _set + _SECOND))
    if not _agrees:
        facts.fail(f"{_name}: is_daylight does not flip within 1 s of get_solar_data's sunrise and sunset.")
    SUN_ROWS.append((_name, _rise.strftime("%H:%M"), _set.strftime("%H:%M"),
                     f"{_d['Day Length (Hours)']:.2f} h", _d["Timezone Name"]))

TROMSO = Point(18.9553, 69.6492)
_summer = wherewhen.get_solar_data(TROMSO, datetime(2026, 6, 21))
_winter = wherewhen.get_solar_data(TROMSO, datetime(2026, 12, 21))
if not (_summer["Sunrise"] is None and _summer["Day Length (Hours)"] == 24.0
        and _winter["Sunrise"] is None and _winter["Day Length (Hours)"] == 0.0
        and _winter["Civil"]["Dawn"] is not None):
    facts.fail("Tromsø is no longer polar day on 21 June and polar night with civil twilight on 21 December.")
TROMSO_SUMMER_H = _summer["Day Length (Hours)"]
TROMSO_CIVIL = (_winter["Civil"]["Dawn"].strftime("%H:%M"), _winter["Civil"]["Dusk"].strftime("%H:%M"))
TROMSO_WINTER_H = _winter["Day Length (Hours)"]

_moon = wherewhen.get_lunar_data(SUN_PLACES[0][1], SUN_DAY)
MOON_LINE = (f"Moon over London that day: {_moon['Phase Name']}, {_moon['Illumination (%)']:.1f}% lit, "
             f"{_moon['Moon Age (Days)']:.1f} days old, rising {_moon['Moonrise'].strftime('%H:%M')}.")
SUN_SOURCE = _source(
    functions=("get_solar_data", "is_daylight", "get_lunar_data"),
    test="tests/test_temporal.py::TestIsDaylight",
)

# Coordinates: write the point out in each format, read it back, measure the gap.
_mgrs_spaced = f"{LIBERTY_MGRS[:5]} {LIBERTY_MGRS[5:10]} {LIBERTY_MGRS[10:]}"
COORD_ROWS = []
for _label, _text in [
    ("DMS", "  ".join(wherewhen.point_to_dms(LIBERTY))),
    ("DDM", "  ".join(wherewhen.point_to_ddm(LIBERTY))),
    ("MGRS (1 m)", LIBERTY_MGRS),
    ("MGRS with spaces", _mgrs_spaced),
]:
    _back = wherewhen.coordinate_to_point(_text)
    _gap = wherewhen.point_distance(LIBERTY, _back, units="m")
    if _gap > 2.0:
        facts.fail(f"{_label} {_text!r} reads back {_gap:.1f} m from where it was written.")
    COORD_ROWS.append((_label, _text, f"{_gap:.1f} m"))
BAD_MGRS = f"{LIBERTY_MGRS[:5]} {LIBERTY_MGRS[5:9]} {LIBERTY_MGRS[9:]}"
try:
    wherewhen.coordinate_to_point(BAD_MGRS)
except ValueError as exc:
    BAD_MGRS_ERROR = str(exc)
else:
    facts.fail(f"{BAD_MGRS!r} (uneven split) no longer raises ValueError.")
if "[coordinate_to_point]" not in BAD_MGRS_ERROR:
    facts.fail(f"the uneven-MGRS error doesn't name coordinate_to_point: {BAD_MGRS_ERROR}")
COORD_SOURCE = _source(
    functions=("coordinate_to_point", "point_to_dms", "point_to_ddm", "point_to_mgrs", "point_distance"),
    test="tests/test_geometry.py::TestMgrsSpacing",
)

# Same emoji and meanings as wherewhen/_messages.py's convention.
OUTPUT_CONVENTIONS = [
    ("⚠", "Error", "every raised error, named for the function you called"),
    ("ℹ", "Informational", "non-fatal notice, e.g. the load line"),
    ("❌", "Skipped", "printed when an item is skipped; never an error"),
    ("✅", "Success", "verbose logging"),
]

EMOJI_FONT = Path.home() / "Code/geo-toolkit/_fonts/noto-color-emoji/NotoColorEmoji.ttf"
_EMOJI_DIR = Path(tempfile.mkdtemp(prefix="wherewhen_emoji_"))
_EMOJI_CACHE: dict = {}


def _emoji_png(ch: str) -> Path:
    """Render one emoji from Noto Color Emoji to a tightly cropped PNG."""
    if ch not in _EMOJI_CACHE:
        from PIL import Image, ImageDraw, ImageFont

        if not EMOJI_FONT.exists():
            raise SystemExit(
                f"Emoji font not found: {EMOJI_FONT}\n"
                "Download NotoColorEmoji.ttf from github.com/googlefonts/noto-emoji (2D/fonts/)."
            )
        font = ImageFont.truetype(str(EMOJI_FONT), 109)  # the font's only bitmap size
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), ch, font=font, embedded_color=True)
        im = im.crop(im.getbbox())
        path = _EMOJI_DIR / f"u{ord(ch):x}.png"
        im.save(path)
        _EMOJI_CACHE[ch] = path
    return _EMOJI_CACHE[ch]


def _draw_emoji(c: canvas.Canvas, ch: str, x: float, baseline: float, size: float) -> float:
    """Draw an emoji *size* points tall sitting on *baseline*; return its width."""
    path = _emoji_png(ch)
    from PIL import Image

    with Image.open(path) as im:
        ratio = im.width / im.height
    c.drawImage(str(path), x, baseline - size * 0.15, width=size * ratio, height=size, mask="auto")
    return size * ratio


# ── Drawing helpers ─────────────────────────────────────────────────────────

def _wrap(c: canvas.Canvas, text: str, x: float, y: float, max_w: float,
          font: str = "Helvetica", size: float = 9, leading: float = 12,
          color=MUTED, align: str = "left") -> float:
    """Draw wrapped text; return y after last line."""
    c.setFont(font, size)
    c.setFillColor(color)
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if c.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    for line in lines:
        if align == "center":
            c.drawCentredString(x + max_w / 2, y, line)
        else:
            c.drawString(x, y, line)
        y -= leading
    return y


def _header(c: canvas.Canvas, page: int, pages: int = 2):
    w, h = letter
    c.setFillColor(INK)
    c.rect(0, h - 36, w, 36, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(0.6 * inch, h - 22, "WHEREWHEN  ·  TOOLKIT OVERVIEW")
    c.setFont("Helvetica", 8)
    c.drawRightString(w - 0.6 * inch, h - 22, f"PAGE {page} OF {pages}")
    c.setFillColor(ACCENT)
    c.rect(0, h - 40, w, 4, fill=1, stroke=0)


def _footer(c: canvas.Canvas):
    w, _ = letter
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(0.6 * inch, 0.45 * inch, w - 0.6 * inch, 0.45 * inch)
    c.setFont("Helvetica", 7)
    c.setFillColor(SOFT)
    c.drawString(0.6 * inch, 0.28 * inch, "wherewhen package  ·  under jematools, h3tools, viztools, tabtools")
    c.drawRightString(w - 0.6 * inch, 0.28 * inch, f"v{VERSION}")


def _card(c: canvas.Canvas, x, y, w, h, fill=CARD, stroke=RULE):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=1)


def _section(c: canvas.Canvas, title: str, intro: str, x: float, y: float, w: float) -> float:
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(x, y, title)
    y -= 12
    return _wrap(c, intro, x, y, w, size=8, leading=10.5) - 4


def _source_line(c: canvas.Canvas, text: str, x: float, y: float, w: float) -> float:
    return _wrap(c, text, x, y, w, font="Helvetica-Oblique", size=6.5, leading=8, color=SOFT)


def _table(c: canvas.Canvas, x: float, y: float, cols: list, header: list, rows: list,
           row_h: float = 11, mono: tuple = ()) -> float:
    """Draw a small table: *cols* are column x-offsets; return y below it."""
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(SOFT)
    for cx, text in zip(cols, header):
        c.drawString(x + cx, y, text)
    y -= 4
    c.setStrokeColor(RULE)
    c.setLineWidth(0.4)
    c.line(x, y, x + cols[-1] + 140, y)
    y -= 9
    for row in rows:
        colour = None
        if isinstance(row, tuple) and len(row) == 2 and isinstance(row[1], dict):
            row, colour = row[0], row[1].get("color")
        for i, (cx, text) in enumerate(zip(cols, row)):
            if i == 0:
                c.setFont("Helvetica-Bold", 7.5)
                c.setFillColor(INK)
            elif i in mono:
                c.setFont("Courier", 7.5)
                c.setFillColor(INK)
            else:
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colour or MUTED)
            c.drawString(x + cx, y, text)
        y -= row_h
    return y


# ── Pages ───────────────────────────────────────────────────────────────────

def page_one(c: canvas.Canvas):
    w, h = letter
    _header(c, 1)
    margin = 0.6 * inch
    y = h - 70

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(margin, y, "wherewhen")
    c.setFont("Helvetica", 11)
    c.setFillColor(MUTED)
    c.drawString(margin + c.stringWidth("wherewhen", "Helvetica-Bold", 28) + 16, y + 4,
                 f"v{VERSION}   ·   {N_TESTS} tests passing")
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(INK)
    c.drawString(margin, y, "The where and when underneath the whole toolkit.")
    y -= 16

    blurb = (
        "wherewhen turns coordinates written in any common military or civil format into Shapely Points, "
        "measures distances and bearings on the globe, and handles the time side: parsing timestamps, "
        "timezones from a location, and sun and moon events. It also converts China's GCJ-02 and BD-09 "
        "and Russia's SK-42 to and from WGS-84. jematools, h3tools, viztools and tabtools all build on it, "
        "and it runs unchanged in Jupyter and inside JEMA's Python blocks."
    )
    y = _wrap(c, blurb, margin, y, w - 2 * margin, size=9, leading=12, color=MUTED)
    y -= 10

    stats = [
        (str(N_FUNCS), "public functions"),
        (str(N_MODULES), "modules: geometry, temporal, crs"),
        (str(N_CRS), "coordinate reference systems"),
        (str(N_TESTS), "tests, all green"),
    ]
    strip_h = 42
    gap = 8
    sw = (w - 2 * margin - 3 * gap) / 4
    for i, (num, label) in enumerate(stats):
        sx = margin + i * (sw + gap)
        _card(c, sx, y - strip_h, sw, strip_h, fill=BG, stroke=RULE)
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(INK)
        c.drawCentredString(sx + sw / 2, y - 20, num)
        c.setFont("Helvetica", 7)
        c.setFillColor(SOFT)
        c.drawCentredString(sx + sw / 2, y - 34, label)
    y -= strip_h + 12

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(margin, y, "What it can do")
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawString(margin + 100, y, f"{N_FUNCS} functions in {facts.number_word(len(AREAS))} areas")
    y -= 8
    c.setStrokeColor(RULE)
    c.line(margin, y, w - margin, y)
    y -= 13

    max_bar = max(a[1] for a in AREAS)
    bar_max_w = 1.4 * inch
    for name, n, desc in AREAS:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawString(margin, y, name)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(SOFT)
        c.drawRightString(margin + 1.3 * inch, y, str(n))
        bw = bar_max_w * (n / max_bar)
        c.setFillColor(HexColor("#e8e8e8"))
        c.roundRect(margin + 1.45 * inch, y - 2, bar_max_w, 9, 2, fill=1, stroke=0)
        c.setFillColor(ACCENT_2)
        c.roundRect(margin + 1.45 * inch, y - 2, bw, 9, 2, fill=1, stroke=0)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTED)
        lines = desc.split("\n")
        for i, line in enumerate(lines):
            c.drawString(margin + 1.45 * inch + bar_max_w + 10, y - i * 8.5, line)
        y -= 21 if len(lines) > 1 else 17

    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(margin, y, "Four functions to start with")
    y -= 12
    y = _wrap(c, "Changes that affect existing results are called out in CHANGELOG.md.",
              margin, y, w - 2 * margin, size=8, leading=10)
    y -= 8

    card_gap = 8
    card_w = (w - 2 * margin - card_gap) / 2
    card_h = 62
    for i, (name, body) in enumerate(CORE_API):
        col, row = i % 2, i // 2
        cx = margin + col * (card_w + card_gap)
        cy = y - (row + 1) * (card_h + card_gap)
        _card(c, cx, cy, card_w, card_h)
        c.setFont("Courier-Bold", 10)
        c.setFillColor(ACCENT_2)
        c.drawString(cx + 10, cy + card_h - 18, name)
        _wrap(c, body, cx + 10, cy + card_h - 32, card_w - 20, size=7.5, leading=10, color=MUTED)
    y = y - 2 * (card_h + card_gap) - 18

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(margin, y, "Where, then when")
    y -= 12
    y = _wrap(c, "The results in the comments were computed from this release when this page was built.",
              margin, y, w - 2 * margin, size=8, leading=10.5)
    y -= 6

    code_gap = 8
    code_w = (w - 2 * margin - code_gap) / 2
    code_h = 112
    if y - code_h - 12 < 0.55 * inch:
        facts.fail(f"page 1 code cards would overflow the footer: y={y:.0f}")
    for i, (label, lines, colour) in enumerate([("WHERE", WHERE_SNIPPET, ACCENT_2),
                                                ("WHEN", WHEN_SNIPPET, ACCENT_4)]):
        cx = margin + i * (code_w + code_gap)
        cy = y - code_h
        _card(c, cx, cy, code_w, code_h, fill=HexColor("#fafafa"))
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(colour)
        c.drawString(cx + 10, cy + code_h - 14, label)
        ty = cy + code_h - 27
        for line in lines:
            c.setFont("Courier", 6.6)
            c.setFillColor(SOFT if line.lstrip().startswith("#") else INK)
            if c.stringWidth(line, "Courier", 6.6) > code_w - 16:
                facts.fail(f"code line too wide for its card: {line!r}")
            c.drawString(cx + 8, ty, line)
            ty -= 9
    y -= code_h + 10
    _source_line(c, CODE_SOURCE, margin, y, w - 2 * margin)
    _footer(c)


def page_two(c: canvas.Canvas):
    w, h = letter
    _header(c, 2)
    margin = 0.6 * inch
    full = w - 2 * margin
    y = h - 58

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(margin, y, "Small, strict and shared")
    y -= 16
    y = _wrap(
        c,
        "Every toolkit package reads coordinates and times through wherewhen, so a fix here reaches all "
        "of them. It is written to the same rules as code running inside JEMA, and every number below "
        "was measured from this release when the page was built.",
        margin, y, full, size=9, leading=12,
    )
    y -= 10

    left_w = 3.4 * inch
    right_x = margin + left_w + 0.15 * inch
    right_w = w - right_x - margin
    box_h = 1.15 * inch
    _card(c, margin, y - box_h, left_w, box_h, fill=BG)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(ACCENT_5)
    c.drawString(margin + 10, y - 16, "JEMA-SAFE")
    rules = [
        f"Python 3.9 syntax; CI runs {' and '.join(CI_PYTHONS)}",
        "No sys, os, pathlib or __future__ imports",
        "No PEP 604 unions (int | None)",
        "Checked on every change by tests/test_jema_runtime_rules.py",
    ]
    ty = y - 30
    for r in rules:
        c.setFillColor(ACCENT_5)
        c.circle(margin + 14, ty + 2, 1.5, fill=1, stroke=0)
        ty = _wrap(c, r, margin + 22, ty, left_w - 34, size=7.5, leading=10, color=MUTED) - 2

    _card(c, right_x, y - box_h, right_w, box_h, fill=BG)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(ACCENT_2)
    c.drawString(right_x + 10, y - 16, "BUILT ON BY")
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(right_x + 10, y - 31, "jematools  ·  h3tools  ·  viztools  ·  tabtools")
    _wrap(
        c,
        "Each declares the lowest wherewhen it supports and versions independently; the toolkit's "
        "COMPATIBILITY.md lists the combinations tested together. wherewhen depends on none of them.",
        right_x + 10, y - 45, right_w - 20, size=7.5, leading=10, color=MUTED,
    )
    y -= box_h + 14

    # China CRS
    y = _section(
        c, "China's offsets, only where China uses them",
        "GCJ-02 and BD-09 are shifts Chinese map services apply inside China. wherewhen applies them only "
        "inside mainland China, Hong Kong and Macau (Taiwan outside); a point elsewhere comes back "
        "unchanged. skip_region_check=True applies the shift anywhere, for data offset outside China. "
        "Distance each conversion moves the city:",
        margin, y, full,
    )
    rows = []
    for name, gcj, bd, forced, inside in CHINA_ROWS:
        fmt = (lambda m: f"{m:,.0f} m") if inside else (lambda m: "unchanged" if m < 0.5 else f"{m:,.1f} m")
        rows.append(((name, fmt(gcj), fmt(bd), f"{forced:,.0f} m"),
                     {"color": None if inside else ACCENT_4}))
    y = _table(c, margin + 10, y - 2, [0, 1.2 * inch, 2.4 * inch, 3.6 * inch],
               ["City", "WGS-84 → GCJ-02", "WGS-84 → BD-09", "BD-09 with skip_region_check=True"], rows)
    y = _source_line(c, CHINA_SOURCE, margin, y - 1, full) - 8

    # Sun and moon
    y = _section(
        c, "Sun and moon, to the second",
        "Events are for the local day, in the place's own timezone (21 June 2026). is_daylight switches "
        "within one second of get_solar_data's sunrise and sunset at every place below:",
        margin, y, full,
    )
    rows = [(name, rise, set_, length, tz) for name, rise, set_, length, tz in SUN_ROWS]
    rows.append(("Tromsø, 21 June", "—", "—", f"{TROMSO_SUMMER_H:.1f} h", "polar day"))
    rows.append(("Tromsø, 21 Dec", "—", "—", f"{TROMSO_WINTER_H:.1f} h",
                 f"polar night; civil twilight {TROMSO_CIVIL[0]}–{TROMSO_CIVIL[1]}"))
    y = _table(c, margin + 10, y - 2, [0, 1.2 * inch, 2.0 * inch, 2.8 * inch, 3.6 * inch],
               ["Place", "Sunrise", "Sunset", "Daylight", "Timezone"], rows)
    y = _wrap(c, MOON_LINE, margin + 10, y + 1, full - 10, size=7.5, leading=10, color=MUTED) - 1
    y = _source_line(c, SUN_SOURCE, margin, y, full) - 8

    # Coordinates
    y = _section(
        c, "Every common coordinate format, one call",
        "The Statue of Liberty written out by wherewhen in each format, then read back with "
        "coordinate_to_point. An MGRS string split unevenly raises an error instead of landing on the "
        "wrong square:",
        margin, y, full,
    )
    y = _table(c, margin + 10, y - 2, [0, 1.2 * inch, 4.2 * inch],
               ["Format", "Written by wherewhen", "Read back, distance from the original"],
               COORD_ROWS, mono=(1,))
    c.setFont("Courier", 7)
    c.setFillColor(INK)
    ex = margin + 10
    c.drawString(ex, y, f"coordinate_to_point({BAD_MGRS!r})  →  ValueError:")
    y -= 10
    ex += 12
    ex += _draw_emoji(c, "⚠", ex, y, 8) + 3
    msg = BAD_MGRS_ERROR.split(" ", 1)[1]          # drop the emoji; it is drawn as an image
    y = _wrap(c, msg, ex, y, margin + full - ex, font="Courier", size=7, leading=9, color=INK) - 3
    y = _source_line(c, COORD_SOURCE, margin, y, full) - 8

    # Output conventions
    y = _section(c, "Consistent, greppable messages",
                 "Every error starts with the name of the function you called. The same symbols run "
                 "through the whole toolkit:", margin, y, full)
    conv_gap = 8
    conv_w = (full - 3 * conv_gap) / 4
    conv_h = 39
    for i, (emoji, label, desc) in enumerate(OUTPUT_CONVENTIONS):
        cx = margin + i * (conv_w + conv_gap)
        _card(c, cx, y - conv_h, conv_w, conv_h, fill=BG)
        _draw_emoji(c, emoji, cx + 8, y - 15, 10)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(INK)
        c.drawString(cx + 23, y - 15, label)
        _wrap(c, desc, cx + 8, y - 27, conv_w - 16, size=6.5, leading=8, color=SOFT)
    y -= conv_h + 10

    cta_h = 40
    if y - cta_h < 0.55 * inch:
        facts.fail(f"page 2 would overflow the footer: y={y:.0f}")
    _card(c, margin, y - cta_h, full, cta_h, fill=INK, stroke=INK)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 14, y - 17, "Install this release")
    c.setFont("Courier", 8)
    c.drawString(margin + 14, y - 31,
                 f'pip install "wherewhen @ git+https://github.com/outsideken/wherewhen.git@wherewhen-v{VERSION}"')
    _footer(c)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    out = Path(argv[0]) if argv else facts.REPORTS / f"wherewhen_overview_v{VERSION}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out), pagesize=letter)
    c.setTitle(f"wherewhen Overview v{VERSION}")
    c.setAuthor("wherewhen")
    c.setSubject("Toolkit overview")
    page_one(c)
    c.showPage()
    page_two(c)
    c.save()
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
