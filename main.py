import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, PreCheckoutQueryHandler, filters
)
import database as db
import handlers as h
import states

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Stars custom input conv
    stars_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_stars_custom, pattern="^stars_custom$")],
        states={
            states.STARS_CUSTOM_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_stars_custom_input)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    # Deposit conv
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_deposit, pattern="^deposit$")],
        states={
            states.DEPOSIT_AMOUNT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_deposit_amount)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    # Support conv
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆘 Поддержка$"), h.handle_support)],
        states={
            states.SUPPORT_MESSAGE: [
                CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_support_message)
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$")],
        per_chat=True, per_user=True,
    )

    # Promo conv
    promo_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏷 Промокод$"), h.handle_promo)],
        states={
            states.PROMO_INPUT: [
                CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_promo_input)
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$")],
        per_chat=True, per_user=True,
    )

    # Order chat conv (user side)
    order_chat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_chat_open, pattern=r"^chat_open_\d+$")],
        states={
            states.ORDER_CHAT_MESSAGE: [
                CallbackQueryHandler(h.cb_chat_close, pattern=r"^chat_close_\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_user_chat_message),
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_chat_close, pattern=r"^chat_close_\d+$")],
        per_chat=True, per_user=True,
    )

    # Admin order chat conv
    admin_chat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_chat_reply, pattern=r"^admin_chat_reply_\d+_\d+$")],
        states={
            states.ADMIN_ORDER_CHAT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_chat_message),
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_admin_back, pattern="^admin_back$")],
        per_chat=True, per_user=True,
    )

    # Admin settings conv
    admin_settings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(h.cb_admin_settings_stars_rate, pattern="^admin_settings_stars_rate$"),
            CallbackQueryHandler(h.cb_admin_settings_stars_recipient, pattern="^admin_settings_stars_recipient$"),
        ],
        states={
            states.ADMIN_SETTINGS_STARS_RECIPIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_settings_recipient),
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_admin_back, pattern="^admin_back$")],
        per_chat=True, per_user=True,
    )

    # Admin contests conv
    admin_contest_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_contest_create, pattern="^admin_contest_create$")],
        states={
            states.ADMIN_CONTEST_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_contest_title)],
            states.ADMIN_CONTEST_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_contest_desc)],
            states.ADMIN_CONTEST_CONDITIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_contest_conditions)],
            states.ADMIN_CONTEST_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_contest_prize)],
            states.ADMIN_CONTEST_ENDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_contest_ends)],
        },
        fallbacks=[CallbackQueryHandler(h.cb_admin_contests, pattern="^admin_contests$")],
        per_chat=True, per_user=True,
    )

    # Admin banners conv
    admin_banners_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_banner_set, pattern=r"^admin_banner_set_\w+$")],
        states={
            states.ADMIN_BANNER_UPLOAD: [
                MessageHandler(filters.PHOTO, h.handle_admin_banner_upload),
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_admin_banners, pattern="^admin_banners$")],
        per_chat=True, per_user=True,
    )

    # Admin add promo conv
    admin_add_promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_add_promo, pattern="^admin_add_promo$")],
        states={
            states.ADMIN_ADD_PROMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_promo)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_add_admin, pattern="^admin_add_admin$")],
        states={
            states.ADMIN_ADD_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_admin)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_remove_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_remove_admin, pattern="^admin_remove_admin$")],
        states={
            states.ADMIN_REMOVE_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_remove_admin)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_broadcast, pattern="^admin_broadcast$")],
        states={
            states.ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_broadcast)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_topup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_topup, pattern="^admin_topup$")],
        states={
            states.ADMIN_TOPUP_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_topup_user)
            ],
            states.ADMIN_TOPUP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_topup_amount)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_stock_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_stock, pattern="^admin_stock$")],
        states={
            states.ADMIN_SET_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_set_stock)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_product_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(h.cb_admin_add_product_type, pattern="^admin_add_product_type_")
        ],
        states={
            states.ADMIN_ADD_PRODUCT_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_product_label)
            ],
            states.ADMIN_ADD_PRODUCT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_product_price)
            ],
            states.ADMIN_ADD_PRODUCT_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_product_stock)
            ],
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_delivery_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_manage_add_delivery, pattern=r"^manage_add_delivery_\d+$")],
        states={
            states.ADMIN_ADD_DELIVERY_ITEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_delivery_item)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_adminsub_add, pattern="^adminsub_add$")],
        states={
            states.ADMIN_ADD_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_channel)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_category_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_admin_add_category, pattern="^admin_add_category$")],
        states={
            states.ADMIN_ADD_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_category)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    admin_add_subcategory_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_adminsubcat_cat, pattern="^adminsubcat_cat_")],
        states={
            states.ADMIN_ADD_SUBCATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_admin_add_subcategory)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True, per_message=False,
    )

    # Product wizard conv
    wizard_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_adminwiz_subcat, pattern="^adminwiz_subcat_")],
        states={
            states.WIZARD_MAIN: [
                CallbackQueryHandler(h.cb_adminwiz_subcat, pattern="^adminwiz_subcat_"),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
                CallbackQueryHandler(h.cb_adminwiz_delivery, pattern="^adminwiz_delivery$"),
                CallbackQueryHandler(h.cb_adminwiz_set_delivery, pattern="^adminwiz_set_delivery_"),
                CallbackQueryHandler(h.cb_adminwiz_set_auto_data, pattern="^adminwiz_set_auto_data$"),
                CallbackQueryHandler(h.cb_adminwiz_qty, pattern="^adminwiz_qty$"),
                CallbackQueryHandler(h.cb_adminwiz_qty, pattern="^adminwiz_qty_"),
                CallbackQueryHandler(h.cb_adminwiz_payment, pattern="^adminwiz_payment$"),
                CallbackQueryHandler(h.cb_adminwiz_togglepay, pattern="^adminwiz_togglepay_"),
                CallbackQueryHandler(h.cb_adminwiz_want_name, pattern="^adminwiz_name$"),
                CallbackQueryHandler(h.cb_adminwiz_want_desc, pattern="^adminwiz_desc$"),
                CallbackQueryHandler(h.cb_adminwiz_want_price, pattern="^adminwiz_price$"),
                CallbackQueryHandler(h.cb_adminwiz_banner, pattern="^adminwiz_banner$"),
                CallbackQueryHandler(h.cb_adminwiz_confirm, pattern="^adminwiz_confirm$"),
                CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^adminwiz_cancel$"),
            ],
            states.WIZARD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_name),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_desc),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_price),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_STARS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_stars),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_BANNER: [
                MessageHandler(filters.PHOTO, h.handle_wizard_banner),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^adminwiz_cancel$"),
            CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^admin_back$"),
        ],
        per_chat=True, per_user=True, per_message=False,
    )

    # Robux conversations
    robux_gp_qty_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_gp_qty, pattern="^robux_gp_qty$")],
        states={
            states.ROBUX_GAMEPASS_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_gp_qty)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_gp_recipient_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_gp_recipient, pattern="^robux_gp_recipient$")],
        states={
            states.ROBUX_USERNAME_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_roblox_username_search)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_group_qty_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_group_qty, pattern="^robux_group_qty$")],
        states={
            states.ROBUX_GROUP_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_group_qty)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_group_recipient_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_group_recipient, pattern="^robux_group_recipient$")],
        states={
            states.ROBUX_GROUP_RECIPIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_group_recipient)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_packs_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_pack, pattern=r"^robux_pack_\d+$")],
        states={
            states.ROBUX_PACKS_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_packs_login)],
            states.ROBUX_PACKS_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_packs_password)],
            states.ROBUX_PACKS_EMAIL_CONFIRMED: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_packs_email)],
            states.ROBUX_PACKS_BACKUP_CODES: [MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_packs_backup)],
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_sp_qty_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_sp_qty, pattern=r"^robux_sp_qty_\d+$")],
        states={
            states.ROBUX_SUPERPASSES_GAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_robux_sp_qty)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    robux_sp_recipient_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_robux_sp_recipient, pattern=r"^robux_sp_recipient_\d+$")],
        states={
            states.ROBUX_USERNAME_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_roblox_username_search)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    roblox_search_again_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h.cb_roblox_search_again, pattern=r"^roblox_search_again_")],
        states={
            states.ROBUX_USERNAME_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_roblox_username_search)
            ]
        },
        fallbacks=[],
        per_chat=True, per_user=True,
    )

    # Register all conversation handlers first
    app.add_handler(stars_conv)
    app.add_handler(deposit_conv)
    app.add_handler(support_conv)
    app.add_handler(promo_conv)
    app.add_handler(order_chat_conv)
    app.add_handler(admin_chat_conv)
    app.add_handler(admin_settings_conv)
    app.add_handler(admin_contest_conv)
    app.add_handler(admin_banners_conv)
    app.add_handler(admin_add_promo_conv)
    app.add_handler(admin_add_admin_conv)
    app.add_handler(admin_remove_admin_conv)
    app.add_handler(admin_broadcast_conv)
    app.add_handler(admin_topup_conv)
    app.add_handler(admin_stock_conv)
    app.add_handler(admin_add_product_conv)
    app.add_handler(admin_add_delivery_conv)
    app.add_handler(admin_add_channel_conv)
    app.add_handler(admin_add_category_conv)
    app.add_handler(admin_add_subcategory_conv)
    app.add_handler(wizard_conv)
    app.add_handler(robux_gp_qty_conv)
    app.add_handler(robux_gp_recipient_conv)
    app.add_handler(robux_group_qty_conv)
    app.add_handler(robux_group_recipient_conv)
    app.add_handler(robux_packs_conv)
    app.add_handler(robux_sp_qty_conv)
    app.add_handler(robux_sp_recipient_conv)
    app.add_handler(roblox_search_again_conv)

    # Commands
    app.add_handler(CommandHandler("start", h.cmd_start))
    app.add_handler(CommandHandler("admin", h.cmd_admin))

    # Menu buttons
    app.add_handler(MessageHandler(filters.Regex("^🛒 Купить$"), h.handle_buy))
    app.add_handler(MessageHandler(filters.Regex("^👤 Профиль$"), h.handle_profile))
    app.add_handler(MessageHandler(filters.Regex("^💎 Реферальная система$"), h.handle_referral))
    app.add_handler(MessageHandler(filters.Regex("^🏆 Лидеры$"), h.handle_leaders))
    app.add_handler(MessageHandler(filters.Regex("^✨ Конкурсы$"), h.handle_contests))
    app.add_handler(MessageHandler(filters.Regex("^📕 Правила$"), h.handle_rules))
    app.add_handler(MessageHandler(filters.Regex("^⭐️ Отзывы$"), h.handle_reviews))
    app.add_handler(MessageHandler(filters.Regex("^🏷 Промокод$"), h.handle_promo))
    app.add_handler(MessageHandler(filters.Regex("^🆘 Поддержка$"), h.handle_support))

    # Admin reply forwarding
    app.add_handler(MessageHandler(
        filters.REPLY & filters.User(int(os.environ.get("ADMIN_ID", "0"))),
        h.handle_admin_reply
    ))

    # Policy callback
    app.add_handler(CallbackQueryHandler(h.cb_agreed_policy, pattern="^agreed_policy$"))

    # Noop
    app.add_handler(CallbackQueryHandler(h.cb_noop, pattern="^noop"))

    # Subscription check
    app.add_handler(CallbackQueryHandler(h.cb_check_subscriptions, pattern="^check_subscriptions$"))

    # Navigation
    app.add_handler(CallbackQueryHandler(h.cb_cat, pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_cat_telegram, pattern="^cat_telegram$"))
    app.add_handler(CallbackQueryHandler(h.cb_subcat, pattern=r"^subcat_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_back_to_categories, pattern="^back_to_categories$"))
    app.add_handler(CallbackQueryHandler(h.cb_back_to_subcategories, pattern="^back_to_subcategories$"))
    app.add_handler(CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(h.cb_back_to_profile, pattern="^back_to_profile$"))
    app.add_handler(CallbackQueryHandler(h.cb_cancel_payment, pattern="^cancel_payment$"))

    # Stars
    app.add_handler(CallbackQueryHandler(h.cb_sub_stars, pattern="^sub_stars$"))
    app.add_handler(CallbackQueryHandler(h.cb_stars_qty, pattern="^stars_(50|100|150|200)$"))
    app.add_handler(CallbackQueryHandler(h.cb_stars_continue, pattern="^stars_continue$"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_crypto_stars, pattern=r"^pay_crypto_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_yoo_stars, pattern=r"^pay_yoo_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_balance_stars, pattern=r"^pay_balance_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_confirm_balance_stars, pattern=r"^confirm_balance_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_crypto_stars, pattern=r"^paid_crypto_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_yoo_stars, pattern=r"^paid_yoo_stars_\d+$"))

    # Premium
    app.add_handler(CallbackQueryHandler(h.cb_sub_premium, pattern="^sub_premium$"))
    app.add_handler(CallbackQueryHandler(h.cb_premium_plan, pattern=r"^premium_(1m|3m|6m|12m)$"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_crypto_premium, pattern=r"^pay_crypto_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_yoo_premium, pattern=r"^pay_yoo_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_balance_premium, pattern=r"^pay_balance_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_stars_premium, pattern=r"^pay_stars_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_confirm_balance_premium, pattern=r"^confirm_balance_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_crypto_premium, pattern=r"^paid_crypto_premium_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_yoo_premium, pattern=r"^paid_yoo_premium_"))

    # Usernames
    app.add_handler(CallbackQueryHandler(h.cb_sub_usernames, pattern="^sub_usernames$"))
    app.add_handler(CallbackQueryHandler(h.cb_username_item, pattern=r"^username_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_crypto_username, pattern=r"^pay_crypto_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_yoo_username, pattern=r"^pay_yoo_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_balance_username, pattern=r"^pay_balance_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_stars_username, pattern=r"^pay_stars_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_confirm_balance_username, pattern=r"^confirm_balance_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_crypto_username, pattern=r"^paid_crypto_username_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_yoo_username, pattern=r"^paid_yoo_username_"))

    # Gifts
    app.add_handler(CallbackQueryHandler(h.cb_sub_gifts, pattern="^sub_gifts$"))
    app.add_handler(CallbackQueryHandler(h.cb_gift_item, pattern=r"^gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_crypto_gift, pattern=r"^pay_crypto_gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_yoo_gift, pattern=r"^pay_yoo_gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_pay_balance_gift, pattern=r"^pay_balance_gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_confirm_balance_gift, pattern=r"^confirm_balance_gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_crypto_gift, pattern=r"^paid_crypto_gift_"))
    app.add_handler(CallbackQueryHandler(h.cb_paid_yoo_gift, pattern=r"^paid_yoo_gift_"))

    # NFT
    app.add_handler(CallbackQueryHandler(h.cb_sub_nft, pattern="^sub_nft$"))

    # Contests
    app.add_handler(CallbackQueryHandler(h.cb_contests_list, pattern="^contests_list$"))
    app.add_handler(CallbackQueryHandler(h.cb_contest_detail, pattern=r"^contest_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_contest_join, pattern=r"^contest_join_\d+$"))

    # Profile
    app.add_handler(CallbackQueryHandler(h.cb_purchase_history, pattern="^purchase_history$"))
    app.add_handler(CallbackQueryHandler(h.cb_referral_profile, pattern="^referral_profile$"))

    # Deposit
    app.add_handler(CallbackQueryHandler(h.cb_dep_crypto, pattern=r"^dep_crypto_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_yoo, pattern=r"^dep_yoo_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_paid_crypto, pattern=r"^dep_paid_crypto_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_paid_yoo, pattern=r"^dep_paid_yoo_"))

    # Dynamic generic products
    app.add_handler(CallbackQueryHandler(h.cb_dynprod, pattern=r"^dynprod_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynbuy, pattern=r"^dynbuy_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_crypto, pattern=r"^dynpay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_yoo, pattern=r"^dynpay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_balance, pattern=r"^dynpay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynconfirm_balance, pattern=r"^dynconfirm_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_crypto, pattern=r"^dynpaid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_yoo, pattern=r"^dynpaid_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_stars, pattern=r"^dynpay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_stars, pattern=r"^dynpaid_stars_\d+$"))

    # Order chat
    app.add_handler(CallbackQueryHandler(h.cb_chat_close, pattern=r"^chat_close_\d+$"))

    # Admin panel
    app.add_handler(CallbackQueryHandler(h.cb_admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_settings, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_robux_settings, pattern="^admin_robux_settings$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_robux_toggle_auto, pattern="^admin_robux_toggle_auto$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_credit, pattern=r"^admin_credit_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_order_done, pattern=r"^admin_order_done_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_order_reject, pattern=r"^admin_order_reject_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_auto_deliver, pattern=r"^admin_auto_deliver_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_add_product, pattern="^admin_add_product$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_remove_product, pattern="^admin_remove_product$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_delete_product, pattern=r"^admin_delete_product_"))

    # Admin: banners
    app.add_handler(CallbackQueryHandler(h.cb_admin_banners, pattern="^admin_banners$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_banner_del, pattern=r"^admin_banner_del_"))

    # Admin: contests
    app.add_handler(CallbackQueryHandler(h.cb_admin_contests, pattern="^admin_contests$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_contest_view, pattern=r"^admin_contest_view_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_contest_toggle, pattern=r"^admin_contest_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_contest_del, pattern=r"^admin_contest_del_\d+$"))

    # Admin: subscriptions
    app.add_handler(CallbackQueryHandler(h.cb_admin_subscriptions, pattern="^admin_subscriptions$"))
    app.add_handler(CallbackQueryHandler(h.cb_adminsub_toggle, pattern=r"^adminsub_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_adminsub_del, pattern=r"^adminsub_del_\d+$"))

    # Admin: categories/subcategories
    app.add_handler(CallbackQueryHandler(h.cb_admin_add_subcategory, pattern="^admin_add_subcategory$"))
    app.add_handler(CallbackQueryHandler(h.cb_adminwiz_cat, pattern=r"^adminwiz_cat_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_product_wizard, pattern="^admin_product_wizard$"))

    # Admin: management panel
    app.add_handler(CallbackQueryHandler(h.cb_admin_management, pattern="^admin_management$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_categories, pattern="^manage_categories$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_cat_view, pattern=r"^manage_cat_view_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_cat_del, pattern=r"^manage_cat_del_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_subcategories, pattern="^manage_subcategories$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_subcat_view, pattern=r"^manage_subcat_view_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_subcat_del, pattern=r"^manage_subcat_del_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_products, pattern="^manage_products$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_prod_view, pattern=r"^manage_prod_view_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_prod_del, pattern=r"^manage_prod_del_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_manage_clear_delivery, pattern=r"^manage_clear_delivery_\d+$"))

    # Robux
    app.add_handler(CallbackQueryHandler(h.cb_sub_robux, pattern="^sub_robux$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_main, pattern="^robux_main$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gamepass, pattern="^robux_gamepass$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_buy, pattern="^robux_gp_buy$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_pay_crypto, pattern=r"^robux_gp_pay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_pay_yoo, pattern=r"^robux_gp_pay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_pay_balance, pattern=r"^robux_gp_pay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_pay_stars, pattern=r"^robux_gp_pay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_paid_crypto, pattern=r"^robux_gp_paid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gp_paid_yoo, pattern=r"^robux_gp_paid_yoo_\d+$"))

    app.add_handler(CallbackQueryHandler(h.cb_robux_giftcard, pattern="^robux_giftcard$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc, pattern=r"^robux_gc_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_pay_crypto, pattern=r"^robux_gc_pay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_pay_yoo, pattern=r"^robux_gc_pay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_pay_balance, pattern=r"^robux_gc_pay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_pay_stars, pattern=r"^robux_gc_pay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_paid_crypto, pattern=r"^robux_gc_paid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_gc_paid_yoo, pattern=r"^robux_gc_paid_yoo_\d+$"))

    app.add_handler(CallbackQueryHandler(h.cb_robux_packs, pattern="^robux_packs$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_pay_crypto, pattern=r"^robux_pack_pay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_pay_yoo, pattern=r"^robux_pack_pay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_pay_balance, pattern=r"^robux_pack_pay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_pay_stars, pattern=r"^robux_pack_pay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_paid_crypto, pattern=r"^robux_pack_paid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_pack_paid_yoo, pattern=r"^robux_pack_paid_yoo_\d+$"))

    app.add_handler(CallbackQueryHandler(h.cb_robux_group, pattern="^robux_group$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_buy, pattern="^robux_group_buy$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_pay_crypto, pattern=r"^robux_group_pay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_pay_yoo, pattern=r"^robux_group_pay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_pay_balance, pattern=r"^robux_group_pay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_pay_stars, pattern=r"^robux_group_pay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_paid_crypto, pattern=r"^robux_group_paid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_group_paid_yoo, pattern=r"^robux_group_paid_yoo_\d+$"))

    app.add_handler(CallbackQueryHandler(h.cb_robux_superpasses, pattern="^robux_superpasses$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_game, pattern=r"^robux_sp_game_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_buy, pattern=r"^robux_sp_buy_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_pay_crypto, pattern=r"^robux_sp_pay_crypto_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_pay_yoo, pattern=r"^robux_sp_pay_yoo_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_pay_balance, pattern=r"^robux_sp_pay_balance_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_pay_stars, pattern=r"^robux_sp_pay_stars_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_paid_crypto, pattern=r"^robux_sp_paid_crypto_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_robux_sp_paid_yoo, pattern=r"^robux_sp_paid_yoo_\d+_\d+$"))

    # Roblox user confirm
    app.add_handler(CallbackQueryHandler(h.cb_roblox_confirm, pattern=r"^roblox_confirm_"))

    # Telegram Stars payments
    app.add_handler(PreCheckoutQueryHandler(h.handle_pre_checkout_query))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, h.handle_successful_payment))

    async def post_init(application):
        await db.init_db()
        logger.info("Database initialized.")

    app.post_init = post_init

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
