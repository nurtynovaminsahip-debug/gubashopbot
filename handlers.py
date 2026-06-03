import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
import keyboards as kb
from rates import get_rates, rub_to_usdt, get_crypto_bot_commission_amount
from crypto_pay import create_invoice
import states

logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    """Send notification to main admin."""
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


# ─── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0][4:])
            if referred_by == user.id:
                referred_by = None
        except ValueError:
            pass

    existing = await db.get_user(user.id)
    if not existing:
        await db.create_user(user.id, user.username or "", user.first_name or "", referred_by)
        if referred_by:
            await db.add_referral(referred_by, user.id)

    user_data = await db.get_user(user.id)
    if not user_data or not user_data["agreed_to_policy"]:
        await update.message.reply_text(
            "🤖Перед использованием бота, убедитесь что вы ознакомились с политикой нашего проекта:",
            reply_markup=kb.policy_keyboard()
        )
        return

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usdt_rub, ton_rub = await get_rates()

    name = user.username and f"@{user.username}" or user.first_name or "пользователь"
    usdt_line = f"1 USDT = {usdt_rub:.2f}₽" if usdt_rub else "USDT — недоступно"
    ton_line = f"1 TON = {ton_rub:.2f}₽" if ton_rub else "TON — недоступно"

    text = (
        f"👋Добро пожаловать в GubaShop, {name}!\n\n"
        f" 💱Текущий курс:\n"
        f"  • {usdt_line}\n"
        f"  • {ton_line}"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=kb.main_menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=kb.main_menu_keyboard())


# ─── Policy ────────────────────────────────────────────────────────────────────

async def cb_agreed_policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_agreed(query.from_user.id)
    await query.edit_message_text("✅ Вы ознакомились с политикой проекта!")
    await show_main_menu(update, context)


# ─── Buy menu ──────────────────────────────────────────────────────────────────

async def _check_subscriptions(context, user_id: int) -> list:
    """Returns list of required channels the user has NOT subscribed to."""
    channels = await db.get_required_channels()
    not_subbed = []
    for ch in channels:
        if not ch['is_active']:
            continue
        try:
            member = await context.bot.get_chat_member(ch['channel_id'], user_id)
            if member.status in ('left', 'kicked', 'banned'):
                not_subbed.append(ch)
        except Exception:
            pass
    return not_subbed


async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    not_subbed = await _check_subscriptions(context, user_id)
    if not_subbed:
        await update.message.reply_text(
            "❗️Для использования магазина необходимо подписаться на каналы:",
            reply_markup=kb.subscribe_check_keyboard(not_subbed)
        )
        return
    cats = await db.get_categories()
    await update.message.reply_text(
        "🛒Выберите категорию:",
        reply_markup=kb.categories_keyboard(cats)
    )


async def cb_check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    not_subbed = await _check_subscriptions(context, user_id)
    if not_subbed:
        await query.edit_message_text(
            "❗️Вы ещё не подписались на все каналы:",
            reply_markup=kb.subscribe_check_keyboard(not_subbed)
        )
        return
    cats = await db.get_categories()
    await query.edit_message_text(
        "🛒Выберите категорию:",
        reply_markup=kb.categories_keyboard(cats)
    )


async def cb_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_", 1)[1])
    context.user_data['cur_cat_id'] = cat_id
    subcats = await db.get_subcategories(cat_id)
    await query.edit_message_text(
        "🛒Выберите подкатегорию:",
        reply_markup=kb.subcategories_keyboard(subcats, cat_id)
    )


async def cb_cat_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cur_cat_id'] = 1
    subcats = await db.get_subcategories(1)
    await query.edit_message_text(
        "🛒Выберите подкатегорию:",
        reply_markup=kb.subcategories_keyboard(subcats, 1)
    )


async def cb_subcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subcat_id = int(query.data.split("_", 1)[1])
    subcat = await db.get_subcategory(subcat_id)
    if not subcat:
        return
    context.user_data['cur_subcat_id'] = subcat_id
    sub_type = subcat.get('sub_type', 'generic')
    if sub_type == 'stars':
        await cb_sub_stars(update, context)
    elif sub_type == 'premium':
        await cb_sub_premium(update, context)
    elif sub_type == 'usernames':
        await cb_sub_usernames(update, context)
    elif sub_type == 'gifts':
        await cb_sub_gifts(update, context)
    elif sub_type == 'nft':
        await cb_sub_nft(update, context)
    else:
        products = await db.get_products_by_subcat(subcat_id)
        stock = await db.get_all_stock()
        buttons = []
        for p in products:
            inv_key = f"generic_{p['key']}"
            qty = stock.get(inv_key, 0)
            if qty == 0:
                continue
            stock_tag = f" [{qty} шт.]" if qty > 1 else ""
            buttons.append([InlineKeyboardButton(
                f"{p['label']}{stock_tag}", callback_data=f"dynprod_{p['id']}"
            )])
        if not buttons:
            await query.edit_message_text(
                "😴 Товары в этой категории временно отсутствуют.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]])
            )
            return
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
        await query.edit_message_text(
            f"🛒 {subcat['name']}:", reply_markup=InlineKeyboardMarkup(buttons)
        )


async def cb_back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = await db.get_categories()
    await query.edit_message_text("🛒Выберите категорию:", reply_markup=kb.categories_keyboard(cats))


async def cb_back_to_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = context.user_data.get('cur_cat_id', 1)
    subcats = await db.get_subcategories(cat_id)
    await query.edit_message_text(
        "🛒Выберите подкатегорию:",
        reply_markup=kb.subcategories_keyboard(subcats, cat_id)
    )


# ─── Stars ─────────────────────────────────────────────────────────────────────

def stars_message(qty: int) -> str:
    price = round(qty * 1.29, 2)
    qty_text = str(qty) if qty > 0 else "не выбрано"
    return (
        f"⭐️В этом разделе вы можете купить Telegram Stars\n"
        f"  • Курс: 1 ⭐️ = 1.29₽\n\n"
        f" Выберите количество или введите вручную:\n"
        f" Ваше количество: {qty_text}"
        + (f"\n 💳 Сумма: {price:.2f}₽" if qty > 0 else "")
    )


async def cb_sub_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["stars_qty"] = 0
    await query.edit_message_text(stars_message(0), reply_markup=kb.stars_quantity_keyboard())


async def cb_stars_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[1])
    context.user_data["stars_qty"] = qty
    await query.edit_message_text(stars_message(qty), reply_markup=kb.stars_quantity_keyboard(qty))


async def cb_stars_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⭐️Введите количество звезд, которое хотите купить(минимум - 50):")
    return states.STARS_CUSTOM_INPUT


async def handle_stars_custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        qty = int(text)
        if qty < 50:
            await update.message.reply_text("❌ Минимальное количество — 50. Введите снова:")
            return states.STARS_CUSTOM_INPUT
        context.user_data["stars_qty"] = qty
        await update.message.reply_text(stars_message(qty), reply_markup=kb.stars_quantity_keyboard(qty))
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число (минимум 50):")
        return states.STARS_CUSTOM_INPUT


async def cb_stars_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = context.user_data.get("stars_qty", 0)
    if not qty or qty < 50:
        await query.answer("⚠️ Сначала выберите количество звезд!", show_alert=True)
        return
    await query.edit_message_text(
        f"💳Выберите способ оплаты для {qty} ⭐️:",
        reply_markup=kb.payment_keyboard_stars(qty)
    )


# Stars payment handlers
async def cb_pay_crypto_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29, 2)
    usdt_amount = await get_crypto_bot_commission_amount(rub_amount)

    invoice = await create_invoice(usdt_amount, f"GubaShop: {qty} Telegram Stars")
    if not invoice["ok"]:
        await query.edit_message_text(f"❌ Ошибка создания счёта. Попробуйте позже.")
        return

    context.user_data[f"crypto_order_stars_{qty}"] = invoice["invoice_id"]
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {rub_amount:.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_stars_{qty}")
    )


async def cb_pay_yoo_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29 * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Yoo Money\n •💳 Сумма: {rub_amount:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_stars_{qty}")
    )


async def cb_pay_balance_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29, 2)
    await query.edit_message_text(
        f"❗️Вы точно хотите оплатить {rub_amount:.2f}₽ со своего баланса для покупки {qty} Telegram Stars?",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_stars_{qty}")
    )


async def cb_confirm_balance_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29, 2)
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < rub_amount:
        await query.edit_message_text("❌Отмена оплаты: недостаточно средств.")
        return
    await db.update_balance(user_id, -rub_amount)
    order_id = await db.add_order(user_id, f"Stars x{qty}", rub_amount, "balance")
    await _notify_payment(context, user_id, f"Stars x{qty}", rub_amount, "Баланс", order_id)
    await query.edit_message_text("✅Заказ оплачен и сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_crypto_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29, 2)
    user_id = query.from_user.id
    order_id = await db.add_order(user_id, f"Stars x{qty}", rub_amount, "crypto_bot")
    await _notify_payment(context, user_id, f"Stars x{qty}", rub_amount, "Crypto Bot", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_yoo_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rub_amount = round(qty * 1.29, 2)
    user_id = query.from_user.id
    order_id = await db.add_order(user_id, f"Stars x{qty}", rub_amount, "yoomoney")
    await _notify_payment(context, user_id, f"Stars x{qty}", rub_amount, "YooMoney", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


# ─── Premium ───────────────────────────────────────────────────────────────────

async def cb_sub_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stock = await db.get_all_stock()
    plans = [("1m", "⭐️ 1 месяц", 319), ("3m", "⭐️ 3 месяца", 1050),
             ("6m", "⭐️ 6 месяцев", 1350), ("12m", "⭐️ 12 месяцев", 2550)]
    buttons = []
    for key, label, price in plans:
        qty = stock.get(f"premium_{key}", 0)
        if qty == 0:
            continue
        stock_tag = f" [{qty} шт.]" if qty > 1 else " [последний!]"
        buttons.append([InlineKeyboardButton(f"{label} — {price}₽{stock_tag}", callback_data=f"premium_{key}")])
    if not buttons:
        await query.edit_message_text(
            "😴 Планы Premium временно отсутствуют в наличии.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]])
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    await query.edit_message_text("💎Выберите абонемент:", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_premium_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[1]
    p = kb.PREMIUM_PRICES[plan]
    await query.edit_message_text(
        f"💠 Telegram Premium — {p['label']}\n💳 Цена: {p['rub']}₽\n\nВыберите способ оплаты:",
        reply_markup=kb.premium_payment_keyboard(plan)
    )


async def cb_pay_crypto_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    rub = p["rub"]
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Premium {p['label']}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {round(rub*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_premium_{plan}")
    )


async def cb_pay_yoo_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    rub = round(p["rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Yoo Money\n •💳 Сумма: {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_premium_{plan}")
    )


async def cb_pay_balance_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    await query.edit_message_text(
        f"❗️Вы точно хотите оплатить {p['rub']}₽ со своего баланса для покупки Telegram Premium ({p['label']})?",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_premium_{plan}")
    )


async def cb_pay_stars_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    prices = [{"label": "Premium", "amount": p["stars"] * 100}]
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Telegram Stars\n •💳 Сумма: {p['stars']} звезд\n\nИспользуйте кнопку ниже для оплаты:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить", callback_data=f"tg_stars_pay_premium_{plan}")]
        ])
    )


async def cb_confirm_balance_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    user_id = query.from_user.id
    if await db.get_stock(f"premium_{plan}") <= 0:
        await query.edit_message_text("❌ Товар закончился. Выберите другой вариант.")
        return
    balance = await db.get_balance(user_id)
    if balance < p["rub"]:
        await query.edit_message_text("❌Отмена оплаты: недостаточно средств.")
        return
    await db.update_balance(user_id, -p["rub"])
    await db.decrement_stock(f"premium_{plan}")
    order_id = await db.add_order(user_id, f"Premium {p['label']}", p["rub"], "balance")
    await _notify_payment(context, user_id, f"Premium {p['label']}", p["rub"], "Баланс", order_id)
    await query.edit_message_text("✅Заказ оплачен и сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(p["rub"] * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_crypto_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    user_id = query.from_user.id
    await db.decrement_stock(f"premium_{plan}")
    order_id = await db.add_order(user_id, f"Premium {p['label']}", p["rub"], "crypto_bot")
    await _notify_payment(context, user_id, f"Premium {p['label']}", p["rub"], "Crypto Bot", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


async def cb_paid_yoo_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    user_id = query.from_user.id
    await db.decrement_stock(f"premium_{plan}")
    order_id = await db.add_order(user_id, f"Premium {p['label']}", p["rub"], "yoomoney")
    await _notify_payment(context, user_id, f"Premium {p['label']}", p["rub"], "YooMoney", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


# ─── Usernames ─────────────────────────────────────────────────────────────────

async def cb_sub_usernames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = await db.get_products('username')
    stock = await db.get_all_stock()
    buttons = []
    for p in products:
        key = p['key']
        qty = stock.get(f"username_{key}", 0)
        if qty == 0:
            continue
        stock_tag = f" [{qty} шт.]" if qty > 1 else ""
        buttons.append([InlineKeyboardButton(f"{p['label']}{stock_tag}", callback_data=f"username_{key}")])
    if not buttons:
        await query.edit_message_text(
            "😴 Юзернеймы временно отсутствуют в наличии.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]])
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    await query.edit_message_text("🔥Выберите юзернейм для покупки:", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_username_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 1)[1]
    u = await db.get_product('username', key)
    if not u:
        await query.answer("❌ Товар не найден.", show_alert=True)
        return
    await query.edit_message_text(
        f"🧩Юзернейм : @{key}\n 📤 Тип передачи: каналом\n\n 💳 Выберите способ оплаты:",
        reply_markup=kb.username_payment_keyboard(key, u['price_rub'])
    )


async def cb_pay_crypto_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = u["price_rub"]
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Username @{key}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {round(rub*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_username_{key}")
    )


async def cb_pay_yoo_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = round(u["price_rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Yoo Money\n •💳 Сумма: {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_username_{key}")
    )


async def cb_pay_balance_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.")
        return
    await query.edit_message_text(
        f"❗️Вы точно хотите оплатить {u['price_rub']:.0f}₽ со своего баланса для покупки Telegram Username @{key}?",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_username_{key}")
    )


async def cb_pay_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Telegram Stars\n\nОплатите через Telegram Stars.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить", callback_data=f"tg_stars_pay_username_{key}")]
        ])
    )


async def cb_confirm_balance_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.")
        return
    user_id = query.from_user.id
    if await db.get_stock(f"username_{key}") <= 0:
        await query.edit_message_text("❌ Товар закончился. Выберите другой юзернейм.")
        return
    balance = await db.get_balance(user_id)
    if balance < u["price_rub"]:
        await query.edit_message_text("❌Отмена оплаты: недостаточно средств.")
        return
    await db.update_balance(user_id, -u["price_rub"])
    await db.decrement_stock(f"username_{key}")
    order_id = await db.add_order(user_id, f"Username @{key}", u["price_rub"], "balance")
    await _notify_payment(context, user_id, f"Username @{key}", u["price_rub"], "Баланс", order_id)
    await query.edit_message_text("✅Заказ оплачен и сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


async def cb_paid_crypto_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    user_id = query.from_user.id
    await db.decrement_stock(f"username_{key}")
    rub = u["price_rub"] if u else 0
    order_id = await db.add_order(user_id, f"Username @{key}", rub, "crypto_bot")
    await _notify_payment(context, user_id, f"Username @{key}", rub, "Crypto Bot", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


async def cb_paid_yoo_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    user_id = query.from_user.id
    await db.decrement_stock(f"username_{key}")
    rub = u["price_rub"] if u else 0
    order_id = await db.add_order(user_id, f"Username @{key}", rub, "yoomoney")
    await _notify_payment(context, user_id, f"Username @{key}", rub, "YooMoney", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


# ─── Gifts ─────────────────────────────────────────────────────────────────────

async def cb_sub_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = await db.get_products('gift')
    stock = await db.get_all_stock()
    buttons = []
    for p in products:
        key = p['key']
        qty = stock.get(f"gift_{key}", 0)
        if qty == 0:
            continue
        stock_tag = f" [{qty} шт.]" if qty > 1 else " [последний!]"
        buttons.append([InlineKeyboardButton(f"{p['label']}{stock_tag}", callback_data=f"gift_{key}")])
    if not buttons:
        await query.edit_message_text(
            "😴 Подарки временно отсутствуют в наличии.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]])
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    await query.edit_message_text("🎁Выберите подарок для покупки:", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_gift_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 1)[1]
    g = await db.get_product('gift', key)
    if not g:
        await query.answer("❌ Товар не найден.", show_alert=True)
        return
    await query.edit_message_text(
        f"💳Выберите способ оплаты для {g['label']}:",
        reply_markup=kb.gift_payment_keyboard(key, g['price_rub'])
    )


async def cb_pay_crypto_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = g["price_rub"]
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Gift {g['label']}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {round(rub*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_gift_{key}")
    )


async def cb_pay_yoo_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = round(g["price_rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Yoo Money\n •💳 Сумма: {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_gift_{key}")
    )


async def cb_pay_balance_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.")
        return
    await query.edit_message_text(
        f"❗️Вы точно хотите оплатить {g['price_rub']:.0f}₽ со своего баланса для покупки {g['label']}?",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_gift_{key}")
    )


async def cb_confirm_balance_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.")
        return
    user_id = query.from_user.id
    if await db.get_stock(f"gift_{key}") <= 0:
        await query.edit_message_text("❌ Товар закончился. Выберите другой подарок.")
        return
    balance = await db.get_balance(user_id)
    if balance < g["price_rub"]:
        await query.edit_message_text("❌Отмена оплаты: недостаточно средств.")
        return
    await db.update_balance(user_id, -g["price_rub"])
    await db.decrement_stock(f"gift_{key}")
    order_id = await db.add_order(user_id, g["label"], g["price_rub"], "balance")
    await _notify_payment(context, user_id, g["label"], g["price_rub"], "Баланс", order_id)
    await query.edit_message_text("✅Заказ оплачен и сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(g["price_rub"] * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_crypto_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    user_id = query.from_user.id
    await db.decrement_stock(f"gift_{key}")
    label = g["label"] if g else f"Gift {key}"
    rub = g["price_rub"] if g else 0
    order_id = await db.add_order(user_id, label, rub, "crypto_bot")
    await _notify_payment(context, user_id, label, rub, "Crypto Bot", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


async def cb_paid_yoo_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    user_id = query.from_user.id
    await db.decrement_stock(f"gift_{key}")
    label = g["label"] if g else f"Gift {key}"
    rub = g["price_rub"] if g else 0
    order_id = await db.add_order(user_id, label, rub, "yoomoney")
    await _notify_payment(context, user_id, label, rub, "YooMoney", order_id)
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте выполнения заказа.")


# ─── NFT ───────────────────────────────────────────────────────────────────────

async def cb_sub_nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "😴В наличии NFT-подарков пока что нет. Мы сообщим вам, когда они появятся.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]])
    )


# ─── Profile ───────────────────────────────────────────────────────────────────

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = await db.get_user(user_id)
    balance = await db.get_balance(user_id)
    purchases = await db.get_purchase_count(user_id)
    deposits = await db.get_deposit_count(user_id)
    refs = await db.get_referral_count(user_id)

    text = (
        f"👤Ваш профиль:\n\n"
        f"🆔Ваш ID: {user_id}\n\n"
        f"🛒Покупок: {purchases}\n\n"
        f"💰Баланс: {balance:.2f}₽\n\n"
        f"📤Пополнений: {deposits}\n\n"
        f"📩Рефералов: {refs}"
    )
    await update.message.reply_text(text, reply_markup=kb.profile_keyboard())


async def cb_back_to_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    purchases = await db.get_purchase_count(user_id)
    deposits = await db.get_deposit_count(user_id)
    refs = await db.get_referral_count(user_id)
    text = (
        f"👤Ваш профиль:\n\n"
        f"🆔Ваш ID: {user_id}\n\n"
        f"🛒Покупок: {purchases}\n\n"
        f"💰Баланс: {balance:.2f}₽\n\n"
        f"📤Пополнений: {deposits}\n\n"
        f"📩Рефералов: {refs}"
    )
    await query.edit_message_text(text, reply_markup=kb.profile_keyboard())


async def cb_purchase_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    history = await db.get_purchase_history(user_id)
    if not history:
        text = "📌 История покупок пуста."
    else:
        lines = ["📌 История покупок (последние 20):"]
        for order in history:
            lines.append(f"• {order['product']} — {order['amount']:.2f}₽ ({order['payment_method']}) [{order['created_at'][:10]}]")
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_to_profile_keyboard())


# ─── Deposit ───────────────────────────────────────────────────────────────────

async def cb_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳Введите сумму пополнения в рублях(цифрами):")
    return states.DEPOSIT_AMOUNT_INPUT


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text)
        if amount <= 0:
            await update.message.reply_text("❌ Введите положительную сумму:")
            return states.DEPOSIT_AMOUNT_INPUT
        context.user_data["deposit_amount"] = amount
        await update.message.reply_text(
            f"💳Выберите способ оплаты для пополнения на {amount:.2f}₽:",
            reply_markup=kb.deposit_payment_keyboard(amount)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число:")
        return states.DEPOSIT_AMOUNT_INPUT


async def cb_dep_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[2])
    usdt_amount = await get_crypto_bot_commission_amount(amount)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Пополнение баланса {amount}₽")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {round(amount*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"dep_paid_crypto_{amount}")
    )


async def cb_dep_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[2])
    rub = round(amount * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Yoo Money\n •💳 Сумма: {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"dep_paid_yoo_{amount}")
    )


async def cb_dep_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[3])
    user_id = query.from_user.id
    await db.increment_deposits(user_id)
    uname = query.from_user.username or str(user_id)
    credit_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"💰 Зачислить {amount:.2f}₽ пользователю",
            callback_data=f"admin_credit_{user_id}_{amount}"
        )
    ]])
    await notify_admin(
        context,
        f"💳 Пополнение баланса (CryptoBot)\n"
        f"👤 @{uname} (ID: {user_id})\n"
        f"💰 Сумма: {amount:.2f}₽\n\n"
        f"Нажмите кнопку ниже, чтобы зачислить деньги пользователю.",
        reply_markup=credit_kb
    )
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте зачисления суммы.")


async def cb_dep_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[3])
    user_id = query.from_user.id
    await db.increment_deposits(user_id)
    uname = query.from_user.username or str(user_id)
    credit_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"💰 Зачислить {amount:.2f}₽ пользователю",
            callback_data=f"admin_credit_{user_id}_{amount}"
        )
    ]])
    await notify_admin(
        context,
        f"💳 Пополнение баланса (YooMoney)\n"
        f"👤 @{uname} (ID: {user_id})\n"
        f"💰 Сумма: {amount:.2f}₽\n\n"
        f"Нажмите кнопку ниже, чтобы зачислить деньги пользователю.",
        reply_markup=credit_kb
    )
    await query.edit_message_text("❗️Сообщение об оплате отправлено администратору. Ожидайте зачисления суммы.")


async def cb_admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin credits user balance after deposit confirmation."""
    query = update.callback_query
    if not await db.is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    parts = query.data.split("_")
    user_id = int(parts[2])
    amount = float(parts[3])
    await db.update_balance(user_id, amount)
    await query.answer(f"✅ Зачислено {amount:.2f}₽", show_alert=True)
    await query.edit_message_text(
        query.message.text + f"\n\n✅ Зачислено {amount:.2f}₽ пользователю {user_id}",
        reply_markup=None
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Ваш баланс пополнен на {amount:.2f}₽. Спасибо!"
        )
    except Exception:
        pass


# ─── Referral ──────────────────────────────────────────────────────────────────

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    refs = await db.get_referral_count(user_id)
    await update.message.reply_text(
        f"💎Благодаря реферальной системе, привлекая пользователей вы будете получать 15% от их трат к себе на баланс!\n"
        f" Твоя реферальная ссылка: {link}\n\n"
        f" 👤Количество своих рефералов ты можешь посмотреть в профиле.",
        reply_markup=kb.back_to_main_keyboard()
    )


async def cb_referral_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    refs = await db.get_referral_count(user_id)
    await query.edit_message_text(
        f"💎Благодаря реферальной системе, привлекая пользователей вы будете получать 15% от их трат к себе на баланс!\n"
        f" Твоя реферальная ссылка: {link}\n\n"
        f" 👤Количество своих рефералов ты можешь посмотреть в профиле.",
        reply_markup=kb.back_to_profile_keyboard()
    )


# ─── Promo ─────────────────────────────────────────────────────────────────────

async def handle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_promos = await db.get_user_promocodes(user_id)
    active_text = ", ".join([p["code"] for p in user_promos]) if user_promos else "нету"
    await update.message.reply_text(
        f"🏷Введите промокод для активации:\n\n 💎Активных промокодов: {active_text}",
        reply_markup=kb.back_to_main_keyboard()
    )
    return states.PROMO_INPUT


async def handle_promo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    promo = await db.get_promocode(code)
    if not promo:
        await update.message.reply_text("❌ Промокод не найден или недействителен.")
        return states.PROMO_INPUT
    await db.activate_promocode(user_id, code)
    desc = promo["description"] or f"Скидка {promo['discount_percent']}%"
    await update.message.reply_text(
        f"✅ Промокод «{code}» активирован!\n🎁 {desc}",
        reply_markup=kb.main_menu_keyboard()
    )
    return ConversationHandler.END


# ─── Support ───────────────────────────────────────────────────────────────────

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💭Опишите ваш вопрос или проблему, и мы ответим вам в ближайшее время.",
        reply_markup=kb.back_to_main_keyboard()
    )
    return states.SUPPORT_MESSAGE


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text
    msg_id = update.message.message_id

    await notify_admin(
        context,
        f"📩 Обращение в поддержку\n"
        f"👤 @{user.username or 'нет'} (ID: {user.id})\n"
        f"💬 {user_text}\n\n"
        f"Ответьте на это сообщение, и ответ придёт пользователю автоматически."
    )

    context.bot_data.setdefault("support_tickets", {})[user.id] = {
        "user_id": user.id,
        "username": user.username
    }

    await update.message.reply_text(
        "✅ Ваше сообщение отправлено в поддержку. Ожидайте ответа.",
        reply_markup=kb.main_menu_keyboard()
    )
    return ConversationHandler.END


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When admin replies to a support notification, forward to user."""
    if update.message.reply_to_message and update.effective_user.id == ADMIN_ID:
        replied_text = update.message.reply_to_message.text or ""
        if "ID:" in replied_text:
            try:
                user_id_str = replied_text.split("ID:")[1].split(")")[0].strip()
                target_user_id = int(user_id_str)
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📢Ответ от техподдержки: {update.message.text}"
                )
                await update.message.reply_text("✅ Ответ отправлен пользователю.")
            except Exception as e:
                logger.error(f"Support reply error: {e}")


# ─── Cancel ────────────────────────────────────────────────────────────────────

async def cb_cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Покупка отменена.")


async def cb_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return ConversationHandler.END


# ─── Admin panel ───────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await db.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    await update.message.reply_text("👤 Админ панель GubaShop", reply_markup=kb.admin_keyboard())


async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        f"📊 Статистика GubaShop\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"✅ Приняли политику: {stats['agreed']}\n"
        f"🛒 Всего заказов: {stats['total_orders']}\n"
        f"💰 Общая выручка: {stats['total_revenue']:.2f}₽"
    )
    await query.edit_message_text(text, reply_markup=kb.admin_keyboard())


async def cb_admin_add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ Введите промокод в формате:\n"
        "<КОД> <СКИДКА%> <МИН.СУММА> <ОПИСАНИЕ>\n\n"
        "Пример: PROMO20 20 300 Скидка 20% от 300₽"
    )
    return states.ADMIN_ADD_PROMO


async def handle_admin_add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split(maxsplit=3)
    try:
        code = parts[0].upper()
        discount = int(parts[1])
        min_amount = float(parts[2])
        desc = parts[3] if len(parts) > 3 else f"Скидка {discount}%"
        await db.add_promocode(code, discount_percent=discount, min_amount=min_amount, description=desc)
        await update.message.reply_text(f"✅ Промокод «{code}» добавлен!", reply_markup=kb.admin_keyboard())
    except Exception:
        await update.message.reply_text("❌ Неверный формат. Попробуйте снова.")
    return ConversationHandler.END


async def cb_admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("➕ Введите Telegram ID пользователя, которого хотите назначить администратором:")
    return states.ADMIN_ADD_ADMIN


async def handle_admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        await db.add_admin(target_id)
        await update.message.reply_text(f"✅ Пользователь {target_id} назначен администратором.", reply_markup=kb.admin_keyboard())
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.")
    return ConversationHandler.END


async def cb_admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("🧨 Введите Telegram ID администратора, которого хотите снять:")
    return states.ADMIN_REMOVE_ADMIN


async def handle_admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        await db.remove_admin(target_id)
        await update.message.reply_text(f"✅ Пользователь {target_id} снят с должности администратора.", reply_markup=kb.admin_keyboard())
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.")
    return ConversationHandler.END


async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("📤 Введите текст рассылки:")
    return states.ADMIN_BROADCAST


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    user_ids = await db.get_all_user_ids()
    success = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
            success += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Рассылка завершена. Отправлено: {success}/{len(user_ids)}", reply_markup=kb.admin_keyboard())
    return ConversationHandler.END


async def cb_admin_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("💰 Введите Telegram ID пользователя для пополнения баланса:")
    return states.ADMIN_TOPUP_USER


async def handle_admin_topup_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        context.user_data["topup_target"] = target_id
        await update.message.reply_text(f"💰 Введите сумму для пополнения баланса пользователя {target_id} (в рублях):")
        return states.ADMIN_TOPUP_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.")
        return ConversationHandler.END


async def handle_admin_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        amount = float(update.message.text.strip())
        target_id = context.user_data.get("topup_target")
        await db.update_balance(target_id, amount)
        await update.message.reply_text(f"✅ Баланс пользователя {target_id} пополнен на {amount:.2f}₽", reply_markup=kb.admin_keyboard())
        try:
            await context.bot.send_message(chat_id=target_id, text=f"✅ Ваш баланс пополнен на {amount:.2f}₽")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Введите числовое значение суммы.")
    return ConversationHandler.END


async def cb_admin_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all product stock levels."""
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    stock = await db.get_all_stock()
    labels = {
        "premium_1m": "Premium 1 мес",
        "premium_3m": "Premium 3 мес",
        "premium_6m": "Premium 6 мес",
        "premium_12m": "Premium 12 мес",
        "username_biden_com": "Username @biden_com",
        "username_ceobocc": "Username @ceobocc",
        "username_ceo_bocc": "Username @ceo_bocc",
        "username_beeryPuccy": "Username @beeryPuccy",
        "gift_bear": "Подарок Мишка",
        "gift_gift": "Подарок Gift",
        "gift_rocket": "Подарок Ракета",
        "gift_ring": "Подарок Кольцо",
    }
    lines = []
    for key, label in labels.items():
        qty = stock.get(key, 0)
        icon = "✅" if qty > 0 else "❌"
        lines.append(f"{icon} {label}: {qty} шт.")
    text = "📦 Склад товаров:\n\n" + "\n".join(lines) + "\n\nВведите ключ товара и количество в формате:\n<код_товара> <количество>\n\nКоды: premium_1m, premium_3m, premium_6m, premium_12m,\nusername_biden_com, username_ceobocc, username_ceo_bocc, username_beeryPuccy,\ngift_bear, gift_gift, gift_rocket, gift_ring"
    await query.edit_message_text(text)
    return states.ADMIN_SET_STOCK


async def handle_admin_set_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split()
    if len(parts) != 2:
        await update.message.reply_text("❌ Формат: <ключ_товара> <количество>\nНапример: gift_bear 5", reply_markup=kb.admin_keyboard())
        return ConversationHandler.END
    key, qty_str = parts
    premium_keys = {"premium_1m", "premium_3m", "premium_6m", "premium_12m"}
    all_stock = await db.get_all_stock()
    if key not in premium_keys and key not in all_stock:
        await update.message.reply_text(f"❌ Неизвестный ключ: {key}", reply_markup=kb.admin_keyboard())
        return ConversationHandler.END
    try:
        qty = int(qty_str)
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом.", reply_markup=kb.admin_keyboard())
        return ConversationHandler.END
    await db.set_stock(key, qty)
    await update.message.reply_text(f"✅ Склад обновлён: {key} = {qty} шт.", reply_markup=kb.admin_keyboard())
    return ConversationHandler.END


# ─── Admin: Add/Remove Products ────────────────────────────────────────────────

async def cb_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ Выберите тип добавляемого товара:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Юзернейм", callback_data="admin_add_product_type_username")],
            [InlineKeyboardButton("🎁 Подарок", callback_data="admin_add_product_type_gift")],
        ])
    )


async def cb_admin_add_product_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    product_type = query.data.split("_")[-1]
    context.user_data['add_product_type'] = product_type
    if product_type == 'username':
        hint = "Например: @mybusiness | не нфт"
    else:
        hint = "Например: 🎁 Elite Gift | 50 ⭐️"
    await query.edit_message_text(
        f"Введите название товара как оно будет отображаться в кнопке:\n({hint})"
    )
    return states.ADMIN_ADD_PRODUCT_LABEL


async def handle_admin_add_product_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    label = update.message.text.strip()
    context.user_data['add_product_label'] = label
    await update.message.reply_text("Введите цену товара в рублях (целое число):")
    return states.ADMIN_ADD_PRODUCT_PRICE


async def handle_admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите числовую цену. Попробуйте ещё раз:")
        return states.ADMIN_ADD_PRODUCT_PRICE
    context.user_data['add_product_price'] = price
    await update.message.reply_text("Введите начальное количество в наличии:")
    return states.ADMIN_ADD_PRODUCT_STOCK


async def handle_admin_add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        stock = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число. Попробуйте ещё раз:")
        return states.ADMIN_ADD_PRODUCT_STOCK

    product_type = context.user_data.get('add_product_type', 'gift')
    label = context.user_data.get('add_product_label', '')
    price = context.user_data.get('add_product_price', 0.0)

    import re
    key = re.sub(r'[^\w]', '_', label).strip('_').lower()
    key = re.sub(r'_+', '_', key)
    if not key:
        key = f"product_{int(price)}"

    await db.add_product(product_type, key, label, price, stock)
    await update.message.reply_text(
        f"✅ Товар добавлен!\n\n"
        f"Тип: {'Юзернейм' if product_type == 'username' else 'Подарок'}\n"
        f"Название: {label}\n"
        f"Цена: {price:.0f}₽\n"
        f"Количество: {stock} шт.\n"
        f"Ключ: {product_type}_{key}",
        reply_markup=kb.admin_keyboard()
    )
    return ConversationHandler.END


async def cb_admin_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    products = await db.get_all_products()
    if not products:
        await query.edit_message_text(
            "😴 Нет товаров для удаления.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    stock = await db.get_all_stock()
    buttons = []
    for p in products:
        qty = stock.get(f"{p['product_type']}_{p['key']}", 0)
        type_icon = "🧩" if p['product_type'] == 'username' else "🎁"
        buttons.append([InlineKeyboardButton(
            f"🗑 {type_icon} {p['label']} ({qty} шт.)",
            callback_data=f"admin_delete_product_{p['product_type']}_{p['key']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    await query.edit_message_text(
        "🗑 Выберите товар для удаления:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    parts = query.data.split("_", 4)
    product_type = parts[3]
    key = parts[4]
    await db.remove_product(product_type, key)
    await query.edit_message_text(
        f"✅ Товар '{product_type}_{key}' удалён.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="admin_back")]])
    )


async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("👤 Админ панель GubaShop", reply_markup=kb.admin_keyboard())


async def cb_admin_order_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin marks order as done."""
    query = update.callback_query
    if not await db.is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    parts = query.data.split("_")
    order_id = int(parts[3])
    user_id = int(parts[4])
    await db.update_order_status(order_id, "done")
    await query.answer("✅ Заказ отмечен как выполненный", show_alert=True)
    await query.edit_message_text(
        query.message.text + "\n\n✅ Заказ выполнен администратором",
        reply_markup=None
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Ваш заказ #{order_id} выполнен! Спасибо за покупку в GubaShop."
        )
    except Exception:
        pass


async def cb_admin_order_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects an order and refunds if paid via balance."""
    query = update.callback_query
    if not await db.is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    parts = query.data.split("_")
    order_id = int(parts[3])
    user_id = int(parts[4])

    order = await db.get_order(order_id)
    if not order:
        await query.answer("❌ Заказ не найден", show_alert=True)
        return

    if order['status'] in ('done', 'rejected'):
        await query.answer(
            f"⚠️ Заказ уже {'выполнен' if order['status'] == 'done' else 'отклонён'}",
            show_alert=True
        )
        return

    await db.update_order_status(order_id, "rejected")

    refund_note = ""
    if order['payment_method'] == "balance":
        await db.update_balance(user_id, order['amount'])
        refund_note = f"\n💰 Средства ({order['amount']:.2f}₽) возвращены на баланс."

    await query.answer("❌ Заказ отклонён", show_alert=True)
    await query.edit_message_text(
        query.message.text + f"\n\n❌ Заказ отклонён администратором{refund_note}",
        reply_markup=None
    )
    try:
        user_msg = (
            f"❌ Ваш заказ #{order_id} был отклонён.\n"
            f"📦 Товар: {order['product']}"
        )
        if order['payment_method'] == "balance":
            user_msg += f"\n\n💰 {order['amount']:.2f}₽ возвращены на ваш баланс."
        else:
            user_msg += "\n\nЕсли вы уже оплатили — свяжитесь с поддержкой для возврата."
        await context.bot.send_message(chat_id=user_id, text=user_msg)
    except Exception:
        pass


# ─── Dynamic generic product handlers ─────────────────────────────────────────

async def cb_dynprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import math
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    delivery_label = "⚡️ Автовыдача" if p.get('delivery_type') == 'auto' else "👤 Ручная выдача"
    inv_key = f"{p['product_type']}_{p['key']}"
    qty = await db.get_stock(inv_key)
    price_rub = p['price_rub']
    methods = [m.strip() for m in (p.get('payment_methods') or 'crypto,yoo,balance').split(',')]
    stars_line = ""
    if 'stars' in methods:
        stars_qty = math.ceil(price_rub / 1.29)
        stars_line = f"\n 💳 Стоимость в звёздах: {stars_qty} ⭐️"
    text = (
        f"🛒 {p['label']}\n\n"
        f" 📌 Описание: {p.get('description') or 'нет'}\n"
        f" 🏷 В наличии: {qty} шт.\n"
        f" 📦 Тип выдачи: {delivery_label}\n"
        f" 💳 Стоимость: {price_rub:.0f}₽{stars_line}"
    )
    await query.edit_message_text(
        text,
        reply_markup=kb.dynamic_product_keyboard(prod_id, methods, price_rub)
    )


async def cb_dynpay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = p['price_rub']
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: {p['label']}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")
        return
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •🤖 Способ: Crypto Bot\n •💳 Сумма: {round(rub*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"dynpaid_crypto_{prod_id}")
    )


async def cb_dynpay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.")
        return
    rub = round(p['price_rub'] * 1.03, 2)
    await query.edit_message_text(
        f"⏳Ожидание оплаты\n\n •💳 Способ: Yoo Money\n •💳 Сумма: {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"dynpaid_yoo_{prod_id}")
    )


async def cb_dynpay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.")
        return
    await query.edit_message_text(
        f"❗️Оплатить {p['price_rub']:.0f}₽ с баланса за {p['label']}?",
        reply_markup=kb.confirm_balance_keyboard(f"dynconfirm_balance_{prod_id}")
    )


async def cb_dynpay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import math
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.")
        return
    stars_qty = math.ceil(p['price_rub'] / 1.29)
    await query.edit_message_text(
        f"⭐️ Оплата звёздами\n\n"
        f"📦 Товар: {p['label']}\n"
        f"💳 Сумма: {stars_qty} ⭐️\n\n"
        f"Отправьте {stars_qty} ⭐️ звёзд через кнопку ниже, затем нажмите «Я оплатил».",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⭐️ Отправить {stars_qty} Stars", url=f"https://t.me/{(await query.get_bot().get_me()).username}?start=stars_{prod_id}")],
            [InlineKeyboardButton("✅ Я оплатил", callback_data=f"dynpaid_stars_{prod_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"dynprod_{prod_id}")],
        ])
    )


async def cb_dynpaid_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import math
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    user_id = query.from_user.id
    if p:
        stars_qty = math.ceil(p['price_rub'] / 1.29)
        inv_key = f"{p['product_type']}_{p['key']}"
        await db.decrement_stock(inv_key)
        order_id = await db.add_order(user_id, p['label'], p['price_rub'], "stars")
        if p.get('delivery_type') == 'auto':
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ Оплата принята! Ваш товар отправлен выше ⬆️")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], f"Stars ({stars_qty} ⭐️)", order_id)
    await query.edit_message_text("❗️ Сообщение об оплате отправлено администратору. Ожидайте выдачи.")


async def _auto_deliver(context, user_id: int, prod_id: int, label: str) -> bool:
    """Try to auto-deliver a key/content. Returns True if delivered."""
    item = await db.get_delivery_item(prod_id)
    if not item:
        return False
    await db.mark_delivery_used(item['id'], user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Ваш товар: {label}\n\n"
                f"📦 Данные для получения:\n"
                f"<code>{item['content']}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    return True


async def cb_dynconfirm_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.")
        return
    user_id = query.from_user.id
    inv_key = f"{p['product_type']}_{p['key']}"
    if await db.get_stock(inv_key) <= 0:
        await query.edit_message_text("❌ Товар закончился.")
        return
    balance = await db.get_balance(user_id)
    if balance < p['price_rub']:
        await query.edit_message_text("❌ Недостаточно средств на балансе.")
        return
    await db.update_balance(user_id, -p['price_rub'])
    await db.decrement_stock(inv_key)
    order_id = await db.add_order(user_id, p['label'], p['price_rub'], "balance")
    if p.get('delivery_type') == 'auto':
        delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
        if delivered:
            await query.edit_message_text("✅ Оплата прошла! Ваш товар отправлен выше ⬆️")
        else:
            await _notify_payment(context, user_id, p['label'], p['price_rub'], "Баланс", order_id)
            await query.edit_message_text("✅ Заказ оплачен! Ожидайте выполнения — ключи скоро закончились, администратор свяжется с вами.")
    else:
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "Баланс", order_id)
        await query.edit_message_text("✅ Заказ оплачен! Ожидайте выполнения.")


async def cb_dynpaid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    user_id = query.from_user.id
    if p:
        inv_key = f"{p['product_type']}_{p['key']}"
        await db.decrement_stock(inv_key)
        order_id = await db.add_order(user_id, p['label'], p['price_rub'], "crypto_bot")
        if p.get('delivery_type') == 'auto':
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ Оплата принята! Ваш товар отправлен выше ⬆️")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "Crypto Bot", order_id)
    await query.edit_message_text("❗️ Сообщение об оплате отправлено администратору. Ожидайте выдачи.")


async def cb_dynpaid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    user_id = query.from_user.id
    if p:
        inv_key = f"{p['product_type']}_{p['key']}"
        await db.decrement_stock(inv_key)
        order_id = await db.add_order(user_id, p['label'], p['price_rub'], "yoomoney")
        if p.get('delivery_type') == 'auto':
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ Оплата принята! Ваш товар отправлен выше ⬆️")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "YooMoney", order_id)
    await query.edit_message_text("❗️ Сообщение об оплате отправлено администратору. Ожидайте выдачи.")


# ─── Admin: Subscriptions ──────────────────────────────────────────────────────

async def cb_admin_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    channels = await db.get_required_channels()
    text = (
        "🔑 Управление обязательными подписками\n\n"
        "Пользователи не смогут пользоваться магазином без подписки на эти каналы.\n\n"
        "🟢 — активно  🔴 — выключено\n"
        "Нажмите на название канала чтобы вкл/выкл, 🗑 — удалить."
    )
    await query.edit_message_text(text, reply_markup=kb.subscriptions_keyboard(channels))


async def cb_adminsub_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    ch_id = int(query.data.split("_")[-1])
    await db.toggle_required_channel(ch_id)
    channels = await db.get_required_channels()
    await query.edit_message_text(
        "🔑 Управление обязательными подписками\n\n🟢 — активно  🔴 — выключено",
        reply_markup=kb.subscriptions_keyboard(channels)
    )


async def cb_adminsub_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    ch_id = int(query.data.split("_")[-1])
    await db.remove_required_channel(ch_id)
    channels = await db.get_required_channels()
    await query.edit_message_text(
        "✅ Канал удалён.\n\n🔑 Управление обязательными подписками:",
        reply_markup=kb.subscriptions_keyboard(channels)
    )


async def cb_adminsub_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "➕ Добавление канала\n\n"
        "Введите данные канала в формате:\n"
        "<channel_id> <название>\n\n"
        "Например:\n"
        "@mychannel Мой канал\n"
        "-1001234567890 Приватный канал\n\n"
        "Бот должен быть участником канала для проверки подписки."
    )
    return states.ADMIN_ADD_CHANNEL


async def handle_admin_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Формат: <channel_id> <название>\nНапример: @mychannel Мой канал"
        )
        return states.ADMIN_ADD_CHANNEL
    channel_id, title = parts[0], parts[1]
    await db.add_required_channel(channel_id, title)
    await update.message.reply_text(
        f"✅ Канал добавлен!\n\n📢 {title}\n🔑 ID: {channel_id}",
        reply_markup=kb.admin_keyboard()
    )
    return ConversationHandler.END


# ─── Admin: Category management ────────────────────────────────────────────────

async def cb_admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "🧩 Добавление категории\n\nВведите название категории:\n(например: 🎮 Игры)"
    )
    return states.ADMIN_ADD_CATEGORY


async def handle_admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    name = update.message.text.strip()
    cat_id = await db.add_category(name)
    await update.message.reply_text(
        f"✅ Категория добавлена!\n\n🧩 {name}\nID: {cat_id}",
        reply_markup=kb.admin_keyboard()
    )
    return ConversationHandler.END


async def cb_admin_add_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await query.edit_message_text(
            "❌ Сначала добавьте хотя бы одну категорию.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    buttons = [[InlineKeyboardButton(c['name'], callback_data=f"adminsubcat_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️Выберите категорию, в которую хотите добавить подкатегорию:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_adminsubcat_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    cat_id = int(query.data.split("_")[-1])
    context.user_data['new_subcat_cat_id'] = cat_id
    await query.edit_message_text(
        "✏️Введите название подкатегории, которую хотите добавить:"
    )
    return states.ADMIN_ADD_SUBCATEGORY


async def handle_admin_add_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    name = update.message.text.strip()
    cat_id = context.user_data.get('new_subcat_cat_id')
    if not cat_id:
        await update.message.reply_text("❌ Ошибка: категория не выбрана.")
        return ConversationHandler.END
    subcat_id = await db.add_subcategory(cat_id, name)
    await update.message.reply_text(
        f"✅ Подкатегория добавлена!\n\n🧩 {name}\nID: {subcat_id}",
        reply_markup=kb.admin_keyboard()
    )
    return ConversationHandler.END


# ─── Admin: Management panel (✏️Управление) ────────────────────────────────────

async def cb_admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("✏️ Управление магазином:", reply_markup=kb.management_keyboard())


async def cb_manage_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cats = await db.get_categories()
    await query.edit_message_text(
        "🗂 Категории (нажмите на название для просмотра подкатегорий, 🗑 — удалить):",
        reply_markup=kb.manage_categories_keyboard(cats)
    )


async def cb_manage_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[-1])
    subcats = await db.get_subcategories(cat_id)
    cats = await db.get_categories()
    cat = next((c for c in cats if c['id'] == cat_id), None)
    cat_name = cat['name'] if cat else f"ID {cat_id}"
    if not subcats:
        await query.edit_message_text(
            f"🧩 Подкатегории {cat_name}:\n\nПодкатегорий нет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="manage_categories")]])
        )
        return
    buttons = []
    for sc in subcats:
        buttons.append([
            InlineKeyboardButton(sc['name'], callback_data=f"manage_subcat_view_{sc['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"manage_subcat_del_{sc['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="manage_categories")])
    await query.edit_message_text(
        f"🧩 Подкатегории {cat_name}:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_manage_cat_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[-1])
    if cat_id == 1:
        await query.answer("❌ Нельзя удалить основную категорию Telegram.", show_alert=True)
        return
    await db.remove_category(cat_id)
    cats = await db.get_categories()
    await query.edit_message_text(
        "✅ Категория удалена.\n\n🗂 Категории:",
        reply_markup=kb.manage_categories_keyboard(cats)
    )


async def cb_manage_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    subcats = await db.get_all_subcategories()
    await query.edit_message_text(
        "🗂 Все подкатегории:",
        reply_markup=kb.manage_subcats_keyboard(subcats)
    )


async def cb_manage_subcat_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    subcat_id = int(query.data.split("_")[-1])
    subcat = await db.get_subcategory(subcat_id)
    if not subcat:
        await query.answer("Подкатегория не найдена.", show_alert=True)
        return
    products = await db.get_products_by_subcat(subcat_id)
    lines = [f"🧩 {subcat['name']} (тип: {subcat['sub_type']})\n"]
    if products:
        for p in products:
            lines.append(f"• {p['label']} — {p['price_rub']:.0f}₽")
    else:
        lines.append("Товаров нет.")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="manage_subcategories")]])
    )


async def cb_manage_subcat_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    subcat_id = int(query.data.split("_")[-1])
    if subcat_id <= 5:
        await query.answer("❌ Нельзя удалить встроенные подкатегории Telegram.", show_alert=True)
        return
    await db.remove_subcategory(subcat_id)
    subcats = await db.get_all_subcategories()
    await query.edit_message_text(
        "✅ Подкатегория удалена.\n\n🗂 Все подкатегории:",
        reply_markup=kb.manage_subcats_keyboard(subcats)
    )


async def cb_manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    products = await db.get_all_products()
    await query.edit_message_text(
        "🗂 Все товары:",
        reply_markup=kb.manage_products_keyboard(products)
    )


async def cb_manage_prod_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    prod_id = int(query.data.split("_")[-1])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.answer("Товар не найден.", show_alert=True)
        return
    inv_key = f"{p['product_type']}_{p['key']}"
    qty = await db.get_stock(inv_key)
    delivery_type = p.get('delivery_type', 'manual')
    is_auto = delivery_type == 'auto'
    total_keys, avail_keys = await db.count_delivery_items(prod_id) if is_auto else (0, 0)
    delivery_label = "⚡️ Автовыдача" if is_auto else "👤 Ручная выдача"
    keys_line = f"\n📦 Ключей выдачи: {avail_keys} доступно / {total_keys} всего" if is_auto else ""
    text = (
        f"📦 {p['label']}\n\n"
        f"Тип: {p['product_type']}\n"
        f"Ключ: {p['key']}\n"
        f"Цена: {p['price_rub']:.0f}₽\n"
        f"Описание: {p.get('description') or 'нет'}\n"
        f"Выдача: {delivery_label}{keys_line}\n"
        f"Способы оплаты: {p.get('payment_methods', 'crypto,yoo,balance')}\n"
        f"Остаток: {qty} шт."
    )
    buttons = []
    if is_auto:
        buttons.append([InlineKeyboardButton("➕ Добавить ключи выдачи", callback_data=f"manage_add_delivery_{prod_id}")])
        if total_keys > 0:
            buttons.append([InlineKeyboardButton("🗑 Очистить все ключи", callback_data=f"manage_clear_delivery_{prod_id}")])
    buttons.append([InlineKeyboardButton("🗑 Удалить товар", callback_data=f"manage_prod_del_{prod_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="manage_products")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_manage_add_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    prod_id = int(query.data.split("_")[-1])
    context.user_data['delivery_prod_id'] = prod_id
    p = await db.get_product_by_id(prod_id)
    _, avail = await db.count_delivery_items(prod_id)
    label = p['label'] if p else f"ID {prod_id}"
    await query.edit_message_text(
        f"➕ Добавление ключей для товара: {label}\n\n"
        f"Сейчас доступно: {avail} ключей\n\n"
        f"Отправьте ключи в следующем сообщении — по одному на строке.\n"
        f"Например:\n"
        f"KEY-AAAA-BBBB-CCCC\n"
        f"KEY-1111-2222-3333\n\n"
        f"Каждая строка будет добавлена как отдельный ключ выдачи.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"manage_prod_view_{prod_id}")]
        ])
    )
    return states.ADMIN_ADD_DELIVERY_ITEM


async def handle_admin_add_delivery_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    prod_id = context.user_data.get('delivery_prod_id')
    if not prod_id:
        return ConversationHandler.END
    lines = [l.strip() for l in update.message.text.split('\n') if l.strip()]
    if not lines:
        await update.message.reply_text("❌ Пустое сообщение. Попробуйте снова.")
        return states.ADMIN_ADD_DELIVERY_ITEM
    for line in lines:
        await db.add_delivery_item(prod_id, line)
    _, avail = await db.count_delivery_items(prod_id)
    p = await db.get_product_by_id(prod_id)
    label = p['label'] if p else f"ID {prod_id}"
    await update.message.reply_text(
        f"✅ Добавлено {len(lines)} ключ(ей) для {label}\n"
        f"Итого доступно: {avail} ключей",
        reply_markup=kb.admin_keyboard()
    )
    return ConversationHandler.END


async def cb_manage_clear_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    prod_id = int(query.data.split("_")[-1])
    await db.delete_delivery_items(prod_id)
    await query.answer("✅ Все ключи очищены", show_alert=True)
    # refresh product view
    p = await db.get_product_by_id(prod_id)
    if p:
        query.data = f"manage_prod_view_{prod_id}"
        await cb_manage_prod_view(update, context)


async def cb_manage_prod_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    prod_id = int(query.data.split("_")[-1])
    await db.remove_product_by_id(prod_id)
    products = await db.get_all_products()
    await query.edit_message_text(
        "✅ Товар удалён.\n\n🗂 Все товары:",
        reply_markup=kb.manage_products_keyboard(products)
    )


# ─── Admin: Product wizard ─────────────────────────────────────────────────────

def _wizard_text(draft: dict) -> str:
    name = draft.get('name') or 'не задано'
    desc = draft.get('description') or 'не задано'
    price = f"{draft.get('price_rub', 0):.0f}₽" if draft.get('price_rub') else 'не задано'
    stock = draft.get('stock', 0)
    delivery = '⚡️Автовыдача' if draft.get('delivery_type') == 'auto' else '👤Ручная выдача'
    methods_map = {'crypto': 'Crypto Bot', 'yoo': 'Yoo Money', 'balance': 'Баланс', 'stars': '⭐️Stars'}
    selected = draft.get('payment_methods', ['crypto', 'yoo', 'balance'])
    methods = ', '.join(methods_map[m] for m in selected if m in methods_map) or 'не выбраны'
    return (
        "✏️Для добавления товара управляйте его данными с помощью кнопок:\n\n"
        f" ✏️Название товара: {name}\n"
        f" 📌Описание товара: {desc}\n"
        f" 📦Тип выдачи: {delivery}\n"
        f" 🏷Количество штук в наличии: {stock}\n"
        f" 💳Доступные способы оплаты: {methods}\n"
        f" 💳Стоимость товара: {price}"
    )


async def cb_admin_product_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await query.edit_message_text(
            "❌ Нет категорий. Сначала добавьте категорию.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    buttons = [[InlineKeyboardButton(c['name'], callback_data=f"adminwiz_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️Выберите категорию, куда хотите добавить товар:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_adminwiz_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[-1])
    subcats = await db.get_subcategories(cat_id)
    if not subcats:
        await query.edit_message_text(
            "❌ В этой категории нет подкатегорий. Сначала добавьте подкатегорию.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    buttons = [[InlineKeyboardButton(sc['name'], callback_data=f"adminwiz_subcat_{sc['id']}")] for sc in subcats]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️Выберите подкатегорию, куда хотите добавить товар:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_adminwiz_subcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    subcat_id = int(query.data.split("_")[-1])
    context.user_data['wizard_draft'] = {
        'subcat_id': subcat_id, 'name': '', 'description': '',
        'price_rub': 0.0, 'stock': 0, 'delivery_type': 'manual',
        'payment_methods': ['crypto', 'yoo', 'balance'],
    }
    context.user_data['wizard_chat_id'] = query.message.chat_id
    context.user_data['wizard_msg_id'] = query.message.message_id
    await query.edit_message_text(_wizard_text(context.user_data['wizard_draft']), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def cb_adminwiz_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    await query.edit_message_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def cb_adminwiz_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    await query.edit_message_text(
        "✏️Управляйте типом выдачи через кнопки снизу:\n\n"
        f" 📦Выбранный тип: {'⚡️Автовыдача' if draft.get('delivery_type') == 'auto' else '👤Ручная выдача'}",
        reply_markup=kb.wizard_delivery_keyboard(draft.get('delivery_type', 'manual'))
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_set_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delivery_type = query.data.split("_")[-1]
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['delivery_type'] = delivery_type
    await query.edit_message_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def cb_adminwiz_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.setdefault('wizard_draft', {})
    parts = query.data.split("_")
    if len(parts) >= 3:
        sign = parts[2][0]
        val = int(parts[2][1:])
        current = draft.get('stock', 0)
        if sign == 'p':
            draft['stock'] = current + val
        else:
            draft['stock'] = max(0, current - val)
    await query.edit_message_text(
        f"✏️Управляйте количеством штук через кнопки снизу:\n\n 🏷Текущее количество: {draft.get('stock', 0)}",
        reply_markup=kb.wizard_qty_keyboard(draft.get('stock', 0))
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.setdefault('wizard_draft', {})
    selected = draft.get('payment_methods', ['crypto', 'yoo', 'balance'])
    await query.edit_message_text(
        "✏️Управляйте способами оплаты:\n\n"
        f" 💳Выберите доступные способы оплаты:\n"
        f" Выбранные: {', '.join(selected) or 'нет'}",
        reply_markup=kb.wizard_payment_keyboard(selected)
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_togglepay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[-1]
    draft = context.user_data.setdefault('wizard_draft', {})
    selected = draft.get('payment_methods', ['crypto', 'yoo', 'balance'])
    if method in selected:
        selected.remove(method)
    else:
        selected.append(method)
    draft['payment_methods'] = selected
    await query.edit_message_text(
        "✏️Управляйте способами оплаты:\n\n"
        f" 💳Выберите доступные способы оплаты:\n"
        f" Выбранные: {', '.join(selected) or 'нет'}",
        reply_markup=kb.wizard_payment_keyboard(selected)
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_want_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('name') or 'не задано'
    await query.edit_message_text(
        f"✏️Управляйте названием товара:\n\n Введите название товара:\n(Текущее: {current})",
        reply_markup=kb.wizard_text_back_keyboard()
    )
    return states.WIZARD_NAME


async def cb_adminwiz_want_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('description') or 'не задано'
    await query.edit_message_text(
        f"✏️Управляйте описанием товара:\n\n 📌Введите описание для товара:\n(Текущее: {current})",
        reply_markup=kb.wizard_text_back_keyboard()
    )
    return states.WIZARD_DESC


async def cb_adminwiz_want_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('price_rub', 0)
    await query.edit_message_text(
        f"✏️Управляйте стоимостью товара:\n\n 💳Введите стоимость товара в рублях цифрами:\n(Текущее: {current:.0f}₽)",
        reply_markup=kb.wizard_text_back_keyboard()
    )
    return states.WIZARD_PRICE


async def handle_wizard_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['name'] = update.message.text.strip()
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft), reply_markup=kb.wizard_main_keyboard()
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def handle_wizard_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['description'] = update.message.text.strip()
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft), reply_markup=kb.wizard_main_keyboard()
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def handle_wizard_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите числовую цену.")
        return states.WIZARD_PRICE
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['price_rub'] = price
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft), reply_markup=kb.wizard_main_keyboard()
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard())
    return states.WIZARD_MAIN


async def cb_adminwiz_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    draft = context.user_data.get('wizard_draft', {})
    name = draft.get('name', '').strip()
    if not name:
        await query.answer("❌ Введите название товара.", show_alert=True)
        return states.WIZARD_MAIN
    if not draft.get('price_rub'):
        await query.answer("❌ Введите стоимость товара.", show_alert=True)
        return states.WIZARD_MAIN
    import re
    key = re.sub(r'[^\w]', '_', name).strip('_').lower()
    key = re.sub(r'_+', '_', key) or f"prod_{int(draft['price_rub'])}"
    payment_methods_str = ','.join(draft.get('payment_methods', ['crypto', 'yoo', 'balance']))
    subcat_id = draft.get('subcat_id')
    await db.add_product(
        product_type='generic',
        key=key,
        label=name,
        price_rub=draft['price_rub'],
        stock=draft.get('stock', 0),
        subcategory_id=subcat_id,
        description=draft.get('description', ''),
        delivery_type=draft.get('delivery_type', 'manual'),
        payment_methods=payment_methods_str,
    )
    await query.edit_message_text(
        f"✅ Товар добавлен!\n\n"
        f"📦 {name}\n"
        f"💳 {draft['price_rub']:.0f}₽\n"
        f"🏷 {draft.get('stock', 0)} шт.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="admin_back")]])
    )
    context.user_data.pop('wizard_draft', None)
    return ConversationHandler.END


async def cb_adminwiz_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('wizard_draft', None)
    if await db.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Добавление отменено.", reply_markup=kb.admin_keyboard())
    return ConversationHandler.END


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def _notify_payment(context: ContextTypes.DEFAULT_TYPE, user_id: int, product: str,
                           amount: float, method: str, order_id: int):
    try:
        user = await context.bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"ID:{user_id}"
    except Exception:
        username = f"ID:{user_id}"

    order_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Выполнен", callback_data=f"admin_order_done_{order_id}_{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}"),
    ]])

    await notify_admin(
        context,
        f"🛒 Новый заказ #{order_id}\n"
        f"👤 {username}\n"
        f"📦 Товар: {product}\n"
        f"💰 Сумма: {amount:.2f}₽\n"
        f"💳 Способ: {method}",
        reply_markup=order_kb
    )
