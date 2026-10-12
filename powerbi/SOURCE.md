# Verified BigQuery source

2026-10-09: BigQuery CLI table metadata request succeeded for:

- Project: `the-met-open-access`
- Dataset: `met_data`
- Table: `mart_met_objects`
- Location: `EU`
- Metadata row count: 484,956
- Columns: 34

Use the existing mart as the initial source. In Power BI's Google BigQuery connector, select this project/dataset/table using the user's authorized account. Start with Import for this bounded source if refresh requirements permit. Name the imported table `Artwork` to use measures.dax. Power BI authentication, import and refresh have not been tested.

Validated schema includes object_id, department, culture, classification, is_highlight, is_public_domain, is_on_view, accession_year, object_begin_date, object_end_date, timeline_period, timeline_period_order, artist_display_name, medium, title, dimensions and link_resource. There is no image URL field in this mart.

Schema validation is not row-level data quality validation: key uniqueness and metric totals still need queries before report sign-off. `is_on_view` represents gallery metadata in the current model; label it Gallery Information. Preserve BCE years as integers. Sort timeline_period by timeline_period_order after verifying a unique sort mapping. Artist attribution strings may contain multiple artists; do not use their distinct count as artist count.

The previous FOUNDATION.md source-identification blocker is resolved by this metadata check. Live Power BI authoring remains blocked by the Codex browser runtime failure.
