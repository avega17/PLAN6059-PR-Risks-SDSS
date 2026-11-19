# Course project working rules

Keep this repository understandable to classmates using ArcGIS ModelBuilder.

- Reuse the two root entrypoints, thin Script Tool adapters and existing hazard packages. Keep runtime data validation in the workflows.
- Maintain the five guides in `docs/` and the two explicitly requested hazard-classification reports; consolidate other findings into their processing plans. Put PNG figures in `figures/` and source documents in `references/`. Do not add further reports without a request.
- Use one canonical result per hazard: `output/hurricane/{data,reports}` and `output/drought/{plan,data,reports,cache}`. The common grid is `output/shared/grid`; project and MCP runtime files belong in `output/arcgis/{project,bridge}`.
- Preserve original inputs, downloaded bodies, hashes and original receipts. Relocate caches through verified content-addressed resolution. Never invent acquisition dates or reinterpret missing data as zero.
- Use temporary directories for staging, probes and relocation checks; clean them on success and failure. Do not retain copied distributions, pilot outputs, investigation scripts or historical evidence directories.
- Do not create unsolicited evidence JSON, verification Markdown, screenshots, test runners or extra reports. Report routine checks in the conversation or commit message. One operational validation JSON per hazard is sufficient.
- Publish normalized tables once. Additional CSV is opt-in with geodatabase publication; CSV remains primary for ordinary Python.
- Keep `tests/test_contracts.py` small and offline. Add tests or dependencies only for a concrete regression risk or implementation need; no new harnesses by default.
- Keep four maintenance files in `tools/`. Package using an explicit allowlist into one current `dist/PR_Risks_SDSS.zip`, excluding datasets/caches.
- Preserve toolbox filenames, aliases and internal model names. Change adapters, Script Tool contracts and GUI-authored graphs together. Preserve durable internal outputs: keep Script Tool outputs Derived (exempt from intermediate deletion); for eligible non-derived outputs, uncheck Intermediate Data. Verify survival after saved-model execution.
- Prefer the ArcGIS GUI for saved graph edits. Programmatic repair is allowed when the user explicitly authorizes it; preserve logical and diagram bindings, inspect imports/parameters, and execute the actual saved model before delivery. For floating dialogs, provide exact values and hand off when automation is unreliable; do not repeatedly hunt coordinates.
- Before replacing toolboxes, close ModelBuilder tabs, save the project on its map, and close Pro. Preserve native ZIP member metadata and GUI-generated diagram geometry during repairs; verify the project and model both reopen afterward.
- Keep hazard estimation and classification behind the processing plans' evaluation gates. The 250 m grid does not establish 250 m observation accuracy.
- The people-focused index covers mainland Puerto Rico, Vieques and Culebra. Mona is outside its scope; retain sparse observations and unknown/NoData states as an expected edge case, not a notable project limitation or classification blocker.

- Keep the requested Boose reading note in `references/boose_2004_method_notes.md`. Embed workflow Mermaid diagrams in the two setup guides; do not add standalone diagram copies or further research notes without a request.
