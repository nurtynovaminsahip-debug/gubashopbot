import os
import logging
import asyncio
from telegram import Update
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
        entry_points=[MessageHandler(filters.Regex("^🆘Поддержка$"), h.handle_support)],
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
        entry_points=[MessageHandler(filters.Regex("^🏷Промокод$"), h.handle_promo)],
        states={
            states.PROMO_INPUT: [
                CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_promo_input)
            ]
        },
        fallbacks=[CallbackQueryHandler(h.cb_back_to_main, pattern="^back_to_main$")],
        per_chat=True, per_user=True,
    )

    # Admin conversations
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

    # Old simple product add (username/gift type)
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

    # Delivery items add conv
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

    # Required channels add conv
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

    # Add category conv
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

    # Add subcategory conv (entry = selecting a category via callback, then text)
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
                CallbackQueryHandler(h.cb_adminwiz_qty, pattern="^adminwiz_qty$"),
                CallbackQueryHandler(h.cb_adminwiz_qty, pattern="^adminwiz_qty_"),
                CallbackQueryHandler(h.cb_adminwiz_payment, pattern="^adminwiz_payment$"),
                CallbackQueryHandler(h.cb_adminwiz_togglepay, pattern="^adminwiz_togglepay_"),
                CallbackQueryHandler(h.cb_adminwiz_want_name, pattern="^adminwiz_name$"),
                CallbackQueryHandler(h.cb_adminwiz_want_desc, pattern="^adminwiz_desc$"),
                CallbackQueryHandler(h.cb_adminwiz_want_price, pattern="^adminwiz_price$"),
                CallbackQueryHandler(h.cb_adminwiz_confirm, pattern="^adminwiz_confirm$"),
                CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^adminwiz_cancel$"),
            ],
            states.WIZARD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_name),
                CallbackQueryHandler(h.cb_adminwiz_subcat, pattern="^adminwiz_subcat_"),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_desc),
                CallbackQueryHandler(h.cb_adminwiz_subcat, pattern="^adminwiz_subcat_"),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_price),
                CallbackQueryHandler(h.cb_adminwiz_subcat, pattern="^adminwiz_subcat_"),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
            states.WIZARD_STARS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_wizard_stars),
                CallbackQueryHandler(h.cb_adminwiz_back_main, pattern="^adminwiz_back_main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^adminwiz_cancel$"),
            CallbackQueryHandler(h.cb_adminwiz_cancel, pattern="^admin_back$"),
        ],
        per_chat=True, per_user=True, per_message=False,
    )

    # Add all handlers
    app.add_handler(CommandHandler("start", h.cmd_start))
    app.add_handler(CommandHandler("admin", h.cmd_admin))

    # Conversations (must be before general handlers)
    app.add_handler(stars_conv)
    app.add_handler(deposit_conv)
    app.add_handler(support_conv)
    app.add_handler(promo_conv)
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

    # Menu buttons
    app.add_handler(MessageHandler(filters.Regex("^🛒Купить$"), h.handle_buy))
    app.add_handler(MessageHandler(filters.Regex("^👤Профиль$"), h.handle_profile))
    app.add_handler(MessageHandler(filters.Regex("^💎Реферальная система$"), h.handle_referral))

    app.add_handler(MessageHandler(filters.Regex("^📕Правила$"), lambda u, c: u.message.reply_text(
        "📕 Правила GubaShop",
        reply_markup=__import__("telegram").InlineKeyboardMarkup([[
            __import__("telegram").InlineKeyboardButton("Открыть правила", url="https://telegra.ph/Politika-proekta-GubaShop-06-01")
        ]])
    )))
    app.add_handler(MessageHandler(filters.Regex("^⭐️Отзывы$"), lambda u, c: u.message.reply_text(
        "⭐️ Отзывы GubaShop",
        reply_markup=__import__("telegram").InlineKeyboardMarkup([[
            __import__("telegram").InlineKeyboardButton("Читать отзывы", url="https://t.me/lihakchm")
        ]])
    )))

    # Admin reply forwarding
    app.add_handler(MessageHandler(
        filters.REPLY & filters.User(int(os.environ.get("ADMIN_ID", "0"))),
        h.handle_admin_reply
    ))

    # Policy callback
    app.add_handler(CallbackQueryHandler(h.cb_agreed_policy, pattern="^agreed_policy$"))

    # Subscription check
    app.add_handler(CallbackQueryHandler(h.cb_check_subscriptions, pattern="^check_subscriptions$"))

    # Navigation callbacks
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

    # Dynamic generic products
    app.add_handler(CallbackQueryHandler(h.cb_dynprod, pattern=r"^dynprod_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_crypto, pattern=r"^dynpay_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_yoo, pattern=r"^dynpay_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_balance, pattern=r"^dynpay_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynconfirm_balance, pattern=r"^dynconfirm_balance_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_crypto, pattern=r"^dynpaid_crypto_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_yoo, pattern=r"^dynpaid_yoo_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpay_stars, pattern=r"^dynpay_stars_\d+$"))
    app.add_handler(CallbackQueryHandler(h.cb_dynpaid_stars, pattern=r"^dynpaid_stars_\d+$"))

    # Profile
    app.add_handler(CallbackQueryHandler(h.cb_purchase_history, pattern="^purchase_history$"))
    app.add_handler(CallbackQueryHandler(h.cb_referral_profile, pattern="^referral_profile$"))

    # Deposit
    app.add_handler(CallbackQueryHandler(h.cb_dep_crypto, pattern=r"^dep_crypto_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_yoo, pattern=r"^dep_yoo_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_paid_crypto, pattern=r"^dep_paid_crypto_"))
    app.add_handler(CallbackQueryHandler(h.cb_dep_paid_yoo, pattern=r"^dep_paid_yoo_"))

    # Admin panel
    app.add_handler(CallbackQueryHandler(h.cb_admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_credit, pattern=r"^admin_credit_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_order_done, pattern=r"^admin_order_done_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_order_reject, pattern=r"^admin_order_reject_"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_add_product, pattern="^admin_add_product$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_remove_product, pattern="^admin_remove_product$"))
    app.add_handler(CallbackQueryHandler(h.cb_admin_delete_product, pattern=r"^admin_delete_product_"))

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
