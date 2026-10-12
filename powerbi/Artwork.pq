let
    Source = GoogleBigQuery.Database([BillingProject="the-met-open-access", UseStorageApi=false]),
    Project = Source{[Name="the-met-open-access"]}[Data],
    Dataset = Project{[Name="met_data", Kind="Schema"]}[Data],
    Mart = Dataset{[Name="mart_met_objects", Kind="Table"]}[Data],
    Typed = Table.TransformColumnTypes(Mart, {{"object_id", Int64.Type}, {"object_number", type text}, {"title", type text}, {"object_name", type text}, {"department", type text}, {"is_highlight", type logical}, {"is_timeline_work", type logical}, {"is_public_domain", type logical}, {"is_on_view", type logical}, {"gallery_number", type text}, {"accession_year", Int64.Type}, {"accession_decade", type text}, {"object_date", type text}, {"object_begin_date", Int64.Type}, {"object_end_date", Int64.Type}, {"timeline_period", type text}, {"timeline_period_order", Int64.Type}, {"period", type text}, {"culture", type text}, {"country", type text}, {"credit_line", type text}, {"acquisition_category_broad", type text}, {"acquisition_type", type text}, {"primary_donor", type text}, {"artist_display_name", type text}, {"artist_nationality", type text}, {"artist_gender_standardized", type text}, {"artist_wikidata_url", type text}, {"object_type_material", type text}, {"classification", type text}, {"medium", type text}, {"dimensions", type text}, {"rights_and_reproduction", type text}, {"link_resource", type text}})
in
    Typed
