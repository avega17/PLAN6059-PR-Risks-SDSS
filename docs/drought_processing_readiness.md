# Drought implementation results and processing readiness

Date: **2026-11-12**. The **Plan / Fetch / Validate acquisition workflow is
implemented**, including [Drought.atbx](../Drought.atbx), thin Script Tools and
the [drought.py](../drought.py) CLI. The [GUI assembly guide](drought_modelbuilder_setup.md)
documents the three-part ModelBuilder wiring; the current toolbox contains the
three Script Tools, not a saved Drought model graph.

## 1. What was acquired and tested

The complete acquisition run is in [output/drought_baseline/](../output/drought_baseline/).

| Product / check | Observed result |
|---|---:|
| Baseline map dates | **1,357**, 2000-01-04 through 2025-12-30 |
| End-recovery buffer dates | **3**, 2026-01-06, 01-13, 01-20 |
| Baseline year cohorts | **26**; buffers excluded |
| Baseline national GIS ZIP size | **1,533,215,548 bytes**, compressed |
| Normalized reference-statistic rows, including buffers | **654,160** |
| Reference products | State cumulative and categorical area %, DSCI, all 78 municipios' categorical area % |
| Acquisition validation | **125 checks passed**, with source warnings retained |
| Automated tests | **52 passed**, including 22 Drought tests and the existing ArcPy-enabled tests |
| Actual Script Tool pilot | All three tools passed for four January 2026 dates, with typed GDB tables |
| Code relocation | All three tools passed from a distribution folder with spaces; imports resolved there |
| Warm-cache proof | Complete archive/statistics acquisition repeated with **zero network requests** |

The raw archives, response bodies, metadata and hashes remain available; no
reference statistics were renormalized. Download validation reconstructs the
canonical CSV from frozen raw JSON, rather than checking only successful return
codes. It also checks published table counts and source preservation. The
download pass does not certify every historical polygon topology or land-domain
assumption.

Evidence: [download manifest](../output/drought_baseline/acquire/download_manifest.json),
[validation report](../output/drought_baseline/validate/download_validation.md),
[current-code validation](../output/drought_baseline/validate_current/download_validation.json),
[live Script Tool test](../output/drought_research/script_tool_test.json),
[relocation test](../output/drought_research/relocated_script_tool_test.json), and
[offline manifest](../output/drought_baseline_offline/acquire/download_manifest.json).

## 2. Findings that refine the next processing stage

### Historical records are not always one feature per class

**225 weekly archives** have multiple features for at least one DM value; these
occur in 2000-2012. One national file has **76 features**. This is a source-layout
finding, not proof of overlapping categories or corruption. Do not assume five
rows per file, interpret each feature as a separate drought event, or add
same-class geometries without resolving their spatial relationship.

**Preparation change:** after a bounded PR clip, preserve feature lineage, check
geometry and dissolve/union by **map date and DM**. Check cross-category overlaps
separately. A union within one class prevents duplicated same-class area from
inflating area summaries. Keep the original ZIP untouched.

### Culebra explains why API statistics need quality flags

The acquisition retained **231 warnings**:

- **225** multiple-DM-feature source-layout warnings.
- **4** categorical-total disagreements: the two previously observed PR records
  and two municipio records.
- **2** state cumulative-versus-categorical disagreements.

For **2015-08-04 and 2015-08-11**, Culebra (`72049`) reports both **None=100%** and
**D2=100%** in the categorical API response, totaling 200%. The spatial pilot
places the Culebra control inside a **D2** polygon on both dates. The state-level
categorical totals also disagree on these dates. These observations justify
flagging reference data, but do not establish the underlying provider error's
cause.

**Preparation change:** derive spatial category assignments from the polygons
and a documented assessment domain. Use API statistics as diagnostic benchmarks,
with these records explicitly flagged. Do not use a municipio's None percentage
as a spatial fill rule or silently delete these severe-drought observations.

### Mona is present in historical drought geometry

The 2026 sample alone had no DM matches at the Mona control. The fetched 2015
files explicitly place it in **D0**, confirming that Mona cannot be excluded
merely because recent dry-category polygons miss it. Raw `DM=0` means **D0**;
it must not be mistaken for the separate None state.

**Coverage change:** assess island/domain continuity across dates, rather than
assigning a blanket status from the 2026 sample or the union of drought polygons.
Some historical geometry includes Mona; a complete 26-year assessed-domain
ledger remains to be established.

### A valid no-drought week can have an empty PR clip

The 2000-01-04 source is structurally valid and its state statistics report 100%
None. Its PR dry-category clip contains **zero features**. This is not a missing
ZIP. Conversely, an empty clip alone cannot certify an island's assessment
coverage.

**Encoding change:** only inside a verified assessed-land domain, and for a valid
acquired week, convert land outside all D0-D4 polygons to **None=0**. Keep unknown
coverage and ocean as NoData. Otherwise normal weeks would incorrectly disappear
from the denominator and break duration calculations.

## 3. ArcPy rasterization feasibility experiment

The [readiness audit](../output/drought_readiness/readiness_audit.json) and its
[reusable audit script](../tools/audit_drought_readiness.py) examine six weeks:

- 2000-01-04: early digitized/no-drought case.
- 2015-08-04 and 2015-08-11: known reference-statistic anomalies.
- 2012-10-16: the 76-feature national source-layout case.
- 2026-01-06 and 2026-08-04: professor-sample pilots.

Each was clipped, projected with the recorded **WGS_1984_(ITRF00)_To_NAD_1983**
transformation, checked for geometry problems and cross-category overlap, and
rasterized by CELL_CENTER onto the existing **EPSG:32161, 250 m, 1,140 x 267**
reference grid. These six projected PR samples had **zero reported geometry
issues and zero measured cross-category overlap**. Raster dimensions, cell size
and exterior NoData checks passed; source ZIP checksums were unchanged.

Diagnostic rasters use **D0=1, D1=2, D2=3, D3=4, D4=5**. Land without a source
dry-category polygon is deliberately **unresolved/NoData** in these diagnostics;
the experiment does not implement the final assessed-domain/None fill. Their
numbers encode drought categories; course hazard ranks are a separate later
transformation. They are not usable as complete weekly input states for a final
frequency surface.

## 4. Readiness decisions

| Next action | Assessment | Required work |
|---|---|---|
| Controlled weekly-raster prototype | **Ready**; actual six-week feasibility passed | Make source/domain normalization explicit and retain diagnostic coverage. |
| Full weekly-state raster series | **Ready to implement, not yet complete** | Verify assessed-domain/island continuity; union same-class pieces; run per-date PR topology checks; fill valid None separately from unknown. |
| Frequency and duration over all 26 years | **Method specified, input series not ready for production** | Complete weekly-state series and valid-count ledger; test temporal state transitions and censoring. |
| Final Low/Medium/High hazard ranks | **Not ready to calculate final classes** | Evaluate continuous indicators, sensitivities and observed-event comparisons, then freeze numeric breakpoints. |
| Risk/loss estimation beyond the course hazard index | **Additional study needed** | Sector-specific exposure and vulnerability, not supplied by the USDM polygons. |

Use a common byte encoding for the eventual complete states:
**None=0, D0=1, D1=2, D2=3, D3=4, D4=5, unknown=255**. Every threshold predicate
must require validity and the upper bound `<=5`, so the unknown sentinel cannot
be counted as an extreme drought. A valid zero remains in the denominator.

For complete coverage, estimate primary D1-or-worse occupancy as
`N_D1 / 1357` and average annual weeks as `N_D1 / 26`. These are equivalent
summaries on the complete cohort; do not double-weight both. Compare D2
occupancy, persistence and the strict versus three-week-recovery event rules.
Keep buffers out of occupancy denominators and retain censored-event flags.

## 5. Three tools versus three scientific phases

The implemented **three-part acquisition model** is:

**Plan Drought Download -> Fetch Drought Data -> Validate Drought Download.**

For the complete SDSS drought branch, organize the later work into three broader
phases:

1. **Acquire and audit:** the three tools above.
2. **Prepare weekly states and estimate historical hazard:** rasterization,
   frequency/occupancy, event duration, peak class, coverage and uncertainty.
3. **Evaluate and classify the hazard indicator:** select/freeze the 1/3/5
   crosswalk, test an alternative, and integrate aligned ranked layers into the
   course screening index.

Thus frequency/duration calculation is already **hazard estimation**. A separate
physical wind-field-style drought reconstruction is not needed to interpret
USDM's published weekly classes. The third phase supplies justified ranking and
index integration; adding exposure/vulnerability for quantified risk would be
an additional, explicitly scoped model.

The [methods review](drought_hazard_methods_review.md) supplies literature,
indicator formulas, classification candidates and validation limitations. The
[download implementation plan](drought_download_implementation_plan.md) retains
the original design rationale.
