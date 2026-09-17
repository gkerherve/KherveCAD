earth_coast.json.gz - coastlines for the Earth globe (solar_earth.py)

Derived from Natural Earth (naturalearthdata.com), 1:50m cultural-free
physical vectors: ne_50m_land, ne_50m_lakes and ne_50m_glaciated_areas.
Natural Earth is in the public domain. Outer rings only, simplified with
Douglas-Peucker to 0.1 degrees, rings under 0.04 square degrees dropped,
coordinates [longitude, latitude] rounded to 0.001 degrees.

earth_elevation.bin.gz - land elevation for the Earth globe's relief

ETOPO 2022 (NOAA National Centers for Environmental Information, public
domain), the 15 arc-second ice-surface model resampled to 0.25 degrees
by the DEM_global_mosaic image service, ocean clamped to 0, stored as
little-endian int16 metres behind a 16-byte header (KCADELEV, width,
height as uint32). Built by khervecad/tools/earth_elevation.py.

<body>.kmap.gz - albedo classes (and, for the Moon and Mars, elevation)
for the mapped bodies (solar_raster.py), built by
khervecad/tools/planet_maps.py from public-domain mission data at 0.5
degrees: the Moon from NASA SVS's CGI Moon Kit (LRO LOLA 4 pixel/degree
DEM, LROC WAC colour); Mars from the MGS MOLA MEGDR 4 pixel/degree grid
(PDS Geosciences Node) and the Viking MDIM 2.1 colour mosaic; Mercury
(MESSENGER colour), Venus (Magellan radar), Io (Galileo SSI colour),
Europa, Ganymede, Callisto (Galileo / Voyager), Mimas, Enceladus, Tethys,
Dione, Rhea, Titan, Iapetus (Cassini / Voyager), Triton (Voyager 2),
Phobos, Deimos (Viking), Pluto and Charon (New Horizons) from the USGS
Astrogeology planetary map server. Each mosaic is reduced to a few
colour classes by k-means (greyscale ones tinted with the body's colour).
