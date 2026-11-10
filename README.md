# Q-LandslideDam

A QGIS plugin for modeling **landslide dams** and river channel obstructions using wedge geometries, with automatic calculation of the **upstream dammed lake**.

Given a DEM, a point where the landslide reaches the river channel and a few geometric parameters, the plugin builds a wedge-shaped dam, burns it into the DEM until the target landslide volume is reached, and then fills the upstream lake up to its spillway level with GRASS `r.lake`.

## Features

- Wedge-shaped dam (four-sided pyramid) grown iteratively until the target volume is reached
- Modified DEM including the dam, displayed with hillshade
- Wedge thickness raster (the dam body alone), with a pseudocolor style from 0 to the maximum thickness
- Automatic upstream dammed lake: spillway level, volume, area and maximum depth, computed with GRASS `r.lake` (with an internal NumPy fallback when GRASS is not available)
- Optional detail layers: landslide point, lake control points (upstream seed, downstream point, overflow point) and a per-run results table
- Interface in English and Italian

## Requirements

- QGIS 3.22 or later
- A DEM in a **projected CRS in metres** (e.g. UTM). Geographic coordinates and Pseudo-Mercator (EPSG:3857) are not allowed
- Optional: the GRASS provider enabled in Processing, to compute the lake with `r.lake`

## Installation

**From the QGIS plugin repository:** in QGIS open *Plugins → Manage and Install Plugins*, search for **Q-LandslideDam** and click *Install*.

**From ZIP:** download `q_landslide_dam-<version>.zip` from the [Releases](https://github.com/pierluigiderosa/Q-LandslideDam/releases) page and install it from *Plugins → Manage and Install Plugins → Install from ZIP*.

## Usage

1. **DEM raster**: select the DEM.
2. **Landslide point**: press *Capture Coordinates* and click on the map where the landslide reaches the river channel, or type the X and Y coordinates.
3. **Landslide parameters**:
   - *Landslide direction*: direction of landslide movement, in degrees clockwise from North (0–359°). The dam crest axis lies along it;
   - *Face slope (upstream/downstream)*: slope of the upstream and downstream faces (typically 25–40°);
   - *Crest slope (along axis)*: slope of the crest from the selected point towards both valley sides; 0° = horizontal crest (typically 0–10°);
   - *Volume*: volume of the landslide deposit (m³).
4. **Settings** (optional): vertical step (default 0.2 m), maximum iterations (default 3000) and maximum radius of the dam (default 400 m).
5. **Output**: check *Save raster permanently* to choose where to save the modified DEM (otherwise a temporary folder is used). Check *Load detailed results table and lake control points* to also load the detail layers.
6. Press **OK**.

Detailed instructions are also available in the *Instructions* tab of the plugin dialog.

### Landslide direction

Enter the direction in which the landslide **moves**, measured clockwise from North (0° = towards North, 90° = towards East, ...). For example, with a river flowing West → East and a landslide coming from the southern slope, the direction is 0°.

| River flows | Landslide source slope | Landslide direction |
|-------------|------------------------|---------------------|
| East–West   | southern               | 0°                  |
| East–West   | northern               | 180°                |
| North–South | western                | 90°                 |
| North–South | eastern                | 270°                |

North is the grid North of the DEM CRS (the +Y axis of the map). Since the model is symmetric, directions θ and θ+180° produce the same deposit.

## Method

**Dam geometry.** The dam is a four-sided pyramid with its apex at the selected point:

```
z = (z0 + h) − |d_axis| · tan(crest slope) − |d_river| · tan(face slope)
```

where `z0` is the DEM elevation at the selected point, `h` the dam height, `d_axis` the distance along the crest axis and `d_river` the distance across it. The height `h` is raised by the vertical step until the volume between the dam surface and the terrain reaches the target volume. The dam is clipped by the terrain and by the maximum radius.

**Dammed lake.**
1. An upstream seed point and a downstream point are found where the river channel crosses a ring around the dam.
2. The spillway level is found by bisection as the highest water level that does not overflow downstream.
3. The lake is filled from the seed with GRASS `r.lake` (or in NumPy as a fallback); volume, area and maximum depth are computed from the resulting depth raster.

If the lake reaches the DEM edge it may be truncated: in that case use a larger DEM.

## Outputs

| Layer | Description |
|-------|-------------|
| Dam DEM | Modified DEM including the dam, with hillshade |
| Wedge thickness | Deposit thickness in metres (NoData outside the dam) |
| Lake | Water depth raster of the dammed lake |
| Landslide point *(detail)* | The selected point with the wedge parameters and results |
| Lake - control points *(detail)* | Upstream seed, downstream point and overflow point |
| Q-LandslideDam results *(detail)* | Table with all inputs, settings and results of the run |

The results table has the columns `section` (Run, Input, Settings, Dam, Lake), `parameter`, `value`, `unit` and `text`. It is a temporary layer: use *Make Permanent* to keep it.

## Credits

Developed by **Pierluigi De Rosa** (University of Perugia) as part of the project *“LANDAM – LANdslide DAMs: Characterization, Prediction, and Emergency Management.”* This project is included in the activities of the RETURN (multi-Risk sciEnce for resilienT commUnities undeR a changiNg climate) - Spoke 2 “Ground Instabilities”, funded by the European Union – NextGenerationEU - PNRR, Mission 4, Component 2, Investment 1.3; D.D. 1243 of August 2, 2022, PE0000005.

Built with [QGIS](https://qgis.org) and PyQGIS, [GRASS GIS r.lake](https://grass.osgeo.org/grass-stable/manuals/r.lake.html), NumPy and GDAL.

## Bug reports

Please report bugs and feature requests on the [issue tracker](https://github.com/pierluigiderosa/Q-LandslideDam/issues).

## License

This program is free software, released under the terms of the [GNU General Public License version 2](LICENSE) or later.
