#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import xml.sax.saxutils
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGION = PROJECT_ROOT / "custom-data" / "chelyabinsk_agglomeration.geojson"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "exports" / "chelyabinsk_agglomeration"
DEFAULT_WORKBOOK_NAME = "region_export.xlsx"
DEFAULT_DATABASE_URL = (
    "postgres://"
    f"{os.getenv('POSTGRES_USER', 'umrs')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'secret')}@"
    f"localhost:{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'umrs_go_backend')}?sslmode=disable"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export movements and linked submissions filtered by a GeoJSON region."
    )
    parser.add_argument(
        "--region-geojson",
        type=Path,
        default=DEFAULT_REGION,
        help="Path to the GeoJSON file whose first feature geometry defines the export region.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where movements.csv and submissions.csv will be written.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("EXPORT_DATABASE_URL") or os.getenv("SEED_DATABASE_URL") or DEFAULT_DATABASE_URL,
        help="PostgreSQL connection string. Defaults to the same local env pattern used by seed.sh.",
    )
    parser.add_argument(
        "--psql-bin",
        help="Optional local psql binary path. If omitted, the script runs psql in a postgres:18-alpine Docker container.",
    )
    parser.add_argument(
        "--workbook-name",
        default=DEFAULT_WORKBOOK_NAME,
        help="Workbook filename to create in the output directory.",
    )
    return parser.parse_args()


def load_region_geometry(geojson_path: Path) -> str:
    data = json.loads(geojson_path.read_text(encoding="utf-8"))

    geometry = None
    if data.get("type") == "FeatureCollection":
        features = data.get("features")
        if not isinstance(features, list) or len(features) == 0:
            raise ValueError("GeoJSON FeatureCollection must contain at least one feature")
        geometry = features[0].get("geometry")
    elif data.get("type") == "Feature":
        geometry = data.get("geometry")
    else:
        geometry = data

    if not isinstance(geometry, dict) or not geometry.get("type") or "coordinates" not in geometry:
        raise ValueError("GeoJSON file must contain a valid geometry object")

    return json.dumps(geometry, ensure_ascii=False, separators=(",", ":"))


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def qualifying_movements_cte(region_geometry: str) -> str:
    region_literal = sql_literal(region_geometry)
    return f"""
WITH region AS (
    SELECT ST_SetSRID(ST_GeomFromGeoJSON({region_literal}), 4326) AS geom
),
qualifying_movements AS (
    SELECT m.id, m.movements_form_submission_id
    FROM movements AS m
    CROSS JOIN region
    WHERE m.departure_place IS NOT NULL
      AND m.destination_place IS NOT NULL
      AND ST_Covers(region.geom, m.departure_place)
      AND ST_Covers(region.geom, m.destination_place)
)
""".strip()


def build_movements_query(region_geometry: str) -> str:
    return (
        qualifying_movements_cte(region_geometry)
        + """
SELECT
    m.id AS movement_id,
    m.created_at AS movement_created_at,
    m.movements_form_submission_id AS submission_id,
    m.departure_time,
    m.destination_time,
    mt.code AS movement_type_code,
    mt.description_ru AS movement_type_description_ru,
    dpt.code AS departure_place_type_code,
    dpt.description_ru AS departure_place_type_description_ru,
    dst.code AS destination_place_type_code,
    dst.description_ru AS destination_place_type_description_ru,
    vs.code AS validation_status_code,
    vs.description_ru AS validation_status_description_ru,
    vt.code AS vehicle_type_code,
    vt.description_ru AS vehicle_type_description_ru,
    m.waiting_time,
    m.seats_amount,
    m.comment,
    m.departure_place_address,
    m.destination_place_address,
    ST_X(m.departure_place) AS departure_longitude,
    ST_Y(m.departure_place) AS departure_latitude,
    ST_X(m.destination_place) AS destination_longitude,
    ST_Y(m.destination_place) AS destination_latitude,
    ST_AsGeoJSON(m.departure_place) AS departure_place_geojson,
    ST_AsGeoJSON(m.destination_place) AS destination_place_geojson
FROM qualifying_movements AS qm
JOIN movements AS m ON m.id = qm.id
JOIN ref_movement_type AS mt ON mt.id = m.movement_type_id
JOIN ref_place_type AS dpt ON dpt.id = m.departure_place_type_id
JOIN ref_place_type AS dst ON dst.id = m.destination_place_type_id
JOIN ref_validation_status AS vs ON vs.id = m.validation_status_id
LEFT JOIN ref_vehicle_type AS vt ON vt.id = m.vehicle_type_id
ORDER BY m.id
"""
    )


def build_submissions_query(region_geometry: str) -> str:
    return (
        qualifying_movements_cte(region_geometry)
        + """
,
qualifying_submissions AS (
    SELECT DISTINCT movements_form_submission_id AS id
    FROM qualifying_movements
)
SELECT
    s.id AS submission_id,
    s.created_at AS submission_created_at,
    s.movements_date,
    s.allowed_respondent_key_id,
    s.birthday,
    s.gender,
    ss.code AS social_status_code,
    ss.description_ru AS social_status_description_ru,
    s.transport_cost_min,
    s.transport_cost_max,
    s.income_min,
    s.income_max,
    s.home_readable_address,
    ST_X(s.home_address) AS home_longitude,
    ST_Y(s.home_address) AS home_latitude,
    ST_AsGeoJSON(s.home_address) AS home_address_geojson
FROM qualifying_submissions AS qs
JOIN movements_form_submissions AS s ON s.id = qs.id
LEFT JOIN social_statuses AS ss ON ss.id = s.social_status_id
ORDER BY s.id
"""
    )


def build_counts_query(region_geometry: str) -> str:
    return (
        qualifying_movements_cte(region_geometry)
        + """
,
qualifying_submissions AS (
    SELECT DISTINCT movements_form_submission_id AS id
    FROM qualifying_movements
)
SELECT
    (SELECT COUNT(*) FROM qualifying_movements) AS movements_count,
    (SELECT COUNT(*) FROM qualifying_submissions) AS submissions_count
"""
    )


def psql_command(database_url: str, psql_bin: str | None) -> list[str]:
    if psql_bin:
        return [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-f", "-"]

    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-i",
        "-v",
        f"{PROJECT_ROOT}:/work",
        "-w",
        "/work",
        "postgres:18-alpine",
        "psql",
        database_url,
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        "-",
    ]


def run_sql(
    sql: str,
    database_url: str,
    psql_bin: str | None,
    *,
    tuples_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = psql_command(database_url, psql_bin)
    if tuples_only:
        cmd.extend(["-t", "-A", "-F", "|"])
    return subprocess.run(
        cmd,
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )


def run_counts_query(region_geometry: str, database_url: str, psql_bin: str | None) -> tuple[int, int]:
    sql = build_counts_query(region_geometry).strip() + ";\n"
    result = run_sql(sql, database_url, psql_bin, tuples_only=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "psql count query failed"
        raise RuntimeError(stderr)

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"unexpected count query output: {result.stdout.strip()!r}")

    parts = [part.strip() for part in lines[0].split("|")]
    if len(parts) != 2:
        raise RuntimeError(f"unexpected count query output: {lines[0]!r}")

    try:
        return int(parts[0]), int(parts[1])
    except ValueError as err:
        raise RuntimeError(f"unexpected count query output: {lines[0]!r}") from err


def run_copy_query(query: str, output_path: Path, database_url: str, psql_bin: str | None) -> None:
    sql = f"COPY (\n{query.strip()}\n) TO STDOUT WITH CSV HEADER;\n"
    result = run_sql(sql, database_url, psql_bin)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "psql export failed"
        raise RuntimeError(stderr)
    output_path.write_text(result.stdout, encoding="utf-8")


def escape_xml(value: str) -> str:
    return xml.sax.saxutils.escape(value, {"'": "&apos;", '"': "&quot;"})


def excel_column_name(index: int) -> str:
    letters: list[str] = []
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def build_sheet_xml(rows: list[list[str]]) -> str:
    row_xml: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{excel_column_name(column_index)}{row_index}"
            escaped_value = escape_xml(value)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">{escaped_value}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(row_xml)
        + "</sheetData></worksheet>"
    )


def create_xlsx_from_csvs(workbook_path: Path, sheets: list[tuple[str, Path]]) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(workbook_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
"""
            + "".join(
                f'  <Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
                for index in range(1, len(sheets) + 1)
            )
            + "</Types>\n",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "docProps/core.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Codex export_region_data.py</dc:creator>
  <cp:lastModifiedBy>Codex export_region_data.py</cp:lastModifiedBy>
</cp:coreProperties>
""",
        )
        archive.writestr(
            "docProps/app.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Python</Application>
  <Sheets>{len(sheets)}</Sheets>
</Properties>
""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
"""
            + "".join(
                f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>\n'
                for index in range(1, len(sheets) + 1)
            )
            + f'  <Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>\n'
            + f'  <Relationship Id="rId{len(sheets) + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>\n'
            + "</Relationships>\n",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
"""
            + "".join(
                f'    <sheet name="{escape_xml(sheet_name)}" sheetId="{index}" r:id="rId{index}"/>\n'
                for index, (sheet_name, _) in enumerate(sheets, start=1)
            )
            + "  </sheets>\n</workbook>\n",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1">
    <font><sz val="10"/><name val="Arial"/></font>
  </fonts>
  <fills count="1">
    <fill><patternFill patternType="none"/></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  </cellXfs>
</styleSheet>
""",
        )
        archive.writestr(
            "xl/theme/theme1.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F497D"/></a:dk2>
      <a:lt2><a:srgbClr val="EEECE1"/></a:lt2>
      <a:accent1><a:srgbClr val="4F81BD"/></a:accent1>
      <a:accent2><a:srgbClr val="C0504D"/></a:accent2>
      <a:accent3><a:srgbClr val="9BBB59"/></a:accent3>
      <a:accent4><a:srgbClr val="8064A2"/></a:accent4>
      <a:accent5><a:srgbClr val="4BACC6"/></a:accent5>
      <a:accent6><a:srgbClr val="F79646"/></a:accent6>
      <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
      <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont><a:latin typeface="Arial"/></a:majorFont>
      <a:minorFont><a:latin typeface="Arial"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>
""",
        )

        for index, (_, csv_path) in enumerate(sheets, start=1):
            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                rows = [[value for value in row] for row in csv.reader(csv_file)]
            archive.writestr(f"xl/worksheets/sheet{index}.xml", build_sheet_xml(rows))


def validate_psql_bin(psql_bin: str | None) -> None:
    if psql_bin and shutil.which(psql_bin) is None and not Path(psql_bin).exists():
        raise FileNotFoundError(f"psql binary not found: {psql_bin}")


def main() -> int:
    started_at = time.monotonic()
    args = parse_args()
    region_geojson = args.region_geojson.resolve()
    out_dir = args.out_dir.resolve()

    if not region_geojson.exists():
        print(f"GeoJSON file not found: {region_geojson}", file=sys.stderr)
        return 1

    try:
        log("Starting region export...")
        log(f"Region GeoJSON: {region_geojson}")
        log(f"Output directory: {out_dir}")
        validate_psql_bin(args.psql_bin)
        log("Loading region geometry from GeoJSON...")
        region_geometry = load_region_geometry(region_geojson)
        log("Region geometry loaded successfully.")
        out_dir.mkdir(parents=True, exist_ok=True)
        log("Output directory is ready.")

        movements_csv = out_dir / "movements.csv"
        submissions_csv = out_dir / "submissions.csv"
        workbook_path = out_dir / args.workbook_name

        log("Counting qualifying movements and linked submissions...")
        counts_started_at = time.monotonic()
        movements_count, submissions_count = run_counts_query(region_geometry, args.database_url, args.psql_bin)
        log(
            "Counts ready "
            f"({time.monotonic() - counts_started_at:.1f}s): "
            f"{movements_count} qualifying movements, "
            f"{submissions_count} linked submissions."
        )

        log(f"Exporting movements CSV to {movements_csv}...")
        movements_started_at = time.monotonic()
        run_copy_query(build_movements_query(region_geometry), movements_csv, args.database_url, args.psql_bin)
        log(
            "Finished movements CSV "
            f"({time.monotonic() - movements_started_at:.1f}s, "
            f"{movements_csv.stat().st_size} bytes)."
        )

        log(f"Exporting submissions CSV to {submissions_csv}...")
        submissions_started_at = time.monotonic()
        run_copy_query(build_submissions_query(region_geometry), submissions_csv, args.database_url, args.psql_bin)
        log(
            "Finished submissions CSV "
            f"({time.monotonic() - submissions_started_at:.1f}s, "
            f"{submissions_csv.stat().st_size} bytes)."
        )

        log(f"Building workbook {workbook_path}...")
        workbook_started_at = time.monotonic()
        create_xlsx_from_csvs(
            workbook_path,
            [
                ("movements", movements_csv),
                ("submissions", submissions_csv),
            ],
        )
        log(
            "Finished workbook "
            f"({time.monotonic() - workbook_started_at:.1f}s, "
            f"{workbook_path.stat().st_size} bytes)."
        )
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as err:
        print(str(err), file=sys.stderr)
        return 1

    log(f"Region export completed in {time.monotonic() - started_at:.1f}s.")
    print(f"Region export completed from {region_geojson}")
    print(f"Movements CSV: {movements_csv}")
    print(f"Submissions CSV: {submissions_csv}")
    print(f"Workbook: {workbook_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
