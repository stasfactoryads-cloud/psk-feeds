#!/usr/bin/env python3
"""
Генератор XML-фида ЖК РЕСПЕКТ для Яндекс Директ (товарная кампания).
Формат: YRL (Yandex Realty Language).
Источник данных: https://psk-info.ru/api/flats/?format=json
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
import sys
import os

# === Конфигурация ===
API_BASE = "https://psk-info.ru/api/flats/?format=json"
PROJECT_ID = 39  # ЖК РЕСПЕКТ
PROJECT_SLUG = "zhk-respect"
PROJECT_NAME = "РЕСПЕКТ"
PROJECT_ADDRESS = "г. Санкт-Петербург, Полюстровский проспект, 87"
METRO = "Лесная"
BUILDING_TYPE = "монолитный"
AGENT_ORG = "Группа компаний ПСК"
AGENT_URL = f"https://psk.house/{PROJECT_SLUG}/"
PAGE_SIZE = 100

# Фотографии проекта (общие для всех квартир)
PROJECT_IMAGES = [
    "https://psk.house/images/projects/zhk-respect/slider/1.jpg",
    "https://psk.house/images/projects/zhk-respect/slider/2.jpg",
    "https://psk.house/images/projects/zhk-respect/slider/3.jpg",
    "https://psk.house/images/projects/zhk-respect/slider/4.jpg",
    "https://psk.house/images/projects/zhk-respect/slider/5.jpg",
]

MSK_TZ = timezone(timedelta(hours=3))


def fetch_all_flats():
    """Загрузить все квартиры из API с пагинацией."""
    all_flats = []
    offset = 0
    total = None

    while True:
        url = f"{API_BASE}&limit={PAGE_SIZE}&offset={offset}"
        print(f"  Fetching offset={offset}...", file=sys.stderr)

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if total is None:
            total = data.get("count", 0)
            print(f"  Total flats in API: {total}", file=sys.stderr)

        results = data.get("results", [])
        if not results:
            break

        all_flats.extend(results)
        offset += PAGE_SIZE

        if offset >= total:
            break

    return all_flats


def filter_respekt_flats(all_flats):
    """Отфильтровать свободные квартиры ЖК РЕСПЕКТ с ценой."""
    filtered = []
    for flat in all_flats:
        project = flat.get("project")
        if not project:
            continue

        project_id = project if isinstance(project, int) else project.get("id")
        if project_id != PROJECT_ID:
            continue

        status = flat.get("status", "")
        if status != "Свободно":
            continue

        price = flat.get("price")
        if not price or price <= 0:
            continue

        filtered.append(flat)

    return filtered


def get_rooms_info(flat):
    """Определить количество комнат и тип (студия)."""
    rooms = flat.get("rooms", 0)
    flat_type = flat.get("type", "")

    is_studio = "студи" in flat_type.lower() if flat_type else (rooms == 0)

    if is_studio:
        return 1, True
    return rooms if rooms else 1, False


def get_finishing(flat):
    """Определить тип отделки."""
    finishing = flat.get("finishing", "")
    if not finishing:
        return None

    finishing_lower = finishing.lower()
    if "чистов" in finishing_lower:
        if "пред" in finishing_lower:
            return "предчистовая отделка"
        return "чистовая отделка"
    if "без" in finishing_lower:
        return "без отделки"
    if "под ключ" in finishing_lower:
        return "под ключ"
    return finishing


def build_feed(flats):
    """Собрать XML-фид в формате YRL."""
    now = datetime.now(MSK_TZ)
    creation_date = now.strftime("%Y-%m-%dT%H:%M:%S+03:00")

    ns = "http://webmaster.yandex.ru/schemas/feed/realty/2010-06"
    ET.register_namespace("", ns)

    root = ET.Element(f"{{{ns}}}realty-feed")
    gen_date = ET.SubElement(root, "generation-date")
    gen_date.text = creation_date

    for flat in flats:
        flat_id = flat.get("id")
        if not flat_id:
            continue

        rooms, is_studio = get_rooms_info(flat)
        area = flat.get("area", 0)
        floor = flat.get("floor", 0)
        price = flat.get("price", 0)
        original_price = flat.get("original_price")

        # Информация о корпусе
        building = flat.get("building", {})
        if isinstance(building, dict):
            building_name = building.get("name", "")
            max_floor = building.get("max_floor", building.get("floors", 0))
            completion_year = building.get("completion_year", 0)
            completion_quarter = building.get("completion_quarter", 0)
        else:
            building_name = str(building) if building else ""
            max_floor = flat.get("max_floor", 0)
            completion_year = flat.get("completion_year", 0)
            completion_quarter = flat.get("completion_quarter", 0)

        offer = ET.SubElement(root, "offer", attrib={"internal-id": str(flat_id)})

        # Основные поля
        add_text(offer, "type", "продажа")
        add_text(offer, "property-type", "жилая")
        add_text(offer, "category", "квартира")
        add_text(offer, "creation-date", creation_date)
        add_text(offer, "url", f"https://psk.house/{PROJECT_SLUG}/flat/{flat_id}/")

        # Локация
        loc = ET.SubElement(offer, "location")
        add_text(loc, "country", "Россия")
        add_text(loc, "region", "Санкт-Петербург")
        add_text(loc, "locality-name", "Санкт-Петербург")
        add_text(loc, "address", PROJECT_ADDRESS)
        metro = ET.SubElement(loc, "metro")
        add_text(metro, "name", METRO)

        # Цена
        price_el = ET.SubElement(offer, "price")
        add_text(price_el, "value", str(int(price)))
        add_text(price_el, "currency", "RUR")

        if original_price and original_price > price:
            add_text(offer, "old-price", str(int(original_price)))

        # Площадь
        area_el = ET.SubElement(offer, "area")
        add_text(area_el, "value", str(round(area, 2)))
        add_text(area_el, "unit", "кв.м")

        # Комнаты
        add_text(offer, "rooms", str(rooms))
        add_text(offer, "rooms-offered", str(rooms))
        if is_studio:
            add_text(offer, "studio", "да")

        # Этаж
        if floor:
            add_text(offer, "floor", str(floor))
        if max_floor:
            add_text(offer, "floors-total", str(max_floor))

        # Здание
        bld_label = f'ЖК «{PROJECT_NAME}»'
        if building_name:
            bld_label += f", корпус {building_name}"
        add_text(offer, "building-name", bld_label)
        add_text(offer, "building-type", BUILDING_TYPE)

        if completion_year:
            add_text(offer, "built-year", str(completion_year))
        if completion_quarter:
            add_text(offer, "ready-quarter", str(completion_quarter))

        add_text(offer, "new-flat", "да")

        # Отделка
        finishing = get_finishing(flat)
        if finishing:
            add_text(offer, "renovation", finishing)

        # Изображения
        for img_url in PROJECT_IMAGES:
            add_text(offer, "image", img_url)

        # Описание
        type_label = "Студия" if is_studio else f"{rooms}-комн. квартира"
        desc_parts = [
            f"{type_label}, {round(area, 2)} кв.м",
            f"Этаж {floor}/{max_floor}" if floor and max_floor else "",
            f"корпус {building_name}" if building_name else "",
        ]
        desc_line1 = ", ".join([p for p in desc_parts if p]) + "."

        desc = (
            f"{desc_line1} "
            f"ЖК «{PROJECT_NAME}» — комфорт-класс на Полюстровском проспекте, "
            f"рядом с метро {METRO}. Монолитный дом, сдача "
            f"{completion_quarter} кв. {completion_year} г."
        )
        if original_price and original_price > price:
            discount_pct = round((1 - price / original_price) * 100)
            desc += f" Скидка {discount_pct}%!"

        add_text(offer, "description", desc)

        # Агент
        agent = ET.SubElement(offer, "sales-agent")
        add_text(agent, "organization", AGENT_ORG)
        add_text(agent, "category", "застройщик")
        add_text(agent, "url", AGENT_URL)

    return root


def add_text(parent, tag, text):
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def prettify_xml(root):
    """Форматирование XML с отступами."""
    rough = ET.tostring(root, encoding="unicode", xml_declaration=False)
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding=None)
    # Remove extra xml declaration from minidom
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    return declaration + "\n".join(lines)


def main():
    output_file = os.environ.get("OUTPUT_FILE", "respekt_yandex_direct_feed.xml")

    print("=== Генерация фида ЖК РЕСПЕКТ для Яндекс Директ ===", file=sys.stderr)

    print("1. Загрузка квартир из API...", file=sys.stderr)
    all_flats = fetch_all_flats()
    print(f"   Загружено: {len(all_flats)} квартир", file=sys.stderr)

    print("2. Фильтрация ЖК РЕСПЕКТ...", file=sys.stderr)
    respekt_flats = filter_respekt_flats(all_flats)
    print(f"   Свободных квартир с ценой: {len(respekt_flats)}", file=sys.stderr)

    if not respekt_flats:
        print("ОШИБКА: Нет квартир для фида!", file=sys.stderr)
        sys.exit(1)

    print("3. Генерация XML...", file=sys.stderr)
    feed = build_feed(respekt_flats)

    print(f"4. Сохранение в {output_file}...", file=sys.stderr)
    xml_str = prettify_xml(feed)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)

    file_size = os.path.getsize(output_file)
    print(f"   Готово! {len(respekt_flats)} квартир, {file_size:,} байт", file=sys.stderr)

    # Статистика
    from collections import Counter
    rooms_count = Counter()
    for flat in respekt_flats:
        rooms, is_studio = get_rooms_info(flat)
        label = "Студии" if is_studio else f"{rooms}-комн."
        rooms_count[label] += 1
    print("\n   Статистика:", file=sys.stderr)
    for label, count in sorted(rooms_count.items()):
        print(f"     {label}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
