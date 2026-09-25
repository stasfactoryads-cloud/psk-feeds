#!/usr/bin/env python3
"""
Трансформер фида ГК ПСК для товарных кампаний Яндекс Директ.
Обогащает описания эмоциональными посылами и добавляет lifestyle-изображения.

Версия 2 — обновлена под реальную FTP-структуру feedhub.realty/ads/render/
"""

import xml.etree.ElementTree as ET
import hashlib
import sys
from urllib.parse import quote

NS = 'http://webmaster.yandex.ru/schemas/feed/realty/2010-06'
ET.register_namespace('', NS)

IMAGE_BASE = 'https://feedhub.realty/ads/render'

# ─────────────────────────────────────────────────────────────
# УНИВЕРСАЛЬНЫЕ LIFESTYLE-ФОТО из папки /render/all/
# Эмоциональные фото: люди, интерьеры, красивые ракурсы
# Используются для ВСЕХ проектов
# ─────────────────────────────────────────────────────────────

ALL_LIFESTYLE_PHOTOS = [
    'photo_2026-09-25 15.30.22.jpeg',
    'photo_2026-09-25 15.30.27.jpeg',
    'photo_2026-09-25 15.30.33.jpeg',
    'photo_2026-09-25 15.30.36.jpeg',
    'photo_2026-09-25 15.30.39.jpeg',
    'photo_2026-09-25 15.30.52.jpeg',
    'photo_2026-09-25 15.31.13.jpeg',
    'photo_2026-09-25 15.31.16.jpeg',
    'photo_2026-09-25 15.31.20.jpeg',
    'photo_2026-09-25 15.31.23.jpeg',
    'photo_2026-09-25 15.31.32.jpeg',
    'photo_2026-09-25 15.31.36.jpeg',
    'photo_2026-09-25 15.31.38.jpeg',
    'photo_2026-09-25 15.31.43.jpeg',
    'photo_2026-09-25 15.31.47.jpeg',
    'photo_2026-09-25 15.31.52.jpeg',
    'photo_2026-09-25 15.32.06.jpeg',
    'photo_2026-09-25 15.32.09.jpeg',
    'photo_2026-09-25 15.32.14.jpeg',
    'photo_2026-09-25 15.32.17.jpeg',
    'photo_2026-09-25 15.32.20.jpeg',
    'photo_2026-09-25 15.32.34.jpeg',
    'photo_2026-09-25 15.32.39.jpeg',
    'photo_2026-09-25 15.32.42.jpeg',
    'photo_2026-09-25 15.32.45.jpeg',
    'photo_2026-09-25 15.32.49.jpeg',
    'photo_2026-09-25 15.32.59.jpeg',
    'photo_2026-09-25 15.33.09.jpeg',
    'photo_2026-09-25 15.33.19.jpeg',
    'photo_2026-09-25 15.33.26.jpeg',
    'photo_2026-09-25 15.33.30.jpeg',
    'photo_2026-09-25 15.33.32.jpeg',
    'photo_2026-09-25 15.33.34.jpeg',
    'photo_2026-09-25 15.33.36.jpeg',
    'photo_2026-09-25 15.33.39.jpeg',
]

# ─────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ ПРОЕКТОВ: описания + рендеры
# slug — реальное имя папки на FTP-сервере
# render_images — реальные имена файлов рендеров проекта
# ─────────────────────────────────────────────────────────────

PROJECTS = {
    'ЖК «Ассамблея»': {
        'slug': 'assambley',
        'class': 'бизнес-класс',
        'metro': 'Горный институт',
        'usp': [
            'Клубный квартал на Васильевском острове',
            'Потолки 3 метра, панорамные окна',
            'Закрытый двор, авторская архитектура',
        ],
        'descriptions': {
            1: [
                'Уютная квартира в клубном квартале на Васильевском. {area} кв.м, этаж {floor}/{floors}, корпус {corpus}. Метро Горный институт — пешком. Потолки 3 м, панорамные окна, закрытый двор без машин. Бизнес-класс по привлекательной цене. Скидка {discount}!',
                'Ваша первая квартира бизнес-класса — {area} кв.м на Васильевском острове. Этаж {floor}/{floors}. Клубный формат, всего 5 корпусов. Рядом Севкабель, набережные, парки. Семейная ипотека доступна. Скидка {discount}!',
                'Компактная квартира с высокими потолками на В.О. {area} кв.м, этаж {floor}. Метро Горный институт рядом. Авторский проект Intercolumnium. Инвестиция в комфорт и статус. Скидка {discount}!',
            ],
            2: [
                'Просторная двушка {area} кв.м в клубном квартале «Ассамблея». Этаж {floor}/{floors}. Васильевский остров, метро Горный институт. Потолки 3 метра, панорамные окна, дизайнерские МОП. Идеально для молодой семьи. Скидка {discount}!',
                'Квартира для семьи на Васильевском — {area} кв.м, этаж {floor}. Закрытый двор, детская площадка, школа рядом. Бизнес-класс от надёжного застройщика ГК ПСК. Семейная ипотека. Скидка {discount}!',
            ],
            3: [
                'Большая трёшка {area} кв.м в ЖК «Ассамблея». Васильевский остров, метро Горный институт. Клубный квартал, потолки 3 м, авторская архитектура. Для тех, кто ценит пространство и локацию. Скидка {discount}!',
                'Семейная квартира {area} кв.м на В.О. Этаж {floor}/{floors}. Рядом парки, набережные, культурные пространства. Закрытый двор, подземный паркинг. Новый уровень жизни. Скидка {discount}!',
            ],
        },
        'render_images': [
            'DSC00117.jpg', 'DSC00121.jpg', 'DSC00141.jpg', 'DSC00146.jpg',
            'DSC09190.jpg', 'DSC09198.jpg', 'DSC09202.jpg', 'DSC09228.jpg',
        ],
    },

    'ЖК «Галерная гавань»': {
        'slug': 'galernaygavan',
        'class': 'бизнес-класс',
        'metro': 'Приморская',
        'usp': [
            'Виды на воду с трёх сторон',
            'Исторический Васильевский остров',
            'Пешеходная набережная вдоль Галерной гавани',
        ],
        'descriptions': {
            1: [
                'Квартира с видом на воду — {area} кв.м на Васильевском острове. Этаж {floor}/{floors}. ЖК «Галерная гавань» — виды на Финский залив и Неву. Потолки 3 м, баварская кладка фасадов. Минимальный первоначальный взнос. Скидка {discount}!',
                'Жизнь у воды в центре Петербурга. {area} кв.м, этаж {floor}. Набережная у дома, Севкабель и Василеостровский рынок рядом. Бизнес-класс, архитектура Intercolumnium. Скидка {discount}!',
            ],
            2: [
                'Двушка {area} кв.м с видами на воду. Этаж {floor}/{floors}. Галерная гавань — уникальная локация между заливом и Невой. Панорамное остекление, французские балконы. Для тех, кто мечтал жить у воды. Скидка {discount}!',
                'Семейная квартира {area} кв.м на набережной Васильевского. Потолки 3 м, терраса. Развитая инфраструктура острова — музеи, рестораны, парки. Семейная ипотека доступна. Скидка {discount}!',
            ],
            3: [
                'Просторная трёшка {area} кв.м в «Галерной гавани». Виды на Финский залив. Этаж {floor}/{floors}. Квартиры с террасами и мастер-спальнями. Исторический центр, бизнес-класс. Скидка {discount}!',
            ],
            4: [
                'Эксклюзивная четырёхкомнатная квартира {area} кв.м с панорамными видами на воду. Галерная гавань, Васильевский остров. Для большой семьи, ценящей простор и локацию. Скидка {discount}!',
            ],
        },
        'render_images': [
            '1.jpg',
            'DJI_0149.jpg', 'DJI_0151.jpg', 'DJI_0156.jpg',
            'DJI_0204.jpg', 'DJI_0207.jpg', 'DJI_0213.jpg', 'DJI_0215.jpg',
            'DJI_0262.jpg', 'DJI_0267.jpg', 'DJI_0270.jpg',
            'DJI_0272.jpg', 'DJI_0273.jpg', 'DJI_0275.jpg',
            'IMG_3661.jpeg',
            'photo_2026-02-18_15-20-39.jpg',
            'photo_2026-02-18_15-20-41_.jpg',
        ],
    },

    'ЖК «ОПТИМИСТ»': {
        'slug': None,  # Папка ещё не создана на сервере
        'class': 'бизнес-класс',
        'metro': 'Бухарестская',
        'usp': [
            'Формат бизнес-лайт — комфорт по доступной цене',
            'Мультиформатное лобби 160 кв.м',
            'Спортзал, коворкинг, кофе-поинт для жителей',
        ],
        'descriptions': {
            1: [
                'Старт продаж! Квартира {area} кв.м в ЖК «Оптимист». Бизнес-лайт: потолки 3 м, лобби 160 кв.м, коворкинг и спортзал для жителей. 10 мин пешком до метро Бухарестская. Семейная ипотека. Скидка {discount}!',
                'Новый дом для активных людей — {area} кв.м, этаж {floor}. ЖК «Оптимист»: авторская архитектура, футуристичные интерьеры, закрытый двор с ландшафтным дизайном. Квартиры с отделкой. Скидка {discount}!',
                'Квартира бизнес-класса от {price_from} ₽. {area} кв.м в ЖК «Оптимист». Коворкинг, спортзал, игровая зона — всё для жителей. Рядом метро, школа, детский сад. Минимальный взнос от 20%. Скидка {discount}!',
            ],
            2: [
                'Двушка {area} кв.м в новом ЖК «Оптимист». Бизнес-класс рядом с метро. Потолки 3 м, панорамные окна, два варианта отделки. Закрытый двор, детская площадка, амфитеатр. Семейная ипотека доступна. Скидка {discount}!',
                'Идеальная квартира для семьи — {area} кв.м, этаж {floor}/{floors}. Школа и детский сад в составе ЖК. Подземный паркинг, зона доставки. Комфорт нового уровня по цене от {price_from} ₽. Скидка {discount}!',
            ],
            3: [
                'Трёхкомнатная квартира {area} кв.м с мастер-спальней. ЖК «Оптимист» — бизнес-лайт у метро Бухарестская. Потолки 3 м, квартиры с террасами, подземный паркинг 256 мест. Скидка {discount}!',
            ],
            4: [
                'Большая семейная квартира {area} кв.м в ЖК «Оптимист». Кухня-гостиная, мастер-спальня, гардеробная. Школа на 350 мест и детсад в комплексе. Бизнес-класс по разумной цене. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Будут добавлены после создания папки
    },

    'ЖК «РЕСПЕКТ»': {
        'slug': 'respect',
        'class': 'комфорт-класс',
        'metro': 'Лесная',
        'usp': [
            'Выборгская сторона — развитый район',
            'Квартиры с отделкой',
            'Рядом парки и набережная',
        ],
        'descriptions': {
            1: [
                'Квартира с отделкой {area} кв.м рядом с метро Лесная. ЖК «РЕСПЕКТ» — комфорт-класс на Выборгской стороне. Заезжай и живи! Этаж {floor}/{floors}. Парки и набережная рядом. Скидка {discount}!',
                'Готовая квартира {area} кв.м — заезжай и живи. Метро Лесная пешком. ЖК «РЕСПЕКТ»: развитая инфраструктура, зелёный район, отличная транспортная доступность. Ипотека от 5,5%. Скидка {discount}!',
                'Ваш новый адрес на Выборгской стороне — {area} кв.м, этаж {floor}. ЖК «РЕСПЕКТ» с отделкой. Рядом Сампсониевский сад, набережная. Комфорт по доступной цене. Скидка {discount}!',
            ],
            2: [
                'Двушка с чистовой отделкой {area} кв.м. ЖК «РЕСПЕКТ», метро Лесная. Просторные комнаты, функциональная планировка. Район с парками и набережными. Семейная ипотека. Скидка {discount}!',
                'Квартира для семьи {area} кв.м с готовой отделкой. Этаж {floor}/{floors}. Выборгская сторона: школы, сады, магазины — всё рядом. Заезжай без ремонта! Скидка {discount}!',
            ],
            3: [
                'Просторная трёшка {area} кв.м с отделкой в ЖК «РЕСПЕКТ». Метро Лесная пешком. Комфорт-класс для большой семьи. Зелёный район, развитая инфраструктура. Семейная ипотека доступна. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «СЕЗОНЫ»': {
        'slug': 'sezony',
        'class': 'комфорт-класс',
        'metro': 'Проспект Просвещения',
        'usp': [
            'Видовой комплекс — малоэтажный',
            'Зелёный район у парков',
            'Квартиры с отделкой',
        ],
        'descriptions': {
            1: [
                'Квартира {area} кв.м в видовом комплексе «СЕЗОНЫ». Этаж {floor}/{floors}. Малоэтажный квартал у метро Просвещения. Квартиры с отделкой, зелёный район. Семейная ипотека. Скидка {discount}!',
                'Жизнь среди зелени — {area} кв.м, этаж {floor}. ЖК «СЕЗОНЫ»: уютный малоэтажный формат, парки рядом. Комфорт-класс с отделкой. Первоначальный взнос от 15%. Скидка {discount}!',
                'Светлая квартира {area} кв.м в зелёном районе. ЖК «СЕЗОНЫ» — видовой комплекс у метро. Готовая отделка, заезжай и живи. Идеально для семьи с детьми. Скидка {discount}!',
            ],
            2: [
                'Двушка {area} кв.м в ЖК «СЕЗОНЫ» — малоэтажный видовой комплекс. Квартира с отделкой, рядом метро Просвещения. Зелёный двор, детские площадки. Для тех, кто ценит тишину и природу. Скидка {discount}!',
            ],
            3: [
                'Семейная трёшка {area} кв.м в видовом комплексе «СЕЗОНЫ». Малоэтажный формат, зелёный район, метро рядом. Квартира с отделкой — заезжай и живи! Скидка {discount}!',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «ПЛЮС Пулковский»': {
        'slug': 'pluspulkovsky',
        'class': 'комфорт-класс',
        'metro': 'Московская',
        'usp': [
            'Город в городе — вся инфраструктура в квартале',
            'Школа с бассейном, 2 детсада, медцентры',
            'Малоэтажный квартал в Московском районе',
        ],
        'descriptions': {
            1: [
                'Квартира с отделкой {area} кв.м в ЖК «ПЛЮС Пулковский». Малоэтажный квартал в Московском районе. Школа, 2 детсада, медцентр — всё в квартале! Рядом КАД и метро. Скидка {discount}!',
                'Город в городе — квартира {area} кв.м, этаж {floor}/{floors}. ЖК «ПЛЮС Пулковский»: школа с бассейном, детские сады, магазины, кафе. Квартира с полной отделкой. Семейная ипотека. Скидка {discount}!',
                'Доступный комфорт для семьи — {area} кв.м от {price_from} ₽. Малоэтажный «ПЛЮС Пулковский» в Московском районе. Вся инфраструктура на месте. Рядом Пушкин, Павловск. Скидка {discount}!',
            ],
            2: [
                'Двушка с отделкой {area} кв.м в семейном квартале. ЖК «ПЛЮС Пулковский»: школа с бассейном в квартале, 2 детсада. Тихий малоэтажный район. Рядом метро Московская. Семейная ипотека. Скидка {discount}!',
                'Квартира для растущей семьи — {area} кв.м, этаж {floor}. Чистовая отделка: заезжай и живи. Вся инфраструктура в шаговой доступности. Парки, дворцы Пушкина и Павловска рядом. Скидка {discount}!',
            ],
            3: [
                'Просторная трёшка {area} кв.м в малоэтажном «ПЛЮС Пулковский». Школа с бассейном, медцентр, закрытые дворы. Московский район — престижная локация. Чистовая отделка. Семейная ипотека. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «Акватория»': {
        'slug': None,  # Папка ещё не создана на сервере
        'class': 'премиум-класс',
        'metro': 'Петроградская',
        'usp': [
            'Премиальный дом на Петроградской стороне',
            'Выборгская набережная — виды на воду',
            'Эксклюзивные планировки от 50 кв.м',
        ],
        'descriptions': {
            1: [
                'Премиальная квартира {area} кв.м на Петроградской стороне. ЖК «Акватория» — дом на набережной с видами на воду. Этаж {floor}/{floors}. Эксклюзивный уровень жизни. Скидка {discount}!',
            ],
            2: [
                'Двухкомнатная резиденция {area} кв.м на Выборгской набережной. ЖК «Акватория» — премиум-класс. Петроградская сторона, виды на воду, авторская архитектура. Для ценителей. Скидка {discount}!',
            ],
            3: [
                'Просторная квартира {area} кв.м в премиальном доме «Акватория». Петроградская, набережная. Высокие потолки, панорамное остекление. Ваш дом на воде в центре Петербурга. Скидка {discount}!',
            ],
            4: [
                'Семейная резиденция {area} кв.м в «Акватории». Премиум-класс на Петроградской. Панорамные виды на Неву, дизайнерские МОП, подземный паркинг. Статус и комфорт. Скидка {discount}!',
            ],
            5: [
                'Эксклюзивная пятикомнатная квартира {area} кв.м в ЖК «Акватория». Петроградская набережная, виды на воду. Премиум-класс для большой семьи. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Будут добавлены после создания папки
    },

    'ЖК «Industrial AVENIR»': {
        'slug': 'indastrial',
        'class': 'комфорт-класс',
        'metro': 'Кировский Завод',
        'usp': [
            'Дом сдан — апартаменты с чистовой отделкой',
            'Рядом метро Кировский Завод',
            'Апарт-формат от надёжного застройщика',
        ],
        'descriptions': {
            1: [
                'Апартаменты с отделкой {area} кв.м рядом с метро. «Industrial AVENIR» — дом сдан, полностью готов! Заезжай и живи! Этаж {floor}/{floors}. Рядом метро Кировский Завод. Скидка {discount}!',
                'Готовые апартаменты {area} кв.м — дом построен и сдан! «Industrial AVENIR» у метро Кировский Завод. Чистовая отделка, отличная инвестиция. Комфорт-класс от ГК ПСК. Скидка {discount}!',
                'Апартаменты {area} кв.м с ключами — дом сдан! «Industrial AVENIR», этаж {floor}. Полностью готовы, с чистовой отделкой. Рядом метро, развитая инфраструктура. Скидка {discount}!',
            ],
            2: [
                'Двухкомнатные апартаменты {area} кв.м с отделкой в «Industrial AVENIR». Дом сдан, готов к заселению! Метро Кировский Завод рядом. Въезжай без ремонта. Комфорт-класс по доступной цене. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «Ladozhsky AVENIR»': {
        'slug': 'ladozsky',
        'class': 'бизнес-класс',
        'metro': 'Ладожская',
        'usp': [
            'Дом сдан — заезжай сейчас',
            'Чистовая отделка',
            'Рядом метро Ладожская',
        ],
        'descriptions': {
            1: [
                'Готовые апартаменты {area} кв.м — дом сдан! «Ladozhsky AVENIR» у метро Ладожская. Чистовая отделка, заезжай сегодня. Бизнес-класс по цене комфорта. Скидка {discount}!',
                'Апартаменты с ключами — {area} кв.м, этаж {floor}. Дом сдан, отделка готова. «Ladozhsky AVENIR» — бизнес-класс у Ладожской. Без ожидания, без ремонта. Скидка {discount}!',
                'Апартаменты бизнес-класса {area} кв.м в готовом доме. «Ladozhsky AVENIR» — дом сдан, рядом метро Ладожская. Чистовая отделка, этаж {floor}/{floors}. Скидка {discount}!',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «BAKUNINA 33»': {
        'slug': 'bakunina',
        'class': 'бизнес-класс',
        'metro': 'Площадь Александра Невского',
        'usp': [
            'Центр Петербурга — метро Площадь Александра Невского',
            'Камерный дом бизнес-класса',
            'Просторные квартиры от 54 кв.м',
        ],
        'descriptions': {
            1: [
                'Квартира {area} кв.м в центре Петербурга! ЖК «BAKUNINA 33» — камерный дом бизнес-класса у метро Площадь Александра Невского. Просторные квартиры, высокие потолки. Дом сдан!',
            ],
            2: [
                'Двушка {area} кв.м в самом центре. «BAKUNINA 33» — бизнес-класс у Невского проспекта. Камерный дом, этаж {floor}/{floors}. Для тех, кто выбирает центр. Дом сдан!',
            ],
            3: [
                'Трёхкомнатная квартира {area} кв.м в центре Петербурга. ЖК «BAKUNINA 33» у метро Площадь Александра Невского. Просторная, с высокими потолками. Бизнес-класс, дом сдан!',
            ],
            4: [
                'Большая семейная квартира {area} кв.м в сердце Петербурга. «BAKUNINA 33» — бизнес-класс рядом с Невским проспектом. Камерный дом, этаж {floor}. Уже готов к заселению!',
            ],
        },
        'render_images': [
            'IMG_2658.jpg', 'IMG_2659.jpg', 'IMG_2664.jpg', 'IMG_2665.jpg',
            'IMG_2679.jpg', 'IMG_2681.jpg', 'IMG_2686.jpg', 'IMG_2687.jpg',
            'IMG_2702.jpg', 'IMG_2703.jpg', 'IMG_2705.jpg', 'IMG_2709.jpg',
            'IMG_2711.jpg', 'IMG_2714.jpg', 'IMG_2715.jpg', 'IMG_2719.jpg',
            'IMG_2723.jpg', 'IMG_2726.jpg', 'IMG_2734.jpg', 'IMG_2741.jpg',
            'IMG_2745.jpg', 'IMG_2748.jpg', 'IMG_2749.jpg', 'IMG_2751.jpg',
            'IMG_2752.jpg',
            # Кириллические имена — URL-кодируем автоматически
            'Б33-011.jpg', 'Б33-021.jpg',
        ],
    },

    'ЖК «Северная корона»': {
        'slug': 'severnaykorona',
        'class': 'премиум-класс',
        'metro': 'Петроградская',
        'usp': [
            'Премиум на Петроградской',
            'Набережная реки Карповки',
            'Дом сдан',
        ],
        'descriptions': {
            1: [
                'Премиальная квартира {area} кв.м на Петроградской. ЖК «Северная корона» — дом сдан, набережная Карповки. Эксклюзивный формат, высокие потолки. Для ценителей.',
            ],
            2: [
                'Двушка {area} кв.м премиум-класса на Петроградской стороне. «Северная корона» — камерный дом на набережной Карповки. Сдан, готов к заселению.',
            ],
            3: [
                'Трёхкомнатная квартира {area} кв.м в «Северной короне». Премиум-класс, Петроградская сторона. Набережная, парки, метро рядом. Дом сдан.',
            ],
        },
        'render_images': [],  # Нужно получить список файлов
    },

    'ЖК «Северная корона Apartments»': {
        'slug': 'severnaykorona',  # Та же папка
        'class': 'премиум-класс',
        'metro': 'Петроградская',
        'usp': ['Апартаменты премиум-класса на Петроградской'],
        'descriptions': {
            3: [
                'Премиальные апартаменты {area} кв.м на Петроградской. «Северная корона Apartments» — набережная Карповки, камерный формат. Дом сдан.',
            ],
        },
        'render_images': [],
    },
}


def get_corpus(building_name):
    """Extract corpus number from building name."""
    if 'корпус' in building_name:
        parts = building_name.split('корпус')
        return parts[1].strip() if len(parts) > 1 else ''
    return ''


def pick_description(project_key, rooms, offer_id, area, floor, floors, corpus, discount, price):
    """Pick an emotional description template and fill it."""
    proj = PROJECTS.get(project_key)
    if not proj:
        return None

    rooms_int = int(rooms) if rooms else 1
    descs = proj['descriptions']

    # Find descriptions for this room count, fall back to nearest
    templates = descs.get(rooms_int)
    if not templates:
        available = sorted(descs.keys())
        closest = min(available, key=lambda x: abs(x - rooms_int))
        templates = descs[closest]

    # Rotate templates based on offer_id hash
    idx = int(hashlib.md5(str(offer_id).encode()).hexdigest(), 16) % len(templates)
    template = templates[idx]

    # Format price
    price_from = ''
    if price:
        try:
            p = int(float(price))
            if p >= 1_000_000:
                price_from = f"{p / 1_000_000:.1f} млн"
            else:
                price_from = f"{p:,}".replace(',', ' ')
        except (ValueError, TypeError):
            price_from = str(price)

    return template.format(
        area=area or '?',
        floor=floor or '?',
        floors=floors or '?',
        corpus=corpus or '?',
        discount=discount or '15%',
        price_from=price_from,
        rooms=rooms or '1',
    )


def make_image_url(base, folder, filename):
    """Build a properly URL-encoded image URL."""
    # Кодируем имя файла (пробелы, кириллица и т.д.)
    encoded_name = quote(filename, safe='')
    return f"{base}/{folder}/{encoded_name}"


def pick_images(project_key, offer_id, original_images):
    """
    Build image list:
    1. Оригинальный план этажа (SVG из исходного фида)
    2. 2 универсальных lifestyle-фото из /render/all/
    3. 1 рендер проекта из /render/{slug}/ (если есть)
    4. Оригинальный план здания (SVG из исходного фида)
    """
    proj = PROJECTS.get(project_key)
    if not proj:
        return original_images

    slug = proj['slug']
    render_files = proj.get('render_images', [])

    h = int(hashlib.md5(str(offer_id).encode()).hexdigest(), 16)

    result = []

    # 1. Первый оригинальный план (план квартиры)
    if original_images:
        result.append(original_images[0])

    # 2. Два универсальных lifestyle-фото из all/ (ротация по offer_id)
    n_lifestyle = min(2, len(ALL_LIFESTYLE_PHOTOS))
    for i in range(n_lifestyle):
        idx = (h + i * 13) % len(ALL_LIFESTYLE_PHOTOS)
        photo = ALL_LIFESTYLE_PHOTOS[idx]
        result.append(make_image_url(IMAGE_BASE, 'all', photo))

    # 3. Один рендер проекта (если папка и файлы есть)
    if slug and render_files:
        render_idx = h % len(render_files)
        render_file = render_files[render_idx]
        result.append(make_image_url(IMAGE_BASE, slug, render_file))
    elif len(ALL_LIFESTYLE_PHOTOS) > n_lifestyle:
        # Если рендеров нет — ещё одно lifestyle-фото
        extra_idx = (h + 37) % len(ALL_LIFESTYLE_PHOTOS)
        photo = ALL_LIFESTYLE_PHOTOS[extra_idx]
        result.append(make_image_url(IMAGE_BASE, 'all', photo))

    # 4. Второй оригинальный план (план здания)
    if len(original_images) > 1:
        result.append(original_images[1])

    return result


def transform_feed(input_path, output_path):
    """Transform the feed: enrich descriptions and add lifestyle images."""
    tree = ET.parse(input_path)
    root = tree.getroot()

    offers = root.findall(f'{{{NS}}}offer')
    stats = {'total': 0, 'transformed': 0, 'skipped': 0}

    for offer in offers:
        stats['total'] += 1
        offer_id = offer.get('internal-id', '')

        bn_elem = offer.find(f'{{{NS}}}building-name')
        if bn_elem is None:
            stats['skipped'] += 1
            continue

        building_name = bn_elem.text.strip()
        project_key = building_name.split(',')[0].strip()

        if project_key not in PROJECTS:
            stats['skipped'] += 1
            continue

        # Get offer data
        rooms = offer.find(f'{{{NS}}}rooms')
        rooms_text = rooms.text if rooms is not None else '1'

        area_elem = offer.find(f'{{{NS}}}area/{{{NS}}}value')
        area = area_elem.text if area_elem is not None else ''

        floor_elem = offer.find(f'{{{NS}}}floor')
        floor = floor_elem.text if floor_elem is not None else ''

        floors_elem = offer.find(f'{{{NS}}}floors-total')
        floors = floors_elem.text if floors_elem is not None else ''

        price_elem = offer.find(f'{{{NS}}}price/{{{NS}}}value')
        price = price_elem.text if price_elem is not None else ''

        corpus = get_corpus(building_name)

        # Extract discount from original description
        desc_elem = offer.find(f'{{{NS}}}description')
        orig_desc = desc_elem.text if desc_elem is not None else ''
        discount = ''
        if 'Скидка' in orig_desc:
            discount = orig_desc.split('Скидка')[1].strip().rstrip('!')

        # Generate new description
        new_desc = pick_description(
            project_key, rooms_text, offer_id,
            area, floor, floors, corpus, discount, price
        )

        if new_desc and desc_elem is not None:
            desc_elem.text = new_desc

        # Get original images
        original_images = []
        for img_elem in offer.findall(f'{{{NS}}}image'):
            original_images.append(img_elem.text)

        # Generate new image set
        new_images = pick_images(project_key, offer_id, original_images)

        # Remove old image elements
        for img_elem in offer.findall(f'{{{NS}}}image'):
            offer.remove(img_elem)

        # Insert new images (before description or at end)
        desc_elem = offer.find(f'{{{NS}}}description')
        for img_url in new_images:
            img_new = ET.SubElement(offer, f'{{{NS}}}image')
            img_new.text = img_url
            if desc_elem is not None:
                offer.remove(img_new)
                idx = list(offer).index(desc_elem)
                offer.insert(idx, img_new)

        stats['transformed'] += 1

    # Write output
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    return stats


if __name__ == '__main__':
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'pskall_feed.xml'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'pskall_adapted_feed.xml'

    print(f"Transforming: {input_file} → {output_file}")
    stats = transform_feed(input_file, output_file)
    print(f"\nResults:")
    print(f"  Total offers:       {stats['total']}")
    print(f"  Transformed:        {stats['transformed']}")
    print(f"  Skipped (no match): {stats['skipped']}")
    print("Done!")
