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

# CDN-прокси для конвертации SVG-планировок в JPG 1200×1200
# CDN proxy removed — floor plans no longer used in feed

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
# slug — реальное имя папки на FTP-сервере (для lifestyle)
# render_images — полные URL рендеров проекта из API psk-info.ru
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
        'headlines': [
            'Квартира бизнес-класса на Васильевском',
            'Клубный квартал у метро — потолки 3 метра',
            'Жизнь на В.О. — панорамные окна и закрытый двор',
            'Авторская архитектура на Васильевском острове',
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
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/cb748a7143c8e9a21662b64c613c3a31a9f18f7d.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/6ee21fc9843ad8d84a01b60bc089d3f3e4c96b6b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/30e25b2ee81cb5639dc229a94770b92d74725850.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c4a12a81f08c5784abc792282b7f391b0ae5840a.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/4c3e87c5a184ff9828fc820d84936138c74cc851.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/902a3cb709b9e9328994365593bf0698c5489411.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/6ef9d8aa936f0f424aa30131836e190b2197ddda.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/79d91736ad0b1489a0185fc89ec03041a7e098a8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/1778f9ee5dab1823a30ff8e7888549cf4e235132.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/b952d04f94ab20fe15623bdd9780051490b89dfb.jpg',
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
        'headlines': [
            'Квартира с видом на воду — живи у залива',
            'Дом на набережной — виды на Неву и залив',
            'Жизнь у воды на Васильевском острове',
            'Квартира мечты с панорамой на Финский залив',
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
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/46f8732c1d9b4327d84e9382d99560a62c54d8fd.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8b496ef1b428bc64bb3feeafb5db62b498719c20.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/2372c1544b0ca579c1f1642a4ada026ff9b746c3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/2d92a3b0621aa50559b9f5fe052f31138f559cdb.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/bb674c48ef387d49eae17bdecf7863bc88f1431.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/99cf3b04964035b6f2e9378ae7a626ba890ed198.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/21c1f34cd9ec5e20d131448a8a49cdff40bb4592.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/acb1c2608d7f58b5491cc818445b3ebda878531b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/63748adccdb324e4c9074df94d5b2523fedc72a6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/a50201533db4ccd40039e2f428fe0d5b19feb1bc.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/852325cdfc1c49952338b696baebf847349b724e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8a099ca6217e61e7b1db8924917f38113196c063.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/252b30d3a01abb41bec12f0e9dccb485fd29bf95.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d6b1b2c118665b19e0ab3e1d73173d6d51d261b3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8a1823dc7944a320568f00b5ab3943fc6ddae82b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d9ce41c64c3076c166f389fa08bd58001ef3159c.jpg',
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
        'headlines': [
            'Бизнес-класс по доступной цене — старт продаж!',
            'Квартира с коворкингом и спортзалом в доме',
            'Бизнес-лайт у метро — всё для активных людей',
            'Квартира мечты — лобби, спортзал, коворкинг',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/dd6f4d8c0ddc182e5392a59657fe88d3ec68635f.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/62df8906c2ec9d67b08f827ab5b2afa0fb8ef5d1.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/029129977548f703c12da9081ad57437c10b54e1.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/67d8568460cfe3c23ec8a39287ed5b477ed5099f.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9a6d404f31a080dfdf93f0e00a9e22381966ca0a.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/ae5e6c376e863ea813bd6bf90b986e066b00dc98.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/23ff2c2453aa4575d63db7ae6c7c1544178c9126.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/cb2353349c593a0d83305abbf90a75d9ec40b8d7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9c7d50bc4f89400605a07b56d156f80acb687793.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/7e0e3648e1b5c143f868b740f3b039b48506188e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/85c07c8b6f01f9bf795929da050b7268815854da.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/6a59494b84606cc78db50ed30d91ecce5b5694d8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/2daf693aecbd93b58f1f7ef32dc44f983ab8e356.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/86d930818976ac8efacf0e484469a8da07d523aa.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9239e170eb14de0569f16d33e3b65fbe4c011446.jpg',
        ],
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
        'headlines': [
            'Квартира с отделкой — заезжай и живи!',
            'Готовая квартира у метро Лесная',
            'Комфорт у парков — квартира с отделкой',
            'Квартира мечты на Выборгской стороне',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/cd2c0412ec9758b132ede0de07def11f0e5b0427.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/354fe95c63e6ba3d0955725e731325fd5792b6a3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0c0948c8f6c72acfcf8bb8a9284c1a60bf5b8f83.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/275570ea49ee06f3e6e12542da0897d5a858cbe6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/7542bf33e643fe49a6f8b8b8942e70c13d3fb3b8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/83f88906eda9da8cb97d57967abe1ce23dcc79dc.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/954309860a3665520a7eeb86c982989fa665c638.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/5a1150a174a03ad725bdf34bf269af05e6d27992.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/6532197d8b88aad3019bb633075ca66b0b27ddc0.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0baf203f87c06c4ea175e436956887de91d530c8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0fe1176a1adf927e8a5c6fe471768ea6ca2f6696.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/3d4309fe4d42b8aaedaa27cdd39a8610b35ce096.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9a502b839cb56f2bbc4e6c68d8c4bf2cf2dae005.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/34ce988aab4ea3853c6edde34b6bfa51fd7b2811.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/96ce242f70cbefcabb51fa01e7f754d39ef89319.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fe85a886361d404ac86ab9fca3977a73e2f31805.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/628aa1d89a520e66ea3a34e19950abdfa011fa82.jpg',
        ],
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
        'headlines': [
            'Квартира в зелёном квартале у метро',
            'Малоэтажный дом — тишина и природа рядом',
            'Видовая квартира с отделкой у парков',
            'Квартира мечты в зелёном районе',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/7051004f3281621ea66f55c4b1d5499807fedbde.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/ce864efc2712537fc1dc82cfd5e87f7fdb4e857b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/1c9cfdb20a22e10cd2f23c23292304a4c9407d36.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fb107de6ae6a87ee1faeab2a6cc5d6124e30a0be.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/614bf8e723fe955ac2ac2e35e786678c8f50fc93.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/98f3bc3457b03df035e34d5f9d315177ee4d77b0.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/29333a2288576e1e5c876eb7f167e3b89a4cd7e7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/23719089108ce70ad6342a7ee2a98ff02855e903.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/81de8ed4353e76ac5a39a769d2f1ea47ddc7e72f.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d8ab0249f98ea8f39238b78fde105f4d821479a3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d4b8405f703827fcfceec263300b4992f0d0bb17.jpg',
        ],
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
        'headlines': [
            'Город в городе — школа, сады, медцентр рядом',
            'Квартира для семьи — школа с бассейном в квартале',
            'Всё для жизни в одном квартале',
            'Семейная квартира — инфраструктура у порога',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/4172e167c1486ef8c1ec930ab9f2c77a3d27a188.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8dd31f830a8def502ac62ca1c1ad51b4b2f45fec.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c9bcb6758c537a43e24b0d4ecce2e7df8a5b5244.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/2fb9ae67b2ddedf4d0d2eec2e01f35155429b024.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8e909f0157337f8de740e9ddf44f5dff74e461b0.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/330de16ee8f7aad7ad8eba81235af307d904df04.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0557c1e9d1c2d7afa53a488a7367d5a279c2f6d4.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/900f38733e3abf1f9b8b3209e24de454e39e29f1.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/076131eb8515af047164753a4175910339bcee60.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/833adc2247eedb0770b527fd5b4294d4b1647411.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9e4bc56e0410967fb60011bed3c8cb10f9f3200b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/97d8cdb20461b0fe1670b69b976db5e9d31a4ed1.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/460a9c15043ac11bbcd6980b31d7c7866871e05e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/a514a1ad15d8efb5d1dc3fcd233b06e6de5f51ba.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/214d7710738a3ae5abe40212a0f7e2a130c128f3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/4f20840cc4de557d6ca734ec9847f3eea6515382.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/bbcca57c6abf2f44293f5b28d60671d5f91f8377.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/08458c62cde0f5926ec0312de86566058c670846.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/556813b8e2e5d9f9c949b6780f11bbd69a70e197.jpg',
        ],
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
        'headlines': [
            'Премиум на Петроградской — виды на воду',
            'Резиденция на набережной — эксклюзивный дом',
            'Квартира премиум-класса с видом на Неву',
            'Дом на воде в центре Петербурга',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/5a845e99155b3e8d98fe5f396ef632735cd86688.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/2e94fd2d7f5d86341ec1cff8a74db208176be809.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/f0c9e4376ba382fa6404f50184493e86bc3c095b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/14b68594fa92378f7caa3ca9912fcf2d7f1d6f02.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8ca684b1eaf38350c687e33e61cfdd088ca4f3f7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/4e21cc0546321e6328fdd5e52602ff3a8a315b27.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/3ac2307ddd5f3ee9ce39d72c438271abeee9e467.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/07a6ccbb4bf1f58cec4ca39d293dee05a2f6dfa8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/57deaff88e33ac1538e5c2af7adbd581dac5b5f5.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/7d065f9fdd464d458bb6ea32d7899d3f3111f46e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/8271509e092a61a9ff8f62a44fe9ccc58c784ad4.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fbff986c46f1164e7b9621f658156bf7a2ef2ff7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/6f40903d9ee39374c0d71db45935a10460bf9cb8.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/153349571e0e90a7143acf7ec68acb105088555f.jpg',
        ],
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
        'headlines': [
            'Готовые апартаменты — дом сдан, заезжай!',
            'Апартаменты с отделкой у метро — дом сдан',
            'Апартаменты с ключами — без ожидания!',
            'Дом сдан — апартаменты готовы к жизни',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/23cb7f55134d072d086f65540df70785bba9b0d9.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/f13e596508998e5dc1a0f23ba4229c6532c076b9.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fd4b0766281213acdfcea905fcb2fda2e8185bb9.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/29a2e3b4cf15561bb03032d667f9a083299c4cb7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/1a04513c1c64a99b8807fd607bb6f310968c347e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/edcc79aef09d4a42b5edf9483efa21b30187eb5e.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/745c4746e04d88b53a9ca5d3141cf8408278e4fe.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d6fa69f85893a50cc542c56b1c31caa3d10988f7.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/511075561c7df0cc5d88adecd472209b1d8411c3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/9ef905047c9a540385a918af1f7c3e8bb2b1c502.jpg',
        ],
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
        'headlines': [
            'Апартаменты бизнес-класса — дом сдан!',
            'Готовые апартаменты у метро Ладожская',
            'Апартаменты с отделкой — заезжай сегодня',
            'Бизнес-класс с ключами — без ожидания',
        ],
        'descriptions': {
            1: [
                'Готовые апартаменты {area} кв.м — дом сдан! «Ladozhsky AVENIR» у метро Ладожская. Чистовая отделка, заезжай сегодня. Бизнес-класс по цене комфорта. Скидка {discount}!',
                'Апартаменты с ключами — {area} кв.м, этаж {floor}. Дом сдан, отделка готова. «Ladozhsky AVENIR» — бизнес-класс у Ладожской. Без ожидания, без ремонта. Скидка {discount}!',
                'Апартаменты бизнес-класса {area} кв.м в готовом доме. «Ladozhsky AVENIR» — дом сдан, рядом метро Ладожская. Чистовая отделка, этаж {floor}/{floors}. Скидка {discount}!',
            ],
        },
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/a3e31d2e668fab6d7f37188add04f192b206789d.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/ba7a4cd5591f6ca7c60ec052c391f04c9d37e095.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/d7e9194ec4b75747c4e29b857477a0d0616efdf4.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/43eb0c95d976b836d27fd13646b74630a6cb8200.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c539efb56106d785b51b4b7b14b9083f10709d65.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/33059eb4b4e452056a38608b2ee11c14d7820b31.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/da239a681ea9f3819008252d82614a86b0dcd0d0.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/3f2d60784cb17f8d5484aa3de4c5650bde978040.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/85fc75c213d01b2e3da5af02307f7983a39ffa24.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/e0d1f51e420ff11e5f079e4c24c4f054257f1c25.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c2cb42319d2c9e27a3a2d1f085e6d5cffc95e1b0.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/01bfd6eebe9353cc2fd1206f6cd0c4e994594cc1.jpg',
        ],
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
        'headlines': [
            'Квартира в центре Петербурга — дом сдан!',
            'Бизнес-класс у Невского проспекта',
            'Камерный дом в сердце Петербурга',
            'Квартира у метро — центр города, дом сдан',
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
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/dd0b4020a4d4409e43eb2d642e9b2f52366ac4c4.jpeg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fef5851888e544ed269749f4f86160ee8da05cc3.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/cef8ebfa1d9d3b6d8b119abf109a047d4fbae863.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/951a2fc1c4d537a697d47eaf995393cae735013d.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/5985e5c584dd0649c450320f97d416d8cf2f5673.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c7f8370f143eb6e4607a36111947bd9330706944.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/007385340fc7dabb9ffd27bba7a3667ba9fba092.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/afcb405214b83e6feb78762d4da3255abdae1d70.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/1a70071136421f05353ab6de09c070db40366f58.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0305bd10d104265f6212638e6c62ccdf9d0c9a61.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/1f25c9e38711ed1dee15f1244d11b0db5b56e020.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/539a7f1505784549a5cb59931db867698a984dda.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/200fb06d9a9dc550113a04338dd473e858a89c1c.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/72d84a04abcf335e82ee83e6daf1a0170628f7e6.jpeg',
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
        'headlines': [
            'Премиум на набережной — дом сдан!',
            'Квартира на Петроградской у воды',
            'Премиальный дом на набережной Карповки',
            'Квартира мечты — премиум, Петроградская',
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
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/80a795ce0a57e6bdd1d209a8f4066f5dbbdc8183.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/06a3457b92c402578fb891fce2bd39b82af38fc6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/483f824c81943ddbe2bd58d4c858d0abdb677946.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/11f31233c97a6980e90d1f7df4bb075fcb2075cf.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fc1bb2f74363b2f37177b60e8f8ce0bf2d0b3a04.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/10ff2e12a1b4e2bed71a7e0c67914db4a4ab813a.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/349f6093c3579175e1b6c75a64bec906b5e27362.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/76b55d4cc0d6d73a7d2a4ca574f5d06dcc9ce74b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/47839a4c3e61fbd243c96a860c21716326270270.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/f8882f2e8331782ffa01705181aa90c83f290718.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/106aef53023e2a1203f47b0ed1a713dbf20089ed.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/13741d69832239cd3a64942b21a657c389434c6b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c9276ad0ea763b78cb0b5ae73159276730b419a4.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0e02de1a7ecb941368781e289f3144ba3a002963.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/09c1162dcd6b4a8d87e61d7597fd10e0c0a8e6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/61d9dd594b3ae06d63e8942055c757966dde44e6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/19ffef8e37b01ff6aa25e37a0d29e5b1a25e47.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/ffadc7fef362eb919c67ca9bf45a4aacd5bf1984.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fc9d68567661a27111e7c43c02138a6276a991be.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/b2e253b49b7159afb2cb09377ba121c4deac4570.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/059a9d1cd35b4c15d0c588feefbb72ab06a71ff1.jpg',
        ],
    },

    'ЖК «Северная корона Apartments»': {
        'slug': 'severnaykorona',  # Та же папка
        'class': 'премиум-класс',
        'metro': 'Петроградская',
        'usp': ['Апартаменты премиум-класса на Петроградской'],
        'headlines': [
            'Премиальные апартаменты на Петроградской',
            'Апартаменты на набережной — дом сдан',
            'Премиум-апартаменты у реки Карповки',
        ],
        'descriptions': {
            3: [
                'Премиальные апартаменты {area} кв.м на Петроградской. «Северная корона Apartments» — набережная Карповки, камерный формат. Дом сдан.',
            ],
        },
        'render_images': [
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/80a795ce0a57e6bdd1d209a8f4066f5dbbdc8183.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/06a3457b92c402578fb891fce2bd39b82af38fc6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/483f824c81943ddbe2bd58d4c858d0abdb677946.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/11f31233c97a6980e90d1f7df4bb075fcb2075cf.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fc1bb2f74363b2f37177b60e8f8ce0bf2d0b3a04.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/10ff2e12a1b4e2bed71a7e0c67914db4a4ab813a.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/349f6093c3579175e1b6c75a64bec906b5e27362.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/76b55d4cc0d6d73a7d2a4ca574f5d06dcc9ce74b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/47839a4c3e61fbd243c96a860c21716326270270.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/f8882f2e8331782ffa01705181aa90c83f290718.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/106aef53023e2a1203f47b0ed1a713dbf20089ed.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/13741d69832239cd3a64942b21a657c389434c6b.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/c9276ad0ea763b78cb0b5ae73159276730b419a4.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/0e02de1a7ecb941368781e289f3144ba3a002963.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/09c1162dcd6b4a8d87e61d7597fd10e0c0a8e6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/61d9dd594b3ae06d63e8942055c757966dde44e6.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/19ffef8e37b01ff6aa25e37a0d29e5b1a25e47.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/ffadc7fef362eb919c67ca9bf45a4aacd5bf1984.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/fc9d68567661a27111e7c43c02138a6276a991be.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/b2e253b49b7159afb2cb09377ba121c4deac4570.jpg',
            'https://storage.yandexcloud.net/psk-media/media/p/si/i/059a9d1cd35b4c15d0c588feefbb72ab06a71ff1.jpg',
        ],
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


def pick_headline(project_key, offer_id):
    """Pick an emotional selling headline for building-name field."""
    proj = PROJECTS.get(project_key)
    if not proj:
        return None

    headlines = proj.get('headlines', [])
    if not headlines:
        return None

    # Rotate headlines based on offer_id hash (same approach as descriptions)
    idx = int(hashlib.md5(str(offer_id).encode()).hexdigest(), 16) % len(headlines)
    return headlines[idx]


def make_image_url(base, folder, filename):
    """Build a properly URL-encoded image URL."""
    # Кодируем имя файла (пробелы, кириллица и т.д.)
    encoded_name = quote(filename, safe='')
    return f"{base}/{folder}/{encoded_name}"



def pick_images(project_key, offer_id, original_images):
    """
    Build image list (5 графических изображений, БЕЗ планировок):
    1. Эмоциональное lifestyle-фото из /render/all/ (feedhub.realty)
    2. Рендер проекта из API psk-info.ru (slider image #1)
    3. Рендер проекта из API psk-info.ru (slider image #2)
    4. Рендер проекта из API psk-info.ru (slider image #3)
    5. Эмоциональное lifestyle-фото из /render/all/ (feedhub.realty)
    """
    proj = PROJECTS.get(project_key)
    if not proj:
        return original_images

    render_urls = proj.get('render_images', [])

    h = int(hashlib.md5(str(offer_id).encode()).hexdigest(), 16)

    result = []
    used_lifestyle = set()

    # 1. Эмоциональное lifestyle-фото (первое)
    idx1 = h % len(ALL_LIFESTYLE_PHOTOS)
    result.append(make_image_url(IMAGE_BASE, 'all', ALL_LIFESTYLE_PHOTOS[idx1]))
    used_lifestyle.add(idx1)

    # 2-4. Три рендера проекта (или lifestyle-замены если рендеров мало)
    if render_urls:
        render_idx1 = h % len(render_urls)
        result.append(render_urls[render_idx1])

        if len(render_urls) > 1:
            render_idx2 = (h + 7) % len(render_urls)
            if render_idx2 == render_idx1:
                render_idx2 = (render_idx1 + 1) % len(render_urls)
            result.append(render_urls[render_idx2])
        else:
            extra_idx = (h + 37) % len(ALL_LIFESTYLE_PHOTOS)
            while extra_idx in used_lifestyle:
                extra_idx = (extra_idx + 1) % len(ALL_LIFESTYLE_PHOTOS)
            result.append(make_image_url(IMAGE_BASE, 'all', ALL_LIFESTYLE_PHOTOS[extra_idx]))
            used_lifestyle.add(extra_idx)

        if len(render_urls) > 2:
            render_idx3 = (h + 17) % len(render_urls)
            while render_idx3 in (render_idx1, render_idx2 if len(render_urls) > 1 else -1):
                render_idx3 = (render_idx3 + 1) % len(render_urls)
            result.append(render_urls[render_idx3])
        else:
            extra_idx = (h + 47) % len(ALL_LIFESTYLE_PHOTOS)
            while extra_idx in used_lifestyle:
                extra_idx = (extra_idx + 1) % len(ALL_LIFESTYLE_PHOTOS)
            result.append(make_image_url(IMAGE_BASE, 'all', ALL_LIFESTYLE_PHOTOS[extra_idx]))
            used_lifestyle.add(extra_idx)
    else:
        # Рендеров нет — три дополнительных lifestyle-фото
        for offset in (17, 37, 47):
            extra_idx = (h + offset) % len(ALL_LIFESTYLE_PHOTOS)
            while extra_idx in used_lifestyle:
                extra_idx = (extra_idx + 1) % len(ALL_LIFESTYLE_PHOTOS)
            result.append(make_image_url(IMAGE_BASE, 'all', ALL_LIFESTYLE_PHOTOS[extra_idx]))
            used_lifestyle.add(extra_idx)

    # 5. Эмоциональное lifestyle-фото (последнее, отличается от всех предыдущих)
    idx5 = (h + 13) % len(ALL_LIFESTYLE_PHOTOS)
    while idx5 in used_lifestyle:
        idx5 = (idx5 + 1) % len(ALL_LIFESTYLE_PHOTOS)
    result.append(make_image_url(IMAGE_BASE, 'all', ALL_LIFESTYLE_PHOTOS[idx5]))

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

        # Replace building-name with emotional selling headline
        headline = pick_headline(project_key, offer_id)
        if headline:
            bn_elem.text = headline

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
