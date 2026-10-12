SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT object_id) AS artwork_count,
  COUNTIF(object_id IS NULL) AS null_object_ids,
  COUNT(DISTINCT department) AS department_count,
  COUNT(DISTINCT IF(is_highlight, object_id, NULL)) AS highlight_count,
  COUNT(DISTINCT IF(is_public_domain, object_id, NULL)) AS public_domain_count,
  COUNT(DISTINCT IF(is_on_view, object_id, NULL)) AS gallery_information_count,
  COUNT(DISTINCT IF(object_begin_date > object_end_date, object_id, NULL)) AS reversed_date_count,
  COUNT(DISTINCT IF(object_begin_date = 0 OR object_end_date = 0, object_id, NULL)) AS zero_year_count,
  COUNT(DISTINCT IF(accession_year IS NULL, object_id, NULL)) AS missing_accession_year_count,
  (SELECT COUNT(*) FROM (
    SELECT timeline_period FROM `the-met-open-access.met_data.mart_met_objects`
    GROUP BY timeline_period HAVING COUNT(DISTINCT timeline_period_order) > 1
  )) AS ambiguous_period_sort_count
FROM `the-met-open-access.met_data.mart_met_objects`
