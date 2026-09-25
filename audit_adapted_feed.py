#!/usr/bin/env python3
"""
Аудит адаптированного фида pskall_adapted_feed.xml.

Проверки:
  1. XML-валидность (парсинг без ошибок)
  2. Наличие обязательных полей в каждом оффере
  3. Доступность URL изображений на сервере (HTTP HEAD)
  4. Уникальность internal-id
  5. Корректность описаний (не пустые, нужная длина)
  6. Общая статистика по проектам

Запуск:
  python audit_adapted_feed.py                           # аудит adapted-фида
  python audit_adapted_feed.py pskall_adapted_feed.xml   # указать файл
  python audit_adapted_feed.py --check-images            # + проверка HTTP-доступности картинок
  python audit_adapted_feed.py --check-images --sample 20  # проверить 20 случайных URL
"""

import xml.etree.ElementTree as ET
import sys
import os
import re
import hashlib
import random
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

NS = 'http://webmaster.yandex.ru/schemas/feed/realty/2010-06'
MSK = timezone(timedelta(hours=3))

# Обязательные поля YRL-оффера
REQUIRED_FIELDS = [
    'type', 'property-type', 'category', 'location/country',
    'location/locality-name', 'price/value', 'price/currency',
    'area/value', 'area/unit', 'description', 'image',
]

# Поля, которые должны быть числовыми
NUMERIC_FIELDS = ['price/value', 'area/value', 'floor', 'floors-total', 'rooms']

# Домены для проверки изображений
IMAGE_DOMAINS = {
    'feedhub.realty': 'Lifestyle/Render (feedhub.realty)',
    'psk-info.ru': 'Оригинальные планировки (psk-info.ru)',
}


def parse_feed(filepath):
    """Парсинг XML и базовая валидация."""
    errors = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        offers = root.findall(f'{{{NS}}}offer')
        return root, offers, errors
    except ET.ParseError as e:
        errors.append(f"XML PARSE ERROR: {e}")
        return None, [], errors
    except FileNotFoundError:
        errors.append(f"Файл не найден: {filepath}")
        return None, [], errors


def check_required_fields(offer, offer_id):
    """Проверяет наличие обязательных полей."""
    issues = []
    for field in REQUIRED_FIELDS:
        path = field.replace('/', f'/{{{NS}}}')
        elem = offer.find(f'{{{NS}}}{path}')
        if elem is None or (elem.text is None and not list(elem)):
            issues.append(f"Отсутствует поле: {field}")
    return issues


def check_numeric_fields(offer, offer_id):
    """Проверяет что числовые поля содержат числа."""
    issues = []
    for field in NUMERIC_FIELDS:
        path = field.replace('/', f'/{{{NS}}}')
        elem = offer.find(f'{{{NS}}}{path}')
        if elem is not None and elem.text:
            try:
                float(elem.text)
            except ValueError:
                issues.append(f"Нечисловое значение в {field}: '{elem.text}'")
    return issues


def check_description(offer, offer_id):
    """Проверяет описание оффера."""
    issues = []
    desc_elem = offer.find(f'{{{NS}}}description')
    if desc_elem is None or not desc_elem.text:
        issues.append("Пустое описание")
        return issues

    desc = desc_elem.text.strip()
    if len(desc) < 50:
        issues.append(f"Слишком короткое описание ({len(desc)} символов)")
    if len(desc) > 3000:
        issues.append(f"Слишком длинное описание ({len(desc)} символов)")
    if '{' in desc or '}' in desc:
        issues.append(f"Незаполненный шаблон в описании: {desc[:80]}...")

    return issues


def check_images(offer, offer_id):
    """Проверяет изображения оффера (наличие, формат URL)."""
    issues = []
    images = offer.findall(f'{{{NS}}}image')

    if not images:
        issues.append("Нет изображений")
        return issues

    for i, img in enumerate(images):
        url = img.text or ''
        if not url.startswith('http'):
            issues.append(f"Невалидный URL изображения #{i+1}: {url[:60]}")
        if ' ' in url and '%20' not in url and '+' not in url:
            issues.append(f"Некодированный пробел в URL #{i+1}: {url[:80]}")

    return issues


def check_image_url_accessible(url, timeout=10):
    """Проверяет HTTP-доступность URL изображения (HEAD-запрос)."""
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': 'PSK-Feed-Audit/1.0',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content_type = resp.headers.get('Content-Type', '')
            if status == 200:
                if 'image' in content_type or 'svg' in content_type:
                    return 'OK', status, content_type
                else:
                    return 'WRONG_TYPE', status, content_type
            return 'ERROR', status, content_type
    except urllib.error.HTTPError as e:
        return 'HTTP_ERROR', e.code, str(e.reason)
    except urllib.error.URLError as e:
        return 'URL_ERROR', 0, str(e.reason)
    except Exception as e:
        return 'ERROR', 0, str(e)


def audit_feed(filepath, check_http=False, sample_size=None):
    """Полный аудит фида."""
    now = datetime.now(MSK)
    print(f"\n{'='*70}")
    print(f"АУДИТ ФИДА: {filepath}")
    print(f"Дата: {now.strftime('%Y-%m-%d %H:%M МСК')}")
    print(f"{'='*70}")

    # 1. Парсинг
    root, offers, parse_errors = parse_feed(filepath)
    if parse_errors:
        for e in parse_errors:
            print(f"  КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return False

    file_size = os.path.getsize(filepath)
    print(f"\n  Размер файла: {file_size / 1024:.0f} KB")
    print(f"  Всего офферов: {len(offers)}")

    # 2. Проверка каждого оффера
    all_issues = defaultdict(list)
    all_ids = []
    project_stats = Counter()
    rooms_stats = Counter()
    all_image_urls = set()
    feedhub_urls = set()

    for offer in offers:
        offer_id = offer.get('internal-id', 'NO_ID')
        all_ids.append(offer_id)

        # Проект
        bn = offer.find(f'{{{NS}}}building-name')
        project_name = bn.text.split(',')[0].strip() if bn is not None and bn.text else 'UNKNOWN'
        project_stats[project_name] += 1

        # Комнаты
        rooms = offer.find(f'{{{NS}}}rooms')
        rooms_text = rooms.text if rooms is not None else '?'
        rooms_stats[rooms_text] += 1

        # Проверки
        issues = []
        issues.extend(check_required_fields(offer, offer_id))
        issues.extend(check_numeric_fields(offer, offer_id))
        issues.extend(check_description(offer, offer_id))
        issues.extend(check_images(offer, offer_id))

        if issues:
            all_issues[offer_id] = issues

        # Собираем URL изображений
        for img in offer.findall(f'{{{NS}}}image'):
            url = img.text or ''
            all_image_urls.add(url)
            if 'feedhub.realty' in url:
                feedhub_urls.add(url)

    # 3. Уникальность ID
    id_counts = Counter(all_ids)
    duplicates = {k: v for k, v in id_counts.items() if v > 1}

    # === ОТЧЁТ ===
    print(f"\n{'─'*70}")
    print(f"СТАТИСТИКА ПО ПРОЕКТАМ:")
    print(f"{'─'*70}")
    for proj, count in sorted(project_stats.items(), key=lambda x: -x[1]):
        print(f"  {proj:<40} {count:>5} офферов")

    print(f"\n{'─'*70}")
    print(f"СТАТИСТИКА ПО КОМНАТНОСТИ:")
    print(f"{'─'*70}")
    for rooms, count in sorted(rooms_stats.items()):
        label = f"{rooms}-комн." if rooms != '?' else 'Без данных'
        print(f"  {label:<20} {count:>5} офферов")

    print(f"\n{'─'*70}")
    print(f"ИЗОБРАЖЕНИЯ:")
    print(f"{'─'*70}")
    print(f"  Всего уникальных URL:  {len(all_image_urls)}")
    print(f"  feedhub.realty:        {len(feedhub_urls)}")
    print(f"  psk-info.ru:           {len(all_image_urls) - len(feedhub_urls)}")

    # Группировка feedhub URL по папкам
    folder_counts = Counter()
    for url in feedhub_urls:
        parts = url.replace('https://feedhub.realty/ads/render/', '').split('/')
        if len(parts) >= 2:
            folder_counts[parts[0]] += 1
    if folder_counts:
        print(f"\n  Распределение по папкам feedhub.realty:")
        for folder, count in sorted(folder_counts.items(), key=lambda x: -x[1]):
            print(f"    /render/{folder}/:  {count} URL")

    # Дубликаты ID
    if duplicates:
        print(f"\n{'─'*70}")
        print(f"ДУБЛИКАТЫ ID ({len(duplicates)}):")
        print(f"{'─'*70}")
        for dup_id, count in sorted(duplicates.items(), key=lambda x: -x[1])[:20]:
            print(f"  {dup_id}: {count} раз")
    else:
        print(f"\n  Дубликатов ID: нет")

    # Ошибки по офферам
    total_issues = sum(len(v) for v in all_issues.values())
    print(f"\n{'─'*70}")
    print(f"ПРОБЛЕМЫ:")
    print(f"{'─'*70}")
    if all_issues:
        # Группировка по типу ошибки
        issue_types = Counter()
        for issues in all_issues.values():
            for issue in issues:
                # Берём тип до двоеточия
                issue_type = issue.split(':')[0].strip()
                issue_types[issue_type] += 1

        print(f"  Офферов с проблемами: {len(all_issues)} из {len(offers)}")
        print(f"  Всего проблем: {total_issues}")
        print(f"\n  По типам:")
        for issue_type, count in sorted(issue_types.items(), key=lambda x: -x[1]):
            print(f"    {issue_type}: {count}")

        # Показать первые 5 проблемных офферов
        print(f"\n  Примеры (первые 5):")
        for i, (oid, issues) in enumerate(list(all_issues.items())[:5]):
            print(f"    [{oid}]:")
            for issue in issues[:3]:
                print(f"      - {issue}")
    else:
        print(f"  Проблем не обнаружено!")

    # 4. HTTP-проверка изображений
    if check_http:
        print(f"\n{'─'*70}")
        print(f"HTTP-ПРОВЕРКА ИЗОБРАЖЕНИЙ:")
        print(f"{'─'*70}")

        urls_to_check = list(feedhub_urls)
        if sample_size and sample_size < len(urls_to_check):
            urls_to_check = random.sample(urls_to_check, sample_size)
            print(f"  Выборка: {sample_size} из {len(feedhub_urls)} URL")
        else:
            print(f"  Проверяем все {len(urls_to_check)} URL feedhub.realty")

        results = {'OK': 0, 'HTTP_ERROR': 0, 'URL_ERROR': 0, 'WRONG_TYPE': 0, 'ERROR': 0}
        broken_urls = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(check_image_url_accessible, url): url
                for url in urls_to_check
            }
            for i, future in enumerate(as_completed(future_to_url)):
                url = future_to_url[future]
                status_label, code, detail = future.result()
                results[status_label] += 1
                if status_label != 'OK':
                    broken_urls.append((url, status_label, code, detail))
                # Прогресс каждые 50
                if (i + 1) % 50 == 0:
                    print(f"    Проверено: {i+1}/{len(urls_to_check)}...")

        print(f"\n  Результаты:")
        print(f"    Доступны (200 OK):     {results['OK']}")
        print(f"    HTTP ошибки:           {results['HTTP_ERROR']}")
        print(f"    URL ошибки:            {results['URL_ERROR']}")
        print(f"    Неверный Content-Type: {results['WRONG_TYPE']}")
        print(f"    Прочие ошибки:         {results['ERROR']}")

        if broken_urls:
            print(f"\n  Недоступные URL ({len(broken_urls)}):")
            for url, status_label, code, detail in broken_urls[:20]:
                short_url = url.replace('https://feedhub.realty/ads/render/', '/render/')
                print(f"    [{code}] {short_url}")
                print(f"           {detail}")

    # Итог
    print(f"\n{'='*70}")
    has_critical = bool(parse_errors) or bool(duplicates)
    has_warnings = total_issues > 0

    if has_critical:
        print(f"СТАТУС: КРИТИЧЕСКИЕ ОШИБКИ")
    elif has_warnings:
        print(f"СТАТУС: ЕСТЬ ЗАМЕЧАНИЯ ({total_issues})")
    else:
        print(f"СТАТУС: ОК")
    print(f"{'='*70}")

    return not has_critical


def main():
    filepath = 'pskall_adapted_feed.xml'
    check_http = False
    sample_size = None

    args = sys.argv[1:]
    for arg in args:
        if arg == '--check-images':
            check_http = True
        elif arg.startswith('--sample'):
            pass  # handled below
        elif arg.endswith('.xml'):
            filepath = arg

    # --sample N
    for i, arg in enumerate(args):
        if arg == '--sample' and i + 1 < len(args):
            try:
                sample_size = int(args[i + 1])
            except ValueError:
                pass

    success = audit_feed(filepath, check_http=check_http, sample_size=sample_size)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
