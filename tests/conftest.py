"""
Shared fixtures and constants for the wherewhen test suite.
"""
from __future__ import annotations

from shapely.geometry import Point

# London, Trafalgar Square — Europe/London
LONDON_LON, LONDON_LAT = -0.1278, 51.5074
LONDON_PT = Point(LONDON_LON, LONDON_LAT)

# Disneyland Paris — Europe/Paris
DISNEY_LON, DISNEY_LAT = 2.7836, 48.8674
DISNEY_PT = Point(DISNEY_LON, DISNEY_LAT)

# Nairobi — Africa/Nairobi, UTC+3
NAIROBI_LON, NAIROBI_LAT = 36.8219, -1.2921
NAIROBI_PT = Point(NAIROBI_LON, NAIROBI_LAT)

# Beijing — Asia/Shanghai (GCJ-02 / BD-09)
BEIJING_LON, BEIJING_LAT = 116.3912, 39.9073
BEIJING_PT = Point(BEIJING_LON, BEIJING_LAT)

# Moscow — Europe/Moscow (SK-42)
MOSCOW_LON, MOSCOW_LAT = 37.6173, 55.7558
MOSCOW_PT = Point(MOSCOW_LON, MOSCOW_LAT)