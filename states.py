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
