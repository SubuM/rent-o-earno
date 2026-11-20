"""Extend the v9 demo dataset with extra categories, products, carts and orders.

This script does not duplicate the dataset generator: it imports seed_v9, registers
the new demo data, then calls the same rebuild routine. Running it is equivalent to
running a fuller ``seed_v9.py`` and is safe to repeat.

Run with:  python seed_v10.py
"""

import seed_v9 as base


# --------------------------------------------------------------------------- categories
# name, lender fee, borrower fee
NEW_CATEGORIES = [
    ("Jewelry & Watches", 2.5, 1.5),
    ("Bags & Backpacks", 2.0, 1.25),
    ("Art & Craft Supplies", 1.5, 0.75),
    ("Home Entertainment", 3.0, 2.0),
    ("Outdoor Recreation", 2.5, 1.5),
    ("Health & Wellness", 1.5, 1.0),
    ("Pet Care", 1.5, 1.0),
    ("Seasonal Decor", 1.0, 0.5),
]

NEW_CONSUMABLE_CATEGORIES = {"Health & Wellness"}

NEW_CATEGORY_DESCRIPTIONS = {
    "Jewelry & Watches": "{title_low} stored in a soft pouch and gently polished before listing. A versatile piece for everyday wear or a special occasion.",
    "Bags & Backpacks": "{title_low} from a careful owner. Straps, zips and compartments all checked, and the interior wiped clean before listing.",
    "Art & Craft Supplies": "{title_low} kept in a dry studio. All pieces present, lightly used at most, and packed neatly so it arrives ready to use.",
    "Home Entertainment": "{title_low} in full working order, factory reset where applicable, with cables and original packaging included.",
    "Outdoor Recreation": "{title_low} used on a few weekends outdoors, dried and cleaned after every trip, with no damage or missing parts.",
    "Health & Wellness": "{title_low} kept sealed in a cool, dry cabinet. Hygienic, unopened where applicable, and within its usable date.",
    "Pet Care": "{title_low} from a pet-friendly home. Washed, inspected and ready for a new furry friend to enjoy.",
    "Seasonal Decor": "{title_low} carefully packed after each season. Tested before listing and stored away from moisture.",
}


# --------------------------------------------------------------------------- products
# (image stem, title, category, rent price, lender username, audience or None)
NEW_AVAILABLE_PRODUCTS = [
    # Jewelry & Watches (gender-specific items: audience filter auto-enables in v9)
    ("pearl_necklace", "Pearl Strand Necklace", "Jewelry & Watches", 18.0, "priya_sharma", "Women's"),
    ("charm_bracelet", "Gold-Tone Charm Bracelet", "Jewelry & Watches", 12.0, "sofia_rodriguez", "Women's"),
    ("smart_watch", "Minimalist Smart Watch", "Jewelry & Watches", 16.0, "david_chen", "Unisex"),
    ("charm_bracelet", "Everyday Charm Bracelet", "Jewelry & Watches", 9.0, "ananya_rao", "Kids"),

    # Bags & Backpacks
    ("backpack", "Travel Backpack 30L", "Bags & Backpacks", 20.0, "emma_davis", "Unisex"),
    ("tote_bag", "Canvas Tote Bag", "Bags & Backpacks", 8.0, "ananya_rao", "Women's"),
    ("carry_on_suitcase", "Compact Laptop Bag", "Bags & Backpacks", 12.0, "noah_brown", None),

    # Art & Craft Supplies
    ("watercolor_set", "Watercolor Paint Set", "Art & Craft Supplies", 9.0, "meera_iyer", None),
    ("watercolor_set", "Kids Watercolor Kit", "Art & Craft Supplies", 6.0, "fatima_khan", "Kids"),
    ("wooden_blocks", "Craft Beads & Tools Kit", "Art & Craft Supplies", 7.0, "sofia_rodriguez", None),

    # Home Entertainment
    ("streaming_stick", "4K Streaming Stick", "Home Entertainment", 14.0, "james_wilson", None),
    ("bluetooth_speaker", "Party Bluetooth Speaker", "Home Entertainment", 16.0, "lucas_martin", None),
    ("portable_projector", "Mini Home Cinema Projector", "Home Entertainment", 24.0, "david_chen", None),

    # Outdoor Recreation
    ("binoculars", "8x42 Binoculars", "Outdoor Recreation", 22.0, "rahul_verma", None),
    ("camping_stove", "Portable Camp Stove", "Outdoor Recreation", 16.0, "lucas_martin", None),
    ("camp_chair", "Reclining Camp Chair", "Outdoor Recreation", 11.0, "noah_brown", None),

    # Health & Wellness (includes consumables with mfg/exp dates)
    ("essential_oil_kit", "Essential Oil Starter Kit", "Health & Wellness", 13.0, "fatima_khan", "Unisex"),
    ("first_aid_kit", "Compact First Aid Kit", "Health & Wellness", 7.0, "priya_sharma", None),
    ("yoga_mat", "Therapeutic Yoga Mat", "Health & Wellness", 10.0, "sofia_rodriguez", None),

    # Pet Care
    ("pet_carrier", "Soft-Sided Pet Carrier", "Pet Care", 18.0, "emma_davis", None),
    ("pet_brush", "Grooming Brush for Pets", "Pet Care", 6.0, "rahul_verma", None),

    # Seasonal Decor
    ("string_lights", "LED String Lights", "Seasonal Decor", 8.0, "meera_iyer", None),
    ("desk_lamp", "Decorative Table Lamp", "Seasonal Decor", 12.0, "james_wilson", None),
]

# Already-rented items used by the new orders below (is_available = 0).
NEW_RENTED_PRODUCTS = [
    ("pearl_necklace", "Vintage Pearl Necklace", "Jewelry & Watches", 24.0, "sofia_rodriguez", "Women's"),
    ("backpack", "Hiking Daypack 40L", "Bags & Backpacks", 26.0, "emma_davis", "Unisex"),
    ("tote_bag", "Structured Leather Tote", "Bags & Backpacks", 22.0, "priya_sharma", "Women's"),
    ("watercolor_set", "Professional Watercolor Set", "Art & Craft Supplies", 16.0, "ananya_rao", None),
    ("streaming_stick", "4K HDR Streaming Box", "Home Entertainment", 20.0, "james_wilson", None),
    ("binoculars", "Roof-Prism Binoculars", "Outdoor Recreation", 32.0, "rahul_verma", None),
    ("camping_stove", "Dual-Burner Camp Stove", "Outdoor Recreation", 28.0, "lucas_martin", None),
    ("essential_oil_kit", "Aromatherapy Oil Collection", "Health & Wellness", 18.0, "fatima_khan", "Unisex"),
    ("pet_carrier", "Rolling Pet Carrier", "Pet Care", 24.0, "emma_davis", None),
    ("string_lights", "Outdoor Fairy Lights", "Seasonal Decor", 12.0, "meera_iyer", None),
    ("pet_brush", "Professional Pet Grooming Kit", "Pet Care", 14.0, "rahul_verma", None),
    ("first_aid_kit", "Deluxe First Aid Kit", "Health & Wellness", 15.0, "priya_sharma", None),
]


# --------------------------------------------------------------------------- carts & orders
# Give the previously cart-less demo users some saved items too.
NEW_CART_PLAN = {
    "rahul_verma": ["8x42 Binoculars"],
    "james_wilson": ["4K Streaming Stick", "Decorative Table Lamp"],
    "david_chen": ["Mini Home Cinema Projector"],
    "lucas_martin": ["Portable Camp Stove"],
    "noah_brown": ["Reclining Camp Chair", "Compact Laptop Bag"],
    "emma_davis": ["Travel Backpack 30L"],
}

# (borrower username, rented product titles, days ago)
NEW_ORDER_PLAN = [
    ("alex_morgan", ["Vintage Pearl Necklace"], 6),
    ("david_chen", ["Hiking Daypack 40L"], 5),
    ("meera_iyer", ["Structured Leather Tote"], 4),
    ("ananya_rao", ["Professional Watercolor Set"], 4),
    ("lucas_martin", ["4K HDR Streaming Box"], 3),
    ("sofia_rodriguez", ["Roof-Prism Binoculars"], 3),
    ("noah_brown", ["Dual-Burner Camp Stove"], 2),
    ("fatima_khan", ["Aromatherapy Oil Collection"], 2),
    ("emma_davis", ["Rolling Pet Carrier"], 1),
    ("priya_sharma", ["Outdoor Fairy Lights"], 1),
    ("james_wilson", ["Professional Pet Grooming Kit", "Deluxe First Aid Kit"], 1),
]


def seed():
    """Register the extended demo data, then rebuild the database using seed_v9."""
    base.CATEGORIES.extend(NEW_CATEGORIES)
    base.CATEGORY_DESCRIPTIONS.update(NEW_CATEGORY_DESCRIPTIONS)
    base.CONSUMABLE_CATEGORIES.update(NEW_CONSUMABLE_CATEGORIES)
    base.AVAILABLE_PRODUCTS.extend(NEW_AVAILABLE_PRODUCTS)
    base.RENTED_PRODUCTS.extend(NEW_RENTED_PRODUCTS)
    base.CART_PLAN.update(NEW_CART_PLAN)
    base.ORDER_PLAN.extend(NEW_ORDER_PLAN)

    base.seed()

    print(
        f"Added {len(NEW_CATEGORIES)} categories, "
        f"{len(NEW_AVAILABLE_PRODUCTS)} available products, "
        f"{len(NEW_RENTED_PRODUCTS)} rented products, "
        f"{sum(len(v) for v in NEW_CART_PLAN.values())} cart items and "
        f"{len(NEW_ORDER_PLAN)} orders to the v9 demo dataset."
    )


if __name__ == "__main__":
    seed()
