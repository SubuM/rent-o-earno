"""Generate a comprehensive demo dataset for the v9 application.

The script rebuilds the demo dataset from scratch (users, address books, categories,
products, shopping carts and order history) so it is safe to re-run whenever you want
a fresh, rich sample database.

Passwords for the regular demo users are read from Streamlit secrets under
the [demo_users] table (locally: .streamlit/secrets.toml, on Streamlit Cloud:
the app's Secrets settings). Admin credentials are handled by v9.init_db().

Run with:  python seed_v9.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

import v9

SECRETS_PATH = Path(".streamlit/secrets.toml")
IMAGE_DIR = Path("sample_images")
NEUTRAL = v9.GENDER_NEUTRAL_LABEL


# --------------------------------------------------------------------------- helpers
def load_demo_passwords():
    """Read demo passwords from Streamlit secrets (Cloud or local .streamlit/secrets.toml)."""
    try:
        demo_users = st.secrets.get("demo_users", {})
        if demo_users:
            return dict(demo_users)
    except Exception:
        pass

    # Fallback for running the seeder outside Streamlit on Python 3.11+.
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 and older
        import tomli as tomllib
    with SECRETS_PATH.open("rb") as handle:
        secrets = tomllib.load(handle)
    return dict(secrets.get("demo_users", {}))


def sample_photos(stem):
    """Main image plus its angled and close-up variants."""
    photos = []
    for pattern in (f"{stem}.*", f"{stem}_angle.*", f"{stem}_closeup.*"):
        photos.extend(
            p.as_posix() for p in sorted(IMAGE_DIR.glob(pattern)) if p.is_file()
        )
    return photos


# --------------------------------------------------------------------------- users
# username, full name, email, phone, city, state/postal, is a lender, house no, street
DEMO_USERS = [
    ("alex_morgan", "Alex Morgan", "alex.morgan@example.com", "+1 (555) 0101", "Springfield", "IL 62701", True, "42B", "Oakwood Avenue"),
    ("priya_sharma", "Priya Sharma", "priya.sharma@example.com", "+1 (555) 0102", "Springfield", "IL 62702", False, "18", "Maple Street"),
    ("rahul_verma", "Rahul Verma", "rahul.verma@example.com", "+1 (555) 0103", "Shelbyville", "IL 62565", True, "7", "Riverside Drive"),
    ("meera_iyer", "Meera Iyer", "meera.iyer@example.com", "+1 (555) 0104", "Springfield", "IL 62703", False, "304", "Kingsway Plaza"),
    ("james_wilson", "James Wilson", "james.wilson@example.com", "+1 (555) 0105", "Capital City", "IL 62704", True, "12", "Cedar Lane"),
    ("sofia_rodriguez", "Sofia Rodriguez", "sofia.rodriguez@example.com", "+1 (555) 0106", "Springfield", "IL 62705", False, "56", "Birchwood Road"),
    ("david_chen", "David Chen", "david.chen@example.com", "+1 (555) 0107", "Shelbyville", "IL 62566", True, "9", "Willow Close"),
    ("ananya_rao", "Ananya Rao", "ananya.rao@example.com", "+1 (555) 0108", "Capital City", "IL 62706", False, "21", "Sunrise Apartments"),
    ("lucas_martin", "Lucas Martin", "lucas.martin@example.com", "+1 (555) 0109", "Springfield", "IL 62707", True, "88", "Grand Avenue"),
    ("fatima_khan", "Fatima Khan", "fatima.khan@example.com", "+1 (555) 0110", "Springfield", "IL 62708", False, "15", "Parkview Drive"),
    ("noah_brown", "Noah Brown", "noah.brown@example.com", "+1 (555) 0111", "Shelbyville", "IL 62567", True, "34", "Hilltop Road"),
    ("emma_davis", "Emma Davis", "emma.davis@example.com", "+1 (555) 0112", "Capital City", "IL 62709", False, "27", "Lakeview Street"),
]

# Admin contact details are enriched so order receipts show realistic pickup data.
ADMIN_CONTACTS = {
    "SMA": ("SMA Admin", "admin.sma@example.com", "+1 (555) 0001", "100", "Admin Plaza", "Springfield", "IL 62701"),
    "MDG": ("MDG Admin", "admin.mdg@example.com", "+1 (555) 0002", "200", "Admin Plaza", "Springfield", "IL 62701"),
}

OFFICE_SPOTS = [
    ("18", "Kingsway Plaza, Suite 304", "Opposite City Mall"),
    ("22", "Tech Park Road, Block B", "Near Metro Station"),
    ("45", "Corporate Boulevard, Floor 6", "Next to Central Library"),
    ("9", "Innovation Drive, Unit 12", "Behind City Hospital"),
    ("77", "Market Square, 2nd Floor", "Above Green Cafe"),
    ("31", "Commerce Street, Suite 8", "Near Post Office"),
    ("5", "Business Park Way, Tower C", "Opposite River Bridge"),
    ("63", "Summit Avenue, Floor 3", "Near City Stadium"),
    ("14", "Garden Court, Block A", "Near Botanical Garden"),
    ("88", "Harbor Road, Suite 21", "Close to Ferry Terminal"),
    ("26", "University Road, Room 4", "Opposite Main Campus"),
    ("40", "Silver Lane, Unit 7", "Near Cinema Hall"),
]

# Custom label text stored in `custom_label` for addresses whose label is 'Other'.
CUSTOM_OTHER_LABELS = [
    "Guest Space",
    "Shared Home",
    "Weekend Place",
    "Secondary Residence",
    "Community Space",
    "Studio Annex",
    "Extended Stay Suite",
    "Holiday Cottage",
]

OTHER_SPOTS = [
    ("7", "Riverside Drive, Apt 12", "By Riverside Park"),
    ("56", "Sunset Residency, Flat 3B", "Near Community Center"),
    ("12", "Hillcrest Colony", "Behind Water Tank"),
    ("33", "Rose Garden Apartments", "Opposite School"),
    ("19", "Green Valley Enclave", "Near Temple"),
    ("64", "Seaside Cottage Road", "By the Beach"),
]


# --------------------------------------------------------------------------- categories
# Categories whose products are treated as consumables (mfg/exp dates are populated).
# Extensible so add-on seed scripts can introduce new consumable categories.
CONSUMABLE_CATEGORIES = {"Makeup", "Self Care"}

# name, lender fee, borrower fee
CATEGORIES = [
    ("Tools", 2.0, 1.0),
    ("Electronics", 3.5, 2.0),
    ("Books", 0.5, 0.25),
    ("Home & Garden", 1.5, 0.75),
    ("Clothing", 2.0, 1.0),
    ("Fashion Accessories", 1.5, 1.0),
    ("Shoes", 2.0, 1.5),
    ("Makeup", 1.5, 1.0),
    ("Self Care", 1.5, 1.0),
    ("Sports Equipment", 2.5, 1.25),
    ("Toys & Games", 1.0, 1.0),
    ("Home & Tools", 2.0, 1.5),
    ("Camping Gear", 2.5, 1.5),
    ("Musical Instruments", 3.0, 2.0),
    ("Baby & Kids", 1.5, 1.0),
    ("Kitchen Appliances", 2.0, 1.25),
    ("Photography", 3.0, 2.0),
    ("Gaming", 2.5, 1.5),
    ("Fitness", 2.0, 1.25),
    ("Travel Gear", 2.0, 1.25),
]

CATEGORY_DESCRIPTIONS = {
    "Tools": "A dependable {title_low} from a well-equipped home workshop. Clean, fully tested and stored in a dry place, with its original case and essential accessories included.",
    "Electronics": "{title_low} in excellent working condition. Factory reset, includes the original charger and packaging, and has no cosmetic damage.",
    "Books": "{title_low} in very good reading condition — clean pages, a solid spine and no highlighting. A great title to borrow before you buy.",
    "Home & Garden": "{title_low} kept in great shape at home. Carefully cleaned before listing and ready for immediate pickup.",
    "Clothing": "{title_low} from a smoke-free home. Washed, inspected and stored folded. Any signs of wear are minor and shown in the photos.",
    "Fashion Accessories": "{title_low} is a versatile piece that pairs with many outfits. Stored in a dust bag and carefully checked before listing.",
    "Shoes": "{title_low} with plenty of life left. Cleaned and deodorised, with soles and uppers in good condition — see the close-up photos.",
    "Makeup": "Unopened / gently used {title_low}, stored away from direct sunlight. Ideal for trying a shade or finishing a project without buying full size.",
    "Self Care": "{title_low} in hygienic, sealed condition. Kept in a cool, dry cabinet and never shared between uses.",
    "Sports Equipment": "{title_low} that has been well looked after. Inspected after every use and stored in a covered garage.",
    "Toys & Games": "{title_low} from a family with growing kids. All pieces checked and accounted for, and wiped clean before listing.",
    "Home & Tools": "{title_low} kept in a tidy garage. Works as intended and includes the accessories pictured.",
    "Camping Gear": "{title_low} used on a handful of trips and dried thoroughly after each one. No tears, odours or missing parts.",
    "Musical Instruments": "{title_low} that has been tuned and play-tested recently. Includes the case and basic accessories for a beginner.",
    "Baby & Kids": "{title_low} from a growing family. Sanitised, safety-checked and stored in a clean, smoke-free home.",
    "Kitchen Appliances": "{title_low} in good working order, descaled and deep-cleaned. All controls tested and the original manual is included.",
    "Photography": "{title_low} in careful enthusiast hands. Lens and sensor cleaned, batteries charged, and all buttons tested.",
    "Gaming": "{title_low} in great condition with all pieces present. Stored indoors and ready for a game night.",
    "Fitness": "{title_low} that has seen light home use. Wiped down after every session and stored flat in a dry room.",
    "Travel Gear": "{title_low} from a careful traveller. Cleaned inside and out, zips tested and wheels checked.",
    "default": "{title_low} in good, well-cared-for condition. Barely used and stored carefully — check the photos for full details.",
}

RENT_REASONS = [
    "Bought for a one-off occasion and rarely use it now.",
    "Upgraded to a newer model, this one is still in great shape.",
    "Received as a gift but already own one.",
    "Bought the wrong size online and never got around to returning it.",
    "Finished the project it was purchased for.",
    "The kids have outgrown it, but it is still perfectly usable.",
    "Switched to a different hobby, so it sits unused in storage.",
    "Won it in a raffle and have no need for it.",
    "Moving house and downsizing my collection.",
    "I rent it out so someone else can get more use from it.",
]


# (image stem, title, category, rent price, lender username, audience or None)
# Publicly available listings — these are what borrowers browse and rent.
AVAILABLE_PRODUCTS = [
    ("cordless_drill_set", "Cordless Drill Set 18V", "Tools", 14.0, "rahul_verma", None),
    ("adjustable_wrench", "Adjustable Wrench & Spanner Set", "Tools", 6.0, "rahul_verma", None),
    ("cordless_screwdriver", "Cordless Screwdriver with Bits", "Tools", 8.0, "lucas_martin", None),
    ("folding_ladder", "Folding Aluminium Ladder", "Tools", 12.0, "noah_brown", None),

    ("bluetooth_speaker", "Portable Bluetooth Speaker", "Electronics", 11.0, "james_wilson", None),
    ("wireless_headphones", "Noise-Cancelling Headphones", "Electronics", 18.0, "james_wilson", None),
    ("portable_projector", "Pocket HD Projector", "Electronics", 22.0, "david_chen", None),
    ("smart_watch", "Smart Watch with Fitness Tracking", "Electronics", 16.0, "david_chen", None),
    ("quadcopter_drone", "Quadcopter Drone with Camera", "Electronics", 35.0, "lucas_martin", None),

    ("python_cookbook", "Python Cookbook (3rd Ed.)", "Books", 7.0, "alex_morgan", None),
    ("gardening_handbook", "Gardening Handbook", "Books", 5.0, "alex_morgan", None),
    ("python_cookbook", "Data Science with Python", "Books", 9.0, "alex_morgan", None),

    ("interior_paint", "Unopened Interior Paint (5L)", "Home & Garden", 15.0, "rahul_verma", None),
    ("plant_pot", "Ceramic Plant Pot Set", "Home & Garden", 6.0, "meera_iyer", None),
    ("desk_lamp", "Adjustable LED Desk Lamp", "Home & Garden", 9.0, "james_wilson", None),

    ("denim_jacket", "Denim Jacket — Size M", "Clothing", 12.0, "alex_morgan", "Unisex"),
    ("denim_jacket", "Vintage Denim Jacket — Size L", "Clothing", 14.0, "sofia_rodriguez", "Women's"),
    ("cotton_tshirt", "Cotton T-Shirt — Navy", "Clothing", 5.0, "noah_brown", "Unisex"),
    ("cotton_tshirt", "Graphic Cotton Tee — Kids", "Clothing", 4.0, "fatima_khan", "Kids"),

    ("leather_handbag", "Leather Handbag", "Fashion Accessories", 20.0, "priya_sharma", "Women's"),
    ("sunglasses", "Polarized Sunglasses", "Fashion Accessories", 8.0, "meera_iyer", "Unisex"),
    ("smart_watch", "Fitness Band Watch", "Fashion Accessories", 10.0, "priya_sharma", "Unisex"),

    ("running_sneakers", "Running Sneakers — Men's 42", "Shoes", 15.0, "rahul_verma", "Men's"),
    ("canvas_shoes", "Canvas Sneakers — Unisex 41", "Shoes", 9.0, "ananya_rao", "Unisex"),

    ("lipstick", "Matte Lipstick Set", "Makeup", 6.0, "priya_sharma", "Women's"),
    ("perfume", "Floral Eau de Parfum (50ml)", "Makeup", 13.0, "sofia_rodriguez", "Women's"),
    ("lipstick", "Everyday Lip Balm Trio", "Makeup", 4.0, "ananya_rao", "Women's"),

    ("electric_shaver", "Electric Shaver with Case", "Self Care", 11.0, "rahul_verma", "Men's"),
    ("skincare_serum", "Hydrating Skincare Serum", "Self Care", 13.0, "meera_iyer", "Unisex"),
    ("yoga_wheel", "Yoga Wheel", "Self Care", 7.0, "fatima_khan", "Unisex"),

    ("dumbbell", "Adjustable Dumbbell Set (20kg)", "Sports Equipment", 14.0, "noah_brown", None),
    ("yoga_mat", "Non-Slip Yoga Mat", "Sports Equipment", 7.0, "fatima_khan", None),
    ("yoga_wheel", "Yoga Stretch Wheel", "Sports Equipment", 6.0, "sofia_rodriguez", None),

    ("wooden_blocks", "Wooden Building Blocks (12 pcs)", "Toys & Games", 7.0, "alex_morgan", "Kids"),
    ("board_game", "Family Board Game Collection", "Toys & Games", 9.0, "meera_iyer", None),

    ("cordless_screwdriver", "Mini Cordless Screwdriver Kit", "Home & Tools", 8.0, "lucas_martin", None),
    ("folding_ladder", "Compact Step Ladder", "Home & Tools", 10.0, "noah_brown", None),

    ("camping_tent", "2-Person Camping Tent", "Camping Gear", 24.0, "lucas_martin", None),
    ("sleeping_bag", "Mummy Sleeping Bag", "Camping Gear", 16.0, "lucas_martin", None),
    ("camp_chair", "Folding Camp Chair", "Camping Gear", 9.0, "noah_brown", None),
    ("led_headlamp", "Rechargeable LED Headlamp", "Camping Gear", 8.0, "james_wilson", None),

    ("acoustic_guitar", "Acoustic Guitar with Case", "Musical Instruments", 28.0, "david_chen", None),
    ("electronic_keyboard", "61-Key Electronic Keyboard", "Musical Instruments", 32.0, "david_chen", None),
    ("violin", "Student Violin 4/4 with Bow", "Musical Instruments", 25.0, "ananya_rao", None),

    ("baby_stroller", "Lightweight Baby Stroller", "Baby & Kids", 30.0, "priya_sharma", "Kids"),
    ("kids_scooter", "Kids Push Scooter", "Baby & Kids", 12.0, "fatima_khan", "Kids"),
    ("wooden_blocks", "Toddler Shape Sorter Blocks", "Baby & Kids", 6.0, "sofia_rodriguez", "Kids"),

    ("countertop_blender", "Countertop Blender 600W", "Kitchen Appliances", 18.0, "meera_iyer", None),
    ("espresso_machine", "Compact Espresso Machine", "Kitchen Appliances", 26.0, "james_wilson", None),
    ("cast_iron_skillet", "10-inch Cast Iron Skillet", "Kitchen Appliances", 10.0, "rahul_verma", None),

    ("dslr_camera", "DSLR Camera with 18-55mm Lens", "Photography", 45.0, "david_chen", None),
    ("camera_tripod", "Adjustable Camera Tripod", "Photography", 12.0, "lucas_martin", None),
    ("portable_projector", "HD Presentation Projector", "Photography", 25.0, "ananya_rao", None),

    ("board_game", "Strategy Board Game Set", "Gaming", 11.0, "noah_brown", None),
    ("wireless_headphones", "Gaming Headset with Mic", "Gaming", 16.0, "james_wilson", None),

    ("dumbbell", "Neoprene Dumbbell Pair (5kg)", "Fitness", 9.0, "fatima_khan", None),
    ("yoga_mat", "Extra-Thick Exercise Mat", "Fitness", 11.0, "sofia_rodriguez", None),
    ("yoga_wheel", "Pilates Resistance Ring", "Fitness", 8.0, "ananya_rao", None),

    ("carry_on_suitcase", "Carry-On Suitcase (Cabin Size)", "Travel Gear", 22.0, "emma_davis", None),
    ("portable_projector", "Travel Mini Projector", "Travel Gear", 20.0, "emma_davis", None),
    ("carry_on_suitcase", "Hard-Shell Travel Case", "Travel Gear", 18.0, "noah_brown", None),
]

# Products that appear in historical orders. They are already rented out
# (is_available = 0), which is what the app does when an order is placed.
RENTED_PRODUCTS = [
    ("dslr_camera", "Mirrorless Camera Kit", "Photography", 55.0, "david_chen", None),
    ("camping_tent", "4-Season Mountain Tent", "Camping Gear", 40.0, "lucas_martin", None),
    ("acoustic_guitar", "Semi-Acoustic Guitar", "Musical Instruments", 35.0, "david_chen", None),
    ("leather_handbag", "Designer Leather Tote", "Fashion Accessories", 30.0, "priya_sharma", "Women's"),
    ("running_sneakers", "Trail Running Shoes", "Shoes", 18.0, "rahul_verma", "Men's"),
    ("baby_stroller", "Travel Stroller", "Baby & Kids", 28.0, "priya_sharma", "Kids"),
    ("espresso_machine", "Dual Boiler Espresso Machine", "Kitchen Appliances", 40.0, "james_wilson", None),
    ("carry_on_suitcase", "Large Check-in Suitcase", "Travel Gear", 26.0, "emma_davis", None),
    ("quadcopter_drone", "Pro Drone with Gimbal", "Photography", 60.0, "lucas_martin", None),
    ("electronic_keyboard", "Stage Keyboard 88 Keys", "Musical Instruments", 45.0, "david_chen", None),
    ("camping_tent", "Family Dome Tent", "Camping Gear", 32.0, "noah_brown", None),
    ("countertop_blender", "High-Speed Smoothie Blender", "Kitchen Appliances", 22.0, "meera_iyer", None),
    ("denim_jacket", "Leather Biker Jacket", "Clothing", 25.0, "sofia_rodriguez", "Women's"),
    ("board_game", "Compact Travel Games Set", "Toys & Games", 8.0, "meera_iyer", None),
    ("smart_watch", "Premium Smartwatch", "Electronics", 28.0, "david_chen", None),
    ("sleeping_bag", "Winter Sleeping Bag", "Camping Gear", 24.0, "lucas_martin", None),
    ("violin", "Intermediate Violin with Bow", "Musical Instruments", 30.0, "ananya_rao", None),
    ("kids_scooter", "Deluxe Kids Scooter", "Baby & Kids", 15.0, "fatima_khan", "Kids"),
    ("cast_iron_skillet", "Enamelled Cast Iron Pot", "Kitchen Appliances", 16.0, "james_wilson", None),
    ("dumbbell", "Adjustable Barbell Set (30kg)", "Fitness", 22.0, "noah_brown", None),
    ("wireless_headphones", "Studio Reference Headphones", "Electronics", 26.0, "james_wilson", None),
    ("dslr_camera", "Vintage Film Camera", "Photography", 20.0, "alex_morgan", None),
    ("folding_ladder", "Extension Ladder (12 ft)", "Home & Tools", 18.0, "noah_brown", None),
    ("perfume", "Woody Eau de Parfum (100ml)", "Makeup", 18.0, "sofia_rodriguez", "Women's"),
    ("electric_shaver", "Premium Rotary Shaver", "Self Care", 20.0, "rahul_verma", "Men's"),
    ("interior_paint", "Exterior Paint (10L)", "Home & Garden", 24.0, "rahul_verma", None),
    ("python_cookbook", "Machine Learning Handbook", "Books", 11.0, "alex_morgan", None),
    ("camera_tripod", "Carbon Fibre Travel Tripod", "Photography", 22.0, "lucas_martin", None),
    ("carry_on_suitcase", "Weekender Duffle Bag", "Travel Gear", 14.0, "emma_davis", None),
    ("board_game", "Puzzle & Quiz Night Box", "Gaming", 10.0, "priya_sharma", None),
]

# username -> list of available product titles currently in the shopping cart
CART_PLAN = {
    "alex_morgan": ["Python Cookbook (3rd Ed.)", "Ceramic Plant Pot Set"],
    "priya_sharma": ["Matte Lipstick Set", "Canvas Sneakers — Unisex 41"],
    "meera_iyer": ["Hydrating Skincare Serum", "Countertop Blender 600W"],
    "sofia_rodriguez": ["Vintage Denim Jacket — Size L"],
    "ananya_rao": ["Student Violin 4/4 with Bow", "Everyday Lip Balm Trio"],
    "fatima_khan": ["Graphic Cotton Tee — Kids", "Non-Slip Yoga Mat"],
    "SMA": ["Cordless Drill Set 18V", "Portable Bluetooth Speaker"],
    "MDG": ["Carry-On Suitcase (Cabin Size)"],
}

# (borrower username, rented product titles, days ago)
ORDER_PLAN = [
    ("priya_sharma", ["Mirrorless Camera Kit"], 212),
    ("alex_morgan", ["4-Season Mountain Tent", "Semi-Acoustic Guitar"], 198),
    ("meera_iyer", ["Designer Leather Tote"], 184),
    ("rahul_verma", ["Trail Running Shoes"], 171),
    ("sofia_rodriguez", ["Travel Stroller", "Dual Boiler Espresso Machine"], 160),
    ("SMA", ["Large Check-in Suitcase"], 149),
    ("ananya_rao", ["Pro Drone with Gimbal", "Stage Keyboard 88 Keys"], 137),
    ("fatima_khan", ["Family Dome Tent"], 126),
    ("james_wilson", ["High-Speed Smoothie Blender"], 115),
    ("david_chen", ["Leather Biker Jacket", "Compact Travel Games Set"], 104),
    ("emma_davis", ["Premium Smartwatch"], 93),
    ("noah_brown", ["Winter Sleeping Bag", "Intermediate Violin with Bow"], 82),
    ("lucas_martin", ["Deluxe Kids Scooter"], 74),
    ("MDG", ["Enamelled Cast Iron Pot"], 65),
    ("priya_sharma", ["Adjustable Barbell Set (30kg)", "Studio Reference Headphones"], 54),
    ("priya_sharma", ["Vintage Film Camera"], 45),
    ("sofia_rodriguez", ["Extension Ladder (12 ft)", "Woody Eau de Parfum (100ml)"], 36),
    ("meera_iyer", ["Premium Rotary Shaver", "Exterior Paint (10L)"], 27),
    ("alex_morgan", ["Machine Learning Handbook", "Carbon Fibre Travel Tripod"], 18),
    ("fatima_khan", ["Weekender Duffle Bag", "Puzzle & Quiz Night Box"], 9),
]


def description_for(title, category, index):
    template = CATEGORY_DESCRIPTIONS.get(category, CATEGORY_DESCRIPTIONS["default"])
    text = template.format(title=title, title_low=title.lower())
    extras = [
        "Pickup can be arranged at a mutually convenient time.",
        "Happy to answer any questions before you confirm the rental.",
        "Please handle with care and return it in the condition shown.",
    ]
    return f"{text} {extras[index % len(extras)]}"


def insert_product(c, spec, index, available, now):
    stem, title, category, price, lender, audience = spec
    lender_row = c.execute("SELECT id FROM users WHERE username = ?", (lender,)).fetchone()
    if lender_row is None:
        raise ValueError(f"Unknown lender '{lender}' for product '{title}'")

    is_specific = int(bool(audience))
    target_gender = audience or NEUTRAL
    if is_specific:
        note = f"Curated demo data — suggested audience: {target_gender}"
    else:
        note = "Curated demo data — gender neutral"

    is_consumable = int(category in CONSUMABLE_CATEGORIES)
    mfg = "2026-01-15" if is_consumable else ""
    exp = "2028-01-15" if is_consumable else ""

    if index % 4 == 0:
        usage_status, usage_duration, purchase_date = "Unused/New", "", "2026-04-12"
    else:
        usage_status = "Used"
        usage_duration = f"Used {index % 5 + 1} times over {index % 6 + 2} months"
        purchase_date = ""

    reason = RENT_REASONS[index % len(RENT_REASONS)]
    photos = sample_photos(stem)
    if len(photos) != 3:
        raise ValueError(f"Expected 3 images for '{stem}', found {len(photos)}")

    c.execute(
        """INSERT INTO products
           (lender_id, title, description, category, rent_price, photos,
            is_consumable, mfg_date, exp_date, rent_reason, usage_status,
            usage_duration, purchase_date, is_gender_specific, target_gender,
            ai_classification_note, is_available, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            lender_row["id"],
            title,
            description_for(title, category, index),
            category,
            price,
            json.dumps(photos),
            is_consumable,
            mfg,
            exp,
            reason,
            usage_status,
            usage_duration,
            purchase_date,
            is_specific,
            target_gender,
            note,
            int(available),
            now,
        ),
    )
    return c.lastrowid


def address_rows_for(c, username):
    if username in ADMIN_CONTACTS:
        return c.execute(
            """SELECT ua.* FROM user_addresses ua
               JOIN users u ON ua.user_id = u.id
               WHERE u.username = ? ORDER BY ua.is_default DESC, ua.id ASC""",
            (username,),
        ).fetchall()
    return c.execute(
        """SELECT ua.* FROM user_addresses ua
           JOIN users u ON ua.user_id = u.id
           WHERE u.username = ? ORDER BY ua.is_default DESC, ua.id ASC""",
        (username,),
    ).fetchall()


def seed():
    passwords = load_demo_passwords()
    missing = [u[0] for u in DEMO_USERS if u[0] not in passwords]
    if missing:
        raise RuntimeError(
            f"Missing demo passwords in .streamlit/secrets.toml [demo_users]: {missing}"
        )

    # Rebuild the demo dataset from a clean slate.
    conn = v9.get_db()
    c = conn.cursor()
    for table in (
        "order_items", "orders", "shopping_list", "user_addresses",
        "products", "categories", "users",
    ):
        c.execute(f"DELETE FROM {table}")
    c.execute(
        "DELETE FROM sqlite_sequence WHERE name IN "
        "('users','user_addresses','categories','products','shopping_list','orders','order_items')"
    )
    conn.commit()
    conn.close()

    # Recreate admins, settings and starter categories (fees are overwritten below).
    v9.init_db()

    conn = v9.get_db()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Users ---
    user_ids = {}
    for username, full_name, email, phone, city, postal, _is_lender, house, street in DEMO_USERS:
        primary_address = f"House No. {house}, {street}, {city}, {postal}"
        c.execute(
            """INSERT INTO users (username, password, email, address, phone, is_admin)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (username, v9.hash_pw(passwords[username]), email, primary_address, phone),
        )
        user_ids[username] = c.lastrowid

    for admin_username, (full_name, email, phone, house, street, city, postal) in ADMIN_CONTACTS.items():
        c.execute(
            """UPDATE users SET email = ?, address = ?, phone = ? WHERE username = ?""",
            (email, f"House No. {house}, {street}, {city}, {postal}", phone, admin_username),
        )
        user_ids[admin_username] = c.execute(
            "SELECT id FROM users WHERE username = ?", (admin_username,)
        ).fetchone()["id"]

    # --- Address books (2-3 per regular user, 1 per admin) ---
    address_count = 0
    for index, (username, full_name, email, phone, city, postal, _is_lender, house, street) in enumerate(DEMO_USERS):
        addresses = [
            (full_name, house, street, "Near Central Metro Station", city, postal, phone, "Home", 1),
        ]
        office_house, office_street, office_landmark = OFFICE_SPOTS[index % len(OFFICE_SPOTS)]
        addresses.append(
            (full_name, office_house, office_street, office_landmark, city, postal, phone, "Office", 0)
        )
        if index % 3 == 0:
            other_house, other_street, other_landmark = OTHER_SPOTS[(index // 3) % len(OTHER_SPOTS)]
            other_city, other_postal = (
                ("Shelbyville", "IL 62565")
                if city == "Springfield"
                else ("Springfield", "IL 62701")
            )
            addresses.append(
                (full_name, other_house, other_street, other_landmark, other_city, other_postal, phone, "Other", 0)
            )
        for recipient, h_no, st, landmark, cty, pstl, phn, label, is_default in addresses:
            custom_lbl = (
                CUSTOM_OTHER_LABELS[(index // 3) % len(CUSTOM_OTHER_LABELS)]
                if label == "Other"
                else ""
            )
            c.execute(
                """INSERT INTO user_addresses
                   (user_id, label, custom_label, recipient_name, house_no, street_address, landmark,
                    city, state_postal, phone, is_default, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_ids[username], label, custom_lbl, recipient, h_no, st, landmark, cty, pstl, phn, is_default, now),
            )
            address_count += 1

    for admin_username, (full_name, email, phone, house, street, city, postal) in ADMIN_CONTACTS.items():
        c.execute(
            """INSERT INTO user_addresses
               (user_id, label, custom_label, recipient_name, house_no, street_address, landmark,
                city, state_postal, phone, is_default, created_at)
               VALUES (?, 'Office', '', ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (user_ids[admin_username], full_name, house, street, "Civic Center Plaza", city, postal, phone, now),
        )
        address_count += 1

    # --- Categories ---
    c.executemany(
        "INSERT OR REPLACE INTO categories (name, lender_fee, borrower_fee) VALUES (?, ?, ?)",
        CATEGORIES,
    )

    # --- Products ---
    available_ids = {}
    for idx, spec in enumerate(AVAILABLE_PRODUCTS):
        pid = insert_product(c, spec, idx, True, now)
        available_ids[spec[1]] = pid

    rented_ids = {}
    for idx, spec in enumerate(RENTED_PRODUCTS):
        pid = insert_product(c, spec, idx + len(AVAILABLE_PRODUCTS), False, now)
        rented_ids[spec[1]] = pid

    # --- Shopping carts ---
    cart_count = 0
    for username, titles in CART_PLAN.items():
        for title in titles:
            if title not in available_ids:
                raise ValueError(f"Unknown cart product '{title}'")
            c.execute(
                "INSERT OR IGNORE INTO shopping_list (user_id, product_id, added_at) VALUES (?, ?, ?)",
                (user_ids[username], available_ids[title], now),
            )
            cart_count += 1

    # --- Orders with line items ---
    order_count = 0
    line_item_count = 0
    fee_by_category = {name: borrower_fee for name, _lender, borrower_fee in CATEGORIES}
    for borrower, titles, days_ago in ORDER_PLAN:
        if borrower not in user_ids:
            raise ValueError(f"Unknown order borrower '{borrower}'")
        addresses = address_rows_for(c, borrower)
        if not addresses:
            raise ValueError(f"No address for order borrower '{borrower}'")
        selected_address = v9.format_address_line(addresses[0])

        items = []
        for title in titles:
            if title not in rented_ids:
                raise ValueError(f"Unknown order product '{title}'")
            pid = rented_ids[title]
            row = c.execute(
                "SELECT title, category, rent_price, target_gender, is_gender_specific, lender_id "
                "FROM products WHERE id = ?",
                (pid,),
            ).fetchone()
            items.append((pid, row))

        subtotal = sum(fee_by_category.get(row["category"], 1.0) for _pid, row in items)
        is_lender = c.execute(
            "SELECT 1 FROM products WHERE lender_id = ? LIMIT 1", (user_ids[borrower],)
        ).fetchone() is not None
        discount_pct = 10.0 if is_lender else 0.0
        total_fee = round(subtotal * (1 - discount_pct / 100.0), 2)

        created_at = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        summary = ", ".join(row["title"] for _pid, row in items)
        c.execute(
            """INSERT INTO orders (borrower_id, total_fee, items_summary, selected_address, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_ids[borrower], total_fee, summary, selected_address, created_at),
        )
        order_id = c.lastrowid
        order_count += 1

        for pid, row in items:
            audience = row["target_gender"] if row["is_gender_specific"] else NEUTRAL
            c.execute(
                """INSERT INTO order_items
                   (order_id, product_id, product_title, category, target_gender,
                    rent_price, borrower_fee, lender_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id,
                    pid,
                    row["title"],
                    row["category"],
                    audience,
                    row["rent_price"],
                    fee_by_category.get(row["category"], 1.0),
                    row["lender_id"],
                ),
            )
            c.execute(
                "UPDATE products SET updated_at = ? WHERE id = ?", (created_at, pid)
            )
            line_item_count += 1

    conn.commit()

    # --- Summary ---
    counts = {
        table: c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "users", "user_addresses", "categories", "products",
            "shopping_list", "orders", "order_items",
        )
    }
    conn.close()

    print("v9 demo dataset rebuilt successfully:")
    for label, value in counts.items():
        print(f"  {label:18s} {value}")
    print(f"  available products  {len(AVAILABLE_PRODUCTS)}")
    print(f"  rented products     {len(RENTED_PRODUCTS)}")
    print(f"  products with 3 images: {len(AVAILABLE_PRODUCTS) + len(RENTED_PRODUCTS)}")
    print("\nTest logins (also stored in .streamlit/secrets.toml):")
    print("  admins: SMA / 12345678, MDG / 09876543")
    for user in DEMO_USERS:
        username = user[0]
        print(f"  {username:18s} {passwords[username]}")


if __name__ == "__main__":
    seed()
