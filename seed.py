"""Populate the database with demo users, categories, and products.

Safe to run repeatedly: rows that already exist are left untouched.
Requires .streamlit/secrets.toml (used by init_db for the default admin).

Run with: python seed.py
"""

import json
from datetime import datetime
from pathlib import Path

from v3 import get_db, hash_pw, init_db

SAMPLE_IMAGE_DIR = Path("sample_images")


def sample_photos(stem):
    """Main image plus its two variants, e.g. cordless_drill_set.png/_angle/_closeup."""
    photos = []
    for pattern in (f"{stem}.*", f"{stem}_angle.*", f"{stem}_closeup.*"):
        photos.extend(
            p.as_posix() for p in sorted(SAMPLE_IMAGE_DIR.glob(pattern)) if p.is_file()
        )
    return photos


DEMO_USERS = [
    # username, password, email, address, phone
    ("demo_lender", "demo1234", "lender@example.com", "12 Maple St", "555-0101"),
    ("demo_borrower", "demo1234", "borrower@example.com", "34 Oak Ave", "555-0102"),
]

DEMO_CATEGORIES = [
    # name, lender_fee, borrower_fee
    ("Tools", 2.0, 1.0),
    ("Electronics", 3.5, 2.0),
    ("Books", 0.5, 0.25),
    ("Home & Garden", 1.5, 0.75),
    ("Clothing", 2.0, 1.0),
    ("Fashion Accessories", 3.0, 1.5),
    ("Sports Equipment", 4.0, 2.0),
    ("Shoes", 2.5, 1.25),
    ("Makeup", 1.5, 0.75),
    # Categories introduced by v3's starter set
    ("Self Care", 1.5, 1.0),
    ("Toys & Games", 1.0, 1.0),
    ("Home & Tools", 2.0, 1.5),
]

DEMO_PRODUCTS = [
    # Tools
    {
        "lender": "demo_lender",
        "title": "Cordless Drill Set",
        "description": "20V cordless drill with two batteries and a charger. Great for home projects.",
        "category": "Tools",
        "rent_price": 15.0,
        "image": "cordless_drill_set",
        "rent_reason": "Bought for a one-off renovation, now gathering dust.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "6 months",
    },
    {
        "lender": "demo_borrower",
        "title": "Adjustable Wrench",
        "description": "Sturdy steel adjustable wrench, fits most common nut sizes.",
        "category": "Tools",
        "rent_price": 5.0,
        "image": "adjustable_wrench",
        "rent_reason": "Inherited a full toolset and don't need the duplicate.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "2 years",
    },
    # Electronics
    {
        "lender": "demo_lender",
        "title": "Portable Bluetooth Speaker",
        "description": "Compact waterproof speaker, perfect for trips and picnics.",
        "category": "Electronics",
        "rent_price": 10.0,
        "image": "bluetooth_speaker",
        "rent_reason": "Upgraded to a bigger model.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-01-10",
    },
    {
        "lender": "demo_borrower",
        "title": "Wireless Headphones",
        "description": "Over-ear wireless headphones with padded cups and long battery life.",
        "category": "Electronics",
        "rent_price": 12.0,
        "image": "wireless_headphones",
        "rent_reason": "Work sent me a newer pair.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "8 months",
    },
    # Books
    {
        "lender": "demo_borrower",
        "title": "Python Cookbook (3rd Ed.)",
        "description": "Well-loved reference book. A few notes in the margins, no missing pages.",
        "category": "Books",
        "rent_price": 4.0,
        "image": "python_cookbook",
        "rent_reason": "Finished the course, passing it on.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "1 year",
    },
    {
        "lender": "demo_lender",
        "title": "Gardening Handbook",
        "description": "Illustrated guide to soil, pruning, and seasonal planting.",
        "category": "Books",
        "rent_price": 3.0,
        "image": "gardening_handbook",
        "rent_reason": "Bought for a school project, barely opened.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-02-20",
    },
    # Home & Garden
    {
        "lender": "demo_lender",
        "title": "Unopened Interior Paint (5L)",
        "description": "Sealed tin of white emulsion paint, still in date.",
        "category": "Home & Garden",
        "rent_price": 8.0,
        "image": "interior_paint",
        "rent_reason": "Ordered too much for the job.",
        "is_consumable": True,
        "mfg_date": "2026-01-15",
        "exp_date": "2028-01-15",
        "usage_status": "Unused/New",
    },
    {
        "lender": "demo_borrower",
        "title": "Ceramic Plant Pot",
        "description": "Glazed terracotta pot, ideal for a medium houseplant.",
        "category": "Home & Garden",
        "rent_price": 6.0,
        "image": "plant_pot",
        "rent_reason": "Moving to a place with no room for plants.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "1 year",
    },
    # Clothing
    {
        "lender": "demo_lender",
        "title": "Denim Jacket",
        "description": "Classic blue denim jacket, medium wash, size M.",
        "category": "Clothing",
        "rent_price": 12.0,
        "image": "denim_jacket",
        "rent_reason": "Bought the wrong size and never returned it.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-03-05",
    },
    {
        "lender": "demo_borrower",
        "title": "Cotton T-Shirt",
        "description": "Plain blue cotton tee in size L, gently worn.",
        "category": "Clothing",
        "rent_price": 4.0,
        "image": "cotton_tshirt",
        "rent_reason": "Closet clean-out.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "6 months",
    },
    # Fashion Accessories
    {
        "lender": "demo_lender",
        "title": "Leather Handbag",
        "description": "Brown faux-leather handbag with a zip closure and inner pocket.",
        "category": "Fashion Accessories",
        "rent_price": 18.0,
        "image": "leather_handbag",
        "rent_reason": "Got a different one as a gift.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "1 year",
    },
    {
        "lender": "demo_borrower",
        "title": "Polarized Sunglasses",
        "description": "Dark polarized lenses with a lightweight frame and case.",
        "category": "Fashion Accessories",
        "rent_price": 7.0,
        "image": "sunglasses",
        "rent_reason": "Bought two pairs by mistake.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-04-12",
    },
    # Sports Equipment
    {
        "lender": "demo_lender",
        "title": "Adjustable Dumbbell Set",
        "description": "Pair of adjustable dumbbells, ideal for a home workout.",
        "category": "Sports Equipment",
        "rent_price": 14.0,
        "image": "dumbbell",
        "rent_reason": "Joined a gym, no longer using the home set.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "2 years",
    },
    {
        "lender": "demo_borrower",
        "title": "Yoga Mat",
        "description": "Non-slip purple yoga mat, easy to roll up and carry.",
        "category": "Sports Equipment",
        "rent_price": 5.0,
        "image": "yoga_mat",
        "rent_reason": "Trying a different fitness class.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "8 months",
    },
    # Shoes
    {
        "lender": "demo_lender",
        "title": "Running Sneakers",
        "description": "Lightweight running shoes, size 42, plenty of tread left.",
        "category": "Shoes",
        "rent_price": 16.0,
        "image": "running_sneakers",
        "rent_reason": "Switched to trail shoes.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "5 months",
    },
    {
        "lender": "demo_borrower",
        "title": "Canvas Sneakers",
        "description": "Neutral canvas sneakers, size 41, great for casual wear.",
        "category": "Shoes",
        "rent_price": 9.0,
        "image": "canvas_shoes",
        "rent_reason": "Bought the wrong size online.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-05-01",
    },
    # Makeup
    {
        "lender": "demo_lender",
        "title": "Matte Lipstick Set",
        "description": "Set of three unopened matte lipsticks in everyday shades.",
        "category": "Makeup",
        "rent_price": 6.0,
        "image": "lipstick",
        "rent_reason": "Received a duplicate set as a gift.",
        "is_consumable": True,
        "mfg_date": "2026-02-01",
        "exp_date": "2028-02-01",
        "usage_status": "Unused/New",
    },
    {
        "lender": "demo_borrower",
        "title": "Eau de Parfum (50ml)",
        "description": "Floral fragrance in a 50ml bottle, about 80% full.",
        "category": "Makeup",
        "rent_price": 20.0,
        "image": "perfume",
        "rent_reason": "Changed my preferred scent.",
        "is_consumable": True,
        "mfg_date": "2025-11-01",
        "exp_date": "2028-11-01",
        "usage_status": "Used",
        "usage_duration": "4 months",
    },
    # Self Care
    {
        "lender": "demo_lender",
        "title": "Electric Shaver",
        "description": "Rechargeable electric shaver with a cleaning brush and travel case.",
        "category": "Self Care",
        "rent_price": 11.0,
        "image": "electric_shaver",
        "rent_reason": "Switched to a manual razor.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "5 months",
    },
    {
        "lender": "demo_borrower",
        "title": "Skincare Serum Set",
        "description": "Two unopened bottles of lightweight hydrating face serum.",
        "category": "Self Care",
        "rent_price": 13.0,
        "image": "skincare_serum",
        "rent_reason": "Skin reacted to one of the ingredients.",
        "is_consumable": True,
        "mfg_date": "2026-03-01",
        "exp_date": "2028-03-01",
        "usage_status": "Unused/New",
    },
    # Toys & Games
    {
        "lender": "demo_lender",
        "title": "Wooden Building Blocks",
        "description": "Set of 12 painted wooden blocks, great for imaginative play.",
        "category": "Toys & Games",
        "rent_price": 7.0,
        "image": "wooden_blocks",
        "rent_reason": "Kids have outgrown them.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "3 years",
    },
    {
        "lender": "demo_borrower",
        "title": "Board Game Collection",
        "description": "Three family board games in one box, all pieces accounted for.",
        "category": "Toys & Games",
        "rent_price": 9.0,
        "image": "board_game",
        "rent_reason": "We rarely have time for game night anymore.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "2 years",
    },
    # Home & Tools
    {
        "lender": "demo_lender",
        "title": "Cordless Screwdriver",
        "description": "Compact rechargeable screwdriver with a bit set, ideal for furniture.",
        "category": "Home & Tools",
        "rent_price": 8.0,
        "image": "cordless_screwdriver",
        "rent_reason": "Finished assembling all the flat-pack furniture.",
        "is_consumable": False,
        "usage_status": "Used",
        "usage_duration": "3 months",
    },
    {
        "lender": "demo_borrower",
        "title": "Folding Ladder",
        "description": "Lightweight aluminium step ladder that folds flat for storage.",
        "category": "Home & Tools",
        "rent_price": 10.0,
        "image": "folding_ladder",
        "rent_reason": "Borrowed one from a neighbour instead.",
        "is_consumable": False,
        "usage_status": "Unused/New",
        "purchase_date": "2026-06-10",
    },
]

# Gender/audience metadata used by v3's classifier display and borrower filters.
# Values map a product title to (is_gender_specific, target_gender).
DEMO_GENDER = {
    "Cordless Drill Set": (False, "Gender Neutral"),
    "Adjustable Wrench": (False, "Gender Neutral"),
    "Portable Bluetooth Speaker": (False, "Gender Neutral"),
    "Wireless Headphones": (False, "Gender Neutral"),
    "Python Cookbook (3rd Ed.)": (False, "Gender Neutral"),
    "Gardening Handbook": (False, "Gender Neutral"),
    "Unopened Interior Paint (5L)": (False, "Gender Neutral"),
    "Ceramic Plant Pot": (False, "Gender Neutral"),
    "Denim Jacket": (True, "Unisex"),
    "Cotton T-Shirt": (True, "Unisex"),
    "Leather Handbag": (True, "Women's"),
    "Polarized Sunglasses": (True, "Unisex"),
    "Adjustable Dumbbell Set": (False, "Gender Neutral"),
    "Yoga Mat": (False, "Gender Neutral"),
    "Running Sneakers": (True, "Men's"),
    "Canvas Sneakers": (True, "Unisex"),
    "Matte Lipstick Set": (True, "Women's"),
    "Eau de Parfum (50ml)": (True, "Women's"),
    "Electric Shaver": (True, "Men's"),
    "Skincare Serum Set": (True, "Unisex"),
    "Wooden Building Blocks": (True, "Kids"),
    "Board Game Collection": (False, "Gender Neutral"),
    "Cordless Screwdriver": (False, "Gender Neutral"),
    "Folding Ladder": (False, "Gender Neutral"),
}


def seed():
    init_db()  # ensure schema and default admin exist first

    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    added_users = 0
    for username, password, email, address, phone in DEMO_USERS:
        if c.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            continue
        c.execute(
            "INSERT INTO users (username, password, email, address, phone) VALUES (?, ?, ?, ?, ?)",
            (username, hash_pw(password), email, address, phone),
        )
        added_users += 1

    added_categories = 0
    for name, lender_fee, borrower_fee in DEMO_CATEGORIES:
        if c.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone():
            continue
        c.execute(
            "INSERT INTO categories (name, lender_fee, borrower_fee) VALUES (?, ?, ?)",
            (name, lender_fee, borrower_fee),
        )
        added_categories += 1

    added_products = 0
    refreshed_products = 0
    for p in DEMO_PRODUCTS:
        lender = c.execute("SELECT id FROM users WHERE username = ?", (p["lender"],)).fetchone()
        if not lender:
            continue
        lender_id = lender["id"]
        photos = sample_photos(p["image"])
        is_specific, target_gender = DEMO_GENDER.get(p["title"], (False, "Gender Neutral"))
        note = (
            f"Gender-specific product (curated demo data) — Suggested: {target_gender}"
            if is_specific
            else "Gender-neutral product (curated demo data)"
        )
        existing = c.execute(
            "SELECT id FROM products WHERE title = ? AND lender_id = ?",
            (p["title"], lender_id),
        ).fetchone()
        if existing:
            # Keep seeded demo products in sync with the latest sample images and
            # v3's gender/audience fields without touching user-created products.
            c.execute(
                """UPDATE products SET photos = ?, is_gender_specific = ?,
                   target_gender = ?, ai_classification_note = ? WHERE id = ?""",
                (
                    json.dumps(photos),
                    int(is_specific),
                    target_gender,
                    note,
                    existing["id"],
                ),
            )
            refreshed_products += 1
            continue
        c.execute(
            """INSERT INTO products
               (lender_id, title, description, category, rent_price, photos,
                is_consumable, mfg_date, exp_date, rent_reason, usage_status,
                usage_duration, purchase_date, is_gender_specific, target_gender,
                ai_classification_note, is_available, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                lender_id,
                p["title"],
                p["description"],
                p["category"],
                p["rent_price"],
                json.dumps(photos),
                int(p.get("is_consumable", False)),
                p.get("mfg_date", ""),
                p.get("exp_date", ""),
                p["rent_reason"],
                p["usage_status"],
                p.get("usage_duration", ""),
                p.get("purchase_date", ""),
                int(is_specific),
                target_gender,
                note,
                now,
            ),
        )
        added_products += 1

    conn.commit()
    conn.close()
    print(
        f"Seed complete: {added_users} users, {added_categories} categories, "
        f"{added_products} products added, {refreshed_products} demo products refreshed."
    )


if __name__ == "__main__":
    seed()
