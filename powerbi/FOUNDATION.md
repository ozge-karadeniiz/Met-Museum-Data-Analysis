# Met Collection dashboard foundation

Status: this original proposal is superseded by `MET Atlas/MET Atlas.pbip`. Source counts have been checked, model/report definitions created and validated, and the project opened in installed Power BI Desktop. See README.md for source baselines and separate refresh requirements.

## Visual direction

Reference: https://www.metmuseum.org/

Use an editorial, artwork-led layout with generous whitespace, serif page headings, readable sans-serif labels, warm white backgrounds, charcoal text and restrained red accents. The palette in met-inspired.theme.json is a proposed interpretation, not an official Met brand specification. Keep analytical charts on light backgrounds and reserve artwork images for detail views.

Import the theme in Power BI Desktop through View > Themes > Browse for themes.

## Proposed report pages

1. Collection overview: distinct artwork count, department count, known artist coverage, and public domain share if the source exposes those fields. Show department ranking and culture distribution. Add department and classification filters.
2. Collection explorer: searchable artwork table and culture, geography, medium and period filters where supported by the actual schema. Treat artwork start/end years as historical intervals, including BCE values, rather than acquisition dates.
3. Artwork detail: title, artist attribution, department, dating text, medium, dimensions and collection link. Show an image only when an available image URL and usage rights support it.

These are proposed analytical fields, not verified source columns. No visitor, attendance, revenue or exhibition measures should be inferred from a collection dataset.

## Source and model requirements

Before writing transformations or DAX, confirm the BigQuery project, dataset and source tables; inspect schema and table grain; check artwork key uniqueness, null rates, repeated fields and artist cardinality. Use one artwork row per stable artwork identifier only after the source confirms that grain.

Begin with an artwork table and only create dimensions when actual field structure warrants them. Multiple artists per artwork require a bridge rather than duplicated artwork facts. Preserve unknown values explicitly and do not infer country from culture. Define every KPI denominator and make measures respect report filters.

Choose Import versus DirectQuery after reviewing source size, freshness needs and access constraints. Configure billing project and credentials in Power BI; do not store credentials in report preparation files. Validate source totals against Power BI measures and test filters before considering the foundation complete.

## Completion blockers

- Source identification, model/report creation and initial Desktop opening are complete.
- The Codex browser runtime remains unavailable; this project uses the installed Desktop application.
- Live refresh succeeded and overview KPI cards matched BigQuery. A full filter-interaction audit remains separate from this foundation check.
