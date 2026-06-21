import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler

import database as db
import keyboards as kb
from rates import get_rates, rub_to_usdt, get_crypto_bot_commission_amount
from crypto_pay import create_invoice
import states

logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode=None):
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


async def notify_all_admins(context, text: str, reply_markup=None, parse_mode=None):
    admin_ids = await db.get_all_admins()
    targets = set(admin_ids) | {ADMIN_ID}
    for aid in targets:
        try:
            await context.bot.send_message(chat_id=aid, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass


async def _get_stars_rate() -> float:
    rate_str = await db.get_setting("stars_rate", "1.26")
    try:
        return float(rate_str)
    except Exception:
        return 1.26


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
            "🤖 <b>Добро пожаловать в GubaShop!</b>\n\n"
            "Перед использованием бота необходимо ознакомиться и принять:\n\n"
            "🔒 <b>Политику конфиденциальности</b> — как мы обрабатываем ваши данные\n"
            "📋 <b>Пользовательское соглашение</b> — правила использования сервиса\n\n"
            "Нажмите на каждый документ, прочитайте, затем нажмите кнопку принятия:",
            reply_markup=kb.policy_keyboard(),
            parse_mode="HTML"
        )
        return

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usdt_rub, ton_rub = await get_rates()
    name = user.username and f"@{user.username}" or user.first_name or "пользователь"
    usdt_line = f"1 USDT = {usdt_rub:.2f}₽" if usdt_rub else "USDT — недоступно"
    ton_line = f"1 TON = {ton_rub:.2f}₽" if ton_rub else "TON — недоступно"
    stars_rate = await _get_stars_rate()

    text = (
        f"👋 <b>Добро пожаловать в GubaShop, {name}!</b>\n\n"
        f"💱 <b>Текущий курс:</b>\n"
        f"  • {usdt_line}\n"
        f"  • {ton_line}\n"
        f"  • 1 ⭐️ Telegram Stars = {stars_rate}₽\n\n"
        f"🛒 Выберите нужный раздел в меню ниже:"
    )

    banner = await db.get_section_banner("main")
    if update.callback_query:
        if banner:
            await update.callback_query.message.reply_photo(
                photo=banner, caption=text, parse_mode="HTML",
                reply_markup=kb.main_menu_keyboard()
            )
        else:
            await update.callback_query.message.reply_text(
                text, reply_markup=kb.main_menu_keyboard(), parse_mode="HTML"
            )
    else:
        if banner:
            await update.message.reply_photo(
                photo=banner, caption=text, parse_mode="HTML",
                reply_markup=kb.main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                text, reply_markup=kb.main_menu_keyboard(), parse_mode="HTML"
            )


# ─── Policy ────────────────────────────────────────────────────────────────────

async def cb_agreed_policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.set_agreed(query.from_user.id)
    await query.edit_message_text(
        "✅ <b>Отлично!</b> Вы приняли условия пользования.\n\n"
        "Добро пожаловать в <b>GubaShop</b>! 🎉",
        parse_mode="HTML"
    )
    await show_main_menu(update, context)


# ─── Leaderboard ───────────────────────────────────────────────────────────────

async def handle_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await db.get_top_buyers(10)
    banner = await db.get_section_banner("leaders")

    if not top:
        text = (
            "🏆 <b>Топ покупателей GubaShop</b>\n\n"
            "😴 <i>Список пока пуст. Станьте первым!</i>"
        )
    else:
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines = ["🏆 <b>Топ покупателей GubaShop</b>\n"]
        for i, buyer in enumerate(top):
            medal = medals[i]
            name = f"@{buyer['username']}" if buyer.get('username') else buyer.get('first_name', f"ID:{buyer['user_id']}")
            methods = buyer.get('methods') or ""
            method_icons = []
            if "crypto_bot" in methods or "crypto" in methods:
                method_icons.append("🤖")
            if "yoomoney" in methods or "yoo" in methods:
                method_icons.append("💳")
            if "balance" in methods:
                method_icons.append("💰")
            if "stars" in methods:
                method_icons.append("⭐️")
            methods_str = " ".join(method_icons) if method_icons else "—"
            lines.append(
                f"{medal} <b>{name}</b>\n"
                f"   💸 Потрачено: <b>{buyer['total_spent']:.2f}₽</b>\n"
                f"   🛒 Покупок: <b>{buyer['order_count']}</b>  {methods_str}\n"
            )
        text = "\n".join(lines)

    if banner:
        await update.message.reply_photo(
            photo=banner, caption=text, parse_mode="HTML",
            reply_markup=kb.back_to_main_keyboard()
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb.back_to_main_keyboard())


# ─── Buy menu ──────────────────────────────────────────────────────────────────

async def _check_subscriptions(context, user_id: int) -> list:
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
            "❗️ <b>Для доступа к магазину</b> необходимо подписаться на каналы:",
            reply_markup=kb.subscribe_check_keyboard(not_subbed),
            parse_mode="HTML"
        )
        return
    cats = await db.get_categories()
    banner = await db.get_section_banner("shop")
    text = "🛒 <b>Выберите категорию товаров:</b>"
    if banner:
        await update.message.reply_photo(
            photo=banner, caption=text, parse_mode="HTML",
            reply_markup=kb.categories_keyboard(cats)
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb.categories_keyboard(cats))


async def cb_check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    not_subbed = await _check_subscriptions(context, user_id)
    if not_subbed:
        await query.edit_message_text(
            "❗️ <b>Вы ещё не подписались на все каналы:</b>",
            reply_markup=kb.subscribe_check_keyboard(not_subbed),
            parse_mode="HTML"
        )
        return
    cats = await db.get_categories()
    await query.edit_message_text(
        "🛒 <b>Выберите категорию товаров:</b>",
        reply_markup=kb.categories_keyboard(cats),
        parse_mode="HTML"
    )


async def cb_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_", 1)[1])
    context.user_data['cur_cat_id'] = cat_id
    subcats = await db.get_subcategories(cat_id)
    await query.edit_message_text(
        "🛒 <b>Выберите подкатегорию:</b>",
        reply_markup=kb.subcategories_keyboard(subcats, cat_id),
        parse_mode="HTML"
    )


async def cb_cat_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cur_cat_id'] = 1
    subcats = await db.get_subcategories(1)
    await query.edit_message_text(
        "🛒 <b>Выберите подкатегорию:</b>",
        reply_markup=kb.subcategories_keyboard(subcats, 1),
        parse_mode="HTML"
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
    elif sub_type == 'robux':
        await cb_sub_robux(update, context)
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
                "😴 <b>Товары в этой категории временно отсутствуют.</b>\n\n<i>Мы скоро пополним ассортимент!</i>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]]),
                parse_mode="HTML"
            )
            return
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
        await query.edit_message_text(
            f"🛒 <b>{subcat['name']}</b>\n\n<i>Выберите товар:</i>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )


async def cb_back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = await db.get_categories()
    await query.edit_message_text(
        "🛒 <b>Выберите категорию товаров:</b>",
        reply_markup=kb.categories_keyboard(cats),
        parse_mode="HTML"
    )


async def cb_back_to_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = context.user_data.get('cur_cat_id', 1)
    subcats = await db.get_subcategories(cat_id)
    await query.edit_message_text(
        "🛒 <b>Выберите подкатегорию:</b>",
        reply_markup=kb.subcategories_keyboard(subcats, cat_id),
        parse_mode="HTML"
    )


# ─── Stars ─────────────────────────────────────────────────────────────────────

def stars_message(qty: int, rate: float) -> str:
    price = round(qty * rate, 2)
    qty_text = str(qty) if qty > 0 else "<i>не выбрано</i>"
    msg = (
        f"⭐️ <b>Telegram Stars</b>\n\n"
        f"📌 <i>Курс:</i> <b>1 ⭐️ = {rate}₽</b>\n\n"
        f"✏️ <i>Выберите количество или введите вручную:</i>\n"
        f"⭐️ <b>Ваш выбор:</b> {qty_text}"
    )
    if qty > 0:
        msg += f"\n💳 <b>Сумма: {price:.2f}₽</b>"
    return msg


async def cb_sub_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rate = await _get_stars_rate()
    context.user_data["stars_qty"] = 0
    banner = await db.get_section_banner("stars")

    msg = stars_message(0, rate)
    if banner:
        try:
            await query.message.reply_photo(
                photo=banner, caption=msg, parse_mode="HTML",
                reply_markup=kb.stars_quantity_keyboard()
            )
            await query.message.delete()
        except Exception:
            await query.edit_message_text(msg, reply_markup=kb.stars_quantity_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(msg, reply_markup=kb.stars_quantity_keyboard(), parse_mode="HTML")


async def cb_stars_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[1])
    rate = await _get_stars_rate()
    context.user_data["stars_qty"] = qty
    await query.edit_message_text(
        stars_message(qty, rate), reply_markup=kb.stars_quantity_keyboard(qty), parse_mode="HTML"
    )


async def cb_stars_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⭐️ <b>Введите количество звёзд</b>\n\n<i>Минимум — 50 штук</i>",
        parse_mode="HTML"
    )
    return states.STARS_CUSTOM_INPUT


async def handle_stars_custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    rate = await _get_stars_rate()
    try:
        qty = int(text)
        if qty < 50:
            await update.message.reply_text("❌ <b>Минимальное количество — 50.</b> Введите снова:", parse_mode="HTML")
            return states.STARS_CUSTOM_INPUT
        context.user_data["stars_qty"] = qty
        await update.message.reply_text(
            stars_message(qty, rate), reply_markup=kb.stars_quantity_keyboard(qty), parse_mode="HTML"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число (минимум 50):", parse_mode="HTML")
        return states.STARS_CUSTOM_INPUT


async def cb_stars_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = context.user_data.get("stars_qty", 0)
    if not qty or qty < 50:
        await query.answer("⚠️ Сначала выберите количество звёзд!", show_alert=True)
        return
    rate = await _get_stars_rate()
    await query.edit_message_text(
        f"⭐️ <b>Покупка {qty} Telegram Stars</b>\n"
        f"💰 <b>Сумма:</b> {round(qty * rate, 2):.2f}₽\n\n"
        f"👤 <i>Кто получит звёзды?</i>",
        reply_markup=kb.stars_recipient_keyboard(),
        parse_mode="HTML"
    )


async def cb_stars_recipient_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = f"@{user.username}" if user.username else str(user.id)
    context.user_data["stars_recipient"] = username
    qty = context.user_data.get("stars_qty", 50)
    rate = await _get_stars_rate()
    await query.edit_message_text(
        f"⭐️ <b>Покупка {qty} Telegram Stars</b>\n\n"
        f"👤 <i>Получатель:</i> <b>{username}</b>\n"
        f"💰 <b>Сумма:</b> {round(qty * rate, 2):.2f}₽\n\n"
        f"💳 <b>Выберите способ оплаты:</b>",
        reply_markup=kb.payment_keyboard_stars(qty, rate),
        parse_mode="HTML"
    )


async def cb_stars_recipient_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ <b>Введите Telegram username получателя</b>\n\n"
        "<i>Например: @username или просто username</i>",
        parse_mode="HTML"
    )
    return states.STARS_RECIPIENT_INPUT


async def handle_stars_recipient_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("@")
    if not text or len(text) < 3:
        await update.message.reply_text(
            "❌ <b>Неверный username.</b>\nВведите корректный Telegram username (минимум 3 символа):",
            parse_mode="HTML"
        )
        return states.STARS_RECIPIENT_INPUT
    username = f"@{text}"
    context.user_data["stars_recipient"] = username
    qty = context.user_data.get("stars_qty", 50)
    rate = await _get_stars_rate()
    await update.message.reply_text(
        f"⭐️ <b>Покупка {qty} Telegram Stars</b>\n\n"
        f"👤 <i>Получатель:</i> <b>{username}</b>\n"
        f"💰 <b>Сумма:</b> {round(qty * rate, 2):.2f}₽\n\n"
        f"💳 <b>Выберите способ оплаты:</b>",
        reply_markup=kb.payment_keyboard_stars(qty, rate),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cb_pay_crypto_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate, 2)
    usdt_amount = await get_crypto_bot_commission_amount(rub_amount)
    recipient = context.user_data.get("stars_recipient", "")

    invoice = await create_invoice(usdt_amount, f"GubaShop: {qty} Telegram Stars")
    if not invoice["ok"]:
        await query.edit_message_text("❌ <b>Ошибка создания счёта.</b> Попробуйте позже.", parse_mode="HTML")
        return

    context.user_data[f"crypto_order_stars_{qty}"] = invoice["invoice_id"]
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"⭐️ <i>Количество:</i> <b>{qty} звёзд</b>{recipient_line}\n"
        f"💳 <i>Сумма:</i> <b>{round(rub_amount*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_stars_{qty}"),
        parse_mode="HTML"
    )


async def cb_pay_yoo_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate * 1.03, 2)
    recipient = context.user_data.get("stars_recipient", "")
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"⭐️ <i>Количество:</i> <b>{qty} звёзд</b>{recipient_line}\n"
        f"💰 <i>Сумма:</i> <b>{rub_amount:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_stars_{qty}"),
        parse_mode="HTML"
    )


async def cb_pay_balance_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate, 2)
    recipient = context.user_data.get("stars_recipient", "")
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"❓ <b>Подтверждение оплаты</b>\n\n"
        f"⭐️ <b>{qty} Telegram Stars</b>{recipient_line}\n"
        f"💰 Спишется: <b>{rub_amount:.2f}₽</b> с баланса",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_stars_{qty}"),
        parse_mode="HTML"
    )


async def cb_confirm_balance_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate, 2)
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < rub_amount:
        await query.edit_message_text(
            "❌ <b>Недостаточно средств на балансе.</b>\n\nПополните баланс и попробуйте снова.",
            parse_mode="HTML"
        )
        return
    recipient = context.user_data.get("stars_recipient", "")
    label = f"Stars x{qty} → {recipient}" if recipient else f"Stars x{qty}"
    await db.update_balance(user_id, -rub_amount)
    order_id = await db.add_order(user_id, label, rub_amount, "balance")
    await _notify_payment(context, user_id, label, rub_amount, "Баланс", order_id)
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"✅ <b>Заказ успешно оплачен!</b>\n\n"
        f"⭐️ <b>{qty} Telegram Stars</b>{recipient_line}\n"
        f"💳 <b>Сумма:</b> {rub_amount:.2f}₽\n\n"
        f"<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_crypto_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate, 2)
    user_id = query.from_user.id
    recipient = context.user_data.get("stars_recipient", "")
    label = f"Stars x{qty} → {recipient}" if recipient else f"Stars x{qty}"
    order_id = await db.add_order(user_id, label, rub_amount, "crypto_bot")
    await _notify_payment(context, user_id, label, rub_amount, "Crypto Bot", order_id)
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"⭐️ <b>{qty} Telegram Stars</b>{recipient_line}\n"
        f"<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


async def cb_paid_yoo_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[3])
    rate = await _get_stars_rate()
    rub_amount = round(qty * rate, 2)
    user_id = query.from_user.id
    recipient = context.user_data.get("stars_recipient", "")
    label = f"Stars x{qty} → {recipient}" if recipient else f"Stars x{qty}"
    order_id = await db.add_order(user_id, label, rub_amount, "yoomoney")
    await _notify_payment(context, user_id, label, rub_amount, "YooMoney", order_id)
    recipient_line = f"\n👤 <i>Получатель:</i> <b>{recipient}</b>" if recipient else ""
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"⭐️ <b>{qty} Telegram Stars</b>{recipient_line}\n"
        f"<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )
    referrer = await db.get_referrer(user_id)
    if referrer:
        bonus = round(rub_amount * 0.15, 2)
        await db.update_balance(referrer, bonus)


# ─── Premium ───────────────────────────────────────────────────────────────────

async def cb_sub_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stock = await db.get_all_stock()
    plans = [("1m", "🌟 1 месяц", 319), ("3m", "💫 3 месяца", 1050),
             ("6m", "✨ 6 месяцев", 1350), ("12m", "👑 12 месяцев", 2550)]
    buttons = []
    for key, label, price in plans:
        qty = stock.get(f"premium_{key}", 0)
        if qty == 0:
            continue
        stock_tag = f" [{qty} шт.]" if qty > 1 else " [последний!]"
        buttons.append([InlineKeyboardButton(f"{label} — {price}₽{stock_tag}", callback_data=f"premium_{key}")])
    if not buttons:
        await query.edit_message_text(
            "😴 <b>Планы Premium временно отсутствуют.</b>\n\n<i>Мы скоро пополним!</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]]),
            parse_mode="HTML"
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    banner = await db.get_section_banner("premium")
    text = (
        "💠 <b>Telegram Premium</b>\n\n"
        "✨ <i>Разблокируйте все возможности Telegram!</i>\n\n"
        "Выберите абонемент:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def cb_premium_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[1]
    p = kb.PREMIUM_PRICES[plan]
    await query.edit_message_text(
        f"💠 <b>Telegram Premium — {p['label']}</b>\n\n"
        f"💳 <i>Стоимость:</i> <b>{p['rub']}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.premium_payment_keyboard(plan),
        parse_mode="HTML"
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
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"💠 <i>Товар:</i> <b>Telegram Premium {p['label']}</b>\n"
        f"💳 <i>Сумма:</i> <b>{round(rub*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_premium_{plan}"),
        parse_mode="HTML"
    )


async def cb_pay_yoo_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    rub = round(p["rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"💠 <i>Товар:</i> <b>Telegram Premium {p['label']}</b>\n"
        f"💰 <i>Сумма:</i> <b>{rub:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_premium_{plan}"),
        parse_mode="HTML"
    )


async def cb_pay_balance_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    await query.edit_message_text(
        f"❓ <b>Подтверждение оплаты</b>\n\n"
        f"💠 <b>Telegram Premium {p['label']}</b>\n"
        f"💰 Спишется: <b>{p['rub']}₽</b> с баланса",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_premium_{plan}"),
        parse_mode="HTML"
    )


async def cb_pay_stars_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    await query.edit_message_text(
        f"⭐️ <b>Счёт на оплату отправлен ниже ⬇️</b>\n\n"
        f"💠 <i>Товар:</i> <b>Telegram Premium {p['label']}</b>\n"
        f"💳 <i>Сумма:</i> <b>{p['stars']} ⭐️</b>",
        parse_mode="HTML"
    )
    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=f"Telegram Premium {p['label']}",
        description=f"Покупка Telegram Premium на {p['label']} через GubaShop",
        payload=f"premium_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(f"Premium {p['label']}", p["stars"])],
    )


async def cb_confirm_balance_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    user_id = query.from_user.id
    if await db.get_stock(f"premium_{plan}") <= 0:
        await query.edit_message_text("❌ <b>Товар закончился.</b> Выберите другой вариант.", parse_mode="HTML")
        return
    balance = await db.get_balance(user_id)
    if balance < p["rub"]:
        await query.edit_message_text("❌ <b>Недостаточно средств на балансе.</b>", parse_mode="HTML")
        return
    await db.update_balance(user_id, -p["rub"])
    await db.decrement_stock(f"premium_{plan}")
    order_id = await db.add_order(user_id, f"Premium {p['label']}", p["rub"], "balance")
    await _notify_payment(context, user_id, f"Premium {p['label']}", p["rub"], "Баланс", order_id)
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n"
        f"💠 <b>Telegram Premium {p['label']}</b>\n"
        f"<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )
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
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💠 <b>Telegram Premium {p['label']}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_paid_yoo_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.split("_")[3]
    p = kb.PREMIUM_PRICES[plan]
    user_id = query.from_user.id
    await db.decrement_stock(f"premium_{plan}")
    order_id = await db.add_order(user_id, f"Premium {p['label']}", p["rub"], "yoomoney")
    await _notify_payment(context, user_id, f"Premium {p['label']}", p["rub"], "YooMoney", order_id)
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💠 <b>Telegram Premium {p['label']}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


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
        buttons.append([InlineKeyboardButton(f"🧩 {p['label']}{stock_tag}", callback_data=f"username_{key}")])
    if not buttons:
        await query.edit_message_text(
            "😴 <b>Юзернеймы временно отсутствуют.</b>\n\n<i>Загляните позже!</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]]),
            parse_mode="HTML"
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    banner = await db.get_section_banner("usernames")
    text = "🧩 <b>Юзернеймы</b>\n\n<i>Выберите юзернейм для покупки:</i>"
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def cb_username_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 1)[1]
    u = await db.get_product('username', key)
    if not u:
        await query.answer("❌ Товар не найден.", show_alert=True)
        return
    await query.edit_message_text(
        f"🧩 <b>Юзернейм: @{key}</b>\n\n"
        f"📤 <i>Тип передачи:</i> <b>Через канал</b>\n"
        f"💳 <i>Стоимость:</i> <b>{u['price_rub']:.0f}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.username_payment_keyboard(key, u['price_rub']),
        parse_mode="HTML"
    )


async def cb_pay_crypto_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = u["price_rub"]
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Username @{key}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"🧩 <i>Товар:</i> <b>@{key}</b>\n"
        f"💳 <i>Сумма:</i> <b>{round(rub*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_username_{key}"),
        parse_mode="HTML"
    )


async def cb_pay_yoo_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = round(u["price_rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"🧩 <i>Товар:</i> <b>@{key}</b>\n"
        f"💰 <i>Сумма:</i> <b>{rub:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_username_{key}"),
        parse_mode="HTML"
    )


async def cb_pay_balance_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"❓ <b>Подтверждение оплаты</b>\n\n"
        f"🧩 <b>@{key}</b>\n"
        f"💰 Спишется: <b>{u['price_rub']:.0f}₽</b> с баланса",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_username_{key}"),
        parse_mode="HTML"
    )


async def cb_pay_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    stars_qty = u.get("stars_price")
    if not stars_qty:
        await query.edit_message_text("❌ <b>Цена в звёздах для этого товара не задана.</b>", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⭐️ <b>Счёт на оплату отправлен ниже ⬇️</b>\n\n"
        f"🧩 <i>Товар:</i> <b>@{key}</b>\n"
        f"💳 <i>Сумма:</i> <b>{stars_qty} ⭐️</b>",
        parse_mode="HTML"
    )
    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=f"Username @{key}",
        description=f"Покупка @{key} через GubaShop",
        payload=f"username_{key}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(f"@{key}", stars_qty)],
    )


async def cb_confirm_balance_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    u = await db.get_product('username', key)
    if not u:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    user_id = query.from_user.id
    if await db.get_stock(f"username_{key}") <= 0:
        await query.edit_message_text("❌ <b>Товар закончился.</b>", parse_mode="HTML")
        return
    balance = await db.get_balance(user_id)
    if balance < u["price_rub"]:
        await query.edit_message_text("❌ <b>Недостаточно средств на балансе.</b>", parse_mode="HTML")
        return
    await db.update_balance(user_id, -u["price_rub"])
    await db.decrement_stock(f"username_{key}")
    order_id = await db.add_order(user_id, f"Username @{key}", u["price_rub"], "balance")
    await _notify_payment(context, user_id, f"Username @{key}", u["price_rub"], "Баланс", order_id)
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n🧩 <b>@{key}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


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
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n🧩 <b>@{key}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


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
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n🧩 <b>@{key}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


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
            "😴 <b>Подарки временно отсутствуют.</b>\n\n<i>Загляните позже!</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]]),
            parse_mode="HTML"
        )
        return
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")])
    banner = await db.get_section_banner("gifts")
    text = "🧸 <b>Подарки Telegram</b>\n\n<i>Выберите подарок для покупки:</i>"
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def cb_gift_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 1)[1]
    g = await db.get_product('gift', key)
    if not g:
        await query.answer("❌ Товар не найден.", show_alert=True)
        return
    await query.edit_message_text(
        f"🎁 <b>{g['label']}</b>\n\n"
        f"💳 <i>Стоимость:</i> <b>{g['price_rub']:.0f}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.gift_payment_keyboard(key, g['price_rub']),
        parse_mode="HTML"
    )


async def cb_pay_crypto_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = g["price_rub"]
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Gift {g['label']}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"🎁 <i>Товар:</i> <b>{g['label']}</b>\n"
        f"💳 <i>Сумма:</i> <b>{round(rub*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"paid_crypto_gift_{key}"),
        parse_mode="HTML"
    )


async def cb_pay_yoo_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = round(g["price_rub"] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"🎁 <i>Товар:</i> <b>{g['label']}</b>\n"
        f"💰 <i>Сумма:</i> <b>{rub:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"paid_yoo_gift_{key}"),
        parse_mode="HTML"
    )


async def cb_pay_balance_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"❓ <b>Подтверждение оплаты</b>\n\n"
        f"🎁 <b>{g['label']}</b>\n"
        f"💰 Спишется: <b>{g['price_rub']:.0f}₽</b> с баланса",
        reply_markup=kb.confirm_balance_keyboard(f"confirm_balance_gift_{key}"),
        parse_mode="HTML"
    )


async def cb_confirm_balance_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_", 3)[3]
    g = await db.get_product('gift', key)
    if not g:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    user_id = query.from_user.id
    if await db.get_stock(f"gift_{key}") <= 0:
        await query.edit_message_text("❌ <b>Товар закончился.</b>", parse_mode="HTML")
        return
    balance = await db.get_balance(user_id)
    if balance < g["price_rub"]:
        await query.edit_message_text("❌ <b>Недостаточно средств на балансе.</b>", parse_mode="HTML")
        return
    await db.update_balance(user_id, -g["price_rub"])
    await db.decrement_stock(f"gift_{key}")
    order_id = await db.add_order(user_id, g["label"], g["price_rub"], "balance")
    await _notify_payment(context, user_id, g["label"], g["price_rub"], "Баланс", order_id)
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n🎁 <b>{g['label']}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )
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
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n🎁 <b>{label}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


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
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n🎁 <b>{label}</b>\n<i>Ожидайте выполнения заказа.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


# ─── NFT ───────────────────────────────────────────────────────────────────────

async def cb_sub_nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎁 <b>NFT-подарки</b>\n\n"
        "😴 <i>В наличии NFT-подарков пока нет.</i>\n\n"
        "Мы сообщим вам, как только они появятся!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcategories")]]),
        parse_mode="HTML"
    )


# ─── Dynamic generic product handlers ─────────────────────────────────────────

async def cb_dynprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    delivery_type = p.get('delivery_type', 'manual')
    delivery_label = "⚡️ Автовыдача" if delivery_type == 'auto' else "👤 Руч.выдача"
    inv_key = f"{p['product_type']}_{p['key']}"
    qty = await db.get_stock(inv_key)
    price_rub = p['price_rub']
    methods = [m.strip() for m in (p.get('payment_methods') or 'crypto,yoo,balance').split(',')]

    text = (
        f"✏️ <i>Название товара:</i>\n"
        f"<b>{p['label']}</b>\n\n"
        f"📌 <i>Описание товара:</i>\n"
        f"<b>{p.get('description') or 'Нет описания'}</b>\n\n"
        f"💳 <i>Стоимость товара:</i>\n"
        f"<b>{price_rub:.0f}₽</b>"
    )

    keyboard = kb.dynamic_product_info_keyboard(prod_id, delivery_type, qty, price_rub, methods, p.get('stars_price'))
    banner = p.get('banner_file_id')

    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=keyboard)
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def cb_dynbuy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    methods = [m.strip() for m in (p.get('payment_methods') or 'crypto,yoo,balance').split(',')]
    await query.edit_message_text(
        f"💳 <b>Оплата товара</b>\n\n"
        f"📦 <i>Товар:</i> <b>{p['label']}</b>\n"
        f"💰 <i>Цена:</i> <b>{p['price_rub']:.0f}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.dynamic_product_payment_keyboard(prod_id, methods, p['price_rub'], p.get('stars_price')),
        parse_mode="HTML"
    )


async def cb_dynpay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = p['price_rub']
    usdt_amount = await get_crypto_bot_commission_amount(rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: {p['label']}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"📦 <i>Товар:</i> <b>{p['label']}</b>\n"
        f"💳 <i>Сумма:</i> <b>{round(rub*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"dynpaid_crypto_{prod_id}"),
        parse_mode="HTML"
    )


async def cb_dynpay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    rub = round(p['price_rub'] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"📦 <i>Товар:</i> <b>{p['label']}</b>\n"
        f"💰 <i>Сумма:</i> <b>{rub:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"dynpaid_yoo_{prod_id}"),
        parse_mode="HTML"
    )


async def cb_dynpay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"❓ <b>Подтверждение оплаты</b>\n\n"
        f"📦 <b>{p['label']}</b>\n"
        f"💰 Спишется: <b>{p['price_rub']:.0f}₽</b> с баланса",
        reply_markup=kb.confirm_balance_keyboard(f"dynconfirm_balance_{prod_id}"),
        parse_mode="HTML"
    )


async def cb_dynpay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    if not p:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    stars_qty = p.get('stars_price')
    if not stars_qty:
        await query.edit_message_text("❌ <b>Цена в звёздах для этого товара не задана.</b>", parse_mode="HTML")
        return
    title = p['label'][:32]
    description = (p.get('description') or p['label'])[:255]
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=title,
            description=description,
            payload=f"dynprod_{prod_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(p['label'][:255], stars_qty)],
        )
        await query.edit_message_text(
            f"⭐️ <b>Счёт на оплату отправлен ниже ⬇️</b>\n\n"
            f"📦 <i>Товар:</i> <b>{p['label']}</b>\n"
            f"💳 <i>Сумма:</i> <b>{stars_qty} ⭐️</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Не удалось выставить счёт: {e}\n\nОбратитесь в поддержку.", parse_mode="HTML")


async def _auto_deliver(context, user_id: int, prod_id: int, label: str) -> bool:
    item = await db.get_delivery_item(prod_id)
    if not item:
        return False
    await db.mark_delivery_used(item['id'], user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Ваш товар готов!</b>\n\n"
                f"📦 <i>Товар:</i> <b>{label}</b>\n\n"
                f"🔑 <i>Данные для получения:</i>\n"
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
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")
        return
    user_id = query.from_user.id
    inv_key = f"{p['product_type']}_{p['key']}"
    if await db.get_stock(inv_key) <= 0:
        await query.edit_message_text("❌ <b>Товар закончился.</b>", parse_mode="HTML")
        return
    balance = await db.get_balance(user_id)
    if balance < p['price_rub']:
        await query.edit_message_text("❌ <b>Недостаточно средств на балансе.</b>", parse_mode="HTML")
        return
    await db.update_balance(user_id, -p['price_rub'])
    await db.decrement_stock(inv_key)
    order_id = await db.add_order(user_id, p['label'], p['price_rub'], "balance")

    if p.get('delivery_type') == 'auto':
        # If auto_data is set - admin must confirm before delivery
        if p.get('auto_data'):
            await _notify_auto_delivery_confirm(context, user_id, p, order_id, p['auto_data'])
            await query.edit_message_text(
                f"✅ <b>Заказ оплачен!</b>\n\n📦 <b>{p['label']}</b>\n"
                f"<i>Ожидайте — данные будут выданы автоматически после подтверждения.</i>",
                reply_markup=kb.order_chat_user_keyboard(order_id),
                parse_mode="HTML"
            )
        else:
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text(
                    f"✅ <b>Оплата прошла! Ваш товар отправлен выше ⬆️</b>",
                    parse_mode="HTML"
                )
            else:
                await _notify_payment(context, user_id, p['label'], p['price_rub'], "Баланс", order_id)
                await query.edit_message_text(
                    f"✅ <b>Заказ оплачен!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте выполнения.</i>",
                    reply_markup=kb.order_chat_user_keyboard(order_id),
                    parse_mode="HTML"
                )
    else:
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "Баланс", order_id)
        await query.edit_message_text(
            f"✅ <b>Заказ оплачен!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте выполнения.</i>",
            reply_markup=kb.order_chat_user_keyboard(order_id),
            parse_mode="HTML"
        )


async def _notify_auto_delivery_confirm(context, user_id: int, product: dict, order_id: int, auto_data: str):
    uname = (await context.bot.get_chat(user_id)).username or str(user_id)
    reply_kb = kb.order_chat_admin_keyboard(order_id, user_id)
    auto_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить и выдать данные", callback_data=f"admin_auto_deliver_{order_id}_{user_id}")],
        [InlineKeyboardButton("❌ Отклонить заказ", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
    ])
    await notify_all_admins(
        context,
        f"⚡️ <b>АВТОВЫДАЧА — требуется подтверждение</b>\n\n"
        f"👤 <i>Покупатель:</i> @{uname} (ID: {user_id})\n"
        f"📦 <i>Товар:</i> <b>{product['label']}</b>\n"
        f"💳 <i>Сумма:</i> <b>{product['price_rub']:.0f}₽</b>\n"
        f"🔑 <i>Данные для выдачи:</i>\n<code>{auto_data}</code>\n\n"
        f"⚠️ <i>Подтвердите заказ для автоматической отправки данных покупателю.</i>",
        reply_markup=auto_kb,
        parse_mode="HTML"
    )


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
            if p.get('auto_data'):
                await _notify_auto_delivery_confirm(context, user_id, p, order_id, p['auto_data'])
                await query.edit_message_text(
                    f"✅ <b>Заявка принята!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте подтверждения и выдачи данных.</i>",
                    reply_markup=kb.order_chat_user_keyboard(order_id),
                    parse_mode="HTML"
                )
                return
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ <b>Оплата принята! Ваш товар отправлен выше ⬆️</b>", parse_mode="HTML")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "Crypto Bot", order_id)
        await query.edit_message_text(
            f"✅ <b>Заявка отправлена!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте выполнения.</i>",
            reply_markup=kb.order_chat_user_keyboard(order_id),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")


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
            if p.get('auto_data'):
                await _notify_auto_delivery_confirm(context, user_id, p, order_id, p['auto_data'])
                await query.edit_message_text(
                    f"✅ <b>Заявка принята!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте подтверждения и выдачи данных.</i>",
                    reply_markup=kb.order_chat_user_keyboard(order_id),
                    parse_mode="HTML"
                )
                return
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ <b>Оплата принята! Ваш товар отправлен выше ⬆️</b>", parse_mode="HTML")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], "YooMoney", order_id)
        await query.edit_message_text(
            f"✅ <b>Заявка отправлена!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте выполнения.</i>",
            reply_markup=kb.order_chat_user_keyboard(order_id),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text("❌ Товар не найден.", parse_mode="HTML")


async def cb_dynpaid_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[2])
    p = await db.get_product_by_id(prod_id)
    user_id = query.from_user.id
    if p:
        stars_qty = p.get('stars_price') or '?'
        inv_key = f"{p['product_type']}_{p['key']}"
        await db.decrement_stock(inv_key)
        order_id = await db.add_order(user_id, p['label'], p['price_rub'], "stars")
        if p.get('delivery_type') == 'auto':
            if p.get('auto_data'):
                await _notify_auto_delivery_confirm(context, user_id, p, order_id, p['auto_data'])
                await query.edit_message_text(
                    f"✅ <b>Заявка принята!</b>\n\n📦 <b>{p['label']}</b>\n<i>Ожидайте подтверждения и выдачи данных.</i>",
                    reply_markup=kb.order_chat_user_keyboard(order_id),
                    parse_mode="HTML"
                )
                return
            delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
            if delivered:
                await query.edit_message_text("✅ <b>Оплата принята! Ваш товар отправлен выше ⬆️</b>", parse_mode="HTML")
                return
        await _notify_payment(context, user_id, p['label'], p['price_rub'], f"Stars ({stars_qty} ⭐️)", order_id)
    await query.edit_message_text(
        "✅ <b>Заявка отправлена!</b>\n\n<i>Ожидайте выполнения заказа.</i>",
        parse_mode="HTML"
    )


async def cb_admin_auto_deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin confirms auto-delivery and sends data to user."""
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
    if order['status'] != 'pending':
        await query.answer("⚠️ Заказ уже обработан", show_alert=True)
        return

    # Find the product from order data and get auto_data
    # We need to find it in the message text or query products
    msg_text = query.message.text or ""
    auto_data = None
    if "<code>" in msg_text:
        start = msg_text.find("<code>") + 6
        end = msg_text.find("</code>")
        if end > start:
            auto_data = msg_text[start:end]

    await db.update_order_status(order_id, "done")
    await query.answer("✅ Данные отправлены покупателю", show_alert=True)
    await query.edit_message_text(
        query.message.text + "\n\n✅ <b>Данные отправлены покупателю</b>",
        reply_markup=None,
        parse_mode="HTML"
    )
    try:
        data_text = f"<code>{auto_data}</code>" if auto_data else "<i>данные были в заказе</i>"
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Ваш заказ #{order_id} выполнен!</b>\n\n"
                f"📦 <i>Товар:</i> <b>{order['product']}</b>\n\n"
                f"🔑 <i>Данные для получения:</i>\n{data_text}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── Order Chat ────────────────────────────────────────────────────────────────

async def cb_chat_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    context.user_data['chat_order_id'] = order_id
    await query.edit_message_text(
        f"💬 <b>Чат с продавцом</b>\n\n"
        f"📋 <i>Заказ №{order_id}</i>\n\n"
        f"Напишите ваше сообщение продавцу:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Завершить чат", callback_data=f"chat_close_{order_id}")]
        ]),
        parse_mode="HTML"
    )
    return states.ORDER_CHAT_MESSAGE


async def handle_user_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get('chat_order_id')
    if not order_id:
        return ConversationHandler.END
    user = update.effective_user
    text = update.message.text
    await db.add_order_chat_message(order_id, user.id, "user", text)

    uname = f"@{user.username}" if user.username else user.first_name
    await notify_all_admins(
        context,
        f"💬 <b>Сообщение от покупателя</b>\n\n"
        f"📋 <i>Заказ №{order_id}</i>\n"
        f"👤 <i>Покупатель:</i> {uname} (ID: {user.id})\n\n"
        f"📝 <b>Сообщение:</b>\n{text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 Ответить покупателю", callback_data=f"admin_chat_reply_{order_id}_{user.id}")],
            [InlineKeyboardButton("✅ Подтвердить заказ", callback_data=f"admin_order_done_{order_id}_{user.id}")],
            [InlineKeyboardButton("❌ Отклонить заказ", callback_data=f"admin_order_reject_{order_id}_{user.id}")],
        ]),
        parse_mode="HTML"
    )
    await update.message.reply_text(
        "✅ <b>Сообщение отправлено продавцу.</b>\n\n<i>Ожидайте ответа...</i>",
        parse_mode="HTML"
    )
    return states.ORDER_CHAT_MESSAGE


async def cb_chat_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    await query.edit_message_text(
        f"✅ <b>Чат завершён.</b>\n\n"
        f"📋 <i>Заказ №{order_id}</i>\n\n"
        f"<i>Продавец получил ваши сообщения и скоро обработает заказ.</i>",
        parse_mode="HTML"
    )
    context.user_data.pop('chat_order_id', None)
    return ConversationHandler.END


async def cb_admin_chat_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await db.is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return ConversationHandler.END
    parts = query.data.split("_")
    order_id = int(parts[3])
    user_id = int(parts[4])
    context.user_data['admin_chat_order_id'] = order_id
    context.user_data['admin_chat_user_id'] = user_id
    await query.edit_message_text(
        f"💬 <b>Ответ покупателю</b>\n\n"
        f"📋 <i>Заказ №{order_id}</i>\n\n"
        f"Введите ваш ответ:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    return states.ADMIN_ORDER_CHAT_MESSAGE


async def handle_admin_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    order_id = context.user_data.get('admin_chat_order_id')
    user_id = context.user_data.get('admin_chat_user_id')
    if not order_id or not user_id:
        return ConversationHandler.END
    text = update.message.text
    await db.add_order_chat_message(order_id, user_id, "admin", text)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"💬 <b>Ответ от продавца</b>\n\n"
                f"📋 <i>Заказ №{order_id}</i>\n\n"
                f"📝 {text}"
            ),
            reply_markup=kb.order_chat_user_keyboard(order_id),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await update.message.reply_text(
        "✅ <b>Ответ отправлен покупателю.</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    context.user_data.pop('admin_chat_order_id', None)
    context.user_data.pop('admin_chat_user_id', None)
    return ConversationHandler.END


# ─── Profile ───────────────────────────────────────────────────────────────────

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = await db.get_user(user_id)
    balance = await db.get_balance(user_id)
    purchases = await db.get_purchase_count(user_id)
    deposits = await db.get_deposit_count(user_id)
    refs = await db.get_referral_count(user_id)
    total_spent = user_data['total_spent'] if user_data and 'total_spent' in user_data.keys() else 0

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 <i>Ваш ID:</i> <code>{user_id}</code>\n\n"
        f"🛒 <i>Покупок:</i> <b>{purchases}</b>\n"
        f"💸 <i>Потрачено всего:</i> <b>{total_spent:.2f}₽</b>\n\n"
        f"💰 <i>Баланс:</i> <b>{balance:.2f}₽</b>\n"
        f"📤 <i>Пополнений:</i> <b>{deposits}</b>\n\n"
        f"📩 <i>Рефералов:</i> <b>{refs}</b>"
    )
    await update.message.reply_text(text, reply_markup=kb.profile_keyboard(), parse_mode="HTML")


async def cb_back_to_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = await db.get_user(user_id)
    balance = await db.get_balance(user_id)
    purchases = await db.get_purchase_count(user_id)
    deposits = await db.get_deposit_count(user_id)
    refs = await db.get_referral_count(user_id)
    total_spent = user_data['total_spent'] if user_data and 'total_spent' in user_data.keys() else 0

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 <i>Ваш ID:</i> <code>{user_id}</code>\n\n"
        f"🛒 <i>Покупок:</i> <b>{purchases}</b>\n"
        f"💸 <i>Потрачено всего:</i> <b>{total_spent:.2f}₽</b>\n\n"
        f"💰 <i>Баланс:</i> <b>{balance:.2f}₽</b>\n"
        f"📤 <i>Пополнений:</i> <b>{deposits}</b>\n\n"
        f"📩 <i>Рефералов:</i> <b>{refs}</b>"
    )
    await query.edit_message_text(text, reply_markup=kb.profile_keyboard(), parse_mode="HTML")


async def cb_purchase_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    history = await db.get_purchase_history(user_id)
    if not history:
        text = "📋 <b>История покупок пуста.</b>\n\n<i>Сделайте первую покупку прямо сейчас!</i>"
    else:
        lines = ["📋 <b>История покупок (последние 20):</b>\n"]
        for order in history:
            status_icon = "✅" if order['status'] == 'done' else ("❌" if order['status'] == 'rejected' else "⏳")
            lines.append(
                f"{status_icon} <b>{order['product']}</b>\n"
                f"   💰 {order['amount']:.2f}₽ · {order['payment_method']} · {order['created_at'][:10]}\n"
            )
        text = "\n".join(lines)
    await query.edit_message_text(text, reply_markup=kb.back_to_profile_keyboard(), parse_mode="HTML")


# ─── Deposit ───────────────────────────────────────────────────────────────────

async def cb_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💳 <b>Пополнение баланса</b>\n\n"
        "<i>Введите сумму пополнения в рублях:</i>",
        parse_mode="HTML"
    )
    return states.DEPOSIT_AMOUNT_INPUT


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text)
        if amount <= 0:
            await update.message.reply_text("❌ Введите положительную сумму:", parse_mode="HTML")
            return states.DEPOSIT_AMOUNT_INPUT
        context.user_data["deposit_amount"] = amount
        await update.message.reply_text(
            f"💳 <b>Пополнение баланса</b>\n\n"
            f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n\n"
            f"Выберите способ оплаты:",
            reply_markup=kb.deposit_payment_keyboard(amount),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число:", parse_mode="HTML")
        return states.DEPOSIT_AMOUNT_INPUT


async def cb_dep_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[2])
    usdt_amount = await get_crypto_bot_commission_amount(amount)
    invoice = await create_invoice(usdt_amount, f"GubaShop: Пополнение баланса {amount}₽")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"🤖 <i>Способ:</i> <b>Crypto Bot</b>\n"
        f"💰 <i>Сумма:</i> <b>{round(amount*1.015,2):.2f}₽</b> ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"dep_paid_crypto_{amount}"),
        parse_mode="HTML"
    )


async def cb_dep_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    amount = float(parts[2])
    rub = round(amount * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n"
        f"💳 <i>Способ:</i> <b>YooMoney</b>\n"
        f"💰 <i>Сумма:</i> <b>{rub:.2f}₽</b>",
        reply_markup=kb.yoo_pay_keyboard(f"dep_paid_yoo_{amount}"),
        parse_mode="HTML"
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
            f"💰 Зачислить {amount:.2f}₽",
            callback_data=f"admin_credit_{user_id}_{amount}"
        )
    ]])
    await notify_all_admins(
        context,
        f"💳 <b>Пополнение баланса (CryptoBot)</b>\n\n"
        f"👤 <i>Пользователь:</i> @{uname} (ID: {user_id})\n"
        f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n\n"
        f"<i>Нажмите кнопку для зачисления средств.</i>",
        reply_markup=credit_kb,
        parse_mode="HTML"
    )
    await query.edit_message_text(
        "✅ <b>Уведомление отправлено!</b>\n\n<i>Ожидайте зачисления средств на баланс.</i>",
        parse_mode="HTML"
    )


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
            f"💰 Зачислить {amount:.2f}₽",
            callback_data=f"admin_credit_{user_id}_{amount}"
        )
    ]])
    await notify_all_admins(
        context,
        f"💳 <b>Пополнение баланса (YooMoney)</b>\n\n"
        f"👤 <i>Пользователь:</i> @{uname} (ID: {user_id})\n"
        f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n\n"
        f"<i>Нажмите кнопку для зачисления средств.</i>",
        reply_markup=credit_kb,
        parse_mode="HTML"
    )
    await query.edit_message_text(
        "✅ <b>Уведомление отправлено!</b>\n\n<i>Ожидайте зачисления средств на баланс.</i>",
        parse_mode="HTML"
    )


async def cb_admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        query.message.text + f"\n\n✅ <b>Зачислено {amount:.2f}₽ пользователю {user_id}</b>",
        reply_markup=None,
        parse_mode="HTML"
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ <b>Ваш баланс пополнен на {amount:.2f}₽!</b>\n\nСпасибо, что пользуетесь <b>GubaShop</b>! 🎉",
            parse_mode="HTML"
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
        f"💎 <b>Реферальная программа GubaShop</b>\n\n"
        f"Приводите друзей и получайте <b>15% бонус</b> с каждой их покупки!\n\n"
        f"🔗 <i>Ваша реферальная ссылка:</i>\n"
        f"<code>{link}</code>\n\n"
        f"📩 <i>Привлечено рефералов:</i> <b>{refs}</b>",
        reply_markup=kb.back_to_main_keyboard(),
        parse_mode="HTML"
    )


async def cb_referral_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    refs = await db.get_referral_count(user_id)
    await query.edit_message_text(
        f"💎 <b>Реферальная программа GubaShop</b>\n\n"
        f"Приводите друзей и получайте <b>15% бонус</b> с каждой их покупки!\n\n"
        f"🔗 <i>Ваша реферальная ссылка:</i>\n"
        f"<code>{link}</code>\n\n"
        f"📩 <i>Привлечено рефералов:</i> <b>{refs}</b>",
        reply_markup=kb.back_to_profile_keyboard(),
        parse_mode="HTML"
    )


# ─── Promo ─────────────────────────────────────────────────────────────────────

async def handle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_promos = await db.get_user_promocodes(user_id)
    active_text = ", ".join([f"<code>{p['code']}</code>" for p in user_promos]) if user_promos else "<i>нету</i>"
    await update.message.reply_text(
        f"🏷 <b>Промокоды</b>\n\n"
        f"Введите промокод для активации:\n\n"
        f"💎 <i>Ваши активные промокоды:</i> {active_text}",
        reply_markup=kb.back_to_main_keyboard(),
        parse_mode="HTML"
    )
    return states.PROMO_INPUT


async def handle_promo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    promo = await db.get_promocode(code)
    if not promo:
        await update.message.reply_text(
            "❌ <b>Промокод не найден или недействителен.</b>",
            parse_mode="HTML"
        )
        return states.PROMO_INPUT
    await db.activate_promocode(user_id, code)
    desc = promo["description"] or f"Скидка {promo['discount_percent']}%"
    await update.message.reply_text(
        f"✅ <b>Промокод «{code}» активирован!</b>\n\n🎁 {desc}",
        reply_markup=kb.main_menu_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ─── Support ───────────────────────────────────────────────────────────────────

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 <b>Служба поддержки GubaShop</b>\n\n"
        "<i>Опишите ваш вопрос или проблему, и мы ответим вам в ближайшее время.</i>",
        reply_markup=kb.back_to_main_keyboard(),
        parse_mode="HTML"
    )
    return states.SUPPORT_MESSAGE


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text

    await notify_all_admins(
        context,
        f"📩 <b>Обращение в поддержку</b>\n\n"
        f"👤 <i>Пользователь:</i> @{user.username or 'нет'} (ID: {user.id})\n\n"
        f"💬 <b>Сообщение:</b>\n{user_text}\n\n"
        f"<i>Ответьте на это сообщение или используйте кнопку ниже.</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"💬 Ответить", callback_data=f"admin_chat_reply_0_{user.id}")
        ]]),
        parse_mode="HTML"
    )

    context.bot_data.setdefault("support_tickets", {})[user.id] = {
        "user_id": user.id,
        "username": user.username
    }

    await update.message.reply_text(
        "✅ <b>Ваше сообщение отправлено в поддержку.</b>\n\n<i>Ожидайте ответа — обычно отвечаем быстро!</i>",
        reply_markup=kb.main_menu_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message and await db.is_admin(update.effective_user.id):
        replied_text = update.message.reply_to_message.text or ""
        if "ID:" in replied_text:
            try:
                user_id_str = replied_text.split("ID:")[1].split(")")[0].strip().split("\n")[0].strip()
                target_user_id = int(user_id_str)
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📢 <b>Ответ от техподдержки:</b>\n\n{update.message.text}",
                    parse_mode="HTML"
                )
                await update.message.reply_text("✅ Ответ отправлен пользователю.")
            except Exception as e:
                logger.error(f"Support reply error: {e}")


# ─── Rules ─────────────────────────────────────────────────────────────────────

async def handle_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📕 <b>Правила и документы GubaShop</b>\n\n"
        "Пожалуйста, ознакомьтесь с нашими правилами перед использованием сервиса:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 Политика конфиденциальности",
                                  url="https://telegra.ph/Politika-konfidencialnosti-Privacy-Policy-06-18")],
            [InlineKeyboardButton("📋 Пользовательское соглашение",
                                  url="https://telegra.ph/Polzovatelskoe-soglashenie-06-18-24")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")],
        ]),
        parse_mode="HTML"
    )


# ─── Reviews ──────────────────────────────────────────────────────────────────

async def handle_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⭐️ <b>Отзывы о GubaShop</b>\n\n"
        "<i>Читайте реальные отзывы наших покупателей:</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐️ Читать отзывы", url="https://t.me/lihakchm")
        ]]),
        parse_mode="HTML"
    )


# ─── Cancel ────────────────────────────────────────────────────────────────────

async def cb_cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ <b>Покупка отменена.</b>", parse_mode="HTML")


async def cb_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return ConversationHandler.END


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()


# ─── Contests ──────────────────────────────────────────────────────────────────

async def handle_contests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contests = await db.get_active_contests()
    banner = await db.get_section_banner("contests")

    if not contests:
        text = (
            "✨ <b>Конкурсы GubaShop</b>\n\n"
            "😴 <i>Активных конкурсов пока нет.</i>\n\n"
            "Следите за обновлениями!"
        )
    else:
        text = (
            "✨ <b>Конкурсы GubaShop</b>\n\n"
            f"🎯 <i>Активных конкурсов: {len(contests)}</i>\n\n"
            "Выберите конкурс для участия:"
        )

    if banner:
        await update.message.reply_photo(
            photo=banner, caption=text, parse_mode="HTML",
            reply_markup=kb.contests_keyboard(contests)
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb.contests_keyboard(contests))


async def cb_contests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contests = await db.get_active_contests()
    if not contests:
        text = "✨ <b>Конкурсы</b>\n\n😴 <i>Активных конкурсов нет.</i>"
    else:
        text = f"✨ <b>Конкурсы</b>\n\n<i>Активных конкурсов: {len(contests)}</i>\n\nВыберите:"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb.contests_keyboard(contests))


async def cb_contest_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contest_id = int(query.data.split("_")[1])
    contest = await db.get_contest(contest_id)
    if not contest:
        await query.answer("❌ Конкурс не найден", show_alert=True)
        return
    user_id = query.from_user.id
    is_participant = await db.is_contest_participant(contest_id, user_id)
    count = await db.get_contest_participants_count(contest_id)

    ends = f"\n⏰ <i>Завершается:</i> <b>{contest['ends_at']}</b>" if contest.get('ends_at') else ""
    status = "🟢 <b>Активен</b>" if contest['is_active'] else "🔴 <b>Завершён</b>"

    text = (
        f"✨ <b>{contest['title']}</b>\n\n"
        f"📌 <i>Статус:</i> {status}\n"
        f"👥 <i>Участников:</i> <b>{count}</b>{ends}\n\n"
        f"📝 <b>Описание:</b>\n{contest['description']}\n\n"
        f"📋 <b>Условия участия:</b>\n{contest['conditions']}\n\n"
        f"🏆 <b>Приз:</b>\n{contest['prize']}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=kb.contest_detail_keyboard(contest_id, is_participant)
    )


async def cb_contest_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contest_id = int(query.data.split("_")[2])
    user_id = query.from_user.id
    contest = await db.get_contest(contest_id)
    if not contest or not contest['is_active']:
        await query.answer("❌ Конкурс недоступен", show_alert=True)
        return
    joined = await db.join_contest(contest_id, user_id)
    if joined:
        await query.answer("🎉 Вы участвуете в конкурсе!", show_alert=True)
        uname = query.from_user.username or str(user_id)
        await notify_all_admins(
            context,
            f"🎯 <b>Новый участник конкурса!</b>\n\n"
            f"✨ <i>Конкурс:</i> <b>{contest['title']}</b>\n"
            f"👤 <i>Участник:</i> @{uname} (ID: {user_id})",
            parse_mode="HTML"
        )
    else:
        await query.answer("ℹ️ Вы уже участвуете в этом конкурсе!", show_alert=True)
    count = await db.get_contest_participants_count(contest_id)
    is_participant = True
    text = (
        f"✨ <b>{contest['title']}</b>\n\n"
        f"👥 <i>Участников:</i> <b>{count}</b>\n\n"
        f"📝 <b>Описание:</b>\n{contest['description']}\n\n"
        f"📋 <b>Условия:</b>\n{contest['conditions']}\n\n"
        f"🏆 <b>Приз:</b>\n{contest['prize']}"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=kb.contest_detail_keyboard(contest_id, is_participant)
    )


# ─── Robux Section ─────────────────────────────────────────────────────────────

async def cb_sub_robux(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banner = await db.get_section_banner("robux")
    text = (
        "💎 <b>Купить Robux</b>\n\n"
        "🎁 <i>В этом разделе вы можете купить робуксы для Roblox!</i>\n\n"
        "💡 <b>Доступные методы покупки:</b>\n"
        "• 🎁 <b>Геймпасс</b> — 5-7 дней | 1 R$ = 0.67₽\n"
        "• 💎 <b>Подарочная карта</b> — мгновенно\n"
        "• 🛍 <b>Паки</b> — с заходом в аккаунт\n"
        "• 👤 <b>Группой</b> — 14 дней | 1 R$ = 0.60₽\n"
        "• ⭐️ <b>Супер-пассы</b> — через игровые пассы\n\n"
        "Выберите способ покупки:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=kb.robux_main_keyboard())
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=kb.robux_main_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=kb.robux_main_keyboard(), parse_mode="HTML")


async def cb_robux_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cur_subcat_id'] = 6
    banner = await db.get_section_banner("robux")
    text = (
        "💎 <b>Купить Robux</b>\n\n"
        "🎁 <i>В этом разделе вы можете купить робуксы для Roblox!</i>\n\n"
        "Выберите способ покупки:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=kb.robux_main_keyboard())
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=kb.robux_main_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=kb.robux_main_keyboard(), parse_mode="HTML")


# ─── Robux: Gamepass ──────────────────────────────────────────────────────────

async def cb_robux_gamepass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault('robux_gp', {'qty': 0, 'recipient': ''})
    banner = await db.get_section_banner("robux_gamepass")
    gp = context.user_data['robux_gp']
    text = (
        "🎁 <b>Купить Robux геймпассом</b>\n\n"
        "📌 <i>Метод:</i> <b>Gamepass</b>\n"
        "⏱ <i>Срок:</i> <b>5-7 рабочих дней</b>\n\n"
        "💰 <i>Курс:</i> <b>1 R$ = 0.67₽ | 1 R$ = 0.45 ⭐️</b>\n\n"
        "❗️ <i>Робуксы приходят в течение 5-7 дней после создания геймпасса.</i>\n\n"
        "Укажите количество и получателя:"
    )
    keyboard = kb.robux_gamepass_keyboard(gp['qty'], gp['recipient'])
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=keyboard)
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def cb_robux_gp_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ <b>Введите количество Robux</b>\n\n"
        "💡 <i>Для геймпасса вам нужно будет создать геймпасс на указанную сумму.</i>\n"
        "📐 <i>Цена геймпасса = количество / 0.7 (Roblox берёт 30%)</i>\n\n"
        "Введите количество Robux (числом):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="robux_gamepass")]]),
        parse_mode="HTML"
    )
    return states.ROBUX_GAMEPASS_QTY


async def handle_robux_gp_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        qty = int(text)
        if qty < 1:
            await update.message.reply_text("❌ Введите положительное число:", parse_mode="HTML")
            return states.ROBUX_GAMEPASS_QTY
        gp = context.user_data.setdefault('robux_gp', {'qty': 0, 'recipient': ''})
        gp['qty'] = qty
        gamepass_price = round(qty / 0.7)
        await update.message.reply_text(
            f"✅ <b>Количество установлено: {qty} R$</b>\n\n"
            f"📐 <i>Вам нужно будет создать геймпасс стоимостью:</i> <b>{gamepass_price} R$</b>\n"
            f"💰 <i>Стоимость покупки:</i> <b>{round(qty * 0.67, 2):.2f}₽</b>",
            reply_markup=kb.robux_gamepass_keyboard(qty, gp.get('recipient', '')),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите целое число:", parse_mode="HTML")
        return states.ROBUX_GAMEPASS_QTY


async def cb_robux_gp_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👤 <b>Введите никнейм получателя в Roblox:</b>\n\n"
        "<i>Мы найдём пользователя и вы подтвердите, что это правильный аккаунт.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="robux_gamepass")]]),
        parse_mode="HTML"
    )
    context.user_data['robux_search_context'] = 'gamepass'
    return states.ROBUX_USERNAME_SEARCH


async def cb_robux_gp_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gp = context.user_data.get('robux_gp', {'qty': 0, 'recipient': ''})
    qty = gp.get('qty', 0)
    recipient = gp.get('recipient', '')
    if not qty:
        await query.answer("❌ Укажите количество Robux!", show_alert=True)
        return
    if not recipient:
        await query.answer("❌ Укажите получателя!", show_alert=True)
        return
    price_rub = round(qty * 0.67, 2)
    await query.edit_message_text(
        f"💳 <b>Оплата Robux (Геймпасс)</b>\n\n"
        f"💎 <i>Количество:</i> <b>{qty} R$</b>\n"
        f"👤 <i>Получатель:</i> <b>{recipient}</b>\n"
        f"💰 <i>Цена:</i> <b>{price_rub:.2f}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.robux_gamepass_payment_keyboard(qty, recipient),
        parse_mode="HTML"
    )


async def _robux_gamepass_paid(context, user_id: int, qty: int, recipient: str, method: str, amount: float):
    order_id = await db.add_order(user_id, f"Robux Gamepass {qty}R$ → {recipient}", amount, method)
    uname_from = (await context.bot.get_chat(user_id)).username or str(user_id)
    gamepass_price = round(qty / 0.7)
    await notify_all_admins(
        context,
        f"💎 <b>ЗАКАЗ: Robux (Геймпасс)</b>\n\n"
        f"👤 <i>Покупатель:</i> @{uname_from} (ID: {user_id})\n"
        f"💎 <i>Количество:</i> <b>{qty} R$</b>\n"
        f"👤 <i>Получатель (Roblox):</i> <b>{recipient}</b>\n"
        f"📐 <i>Цена геймпасса:</i> <b>{gamepass_price} R$</b>\n"
        f"💰 <i>Сумма оплаты:</i> <b>{amount:.2f}₽</b>\n"
        f"💳 <i>Способ оплаты:</i> <b>{method}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить заказ", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
    return order_id


async def cb_robux_gp_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    price_rub = round(qty * 0.67, 2)
    usdt_amount = await get_crypto_bot_commission_amount(price_rub)
    invoice = await create_invoice(usdt_amount, f"GubaShop: {qty} Robux Gamepass → {recipient}")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта.", parse_mode="HTML")
        return
    context.user_data['robux_gp_pending'] = {'qty': qty, 'recipient': recipient, 'method': 'Crypto Bot', 'amount': price_rub}
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n💎 {qty} R$ → {recipient}\n💳 {round(price_rub*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"robux_gp_paid_crypto_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_gp_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    price_rub = round(qty * 0.67, 2)
    order_id = await _robux_gamepass_paid(context, query.from_user.id, qty, recipient, "crypto_bot", price_rub)
    context.user_data.pop('robux_gp', None)
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💎 <b>{qty} R$</b> → {recipient}\n<i>Ожидайте — робуксы придут в течение 5-7 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gp_pay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    price_rub = round(qty * 0.67 * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты (YooMoney)</b>\n\n💎 {qty} R$ → {recipient}\n💳 {price_rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"robux_gp_paid_yoo_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_gp_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    price_rub = round(qty * 0.67, 2)
    order_id = await _robux_gamepass_paid(context, query.from_user.id, qty, recipient, "yoomoney", price_rub)
    context.user_data.pop('robux_gp', None)
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💎 <b>{qty} R$</b> → {recipient}\n<i>Ожидайте 5-7 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gp_pay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    price_rub = round(qty * 0.67, 2)
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < price_rub:
        await query.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    await db.update_balance(user_id, -price_rub)
    order_id = await _robux_gamepass_paid(context, user_id, qty, recipient, "balance", price_rub)
    context.user_data.pop('robux_gp', None)
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n💎 <b>{qty} R$</b> → {recipient}\n<i>Ожидайте 5-7 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gp_pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    gp = context.user_data.get('robux_gp', {})
    recipient = gp.get('recipient', 'не указан')
    stars_qty = round(qty * 0.45)
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"{qty} Robux (Геймпасс)",
            description=f"Покупка {qty} Robux методом Gamepass для {recipient}",
            payload=f"robux_gp_{qty}_{recipient}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"{qty} Robux", stars_qty)],
        )
        await query.edit_message_text(
            f"⭐️ <b>Счёт отправлен ниже ⬇️</b>\n\n💎 {qty} R$ → {recipient}\n⭐️ {stars_qty} Stars",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode="HTML")


# ─── Robux: Gift Card ─────────────────────────────────────────────────────────

async def cb_robux_giftcard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banner = await db.get_section_banner("robux_gift")
    text = (
        "💎 <b>Купить Robux подарочной картой</b>\n\n"
        "📌 <i>Метод:</i> <b>Подарочная карта</b>\n\n"
        "❗️ <i>Некоторые подарочные карты могут не подходить под ваш регион.</i>\n\n"
        "🌍 <b>Регион: Global</b> (любая страна кроме Вьетнама)\n\n"
        "Выберите количество Robux:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=kb.robux_giftcard_keyboard())
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=kb.robux_giftcard_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=kb.robux_giftcard_keyboard(), parse_mode="HTML")


async def cb_robux_gc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    if not card:
        await query.answer("❌ Не найдено", show_alert=True)
        return
    await query.edit_message_text(
        f"💎 <b>Подарочная карта {robux} R$</b>\n\n"
        f"🌍 <i>Регион:</i> <b>{card['region']}</b>\n"
        f"💰 <i>Стоимость:</i> <b>{card['rub']}₽</b> / <b>{card['stars']} ⭐️</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.robux_giftcard_payment_keyboard(robux, card['rub'], card['stars']),
        parse_mode="HTML"
    )


async def _robux_gc_paid(context, user_id: int, robux: int, method: str, amount: float):
    order_id = await db.add_order(user_id, f"Robux Gift Card {robux}R$", amount, method)
    uname = (await context.bot.get_chat(user_id)).username or str(user_id)
    await notify_all_admins(
        context,
        f"💎 <b>ЗАКАЗ: Robux Gift Card</b>\n\n"
        f"👤 <i>Покупатель:</i> @{uname} (ID: {user_id})\n"
        f"💎 <i>Карта:</i> <b>{robux} R$</b>\n"
        f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n"
        f"💳 <i>Способ:</i> <b>{method}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Выдать карту", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
    return order_id


async def cb_robux_gc_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    if not card:
        return
    usdt_amount = await get_crypto_bot_commission_amount(card['rub'])
    invoice = await create_invoice(usdt_amount, f"GubaShop: Robux Gift Card {robux}R$")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка создания счёта.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n💎 Gift Card {robux} R$\n💳 {round(card['rub']*1.015,2):.2f}₽ ({usdt_amount} USDT)",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"robux_gc_paid_crypto_{robux}"),
        parse_mode="HTML"
    )


async def cb_robux_gc_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    amount = card['rub'] if card else 0
    order_id = await _robux_gc_paid(context, query.from_user.id, robux, "crypto_bot", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💎 <b>Gift Card {robux} R$</b>\n<i>Ожидайте выдачи карты.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gc_pay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    if not card:
        return
    rub = round(card['rub'] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты (YooMoney)</b>\n\n💎 Gift Card {robux} R$\n💳 {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"robux_gc_paid_yoo_{robux}"),
        parse_mode="HTML"
    )


async def cb_robux_gc_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    amount = card['rub'] if card else 0
    order_id = await _robux_gc_paid(context, query.from_user.id, robux, "yoomoney", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка отправлена!</b>\n\n💎 <b>Gift Card {robux} R$</b>\n<i>Ожидайте выдачи карты.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gc_pay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    if not card:
        return
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < card['rub']:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    await db.update_balance(user_id, -card['rub'])
    order_id = await _robux_gc_paid(context, user_id, robux, "balance", card['rub'])
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n💎 <b>Gift Card {robux} R$</b>\n<i>Ожидайте выдачи карты.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_gc_pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    card = next((c for c in kb.ROBUX_GIFT_CARDS if c['robux'] == robux), None)
    if not card:
        return
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Robux Gift Card {robux}R$",
            description=f"Подарочная карта {robux} Robux | {card['region']}",
            payload=f"robux_gc_{robux}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"Gift Card {robux}R$", card['stars'])],
        )
        await query.edit_message_text(
            f"⭐️ <b>Счёт отправлен ниже ⬇️</b>\n\n💎 Gift Card {robux} R$\n⭐️ {card['stars']} Stars",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode="HTML")


# ─── Robux: Packs ────────────────────────────────────────────────────────────

async def cb_robux_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banner = await db.get_section_banner("robux_packs")
    text = (
        "🛍 <b>Купить Robux паками</b>\n\n"
        "📌 <i>Метод:</i> <b>Паки (с заходом в аккаунт)</b>\n\n"
        "❗️ <i>Для этого метода потребуется доступ к вашему аккаунту Roblox.</i>\n\n"
        "Выберите пак:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=kb.robux_packs_keyboard())
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=kb.robux_packs_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=kb.robux_packs_keyboard(), parse_mode="HTML")


async def cb_robux_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        await query.answer("❌ Не найдено", show_alert=True)
        return
    context.user_data['robux_pack_robux'] = robux
    await query.edit_message_text(
        f"🛍 <b>Пак {robux} R$</b>\n\n"
        f"💰 <i>Стоимость:</i> <b>{pack['rub']}₽</b>\n\n"
        f"⚠️ <i>Для покупки потребуется доступ к вашему Roblox аккаунту.</i>\n\n"
        f"📝 Пожалуйста, введите логин от аккаунта Roblox:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="robux_packs")]]),
        parse_mode="HTML"
    )
    return states.ROBUX_PACKS_LOGIN


async def handle_robux_packs_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['robux_packs_login'] = update.message.text.strip()
    await update.message.reply_text(
        "🔑 <b>Введите пароль от аккаунта Roblox:</b>\n\n"
        "<i>Сообщение будет удалено сразу после отправки для безопасности.</i>",
        parse_mode="HTML"
    )
    return states.ROBUX_PACKS_PASSWORD


async def handle_robux_packs_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['robux_packs_password'] = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    await update.message.reply_text(
        "📧 <b>Подтверждена ли почта на аккаунте?</b>\n\n"
        "Ответьте: <b>да</b> или <b>нет</b>",
        parse_mode="HTML"
    )
    return states.ROBUX_PACKS_EMAIL_CONFIRMED


async def handle_robux_packs_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    context.user_data['robux_packs_email'] = text
    await update.message.reply_text(
        "🔐 <b>Введите 2 резервных кода от аккаунта</b>\n\n"
        "<i>Введите через запятую или каждый с новой строки.</i>",
        parse_mode="HTML"
    )
    return states.ROBUX_PACKS_BACKUP_CODES


async def handle_robux_packs_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codes = update.message.text.strip()
    context.user_data['robux_packs_codes'] = codes
    robux = context.user_data.get('robux_pack_robux', 0)
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        await update.message.reply_text("❌ Ошибка. Начните заново.", parse_mode="HTML")
        return ConversationHandler.END

    # Show payment options
    await update.message.reply_text(
        f"✅ <b>Данные получены!</b>\n\n"
        f"🛍 <b>Пак {robux} R$</b>\n"
        f"💰 <b>Стоимость: {pack['rub']}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb.robux_packs_payment_keyboard(robux, pack['rub']),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def _robux_pack_paid(context, user_id: int, robux: int, method: str, amount: float):
    login = context.user_data.pop('robux_packs_login', 'не указан')
    password = context.user_data.pop('robux_packs_password', 'не указан')
    email = context.user_data.pop('robux_packs_email', 'не указан')
    codes = context.user_data.pop('robux_packs_codes', 'не указаны')

    order_id = await db.add_order(user_id, f"Robux Pack {robux}R$", amount, method,
                                   extra_data=f"login:{login}|email:{email}")
    uname = (await context.bot.get_chat(user_id)).username or str(user_id)
    await notify_all_admins(
        context,
        f"🛍 <b>ЗАКАЗ: Robux Пак (с заходом)</b>\n\n"
        f"👤 <i>Покупатель:</i> @{uname} (ID: {user_id})\n"
        f"💎 <i>Количество:</i> <b>{robux} R$</b>\n"
        f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n"
        f"💳 <i>Способ:</i> <b>{method}</b>\n\n"
        f"🔐 <b>ДАННЫЕ ДЛЯ ВХОДА:</b>\n"
        f"👤 Логин: <code>{login}</code>\n"
        f"🔑 Пароль: <code>{password}</code>\n"
        f"📧 Почта подтверждена: <b>{email}</b>\n"
        f"🔐 Резервные коды: <code>{codes}</code>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Выдать Robux", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
    return order_id


async def cb_robux_pack_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        return
    usdt_amount = await get_crypto_bot_commission_amount(pack['rub'])
    invoice = await create_invoice(usdt_amount, f"GubaShop: Robux Pack {robux}R$")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n🛍 Pack {robux} R$\n💳 {round(pack['rub']*1.015,2):.2f}₽",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"robux_pack_paid_crypto_{robux}"),
        parse_mode="HTML"
    )


async def cb_robux_pack_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    amount = pack['rub'] if pack else 0
    order_id = await _robux_pack_paid(context, query.from_user.id, robux, "crypto_bot", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n🛍 <b>Pack {robux} R$</b>\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_pack_pay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        return
    rub = round(pack['rub'] * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты (YooMoney)</b>\n\n🛍 Pack {robux} R$\n💳 {rub:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"robux_pack_paid_yoo_{robux}"),
        parse_mode="HTML"
    )


async def cb_robux_pack_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    amount = pack['rub'] if pack else 0
    order_id = await _robux_pack_paid(context, query.from_user.id, robux, "yoomoney", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n🛍 <b>Pack {robux} R$</b>\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_pack_pay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        return
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < pack['rub']:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    await db.update_balance(user_id, -pack['rub'])
    order_id = await _robux_pack_paid(context, user_id, robux, "balance", pack['rub'])
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n🛍 <b>Pack {robux} R$</b>\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_pack_pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    robux = int(query.data.split("_")[-1])
    pack = next((p for p in kb.ROBUX_PACKS if p['robux'] == robux), None)
    if not pack:
        return
    stars = round(pack['rub'] / 1.26)
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Robux Pack {robux}R$",
            description=f"Пак {robux} Robux с заходом в аккаунт",
            payload=f"robux_pack_{robux}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"Pack {robux}R$", stars)],
        )
        await query.edit_message_text(f"⭐️ <b>Счёт отправлен ниже ⬇️</b>\n\n🛍 Pack {robux} R$\n⭐️ {stars} Stars", parse_mode="HTML")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode="HTML")


# ─── Robux: Group ─────────────────────────────────────────────────────────────

async def cb_robux_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault('robux_group', {'qty': 0, 'recipient': ''})
    banner = await db.get_section_banner("robux_group")
    grp = context.user_data['robux_group']
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    rate_stars = float(await db.get_setting("robux_group_rate_stars", "0.45"))
    text = (
        "👤 <b>Купить Robux через группу</b>\n\n"
        "📌 <i>Метод:</i> <b>Группа (14 дней)</b>\n"
        f"⏱ <i>Срок:</i> <b>14 рабочих дней</b>\n\n"
        f"💰 <i>Курс:</i> <b>1 R$ = {rate_rub}₽ | 1 R$ = {rate_stars} ⭐️</b>\n\n"
        "📋 <i>Как это работает:</i>\n"
        "1️⃣ Укажите ваш ник Roblox и количество R$\n"
        "2️⃣ Оплатите заказ\n"
        "3️⃣ После оплаты получите ссылку на группу\n"
        "4️⃣ Вступите — робуксы придут через 14 дней\n\n"
        "Укажите количество и ваш ник Roblox:"
    )
    keyboard = kb.robux_group_keyboard(grp['qty'], grp['recipient'], rate_rub, rate_stars)
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=keyboard)
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def cb_robux_group_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✏️ <b>Введите количество Robux для покупки через группу:</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="robux_group")]]),
        parse_mode="HTML"
    )
    return states.ROBUX_GROUP_QTY


async def handle_robux_group_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        qty = int(text)
        if qty < 1:
            await update.message.reply_text("❌ Введите положительное число:", parse_mode="HTML")
            return states.ROBUX_GROUP_QTY
        grp = context.user_data.setdefault('robux_group', {'qty': 0, 'recipient': ''})
        grp['qty'] = qty
        rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
        rate_stars = float(await db.get_setting("robux_group_rate_stars", "0.45"))
        await update.message.reply_text(
            f"✅ <b>Количество: {qty} R$</b>\n💰 Стоимость: <b>{qty * rate_rub:.2f}₽</b>",
            reply_markup=kb.robux_group_keyboard(qty, grp.get('recipient', ''), rate_rub, rate_stars),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите целое число:", parse_mode="HTML")
        return states.ROBUX_GROUP_QTY


async def cb_robux_group_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👤 <b>Введите ваш никнейм в Roblox:</b>\n\n"
        "<i>Это нужно чтобы мы знали, кому выдать Robux через группу.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="robux_group")]]),
        parse_mode="HTML"
    )
    context.user_data['robux_search_context'] = 'group'
    return states.ROBUX_GROUP_RECIPIENT


async def handle_robux_group_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recipient = update.message.text.strip()
    grp = context.user_data.setdefault('robux_group', {'qty': 0, 'recipient': ''})
    grp['recipient'] = recipient
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    rate_stars = float(await db.get_setting("robux_group_rate_stars", "0.45"))
    await update.message.reply_text(
        f"✅ <b>Ваш ник Roblox: {recipient}</b>",
        reply_markup=kb.robux_group_keyboard(grp['qty'], recipient, rate_rub, rate_stars),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cb_robux_group_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    grp = context.user_data.get('robux_group', {'qty': 0, 'recipient': ''})
    qty = grp.get('qty', 0)
    recipient = grp.get('recipient', '')
    if not qty:
        await query.answer("❌ Укажите количество!", show_alert=True)
        return
    if not recipient:
        await query.answer("❌ Укажите ваш ник Roblox!", show_alert=True)
        return
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    rate_stars = float(await db.get_setting("robux_group_rate_stars", "0.45"))
    await query.edit_message_text(
        f"💳 <b>Оплата Robux (Группой)</b>\n\n"
        f"💎 <b>{qty} R$</b> | ник: <b>{recipient}</b>\n"
        f"💰 <b>{qty * rate_rub:.2f}₽</b>\n\nВыберите способ оплаты:",
        reply_markup=kb.robux_group_payment_keyboard(qty, recipient, rate_rub, rate_stars),
        parse_mode="HTML"
    )


async def _robux_group_paid(context, user_id: int, qty: int, recipient: str, method: str, amount: float):
    order_id = await db.add_order(user_id, f"Robux Group {qty}R$ → {recipient}", amount, method)
    uname = (await context.bot.get_chat(user_id)).username or str(user_id)
    await notify_all_admins(
        context,
        f"👤 <b>ЗАКАЗ: Robux (Группой)</b>\n\n"
        f"👤 <i>Покупатель:</i> @{uname} (ID: {user_id})\n"
        f"💎 <b>{qty} R$</b> | Roblox ник: <b>{recipient}</b>\n"
        f"💰 <b>{amount:.2f}₽</b> | {method}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
    return order_id


async def cb_robux_group_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    price = round(qty * rate_rub * 1.015, 2)
    usdt = await get_crypto_bot_commission_amount(qty * rate_rub)
    invoice = await create_invoice(usdt, f"GubaShop: {qty} Robux Group")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n💎 {qty} R$ | ник: {recipient}\n💳 {price:.2f}₽",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"robux_group_paid_crypto_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_group_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    amount = round(qty * rate_rub, 2)
    order_id = await _robux_group_paid(context, query.from_user.id, qty, recipient, "crypto_bot", amount)
    context.user_data.pop('robux_group', None)
    group_link = await db.get_setting("robux_group_link", "")
    link_part = f"\n\n🔗 <b>Ссылка на группу:</b> <a href='{group_link}'>{group_link}</a>" if group_link else ""
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n💎 <b>{qty} R$</b> | ник: {recipient}{link_part}\n\n<i>Вступите в группу и ожидайте 14 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def cb_robux_group_pay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    price = round(qty * rate_rub * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты (YooMoney)</b>\n\n💎 {qty} R$ | ник: {recipient}\n💳 {price:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"robux_group_paid_yoo_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_group_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    amount = round(qty * rate_rub, 2)
    order_id = await _robux_group_paid(context, query.from_user.id, qty, recipient, "yoomoney", amount)
    context.user_data.pop('robux_group', None)
    group_link = await db.get_setting("robux_group_link", "")
    link_part = f"\n\n🔗 <b>Ссылка на группу:</b> <a href='{group_link}'>{group_link}</a>" if group_link else ""
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n💎 <b>{qty} R$</b> | ник: {recipient}{link_part}\n\n<i>Вступите в группу и ожидайте 14 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def cb_robux_group_pay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_rub = float(await db.get_setting("robux_group_rate_rub", "0.60"))
    amount = round(qty * rate_rub, 2)
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < amount:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    await db.update_balance(user_id, -amount)
    order_id = await _robux_group_paid(context, user_id, qty, recipient, "balance", amount)
    context.user_data.pop('robux_group', None)
    group_link = await db.get_setting("robux_group_link", "")
    link_part = f"\n\n🔗 <b>Ссылка на группу:</b> <a href='{group_link}'>{group_link}</a>" if group_link else ""
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n💎 <b>{qty} R$</b> | ник: {recipient}{link_part}\n\n<i>Вступите в группу и ожидайте 14 дней.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def cb_robux_group_pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[-1])
    grp = context.user_data.get('robux_group', {})
    recipient = grp.get('recipient', 'не указано')
    rate_stars = float(await db.get_setting("robux_group_rate_stars", "0.45"))
    stars = round(qty * rate_stars)
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Robux Group {qty}R$",
            description=f"{qty} Robux через группу | ник: {recipient}",
            payload=f"robux_group_{qty}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"Group {qty}R$", stars)],
        )
        group_link = await db.get_setting("robux_group_link", "")
        link_part = f"\n\n🔗 <b>Ссылка на группу:</b> <a href='{group_link}'>{group_link}</a>" if group_link else ""
        await query.edit_message_text(f"⭐️ <b>Счёт отправлен ниже ⬇️</b>\n\n💎 {qty} R$ | ник: {recipient}\n⭐️ {stars} Stars{link_part}\n\n<i>После оплаты вступите в группу.</i>", parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode="HTML")


# ─── Robux: Superpasses ───────────────────────────────────────────────────────

async def cb_robux_superpasses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banner = await db.get_section_banner("robux_superpasses")
    text = (
        "⭐️ <b>Супер-пассы Roblox</b>\n\n"
        "📌 <i>Метод:</i> <b>Игровые геймпассы</b>\n\n"
        "💰 <i>Курс:</i> <b>1 R$ = 0.59₽ | 1 R$ = 0.35 ⭐️</b>\n\n"
        "🎮 Выберите игру для покупки суперпасса:"
    )
    if banner:
        try:
            await query.message.reply_photo(photo=banner, caption=text, parse_mode="HTML", reply_markup=kb.robux_superpasses_keyboard())
            await query.message.delete()
        except Exception:
            await query.edit_message_text(text, reply_markup=kb.robux_superpasses_keyboard(), parse_mode="HTML")
    else:
        await query.edit_message_text(text, reply_markup=kb.robux_superpasses_keyboard(), parse_mode="HTML")


async def cb_robux_sp_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_idx = int(query.data.split("_")[-1])
    game = kb.ROBLOX_SUPERPASSES_GAMES[game_idx] if game_idx < len(kb.ROBLOX_SUPERPASSES_GAMES) else "?"
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {'qty': 0, 'recipient': ''})
    await query.edit_message_text(
        f"⭐️ <b>Суперпасс: {game}</b>\n\n"
        f"💰 <i>Курс:</i> <b>1 R$ = 0.59₽</b>\n\n"
        f"Укажите количество R$ и никнейм получателя:",
        reply_markup=kb.robux_superpass_buy_keyboard(game_idx, sp_data['qty'], sp_data['recipient']),
        parse_mode="HTML"
    )


async def cb_robux_sp_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_idx = int(query.data.split("_")[-1])
    await query.edit_message_text(
        "✏️ <b>Введите количество Robux для суперпасса:</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"robux_sp_game_{game_idx}")]]),
        parse_mode="HTML"
    )
    context.user_data['robux_sp_current_game'] = game_idx
    return states.ROBUX_SUPERPASSES_GAME


async def handle_robux_sp_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    game_idx = context.user_data.get('robux_sp_current_game', 0)
    try:
        qty = int(text)
        sp_data = context.user_data.setdefault(f'robux_sp_{game_idx}', {'qty': 0, 'recipient': ''})
        sp_data['qty'] = qty
        await update.message.reply_text(
            f"✅ <b>Количество: {qty} R$</b>\n💰 Стоимость: <b>{round(qty*0.59,2):.2f}₽</b>",
            reply_markup=kb.robux_superpass_buy_keyboard(game_idx, qty, sp_data['recipient']),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите целое число:", parse_mode="HTML")
        return states.ROBUX_SUPERPASSES_GAME


async def cb_robux_sp_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_idx = int(query.data.split("_")[-1])
    context.user_data['robux_search_context'] = f'sp_{game_idx}'
    await query.edit_message_text(
        "👤 <b>Введите никнейм получателя в Roblox:</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"robux_sp_game_{game_idx}")]]),
        parse_mode="HTML"
    )
    return states.ROBUX_USERNAME_SEARCH


async def cb_robux_sp_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_idx = int(query.data.split("_")[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {'qty': 0, 'recipient': ''})
    qty = sp_data.get('qty', 0)
    recipient = sp_data.get('recipient', '')
    game = kb.ROBLOX_SUPERPASSES_GAMES[game_idx] if game_idx < len(kb.ROBLOX_SUPERPASSES_GAMES) else "?"
    if not qty:
        await query.answer("❌ Укажите количество!", show_alert=True)
        return
    if not recipient:
        await query.answer("❌ Укажите получателя!", show_alert=True)
        return
    await query.edit_message_text(
        f"💳 <b>Оплата суперпасса</b>\n\n"
        f"🎮 <b>{game}</b>\n"
        f"💎 <b>{qty} R$</b> → {recipient}\n"
        f"💰 <b>{round(qty*0.59,2):.2f}₽</b>\n\nВыберите способ оплаты:",
        reply_markup=kb.robux_superpass_payment_keyboard(game_idx, qty),
        parse_mode="HTML"
    )


async def _robux_sp_paid(context, user_id: int, game_idx: int, qty: int, recipient: str, method: str, amount: float):
    game = kb.ROBLOX_SUPERPASSES_GAMES[game_idx] if game_idx < len(kb.ROBLOX_SUPERPASSES_GAMES) else "?"
    order_id = await db.add_order(user_id, f"Robux Superpass {qty}R$ {game} → {recipient}", amount, method)
    uname = (await context.bot.get_chat(user_id)).username or str(user_id)
    await notify_all_admins(
        context,
        f"⭐️ <b>ЗАКАЗ: Robux Суперпасс</b>\n\n"
        f"👤 @{uname} (ID: {user_id})\n"
        f"🎮 <b>{game}</b>\n"
        f"💎 <b>{qty} R$</b> → {recipient}\n"
        f"💰 <b>{amount:.2f}₽</b> | {method}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
    return order_id


async def cb_robux_sp_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    price = round(qty * 0.59, 2)
    usdt = await get_crypto_bot_commission_amount(price)
    invoice = await create_invoice(usdt, f"GubaShop: Robux SP {qty}R$")
    if not invoice["ok"]:
        await query.edit_message_text("❌ Ошибка.", parse_mode="HTML")
        return
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты</b>\n\n⭐️ {qty} R$ → {recipient}\n💳 {round(price*1.015,2):.2f}₽",
        reply_markup=kb.crypto_pay_keyboard(invoice["pay_url"], f"robux_sp_paid_crypto_{game_idx}_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_sp_paid_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    amount = round(qty * 0.59, 2)
    order_id = await _robux_sp_paid(context, query.from_user.id, game_idx, qty, recipient, "crypto_bot", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n⭐️ <b>{qty} R$</b> → {recipient}\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_sp_pay_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    price = round(qty * 0.59 * 1.03, 2)
    await query.edit_message_text(
        f"⏳ <b>Ожидание оплаты (YooMoney)</b>\n\n⭐️ {qty} R$ → {recipient}\n💳 {price:.2f}₽",
        reply_markup=kb.yoo_pay_keyboard(f"robux_sp_paid_yoo_{game_idx}_{qty}"),
        parse_mode="HTML"
    )


async def cb_robux_sp_paid_yoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    amount = round(qty * 0.59, 2)
    order_id = await _robux_sp_paid(context, query.from_user.id, game_idx, qty, recipient, "yoomoney", amount)
    await query.edit_message_text(
        f"✅ <b>Заявка принята!</b>\n\n⭐️ <b>{qty} R$</b> → {recipient}\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_sp_pay_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    amount = round(qty * 0.59, 2)
    user_id = query.from_user.id
    balance = await db.get_balance(user_id)
    if balance < amount:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    await db.update_balance(user_id, -amount)
    order_id = await _robux_sp_paid(context, user_id, game_idx, qty, recipient, "balance", amount)
    await query.edit_message_text(
        f"✅ <b>Заказ оплачен!</b>\n\n⭐️ <b>{qty} R$</b> → {recipient}\n<i>Ожидайте выдачи.</i>",
        reply_markup=kb.order_chat_user_keyboard(order_id),
        parse_mode="HTML"
    )


async def cb_robux_sp_pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_idx = int(parts[-2])
    qty = int(parts[-1])
    sp_data = context.user_data.get(f'robux_sp_{game_idx}', {})
    recipient = sp_data.get('recipient', 'не указано')
    game = kb.ROBLOX_SUPERPASSES_GAMES[game_idx] if game_idx < len(kb.ROBLOX_SUPERPASSES_GAMES) else "?"
    stars = round(qty * 0.35)
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Robux Superpass {qty}R$",
            description=f"Суперпасс {game} → {recipient}",
            payload=f"robux_sp_{game_idx}_{qty}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"SP {qty}R$", stars)],
        )
        await query.edit_message_text(f"⭐️ <b>Счёт отправлен ⬇️</b>\n\n⭐️ {qty} R$ → {recipient}\n⭐️ {stars} Stars", parse_mode="HTML")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", parse_mode="HTML")


# ─── Roblox Username Search ───────────────────────────────────────────────────

async def handle_roblox_username_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roblox_api import search_roblox_users, get_user_avatar_url
    username = update.message.text.strip()
    search_ctx = context.user_data.get('robux_search_context', 'gamepass')

    await update.message.reply_text("🔍 <b>Поиск пользователя...</b>", parse_mode="HTML")
    results = await search_roblox_users(username)

    if not results:
        await update.message.reply_text(
            f"❌ <b>Пользователь «{username}» не найден в Roblox.</b>\n\nПопробуйте ещё раз:",
            parse_mode="HTML"
        )
        return states.ROBUX_USERNAME_SEARCH

    user_data = results[0]
    roblox_id = user_data.get('id')
    display_name = user_data.get('displayName', username)
    roblox_name = user_data.get('name', username)

    context.user_data['roblox_found_user'] = {
        'id': roblox_id,
        'display_name': display_name,
        'name': roblox_name,
        'context': search_ctx
    }

    avatar_url = await get_user_avatar_url(roblox_id)
    text = (
        f"🔍 <b>Найден пользователь Roblox:</b>\n\n"
        f"👤 <i>Никнейм:</i> <b>{roblox_name}</b>\n"
        f"✨ <i>Отображаемое имя:</i> <b>{display_name}</b>\n"
        f"🆔 <i>ID:</i> <code>{roblox_id}</code>\n\n"
        f"<i>Это правильный получатель?</i>"
    )
    confirm_kb = kb.roblox_user_confirm_keyboard(roblox_id, search_ctx)

    if avatar_url:
        try:
            await update.message.reply_photo(photo=avatar_url, caption=text, parse_mode="HTML", reply_markup=confirm_kb)
        except Exception:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=confirm_kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=confirm_kb)

    return ConversationHandler.END


async def _safe_edit_or_replace(query, text: str, parse_mode: str = "HTML", reply_markup=None):
    """Edit message text, or delete+resend if the message is a photo."""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_message(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def cb_roblox_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    roblox_user_id = int(parts[2])
    search_ctx = "_".join(parts[3:])

    found = context.user_data.get('roblox_found_user', {})
    roblox_name = found.get('name', str(roblox_user_id))

    if search_ctx == 'gamepass':
        gp = context.user_data.setdefault('robux_gp', {'qty': 0, 'recipient': ''})
        gp['recipient'] = roblox_name
        await _safe_edit_or_replace(query, f"✅ <b>Получатель выбран: {roblox_name}</b>")
        await cb_robux_gamepass(update, context)
    elif search_ctx == 'group':
        grp = context.user_data.setdefault('robux_group', {'qty': 0, 'recipient': ''})
        grp['recipient'] = roblox_name
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад к выбору количества", callback_data="robux_group")]
        ])
        await _safe_edit_or_replace(
            query,
            f"✅ <b>Никнейм выбран: {roblox_name}</b>\n\nТеперь вернитесь и укажите количество R$:",
            reply_markup=back_kb
        )
    elif search_ctx.startswith('sp_'):
        game_idx = int(search_ctx.split('_')[1])
        sp = context.user_data.setdefault(f'robux_sp_{game_idx}', {'qty': 0, 'recipient': ''})
        sp['recipient'] = roblox_name
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад к выбору количества", callback_data=f"robux_sp_game_{game_idx}")]
        ])
        await _safe_edit_or_replace(
            query,
            f"✅ <b>Получатель выбран: {roblox_name}</b>\n\nТеперь вернитесь и укажите количество R$:",
            reply_markup=back_kb
        )


async def cb_roblox_search_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    search_ctx = "_".join(query.data.split("_")[3:])
    context.user_data['robux_search_context'] = search_ctx
    back_cb = f"robux_{search_ctx}" if search_ctx in ['gamepass', 'group'] else "robux_superpasses"
    await _safe_edit_or_replace(
        query,
        "👤 <b>Введите другой никнейм в Roblox:</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]])
    )
    return states.ROBUX_USERNAME_SEARCH


# ─── Admin panel ───────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await db.is_admin(user_id):
        await update.message.reply_text("❌ <b>У вас нет прав администратора.</b>", parse_mode="HTML")
        return
    await update.message.reply_text(
        "🛡 <b>Панель администратора GubaShop</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )


async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        f"📊 <b>Статистика GubaShop</b>\n\n"
        f"👥 <i>Всего пользователей:</i> <b>{stats['total_users']}</b>\n"
        f"✅ <i>Приняли политику:</i> <b>{stats['agreed']}</b>\n"
        f"🛒 <i>Всего заказов:</i> <b>{stats['total_orders']}</b>\n"
        f"💰 <i>Общая выручка:</i> <b>{stats['total_revenue']:.2f}₽</b>"
    )
    await query.edit_message_text(text, reply_markup=kb.admin_keyboard(), parse_mode="HTML")


async def cb_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    rate = await db.get_setting("stars_rate", "1.26")
    recipient = await db.get_setting("stars_recipient", "не задан")
    rg_rate_rub = await db.get_setting("robux_group_rate_rub", "0.60")
    rg_rate_stars = await db.get_setting("robux_group_rate_stars", "0.45")
    rg_link = await db.get_setting("robux_group_link", "не задана")
    await query.edit_message_text(
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"⭐️ <i>Курс звёзд:</i> <b>1 ⭐️ = {rate}₽</b>\n"
        f"👤 <i>Получатель звёзд:</i> <b>{recipient or 'не задан'}</b>\n\n"
        f"💰 <i>Курс группы (₽):</i> <b>1 R$ = {rg_rate_rub}₽</b>\n"
        f"⭐️ <i>Курс группы (Stars):</i> <b>1 R$ = {rg_rate_stars} ⭐️</b>\n"
        f"🔗 <i>Группа Roblox:</i> <b>{rg_link}</b>",
        reply_markup=kb.admin_settings_keyboard(),
        parse_mode="HTML"
    )


async def cb_admin_settings_stars_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    rate = await db.get_setting("stars_rate", "1.26")
    await query.edit_message_text(
        f"⭐️ <b>Изменение курса звёзд</b>\n\n"
        f"<i>Текущий курс: 1 ⭐️ = {rate}₽</i>\n\n"
        f"Введите новый курс (число, например: 1.26):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]),
        parse_mode="HTML"
    )
    return states.ADMIN_SETTINGS_STARS_RECIPIENT


async def handle_admin_settings_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        rate = float(update.message.text.strip())
        await db.set_setting("stars_rate", str(rate))
        await update.message.reply_text(
            f"✅ <b>Курс звёзд обновлён: 1 ⭐️ = {rate}₽</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите числовое значение.", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_settings_stars_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    current = await db.get_setting("stars_recipient", "")
    await query.edit_message_text(
        f"👤 <b>Получатель звёзд</b>\n\n"
        f"<i>Текущий: {current or 'не задан'}</i>\n\n"
        f"Введите Telegram username или ID получателя звёзд\n"
        f"(кому пересылать звёзды при покупке):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]),
        parse_mode="HTML"
    )
    context.user_data['admin_setting_type'] = 'recipient'
    return states.ADMIN_SETTINGS_STARS_RECIPIENT


async def handle_admin_settings_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    recipient = update.message.text.strip()
    setting_type = context.user_data.get('admin_setting_type', 'recipient')
    if setting_type == 'recipient':
        await db.set_setting("stars_recipient", recipient)
        await update.message.reply_text(
            f"✅ <b>Получатель звёзд установлен: {recipient}</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        try:
            rate = float(recipient)
            await db.set_setting("stars_rate", str(rate))
            await update.message.reply_text(
                f"✅ <b>Курс звёзд: 1 ⭐️ = {rate}₽</b>",
                reply_markup=kb.admin_keyboard(),
                parse_mode="HTML"
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат.", parse_mode="HTML")
    context.user_data.pop('admin_setting_type', None)
    return ConversationHandler.END


async def cb_admin_robux_group_rate_rub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    current = await db.get_setting("robux_group_rate_rub", "0.60")
    await query.edit_message_text(
        f"💰 <b>Курс группы — рубли</b>\n\n"
        f"<i>Текущий курс: 1 R$ = {current}₽</i>\n\n"
        f"Введите новый курс (например: 0.60):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]),
        parse_mode="HTML"
    )
    return states.ADMIN_ROBUX_GROUP_RATE_RUB


async def handle_admin_robux_group_rate_rub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        rate = float(update.message.text.strip())
        if rate <= 0:
            raise ValueError
        await db.set_setting("robux_group_rate_rub", str(rate))
        await update.message.reply_text(
            f"✅ <b>Курс группы обновлён: 1 R$ = {rate}₽</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите положительное числовое значение (например: 0.60).", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_robux_group_rate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    current = await db.get_setting("robux_group_rate_stars", "0.45")
    await query.edit_message_text(
        f"⭐️ <b>Курс группы — Stars</b>\n\n"
        f"<i>Текущий курс: 1 R$ = {current} ⭐️</i>\n\n"
        f"Введите новый курс (например: 0.45):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]),
        parse_mode="HTML"
    )
    return states.ADMIN_ROBUX_GROUP_RATE_STARS


async def handle_admin_robux_group_rate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        rate = float(update.message.text.strip())
        if rate <= 0:
            raise ValueError
        await db.set_setting("robux_group_rate_stars", str(rate))
        await update.message.reply_text(
            f"✅ <b>Курс группы обновлён: 1 R$ = {rate} ⭐️</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите положительное числовое значение (например: 0.45).", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_robux_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    current = await db.get_setting("robux_group_link", "не задана")
    await query.edit_message_text(
        f"🔗 <b>Ссылка на группу Roblox</b>\n\n"
        f"<i>Текущая: {current}</i>\n\n"
        f"Введите ссылку на вашу группу Roblox\n"
        f"(например: https://www.roblox.com/groups/12345):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]]),
        parse_mode="HTML"
    )
    return states.ADMIN_ROBUX_GROUP_LINK


async def handle_admin_robux_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    link = update.message.text.strip()
    await db.set_setting("robux_group_link", link)
    await update.message.reply_text(
        f"✅ <b>Ссылка на группу сохранена:</b>\n{link}",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cb_admin_robux_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    enabled = await db.get_setting("robux_auto_enabled", "0")
    status = "✅ Включена" if enabled == "1" else "❌ Выключена"
    await query.edit_message_text(
        f"💎 <b>Настройки Robux</b>\n\n"
        f"⚡️ <i>Автовыдача Robux:</i> <b>{status}</b>\n\n"
        f"<i>При включённой автовыдаче заказы обрабатываются автоматически.</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔄 Переключить автовыдачу",
                callback_data="admin_robux_toggle_auto"
            )],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")],
        ]),
        parse_mode="HTML"
    )


async def cb_admin_robux_toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    current = await db.get_setting("robux_auto_enabled", "0")
    new_val = "1" if current == "0" else "0"
    await db.set_setting("robux_auto_enabled", new_val)
    status = "✅ Включена" if new_val == "1" else "❌ Выключена"
    await query.answer(f"Автовыдача Robux: {status}", show_alert=True)
    await cb_admin_robux_settings(update, context)


# ─── Admin: Banners ───────────────────────────────────────────────────────────

async def cb_admin_banners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    all_banners = await db.get_all_section_banners()
    existing = {b['section_key'] for b in all_banners}
    await query.edit_message_text(
        "🖼 <b>Баннеры разделов</b>\n\n"
        "<i>Нажмите на раздел, чтобы добавить или изменить баннер.</i>\n"
        "🖼 — баннер установлен | ➕ — баннер не установлен",
        reply_markup=kb.admin_banners_keyboard(existing),
        parse_mode="HTML"
    )


async def cb_admin_banner_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    section_key = query.data.split("_", 3)[3]
    context.user_data['banner_section'] = section_key
    section_name = kb.SECTION_NAMES.get(section_key, section_key)
    current = await db.get_section_banner(section_key)

    buttons = []
    if current:
        buttons.append([InlineKeyboardButton("🗑 Удалить баннер", callback_data=f"admin_banner_del_{section_key}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_banners")])

    await query.edit_message_text(
        f"🖼 <b>Баннер для раздела: {section_name}</b>\n\n"
        f"{'✅ <i>Баннер установлен. Отправьте новое фото, чтобы заменить.</i>' if current else '❌ <i>Баннер не установлен.</i>'}\n\n"
        f"Отправьте фото для установки баннера:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return states.ADMIN_BANNER_UPLOAD


async def handle_admin_banner_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото.", parse_mode="HTML")
        return states.ADMIN_BANNER_UPLOAD
    section_key = context.user_data.get('banner_section')
    if not section_key:
        return ConversationHandler.END
    file_id = update.message.photo[-1].file_id
    await db.set_section_banner(section_key, file_id)
    section_name = kb.SECTION_NAMES.get(section_key, section_key)
    await update.message.reply_text(
        f"✅ <b>Баннер для раздела «{section_name}» установлен!</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    context.user_data.pop('banner_section', None)
    return ConversationHandler.END


async def cb_admin_banner_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    section_key = query.data.split("_", 3)[3]
    await db.delete_section_banner(section_key)
    section_name = kb.SECTION_NAMES.get(section_key, section_key)
    await query.answer(f"✅ Баннер раздела «{section_name}» удалён", show_alert=True)
    await cb_admin_banners(update, context)


# ─── Admin: Contests ──────────────────────────────────────────────────────────

async def cb_admin_contests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    contests = await db.get_all_contests()
    await query.edit_message_text(
        "✨ <b>Управление конкурсами</b>\n\n"
        f"<i>Всего конкурсов: {len(contests)}</i>",
        reply_markup=kb.admin_contests_keyboard(contests),
        parse_mode="HTML"
    )


async def cb_admin_contest_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    context.user_data['contest_draft'] = {}
    await query.edit_message_text(
        "✨ <b>Создание нового конкурса</b>\n\nШаг 1/5\n\n✏️ Введите <b>название</b> конкурса:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_contests")]]),
        parse_mode="HTML"
    )
    return states.ADMIN_CONTEST_TITLE


async def handle_admin_contest_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data['contest_draft']['title'] = update.message.text.strip()
    await update.message.reply_text(
        "✨ Шаг 2/5\n\n📝 Введите <b>описание</b> конкурса:",
        parse_mode="HTML"
    )
    return states.ADMIN_CONTEST_DESC


async def handle_admin_contest_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data['contest_draft']['description'] = update.message.text.strip()
    await update.message.reply_text(
        "✨ Шаг 3/5\n\n📋 Введите <b>условия участия</b>:",
        parse_mode="HTML"
    )
    return states.ADMIN_CONTEST_CONDITIONS


async def handle_admin_contest_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data['contest_draft']['conditions'] = update.message.text.strip()
    await update.message.reply_text(
        "✨ Шаг 4/5\n\n🏆 Введите <b>приз</b> конкурса:",
        parse_mode="HTML"
    )
    return states.ADMIN_CONTEST_PRIZE


async def handle_admin_contest_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data['contest_draft']['prize'] = update.message.text.strip()
    await update.message.reply_text(
        "✨ Шаг 5/5\n\n⏰ Введите <b>дату окончания</b> (например: 30.06.2026) или отправьте <b>«нет»</b> для бессрочного конкурса:",
        parse_mode="HTML"
    )
    return states.ADMIN_CONTEST_ENDS


async def handle_admin_contest_ends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    ends_at = None if text.lower() in ['нет', 'no', '-'] else text
    draft = context.user_data.get('contest_draft', {})
    contest_id = await db.create_contest(
        title=draft.get('title', 'Конкурс'),
        description=draft.get('description', ''),
        conditions=draft.get('conditions', ''),
        prize=draft.get('prize', ''),
        ends_at=ends_at
    )
    await update.message.reply_text(
        f"✅ <b>Конкурс создан!</b>\n\n"
        f"✨ <b>{draft.get('title')}</b>\n"
        f"🆔 ID: {contest_id}",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    context.user_data.pop('contest_draft', None)
    return ConversationHandler.END


async def cb_admin_contest_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    contest_id = int(query.data.split("_")[-1])
    contest = await db.get_contest(contest_id)
    if not contest:
        await query.answer("❌ Не найдено", show_alert=True)
        return
    count = await db.get_contest_participants_count(contest_id)
    text = (
        f"✨ <b>{contest['title']}</b>\n\n"
        f"👥 <i>Участников:</i> <b>{count}</b>\n"
        f"📅 <i>Создан:</i> {contest['created_at'][:10]}\n\n"
        f"📝 {contest['description']}\n\n"
        f"📋 <b>Условия:</b> {contest['conditions']}\n\n"
        f"🏆 <b>Приз:</b> {contest['prize']}"
    )
    await query.edit_message_text(
        text,
        reply_markup=kb.admin_contest_detail_keyboard(contest_id, bool(contest['is_active'])),
        parse_mode="HTML"
    )


async def cb_admin_contest_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    contest_id = int(query.data.split("_")[-1])
    await db.toggle_contest(contest_id)
    await cb_admin_contest_view(update, context)


async def cb_admin_contest_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    contest_id = int(query.data.split("_")[-1])
    await db.delete_contest(contest_id)
    await query.answer("✅ Конкурс удалён", show_alert=True)
    await cb_admin_contests(update, context)


# ─── Admin: other handlers ────────────────────────────────────────────────────

async def cb_admin_add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ <b>Добавление промокода</b>\n\n"
        "Введите в формате:\n"
        "<code>КОД СКИДКА% МИН.СУММА ОПИСАНИЕ</code>\n\n"
        "Пример: <code>PROMO20 20 300 Скидка 20% от 300₽</code>",
        parse_mode="HTML"
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
        await update.message.reply_text(
            f"✅ <b>Промокод «{code}» добавлен!</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text("❌ Неверный формат. Попробуйте снова.", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ <b>Добавление администратора</b>\n\nВведите Telegram ID пользователя:",
        parse_mode="HTML"
    )
    return states.ADMIN_ADD_ADMIN


async def handle_admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        await db.add_admin(target_id)
        await update.message.reply_text(
            f"✅ <b>Пользователь {target_id} назначен администратором.</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "🧨 <b>Снятие администратора</b>\n\nВведите Telegram ID администратора:",
        parse_mode="HTML"
    )
    return states.ADMIN_REMOVE_ADMIN


async def handle_admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        await db.remove_admin(target_id)
        await update.message.reply_text(
            f"✅ <b>Пользователь {target_id} снят с должности.</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text("📤 <b>Рассылка</b>\n\nВведите текст рассылки:", parse_mode="HTML")
    return states.ADMIN_BROADCAST


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    user_ids = await db.get_all_user_ids()
    success = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>Объявление GubaShop</b>\n\n{text}", parse_mode="HTML")
            success += 1
        except Exception:
            pass
    await update.message.reply_text(
        f"✅ <b>Рассылка завершена.</b>\n\n📤 Отправлено: <b>{success}/{len(user_ids)}</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cb_admin_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "💰 <b>Пополнение баланса</b>\n\nВведите Telegram ID пользователя:",
        parse_mode="HTML"
    )
    return states.ADMIN_TOPUP_USER


async def handle_admin_topup_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        target_id = int(update.message.text.strip())
        context.user_data["topup_target"] = target_id
        await update.message.reply_text(
            f"💰 Введите сумму для пользователя <code>{target_id}</code>:",
            parse_mode="HTML"
        )
        return states.ADMIN_TOPUP_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введите числовой ID.", parse_mode="HTML")
        return ConversationHandler.END


async def handle_admin_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        amount = float(update.message.text.strip())
        target_id = context.user_data.get("topup_target")
        await db.update_balance(target_id, amount)
        await update.message.reply_text(
            f"✅ <b>Баланс пополнен: {amount:.2f}₽ → {target_id}</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ <b>Ваш баланс пополнен на {amount:.2f}₽!</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Введите числовое значение.", parse_mode="HTML")
    return ConversationHandler.END


async def cb_admin_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    stock = await db.get_all_stock()
    lines = []
    for key, qty in sorted(stock.items()):
        icon = "✅" if qty > 0 else "❌"
        lines.append(f"{icon} <code>{key}</code>: <b>{qty} шт.</b>")
    text = (
        "📦 <b>Склад товаров</b>\n\n" +
        "\n".join(lines) +
        "\n\n<i>Введите ключ и количество: <code>ключ количество</code></i>"
    )
    await query.edit_message_text(text, parse_mode="HTML")
    return states.ADMIN_SET_STOCK


async def handle_admin_set_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split()
    if len(parts) != 2:
        await update.message.reply_text("❌ Формат: <code>ключ_товара количество</code>", parse_mode="HTML", reply_markup=kb.admin_keyboard())
        return ConversationHandler.END
    key, qty_str = parts
    try:
        qty = int(qty_str)
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом.", parse_mode="HTML", reply_markup=kb.admin_keyboard())
        return ConversationHandler.END
    await db.set_stock(key, qty)
    await update.message.reply_text(
        f"✅ <b>Склад обновлён: <code>{key}</code> = {qty} шт.</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cb_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "➕ <b>Добавление товара</b>\n\nВыберите тип:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Юзернейм", callback_data="admin_add_product_type_username")],
            [InlineKeyboardButton("🎁 Подарок", callback_data="admin_add_product_type_gift")],
        ]),
        parse_mode="HTML"
    )


async def cb_admin_add_product_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    product_type = query.data.split("_")[-1]
    context.user_data['add_product_type'] = product_type
    await query.edit_message_text(
        f"✏️ Введите название товара:",
        parse_mode="HTML"
    )
    return states.ADMIN_ADD_PRODUCT_LABEL


async def handle_admin_add_product_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data['add_product_label'] = update.message.text.strip()
    await update.message.reply_text("💳 Введите цену товара в рублях:", parse_mode="HTML")
    return states.ADMIN_ADD_PRODUCT_PRICE


async def handle_admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите числовую цену:", parse_mode="HTML")
        return states.ADMIN_ADD_PRODUCT_PRICE
    context.user_data['add_product_price'] = price
    await update.message.reply_text("🏷 Введите количество в наличии:", parse_mode="HTML")
    return states.ADMIN_ADD_PRODUCT_STOCK


async def handle_admin_add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        stock = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите целое число:", parse_mode="HTML")
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
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 <b>{label}</b>\n"
        f"💳 {price:.0f}₽ | {stock} шт.",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
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
            "😴 <b>Нет товаров для удаления.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]),
            parse_mode="HTML"
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
        "🗑 <b>Выберите товар для удаления:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
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
        f"✅ <b>Товар удалён: {product_type}_{key}</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="admin_back")]]),
        parse_mode="HTML"
    )


async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "🛡 <b>Панель администратора GubaShop</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )


async def cb_admin_order_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await db.is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    parts = query.data.split("_")
    order_id = int(parts[3])
    user_id = int(parts[4])
    await db.update_order_status(order_id, "done")
    await query.answer("✅ Заказ выполнен", show_alert=True)
    await query.edit_message_text(
        query.message.text + "\n\n✅ <b>Заказ выполнен администратором</b>",
        reply_markup=None,
        parse_mode="HTML"
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ <b>Ваш заказ #{order_id} выполнен!</b>\n\nСпасибо за покупку в GubaShop! 🎉",
            parse_mode="HTML"
        )
    except Exception:
        pass


async def cb_admin_order_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.answer(f"⚠️ Заказ уже обработан", show_alert=True)
        return

    await db.update_order_status(order_id, "rejected")
    refund_note = ""
    if order['payment_method'] == "balance":
        await db.update_balance(user_id, order['amount'])
        refund_note = f"\n💰 Возвращено: <b>{order['amount']:.2f}₽</b>"

    await query.answer("❌ Заказ отклонён", show_alert=True)
    await query.edit_message_text(
        query.message.text + f"\n\n❌ <b>Заказ отклонён администратором</b>{refund_note}",
        reply_markup=None,
        parse_mode="HTML"
    )
    try:
        msg = (
            f"❌ <b>Ваш заказ #{order_id} был отклонён.</b>\n\n"
            f"📦 <i>Товар:</i> <b>{order['product']}</b>"
        )
        if order['payment_method'] == "balance":
            msg += f"\n\n💰 <b>{order['amount']:.2f}₽ возвращены на ваш баланс.</b>"
        else:
            msg += "\n\n<i>Если вы уже оплатили — свяжитесь с поддержкой.</i>"
        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
    except Exception:
        pass


# ─── Admin: Subscriptions ──────────────────────────────────────────────────────

async def cb_admin_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    channels = await db.get_required_channels()
    await query.edit_message_text(
        "🔑 <b>Обязательные подписки</b>\n\n"
        "🟢 — активно  🔴 — выключено\n"
        "Нажмите на название для вкл/выкл, 🗑 — удалить.",
        reply_markup=kb.subscriptions_keyboard(channels),
        parse_mode="HTML"
    )


async def cb_adminsub_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    ch_id = int(query.data.split("_")[-1])
    await db.toggle_required_channel(ch_id)
    channels = await db.get_required_channels()
    await query.edit_message_text(
        "🔑 <b>Обязательные подписки</b>\n\n🟢 — активно  🔴 — выключено",
        reply_markup=kb.subscriptions_keyboard(channels),
        parse_mode="HTML"
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
        "✅ <b>Канал удалён.</b>\n\n🔑 <b>Обязательные подписки:</b>",
        reply_markup=kb.subscriptions_keyboard(channels),
        parse_mode="HTML"
    )


async def cb_adminsub_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "➕ <b>Добавление канала</b>\n\n"
        "Введите в формате:\n"
        "<code>@channel_id Название канала</code>",
        parse_mode="HTML"
    )
    return states.ADMIN_ADD_CHANNEL


async def handle_admin_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = update.message.text.strip().split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Формат: <code>@channel_id Название</code>", parse_mode="HTML")
        return states.ADMIN_ADD_CHANNEL
    channel_id, title = parts[0], parts[1]
    await db.add_required_channel(channel_id, title)
    await update.message.reply_text(
        f"✅ <b>Канал добавлен!</b>\n\n📢 {title}\n🔑 {channel_id}",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ─── Admin: Category management ────────────────────────────────────────────────

async def cb_admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "🧩 <b>Добавление категории</b>\n\nВведите название:",
        parse_mode="HTML"
    )
    return states.ADMIN_ADD_CATEGORY


async def handle_admin_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    name = update.message.text.strip()
    cat_id = await db.add_category(name)
    await update.message.reply_text(
        f"✅ <b>Категория добавлена!</b>\n\n🧩 {name} (ID: {cat_id})",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
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
            "❌ <b>Сначала добавьте категорию.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]),
            parse_mode="HTML"
        )
        return
    buttons = [[InlineKeyboardButton(c['name'], callback_data=f"adminsubcat_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️ <b>Выберите категорию:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )


async def cb_adminsubcat_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return ConversationHandler.END
    cat_id = int(query.data.split("_")[-1])
    context.user_data['new_subcat_cat_id'] = cat_id
    await query.edit_message_text("✏️ <b>Введите название подкатегории:</b>", parse_mode="HTML")
    return states.ADMIN_ADD_SUBCATEGORY


async def handle_admin_add_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    name = update.message.text.strip()
    cat_id = context.user_data.get('new_subcat_cat_id')
    if not cat_id:
        await update.message.reply_text("❌ Ошибка: категория не выбрана.", parse_mode="HTML")
        return ConversationHandler.END
    subcat_id = await db.add_subcategory(cat_id, name)
    await update.message.reply_text(
        f"✅ <b>Подкатегория добавлена!</b>\n\n🧩 {name} (ID: {subcat_id})",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ─── Admin: Management panel ────────────────────────────────────────────────────

async def cb_admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "✏️ <b>Управление магазином:</b>",
        reply_markup=kb.management_keyboard(),
        parse_mode="HTML"
    )


async def cb_manage_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cats = await db.get_categories()
    await query.edit_message_text(
        "🗂 <b>Категории:</b>",
        reply_markup=kb.manage_categories_keyboard(cats),
        parse_mode="HTML"
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
            f"🧩 <b>Подкатегории {cat_name}:</b>\n\nПодкатегорий нет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="manage_categories")]]),
            parse_mode="HTML"
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
        f"🧩 <b>Подкатегории {cat_name}:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )


async def cb_manage_cat_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[-1])
    if cat_id in (1, 2):
        await query.answer("❌ Нельзя удалить встроенные категории.", show_alert=True)
        return
    await db.remove_category(cat_id)
    cats = await db.get_categories()
    await query.edit_message_text(
        "✅ <b>Категория удалена.</b>\n\n🗂 <b>Категории:</b>",
        reply_markup=kb.manage_categories_keyboard(cats),
        parse_mode="HTML"
    )


async def cb_manage_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    subcats = await db.get_all_subcategories()
    await query.edit_message_text(
        "🗂 <b>Все подкатегории:</b>",
        reply_markup=kb.manage_subcats_keyboard(subcats),
        parse_mode="HTML"
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
    lines = [f"🧩 <b>{subcat['name']}</b> (тип: {subcat['sub_type']})\n"]
    if products:
        for p in products:
            lines.append(f"• {p['label']} — {p['price_rub']:.0f}₽")
    else:
        lines.append("<i>Товаров нет.</i>")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="manage_subcategories")]]),
        parse_mode="HTML"
    )


async def cb_manage_subcat_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    subcat_id = int(query.data.split("_")[-1])
    if subcat_id <= 6:
        await query.answer("❌ Нельзя удалить встроенные подкатегории.", show_alert=True)
        return
    await db.remove_subcategory(subcat_id)
    subcats = await db.get_all_subcategories()
    await query.edit_message_text(
        "✅ <b>Подкатегория удалена.</b>\n\n🗂 <b>Все подкатегории:</b>",
        reply_markup=kb.manage_subcats_keyboard(subcats),
        parse_mode="HTML"
    )


async def cb_manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    products = await db.get_all_products()
    await query.edit_message_text(
        "🗂 <b>Все товары:</b>",
        reply_markup=kb.manage_products_keyboard(products),
        parse_mode="HTML"
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
    has_banner = bool(p.get('banner_file_id'))
    has_auto_data = bool(p.get('auto_data'))

    text = (
        f"📦 <b>{p['label']}</b>\n\n"
        f"<i>Тип:</i> {p['product_type']}\n"
        f"<i>Ключ:</i> <code>{p['key']}</code>\n"
        f"<i>Цена:</i> <b>{p['price_rub']:.0f}₽</b>\n"
        f"<i>Описание:</i> {p.get('description') or 'нет'}\n"
        f"<i>Выдача:</i> {delivery_label}\n"
        f"<i>Баннер:</i> {'✅' if has_banner else '❌'}\n"
        f"<i>Авто-данные:</i> {'✅' if has_auto_data else '❌'}\n"
        f"<i>Остаток:</i> <b>{qty} шт.</b>"
    )
    if is_auto:
        text += f"\n<i>Ключей:</i> <b>{avail_keys} / {total_keys}</b>"

    buttons = []
    if is_auto:
        buttons.append([InlineKeyboardButton("➕ Добавить ключи", callback_data=f"manage_add_delivery_{prod_id}")])
        if total_keys > 0:
            buttons.append([InlineKeyboardButton("🗑 Очистить ключи", callback_data=f"manage_clear_delivery_{prod_id}")])
    buttons.append([InlineKeyboardButton("🗑 Удалить товар", callback_data=f"manage_prod_del_{prod_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="manage_products")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


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
        f"➕ <b>Добавление ключей для: {label}</b>\n\n"
        f"<i>Доступно: {avail} ключей</i>\n\n"
        f"Отправьте ключи — по одному на строке:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"manage_prod_view_{prod_id}")]]),
        parse_mode="HTML"
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
        await update.message.reply_text("❌ Пустое сообщение.", parse_mode="HTML")
        return states.ADMIN_ADD_DELIVERY_ITEM
    for line in lines:
        await db.add_delivery_item(prod_id, line)
    _, avail = await db.count_delivery_items(prod_id)
    p = await db.get_product_by_id(prod_id)
    await update.message.reply_text(
        f"✅ <b>Добавлено {len(lines)} ключей для {p['label'] if p else ''}</b>\n"
        f"<i>Итого доступно: {avail}</i>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML"
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
        "✅ <b>Товар удалён.</b>\n\n🗂 <b>Все товары:</b>",
        reply_markup=kb.manage_products_keyboard(products),
        parse_mode="HTML"
    )


# ─── Admin: Product wizard ─────────────────────────────────────────────────────

def _wizard_text(draft: dict) -> str:
    name = draft.get('name') or '<i>не задано</i>'
    desc = draft.get('description') or '<i>не задано</i>'
    price = f"<b>{draft.get('price_rub', 0):.0f}₽</b>" if draft.get('price_rub') else '<i>не задано</i>'
    stock = draft.get('stock', 0)
    delivery = '⚡️ Автовыдача' if draft.get('delivery_type') == 'auto' else '👤 Ручная выдача'
    methods_map = {'crypto': 'Crypto Bot', 'yoo': 'YooMoney', 'balance': 'Баланс', 'stars': '⭐️Stars'}
    selected = draft.get('payment_methods', ['crypto', 'yoo', 'balance'])
    methods = ', '.join(methods_map[m] for m in selected if m in methods_map) or 'не выбраны'
    stars_line = ''
    if 'stars' in selected and draft.get('stars_price'):
        stars_line = f"\n⭐️ <i>Цена в звёздах:</i> <b>{draft['stars_price']} ⭐️</b>"
    auto_data_line = f"\n🔑 <i>Авто-данные:</i> ✅" if draft.get('auto_data') else ''
    banner_line = f"\n🖼 <i>Баннер:</i> ✅" if draft.get('banner_file_id') else ''
    return (
        "✏️ <b>Добавление товара</b>\n\n"
        f"✏️ <i>Название:</i> <b>{name}</b>\n"
        f"📌 <i>Описание:</i> <b>{desc}</b>\n"
        f"📦 <i>Выдача:</i> <b>{delivery}</b>\n"
        f"🏷 <i>Количество:</i> <b>{stock} шт.</b>\n"
        f"💳 <i>Способы оплаты:</i> <b>{methods}</b>\n"
        f"💳 <i>Стоимость:</i> {price}"
        f"{stars_line}{auto_data_line}{banner_line}"
    )


async def cb_admin_product_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await db.is_admin(query.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await query.edit_message_text(
            "❌ <b>Сначала добавьте категорию.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]),
            parse_mode="HTML"
        )
        return
    buttons = [[InlineKeyboardButton(c['name'], callback_data=f"adminwiz_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️ <b>Выберите категорию:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
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
            "❌ <b>Нет подкатегорий в этой категории.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]),
            parse_mode="HTML"
        )
        return
    buttons = [[InlineKeyboardButton(sc['name'], callback_data=f"adminwiz_subcat_{sc['id']}")] for sc in subcats]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_back")])
    await query.edit_message_text(
        "✏️ <b>Выберите подкатегорию:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
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
        'banner_file_id': None, 'auto_data': None,
    }
    context.user_data['wizard_chat_id'] = query.message.chat_id
    context.user_data['wizard_msg_id'] = query.message.message_id
    await query.edit_message_text(
        _wizard_text(context.user_data['wizard_draft']),
        reply_markup=kb.wizard_main_keyboard(),
        parse_mode="HTML"
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    await query.edit_message_text(
        _wizard_text(draft),
        reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
        parse_mode="HTML"
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    await query.edit_message_text(
        "✏️ <b>Тип выдачи товара:</b>\n\n"
        "<i>При автовыдаче можно добавить ключи или задать фиксированные данные.</i>",
        reply_markup=kb.wizard_delivery_keyboard(draft.get('delivery_type', 'manual')),
        parse_mode="HTML"
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_set_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delivery_type = query.data.split("_")[-1]
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['delivery_type'] = delivery_type
    if delivery_type == 'auto':
        # Ask if they want to set auto_data
        await query.edit_message_text(
            "⚡️ <b>Автовыдача выбрана!</b>\n\n"
            "Хотите задать фиксированные данные для автовыдачи?\n"
            "<i>(Это заменит систему ключей — данные будут одинаковы для всех)</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Задать данные", callback_data="adminwiz_set_auto_data")],
                [InlineKeyboardButton("⏭ Пропустить", callback_data="adminwiz_back_main")],
            ]),
            parse_mode="HTML"
        )
    else:
        draft['auto_data'] = None
        await query.edit_message_text(
            _wizard_text(draft),
            reply_markup=kb.wizard_main_keyboard(),
            parse_mode="HTML"
        )
    return states.WIZARD_MAIN


async def cb_adminwiz_set_auto_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 <b>Введите данные для автовыдачи</b>\n\n"
        "<i>Это сообщение будет отправлено покупателю после подтверждения заказа.</i>\n"
        "Например: логин и пароль, код активации, ссылка и т.д.",
        reply_markup=kb.wizard_text_back_keyboard(),
        parse_mode="HTML"
    )
    return states.WIZARD_DESC  # reuse desc state for auto_data input


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
        f"✏️ <b>Количество товара:</b> <b>{draft.get('stock', 0)} шт.</b>",
        reply_markup=kb.wizard_qty_keyboard(draft.get('stock', 0)),
        parse_mode="HTML"
    )
    return states.WIZARD_MAIN


async def cb_adminwiz_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.setdefault('wizard_draft', {})
    selected = draft.get('payment_methods', ['crypto', 'yoo', 'balance'])
    await query.edit_message_text(
        "✏️ <b>Способы оплаты:</b>",
        reply_markup=kb.wizard_payment_keyboard(selected),
        parse_mode="HTML"
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
        if method == 'stars':
            draft.pop('stars_price', None)
        draft['payment_methods'] = selected
        await query.edit_message_text(
            "✏️ <b>Способы оплаты:</b>",
            reply_markup=kb.wizard_payment_keyboard(selected),
            parse_mode="HTML"
        )
        return states.WIZARD_MAIN
    else:
        selected.append(method)
        draft['payment_methods'] = selected
        if method == 'stars':
            await query.edit_message_text(
                "⭐️ <b>Введите цену в звёздах:</b>",
                reply_markup=kb.wizard_text_back_keyboard(),
                parse_mode="HTML"
            )
            return states.WIZARD_STARS
        await query.edit_message_text(
            "✏️ <b>Способы оплаты:</b>",
            reply_markup=kb.wizard_payment_keyboard(selected),
            parse_mode="HTML"
        )
        return states.WIZARD_MAIN


async def cb_adminwiz_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🖼 <b>Баннер товара</b>\n\nОтправьте фото для баннера товара:",
        reply_markup=kb.wizard_text_back_keyboard(),
        parse_mode="HTML"
    )
    return states.WIZARD_BANNER


async def handle_wizard_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото.", parse_mode="HTML")
        return states.WIZARD_BANNER
    file_id = update.message.photo[-1].file_id
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['banner_file_id'] = file_id
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft),
            reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(
            "✅ <b>Баннер добавлен!</b>",
            reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
            parse_mode="HTML"
        )
    return states.WIZARD_MAIN


async def handle_wizard_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    draft = context.user_data.setdefault('wizard_draft', {})
    try:
        stars = int(text)
        if stars <= 0:
            await update.message.reply_text("❌ Введите положительное число:", reply_markup=kb.wizard_text_back_keyboard(), parse_mode="HTML")
            return states.WIZARD_STARS
        draft['stars_price'] = stars
        selected = draft.get('payment_methods', [])
        await update.message.reply_text(
            _wizard_text(draft),
            reply_markup=kb.wizard_payment_keyboard(selected),
            parse_mode="HTML"
        )
        return states.WIZARD_MAIN
    except ValueError:
        await update.message.reply_text("❌ Введите целое число:", reply_markup=kb.wizard_text_back_keyboard(), parse_mode="HTML")
        return states.WIZARD_STARS


async def cb_adminwiz_want_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('name') or 'не задано'
    await query.edit_message_text(
        f"✏️ <b>Название товара</b>\n\n<i>Текущее: {current}</i>\n\nВведите новое название:",
        reply_markup=kb.wizard_text_back_keyboard(),
        parse_mode="HTML"
    )
    return states.WIZARD_NAME


async def cb_adminwiz_want_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('description') or 'не задано'
    if draft.get('delivery_type') == 'auto' and not draft.get('auto_data'):
        await query.edit_message_text(
            "📌 <b>Описание / Авто-данные</b>\n\n"
            "Введите описание товара (или авто-данные для выдачи):",
            reply_markup=kb.wizard_text_back_keyboard(),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"📌 <b>Описание товара</b>\n\n<i>Текущее: {current}</i>\n\nВведите описание:",
            reply_markup=kb.wizard_text_back_keyboard(),
            parse_mode="HTML"
        )
    return states.WIZARD_DESC


async def cb_adminwiz_want_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('wizard_draft', {})
    current = draft.get('price_rub', 0)
    await query.edit_message_text(
        f"💳 <b>Стоимость товара</b>\n\n<i>Текущая: {current:.0f}₽</i>\n\nВведите цену в рублях:",
        reply_markup=kb.wizard_text_back_keyboard(),
        parse_mode="HTML"
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
            text=_wizard_text(draft),
            reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard(), parse_mode="HTML")
    return states.WIZARD_MAIN


async def handle_wizard_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    draft = context.user_data.setdefault('wizard_draft', {})
    text = update.message.text.strip()
    # If in auto-delivery and no auto_data yet, set as auto_data
    if draft.get('delivery_type') == 'auto' and not draft.get('auto_data') and not draft.get('description'):
        draft['auto_data'] = text
    else:
        draft['description'] = text
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft),
            reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard(), parse_mode="HTML")
    return states.WIZARD_MAIN


async def handle_wizard_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите числовую цену.", parse_mode="HTML")
        return states.WIZARD_PRICE
    draft = context.user_data.setdefault('wizard_draft', {})
    draft['price_rub'] = price
    chat_id = context.user_data.get('wizard_chat_id')
    msg_id = context.user_data.get('wizard_msg_id')
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=_wizard_text(draft),
            reply_markup=kb.wizard_main_keyboard('stars' in draft.get('payment_methods', [])),
            parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(_wizard_text(draft), reply_markup=kb.wizard_main_keyboard(), parse_mode="HTML")
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
    stars_price = draft.get('stars_price') if 'stars' in draft.get('payment_methods', []) else None
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
        stars_price=stars_price,
        banner_file_id=draft.get('banner_file_id'),
        auto_data=draft.get('auto_data'),
    )
    await query.edit_message_text(
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 <b>{name}</b>\n"
        f"💳 <b>{draft['price_rub']:.0f}₽</b> · <b>{draft.get('stock', 0)} шт.</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="admin_back")]]),
        parse_mode="HTML"
    )
    context.user_data.pop('wizard_draft', None)
    return ConversationHandler.END


async def cb_adminwiz_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('wizard_draft', None)
    if await db.is_admin(query.from_user.id):
        await query.edit_message_text(
            "❌ <b>Добавление отменено.</b>",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML"
        )
    return ConversationHandler.END


# ─── Telegram Stars: pre-checkout & successful payment ─────────────────────────

async def handle_pre_checkout_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    stars = payment.total_amount
    user_id = update.message.from_user.id

    if payload.startswith("premium_"):
        plan = payload.split("_", 1)[1]
        p = kb.PREMIUM_PRICES.get(plan)
        if p:
            order_id = await db.add_order(user_id, f"Telegram Premium {p['label']}", p["rub"], "stars")
            await _notify_payment(context, user_id, f"Telegram Premium {p['label']}", p["rub"], f"Stars ({stars} ⭐️)", order_id)
        await update.message.reply_text(
            "✅ <b>Оплата принята! Ожидайте выполнения заказа.</b>",
            parse_mode="HTML"
        )

    elif payload.startswith("username_"):
        key = payload.split("_", 1)[1]
        u = await db.get_product('username', key)
        if u:
            if await db.get_stock(f"username_{key}") > 0:
                await db.decrement_stock(f"username_{key}")
            order_id = await db.add_order(user_id, f"Username @{key}", u["price_rub"], "stars")
            await _notify_payment(context, user_id, f"Username @{key}", u["price_rub"], f"Stars ({stars} ⭐️)", order_id)
        await update.message.reply_text(
            "✅ <b>Оплата принята! Ожидайте выполнения заказа.</b>",
            parse_mode="HTML"
        )

    elif payload.startswith("dynprod_"):
        prod_id = int(payload.split("_")[1])
        p = await db.get_product_by_id(prod_id)
        if p:
            inv_key = f"{p['product_type']}_{p['key']}"
            if await db.get_stock(inv_key) > 0:
                await db.decrement_stock(inv_key)
            order_id = await db.add_order(user_id, p['label'], p['price_rub'], "stars")
            if p.get('delivery_type') == 'auto':
                if p.get('auto_data'):
                    await _notify_auto_delivery_confirm(context, user_id, p, order_id, p['auto_data'])
                    await update.message.reply_text(
                        "✅ <b>Оплата принята! Ожидайте выдачи данных.</b>",
                        parse_mode="HTML"
                    )
                    return
                delivered = await _auto_deliver(context, user_id, p['id'], p['label'])
                if delivered:
                    await update.message.reply_text("✅ <b>Оплата принята! Ваш товар отправлен выше ⬆️</b>", parse_mode="HTML")
                    return
            await _notify_payment(context, user_id, p['label'], p['price_rub'], f"Stars ({stars} ⭐️)", order_id)
        await update.message.reply_text(
            "✅ <b>Оплата принята! Ожидайте выдачи.</b>",
            parse_mode="HTML"
        )

    elif payload.startswith("robux_"):
        order_id = await db.add_order(user_id, f"Robux ({payload})", 0, "stars")
        uname = update.message.from_user.username or str(user_id)
        await notify_all_admins(
            context,
            f"💎 <b>ОПЛАТА STARS: {payload}</b>\n\n"
            f"👤 @{uname} (ID: {user_id})\n"
            f"⭐️ <b>{stars} Stars</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_order_done_{order_id}_{user_id}")],
                [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
            ]),
            parse_mode="HTML"
        )
        await update.message.reply_text(
            "✅ <b>Оплата принята! Ожидайте выполнения заказа.</b>",
            parse_mode="HTML"
        )


# ─── Notify payment helper ────────────────────────────────────────────────────

async def _notify_payment(context, user_id: int, product: str, amount: float, method: str, order_id: int):
    try:
        user = await context.bot.get_chat(user_id)
        uname = f"@{user.username}" if user.username else user.first_name or str(user_id)
    except Exception:
        uname = str(user_id)

    await notify_all_admins(
        context,
        f"🛒 <b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n\n"
        f"👤 <i>Покупатель:</i> {uname} (ID: {user_id})\n"
        f"📦 <i>Товар:</i> <b>{product}</b>\n"
        f"💰 <i>Сумма:</i> <b>{amount:.2f}₽</b>\n"
        f"💳 <i>Способ:</i> <b>{method}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать покупателю", callback_data=f"admin_chat_reply_{order_id}_{user_id}")],
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_order_done_{order_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_order_reject_{order_id}_{user_id}")],
        ]),
        parse_mode="HTML"
    )
