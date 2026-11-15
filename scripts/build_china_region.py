"""
Build ``wherewhen/_china_region.py``: the region where GCJ-02 and BD-09 apply.

The region is mainland China, Hong Kong and Macau (Taiwan is left out), with a
0.2° (about 20 km) sea margin so coastal waters and small islands count as
inside.  The margin never reaches into another country's land.

Source: Natural Earth 1:10m Admin 0 – Countries (public domain),
https://www.naturalearthdata.com/downloads/10m-cultural-vectors/

Usage (needs geopandas; run from the repository root)::

    python scripts/build_china_region.py path/to/ne_10m_admin_0_countries.shp

Re-run only to change the source data or the parameters below; commit the
regenerated module with the script.
"""

import argparse
from pathlib import Path

import geopandas as gpd
from shapely import set_precision
from shapely.ops import unary_union

INSIDE = ("CHN", "HKG", "MAC")   # Natural Earth ADM0_A3 codes
SEA_MARGIN_DEG = 0.2             # coastal waters and small islands count as inside
SIMPLIFY_DEG = 0.01              # about 1 km
GRID_DEG = 0.001                 # stored coordinates rounded to about 100 m

OUT = Path(__file__).resolve().parent.parent / "wherewhen" / "_china_region.py"


def build(shp: Path) -> str:
    countries = gpd.read_file(shp)
    inside = countries["ADM0_A3"].isin(INSIDE)
    land = unary_union(countries[inside].geometry.values)
    others = unary_union(countries[~inside].geometry.values)
    region = land.buffer(SEA_MARGIN_DEG).difference(others)
    region = set_precision(region.simplify(SIMPLIFY_DEG, preserve_topology=True), GRID_DEG)
    if not region.is_valid:
        raise SystemExit("the simplified region is not a valid geometry")
    return region.wkt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("shapefile", type=Path, help="ne_10m_admin_0_countries.shp")
    args = parser.parse_args()
    version_file = args.shapefile.with_suffix(".VERSION.txt")
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    wkt = build(args.shapefile)
    # Fixed-width slices, so joining the literals gives back the WKT exactly.
    body = "\n".join(f"    {wkt[i:i + 72]!r}" for i in range(0, len(wkt), 72))
    OUT.write_text(
        '"""\n'
        "Region where the GCJ-02 and BD-09 offsets apply: mainland China, Hong Kong\n"
        f"and Macau, with a {SEA_MARGIN_DEG}° sea margin that stops at other countries' land.\n"
        "\n"
        f"Built by scripts/build_china_region.py from Natural Earth {version} 1:10m\n"
        "Admin 0 – Countries (public domain), simplified to "
        f"{SIMPLIFY_DEG}° and rounded to {GRID_DEG}°.\n"
        "Do not edit by hand: re-run the script.\n"
        '"""\n'
        "\n"
        "# WGS-84 longitude/latitude, as WKT.\n"
        "CHINA_REGION_WKT = (\n"
        f"{body}\n"
        ")\n"
    )
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
