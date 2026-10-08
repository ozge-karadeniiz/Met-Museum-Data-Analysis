select
    object_id
from {{ ref('stg_met_objects') }}
where object_id <= 0