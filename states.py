from telegram.ext import ConversationHandler

# Stars flow
STARS_CUSTOM_INPUT = "stars_custom_input"

# Deposit flow
DEPOSIT_AMOUNT_INPUT = "deposit_amount_input"

# Support flow
SUPPORT_MESSAGE = "support_message"

# Promo flow
PROMO_INPUT = "promo_input"

# Admin states
ADMIN_ADD_PROMO = "admin_add_promo"
ADMIN_ADD_ADMIN = "admin_add_admin"
ADMIN_REMOVE_ADMIN = "admin_remove_admin"
ADMIN_BROADCAST = "admin_broadcast"
ADMIN_TOPUP_USER = "admin_topup_user"
ADMIN_TOPUP_AMOUNT = "admin_topup_amount"
ADMIN_SET_STOCK = "admin_set_stock"
ADMIN_SET_STOCK_QTY = "admin_set_stock_qty"
ADMIN_ADD_PRODUCT_LABEL = "admin_add_product_label"
ADMIN_ADD_PRODUCT_PRICE = "admin_add_product_price"
ADMIN_ADD_PRODUCT_STOCK = "admin_add_product_stock"

# Category / subcategory management
ADMIN_ADD_CATEGORY = "admin_add_category"
ADMIN_ADD_SUBCATEGORY = "admin_add_subcategory"

# Required channels
ADMIN_ADD_CHANNEL = "admin_add_channel"

# Product wizard
WIZARD_MAIN = "wizard_main"
WIZARD_NAME = "wizard_name"
WIZARD_DESC = "wizard_desc"
WIZARD_PRICE = "wizard_price"

# Auto-delivery keys management
ADMIN_ADD_DELIVERY_ITEM = "admin_add_delivery_item"

# Wizard: stars price input
WIZARD_STARS = "wizard_stars"

# Wizard: banner upload
WIZARD_BANNER = "wizard_banner"

# Contest states
ADMIN_CONTEST_TITLE = "admin_contest_title"
ADMIN_CONTEST_DESC = "admin_contest_desc"
ADMIN_CONTEST_CONDITIONS = "admin_contest_conditions"
ADMIN_CONTEST_PRIZE = "admin_contest_prize"
ADMIN_CONTEST_ENDS = "admin_contest_ends"

# Order chat states
ORDER_CHAT_MESSAGE = "order_chat_message"
ADMIN_ORDER_CHAT_MESSAGE = "admin_order_chat_message"

# Stars purchase: recipient username
STARS_RECIPIENT_INPUT = "stars_recipient_input"
STARS_RECIPIENT_CONFIRM = "stars_recipient_confirm"

# Section banner upload
ADMIN_BANNER_UPLOAD = "admin_banner_upload"

# Settings
ADMIN_SETTINGS_STARS_RECIPIENT = "admin_settings_stars_recipient"

# Robux states
ROBUX_GAMEPASS_QTY = "robux_gamepass_qty"
ROBUX_GAMEPASS_RECIPIENT = "robux_gamepass_recipient"
ROBUX_GROUP_RECIPIENT = "robux_group_recipient"
ROBUX_GROUP_QTY = "robux_group_qty"
ROBUX_PACKS_LOGIN = "robux_packs_login"
ROBUX_PACKS_PASSWORD = "robux_packs_password"
ROBUX_PACKS_EMAIL_CONFIRMED = "robux_packs_email_confirmed"
ROBUX_PACKS_BACKUP_CODES = "robux_packs_backup_codes"
ROBUX_SUPERPASSES_GAME = "robux_superpasses_game"
ROBUX_SUPERPASSES_QTY = "robux_superpasses_qty"
ROBUX_USERNAME_SEARCH = "robux_username_search"
