# Drought source inspection and API findings

Research date: **2026-11-12**. This is exploratory inspection, not a completed drought download or hazard model. Read with the [implementation plan](drought_download_implementation_plan.md) and [methods review](drought_hazard_methods_review.md).

## 1. What the professor's sample contains

The original [sample folder](../Hazard_Variables/Drought/2026_USDM_M/) contains **40 ZIP archives**, one per Tuesday from **2026-01-06 through 2026-10-06**, with no missing Tuesdays inside that interval. Their combined compressed size is **103,420,614 bytes**. Every ZIP passed its CRC check. Inspection read the archives without changing or extracting into the source folder; SHA-256 hashes are recorded in the [evidence manifest](drought_research_evidence.json).

The `_M` collection is a merged-class GIS product, not a monthly time series. The dated filenames and UNL's [shapefile metadata](https://droughtmonitor.unl.edu/DmData/Metadata.aspx) establish the distinction. The files are national multipart drought polygons, rather than Puerto Rico-only municipal observations. A record represents a drought class assembled from potentially many disconnected polygon parts.

All 40 DBFs have the same schema:

| Field | Observed storage | Interpretation for this project |
|---|---|---|
| OBJECTID | Numeric integer | File-local identifier, not a persistent geographic key. |
| DM | Numeric integer | Source drought category; retain the literal D0-D4 code. |
| Shape_Leng | Floating point | Supplied geometric attribute; do not assume current CRS units. |
| Shape_Area | Floating point | Supplied geometric attribute; recompute areas after projection. |

There is **no feature date field, municipio identifier, SPI/SPEI, rainfall, soil moisture, population, damage, or vulnerability attribute** in this schema. Add an audited `MAP_DATE` from the archive/member identity during preparation, and preserve the original file and metadata. A missing class in a file does not mean a missing download: some categories can genuinely be absent nationally.

All sample `.prj` files specify **WGS84 geographic coordinates**, and the SHP headers identify polygon geometry. UNL's general metadata describes an Albers product; embedded lineage in the sample also contains older projection/merge processing. Consequently, inspect each actual `.prj`/ArcPy spatial reference, preserve the discrepancy, and use **Project**, rather than assigning a different CRS with Define Projection. The January 2000 pilot ZIP also has WGS84 in its projection file. These observations do not certify every historical file's CRS.

The January 6 sample has five national features with DM values 0-4 and stored areas of order 10^9-10^12 despite its geographic CRS. Those fields are not usable as degree-squared Puerto Rico areas or as current area measurements.

### Island control checks

Read-only point-in-polygon tests found a DM polygon at the mainland-center control in 17 of 40 weeks, Vieques in 16, and Culebra in 21. There were no multiple-class matches at the eight tested controls. **Mona had no match in any sample week; Mayaguez's mainland control also had no match.** Neither absence establishes that a location was unassessed or drought-free. These are spot checks, not a complete topology or assessment-domain audit. Coordinates and per-week results are in the evidence files.

The sample is sufficient to design geometry/schema handling and an ingestion pilot. It is **not sufficient for a multi-year climatology**, and all its dates are outside the proposed 2000-2025 indicator cohort. It can still supply January 2026 recovery-buffer observations for later event analysis.

## 2. Public-source requests actually tested

Successful requests used HTTPS and required no API token. JSON statistics were requested with `Accept: application/json`. Results below describe observed service behavior, not a guarantee of future availability. Exact URLs, response sizes, retrieval times, hashes, and failed/successful attempts are in the [probe receipts](drought_research_evidence.json).

| Probe | Result |
|---|---|
| State area-percent, `aoi=72`, 1955-01-01 to 2000-01-31 | Only four records, beginning **2000-01-04**; no earlier PR history returned. |
| State cumulative area-percent, 2000-2025 | **1,357 unique dates**, 2000-01-04 to 2025-12-30. |
| State categorical area-percent, 2000-2025 | Same 1,357 dates. |
| State DSCI, 2000-2025 | Same 1,357 dates. |
| County categorical area-percent, `aoi=PR`, 2026-01-06 | **78 municipio rows**, with string FIPS such as `72001`. |
| Threshold service, January 2026, D2 | Empty array: this filtered response cannot establish the complete weekly calendar. |
| Threshold service, January 2026, D0 | Five rows, including the preceding 2025-12-30 map. |
| Official merged-shapefile directory | A matching weekly link for **all 1,357 baseline dates**. |
| Historical 2000-01-04 GIS ZIP | Downloaded, **615,840 bytes**, valid ZIP/CRC, with three class features. |

The index lists **1,533,215,548 compressed bytes** for those 1,357 individual weekly archives, approximately 1.53 GB before extraction or processing. This is a directory-listing calculation, not a completed bulk download. Annual bundles exist, but their complete contents were not fetched or certified in this round.

### Date and ordering behavior

For a query starting **January 1, 2026**, comprehensive statistics and DSCI included the **December 30, 2025** map, whose validity interval extends into January. Therefore, preserve `mapDate`, `validStart`, and `validEnd`, then apply our explicit **map-date cohort filter** after retrieval. Request boundaries alone do not define the analytical cohort. Comprehensive responses were descending by date; DSCI was ascending. Always sort explicitly and deduplicate by geography/date/format. No claim is made about all endpoint ordering.

The 2000-2025 responses matched an independently generated Tuesday calendar exactly: no missing or extra dates after cohort filtering. This verifies the **state statistics chronology**, not per-cell historical spatial coverage. The first week's statistics do not cover January 1-3, 2000; our indicator counts weekly map observations rather than reconstructing continuous daily conditions.

### Cumulative/categorical discrepancy worth preserving

Normally, exact-category percentages plus None sum to 100, and summing exact categories at/above a threshold reproduces cumulative percentages. Two live PR records exceeded a proposed **0.035 percentage-point rounding screen**:

| Map date | Sum of categorical None + D0 + ... + D4 | Largest disagreement with cumulative data |
|---|---:|---:|
| 2015-08-04 | 100.33% | 0.33 percentage points |
| 2015-08-11 | 100.32% | 0.32 percentage points |

Cumulative None + D0-D4 equaled 100 throughout the baseline; cumulative thresholds were monotonic throughout. DSCI differed from both the cumulative sum and the weighted categorical calculation by at most **0.5 index units**, consistent with its observed integer presentation. That agreement does **not** resolve the two categorical discrepancies.

Keep both raw formats. Use cumulative area-percent as the primary tabular threshold benchmark, and flag these two records as source disagreements requiring polygon/archival comparison. Do not renormalize them silently, delete these drought weeks, or label the disagreement as a demonstrated polygon error. Statistics are a reference check; future cell hazards come from weekly geometry.

### HTTP behavior

The historical ZIP request returned **406** with `Accept: application/zip` and succeeded with **`Accept: */*`**, returning `application/x-zip-compressed`. A downloader should use the tested browser-style header for archive requests and validate ZIP signatures/CRC instead of requiring one exact MIME spelling. The statistics API accepted a multi-year request in this test; the website download forms display a one-year limit. Annual chunking is our resumability choice, not a verified universal API restriction.

## 3. What remains unverified

- Integrity, per-date metadata, geometry and coverage of the remaining 1,356 baseline GIS ZIPs.
- Exact-category non-overlap across every historical feature, valid assessed land, and small-island coverage over time.
- Reasons for the two statistics discrepancies and whether an archival revision is involved.
- Complete annual-bundle contents, archive resumable-range support, and service rate limits.
- Production ArcGIS drought tools, temporal rasters, scientific validation, and final 1/3/5 thresholds.

Raw responses and exploratory inspection/probe scripts are in [the research evidence folder](../output/drought_research/). The existing Hurricane toolbox, code, outputs, and release ZIPs were not changed by this research.
