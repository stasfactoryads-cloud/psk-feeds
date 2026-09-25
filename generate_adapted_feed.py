#!/usr/bin/env python3
"""
Генерация адаптированного фида для товарных кампаний Яндекс Директ.

Скачивает актуальный исходный фид pskall_yandex_direct_feed.xml из main-ветки,
применяет трансформацию (эмоциональные описания + lifestyle-изображения),
сохраняет результат как pskall_adapted_feed.xml.

Запуск:
  python generate_adapted_feed.py              # стандартная генерация
  python generate_adapted_feed.py --local      # из локального файла (без скачивания)
"""

import os
import sys
import urllib.request
import json
from datetime import datetime, timezone, timedelta

# Импортируем трансформер
from feed_transformer import transform_feed

# === Конфигурация ===
FEED_URL = 'https://raw.githubusercontent.com/stasfactoryads-cloud/psk-feeds/main/pskall_yandex_direct_feed.xml'
INPUT_FILE = 'pskall_yandex_direct_feed.xml'
OUTPUT_FILE = 'pskall_adapted_feed.xml'

MSK = timezone(timedelta(hours=3))


def download_feed(url, output_path):
    """Скачивает свежий исходный фид из GitHub."""
    print(f"Скачиваю исходный фид: {url}")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'PSK-Feed-Generator/1.0',
            'Accept': 'application/xml',
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            with open(output_path, 'wb') as f:
                f.write(data)
        size_kb = len(data) / 1024
        print(f"  Скачано: {size_kb:.0f} KB")
        return True
    except Exception as e:
        print(f"  ОШИБКА скачивания: {e}")
        return False


def main():
    use_local = '--local' in sys.argv

    now = datetime.now(MSK)
    print(f"{'='*60}")
    print(f"Генерация адаптированного фида ГК ПСК")
    print(f"Дата: {now.strftime('%Y-%m-%d %H:%M МСК')}")
    print(f"{'='*60}")

    # 1. Получаем исходный фид
    if use_local:
        if not os.path.exists(INPUT_FILE):
            print(f"ОШИБКА: Локальный файл {INPUT_FILE} не найден")
            sys.exit(1)
        print(f"Используем локальный файл: {INPUT_FILE}")
    else:
        if not download_feed(FEED_URL, INPUT_FILE):
            # Пробуем использовать локальный файл как fallback
            if os.path.exists(INPUT_FILE):
                print(f"Используем локальную копию: {INPUT_FILE}")
            else:
                print("ОШИБКА: Не удалось получить исходный фид")
                sys.exit(1)

    # 2. Трансформируем
    print(f"\nТрансформация: {INPUT_FILE} → {OUTPUT_FILE}")
    stats = transform_feed(INPUT_FILE, OUTPUT_FILE)

    # 3. Отчёт
    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТ:")
    print(f"  Всего офферов:     {stats['total']}")
    print(f"  Трансформировано:  {stats['transformed']}")
    print(f"  Пропущено:        {stats['skipped']}")

    if os.path.exists(OUTPUT_FILE):
        size_kb = os.path.getsize(OUTPUT_FILE) / 1024
        print(f"  Размер файла:     {size_kb:.0f} KB")

    print(f"{'='*60}")

    if stats['transformed'] == 0:
        print("ВНИМАНИЕ: Ни один оффер не трансформирован!")
        sys.exit(1)

    print("Готово!")
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
