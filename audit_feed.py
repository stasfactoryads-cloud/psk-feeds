#!/usr/bin/env python3
"""
Аудит XML-фидов ЖК ПСК для Яндекс Директ.
Проверяет и исправляет типичные ошибки в YRL-фидах.

Запуск:
  python audit_feed.py                    # проверка всех фидов
  python audit_feed.py --fix              # проверка + автоисправление
  python audit_feed.py feed.xml           # проверка конкретного файла
  python audit_feed.py feed.xml --fix     # проверка + исправление конкретного файла
"""

import xml.etree.ElementTree as ET
import json
import urllib.request
import sys
import os
import re
from datetime import datetime, timezone, timedelta

# === Конфигурация ===
FEED_FILES = [
    "respekt_yandex_direct_feed.xml",
    "optimist_yandex_direct_feed.xml",
    "sezony_yandex_direct_feed.xml",
]

VALID_PROJECT_SLUGS = {
    "zhk-respect": "РЕСПЕКТ",
    "optimist-zhiloj-kompleks": "ОПТИМИСТ",
    "sezony-vidovoj-kompleks": "СЕЗОНЫ",
}

SITE_DOMAIN = "psk-info.ru"
IMAGE_DOMAIN = "storage.yandexcloud.net"
IMAGE_BASE = f"https://{IMAGE_DOMAIN}/psk-media/media/"

# Правильные форматы URL
CORRECT_FLAT_URL = f"https://{SITE_DOMAIN}/flats/{{flat_id}}"
CORRECT_PROJECT_URL = f"https://{SITE_DOMAIN}/projects/{{slug}}"

YRL_NS = "http://webmaster.yandex.ru/schemas/feed/realty/2010-06"

MSK_TZ = timezone(timedelta(hours=3))


class AuditResult:
    def __init__(self, filename):
        self.filename = filename
        self.errors = []
        self.warnings = []
        self.fixes = []
        self.stats = {}

    def error(self, offer_id, field, message):
        self.errors.append({"offer_id": offer_id, "field": field, "message": message})

    def warning(self, offer_id, field, message):
        self.warnings.append({"offer_id": offer_id, "field": field, "message": message})

    def fix(self, offer_id, field, old_val, new_val):
        self.fixes.append({
            "offer_id": offer_id,
            "field": field,
            "old": old_val,
            "new": new_val,
        })

    def summary(self):
        lines = [f"\n{'='*60}", f"АУДИТ: {self.filename}", f"{'='*60}"]

        if self.stats:
            lines.append(f"\nСтатистика:")
            for k, v in self.stats.items():
                lines.append(f"  {k}: {v}")

        if self.errors:
            lines.append(f"\n❌ ОШИБКИ ({len(self.errors)}):")
            for e in self.errors:
                oid = f"[offer {e['offer_id']}] " if e["offer_id"] else ""
                lines.append(f"  {oid}{e['field']}: {e['message']}")

        if self.warnings:
            lines.append(f"\n⚠️  ПРЕДУПРЕЖДЕНИЯ ({len(self.warnings)}):")
            for w in self.warnings:
                oid = f"[offer {w['offer_id']}] " if w["offer_id"] else ""
                lines.append(f"  {oid}{w['field']}: {w['message']}")

        if self.fixes:
            lines.append(f"\n✅ ИСПРАВЛЕНИЯ ({len(self.fixes)}):")
            for f in self.fixes:
                oid = f"[offer {f['offer_id']}] " if f["offer_id"] else ""
                lines.append(f"  {oid}{f['field']}: {f['old']} → {f['new']}")

        if not self.errors and not self.warnings:
            lines.append("\n✅ Всё в порядке!")

        return "\n".join(lines)


def find_element(parent, tag):
    """Найти элемент по тегу (с учётом namespace)."""
    el = parent.find(tag)
    if el is None:
        el = parent.find(f"{{{YRL_NS}}}{tag}")
    return el


def find_all_elements(parent, tag):
    """Найти все элементы по тегу (с учётом namespace)."""
    els = parent.findall(tag)
    if not els:
        els = parent.findall(f"{{{YRL_NS}}}{tag}")
    return els


def get_text(parent, tag):
    """Получить текст элемента."""
    el = find_element(parent, tag)
    return el.text if el is not None and el.text else ""


def set_text(parent, tag, value):
    """Установить текст элемента."""
    el = find_element(parent, tag)
    if el is not None:
        el.text = value


def audit_url(result, offer_id, url_text, do_fix, offer_el):
    """Проверить URL квартиры."""
    if not url_text:
        result.error(offer_id, "url", "URL отсутствует")
        return

    # Проверка 1: Домен должен быть psk-info.ru
    wrong_domains = ["psk.house", "psk-house.ru", "psk.ru"]
    for wrong in wrong_domains:
        if wrong in url_text:
            result.error(offer_id, "url", f"Неверный домен: {wrong}")
            if do_fix:
                new_url = url_text.replace(wrong, SITE_DOMAIN)
                set_text(offer_el, "url", new_url)
                result.fix(offer_id, "url", url_text, new_url)
                url_text = new_url

    # Проверка 2: Формат URL должен быть /flats/{id}
    # Неверные форматы: /{slug}/flat/{id}/, /{slug}/flats/{id}/
    bad_patterns = [
        (r"https?://[^/]+/[a-z0-9_-]+/flat/(\d+)/?", "/{slug}/flat/{id}"),
        (r"https?://[^/]+/[a-z0-9_-]+/flats/(\d+)/?", "/{slug}/flats/{id}"),
    ]
    for pattern, desc in bad_patterns:
        m = re.match(pattern, url_text)
        if m:
            flat_id = m.group(1)
            correct = CORRECT_FLAT_URL.format(flat_id=flat_id)
            result.error(offer_id, "url", f"Неверный формат URL ({desc}), должен быть /flats/{{id}}")
            if do_fix:
                set_text(offer_el, "url", correct)
                result.fix(offer_id, "url", url_text, correct)
                url_text = correct

    # Проверка 3: URL должен содержать /flats/ и ID
    if f"{SITE_DOMAIN}/flats/" not in url_text:
        flat_id_match = re.search(r"/(\d+)/?$", url_text)
        if flat_id_match:
            flat_id = flat_id_match.group(1)
            correct = CORRECT_FLAT_URL.format(flat_id=flat_id)
            result.error(offer_id, "url", f"URL не содержит /flats/")
            if do_fix:
                set_text(offer_el, "url", correct)
                result.fix(offer_id, "url", url_text, correct)

    # Проверка 4: URL не должен заканчиваться на /
    # (для Яндекс Директ оба варианта допустимы, но единообразие лучше)


def audit_images(result, offer_id, offer_el, do_fix):
    """Проверить изображения."""
    images = find_all_elements(offer_el, "image")

    if not images:
        result.warning(offer_id, "image", "Нет изображений")
        return

    for i, img in enumerate(images):
        img_url = img.text if img.text else ""

        if not img_url:
            result.error(offer_id, f"image[{i}]", "Пустой URL изображения")
            continue

        # Проверка: изображения НЕ должны ссылаться на несуществующий домен
        wrong_image_domains = ["psk.house", "psk-info.ru/images/"]
        for wrong in wrong_image_domains:
            if wrong in img_url:
                result.error(
                    offer_id,
                    f"image[{i}]",
                    f"Изображение на несуществующем пути ({wrong}): {img_url}",
                )
                # Удалить битые картинки если fix
                if do_fix:
                    offer_el.remove(img)
                    result.fix(offer_id, f"image[{i}]", img_url, "[удалён — битая ссылка]")

        # Проверка: допустимые домены для изображений
        valid_image_hosts = [
            "storage.yandexcloud.net",
            "cdn.psk.idacloud.ru",
        ]
        if not any(host in img_url for host in valid_image_hosts):
            if "psk-info.ru" not in img_url and "psk.house" not in img_url:
                result.warning(
                    offer_id,
                    f"image[{i}]",
                    f"Нестандартный домен изображения: {img_url}",
                )


def audit_price(result, offer_id, offer_el):
    """Проверить цену."""
    price_el = find_element(offer_el, "price")
    if price_el is None:
        result.error(offer_id, "price", "Цена отсутствует")
        return

    value = get_text(price_el, "value")
    currency = get_text(price_el, "currency")

    if not value:
        result.error(offer_id, "price/value", "Значение цены отсутствует")
    else:
        try:
            price_int = int(value)
            if price_int <= 0:
                result.error(offer_id, "price/value", f"Цена <= 0: {price_int}")
            elif price_int < 1_000_000:
                result.warning(offer_id, "price/value", f"Подозрительно низкая цена: {price_int}")
            elif price_int > 500_000_000:
                result.warning(offer_id, "price/value", f"Подозрительно высокая цена: {price_int}")
        except ValueError:
            result.error(offer_id, "price/value", f"Цена не число: {value}")

    if not currency:
        result.error(offer_id, "price/currency", "Валюта не указана")
    elif currency not in ("RUR", "RUB", "USD", "EUR"):
        result.error(offer_id, "price/currency", f"Неизвестная валюта: {currency}")

    # Проверка old-price
    old_price_text = get_text(offer_el, "old-price")
    if old_price_text:
        try:
            old_price = int(old_price_text)
            current_price = int(value) if value else 0
            if old_price <= current_price:
                result.warning(
                    offer_id,
                    "old-price",
                    f"Старая цена ({old_price}) <= текущей ({current_price})",
                )
            elif old_price > current_price * 3:
                result.warning(
                    offer_id,
                    "old-price",
                    f"Старая цена ({old_price}) > 3x текущей ({current_price})",
                )
        except ValueError:
            result.error(offer_id, "old-price", f"Старая цена не число: {old_price_text}")


def audit_area(result, offer_id, offer_el):
    """Проверить площадь."""
    area_el = find_element(offer_el, "area")
    if area_el is None:
        result.error(offer_id, "area", "Площадь отсутствует")
        return

    value = get_text(area_el, "value")
    unit = get_text(area_el, "unit")

    if not value:
        result.error(offer_id, "area/value", "Значение площади отсутствует")
    else:
        try:
            area_val = float(value)
            if area_val <= 0:
                result.error(offer_id, "area/value", f"Площадь <= 0: {area_val}")
            elif area_val < 10:
                result.warning(offer_id, "area/value", f"Подозрительно малая площадь: {area_val}")
            elif area_val > 500:
                result.warning(offer_id, "area/value", f"Подозрительно большая площадь: {area_val}")
        except ValueError:
            result.error(offer_id, "area/value", f"Площадь не число: {value}")

    if unit and unit != "кв.м":
        result.warning(offer_id, "area/unit", f"Нестандартная единица: {unit}")


def audit_rooms(result, offer_id, offer_el):
    """Проверить комнаты."""
    rooms = get_text(offer_el, "rooms")
    rooms_offered = get_text(offer_el, "rooms-offered")
    is_studio = get_text(offer_el, "studio") == "да"

    if not rooms:
        result.error(offer_id, "rooms", "Количество комнат отсутствует")
    else:
        try:
            r = int(rooms)
            if r < 1 or r > 10:
                result.warning(offer_id, "rooms", f"Необычное количество комнат: {r}")
            if is_studio and r != 1:
                result.warning(offer_id, "rooms", f"Студия, но rooms={r} (ожидается 1)")
        except ValueError:
            result.error(offer_id, "rooms", f"Комнаты не число: {rooms}")

    if rooms_offered and rooms and rooms_offered != rooms:
        result.warning(
            offer_id,
            "rooms-offered",
            f"rooms-offered ({rooms_offered}) != rooms ({rooms})",
        )


def audit_floor(result, offer_id, offer_el):
    """Проверить этаж."""
    floor = get_text(offer_el, "floor")
    floors_total = get_text(offer_el, "floors-total")

    if floor:
        try:
            f = int(floor)
            if f < 1:
                result.error(offer_id, "floor", f"Этаж < 1: {f}")
            if floors_total:
                ft = int(floors_total)
                if f > ft:
                    result.error(
                        offer_id,
                        "floor",
                        f"Этаж ({f}) > этажность ({ft})",
                    )
        except ValueError:
            result.error(offer_id, "floor", f"Этаж не число: {floor}")


def audit_required_fields(result, offer_id, offer_el):
    """Проверить обязательные поля YRL."""
    required = [
        "type", "property-type", "category", "url",
        "price", "area", "rooms", "creation-date",
    ]
    for field in required:
        val = get_text(offer_el, field)
        el = find_element(offer_el, field)
        if el is None and not val:
            result.error(offer_id, field, "Обязательное поле отсутствует")

    # Проверка location
    loc = find_element(offer_el, "location")
    if loc is None:
        result.error(offer_id, "location", "Блок location отсутствует")
    else:
        for loc_field in ["country", "region", "address"]:
            if not get_text(loc, loc_field):
                result.error(offer_id, f"location/{loc_field}", "Поле отсутствует")

    # Проверка sales-agent
    agent = find_element(offer_el, "sales-agent")
    if agent is None:
        result.warning(offer_id, "sales-agent", "Блок sales-agent отсутствует")
    else:
        if not get_text(agent, "organization"):
            result.warning(offer_id, "sales-agent/organization", "Организация не указана")

    # Проверка sales-agent URL
    if agent is not None:
        agent_url = get_text(agent, "url")
        if agent_url:
            wrong_domains = ["psk.house"]
            for wrong in wrong_domains:
                if wrong in agent_url:
                    result.error(
                        offer_id,
                        "sales-agent/url",
                        f"Неверный домен агента: {wrong}",
                    )


def audit_agent_url(result, offer_id, offer_el, do_fix):
    """Проверить и исправить URL агента."""
    agent = find_element(offer_el, "sales-agent")
    if agent is None:
        return

    agent_url_el = find_element(agent, "url")
    if agent_url_el is None or not agent_url_el.text:
        return

    url = agent_url_el.text

    # Исправить домен
    wrong_domains = ["psk.house"]
    for wrong in wrong_domains:
        if wrong in url:
            if do_fix:
                # Формат: https://psk-info.ru/projects/{slug}
                slug_match = re.search(r"//[^/]+/([a-z0-9_-]+)/?$", url)
                if slug_match:
                    slug = slug_match.group(1)
                    new_url = CORRECT_PROJECT_URL.format(slug=slug)
                    agent_url_el.text = new_url
                    result.fix(offer_id, "sales-agent/url", url, new_url)
                else:
                    new_url = url.replace(wrong, SITE_DOMAIN)
                    agent_url_el.text = new_url
                    result.fix(offer_id, "sales-agent/url", url, new_url)


def audit_description(result, offer_id, offer_el):
    """Проверить описание."""
    desc = get_text(offer_el, "description")
    if not desc:
        result.warning(offer_id, "description", "Описание отсутствует")
        return

    if len(desc) < 30:
        result.warning(offer_id, "description", f"Слишком короткое описание ({len(desc)} символов)")
    if len(desc) > 3000:
        result.warning(offer_id, "description", f"Слишком длинное описание ({len(desc)} символов)")

    # Проверка на мусор
    if "None" in desc or "null" in desc.lower():
        result.warning(offer_id, "description", "Описание содержит None/null")
    if "0 кв. 0 г." in desc:
        result.warning(offer_id, "description", "Описание содержит '0 кв. 0 г.' (нет данных о сдаче)")


def audit_xml_structure(result, tree, root):
    """Проверить общую структуру XML."""
    # Проверка generation-date
    gen_date = find_element(root, "generation-date")
    if gen_date is None or not gen_date.text:
        result.error(None, "generation-date", "Дата генерации отсутствует")
    else:
        try:
            dt = datetime.fromisoformat(gen_date.text)
            now = datetime.now(MSK_TZ)
            age_days = (now - dt).days
            if age_days > 3:
                result.warning(None, "generation-date", f"Фид устарел на {age_days} дней")
        except (ValueError, TypeError):
            result.warning(None, "generation-date", f"Не удалось распарсить дату: {gen_date.text}")

    # Подсчёт offers
    offers = find_all_elements(root, "offer")
    result.stats["Количество предложений"] = len(offers)

    if len(offers) == 0:
        result.error(None, "offers", "Фид пуст — нет ни одного предложения")

    # Проверка уникальности internal-id
    ids = [o.get("internal-id") for o in offers]
    dupes = [x for x in set(ids) if ids.count(x) > 1]
    if dupes:
        result.error(None, "internal-id", f"Дублирующиеся ID: {', '.join(dupes[:10])}")


def audit_feed(filename, do_fix=False):
    """Полный аудит одного файла фида."""
    result = AuditResult(filename)

    if not os.path.exists(filename):
        result.error(None, "file", f"Файл не найден: {filename}")
        return result

    # Парсинг XML
    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except ET.ParseError as e:
        result.error(None, "xml", f"Ошибка парсинга XML: {e}")
        return result

    # Общая структура
    audit_xml_structure(result, tree, root)

    # Аудит каждого offer
    offers = find_all_elements(root, "offer")
    for offer in offers:
        offer_id = offer.get("internal-id", "?")

        # URL квартиры
        url_text = get_text(offer, "url")
        audit_url(result, offer_id, url_text, do_fix, offer)

        # Изображения
        audit_images(result, offer_id, offer, do_fix)

        # Цена
        audit_price(result, offer_id, offer)

        # Площадь
        audit_area(result, offer_id, offer)

        # Комнаты
        audit_rooms(result, offer_id, offer)

        # Этаж
        audit_floor(result, offer_id, offer)

        # Обязательные поля
        audit_required_fields(result, offer_id, offer)

        # URL агента
        audit_agent_url(result, offer_id, offer, do_fix)

        # Описание
        audit_description(result, offer_id, offer)

    # Сохранение исправлений
    if do_fix and result.fixes:
        tree.write(filename, encoding="unicode", xml_declaration=True)
        result.stats["Файл перезаписан"] = "да"

    return result


def check_api_consistency(filename):
    """Проверить консистентность фида с API (опционально)."""
    result = AuditResult(f"{filename} [API]")

    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except Exception:
        return result

    offers = find_all_elements(root, "offer")
    offer_ids = {o.get("internal-id") for o in offers}

    result.stats["Квартир в фиде"] = len(offer_ids)

    # Выборочная проверка — первые 3 квартиры
    sample_ids = list(offer_ids)[:3]
    for flat_id in sample_ids:
        try:
            url = f"https://psk-info.ru/api/flats/{flat_id}/?format=json"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            api_status = data.get("status", "")
            api_price = data.get("price", 0)

            if api_status != "Свободно":
                result.warning(flat_id, "status", f"В API статус = '{api_status}', а в фиде квартира есть")
            if api_price and api_price <= 0:
                result.warning(flat_id, "price", f"В API цена = {api_price}")

        except Exception as e:
            result.warning(flat_id, "api", f"Не удалось проверить по API: {e}")

    return result


def main():
    args = sys.argv[1:]
    do_fix = "--fix" in args
    check_api = "--api" in args
    files = [a for a in args if not a.startswith("--")]

    if not files:
        files = FEED_FILES

    print("=" * 60)
    print("  АУДИТ ФИДОВ ГК ПСК — Яндекс Директ")
    print(f"  Режим: {'ПРОВЕРКА + ИСПРАВЛЕНИЕ' if do_fix else 'ТОЛЬКО ПРОВЕРКА'}")
    print(f"  Файлы: {', '.join(files)}")
    print("=" * 60)

    total_errors = 0
    total_warnings = 0
    total_fixes = 0

    for filename in files:
        result = audit_feed(filename, do_fix=do_fix)
        print(result.summary())
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)
        total_fixes += len(result.fixes)

        if check_api:
            api_result = check_api_consistency(filename)
            if api_result.warnings or api_result.errors:
                print(api_result.summary())

    # Итого
    print(f"\n{'='*60}")
    print(f"  ИТОГО:")
    print(f"    Файлов проверено: {len(files)}")
    print(f"    Ошибок: {total_errors}")
    print(f"    Предупреждений: {total_warnings}")
    if do_fix:
        print(f"    Исправлений: {total_fixes}")
    print(f"{'='*60}")

    if total_errors > 0 and not do_fix:
        print("\n  💡 Запустите с --fix для автоисправления.")

    sys.exit(1 if total_errors > 0 and not do_fix else 0)


if __name__ == "__main__":
    main()
