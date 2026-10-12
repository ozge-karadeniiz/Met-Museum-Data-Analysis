# MET Atlas — Power BI Desktop

Open `MET Atlas/MET Atlas.pbip` in the installed Power BI Desktop. Keep its `.Report` and `.SemanticModel` folders beside it.

To only view or present the report, download `MET Atlas/MET Atlas v2.pbix` and open it in the free Power BI Desktop (Windows). It is a 2026-10-12 snapshot of the museum version with the data included (about 48 MB), so it works without a BigQuery login. Do not press Refresh unless you have access to `the-met-open-access`. In Desktop, Ctrl+click the buttons. Re-save the `.pbix` after changing the PBIP project, or it goes stale.

The project contains four pages: overview, departments, periods/materials and data quality; 34 source columns; 18 measures; interactive slicers; a Met-inspired theme; and an Import-mode BigQuery connection to `the-met-open-access.met_data.mart_met_objects` (EU). Billing project: `the-met-open-access`. Storage API is disabled for the initial connection to avoid requiring extra Storage API permission. No credentials are stored in the project.

The first refresh succeeded in the installed Power BI Desktop, and the project was saved. The visible overview cards matched BigQuery: 484,956 artworks, 19 departments, 51.2% public domain share and 2,777 highlight artworks. Use Save As if you need a `.pbix` file. Future refreshes may require Google authorization through Power BI's own dialog; CLI authorization is separate.

## Verified source baseline — 2026-10-09

| Check | Value |
| --- | ---: |
| Rows / distinct artworks | 484,956 / 484,956 |
| Null artwork IDs | 0 |
| Departments | 19 |
| Highlight artworks | 2,777 |
| Public domain artworks | 248,472 |
| Gallery metadata present | 49,541 |
| Reversed date intervals | 205 |
| Artworks containing year zero | 1,444 |
| Missing acquisition year | 3,902 |
| Ambiguous period sort mappings | 0 |

Query: `validate_source.sql`. Dry-run estimate: 40,086,900 bytes. Execution limit: 100,000,000 bytes. Results: `source-validation.json`. These are source baselines; compare them with unfiltered Desktop measures after refresh.

## Interpretation

Artwork counts use distinct object_id. Ratios preserve report filters and return blank for an unavailable denominator. Department share removes only Artwork[department] filters. The starter model uses this same column for its department slicer and chart axis.

Gallery metadata does not establish current exhibition or storage status. Historical years remain integers, including BCE values. Periods use artwork start year. Date issues are counted rather than repaired. Missing acquisition years can reflect staging's cast limitation for full-date source values.

Null, blank and relevant Unknown placeholders are missing in quality measures. Artist attribution is not a unique artist count. The mart has no artwork image URL, so images are not fabricated. Material categories are existing model-derived rules. The palette is inspired by https://www.metmuseum.org/ and is not an official Met brand specification.

## Interactive exploration pages

`add_exploration.py` added two pages to the initial four. `polish_museum.py` later rebuilt the gallery page as the Başyapıtlar room (see below) and removed the bubble page together with the data-quality page on 2026-10-12. The original descriptions are kept for history:

- **Dijital galeri:** 11 public-domain artworks with image URLs and descriptive metadata fetched from the official Met Collection API. Select one artwork in the list to change the large image, title, artist, date, medium and clickable Met/Wikidata links. This is a curated snapshot, not a representative sample or the full collection. Its disconnected Gallery table does not alter full-collection counts. For multiple/no selections, Wheat Field with Cypresses is shown when it is in the selection; otherwise the lowest artwork ID is shown (set by `polish_museum.py`).
- **Koleksiyon pusulası:** a department bubble chart of public-domain share versus gallery-information share, with artwork count controlling bubble size. Selecting a department filters the adjacent count, percentage cards and culture ranking. Period, material and culture slicers apply to the full BigQuery artwork source.

Gallery metadata source: https://metmuseum.github.io/ . Individual API, image, Met and Wikidata URLs are retained in `gallery-catalog.json`. `fetch_gallery.py` refreshes this small catalog snapshot; `add_exploration.py` builds only the new pages and Gallery model table. It backs up the changed model and page index under `work` before writing. Close the report before rebuilding, then refresh it in Desktop. Existing four page definitions are preserved.

The two new pages opened and rendered in the installed Desktop. The gallery loaded all 11 rows while the full Artwork table retained 484,956 rows. Selecting Irises in the native slicer changed the painting, artist to Vincent van Gogh and date to 1890. A filtered local DAX query also confirmed that Wheat Field with Cypresses selects its own image and Met URL. All 92 schema-bearing report/project files and visual field references passed validation. The dark bubble page rendered department labels, sizes, percentages and culture rankings from the full source; its explicit cross-filter targets are stored in page.json.

## Museum presentation layer

`polish_museum.py` restyles the report as a walk through a museum. Run it after `build_project.py`, `add_exploration.py` and `fetch_highlights.py`, with the report closed in Desktop, then refresh the `Gallery`, `Gallery Era`, `Gallery Department` and `Gallery Type` tables in Desktop. It backs up the project under `work/powerbi-before-polish-*` before writing, and it can be re-run.

- **Rooms:** Büyük Salon (lobby) plus four galleries, each with its own wall colour: I Koleksiyon (oxblood), II Departmanlar (Prussian blue), III Zaman (olive) and IV Başyapıtlar (aubergine). The night-tour (bubble chart) and conservation (data quality) rooms were removed on 2026-10-12; hypothesis and ML rooms are planned. To add a room, add it to `ROOMS` and write a `build_*` function; the navigation bar, floor plan and previous/next buttons follow `ROOMS`.
- **Backgrounds:** `museum_art.py` draws one 2880×1800 JPEG per page from the same layout boxes that position the visuals: lit plaster walls, gilded frames with mats, brass plaques, slicer pedestals, the floor plan and the navigation band. The backgrounds hold only decoration. Titles, labels and data stay in Power BI visuals.
- **Navigation:** a wayfinding bar on every page, a clickable floor plan in the lobby, previous/next room buttons and a clear-filters button. Department, period, material and public-domain slicers sync across the collection rooms. In Desktop edit mode, Ctrl+click the buttons.
- **Live text:** narrative measures (`Narrative *`) return SVG images. Each sentence follows the current filters, and a value that cannot be calculated shows as "hesaplanamıyor". Department charts and the bubble chart open a museum-label tooltip page (`tooltip_department`).
- **Periods:** a period × material heat map coloured by the share of each material within its period (`Period Material Share`, `Heat Fill`, `Heat Ink`).
- **Masterpieces:** in each era, the 50 best-known highlight artworks that have an open-access image: 465 of the mart's 2,777 highlights on 2026-10-12 (MÖ 8000–2000 has 37 with an image and 1900–günümüz 28, so they show all of theirs). "Best-known" is a popularity proxy, not a curatorial or quality judgement: the number of Wikipedia language editions with an article about the artwork, then about its artist (Wikidata sitelinks), then a fixed pseudo-random order. Most artworks before 1400 have no Wikipedia article, so their order there falls largely to the artist count and the pseudo-random tie-break. Highlights without an image (761 of the 789 in 1900–günümüz) are not shown. Era tabs (a button slicer with the artwork count under each era) filter a guide list ordered by rank; department, painting/object and find-as-you-type title/artist pickers narrow it further. The era, department and type pickers filter through small lookup tables, so a row picked in one era cannot leave the wall empty after another tab is chosen. Choosing an artwork swaps the photo, a frame DAX draws to that photo's measured aspect ratio (gilded for paintings, a bronze shadow box for objects; it covers the black border many Met photos have), the wall label (with the era rank and Wikipedia language count) and the Met/Wikidata buttons. With no selection, the page shows the best-known artwork in view.

`fetch_highlights.py` builds `highlights-catalog.json`: the highlight rows from the mart (through `bq`, or `--source` with the same rows as JSON), plus image URL, artist bio, Wikidata link and overall size from the Met Collection API, each open-access photo's pixel size and black border, and the Wikipedia language counts of the artwork and artist from the Wikidata API (`era_rank`, cached in `work/highlight-cache/wikipedia-languages.json`). API calls are paced and cached under `work/highlight-cache/`; the API answers 403 for a while after bursts, and a rerun resumes. `polish_museum.py` stores the catalogue inside the model as a compressed `Gallery` import table, so refreshing it needs no file path or API access. Gallery numbers come from the API snapshot and do not guarantee current display. Analytical measures are unchanged.

Checks on 2026-10-12: all 136 schema-bearing files and visual field references passed `validate_project.py`. The project opened in Desktop and the four gallery tables refreshed from the embedded catalogue. Local DAX returned 465 gallery rows, 10 eras (37, 8 × 50, 28) and 19 departments. With no selection the wall showed The Death of Socrates; with a row from 1600–1800 still selected, the 1800–1900 tab and the Egyptian Art department fell back to their own best-known artworks. In Desktop, the 1600–1800 tab, a click on Young Woman with a Water Pitcher (third), and a switch to MÖ 2000–1000 swapped the photo, frame and wall label as expected. `MET Atlas v2.pbix` was saved from that state with no selection and the lobby as the opening page.

Checks on 2026-10-09: all 197 schema-bearing files and visual field references passed `validate_project.py`. All seven rooms and the tooltip page rendered in Desktop with the cached data. Every narrative measure evaluated through local DAX. Selecting The Annunciation swapped the painting, the portrait-format frame and the wall label. The hover tooltip popup itself was not captured in a screenshot.

## Build and validation

`build_project.py` generates the initial project from metadata saved under `work/met-mart-metadata.json`. Do not rerun after Desktop edits unless replacing the generated definitions is intended.

`validate_project.py` checks official Microsoft PBIR schemas and visual field references. All 69 generated schema-bearing files passed. The model passed the installed Tabular library's deserializer. The project opened in Power BI Desktop with all four page tabs and themed visuals; refresh completed and the overview cards matched source baselines. A full audit of filter interactions and every page's metrics remains beyond this foundation check.

References:
- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
- https://learn.microsoft.com/en-us/power-query/connectors/google-bigquery
