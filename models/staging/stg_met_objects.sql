select
    -- Birincil Anahtar
    safe_cast(object_id as int64) as object_id,

    -- Eser Tanımlayıcıları
    coalesce(nullif(trim(object_number), ''), 'Unknown') as object_number,
    coalesce(nullif(trim(title), ''), 'Untitled') as title,
    coalesce(nullif(trim(object_name), ''), 'Unknown') as object_name,
    coalesce(nullif(trim(department), ''), 'Unknown') as department,

    -- Sergi ve Kronoloji Bayrakları
    coalesce(safe_cast(is_highlight as bool), false) as is_highlight,
    coalesce(safe_cast(is_timeline_work as bool), false) as is_timeline_work,
    coalesce(safe_cast(is_public_domain as bool), false) as is_public_domain,
    case 
        when gallery_number is not null and trim(gallery_number) != '' then true 
        else false 
    end as is_on_view,
    coalesce(nullif(trim(gallery_number), ''), 'In Storage') as gallery_number,

    -- Tarih ve Dönem Bilgileri (Alt çizgi kaldırıldı)
    safe_cast(accessionyear as int64) as accession_year,
    coalesce(nullif(trim(object_date), ''), 'Date Unknown') as object_date,
    safe_cast(object_begin_date as int64) as object_begin_date,
    safe_cast(object_end_date as int64) as object_end_date,
    coalesce(nullif(trim(period), ''), 'Unknown') as period,
    coalesce(nullif(trim(culture), ''), 'Unknown') as culture,

    -- Sanatçı Bilgileri
    coalesce(nullif(trim(artist_display_name), ''), 'Anonymous / Unknown') as artist_display_name,
    coalesce(nullif(trim(artist_nationality), ''), 'Unknown') as artist_nationality,
    coalesce(nullif(trim(artist_gender), ''), 'Not Specified') as artist_gender,
    nullif(trim(artist_wikidata_url), '') as artist_wikidata_url,

    -- Fiziksel ve Sınıflandırma Nitelikleri
    coalesce(nullif(trim(medium), ''), 'Unknown') as medium,
    coalesce(nullif(trim(classification), ''), 'Unknown') as classification,
    coalesce(nullif(trim(country), ''), 'Unknown') as country,
    nullif(trim(dimensions), '') as dimensions,
    coalesce(trim(credit_line), 'Unknown') as credit_line,
    -- Hukuki ve Web Bağlantıları
    nullif(trim(rights_and_reproduction), '') as rights_and_reproduction,
    nullif(trim(link_resource), '') as link_resource

from `the-met-open-access.met_data.met_objects`
where object_id is not null