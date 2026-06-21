from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

STARS_RATE = 1.26


def policy_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-Privacy-Policy-06-18")],
        [InlineKeyboardButton("📋 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-06-18-24")],
        [InlineKeyboardButton("✅ Принимаю оба документа", callback_data="agreed_policy")]
    ])


def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["🛒 Купить", "👤 Профиль"],
        ["🏆 Лидеры", "✨ Конкурсы"],
        ["💎 Реферальная система", "🏷 Промокод"],
        ["🆘 Поддержка", "📕 Правила"],
        ["⭐️ Отзывы"]
    ], resize_keyboard=True)


def categories_keyboard(cats: list):
    buttons = []
    icons = ["💎", "🎮", "🛍", "🎯", "🌟", "💫", "🔥", "⚡️"]
    for i, cat in enumerate(cats):
        icon = icons[i % len(icons)]
        buttons.append([InlineKeyboardButton(f"{cat['name']}", callback_data=f"cat_{cat['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)


def subcategories_keyboard(subcats: list, cat_id: int):
    buttons = []
    for sc in subcats:
        buttons.append([InlineKeyboardButton(sc['name'], callback_data=f"subcat_{sc['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад к категориям", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(buttons)


def subscribe_check_keyboard(channels: list):
    buttons = []
    for ch in channels:
        url = ch.get('invite_url') or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        buttons.append([InlineKeyboardButton(f"📢 {ch['channel_title']}", url=url)])
    buttons.append([InlineKeyboardButton("✅ Я подписался — проверить", callback_data="check_subscriptions")])
    return InlineKeyboardMarkup(buttons)


def stars_quantity_keyboard(selected: int = 0):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐️ 50 звёзд", callback_data="stars_50"),
            InlineKeyboardButton("🌟 100 звёзд", callback_data="stars_100"),
        ],
        [
            InlineKeyboardButton("💫 150 звёзд", callback_data="stars_150"),
            InlineKeyboardButton("✨ 200 звёзд", callback_data="stars_200"),
        ],
        [InlineKeyboardButton("🔢 Ввести своё количество", callback_data="stars_custom")],
        [InlineKeyboardButton("✅ Продолжить к оплате", callback_data="stars_continue")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]
    ])


def stars_recipient_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋 Себе", callback_data="stars_recipient_me")],
        [InlineKeyboardButton("🎁 Другому человеку", callback_data="stars_recipient_other")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_stars")]
    ])


def payment_keyboard_stars(qty: int, rate: float = STARS_RATE):
    price = round(qty * rate, 2)
    crypto_price = round(price * 1.015, 2)
    yoo_price = round(price * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟡 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"pay_crypto_stars_{qty}")],
        [InlineKeyboardButton(f"🔵 YooMoney — {yoo_price:.2f}₽", callback_data=f"pay_yoo_stars_{qty}")],
        [InlineKeyboardButton(f"💰 Баланс — {price:.2f}₽", callback_data=f"pay_balance_stars_{qty}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_stars")]
    ])


def confirm_balance_keyboard(callback_yes: str, callback_no: str = "cancel_payment"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Оплатить с баланса", callback_data=callback_yes)],
        [InlineKeyboardButton("❌ Отмена", callback_data=callback_no)]
    ])


def crypto_pay_keyboard(pay_url: str, paid_callback: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Перейти к оплате (Crypto Bot)", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=paid_callback)]
    ])


def yoo_pay_keyboard(paid_callback: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Оплатить через YooMoney", url="https://yoomoney.ru/to/4100119097043413/0")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=paid_callback)]
    ])


def premium_plans_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 1 месяц — 319₽", callback_data="premium_1m")],
        [InlineKeyboardButton("💫 3 месяца — 1050₽", callback_data="premium_3m")],
        [InlineKeyboardButton("✨ 6 месяцев — 1350₽", callback_data="premium_6m")],
        [InlineKeyboardButton("👑 12 месяцев — 2550₽", callback_data="premium_12m")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]
    ])


PREMIUM_PRICES = {
    "1m": {"rub": 319, "stars": 250, "label": "1 месяц"},
    "3m": {"rub": 1050, "stars": 1000, "label": "3 месяца"},
    "6m": {"rub": 1350, "stars": 1500, "label": "6 месяцев"},
    "12m": {"rub": 2550, "stars": 2500, "label": "12 месяцев"},
}


def premium_payment_keyboard(plan: str):
    p = PREMIUM_PRICES[plan]
    rub = p["rub"]
    crypto_price = round(rub * 1.015, 2)
    yoo_price = round(rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟡 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"pay_crypto_premium_{plan}")],
        [InlineKeyboardButton(f"🔵 YooMoney — {yoo_price:.2f}₽", callback_data=f"pay_yoo_premium_{plan}")],
        [InlineKeyboardButton(f"🟢 Баланс — {rub}₽", callback_data=f"pay_balance_premium_{plan}")],
        [InlineKeyboardButton(f"⭐️ Telegram Stars — {p['stars']} ⭐️", callback_data=f"pay_stars_premium_{plan}")],
        [InlineKeyboardButton("🔙 Назад к планам", callback_data="sub_premium")]
    ])


USERNAMES = {
    "biden_com": {"label": "@biden_com | не нфт", "rub": 100, "stars": 75},
    "ceobocc": {"label": "@ceobocc | не нфт", "rub": 100, "stars": 75},
    "ceo_bocc": {"label": "@ceo_bocc | не нфт", "rub": 100, "stars": 75},
    "beeryPuccy": {"label": "@beeryPuccy | не нфт", "rub": 100, "stars": 75},
}


def username_payment_keyboard(username_key: str, price_rub: float):
    rub = price_rub
    crypto_price = round(rub * 1.015, 2)
    yoo_price = round(rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟡 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"pay_crypto_username_{username_key}")],
        [InlineKeyboardButton(f"🔵 YooMoney — {yoo_price:.2f}₽", callback_data=f"pay_yoo_username_{username_key}")],
        [InlineKeyboardButton(f"🟢 Баланс — {rub:.0f}₽", callback_data=f"pay_balance_username_{username_key}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_usernames")]
    ])


GIFTS = {
    "bear": {"label": "🧸 Мишка | 13 ⭐️", "rub": 19, "stars": 13},
    "gift": {"label": "🎁 Подарок | 21 ⭐️", "rub": 29, "stars": 21},
    "rocket": {"label": "🚀 Ракета | 43 ⭐️", "rub": 60, "stars": 43},
    "ring": {"label": "💍 Кольцо | 85 ⭐️", "rub": 120, "stars": 85},
}


def gift_payment_keyboard(gift_key: str, price_rub: float):
    rub = price_rub
    crypto_price = round(rub * 1.015, 2)
    yoo_price = round(rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟡 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"pay_crypto_gift_{gift_key}")],
        [InlineKeyboardButton(f"🔵 YooMoney — {yoo_price:.2f}₽", callback_data=f"pay_yoo_gift_{gift_key}")],
        [InlineKeyboardButton(f"🟢 Баланс — {rub:.0f}₽", callback_data=f"pay_balance_gift_{gift_key}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_gifts")]
    ])


def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton("🧾 История покупок", callback_data="purchase_history")],
        [InlineKeyboardButton("💎 Реферальная система", callback_data="referral_profile")],
        [InlineKeyboardButton("📕 Правила", url="https://telegra.ph/Polzovatelskoe-soglashenie-06-18-24")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main")]
    ])


def deposit_payment_keyboard(amount: float):
    crypto_price = round(amount * 1.015, 2)
    yoo_price = round(amount * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟡 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"dep_crypto_{amount}")],
        [InlineKeyboardButton(f"🔵 YooMoney — {yoo_price:.2f}₽", callback_data=f"dep_yoo_{amount}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="deposit")]
    ])


def back_to_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main")]
    ])


def back_to_profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад в профиль", callback_data="back_to_profile")]
    ])


# ─── Dynamic product keyboard (new format) ────────────────────────────────────

def dynamic_product_info_keyboard(product_id: int, delivery_type: str, qty: int, price_rub: float,
                                   payment_methods: list, stars_price: int = None):
    delivery_label = "⚡️ Авто" if delivery_type == 'auto' else "👤 Ручная"
    buttons = [
        [
            InlineKeyboardButton(f"📦 В наличии: {qty} шт.", callback_data="noop_info"),
            InlineKeyboardButton(f"⚡️ Выдача: {delivery_label}", callback_data="noop_info"),
        ],
        [
            InlineKeyboardButton(f"🏷 Цена: {price_rub:.0f}₽", callback_data="noop_info"),
        ],
        [InlineKeyboardButton("🛒 Купить сейчас", callback_data=f"dynbuy_{product_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]
    ]
    return InlineKeyboardMarkup(buttons)


def dynamic_product_payment_keyboard(product_id: int, payment_methods: list, price_rub: float = 0, stars_price: int = None):
    buttons = []
    if 'crypto' in payment_methods:
        price_str = f" — {price_rub * 1.015:.0f}₽" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"🟡 Crypto Bot{price_str}", callback_data=f"dynpay_crypto_{product_id}")])
    if 'yoo' in payment_methods:
        price_str = f" — {price_rub * 1.03:.0f}₽" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"🔵 YooMoney{price_str}", callback_data=f"dynpay_yoo_{product_id}")])
    if 'balance' in payment_methods:
        price_str = f" — {price_rub:.0f}₽" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"🟢 Баланс{price_str}", callback_data=f"dynpay_balance_{product_id}")])
    if 'stars' in payment_methods:
        stars_str = f" — {stars_price} ⭐️" if stars_price else ""
        buttons.append([InlineKeyboardButton(f"⭐️ Telegram Stars{stars_str}", callback_data=f"dynpay_stars_{product_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад к товару", callback_data=f"dynprod_{product_id}")])
    return InlineKeyboardMarkup(buttons)


def dynamic_product_keyboard(product_id: int, payment_methods: list, price_rub: float = 0, stars_price: int = None):
    return dynamic_product_payment_keyboard(product_id, payment_methods, price_rub, stars_price)


# ─── Admin keyboard ──────────────────────────────────────────────────────────

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("🎁 Добавить товар", callback_data="admin_product_wizard"),
         InlineKeyboardButton("✏️ Управление", callback_data="admin_management")],
        [InlineKeyboardButton("🧩 Добавить категорию", callback_data="admin_add_category"),
         InlineKeyboardButton("🧩 Добавить подкат.", callback_data="admin_add_subcategory")],
        [InlineKeyboardButton("🔑 Обязательные подписки", callback_data="admin_subscriptions")],
        [InlineKeyboardButton("📦 Склад товаров", callback_data="admin_stock")],
        [InlineKeyboardButton("➕ Добавить промокод", callback_data="admin_add_promo")],
        [InlineKeyboardButton("🖼 Баннеры разделов", callback_data="admin_banners")],
        [InlineKeyboardButton("✨ Управление конкурсами", callback_data="admin_contests")],
        [InlineKeyboardButton("➕ Добавить администратора", callback_data="admin_add_admin")],
        [InlineKeyboardButton("🧨 Снять администратора", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("📤 Рассылка пользователям", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Пополнить баланс юзера", callback_data="admin_topup")],
    ])


# ─── Product wizard keyboards ─────────────────────────────────────────────────

def wizard_main_keyboard(has_stars: bool = False, has_banner: bool = False):
    rows = [
        [InlineKeyboardButton("✏️ Название товара", callback_data="adminwiz_name"),
         InlineKeyboardButton("📌 Описание", callback_data="adminwiz_desc")],
        [InlineKeyboardButton("💳 Стоимость", callback_data="adminwiz_price"),
         InlineKeyboardButton("🏷 Количество", callback_data="adminwiz_qty")],
        [InlineKeyboardButton("📦 Тип выдачи", callback_data="adminwiz_delivery")],
        [InlineKeyboardButton("💳 Способы оплаты", callback_data="adminwiz_payment")],
        [InlineKeyboardButton("🖼 Добавить баннер", callback_data="adminwiz_banner")],
    ]
    if has_stars:
        rows.append([InlineKeyboardButton("⭐️ Цена в звёздах", callback_data="adminwiz_stars")])
    rows.append([InlineKeyboardButton("✅ Добавить товар", callback_data="adminwiz_confirm")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="adminwiz_cancel")])
    return InlineKeyboardMarkup(rows)


def wizard_qty_keyboard(stock: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📦 Текущее кол-во: {stock} шт.", callback_data="noop")],
        [
            InlineKeyboardButton("➕1", callback_data="adminwiz_qty_p1"),
            InlineKeyboardButton("➕5", callback_data="adminwiz_qty_p5"),
            InlineKeyboardButton("➕100", callback_data="adminwiz_qty_p100"),
        ],
        [
            InlineKeyboardButton("➖1", callback_data="adminwiz_qty_m1"),
            InlineKeyboardButton("➖5", callback_data="adminwiz_qty_m5"),
            InlineKeyboardButton("➖100", callback_data="adminwiz_qty_m100"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="adminwiz_back_main")],
    ])


def wizard_delivery_keyboard(delivery_type: str):
    auto_mark = "✅ " if delivery_type == 'auto' else ""
    manual_mark = "✅ " if delivery_type == 'manual' else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{auto_mark}⚡️ Автовыдача", callback_data="adminwiz_set_delivery_auto")],
        [InlineKeyboardButton(f"{manual_mark}👤 Ручная выдача", callback_data="adminwiz_set_delivery_manual")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adminwiz_back_main")],
    ])


def wizard_payment_keyboard(selected: list):
    def mark(m):
        return "✅ " if m in selected else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{mark('crypto')}🤖 Crypto Bot", callback_data="adminwiz_togglepay_crypto"),
         InlineKeyboardButton(f"{mark('yoo')}💳 YooMoney", callback_data="adminwiz_togglepay_yoo")],
        [InlineKeyboardButton(f"{mark('balance')}💰 Баланс", callback_data="adminwiz_togglepay_balance"),
         InlineKeyboardButton(f"{mark('stars')}⭐️ Stars", callback_data="adminwiz_togglepay_stars")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adminwiz_back_main")],
    ])


def wizard_text_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="adminwiz_back_main")]
    ])


# ─── Admin subscriptions keyboards ────────────────────────────────────────────

def subscriptions_keyboard(channels: list):
    buttons = []
    for ch in channels:
        status = "🟢" if ch['is_active'] else "🔴"
        buttons.append([
            InlineKeyboardButton(
                f"{status} {ch['channel_title']}",
                callback_data=f"adminsub_toggle_{ch['id']}"
            ),
            InlineKeyboardButton("🗑", callback_data=f"adminsub_del_{ch['id']}")
        ])
    buttons.append([InlineKeyboardButton("➕ Добавить канал", callback_data="adminsub_add")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(buttons)


# ─── Management keyboards ──────────────────────────────────────────────────────

def management_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Категории", callback_data="manage_categories")],
        [InlineKeyboardButton("🗂 Подкатегории", callback_data="manage_subcategories")],
        [InlineKeyboardButton("🗂 Товары", callback_data="manage_products")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")],
    ])


def manage_categories_keyboard(cats: list):
    buttons = []
    for cat in cats:
        buttons.append([
            InlineKeyboardButton(cat['name'], callback_data=f"manage_cat_view_{cat['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"manage_cat_del_{cat['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_management")])
    return InlineKeyboardMarkup(buttons)


def manage_subcats_keyboard(subcats: list):
    buttons = []
    for sc in subcats:
        buttons.append([
            InlineKeyboardButton(f"{sc['cat_name']} → {sc['name']}", callback_data=f"manage_subcat_view_{sc['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"manage_subcat_del_{sc['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_management")])
    return InlineKeyboardMarkup(buttons)


def manage_products_keyboard(products: list):
    buttons = []
    for p in products:
        type_icon = "🧩" if p['product_type'] == 'username' else ("🎁" if p['product_type'] == 'gift' else "📦")
        buttons.append([
            InlineKeyboardButton(f"{type_icon} {p['label']}", callback_data=f"manage_prod_view_{p['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"manage_prod_del_{p['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_management")])
    return InlineKeyboardMarkup(buttons)


# ─── Order chat keyboard ──────────────────────────────────────────────────────

def order_chat_user_keyboard(order_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Написать продавцу", callback_data=f"chat_open_{order_id}")],
        [InlineKeyboardButton("✅ Завершить чат и подтвердить", callback_data=f"chat_close_{order_id}")],
    ])


def order_chat_admin_keyboard(order_id: int, user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ответить покупателю", callback_data=f"admin_chat_reply_{order_id}_{user_id}")],
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data=f"admin_order_done_{order_id}_{user_id}")],
        [InlineKeyboardButton("❌ Отклонить заказ", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
    ])


# ─── Contests keyboards ───────────────────────────────────────────────────────

def contests_keyboard(contests: list):
    buttons = []
    for c in contests:
        status = "🟢" if c['is_active'] else "🔴"
        buttons.append([InlineKeyboardButton(f"{status} {c['title']}", callback_data=f"contest_{c['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)


def contest_detail_keyboard(contest_id: int, is_participant: bool):
    buttons = []
    if not is_participant:
        buttons.append([InlineKeyboardButton("✅ Участвовать в конкурсе", callback_data=f"contest_join_{contest_id}")])
    else:
        buttons.append([InlineKeyboardButton("✅ Вы уже участвуете", callback_data="noop_info")])
    buttons.append([InlineKeyboardButton("🔙 Назад к конкурсам", callback_data="contests_list")])
    return InlineKeyboardMarkup(buttons)


def admin_contests_keyboard(contests: list):
    buttons = [[InlineKeyboardButton("➕ Создать новый конкурс", callback_data="admin_contest_create")]]
    for c in contests:
        status = "🟢" if c['is_active'] else "🔴"
        buttons.append([
            InlineKeyboardButton(f"{status} {c['title']}", callback_data=f"admin_contest_view_{c['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"admin_contest_del_{c['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(buttons)


def admin_contest_detail_keyboard(contest_id: int, is_active: bool):
    status_label = "🔴 Деактивировать" if is_active else "🟢 Активировать"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(status_label, callback_data=f"admin_contest_toggle_{contest_id}")],
        [InlineKeyboardButton("🗑 Удалить конкурс", callback_data=f"admin_contest_del_{contest_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_contests")],
    ])


# ─── Banners keyboard ─────────────────────────────────────────────────────────

SECTION_NAMES = {
    "main": "🏠 Главное меню",
    "shop": "🛒 Магазин",
    "stars": "⭐️ Звёзды",
    "premium": "💠 Премиум",
    "usernames": "🧩 Юзернеймы",
    "gifts": "🧸 Подарки",
    "contests": "✨ Конкурсы",
    "leaders": "🏆 Лидеры",
    "robux": "💎 Robux",
    "robux_gamepass": "🎮 Геймпасс",
    "robux_gift": "🎁 Подарочная карта",
    "robux_packs": "🛍 Паки",
    "robux_group": "👤 Группой",
    "robux_superpasses": "⭐️ Супер-пассы",
}


def admin_banners_keyboard(existing_banners: dict):
    buttons = []
    for key, name in SECTION_NAMES.items():
        has = "🖼 " if key in existing_banners else "➕ "
        buttons.append([InlineKeyboardButton(f"{has}{name}", callback_data=f"admin_banner_set_{key}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(buttons)


# ─── Admin settings keyboard ──────────────────────────────────────────────────

def admin_settings_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐️ Изменить курс звёзд", callback_data="admin_settings_stars_rate")],
        [InlineKeyboardButton("👤 Получатель звёзд", callback_data="admin_settings_stars_recipient")],
        [InlineKeyboardButton("💎 Настройки Robux", callback_data="admin_robux_settings")],
        [InlineKeyboardButton("💰 Курс группы (₽)", callback_data="admin_robux_group_rate_rub")],
        [InlineKeyboardButton("⭐️ Курс группы (Stars)", callback_data="admin_robux_group_rate_stars")],
        [InlineKeyboardButton("🔗 Ссылка на группу Roblox", callback_data="admin_robux_group_link")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")],
    ])


# ─── Robux keyboards ──────────────────────────────────────────────────────────

def robux_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Геймпассом (5-7д)", callback_data="robux_gamepass")],
        [InlineKeyboardButton("💎 Подарочная карта", callback_data="robux_giftcard")],
        [InlineKeyboardButton("🛍 Паки (с заходом)", callback_data="robux_packs")],
        [InlineKeyboardButton("👤 Группой (14д)", callback_data="robux_group")],
        [InlineKeyboardButton("⭐️ Супер-пассы", callback_data="robux_superpasses")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")],
    ])


def robux_gamepass_keyboard(qty: int = 0, recipient: str = ""):
    qty_text = f"{qty} R$" if qty else "не выбрано"
    rec_text = recipient if recipient else "не выбран"
    price_rub = round(qty * 0.67, 2) if qty else 0
    price_stars = round(qty * 0.45) if qty else 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Количество: {qty_text}", callback_data="robux_gp_qty")],
        [InlineKeyboardButton(f"👤 Получатель: {rec_text}", callback_data="robux_gp_recipient")],
        [InlineKeyboardButton(f"💳 Купить" + (f" — {price_rub:.2f}₽" if qty else ""), callback_data="robux_gp_buy")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_main")],
    ])


ROBUX_GIFT_CARDS = [
    {"robux": 100, "rub": 279, "stars": 200, "region": "Global"},
    {"robux": 200, "rub": 279, "stars": 200, "region": "Global"},
    {"robux": 300, "rub": 279, "stars": 200, "region": "Global"},
    {"robux": 400, "rub": 379, "stars": 300, "region": "Global"},
    {"robux": 500, "rub": 499, "stars": 400, "region": "Global"},
    {"robux": 600, "rub": 579, "stars": 500, "region": "Global"},
    {"robux": 800, "rub": 759, "stars": 650, "region": "Global"},
]

ROBUX_PACKS = [
    {"robux": 80, "rub": 95},
    {"robux": 160, "rub": 180},
    {"robux": 240, "rub": 265},
    {"robux": 320, "rub": 345},
    {"robux": 500, "rub": 430},
    {"robux": 740, "rub": 680},
    {"robux": 820, "rub": 760},
    {"robux": 1000, "rub": 855},
    {"robux": 1240, "rub": 1090},
]


def robux_giftcard_keyboard():
    buttons = []
    for card in ROBUX_GIFT_CARDS:
        buttons.append([InlineKeyboardButton(
            f"💎 {card['robux']} R$ — {card['rub']}₽ / {card['stars']}⭐️",
            callback_data=f"robux_gc_{card['robux']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="robux_main")])
    return InlineKeyboardMarkup(buttons)


def robux_giftcard_payment_keyboard(robux: int, rub: float, stars: int):
    crypto_price = round(rub * 1.015, 2)
    yoo_price = round(rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"robux_gc_pay_crypto_{robux}")],
        [InlineKeyboardButton(f"💳 YooMoney — {yoo_price:.2f}₽", callback_data=f"robux_gc_pay_yoo_{robux}")],
        [InlineKeyboardButton(f"💰 Баланс — {rub:.0f}₽", callback_data=f"robux_gc_pay_balance_{robux}")],
        [InlineKeyboardButton(f"⭐️ Telegram Stars — {stars} ⭐️", callback_data=f"robux_gc_pay_stars_{robux}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_giftcard")],
    ])


def robux_packs_keyboard():
    buttons = []
    for pack in ROBUX_PACKS:
        buttons.append([InlineKeyboardButton(
            f"🛍 {pack['robux']} R$ — {pack['rub']}₽",
            callback_data=f"robux_pack_{pack['robux']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="robux_main")])
    return InlineKeyboardMarkup(buttons)


def robux_packs_payment_keyboard(robux: int, rub: float):
    crypto_price = round(rub * 1.015, 2)
    yoo_price = round(rub * 1.03, 2)
    stars = round(rub / 1.26)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"robux_pack_pay_crypto_{robux}")],
        [InlineKeyboardButton(f"💳 YooMoney — {yoo_price:.2f}₽", callback_data=f"robux_pack_pay_yoo_{robux}")],
        [InlineKeyboardButton(f"💰 Баланс — {rub:.0f}₽", callback_data=f"robux_pack_pay_balance_{robux}")],
        [InlineKeyboardButton(f"⭐️ Telegram Stars — {stars} ⭐️", callback_data=f"robux_pack_pay_stars_{robux}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_packs")],
    ])


def robux_group_keyboard(qty: int = 0, recipient: str = "", rate_rub: float = 0.60, rate_stars: float = 0.45):
    qty_text = f"{qty} R$" if qty else "не выбрано"
    rec_text = recipient if recipient else "не указан"
    price_rub = round(qty * rate_rub, 2) if qty else 0
    price_stars = round(qty * rate_stars) if qty else 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Количество: {qty_text}", callback_data="robux_group_qty")],
        [InlineKeyboardButton(f"👤 Ваш ник Roblox: {rec_text}", callback_data="robux_group_recipient")],
        [InlineKeyboardButton(f"✅ Купить" + (f" — {price_rub:.2f}₽" if qty else ""), callback_data="robux_group_buy")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_main")],
    ])


ROBLOX_SUPERPASSES_GAMES = [
    "Adopt Me!", "Brookhaven RP", "Pet Simulator X",
    "Murder Mystery 2", "Tower of Hell", "Arsenal",
    "Natural Disaster Survival", "Theme Park Tycoon 2",
    "Work at a Pizza Place", "Jailbreak", "Piggy",
    "Royale High", "Bloxburg", "Speed Run 4",
    "Flee the Facility", "Super Golf", "Car Crushers 2",
    "Mining Simulator 2", "Islands", "Shindo Life",
]


def robux_superpasses_keyboard():
    buttons = []
    for i in range(0, len(ROBLOX_SUPERPASSES_GAMES), 2):
        row = []
        row.append(InlineKeyboardButton(
            ROBLOX_SUPERPASSES_GAMES[i],
            callback_data=f"robux_sp_game_{i}"
        ))
        if i + 1 < len(ROBLOX_SUPERPASSES_GAMES):
            row.append(InlineKeyboardButton(
                ROBLOX_SUPERPASSES_GAMES[i + 1],
                callback_data=f"robux_sp_game_{i + 1}"
            ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="robux_main")])
    return InlineKeyboardMarkup(buttons)


def robux_superpass_buy_keyboard(game_idx: int, qty: int = 0, recipient: str = ""):
    game = ROBLOX_SUPERPASSES_GAMES[game_idx] if game_idx < len(ROBLOX_SUPERPASSES_GAMES) else "Игра"
    qty_text = f"{qty} R$" if qty else "не выбрано"
    rec_text = recipient if recipient else "не выбран"
    price_rub = round(qty * 0.59, 2) if qty else 0
    price_stars = round(qty * 0.35) if qty else 0
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Количество R$: {qty_text}", callback_data=f"robux_sp_qty_{game_idx}")],
        [InlineKeyboardButton(f"👤 Получатель: {rec_text}", callback_data=f"robux_sp_recipient_{game_idx}")],
        [InlineKeyboardButton(f"💳 Купить" + (f" — {price_rub:.2f}₽" if qty else ""), callback_data=f"robux_sp_buy_{game_idx}")],
        [InlineKeyboardButton("🔙 Назад к играм", callback_data="robux_superpasses")],
    ])


def robux_superpass_payment_keyboard(game_idx: int, qty: int):
    price_rub = round(qty * 0.59, 2)
    price_stars = round(qty * 0.35)
    crypto_price = round(price_rub * 1.015, 2)
    yoo_price = round(price_rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"robux_sp_pay_crypto_{game_idx}_{qty}")],
        [InlineKeyboardButton(f"💳 YooMoney — {yoo_price:.2f}₽", callback_data=f"robux_sp_pay_yoo_{game_idx}_{qty}")],
        [InlineKeyboardButton(f"💰 Баланс — {price_rub:.2f}₽", callback_data=f"robux_sp_pay_balance_{game_idx}_{qty}")],
        [InlineKeyboardButton(f"⭐️ Stars — {price_stars} ⭐️", callback_data=f"robux_sp_pay_stars_{game_idx}_{qty}")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"robux_sp_game_{game_idx}")],
    ])


def robux_gamepass_payment_keyboard(qty: int, recipient: str):
    price_rub = round(qty * 0.67, 2)
    price_stars = round(qty * 0.45)
    crypto_price = round(price_rub * 1.015, 2)
    yoo_price = round(price_rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"robux_gp_pay_crypto_{qty}")],
        [InlineKeyboardButton(f"💳 YooMoney — {yoo_price:.2f}₽", callback_data=f"robux_gp_pay_yoo_{qty}")],
        [InlineKeyboardButton(f"💰 Баланс — {price_rub:.2f}₽", callback_data=f"robux_gp_pay_balance_{qty}")],
        [InlineKeyboardButton(f"⭐️ Stars — {price_stars} ⭐️", callback_data=f"robux_gp_pay_stars_{qty}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_gamepass")],
    ])


def robux_group_payment_keyboard(qty: int, recipient: str, rate_rub: float = 0.60, rate_stars: float = 0.45):
    price_rub = round(qty * rate_rub, 2)
    price_stars = round(qty * rate_stars)
    crypto_price = round(price_rub * 1.015, 2)
    yoo_price = round(price_rub * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot — {crypto_price:.2f}₽", callback_data=f"robux_group_pay_crypto_{qty}")],
        [InlineKeyboardButton(f"💳 YooMoney — {yoo_price:.2f}₽", callback_data=f"robux_group_pay_yoo_{qty}")],
        [InlineKeyboardButton(f"💰 Баланс — {price_rub:.2f}₽", callback_data=f"robux_group_pay_balance_{qty}")],
        [InlineKeyboardButton(f"⭐️ Stars — {price_stars} ⭐️", callback_data=f"robux_group_pay_stars_{qty}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="robux_group")],
    ])


def roblox_user_confirm_keyboard(user_id: int, context_key: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Это я / он", callback_data=f"roblox_confirm_{user_id}_{context_key}")],
        [InlineKeyboardButton("🔍 Выбрать другого", callback_data=f"roblox_search_again_{context_key}")],
    ])
