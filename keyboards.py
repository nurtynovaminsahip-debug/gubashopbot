from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def policy_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Политика проекта", url="https://telegra.ph/Politika-proekta-GubaShop-06-01")],
        [InlineKeyboardButton("✅ Я ознакомился", callback_data="agreed_policy")]
    ])


def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["🛒Купить", "👤Профиль"],
        ["💎Реферальная система", "🏷Промокод"],
        ["🆘Поддержка", "📕Правила"],
        ["⭐️Отзывы"]
    ], resize_keyboard=True)


def categories_keyboard(cats: list):
    buttons = []
    for cat in cats:
        buttons.append([InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)


def subcategories_keyboard(subcats: list, cat_id: int):
    buttons = []
    for sc in subcats:
        buttons.append([InlineKeyboardButton(sc['name'], callback_data=f"subcat_{sc['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(buttons)


def subscribe_check_keyboard(channels: list):
    buttons = []
    for ch in channels:
        url = ch.get('invite_url') or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        buttons.append([InlineKeyboardButton(f"📢 {ch['channel_title']}", url=url)])
    buttons.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_subscriptions")])
    return InlineKeyboardMarkup(buttons)


def stars_quantity_keyboard(selected: int = 0):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("50 ⭐️", callback_data="stars_50"),
            InlineKeyboardButton("100 ⭐️", callback_data="stars_100"),
        ],
        [
            InlineKeyboardButton("150 ⭐️", callback_data="stars_150"),
            InlineKeyboardButton("200 ⭐️", callback_data="stars_200"),
        ],
        [InlineKeyboardButton("✏️ Ввести количество", callback_data="stars_custom")],
        [InlineKeyboardButton("▶️ Продолжить", callback_data="stars_continue")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]
    ])


def payment_keyboard_stars(qty: int):
    price = round(qty * 1.29, 2)
    crypto_price = round(qty * 1.29 * 1.015, 2)
    yoo_price = round(qty * 1.29 * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot ({crypto_price:.2f}₽)", callback_data=f"pay_crypto_stars_{qty}")],
        [InlineKeyboardButton(f"💳 YooMoney ({yoo_price:.2f}₽)", callback_data=f"pay_yoo_stars_{qty}")],
        [InlineKeyboardButton(f"💰 Баланс ({price:.2f}₽)", callback_data=f"pay_balance_stars_{qty}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_stars")]
    ])


def confirm_balance_keyboard(callback_yes: str, callback_no: str = "cancel_payment"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить", callback_data=callback_yes)],
        [InlineKeyboardButton("❌ Отмена", callback_data=callback_no)]
    ])


def crypto_pay_keyboard(pay_url: str, paid_callback: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=paid_callback)]
    ])


def yoo_pay_keyboard(paid_callback: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить", url="https://yoomoney.ru/to/4100119097043413/0")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=paid_callback)]
    ])


def premium_plans_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐️ 1 месяц — 319₽", callback_data="premium_1m")],
        [InlineKeyboardButton("⭐️ 3 месяца — 1050₽", callback_data="premium_3m")],
        [InlineKeyboardButton("⭐️ 6 месяцев — 1350₽", callback_data="premium_6m")],
        [InlineKeyboardButton("⭐️ 12 месяцев — 2550₽", callback_data="premium_12m")],
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
        [InlineKeyboardButton(f"🤖 Crypto Bot ({crypto_price:.2f}₽)", callback_data=f"pay_crypto_premium_{plan}")],
        [InlineKeyboardButton(f"💳 YooMoney ({yoo_price:.2f}₽)", callback_data=f"pay_yoo_premium_{plan}")],
        [InlineKeyboardButton(f"💰 Баланс ({rub}₽)", callback_data=f"pay_balance_premium_{plan}")],
        [InlineKeyboardButton(f"⭐️ Оплатить звездами ({p['stars']} ⭐️)", callback_data=f"pay_stars_premium_{plan}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_premium")]
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
        [InlineKeyboardButton(f"🤖 Crypto Bot ({crypto_price:.2f}₽)", callback_data=f"pay_crypto_username_{username_key}")],
        [InlineKeyboardButton(f"💳 YooMoney ({yoo_price:.2f}₽)", callback_data=f"pay_yoo_username_{username_key}")],
        [InlineKeyboardButton(f"💰 Баланс ({rub:.0f}₽)", callback_data=f"pay_balance_username_{username_key}")],
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
        [InlineKeyboardButton(f"🤖 Crypto Bot ({crypto_price:.2f}₽)", callback_data=f"pay_crypto_gift_{gift_key}")],
        [InlineKeyboardButton(f"💳 YooMoney ({yoo_price:.2f}₽)", callback_data=f"pay_yoo_gift_{gift_key}")],
        [InlineKeyboardButton(f"💰 Баланс ({rub:.0f}₽)", callback_data=f"pay_balance_gift_{gift_key}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="sub_gifts")]
    ])


def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton("📌 История покупок", callback_data="purchase_history")],
        [InlineKeyboardButton("💎 Реферальная система", callback_data="referral_profile")],
        [InlineKeyboardButton("📕 Правила", url="https://telegra.ph/Politika-proekta-GubaShop-06-01")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ])


def deposit_payment_keyboard(amount: float):
    crypto_price = round(amount * 1.015, 2)
    yoo_price = round(amount * 1.03, 2)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🤖 Crypto Bot ({crypto_price:.2f}₽)", callback_data=f"dep_crypto_{amount}")],
        [InlineKeyboardButton(f"💳 Yoo Money ({yoo_price:.2f}₽)", callback_data=f"dep_yoo_{amount}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="deposit")]
    ])


def back_to_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ])


def back_to_profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_profile")]
    ])


# ─── Admin keyboard ──────────────────────────────────────────────────────────

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🎁 Добавить товар", callback_data="admin_product_wizard"),
         InlineKeyboardButton("✏️ Управление", callback_data="admin_management")],
        [InlineKeyboardButton("🧩 Добавить категорию", callback_data="admin_add_category"),
         InlineKeyboardButton("🧩 Добавить подкат.", callback_data="admin_add_subcategory")],
        [InlineKeyboardButton("🔑 Подписки", callback_data="admin_subscriptions")],
        [InlineKeyboardButton("📦 Управление складом", callback_data="admin_stock")],
        [InlineKeyboardButton("➕ Добавить промокод", callback_data="admin_add_promo")],
        [InlineKeyboardButton("➕ Добавить администратора", callback_data="admin_add_admin")],
        [InlineKeyboardButton("🧨 Снять администратора", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("📤 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Пополнить баланс юзера", callback_data="admin_topup")],
    ])


# ─── Product wizard keyboards ─────────────────────────────────────────────────

def wizard_main_keyboard(has_stars: bool = False):
    rows = [
        [InlineKeyboardButton("✏️ Название товара", callback_data="adminwiz_name"),
         InlineKeyboardButton("📌 Описание", callback_data="adminwiz_desc")],
        [InlineKeyboardButton("💳 Стоимость товара", callback_data="adminwiz_price"),
         InlineKeyboardButton("🏷 Кол-во штук", callback_data="adminwiz_qty")],
        [InlineKeyboardButton("📦 Тип выдачи", callback_data="adminwiz_delivery")],
        [InlineKeyboardButton("💳 Способы оплаты", callback_data="adminwiz_payment")],
    ]
    if has_stars:
        rows.append([InlineKeyboardButton("⭐️ Цена в звёздах", callback_data="adminwiz_stars")])
    rows.append([InlineKeyboardButton("➕ Добавить товар", callback_data="adminwiz_confirm")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="adminwiz_cancel")])
    return InlineKeyboardMarkup(rows)


def wizard_qty_keyboard(stock: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Количество штук в наличии:", callback_data="noop")],
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
         InlineKeyboardButton(f"{mark('yoo')}💳 Yoo Money", callback_data="adminwiz_togglepay_yoo")],
        [InlineKeyboardButton(f"{mark('balance')}💰 Баланс", callback_data="adminwiz_togglepay_balance"),
         InlineKeyboardButton(f"{mark('stars')}⭐️ Звёзды", callback_data="adminwiz_togglepay_stars")],
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


# ─── Dynamic product payment keyboard ────────────────────────────────────────

def dynamic_product_keyboard(product_id: int, payment_methods: list, price_rub: float = 0):
    import math
    buttons = []
    if 'crypto' in payment_methods:
        price_str = f" ({price_rub * 1.015:.0f}₽)" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"🤖 Crypto Bot{price_str}", callback_data=f"dynpay_crypto_{product_id}")])
    if 'yoo' in payment_methods:
        price_str = f" ({price_rub * 1.03:.0f}₽)" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"💳 Yoo Money{price_str}", callback_data=f"dynpay_yoo_{product_id}")])
    if 'balance' in payment_methods:
        price_str = f" ({price_rub:.0f}₽)" if price_rub else ""
        buttons.append([InlineKeyboardButton(f"💰 Баланс{price_str}", callback_data=f"dynpay_balance_{product_id}")])
    if 'stars' in payment_methods:
        stars_qty = math.ceil(price_rub / 1.29) if price_rub else 0
        stars_str = f" ({stars_qty} ⭐️)" if stars_qty else ""
        buttons.append([InlineKeyboardButton(f"⭐️ Telegram Stars{stars_str}", callback_data=f"dynpay_stars_{product_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    return InlineKeyboardMarkup(buttons)
