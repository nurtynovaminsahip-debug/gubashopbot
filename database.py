import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gubashop.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                agreed_to_policy INTEGER DEFAULT 0,
                balance REAL DEFAULT 0.0,
                purchases INTEGER DEFAULT 0,
                deposits INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                total_spent REAL DEFAULT 0.0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                UNIQUE(referred_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extra_data TEXT DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_percent INTEGER DEFAULT 0,
                discount_rub REAL DEFAULT 0,
                min_amount REAL DEFAULT 0,
                active INTEGER DEFAULT 1,
                description TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_promocodes (
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, code)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                product_key TEXT PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_type TEXT NOT NULL,
                key TEXT NOT NULL,
                label TEXT NOT NULL,
                price_rub REAL NOT NULL,
                subcategory_id INTEGER DEFAULT NULL,
                description TEXT DEFAULT '',
                delivery_type TEXT DEFAULT 'manual',
                payment_methods TEXT DEFAULT 'crypto,yoo,balance',
                stars_price INTEGER DEFAULT NULL,
                banner_file_id TEXT DEFAULT NULL,
                auto_data TEXT DEFAULT NULL,
                UNIQUE(product_type, key)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sub_type TEXT DEFAULT 'generic'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                channel_title TEXT NOT NULL,
                invite_url TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS delivery_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                conditions TEXT DEFAULT '',
                prize TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ends_at TEXT DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contest_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(contest_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS section_banners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_top_buyers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                total_spent REAL DEFAULT 0.0,
                order_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrate existing tables
        migrations = [
            ("users", "total_spent", "REAL DEFAULT 0.0"),
            ("orders", "extra_data", "TEXT DEFAULT NULL"),
            ("products", "banner_file_id", "TEXT DEFAULT NULL"),
            ("products", "auto_data", "TEXT DEFAULT NULL"),
            ("products", "subcategory_id", "INTEGER DEFAULT NULL"),
            ("products", "description", "TEXT DEFAULT ''"),
            ("products", "delivery_type", "TEXT DEFAULT 'manual'"),
            ("products", "payment_methods", "TEXT DEFAULT 'crypto,yoo,balance'"),
            ("products", "stars_price", "INTEGER DEFAULT NULL"),
        ]
        for table, col, col_def in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        await db.commit()
        await _seed_categories(db)
        await _seed_products(db)
        await _seed_inventory(db)
        await _seed_settings(db)


async def _seed_settings(db):
    defaults = [
        ("stars_rate", "1.26"),
        ("stars_recipient", ""),
        ("robux_auto_enabled", "0"),
    ]
    for key, value in defaults:
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    await db.commit()


async def _seed_categories(db):
    await db.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (1, '💎 Telegram')")
    await db.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (2, '🎮 Roblox')")
    subcats = [
        (1, 1, '⭐️ Звезды', 'stars'),
        (2, 1, '💠 Премиум', 'premium'),
        (3, 1, '🧩 Юзернеймы', 'usernames'),
        (4, 1, '🧸 Подарки', 'gifts'),
        (5, 1, '🎁 NFT', 'nft'),
        (6, 2, '💎 Robux', 'robux'),
    ]
    for id_, cat_id, name, sub_type in subcats:
        await db.execute(
            "INSERT OR IGNORE INTO subcategories (id, category_id, name, sub_type) VALUES (?, ?, ?, ?)",
            (id_, cat_id, name, sub_type)
        )
    await db.commit()


async def _seed_products(db):
    usernames = [
        ("biden_com", "@biden_com | не нфт", 100),
        ("ceobocc", "@ceobocc | не нфт", 100),
        ("ceo_bocc", "@ceo_bocc | не нфт", 100),
        ("beeryPuccy", "@beeryPuccy | не нфт", 100),
    ]
    gifts = [
        ("bear", "🧸 Мишка | 13 ⭐️", 19),
        ("gift", "🎁 Подарок | 21 ⭐️", 29),
        ("rocket", "🚀 Ракета | 43 ⭐️", 60),
        ("ring", "💍 Кольцо | 85 ⭐️", 120),
    ]
    for key, label, price in usernames:
        await db.execute(
            "INSERT OR IGNORE INTO products (product_type, key, label, price_rub) VALUES ('username', ?, ?, ?)",
            (key, label, price)
        )
    for key, label, price in gifts:
        await db.execute(
            "INSERT OR IGNORE INTO products (product_type, key, label, price_rub) VALUES ('gift', ?, ?, ?)",
            (key, label, price)
        )
    await db.commit()


async def _seed_inventory(db):
    defaults = {
        "premium_1m": 10, "premium_3m": 10, "premium_6m": 10, "premium_12m": 10,
        "username_biden_com": 1, "username_ceobocc": 1,
        "username_ceo_bocc": 1, "username_beeryPuccy": 1,
        "gift_bear": 10, "gift_gift": 10, "gift_rocket": 10, "gift_ring": 10,
    }
    for key, qty in defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO inventory (product_key, quantity) VALUES (?, ?)",
            (key, qty)
        )
    await db.commit()


# ─── Settings ────────────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


# ─── Section Banners ─────────────────────────────────────────────────────────────

async def get_section_banner(section_key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM section_banners WHERE section_key = ?", (section_key,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_section_banner(section_key: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO section_banners (section_key, file_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (section_key, file_id)
        )
        await db.commit()


async def delete_section_banner(section_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM section_banners WHERE section_key = ?", (section_key,))
        await db.commit()


async def get_all_section_banners() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT section_key, file_id FROM section_banners") as cur:
            return [dict(r) for r in await cur.fetchall()]


# ─── Users ──────────────────────────────────────────────────────────────────────

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def create_user(user_id: int, username: str, first_name: str, referred_by: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, referred_by)
        )
        await db.commit()


async def set_agreed(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET agreed_to_policy = 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_balance(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0.0


async def update_balance(user_id: int, delta: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        await db.commit()


async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def add_referral(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (referrer_id, referred_id)
        )
        await db.commit()


async def get_referrer(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_order(order_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_order_status(order_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()


async def add_order(user_id: int, product: str, amount: float, payment_method: str, extra_data: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, product, amount, payment_method, extra_data) VALUES (?, ?, ?, ?, ?)",
            (user_id, product, amount, payment_method, extra_data)
        )
        await db.execute("UPDATE users SET purchases = purchases + 1, total_spent = total_spent + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
        return cur.lastrowid


async def increment_deposits(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET deposits = deposits + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_purchase_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT purchases FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_deposit_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT deposits FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_purchase_history(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        ) as cur:
            return await cur.fetchall()


async def get_top_buyers(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.user_id, u.username, u.first_name, u.total_spent,
               COUNT(o.id) as order_count,
               GROUP_CONCAT(DISTINCT o.payment_method) as methods
               FROM users u
               LEFT JOIN orders o ON u.user_id = o.user_id AND o.status != 'rejected'
               WHERE u.total_spent > 0
               GROUP BY u.user_id
               ORDER BY u.total_spent DESC
               LIMIT ?""",
            (limit,)
        ) as cur:
            real = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT * FROM custom_top_buyers ORDER BY total_spent DESC") as cur:
            custom = [dict(r) for r in await cur.fetchall()]

    custom_entries = [
        {
            'user_id': None,
            'username': None,
            'first_name': c['display_name'],
            'total_spent': c['total_spent'],
            'order_count': c['order_count'],
            'methods': None,
            'is_custom': True,
            'custom_id': c['id'],
        }
        for c in custom
    ]
    merged = real + custom_entries
    merged.sort(key=lambda x: x['total_spent'], reverse=True)
    return merged[:limit]


async def get_custom_top_buyers() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM custom_top_buyers ORDER BY total_spent DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_custom_top_buyer(display_name: str, total_spent: float, order_count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO custom_top_buyers (display_name, total_spent, order_count) VALUES (?, ?, ?)",
            (display_name, total_spent, order_count)
        )
        await db.commit()


async def remove_custom_top_buyer(entry_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM custom_top_buyers WHERE id = ?", (entry_id,))
        await db.commit()


async def get_promocode(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promocodes WHERE code = ? AND active = 1", (code,)) as cur:
            return await cur.fetchone()


async def add_promocode(code: str, discount_percent: int = 0, discount_rub: float = 0,
                         min_amount: float = 0, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, discount_percent, discount_rub, min_amount, description) VALUES (?, ?, ?, ?, ?)",
            (code, discount_percent, discount_rub, min_amount, description)
        )
        await db.commit()


async def activate_promocode(user_id: int, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_promocodes (user_id, code) VALUES (?, ?)",
            (user_id, code)
        )
        await db.commit()


async def get_user_promocodes(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_promocodes WHERE user_id = ? AND used = 0",
            (user_id,)
        ) as cur:
            return await cur.fetchall()


async def is_admin(user_id: int) -> bool:
    import os as _os
    admin_id = int(_os.environ.get("ADMIN_ID", "0"))
    if user_id == admin_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cur:
            return (await cur.fetchone()) is not None


async def add_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def remove_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            return [row[0] for row in await cur.fetchall()]


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM orders WHERE status != 'rejected'") as cur:
            total_revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM users WHERE agreed_to_policy = 1") as cur:
            agreed = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "agreed": agreed
    }


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE agreed_to_policy = 1") as cur:
            return [row[0] for row in await cur.fetchall()]


# ─── Categories ────────────────────────────────────────────────────────────────

async def get_categories() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name FROM categories ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_category(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()
        return cur.lastrowid


async def remove_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subcategories WHERE category_id = ?", (cat_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()


# ─── Subcategories ─────────────────────────────────────────────────────────────

async def get_subcategories(cat_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, category_id, name, sub_type FROM subcategories WHERE category_id = ? ORDER BY id",
            (cat_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_subcategory(subcat_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, category_id, name, sub_type FROM subcategories WHERE id = ?",
            (subcat_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def add_subcategory(cat_id: int, name: str, sub_type: str = 'generic') -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO subcategories (category_id, name, sub_type) VALUES (?, ?, ?)",
            (cat_id, name, sub_type)
        )
        await db.commit()
        return cur.lastrowid


async def remove_subcategory(subcat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subcategories WHERE id = ?", (subcat_id,))
        await db.commit()


async def get_all_subcategories() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT s.id, s.category_id, s.name, s.sub_type, c.name AS cat_name "
            "FROM subcategories s JOIN categories c ON s.category_id = c.id ORDER BY s.id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ─── Products ──────────────────────────────────────────────────────────────────

async def get_products(product_type: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, key, label, price_rub, description, delivery_type, payment_methods, banner_file_id "
            "FROM products WHERE product_type = ? ORDER BY id",
            (product_type,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_product(product_type: str, key: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, key, label, price_rub, description, delivery_type, payment_methods, banner_file_id "
            "FROM products WHERE product_type = ? AND key = ?",
            (product_type, key)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_product_by_id(product_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, product_type, key, label, price_rub, subcategory_id, "
            "description, delivery_type, payment_methods, stars_price, banner_file_id, auto_data "
            "FROM products WHERE id = ?",
            (product_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_products_by_subcat(subcat_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, product_type, key, label, price_rub, description, delivery_type, payment_methods, banner_file_id "
            "FROM products WHERE subcategory_id = ? AND product_type = 'generic' ORDER BY id",
            (subcat_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_products() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, product_type, key, label, price_rub FROM products ORDER BY product_type, id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_product(product_type: str, key: str, label: str, price_rub: float, stock: int,
                      subcategory_id=None, description: str = '', delivery_type: str = 'manual',
                      payment_methods: str = 'crypto,yoo,balance', stars_price: int = None,
                      banner_file_id: str = None, auto_data: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO products "
            "(product_type, key, label, price_rub, subcategory_id, description, delivery_type, payment_methods, stars_price, banner_file_id, auto_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (product_type, key, label, price_rub, subcategory_id, description, delivery_type, payment_methods, stars_price, banner_file_id, auto_data)
        )
        inv_key = f"{product_type}_{key}"
        await db.execute(
            "INSERT INTO inventory (product_key, quantity) VALUES (?, ?) "
            "ON CONFLICT(product_key) DO UPDATE SET quantity = excluded.quantity",
            (inv_key, stock)
        )
        await db.commit()


async def update_product_banner(product_id: int, banner_file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE products SET banner_file_id = ? WHERE id = ?",
            (banner_file_id, product_id)
        )
        await db.commit()


async def remove_product(product_type: str, key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM products WHERE product_type = ? AND key = ?",
            (product_type, key)
        )
        await db.execute(
            "UPDATE inventory SET quantity = 0 WHERE product_key = ?",
            (f"{product_type}_{key}",)
        )
        await db.commit()


async def remove_product_by_id(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT product_type, key FROM products WHERE id = ?", (product_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.execute(
                "UPDATE inventory SET quantity = 0 WHERE product_key = ?",
                (f"{row[0]}_{row[1]}",)
            )
            await db.commit()


# ─── Inventory ─────────────────────────────────────────────────────────────────

async def get_stock(key: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT quantity FROM inventory WHERE product_key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def set_stock(key: str, qty: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO inventory (product_key, quantity) VALUES (?, ?) "
            "ON CONFLICT(product_key) DO UPDATE SET quantity = excluded.quantity",
            (key, qty)
        )
        await db.commit()


async def decrement_stock(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE inventory SET quantity = MAX(0, quantity - 1) WHERE product_key = ?", (key,)
        )
        await db.commit()


async def get_all_stock() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT product_key, quantity FROM inventory") as cur:
            return {row[0]: row[1] for row in await cur.fetchall()}


# ─── Delivery Items ─────────────────────────────────────────────────────────────

async def add_delivery_item(product_id: int, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO delivery_items (product_id, content) VALUES (?, ?)",
            (product_id, content)
        )
        await db.commit()


async def get_delivery_item(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, content FROM delivery_items WHERE product_id = ? AND used = 0 LIMIT 1",
            (product_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def mark_delivery_used(item_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE delivery_items SET used = 1, used_by = ? WHERE id = ?",
            (user_id, item_id)
        )
        await db.commit()


async def count_delivery_items(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM delivery_items WHERE product_id = ?", (product_id,)
        ) as cur:
            total = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM delivery_items WHERE product_id = ? AND used = 0", (product_id,)
        ) as cur:
            avail = (await cur.fetchone())[0]
    return total, avail


async def delete_delivery_items(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM delivery_items WHERE product_id = ?", (product_id,))
        await db.commit()


# ─── Required Channels ─────────────────────────────────────────────────────────

async def get_required_channels() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM required_channels ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_required_channel(channel_id: str, title: str, invite_url: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO required_channels (channel_id, channel_title, invite_url) VALUES (?, ?, ?)",
            (channel_id, title, invite_url)
        )
        await db.commit()


async def toggle_required_channel(ch_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE required_channels SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (ch_id,)
        )
        await db.commit()


async def remove_required_channel(ch_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM required_channels WHERE id = ?", (ch_id,))
        await db.commit()


# ─── Contests ──────────────────────────────────────────────────────────────────

async def create_contest(title: str, description: str, conditions: str, prize: str, ends_at: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO contests (title, description, conditions, prize, ends_at) VALUES (?, ?, ?, ?, ?)",
            (title, description, conditions, prize, ends_at)
        )
        await db.commit()
        return cur.lastrowid


async def get_active_contests() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM contests WHERE is_active = 1 ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_contests() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM contests ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_contest(contest_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM contests WHERE id = ?", (contest_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def toggle_contest(contest_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE contests SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (contest_id,)
        )
        await db.commit()


async def delete_contest(contest_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM contest_participants WHERE contest_id = ?", (contest_id,))
        await db.execute("DELETE FROM contests WHERE id = ?", (contest_id,))
        await db.commit()


async def join_contest(contest_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO contest_participants (contest_id, user_id) VALUES (?, ?)",
                (contest_id, user_id)
            )
            await db.commit()
            return True
        except Exception:
            return False


async def is_contest_participant(contest_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM contest_participants WHERE contest_id = ? AND user_id = ?",
            (contest_id, user_id)
        ) as cur:
            return (await cur.fetchone()) is not None


async def get_contest_participants_count(contest_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM contest_participants WHERE contest_id = ?", (contest_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# ─── Order Chat ────────────────────────────────────────────────────────────────

async def add_order_chat_message(order_id: int, user_id: int, sender: str, message: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO order_chat (order_id, user_id, sender, message) VALUES (?, ?, ?, ?)",
            (order_id, user_id, sender, message)
        )
        await db.commit()


async def get_order_chat(order_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM order_chat WHERE order_id = ? ORDER BY created_at",
            (order_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_active_order(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
