{{ config(
    materialized='table'
) }}

with staging as (
    select * from {{ ref('stg_met_objects') }}
)

select
    -- 1. IDENTIFIERS & METADATA
    object_id,
    object_number,
    title,
    object_name,
    department,

    -- 2. CURATORIAL & EXHIBITION FLAGS
    is_highlight,
    is_timeline_work,
    is_public_domain,
    is_on_view,
    gallery_number,

    -- 3. PROVENANCE & CHRONOLOGY
    accession_year,
    case 
        when accession_year is not null and accession_year >= 1870 
            then concat(cast(floor(accession_year / 10) * 10 as string), 's')
        else 'Unknown'
    end as accession_decade,
    
    object_date,
    object_begin_date,
    object_end_date,

    -- Official The Met Chronological Eras
    case
        when object_begin_date is null then 'Date Unknown'
        when object_begin_date < -8000 then 'Before 8000 B.C.'
        when object_begin_date between -8000 and -2001 then '8000–2000 B.C.'
        when object_begin_date between -2000 and -1001 then '2000–1000 B.C.'
        when object_begin_date between -1000 and 0 then '1000 B.C.–1 A.D.'
        when object_begin_date between 1 and 500 then '1–500 A.D.'
        when object_begin_date between 501 and 1000 then '500–1000 A.D.'
        when object_begin_date between 1001 and 1400 then '1000–1400 A.D.'
        when object_begin_date between 1401 and 1600 then '1400–1600 A.D.'
        when object_begin_date between 1601 and 1800 then '1600–1800 A.D.'
        when object_begin_date between 1801 and 1900 then '1800–1900 A.D.'
        when object_begin_date >= 1901 then '1900 A.D.–present'
        else 'Other'
    end as timeline_period,

    case
        when object_begin_date is null then 99
        when object_begin_date < -8000 then 1
        when object_begin_date between -8000 and -2001 then 2
        when object_begin_date between -2000 and -1001 then 3
        when object_begin_date between -1000 and 0 then 4
        when object_begin_date between 1 and 500 then 5
        when object_begin_date between 501 and 1000 then 6
        when object_begin_date between 1001 and 1400 then 7
        when object_begin_date between 1401 and 1600 then 8
        when object_begin_date between 1601 and 1800 then 9
        when object_begin_date between 1801 and 1900 then 10
        when object_begin_date >= 1901 then 11
        else 98
    end as timeline_period_order,

    period,
    culture,
    country,

    -- 4. ACQUISITION & DONOR INTELLIGENCE
    credit_line,

    case
        when lower(credit_line) like '%purchase%' or lower(credit_line) like '%fund%' 
            then 'Purchase'
        when lower(credit_line) like '%gift%' or lower(credit_line) like '%bequest%' 
            then 'Donation (Gift / Bequest)'
        else 'Other / Undisclosed'
    end as acquisition_category_broad,

    case
        when lower(credit_line) like '%purchase%' or lower(credit_line) like '%fund%' 
            then 'Purchase'
        when lower(credit_line) like '%gift%' and lower(credit_line) like '%bequest%' 
            then 'Gift & Bequest'
        when lower(credit_line) like '%gift%' 
            then 'Gift'
        when lower(credit_line) like '%bequest%' 
            then 'Bequest'
        else 'Other / Undisclosed'
    end as acquisition_type,

    case
        when lower(credit_line) like '%anonymous%' 
            then 'Anonymous Donor'
        when lower(credit_line) like '%gift of%' or lower(credit_line) like '%bequest of%'
            then trim(regexp_extract(credit_line, r'(?i)(?:gift of|bequest of)\s+([^,0-9()]+)'))
        else null
    end as primary_donor,

    -- 5. ARTIST DEMOGRAPHICS
    artist_display_name,
    artist_nationality,
    case
        when lower(artist_gender) like '%female%' and lower(artist_gender) like '%male%' 
            then 'Mixed / Collaborative'
        when lower(artist_gender) like '%female%' 
            then 'Female'
        when lower(artist_gender) like '%male%' 
            then 'Male'
        else 'Not Specified / Unknown'
    end as artist_gender_standardized,
    artist_wikidata_url,

    -- 6. OFFICIAL TAXONOMY (OBJECT TYPE / MATERIAL)
    case
        when coalesce(medium, 'Unknown') = 'Unknown' 
             and coalesce(classification, 'Unknown') = 'Unknown' 
            then 'Unknown'

        when lower(classification) like '%musical instrument%' 
             or lower(department) like '%musical instrument%'
             or lower(object_name) like '%instrument%'
             or lower(object_name) like '%violin%'
             or lower(object_name) like '%flute%'
            then 'Musical Instruments'

        when lower(classification) in ('arms and armor') 
             or lower(department) like '%arms and armor%'
             or lower(object_name) like '%sword%'
             or lower(object_name) like '%armor%'
             or lower(object_name) like '%dagger%'
            then 'Arms and Armor'

        when lower(classification) in ('costume', 'costumes') 
             or lower(department) like '%costume institute%'
             or lower(object_name) like '%dress%'
             or lower(object_name) like '%shoe%'
             or lower(object_name) like '%jacket%'
            then 'Costume'

        when lower(classification) in ('books', 'manuscripts', 'illuminated manuscripts')
             or lower(object_name) like '%book%'
             or lower(object_name) like '%manuscript%'
            then 'Books and Manuscripts'

        when lower(classification) like '%photograph%' 
             or lower(department) like '%photograph%'
             or lower(object_name) like '%photograph%'
            then 'Photographs'

        when lower(classification) like '%print%' 
             or lower(object_name) in ('print', 'woodcut', 'etching', 'engraving', 'lithograph')
            then 'Prints'

        when lower(classification) like '%drawing%' 
             or lower(object_name) in ('drawing', 'sketch', 'study')
             or lower(medium) like '%watercolor%'
             or lower(medium) like '%graphite%'
            then 'Drawings'

        when lower(classification) like '%painting%' 
             or lower(department) like '%paintings%'
             or lower(medium) like '%oil on%'
             or lower(medium) like '%tempera on%'
            then 'Paintings'

        when lower(classification) in ('woodwork', 'furniture') 
             or lower(object_name) like '%chair%'
             or lower(object_name) like '%table%'
             or lower(object_name) like '%cabinet%'
             or lower(medium) like '%wood%'
            then 'Woodwork'

        when lower(classification) like '%ceramic%' 
             or lower(medium) like '%clay%'
             or lower(medium) like '%porcelain%'
             or lower(medium) like '%terracotta%'
             or lower(medium) like '%pottery%'
            then 'Ceramics'

        when lower(classification) like '%textile%' 
             or lower(object_name) like '%tapestry%'
             or lower(object_name) like '%carpet%'
             or lower(medium) like '%silk%'
             or lower(medium) like '%wool%'
             or lower(medium) like '%cotton%'
            then 'Textiles'

        when lower(classification) in ('gold and silver', 'jewelry', 'coins', 'medals', 'gems')
             or lower(object_name) in ('coin', 'medal', 'necklace', 'ring', 'brooch')
             or ((lower(medium) like '%gold%' or lower(medium) like '%silver%')
                 and lower(medium) not like '%gold leaf%' 
                 and lower(medium) not like '%silver leaf%')
            then 'Gold and Silver'

        when lower(classification) like '%glass%' 
             or lower(medium) like '%glass%'
            then 'Glass'

        when lower(classification) in ('metalwork', 'metals') 
             or lower(medium) like '%bronze%'
             or lower(medium) like '%brass%'
             or lower(medium) like '%iron%'
             or lower(medium) like '%copper%'
            then 'Metalwork'

        when lower(classification) like '%sculpture%' 
             or lower(object_name) like '%sculpture%'
             or lower(object_name) like '%statue%'
             or lower(object_name) like '%bust%'
             or lower(object_name) like '%relief%'
            then 'Sculpture'

        else 'Other / Miscellaneous'
    end as object_type_material,

    classification,
    medium,
    dimensions,
    rights_and_reproduction,
    link_resource

from staging