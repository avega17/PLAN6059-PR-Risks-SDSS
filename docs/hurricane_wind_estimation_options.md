# Hurricane wind spatial estimation: options and validation gate

This is the design note for the **next** implementation round. The current prototype prepares and audits IBTrACS observations, establishes the Puerto Rico/Vieques/Culebra/Mona reference grid, and validates those products. It does not reconstruct wind fields, count exceedances, assign a hazard rank, or calculate a risk index.

## Quantity to estimate

The proposed physical quantity is each storm's maximum **10 m, 1-minute sustained wind speed** at each reference-grid cell. Keep the event identifier and a coverage mask alongside those maxima. A hurricane's reported maximum wind is the strongest wind within its circulation; it is not the wind at every location near its track. NOAA discusses measurement height, exposure, averaging periods, and the approximately 0.1-degree source resolution on printed page 5 of the [IBTrACS technical guide](https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf). The grid's 250 m cell size is an integration convention, not evidence of 250 m meteorological accuracy.

Use **64 kt** as the primary future hurricane-force exceedance threshold and **34 kt** as a separately labeled tropical-storm-force sensitivity scenario. The proposed historical statistic is the number of distinct storms exceeding the threshold in each cell, divided by the **71 seasons from 1955 through 2025**. Its unit is events per year. It is not the probability of at least one exceedance in a year: multiple storms can occur in a year. That probability requires distinct affected-year counts and a declared treatment of incompletely observed years. No such statistic or **1/3/5 reclassification** is implemented here.

## Candidate methods

| Candidate | Appropriate role | Main limitation to resolve |
| --- | --- | --- |
| HURRECON | First candidate for a transparent historical reconstruction and sensitivity study | Choose and justify radius of maximum wind and profile parameters; reconcile its geographic raster conventions with our projected grid. |
| CLIMADA | Independent implementation and model-choice comparison | Separate environment; make provider, imputation, distance, cutoff, and wind-model settings explicit. |
| Recorded IBTrACS quadrant radii | Compare modeled 34/50/64 kt footprints where observations exist | Coverage varies through history; missing radii cannot mean zero exposure. |
| Tropycal track proximity | Exploratory storm selection and independent track-statistics checks | Proximity is not a wind-field reconstruction. |
| `tcwind` | Small experimental Holland-model reference | Scientific normalization, missing-data behavior, and illustrative imputations require review. |

### HURRECON: first candidate, not a selected final model

HURRECON accepts track location and maximum wind, plus radius/profile parameters and a land-water representation. Its regional workflow produces peak-wind GeoTIFF products and distinguishes land/water friction; it does not require central pressure. Parameter defaults still express scientific assumptions. Its normal regional raster coordinates are latitude/longitude, so a future adapter must retain the reference grid's cell identity and document any reprojection/resampling. See the author's [Python workflow and input definitions](https://github.com/hurrecon-model/HurreconPython).

The [Harvard Forest HF446 archive](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF446) provides version 1.1 source released in 2024 and a traceable research history. This supplies a documented comparison basis, but it does not establish that the published parameter choices fit Puerto Rico. Treat alternative radius/profile values as labeled project sensitivity scenarios, not universally valid defaults. Preserve the distinction between sustained wind, gust speed, and modeled damage: these are separate outputs, and only the first matches the proposed target.

### CLIMADA: comparison with explicit controls

CLIMADA's `TropCyclone.from_tracks` models event-maximum 1-minute 10 m wind at centroids in m/s. The documented default is **H08**, with H1980, H10, and ER11 alternatives. Defaults include a **17.5 m/s storage threshold**, **300 km eye-distance cutoff**, and equirectangular distance metric; these must appear in benchmark manifests rather than remain hidden. H10 also exposes a pressure-derived maximum-wind option. See the [CLIMADA tropical-cyclone API](https://climada-python.readthedocs.io/en/stable/api/climada/climada.hazard.trop_cyclone.html).

Do not infer complete input coverage from a successful run. The [windfield source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/trop_cyclone/trop_cyclone_windfields.html) estimates missing RMW during conversion and contains NaN-to-zero handling. An adapter must carry an external validity mask and imputation flags. The [track importer source](https://climada-python.readthedocs.io/en/stable/_modules/climada/hazard/tc_tracks.html) also has provider selection and interpolation policies: choose USA explicitly or construct validated track objects from our canonical data; do not silently replace them with the importer's provider hierarchy.

The documentation inspected was **CLIMADA 6.1.0**. Its [installation guide](https://climada-python.readthedocs.io/en/stable/getting-started/install.html) supports Python 3.11 and allows 3.10-3.12, with substantial Conda dependencies. The local ArcGIS Pro 3.7 environment uses Python 3.13.13. A future CLIMADA benchmark belongs in a separate pinned Python 3.11 environment, exchanging CSV/JSON and grid coordinates with ArcPy. No compatibility installation or benchmark was performed in this prototype.

### Recorded radii and Tropycal

Where available, the four USA quadrant radii describe the recorded maximum reach of the **34, 50, and 64 kt** wind thresholds in nautical miles. They are a useful footprint comparison and coverage audit, not complete continuous wind fields. No observed radius is invented where absent; avoid interpolating across unsupported time spans or treating blank/zero radii as universal evidence of no wind. Definitions are on printed page 4 of the [IBTrACS column guide](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf).

Tropycal can find analog tracks near points/shapes and calculate track statistics. Its [TrackDataset API](https://tropycal.github.io/tropycal/api/generated/tropycal.tracks.TrackDataset.html) defaults to online HURDAT2, excludes recent best-track additions unless requested, and has separate IBTrACS provider modes. Pin the data snapshot and provider rather than accepting defaults. Its [data-source discussion](https://tropycal.github.io/tropycal/data.html) explains agency differences. Hourly interpolated point proximity can miss a fast crossing between samples; continuous segment-distance checks are more suitable for selection. Neither approach establishes local hurricane-force wind. Tropycal is not a prototype dependency, and its compatibility with the local Pro environment has not been tested.

### `tcwind`: findings from static source inspection

The inspected revision is [`d3a379ce880297ee36e53be3fd741981501a30e2`](https://github.com/zhang-962464/tcwind/tree/d3a379ce880297ee36e53be3fd741981501a30e2), the initial June 8, 2026 commit. The repository had no tags or releases at inspection. Its [manifest](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/pyproject.toml) declares version 0.1.0, Python >=3.9, NumPy >=1.20, and optional netCDF4. This is a dependency description, not a successful ArcGIS compatibility test.

The [ingestion module](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/data/ibtracs.py) reads CSV using combined `LAT/LON` with USA wind, pressure, and RMW. It does not enforce our USA-coordinate/provenance policy or read the local shapefiles directly. Its interpolation can extend observed RMW to endpoints; its RMW gap-filler explicitly uses illustrative western North Pacific coefficients. Those choices need flags and basin-specific review.

Static deductions from the [physics implementation](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/physics/holland.py), **not executed or observed failures**:

- Missing pressure or RMW can become zero radial wind through `nan_to_num`; with finite positions and Vmax, an unresolved input can therefore appear calm.
- B derives from input Vmax, and the final field receives a 0.9 surface factor. In the stationary, equatorial, unclipped-B case, 50 m/s input yields a 45 m/s modeled peak. The treatment of an already surface-based USA_WIND needs normalization review.
- The translation correction has zero weight for exactly opposing flow, so its stated opposite-side reduction is not guaranteed by the implementation.
- The optional intensity/latitude B formula is explicitly illustrative, and the engine does not apply land friction or terrain effects.

The [core API](https://github.com/zhang-962464/tcwind/blob/d3a379ce880297ee36e53be3fd741981501a30e2/tcwind/core.py) could evaluate existing cell-center coordinates through `at_points`, avoiding a second grid and large time cubes. Its default environmental pressure is 1013 mb. The four [test modules](https://github.com/zhang-962464/tcwind/tree/d3a379ce880297ee36e53be3fd741981501a30e2/tests) contain useful synthetic checks; they do not establish Puerto Rico observational skill. No remote package code was executed during this review.

## Required benchmark before selecting an engine

1. **Freeze inputs and interpretation.** Reuse the audited USA-coordinate series and fixed 250 m grid. Declare supported storm statuses, time intervals, imputation limits, physical wind definition, boundary and sea/land treatment. Retain complete selected tracks for interpolation; select candidate storms conservatively rather than clipping track points at the island boundary.
2. **Verify numerical invariants.** Test knots/m/s and nautical-mile/km conversion, cardinal directions and hemisphere rotation, calm-eye/profile behavior, preservation of an intended maximum, time ordering, zero/negative pressure deficit, missing critical inputs, and coverage masks. An unresolved input must never become an observed zero.
3. **Compare temporal/spatial convergence.** On representative storms, refine time steps until event maxima and affected area stabilize against a recorded tolerance. Compare use of existing cell centers with any reprojected output. Set and record the final tolerance before accepting a production run.
4. **Benchmark known Puerto Rico events.** Include a modern well-observed crossing event such as Maria (2017), a different track/intensity such as Georges (1998), and an older event with sparse radius/pressure data. Compare HURRECON and CLIMADA with identical data and units. Inspect point time series and footprint maps before computing historical aggregates.
5. **Separate calibration from validation.** Compare available station observations and documented wind analyses with correct height, exposure, sustained/gust definitions, and instrument limitations. NHC/IBTrACS values reused as model inputs are a consistency check, not independent validation. Hold out observations/events where feasible; report bias, absolute error, coverage, and affected-area differences.
6. **Report sensitivity and coverage.** Vary radius/profile assumptions, supported imputation rules, land treatment, time step, and 64/34 kt thresholds. Report valid-event/year denominators by cell. Present uncertainty and unsupported periods beside any final class map.

The engine selection gate requires documented input coverage, numerical tests, converged event maxima, intelligible benchmark differences, and an agreed classification method. Until these pass, no production exceedance raster or class ranking should be generated. The final class method must also match the class-wide project agreement.

## Reproducibility and code reuse

Keep research engines outside the core prototype. Pin release/commit, Python and dependency versions, model settings, input checksums, grid specification, and validation evidence for every future benchmark. Any external download must retain its URL, retrieval date, version, and license.

HURRECON and CLIMADA carry [GPL-3.0 licenses](https://github.com/hurrecon-model/HurreconPython/blob/master/LICENSE) ([CLIMADA license](https://github.com/CLIMADA-project/climada_python/blob/main/LICENSE)); [Tropycal](https://github.com/tropycal/tropycal/blob/master/LICENSE) and [`tcwind`](https://github.com/zhang-962464/tcwind/blob/main/LICENSE) use MIT. Record these before importing, adapting, or distributing code; preserve notices and license texts and make any copied/adapted code identifiable. A literature citation alone does not replace software-license obligations. This prototype vendors none of these engines and makes no claim that their defaults are validated for Puerto Rico.
