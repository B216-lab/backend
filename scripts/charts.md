## Assistant

Your backend is a good fit for Superset. The core model is a travel-diary survey: one respondent submission with demographics, income/transport budget, home point, and movement date, plus many trip records with origin/destination points, place types, transport mode, validation status, waiting time, seats, cost, and comment in [00001_initial_schema.sql](/mnt/data/Projects/geoform-full/backend/db/migrations/00001_initial_schema.sql:42). The category dictionaries are already normalized in [seed.sql](/mnt/data/Projects/geoform-full/backend/db/seed.sql:1), and you also have OSM admin polygons in [00002_osm_admin_boundaries.sql](/mnt/data/Projects/geoform-full/backend/db/migrations/00002_osm_admin_boundaries.sql:4). Current Superset docs still cover the chart families that matter here: time series, heatmaps, sankey, pivot tables, and map plugins.

From the live DB, the strongest usable signals are:
- `4,816` submissions and `12,656` movements
- all movements have timestamps and coordinates
- `8,158` movements have waiting time, `8,150` have trip cost, `1,905` have seats, `1,570` have comments
- split is `8,064` transport vs `4,592` on foot
- biggest respondent groups are `WORKING` (`2,731`) and `UNIVERSITY_STUDENT` (`1,441`)
- top OD flow is `HOME_RESIDENCE -> WORKPLACE` (`1,637`)
- all `created_at` values in this dump are the same import timestamp, so trend charts should use `movements_date` or `departure_time`, not `created_at`

Best charts to build:
- KPI tiles: submissions, movements, avg trips per respondent, valid rate, transport share, avg duration, avg waiting time, avg trip cost
- Time series: submissions by `movements_date` month; movements by departure date; valid vs invalid over time
- Stacked bars: social status by gender, vehicle type by social status, movement type by validation status
- Heatmap: departure hour x weekday
- Sankey: departure place type -> destination place type, optionally filtered by vehicle type or social status
- Box plot: trip duration by vehicle type or movement type
- Pivot table: social status x vehicle type, place type origin x destination, validation status x vehicle type
- Point maps: home locations, departure locations, destination locations
- Boundary aggregates: counts by city/district using `osm_admin` polygons
- Table charts: most common comments, invalid trips, longest trips, highest-cost trips

A strong first dashboard would be:
- **Overview**: KPI tiles, monthly submissions, transport vs on-foot split, validation split
- **Behavior**: departure-hour heatmap, top OD sankey, duration by vehicle type, vehicle type share by social status
- **Geography**: home-point map, departure-point map, destination-point map, boundary-level choropleth
- **Quality**: invalid/pending review counts, invalid by vehicle/place type, comments table for moderation

Two caveats matter:
- `birthday` is effectively unusable right now: in this DB it is empty for all submissions, so age charts are not possible
- `movements.cost` exists in schema, but the current submit path does not write it: the API accepts `tripCost` in [types.go](/mnt/data/Projects/geoform-full/backend/internal/forms/types.go:16), but `Movement` has no `Cost` field and the insert in [repository.go](/mnt/data/Projects/geoform-full/backend/internal/store/postgres/repository.go:153) does not persist `cost`. Cost charts will reflect imported legacy data, not necessarily new app data

For Superset setup, I’d create:
- one enriched `fact_movements` dataset joining movements + submissions + reference tables
- one `fact_submissions` dataset for respondent/home analysis
- optionally a region-filtered dataset using [export_region_data.py](/mnt/data/Projects/geoform-full/backend/scripts/export_region_data.py:91), which already exports BI-friendly `movements.csv` and `submissions.csv`

If you want, I can write the exact SQL views for Superset next: `fact_movements`, `fact_submissions`, and a ready-to-use dashboard layout with chart-by-chart config.

