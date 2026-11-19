# Boose (2004): method notes for the PR hazard project

Reviewed 19 November 2026. This is the requested reading note supporting the [hurricane classification report](../docs/hurricane_classification_report.md), not a new hazard result.

**Citation:** Boose, E. R., Serrano, M. I., & Foster, D. R. (2004). Landscape and regional impacts of hurricanes in Puerto Rico. *Ecological Monographs, 74*(2), 335?352. [DOI](https://doi.org/10.1890/02-4057). The local reading copy is `Boose_2004_ LANDSCAPE AND REGIONAL IMPACTS OF HURRICANES IN PUERTO RICO.pdf` in this directory. Its bytes were preserved when relocated from the repository root; it remains ignored and is not included in the code distribution. Public links remain usable without that local copy.

## What the study actually mapped

| Product | Period/support | Location in paper |
|---|---|---|
| Historical damage reports for 85 selected storms | 1508?1997; incomplete, uneven historical evidence | pp. 337?338 |
| Municipality maps of reported damage | 0.5 km display grid; maximum reported damage by municipality, not independent observations in every cell | p. 339; Fig. 4, p. 343 |
| HURRECON reconstructions for 43 storms | 1851?1997; 3 km regional calculations | pp. 339?340; Fig. 3, p. 341 |
| Regional damage frequency/mean recurrence | Storm counts at minimum damage levels; frequency maps divided manually into 3?4 regions | p. 340; Fig. 7, p. 347 |
| Luquillo terrain exposure | Separate EXPOS analysis using 30 m elevation and reconstructed peak wind directions | p. 340; Fig. 10, p. 349 |

These are useful precedents for aligned hazard maps. They are not a demonstration of 250 m predictive accuracy. Our output can use the class's 250 m grid while retaining coarser model/information support. Current code evaluates the parametric model at 250 m cell centers directly; any future coarse-grid calculation followed by resampling must be identified separately.

## Damage scale and wind statistic

Table 1 (p. 338) modifies the original **Fujita F scale** for Puerto Rico. It includes trees, crops, houses of different construction, utilities and other structures. It is not exclusively a forest scale, but neither is it a calibrated loss model for current residents/buildings.

| Minimum damage level | Reported sustained-wind range, m/s | Interpretation examples |
|---|---:|---|
| F0 | 18?25 | Leaves/branches damaged; minor damage to some structures |
| F1 | 26?35 | Tree blowdown; roofs/windows can be damaged |
| F2 | 36?47 | Extensive blowdown and substantial structural damage |
| F3 | 48?62 | Most trees down; severe structural destruction |

The table's wind ranges are derived from Fujita equations with a land gust factor of 1.5. The original HURRECON damage method also uses fastest-quarter-mile wind (pp. 339?340; [HF025](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF025)). Rounded table ranges are not sufficient to reproduce continuous category boundaries faithfully. A direct sustained-wind crosswalk would be a separately labeled project proxy until the original conversion and thresholds are verified.

The updated R/Python package instead advertises **enhanced Fujita EF** damage ([HF446](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF446)). Do not relabel EF as the paper's F or mix their recurrence statistics. HF012 town data use -1 for reported no damage, 0 for F0 and 1?3 for F1?F3; an absent town/report is not demonstrated no damage. Current project code calculates sustained peak winds, not F/EF damage, gust damage or EXPOS sheltering.

## What the quoted return intervals mean

The results on p. 342 describe **F0 or higher (~4 years), F1 or higher (~6), F2 or higher (~15?33) and F3 (~50?150)**. Thus these quantities overlap cumulatively; they must not be added as independent risk components. The values vary by location and are outcomes of the reconstructed record, not published Low/Medium/High bin boundaries.

The authors calculated regional average return times from average storm counts and the observation period (p. 340). Distinguish this event-based interval from the reciprocal of a probability of at least one exceedance in a year: several storms can affect one year. The Luquillo >150-year category means no modeled F3 exposure in that study window, not proof of permanent protection or a calibrated extreme-tail return level. Figure 10 reflects local terrain and selected storm directions; it cannot supply a PR-wide 250 m terrain correction.

The finding of no clear centennial trend in major damage is qualified by reporting completeness and a record ending in 1997. It does not establish a forecast for 2026 or demonstrate stationarity under present/future climate conditions.

## Calibration differences we must preserve

The authors compared four radius/profile pairs and selected a best fit for each storm. They also adjusted HURDAT intensities for 13 storms, moved Betsy's track by 25 km and imposed overland weakening on 15 landfalling storms (p. 340). These changes helped match historical damage. We should not apply them to modern USA-family IBTrACS values automatically: their revisions or land effects may already be represented. Evaluations using fitted storm damage require disclosure of calibration dependence.

The four-storm project benchmark is therefore an equation-based sensitivity experiment, not a reproduction of the full study. Next work should preserve separate evidence for wind modeling, damage conversion, historical completeness and classification. The source archive [HF012](https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=hf012) can support historical comparisons; municipality maxima are credible regional references, not cell-level ground truth. Missing reports remain unknown.
