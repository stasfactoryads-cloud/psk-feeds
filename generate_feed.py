#!/usr/bin/env python3
"""
Генератор XML-фидов для Яндекс Директ (товарная кампания).
Формат: YRL (Yandex Realty Language).
Источник данных: https://psk-info.ru/api/flats/?format=json

Поддерживаемые проекты: весь портфель ГК ПСК (кроме ЖК Friends).
Генерирует индивидуальные фиды по проектам + единый фид pskall.
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
from collections import Counter
import sys
import os

# === Конфигурация проектов ===
# Структура API (list endpoint):
#   id, type, status, number, rooms, price, original_price, area,
#   project (int), project_name, project_slug, project_class,
#   building (str - номер корпуса), max_floor (int),
#   floor, completion_year, completion_quarter, section,
#   plan (URL планировки SVG), floor_plan (URL этажа SVG),
#   finishing, tags, discount, ...

PROJECTS = {
    2: {
        "name": "Ladozhsky AVENIR",
        "slug": "ladozhsky",
        "address": "г. Санкт-Петербург, Магнитогорская улица, 51 литера 3",
        "metro": "Ладожская",
        "building_class": "бизнес",
        "building_type": "монолитный",
        "output_file": "ladozhsky_yandex_direct_feed.xml",
    },
    22: {
        "name": "Северная корона",
        "slug": "korona",
        "address": "г. Санкт-Петербург, наб. Реки Карповки, 31Б",
        "metro": "Петроградская",
        "building_class": "премиум",
        "building_type": "монолитный",
        "output_file": "korona_yandex_direct_feed.xml",
    },
    23: {
        "name": "Северная корона Apartments",
        "slug": "korona_apart",
        "address": "г. Санкт-Петербург, наб. Реки Карповки, 31",
        "metro": "Петроградская",
        "building_class": "премиум",
        "building_type": "монолитный",
        "output_file": "korona_apart_yandex_direct_feed.xml",
    },
    30: {
        "name": "BAKUNINA 33",
        "slug": "bakunina33",
        "address": "г. Санкт-Петербург, проспект Бакунина, 33",
        "metro": "Площадь Александра Невского",
        "building_class": "бизнес",
        "building_type": "монолитный",
        "output_file": "bakunina33_yandex_direct_feed.xml",
    },
    32: {
        "name": "ПЛЮС Пулковский",
        "slug": "plus-pulkovskij",
        "address": "г. Санкт-Петербург, Пулковское шоссе / Волхонское шоссе",
        "metro": "Московская",
        "building_class": "комфорт",
        "building_type": "монолитный",
        "output_file": "plus_pulkovskij_yandex_direct_feed.xml",
    },
    39: {
        "name": "РЕСПЕКТ",
        "slug": "zhk-respect",
        "address": "г. Санкт-Петербург, Полюстровский проспект, 87",
        "metro": "Лесная",
        "building_class": "комфорт",
        "building_type": "монолитный",
        "output_file": "respekt_yandex_direct_feed.xml",
    },
    40: {
        "name": "Industrial AVENIR",
        "slug": "industrial-avenir",
        "address": "г. Санкт-Петербург, пр. Стачек, 62, литера А",
        "metro": "Кировский Завод",
        "building_class": "комфорт",
        "building_type": "монолитный",
        "output_file": "industrial_avenir_yandex_direct_feed.xml",
    },
    41: {
        "name": "Ассамблея",
        "slug": "assambleya-klubnyj-kvartal",
        "address": "г. Санкт-Петербург, Средний проспект Васильевского острова, 60",
        "metro": "Горный институт",
        "building_class": "бизнес",
        "building_type": "монолитный",
        "output_file": "assambleya_yandex_direct_feed.xml",
    },
    42: {
        "name": "Галерная гавань",
        "slug": "galernaya-gavan",
        "address": "г. Санкт-Петербург, ул. Шкиперский проток, 16-18",
        "metro": "Приморская",
        "building_class": "бизнес",
        "building_type": "монолитный",
        "output_file": "galernaya_gavan_yandex_direct_feed.xml",
    },
    43: {
        "name": "СЕЗОНЫ",
        "slug": "sezony-vidovoj-kompleks",
        "address": "г. Санкт-Петербург, Суздальское шоссе, уч. 26",
        "metro": "Проспект Просвещения",
        "building_class": "комфорт",
        "building_type": "монолитный",
        "output_file": "sezony_yandex_direct_feed.xml",
    },
    44: {
        "name": "Акватория",
        "slug": "akvatoriya-premialnyj-dom",
        "address": "г. Санкт-Петербург, Выборгская набережная, 61",
        "metro": "Петроградская",
        "building_class": "премиум",
        "building_type": "монолитный",
        "output_file": "akvatoriya_yandex_direct_feed.xml",
    },
    45: {
        "name": "ОПТИМИСТ",
        "slug": "optimist-zhiloj-kompleks",
        "address": "г. Санкт-Петербург, ул. Фучика, дом 21",
        "metro": "Бухарестская",
        "building_class": "бизнес",
        "building_type": "монолитный",
        "output_file": "optimist_yandex_direct_feed.xml",
    },
}

# ЖК Friends (ID=20) исключён из генерации

PSKALL_OUTPUT = "pskall_yandex_direct_feed.xml"

API_BASE = "https://psk-info.ru/api/flats/?format=json"
SITE_DOMAIN = "https://psk-info.ru"
PAGE_SIZE = 100
AGENT_ORG = "Группа компаний ПСК"
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


def filter_project_flats(all_flats, project_id):
    """Отфильтровать свободные квартиры проекта с ценой."""
    filtered = []
    for flat in all_flats:
        pid = flat.get("project")
        if pid != project_id:
            continue

        status = flat.get("status", "")
        if status != "Свободно":
            continue

        price = flat.get("price")
        if not price or price <= 0:
            continue

        filtered.append(flat)

    return filtered


def filter_all_flats_except(all_flats, exclude_ids):
    """Отфильтровать свободные квартиры по всем проектам кроме исключённых."""
    filtered = []
    for flat in all_flats:
        pid = flat.get("project")
        if pid in exclude_ids:
            continue
        if pid not in PROJECTS:
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
    if "с отделк" in finishing_lower:
        return "чистовая отделка"
    return finishing


def get_project_config_for_flat(flat):
    """Получить конфигурацию проекта для конкретной квартиры."""
    pid = flat.get("project")
    return PROJECTS.get(pid)


def build_feed(flats, project_config):
    """Собрать XML-фид в формате YRL для конкретного проекта."""
    now = datetime.now(MSK_TZ)
    creation_date = now.strftime("%Y-%m-%dT%H:%M:%S+03:00")

    ns = "http://webmaster.yandex.ru/schemas/feed/realty/2010-06"
    ET.register_namespace("", ns)

    root = ET.Element(f"{{{ns}}}realty-feed")
    gen_date = ET.SubElement(root, "generation-date")
    gen_date.text = creation_date

    slug = project_config["slug"]
    name = project_config["name"]
    address = project_config["address"]
    metro_name = project_config["metro"]
    building_class = project_config["building_class"]
    building_type = project_config["building_type"]
    agent_url = f"{SITE_DOMAIN}/projects/{slug}"

    for flat in flats:
        flat_id = flat.get("id")
        if not flat_id:
            continue

        rooms, is_studio = get_rooms_info(flat)
        area = flat.get("area", 0)
        floor = flat.get("floor", 0)
        price = flat.get("price", 0)
        original_price = flat.get("original_price")

        building_name = flat.get("building", "")
        if building_name and not isinstance(building_name, str):
            building_name = str(building_name)
        max_floor = flat.get("max_floor", 0)
        completion_year = flat.get("completion_year", 0)
        completion_quarter = flat.get("completion_quarter", 0)

        offer = ET.SubElement(root, "offer", attrib={"internal-id": str(flat_id)})

        add_text(offer, "type", "продажа")
        add_text(offer, "property-type", "жилая")
        add_text(offer, "category", "квартира")
        add_text(offer, "creation-date", creation_date)
        add_text(offer, "url", f"{SITE_DOMAIN}/flats/{flat_id}")

        loc = ET.SubElement(offer, "location")
        add_text(loc, "country", "Россия")
        add_text(loc, "region", "Санкт-Петербург")
        add_text(loc, "locality-name", "Санкт-Петербург")
        add_text(loc, "address", address)
        metro = ET.SubElement(loc, "metro")
        add_text(metro, "name", metro_name)

        price_el = ET.SubElement(offer, "price")
        add_text(price_el, "value", str(int(price)))
        add_text(price_el, "currency", "RUR")

        if original_price and float(original_price) > price:
            add_text(offer, "old-price", str(int(float(original_price))))

        area_el = ET.SubElement(offer, "area")
        add_text(area_el, "value", str(round(area, 2)))
        add_text(area_el, "unit", "кв.м")

        add_text(offer, "rooms", str(rooms))
        add_text(offer, "rooms-offered", str(rooms))
        if is_studio:
            add_text(offer, "studio", "да")

        if floor:
            add_text(offer, "floor", str(floor))
        if max_floor:
            add_text(offer, "floors-total", str(max_floor))

        bld_label = f'ЖК «{name}»'
        if building_name:
            bld_label += f", корпус {building_name}"
        add_text(offer, "building-name", bld_label)
        add_text(offer, "building-type", building_type)

        if completion_year:
            add_text(offer, "built-year", str(completion_year))
        if completion_quarter:
            add_text(offer, "ready-quarter", str(completion_quarter))

        add_text(offer, "new-flat", "да")

        finishing = get_finishing(flat)
        if finishing:
            add_text(offer, "renovation", finishing)

        plan_url = flat.get("plan", "")
        if plan_url:
            add_text(offer, "image", plan_url)

        floor_plan_url = flat.get("floor_plan", "")
        if floor_plan_url:
            add_text(offer, "image", floor_plan_url)

        type_label = "Студия" if is_studio else f"{rooms}-комн. квартира"
        desc_parts = [
            f"{type_label}, {round(area, 2)} кв.м",
            f"Этаж {floor}/{max_floor}" if floor and max_floor else "",
            f"корпус {building_name}" if building_name else "",
        ]
        desc_line1 = ", ".join([p for p in desc_parts if p]) + "."

        desc = (
            f"{desc_line1} "
            f"ЖК «{name}» — {building_class}-класс, "
            f"рядом с метро {metro_name}. {building_type.capitalize()} дом"
        )
        if completion_quarter and completion_year:
            desc += f", сдача {completion_quarter} кв. {completion_year} г."
        else:
            desc += "."

        if original_price and float(original_price) > price:
            discount_pct = round((1 - price / float(original_price)) * 100)
            if discount_pct > 0:
                desc += f" Скидка {discount_pct}%!"

        add_text(offer, "description", desc)

        agent = ET.SubElement(offer, "sales-agent")
        add_text(agent, "organization", AGENT_ORG)
        add_text(agent, "category", "застройщик")
        add_text(agent, "url", agent_url)

    return root


def build_combined_feed(flats):
    """Собрать единый XML-фид по всем проектам (pskall)."""
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

        config = get_project_config_for_flat(flat)
        if not config:
            continue

        slug = config["slug"]
        name = config["name"]
        address = config["address"]
        metro_name = config["metro"]
        building_class = config["building_class"]
        building_type = config["building_type"]
        agent_url = f"{SITE_DOMAIN}/projects/{slug}"

        rooms, is_studio = get_rooms_info(flat)
        area = flat.get("area", 0)
        floor = flat.get("floor", 0)
        price = flat.get("price", 0)
        original_price = flat.get("original_price")

        building_name = flat.get("building", "")
        if building_name and not isinstance(building_name, str):
            building_name = str(building_name)
        max_floor = flat.get("max_floor", 0)
        completion_year = flat.get("completion_year", 0)
        completion_quarter = flat.get("completion_quarter", 0)

        offer = ET.SubElement(root, "offer", attrib={"internal-id": str(flat_id)})

        add_text(offer, "type", "продажа")
        add_text(offer, "property-type", "жилая")
        add_text(offer, "category", "квартира")
        add_text(offer, "creation-date", creation_date)
        add_text(offer, "url", f"{SITE_DOMAIN}/flats/{flat_id}")

        loc = ET.SubElement(offer, "location")
        add_text(loc, "country", "Россия")
        add_text(loc, "region", "Санкт-Петербург")
        add_text(loc, "locality-name", "Санкт-Петербург")
        add_text(loc, "address", address)
        metro = ET.SubElement(loc, "metro")
        add_text(metro, "name", metro_name)

        price_el = ET.SubElement(offer, "price")
        add_text(price_el, "value", str(int(price)))
        add_text(price_el, "currency", "RUR")

        if original_price and float(original_price) > price:
            add_text(offer, "old-price", str(int(float(original_price))))

        area_el = ET.SubElement(offer, "area")
        add_text(area_el, "value", str(round(area, 2)))
        add_text(area_el, "unit", "кв.м")

        add_text(offer, "rooms", str(rooms))
        add_text(offer, "rooms-offered", str(rooms))
        if is_studio:
            add_text(offer, "studio", "да")

        if floor:
            add_text(offer, "floor", str(floor))
        if max_floor:
            add_text(offer, "floors-total", str(max_floor))

        bld_label = f'ЖК «{name}»'
        if building_name:
            bld_label += f", корпус {building_name}"
        add_text(offer, "building-name", bld_label)
        add_text(offer, "building-type", building_type)

        if completion_year:
            add_text(offer, "built-year", str(completion_year))
        if completion_quarter:
            add_text(offer, "ready-quarter", str(completion_quarter))

        add_text(offer, "new-flat", "да")

        finishing = get_finishing(flat)
        if finishing:
            add_text(offer, "renovation", finishing)

        plan_url = flat.get("plan", "")
        if plan_url:
            add_text(offer, "image", plan_url)

        floor_plan_url = flat.get("floor_plan", "")
        if floor_plan_url:
            add_text(offer, "image", floor_plan_url)

        type_label = "Студия" if is_studio else f"{rooms}-комн. квартира"
        desc_parts = [
            f"{type_label}, {round(area, 2)} кв.м",
            f"Этаж {floor}/{max_floor}" if floor and max_floor else "",
            f"корпус {building_name}" if building_name else "",
        ]
        desc_line1 = ", ".join([p for p in desc_parts if p]) + "."

        desc = (
            f"{desc_line1} "
            f"ЖК «{name}» — {building_class}-класс, "
            f"рядом с метро {metro_name}. {building_type.capitalize()} дом"
        )
        if completion_quarter and completion_year:
            desc += f", сдача {completion_quarter} кв. {completion_year} г."
        else:
            desc += "."

        if original_price and float(original_price) > price:
            discount_pct = round((1 - price / float(original_price)) * 100)
            if discount_pct > 0:
                desc += f" Скидка {discount_pct}%!"

        add_text(offer, "description", desc)

        agent = ET.SubElement(offer, "sales-agent")
        add_text(agent, "organization", AGENT_ORG)
        add_text(agent, "category", "застройщик")
        add_text(agent, "url", agent_url)

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
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    return declaration + "\n".join(lines)


def generate_project_feed(all_flats, project_id, project_config):
    """Сгенерировать фид для одного проекта."""
    name = project_config["name"]
    output_file = project_config["output_file"]

    print(f"\n--- ЖК {name} (ID={project_id}) ---", file=sys.stderr)

    flats = filter_project_flats(all_flats, project_id)
    print(f"  Свободных квартир с ценой: {len(flats)}", file=sys.stderr)

    if not flats:
        print(f"  ВНИМАНИЕ: Нет квартир для ЖК {name}, пропускаем", file=sys.stderr)
        return 0

    feed = build_feed(flats, project_config)
    xml_str = prettify_xml(feed)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)

    file_size = os.path.getsize(output_file)
    print(f"  Сохранено: {output_file} ({len(flats)} квартир, {file_size:,} байт)", file=sys.stderr)

    rooms_count = Counter()
    for flat in flats:
        rooms, is_studio = get_rooms_info(flat)
        label = "Студии" if is_studio else f"{rooms}-комн."
        rooms_count[label] += 1
    for label, count in sorted(rooms_count.items()):
        print(f"    {label}: {count}", file=sys.stderr)

    return len(flats)


def generate_pskall_feed(all_flats):
    """Сгенерировать единый фид pskall по всем проектам (кроме исключённых)."""
    print(f"\n--- ЕДИНЫЙ ФИД pskall ---", file=sys.stderr)

    # Friends (ID=20) исключён
    exclude_ids = {20}
    flats = filter_all_flats_except(all_flats, exclude_ids)
    print(f"  Свободных квартир с ценой (все проекты): {len(flats)}", file=sys.stderr)

    if not flats:
        print(f"  ВНИМАНИЕ: Нет квартир для pskall, пропускаем", file=sys.stderr)
        return 0

    feed = build_combined_feed(flats)
    xml_str = prettify_xml(feed)

    with open(PSKALL_OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml_str)

    file_size = os.path.getsize(PSKALL_OUTPUT)
    print(f"  Сохранено: {PSKALL_OUTPUT} ({len(flats)} квартир, {file_size:,} байт)", file=sys.stderr)

    # Статистика по проектам
    project_count = Counter()
    rooms_count = Counter()
    for flat in flats:
        pid = flat.get("project")
        config = PROJECTS.get(pid)
        if config:
            project_count[config["name"]] += 1
        rooms, is_studio = get_rooms_info(flat)
        label = "Студии" if is_studio else f"{rooms}-комн."
        rooms_count[label] += 1

    print(f"  По проектам:", file=sys.stderr)
    for name, count in sorted(project_count.items(), key=lambda x: -x[1]):
        print(f"    {name}: {count}", file=sys.stderr)
    print(f"  По комнатам:", file=sys.stderr)
    for label, count in sorted(rooms_count.items()):
        print(f"    {label}: {count}", file=sys.stderr)

    return len(flats)


def main():
    print("=== Генерация фидов ГК ПСК для Яндекс Директ ===", file=sys.stderr)

    print("\n1. Загрузка квартир из API...", file=sys.stderr)
    all_flats = fetch_all_flats()
    print(f"   Загружено: {len(all_flats)} квартир всего", file=sys.stderr)

    print("\n2. Генерация фидов по проектам...", file=sys.stderr)
    total_flats = 0
    total_feeds = 0

    for project_id, config in PROJECTS.items():
        count = generate_project_feed(all_flats, project_id, config)
        if count > 0:
            total_flats += count
            total_feeds += 1

    print("\n3. Генерация единого фида pskall...", file=sys.stderr)
    pskall_count = generate_pskall_feed(all_flats)
    if pskall_count > 0:
        total_feeds += 1

    print(f"\n=== Итого: {total_feeds} фидов, {total_flats} квартир (по проектам) + {pskall_count} (pskall) ===", file=sys.stderr)

    if total_feeds == 0:
        print("ОШИБКА: Ни один фид не сгенерирован!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
