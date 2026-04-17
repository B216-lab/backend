import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_region_data import (
    build_counts_query,
    build_movements_query,
    build_submissions_query,
    create_xlsx_from_csvs,
    load_region_geometry,
)


class LoadRegionGeometryTests(unittest.TestCase):
    def test_loads_first_feature_geometry_from_feature_collection(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[60.0, 55.0], [61.0, 55.0], [60.0, 56.0], [60.0, 55.0]]],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            geojson_path = Path(tmp_dir) / "region.geojson"
            geojson_path.write_text(json.dumps(payload), encoding="utf-8")

            geometry = load_region_geometry(geojson_path)

        self.assertEqual(
            geometry,
            json.dumps(payload["features"][0]["geometry"], ensure_ascii=False, separators=(",", ":")),
        )

    def test_raises_when_feature_collection_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            geojson_path = Path(tmp_dir) / "region.geojson"
            geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "at least one feature"):
                load_region_geometry(geojson_path)


class QueryShapeTests(unittest.TestCase):
    def test_movements_query_uses_boundary_inclusive_region_filter(self) -> None:
        query = build_movements_query('{"type":"Polygon","coordinates":[]}')

        self.assertIn("ST_Covers(region.geom, m.departure_place)", query)
        self.assertIn("ST_Covers(region.geom, m.destination_place)", query)
        self.assertIn("m.departure_place IS NOT NULL", query)
        self.assertIn("m.destination_place IS NOT NULL", query)
        self.assertIn("ORDER BY m.id", query)

    def test_submissions_query_deduplicates_linked_submissions(self) -> None:
        query = build_submissions_query('{"type":"Polygon","coordinates":[]}')

        self.assertIn("SELECT DISTINCT movements_form_submission_id AS id", query)
        self.assertIn("LEFT JOIN social_statuses AS ss", query)
        self.assertIn("ORDER BY s.id", query)

    def test_counts_query_reports_both_totals(self) -> None:
        query = build_counts_query('{"type":"Polygon","coordinates":[]}')

        self.assertIn("COUNT(*) FROM qualifying_movements", query)
        self.assertIn("COUNT(*) FROM qualifying_submissions", query)


class WorkbookTests(unittest.TestCase):
    def test_create_xlsx_from_csvs_creates_workbook_with_two_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            movements_csv = tmp_path / "movements.csv"
            submissions_csv = tmp_path / "submissions.csv"
            workbook_path = tmp_path / "region_export.xlsx"

            movements_csv.write_text("id,name\n1,Move A\n", encoding="utf-8")
            submissions_csv.write_text("id,name\n10,Submission A\n", encoding="utf-8")

            create_xlsx_from_csvs(
                workbook_path,
                [
                    ("movements", movements_csv),
                    ("submissions", submissions_csv),
                ],
            )

            self.assertTrue(workbook_path.exists())

            with zipfile.ZipFile(workbook_path) as archive:
                workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
                sheet1_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
                sheet2_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

            self.assertIn('sheet name="movements"', workbook_xml)
            self.assertIn('sheet name="submissions"', workbook_xml)
            self.assertIn("Move A", sheet1_xml)
            self.assertIn("Submission A", sheet2_xml)


if __name__ == "__main__":
    unittest.main()
