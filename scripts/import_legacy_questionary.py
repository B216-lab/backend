#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"x": SPREADSHEET_NS}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00A0", " ")
    text = text.replace("\u2007", " ")
    text = text.replace("\u202F", " ")
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip().lower()


VALIDATION_STATUS_MAP = {
    normalize_text("Ожидает проверки"): "PENDING_REVIEW",
    normalize_text("Корректно"): "VALID",
    normalize_text("Не корректно"): "INVALID",
    normalize_text("Ожидает удаления"): "PENDING_DELETION",
}

GENDER_MAP = {
    normalize_text("мужской"): "MALE",
    normalize_text("женский"): "FEMALE",
}

SOCIAL_STATUS_MAP = {
    normalize_text("работающий"): "WORKING",
    normalize_text("школьник"): "STUDENT",
    normalize_text("студент"): "UNIVERSITY_STUDENT",
    normalize_text("пенсионер по возрасту"): "PENSIONER",
    normalize_text("человек c ограниченными возможностями"): "PERSON_WITH_DISABILITIES",
    normalize_text("человек ограниченными возможностями"): "PERSON_WITH_DISABILITIES",
    normalize_text("безработный"): "UNEMPLOYED",
    normalize_text("домохозяйка"): "HOUSEWIFE",
    normalize_text("временно нетрудящийся (декретный отпуск, отпуск по уходу за ребенком)"): "TEMPORARILY_UNEMPLOYED",
}

MOVEMENT_TYPE_MAP = {
    normalize_text("пешком"): "ON_FOOT",
    normalize_text("транспорт"): "TRANSPORT",
}

PLACE_TYPE_MAP = {
    normalize_text("дом - место жительства"): "HOME_RESIDENCE",
    normalize_text("дом друзей / родственников"): "FRIENDS_RELATIVES_HOME",
    normalize_text("работа / рабочее место"): "WORKPLACE",
    normalize_text("работа - служебная поездка"): "WORK_BUSINESS_TRIP",
    normalize_text("детский сад"): "DAYCARE_CENTER",
    normalize_text("школа"): "SCHOOL",
    normalize_text("колледж / техникум / училище"): "COLLEGE_TECHNICAL_SCHOOL",
    normalize_text("университет / институт"): "UNIVERSITY_INSTITUTE",
    normalize_text("больница / поликлиника"): "HOSPITAL_CLINIC",
    normalize_text("учреждение культуры (музей, театр, цирк, библиотека и т.п.)"): "CULTURAL_INSTITUTION",
    normalize_text("учреждение культуры"): "CULTURAL_INSTITUTION",
    normalize_text("спорт / фитнес"): "SPORT_FITNESS",
    normalize_text("магазин / рынок"): "STORE_MARKET",
    normalize_text("торгово - развлекательный центр"): "SHOPPING_ENTERTAINMENT_CENTER",
    normalize_text("ресторан / кафе / пункт общественного питания"): "RESTAURANT_CAFE",
    normalize_text("пригород"): "SUBURB",
    normalize_text("другое"): "OTHER",
}

VEHICLE_TYPE_MAP = {
    normalize_text("велосипед"): "BICYCLE",
    normalize_text("средства индивидуальной мобильности (самокат и пр.)"): "INDIVIDUAL_MOBILITY",
    normalize_text("автобус"): "BUS",
    normalize_text("маршрутное такси"): "SHUTTLE_TAXI",
    normalize_text("трамвай"): "TRAM",
    normalize_text("личный автомобиль"): "PRIVATE_CAR",
    normalize_text("троллейбус"): "TROLLEYBUS",
    normalize_text("электричка"): "SUBURBAN_TRAIN",
    normalize_text("метро"): "METRO",
    normalize_text("такси"): "TAXI",
    normalize_text("каршеринг"): "CAR_SHARING",
    normalize_text("городской велопрокат"): "CITY_BIKE_RENTAL",
    normalize_text("служебный транспорт"): "SERVICE",
}

TRANSPORT_COST_RANGE_MAP = {
    normalize_text("ничего не трачу"): (0, 0),
    normalize_text("менее 1000"): (0, 1000),
    normalize_text("1000-2000"): (1000, 2000),
    normalize_text("2000-3000"): (2000, 3000),
    normalize_text("3000-5000"): (3000, 5000),
    normalize_text("5000-7000"): (5000, 7000),
    normalize_text("7000-10 000"): (7000, 10000),
    normalize_text("более 10 000"): (10000, None),
}

INCOME_RANGE_MAP = {
    normalize_text("нет заработка"): (0, 0),
    normalize_text("до 10 тысяч рублей"): (0, 10000),
    normalize_text("от 10 до 25 тысяч рублей"): (10000, 25000),
    normalize_text("от 25 до 35 тысяч рублей"): (25000, 35000),
    normalize_text("от 35 до 45 тысяч рублей"): (35000, 45000),
    normalize_text("от 45 до 65 тысяч рублей"): (45000, 65000),
    normalize_text("от 65 до 90 тысяч рублей"): (65000, 90000),
    normalize_text("от 90 до 120 тысяч рублей"): (90000, 120000),
    normalize_text("от 120 тысяч рублей и выше"): (120000, None),
}


@dataclass
class Point:
    lon: float
    lat: float
    swapped: bool = False


@dataclass
class ImportStats:
    rows_seen: int = 0
    submissions_seen: int = 0
    legacy_keys_seen: int = 0
    linked_submissions_seen: int = 0
    home_coords_swapped: int = 0
    departure_coords_swapped: int = 0
    destination_coords_swapped: int = 0


@dataclass(frozen=True)
class LegacyNameGroup:
    normalized_key: str
    canonical_name: str
    respondent_key: str


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_nullable_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    trimmed = str(value).strip()
    if trimmed == "":
        return "NULL"
    return sql_literal(trimmed)


def sql_nullable_int(value: int | None) -> str:
    if value is None:
        return "NULL"
    return str(int(value))


def sql_nullable_numeric(value: int | float | None) -> str:
    if value is None:
        return "NULL"
    return str(value)


def sql_nullable_date(value: dt.date | None) -> str:
    if value is None:
        return "NULL"
    return f"{sql_literal(value.isoformat())}::date"


def sql_nullable_timestamptz(value: dt.datetime | None) -> str:
    if value is None:
        return "NULL"
    return f"{sql_literal(value.strftime('%Y-%m-%d %H:%M:%S+00'))}::timestamptz"


def sql_nullable_point(point: Point | None) -> str:
    if point is None:
        return "NULL"
    return f"ST_SetSRID(ST_MakePoint({point.lon}, {point.lat}), 4326)"


def lookup_ref_id_sql(table: str, code: str | None) -> str:
    if code is None:
        return "NULL"
    return f"(SELECT id FROM {table} WHERE code = {sql_literal(code)})"


def column_letters_to_number(value: str) -> int:
    total = 0
    for char in value:
        total = total * 26 + (ord(char.upper()) - 64)
    return total


def number_to_column_letters(value: int) -> str:
    result = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        parts = []
        for text_node in cell.findall(".//x:t", NS):
            parts.append(text_node.text or "")
        return "".join(parts)

    value_node = cell.find("x:v", NS)
    if value_node is None or value_node.text is None:
        return ""

    if cell_type == "s":
        index = int(value_node.text)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
        return ""

    return value_node.text


def load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    result: list[str] = []
    for item in root.findall("x:si", NS):
        parts = []
        for text_node in item.findall(".//x:t", NS):
            parts.append(text_node.text or "")
        result.append("".join(parts))
    return result


def read_rows_from_xlsx(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = load_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("x:sheets/x:sheet", NS)
        if first_sheet is None:
            raise ValueError(f"No worksheets found in {path}")

        sheet_rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = None
        for rel in rels:
            if rel.attrib.get("Id") == sheet_rel_id:
                target = rel.attrib.get("Target")
                break
        if not target:
            raise ValueError(f"Could not resolve sheet target for {path}")

        sheet_root = ET.fromstring(archive.read(f"xl/{target}"))

    sheet_data = sheet_root.find("x:sheetData", NS)
    if sheet_data is None:
        raise ValueError(f"Worksheet {path} has no sheetData section")

    rows = list(sheet_data.findall("x:row", NS))
    if not rows:
        return []

    header_map: OrderedDict[int, str] = OrderedDict()
    output_rows: list[dict[str, str]] = []

    for row_index, row in enumerate(rows):
        values_by_index: dict[int, str] = {}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            match = re.match(r"([A-Z]+)", ref)
            if not match:
                continue
            column_index = column_letters_to_number(match.group(1))
            values_by_index[column_index] = cell_text(cell, shared_strings)

        if row_index == 0:
            for column_index in sorted(values_by_index):
                header_map[column_index] = values_by_index[column_index]
            continue

        row_dict: dict[str, str] = {}
        for column_index, header in header_map.items():
            row_dict[header] = values_by_index.get(column_index, "")
        output_rows.append(row_dict)

    return output_rows


def load_polygons(geojson_dir: Path) -> list[list[list[tuple[float, float]]]]:
    polygons: list[list[list[tuple[float, float]]]] = []
    if not geojson_dir.exists():
        return polygons

    for path in sorted(geojson_dir.glob("*.geojson")):
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for feature in data.get("features", []):
            geometry = feature.get("geometry") or {}
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates") or []
            if geometry_type == "Polygon":
                polygons.append(_normalize_polygon(coordinates))
            elif geometry_type == "MultiPolygon":
                for polygon in coordinates:
                    polygons.append(_normalize_polygon(polygon))
    return polygons


def _normalize_polygon(rings: list[list[list[float]]]) -> list[list[tuple[float, float]]]:
    normalized: list[list[tuple[float, float]]] = []
    for ring in rings:
        normalized.append([(float(point[0]), float(point[1])) for point in ring])
    return normalized


def point_in_ring(point: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    if len(ring) < 3:
        return False

    x, y = point
    inside = False
    previous = ring[-1]

    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        intersects = ((y1 > y) != (y2 > y))
        if intersects:
            denominator = y2 - y1
            if denominator != 0:
                xinters = (x2 - x1) * (y - y1) / denominator + x1
                if x < xinters:
                    inside = not inside
        previous = current

    return inside


def point_in_polygon(point: tuple[float, float], polygon: list[list[tuple[float, float]]]) -> bool:
    if not polygon:
        return False
    if not point_in_ring(point, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def point_in_any_polygon(point: tuple[float, float], polygons: list[list[list[tuple[float, float]]]]) -> bool:
    return any(point_in_polygon(point, polygon) for polygon in polygons)


def is_valid_lon_lat(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def parse_point(raw_value: str, polygons: list[list[list[tuple[float, float]]]]) -> Point | None:
    text = raw_value.replace('"', "").replace("'", "").strip()
    if text == "":
        return None

    parts = [part.strip() for part in text.split(",")] if "," in text else text.split()
    if len(parts) != 2:
        return None

    try:
        first = float(parts[0])
        second = float(parts[1])
    except ValueError:
        return None

    candidate_a = (first, second)
    candidate_b = (second, first)

    if polygons:
        in_a = is_valid_lon_lat(*candidate_a) and point_in_any_polygon(candidate_a, polygons)
        in_b = is_valid_lon_lat(*candidate_b) and point_in_any_polygon(candidate_b, polygons)
        if in_a and not in_b:
            return Point(candidate_a[0], candidate_a[1], swapped=False)
        if in_b and not in_a:
            return Point(candidate_b[0], candidate_b[1], swapped=True)

    if abs(first) > 90 and is_valid_lon_lat(*candidate_a):
        return Point(candidate_a[0], candidate_a[1], swapped=False)

    if abs(second) > 90 and is_valid_lon_lat(*candidate_b):
        return Point(candidate_b[0], candidate_b[1], swapped=True)

    if is_valid_lon_lat(*candidate_a):
        return Point(candidate_a[0], candidate_a[1], swapped=False)

    if is_valid_lon_lat(*candidate_b):
        return Point(candidate_b[0], candidate_b[1], swapped=True)

    return None


def first_vehicle_code(raw_value: str) -> str | None:
    if raw_value.strip() == "":
        return None
    parts = re.split(r"[;,/\n]+", raw_value)
    for part in parts:
        code = VEHICLE_TYPE_MAP.get(normalize_text(part))
        if code:
            return code
    return None


def parse_date(raw_value: str) -> dt.date:
    return dt.datetime.strptime(raw_value.strip(), "%Y-%m-%d").date()


def parse_time(raw_value: str, movement_date: dt.date) -> dt.datetime | None:
    text = raw_value.strip()
    if text == "":
        return None
    parsed_time = dt.datetime.strptime(text, "%H:%M").time()
    return dt.datetime(
        movement_date.year,
        movement_date.month,
        movement_date.day,
        parsed_time.hour,
        parsed_time.minute,
        tzinfo=dt.timezone.utc,
    )


def parse_optional_int(raw_value: str) -> int | None:
    text = raw_value.strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_optional_numeric(raw_value: str) -> int | None:
    return parse_optional_int(raw_value)


def parse_transport_cost_range(raw_value: str) -> tuple[int | None, int | None]:
    key = normalize_text(raw_value)
    if key in TRANSPORT_COST_RANGE_MAP:
        return TRANSPORT_COST_RANGE_MAP[key]
    raise ValueError(f"Unsupported transport cost range: {raw_value}")


def parse_income_range(raw_value: str) -> tuple[int | None, int | None]:
    key = normalize_text(raw_value)
    if key in INCOME_RANGE_MAP:
        return INCOME_RANGE_MAP[key]
    raise ValueError(f"Unsupported income range: {raw_value}")


def choose_waiting_time(wait_at_start: str, wait_between_transfers: str) -> int | None:
    value = parse_optional_int(wait_at_start)
    if value is not None:
        return value
    return parse_optional_int(wait_between_transfers)


def legacy_key_name(row: dict[str, str]) -> str | None:
    name = (row.get("Имя") or "").strip()
    if name == "":
        return None
    return name


def normalize_legacy_name_key(name: str | None) -> str:
    text = normalize_text(name)
    if text == "":
        return ""
    return re.sub(r"[^0-9a-zа-яё]+", "", text, flags=re.IGNORECASE)


def build_legacy_respondent_key(normalized_name_key: str) -> str:
    digest = hashlib.sha256(normalized_name_key.encode("utf-8")).hexdigest()
    return f"legacy-import-{digest}"


def build_legacy_name_groups(workbook_rows: list[dict[str, str]]) -> dict[str, LegacyNameGroup]:
    variants_by_key: dict[str, OrderedDict[str, int]] = {}
    for row in workbook_rows:
        name = legacy_key_name(row)
        if name is None:
            continue
        normalized_key = normalize_legacy_name_key(name)
        if normalized_key == "":
            continue
        if normalized_key not in variants_by_key:
            variants_by_key[normalized_key] = OrderedDict()
        variants_by_key[normalized_key][name] = variants_by_key[normalized_key].get(name, 0) + 1

    result: dict[str, LegacyNameGroup] = {}
    for normalized_key, variants in variants_by_key.items():
        canonical_name = sorted(
            variants.items(),
            key=lambda item: (-item[1], -len(item[0]), item[0].lower(), item[0]),
        )[0][0]
        result[normalized_key] = LegacyNameGroup(
            normalized_key=normalized_key,
            canonical_name=canonical_name,
            respondent_key=build_legacy_respondent_key(normalized_key),
        )
    return result


def legacy_name_group_for_row(
    row: dict[str, str],
    name_groups: dict[str, LegacyNameGroup],
) -> LegacyNameGroup | None:
    name = legacy_key_name(row)
    if name is None:
        return None
    normalized_key = normalize_legacy_name_key(name)
    if normalized_key == "":
        return None
    return name_groups.get(normalized_key)


def build_allowed_keys_sql(name_groups: dict[str, LegacyNameGroup]) -> tuple[str, int]:
    if not name_groups:
        return "", 0

    values = []
    for group in name_groups.values():
        values.append(
            f"({sql_literal(group.canonical_name)}, {sql_literal(group.respondent_key)}, FALSE)"
        )

    sql = (
        "INSERT INTO allowed_respondent_keys (name, respondent_key, is_active)\n"
        "VALUES\n"
        + ",\n".join(values)
        + "\nON CONFLICT (respondent_key) DO UPDATE\n"
        "SET name = EXCLUDED.name,\n"
        "    is_active = FALSE;\n"
    )
    return sql, len(name_groups)


def allowed_respondent_key_id_sql(respondent_key: str | None) -> str:
    if respondent_key is None:
        return "NULL"
    return f"(SELECT id FROM allowed_respondent_keys WHERE respondent_key = {sql_literal(respondent_key)})"


def build_submission_sql(
    group_key: str,
    rows: list[dict[str, str]],
    polygons: list[list[list[tuple[float, float]]]],
    name_groups: dict[str, LegacyNameGroup],
    stats: ImportStats,
) -> str:
    first_row = rows[0]
    movement_date = parse_date(first_row["Дата перемещений"])
    legacy_name_group = legacy_name_group_for_row(first_row, name_groups)
    legacy_respondent_key = legacy_name_group.respondent_key if legacy_name_group is not None else None

    gender_code = GENDER_MAP.get(normalize_text(first_row["Пол"]))
    social_status_code = SOCIAL_STATUS_MAP.get(normalize_text(first_row["Социальный статус"]))
    if normalize_text(first_row["Пол"]) and gender_code is None:
        raise ValueError(f"{group_key}: unsupported gender {first_row['Пол']!r}")
    if normalize_text(first_row["Социальный статус"]) and social_status_code is None:
        raise ValueError(f"{group_key}: unsupported social status {first_row['Социальный статус']!r}")

    income_min, income_max = parse_income_range(first_row["Финансовое положение"])
    transport_cost_min, transport_cost_max = parse_transport_cost_range(first_row["Затраты на транспор"])
    home_point = parse_point(first_row["Координаты адреса"], polygons)
    if home_point and home_point.swapped:
        stats.home_coords_swapped += 1

    profile_fields = [
        "Имя",
        "Возраст",
        "Пол",
        "Социальный статус",
        "Финансовое положение",
        "Затраты на транспор",
        "Город",
        "Адрес проживания",
        "Координаты адреса",
    ]
    for field in profile_fields:
        distinct = {(row.get(field) or "").strip() for row in rows}
        if len(distinct) > 1:
            raise ValueError(f"{group_key}: inconsistent submission field {field!r}: {sorted(distinct)!r}")

    if legacy_respondent_key is not None:
        stats.linked_submissions_seen += 1

    submission_insert = f"""WITH inserted_submission AS (
    INSERT INTO movements_form_submissions (
        allowed_respondent_key_id,
        birthday,
        gender,
        social_status_id,
        transport_cost_min,
        transport_cost_max,
        income_min,
        income_max,
        home_address,
        home_readable_address,
        movements_date
    )
    VALUES (
        {allowed_respondent_key_id_sql(legacy_respondent_key)},
        NULL,
        {sql_nullable_text(gender_code)},
        {lookup_ref_id_sql("social_statuses", social_status_code)},
        {sql_nullable_int(transport_cost_min)},
        {sql_nullable_int(transport_cost_max)},
        {sql_nullable_int(income_min)},
        {sql_nullable_int(income_max)},
        {sql_nullable_point(home_point)},
        {sql_nullable_text(first_row["Адрес проживания"])},
        {sql_nullable_date(movement_date)}
    )
    RETURNING id
)
INSERT INTO movements (
    movement_type_id,
    departure_time,
    destination_time,
    departure_place,
    destination_place,
    departure_place_address,
    destination_place_address,
    departure_place_type_id,
    validation_status_id,
    destination_place_type_id,
    vehicle_type_id,
    cost,
    waiting_time,
    seats_amount,
    comment,
    movements_form_submission_id
)
VALUES
"""

    movement_values: list[str] = []
    for row in rows:
        stats.rows_seen += 1

        movement_type_code = MOVEMENT_TYPE_MAP.get(normalize_text(row["Тип передвижения"]))
        departure_place_code = PLACE_TYPE_MAP.get(normalize_text(row["Пункт отправления"]))
        destination_place_code = PLACE_TYPE_MAP.get(normalize_text(row["Пункт прибытия"]))
        validation_status_code = VALIDATION_STATUS_MAP.get(normalize_text(row["Статус"]))
        vehicle_type_code = first_vehicle_code(row["Транспорт"])

        if movement_type_code is None:
            raise ValueError(f"{group_key}: unsupported movement type {row['Тип передвижения']!r}")
        if departure_place_code is None:
            raise ValueError(f"{group_key}: unsupported departure place {row['Пункт отправления']!r}")
        if destination_place_code is None:
            raise ValueError(f"{group_key}: unsupported destination place {row['Пункт прибытия']!r}")
        if validation_status_code is None:
            raise ValueError(f"{group_key}: unsupported validation status {row['Статус']!r}")

        departure_point = parse_point(row["Координаты отправления"], polygons)
        destination_point = parse_point(row["Координаты прибытия"], polygons)
        if departure_point and departure_point.swapped:
            stats.departure_coords_swapped += 1
        if destination_point and destination_point.swapped:
            stats.destination_coords_swapped += 1

        departure_time = parse_time(row["Время отправления"], movement_date)
        destination_time = parse_time(row["Время прибытия"], movement_date)
        waiting_time = choose_waiting_time(
            row["Время ожидания транспорта"],
            row["Время ожидания между пересадками"],
        )
        seats_amount = parse_optional_int(row["Количество людей в машине"])
        cost = parse_optional_numeric(row["Стоимость поездки или парковки"])

        movement_values.append(
            """(
    {movement_type_id},
    {departure_time},
    {destination_time},
    {departure_place},
    {destination_place},
    {departure_place_address},
    {destination_place_address},
    {departure_place_type_id},
    {validation_status_id},
    {destination_place_type_id},
    {vehicle_type_id},
    {cost},
    {waiting_time},
    {seats_amount},
    {comment},
    (SELECT id FROM inserted_submission)
)""".format(
                movement_type_id=lookup_ref_id_sql("ref_movement_type", movement_type_code),
                departure_time=sql_nullable_timestamptz(departure_time),
                destination_time=sql_nullable_timestamptz(destination_time),
                departure_place=sql_nullable_point(departure_point),
                destination_place=sql_nullable_point(destination_point),
                departure_place_address=sql_nullable_text(row["Адрес отправления"]),
                destination_place_address=sql_nullable_text(row["Адрес прибытия"]),
                departure_place_type_id=lookup_ref_id_sql("ref_place_type", departure_place_code),
                validation_status_id=lookup_ref_id_sql("ref_validation_status", validation_status_code),
                destination_place_type_id=lookup_ref_id_sql("ref_place_type", destination_place_code),
                vehicle_type_id=lookup_ref_id_sql("ref_vehicle_type", vehicle_type_code),
                cost=sql_nullable_numeric(cost),
                waiting_time=sql_nullable_int(waiting_time),
                seats_amount=sql_nullable_int(seats_amount),
                comment=sql_nullable_text(row["Комментарий"]),
            )
        )

    return submission_insert + ",\n".join(movement_values) + ";\n"


def build_import_sql(
    workbook_rows: list[dict[str, str]],
    polygons: list[list[list[tuple[float, float]]]],
    replace_existing: bool,
) -> tuple[str, ImportStats]:
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in workbook_rows:
        group_key = f"{row['ID'].strip()}|{row['Дата перемещений'].strip()}"
        groups.setdefault(group_key, []).append(row)

    stats = ImportStats(submissions_seen=len(groups))
    name_groups = build_legacy_name_groups(workbook_rows)

    parts = ["BEGIN;\n"]
    if replace_existing:
        parts.append("TRUNCATE TABLE movements, movements_form_submissions RESTART IDENTITY CASCADE;\n")
        parts.append("DELETE FROM allowed_respondent_keys WHERE is_active = FALSE;\n")

    allowed_keys_sql, allowed_keys_count = build_allowed_keys_sql(name_groups)
    stats.legacy_keys_seen = allowed_keys_count
    if allowed_keys_sql:
        parts.append(allowed_keys_sql)

    for group_key, rows in groups.items():
        parts.append(build_submission_sql(group_key, rows, polygons, name_groups, stats))

    parts.append("COMMIT;\n")
    return "".join(parts), stats


def run_psql(sql: str, container: str, db_user: str, db_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )


def query_counts(container: str, db_user: str, db_name: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            db_user,
            "-d",
            db_name,
            "-t",
            "-A",
            "-F",
            ",",
            "-c",
            (
                "select 'submissions', count(*) from movements_form_submissions "
                "union all "
                "select 'movements', count(*) from movements "
                "union all "
                "select 'allowed_respondent_keys', count(*) from allowed_respondent_keys "
                "union all "
                "select 'inactive_allowed_respondent_keys', count(*) from allowed_respondent_keys where is_active = false"
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "count query failed")
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy questionnaire workbook into the backend PostGIS database.")
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=PROJECT_ROOT / "2025_12_14_questionary" / "анкеты.xlsx",
        help="Path to the legacy анкеты.xlsx workbook.",
    )
    parser.add_argument(
        "--geojson-dir",
        type=Path,
        default=PROJECT_ROOT / "2025_12_14_questionary",
        help="Directory with GeoJSON files used to validate coordinate order.",
    )
    parser.add_argument(
        "--docker-container",
        default="backend-postgres-1",
        help="Running Docker container name for PostgreSQL.",
    )
    parser.add_argument(
        "--db-user",
        default="umrs",
        help="Database user.",
    )
    parser.add_argument(
        "--db-name",
        default="umrs_go_backend",
        help="Database name.",
    )
    parser.add_argument(
        "--sql-out",
        type=Path,
        help="Optional path to save the generated SQL for inspection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build SQL and print summary without executing it.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Truncate existing form data before importing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    workbook_path = args.xlsx.resolve()
    geojson_dir = args.geojson_dir.resolve()

    if not workbook_path.exists():
        print(f"Workbook not found: {workbook_path}", file=sys.stderr)
        return 1

    workbook_rows = read_rows_from_xlsx(workbook_path)
    polygons = load_polygons(geojson_dir)
    sql, stats = build_import_sql(workbook_rows, polygons, args.replace_existing)

    if args.sql_out is not None:
        args.sql_out.write_text(sql, encoding="utf-8")

    print(f"Workbook rows: {len(workbook_rows)}")
    print(f"Submission groups: {stats.submissions_seen}")
    print(f"Legacy respondent keys prepared: {stats.legacy_keys_seen}")
    print(f"Linked submissions prepared: {stats.linked_submissions_seen}")
    print(f"Home coordinates swapped: {stats.home_coords_swapped}")
    print(f"Departure coordinates swapped: {stats.departure_coords_swapped}")
    print(f"Destination coordinates swapped: {stats.destination_coords_swapped}")
    print(f"GeoJSON polygons loaded: {len(polygons)}")

    if args.dry_run:
        print("Dry run only, SQL was not executed.")
        return 0

    result = run_psql(sql, args.docker_container, args.db_user, args.db_name)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        print(result.stderr.strip() or "psql import failed", file=sys.stderr)
        return result.returncode

    print("Import completed.")
    print(query_counts(args.docker_container, args.db_user, args.db_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
