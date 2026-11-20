import streamlit as st
import sqlite3
import hashlib
import os
import re
from datetime import datetime
import json

try:
    from transformers import pipeline as hf_pipeline
except ImportError:
    hf_pipeline = None

# --- Configuration & Directories ---
DB_NAME = "rental_app.db"
UPLOAD_DIR = "uploads"
MODEL_DIR = os.path.join("models", "xtremedistil-gender-nli")
TINY_MODEL_ID = "MoritzLaurer/xtremedistil-l6-h256-mnli-fever-anli-ling-binary"

GENDER_OPTIONS = ["Women's", "Men's", "Kids", "Unisex"]
GENDER_NEUTRAL_LABEL = "Gender Neutral"

# Domain hints used alongside the zero-shot model for high accuracy on edge cases
GENDER_SPECIFIC_KEYWORDS = {
    "cloth", "clothing", "apparel", "shirt", "t-shirt", "dress", "skirt", "jeans",
    "trouser", "pant", "jacket", "coat", "sweater", "hoodie", "suit", "saree",
    "kurta", "legging", "shorts", "blouse", "ethnic", "wear", "outfit",
    "makeup", "cosmetic", "lipstick", "foundation", "mascara", "eyeliner",
    "blush", "concealer", "eyeshadow", "perfume", "cologne", "fragrance",
    "skincare", "self care", "self-care", "grooming", "shampoo", "conditioner",
    "lotion", "serum", "razor", "trimmer", "nail polish",
    "shoe", "shoes", "sneaker", "boot", "heel", "heels", "sandal", "loafer",
    "slipper", "footwear", "flats",
    "fashion", "accessory", "accessories", "handbag", "purse", "wallet",
    "watch", "jewelry", "jewellery", "necklace", "earring", "bracelet", "ring",
    "belt", "sunglasses", "hat", "cap", "scarf", "tie", "clutch", "backpack",
    "men", "mens", "men's", "women", "womens", "women's", "ladies", "gents",
    "kids", "kid", "children", "child", "toddler", "baby", "boy", "boys", "girl", "girls"
}

GENDER_NEUTRAL_KEYWORDS = {
    "laptop", "camera", "tripod", "drill", "hammer", "wrench", "tent", "projector",
    "speaker", "monitor", "keyboard", "mouse", "router", "cable", "charger",
    "furniture", "chair", "table", "lamp", "book", "board game", "puzzle",
    "kitchen", "blender", "toaster", "microwave", "vacuum", "ladder", "toolbox"
}


def _ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)


# --- Database Initialization & Migration ---
def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor, table_name, column_name, column_definition):
    existing_cols = [
        row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]
    if column_name not in existing_cols:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _get_admin_credentials():
    """Return all admin (username, password) pairs from secrets.

    v3 supports multiple admins via a [[admins]] array in .streamlit/secrets.toml.
    A single [admin] section and environment variables remain as fallbacks.
    """
    admins = []
    try:
        for entry in st.secrets.get("admins", []):
            username = entry.get("username")
            password = entry.get("password")
            if username and password:
                admins.append((username, password))
    except Exception:
        pass
    if admins:
        return admins

    try:
        return [(st.secrets["admin"]["username"], st.secrets["admin"]["password"])]
    except Exception:
        pass

    return [
        (
            os.environ.get("RENTIT_ADMIN_USER", "admin"),
            os.environ.get("RENTIT_ADMIN_PASS", "admin123"),
        )
    ]


def init_db():
    _ensure_dirs()
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        address TEXT,
        phone TEXT,
        is_admin BOOLEAN DEFAULT 0
    )''')

    # Settings/Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        lender_fee REAL,
        borrower_fee REAL
    )''')

    # General Settings (Loyalty Discount)
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lender_id INTEGER,
        title TEXT,
        description TEXT,
        category TEXT,
        rent_price REAL,
        photos TEXT,
        is_consumable BOOLEAN,
        mfg_date TEXT,
        exp_date TEXT,
        rent_reason TEXT,
        usage_status TEXT,
        usage_duration TEXT,
        purchase_date TEXT,
        is_gender_specific BOOLEAN DEFAULT 0,
        target_gender TEXT DEFAULT 'Gender Neutral',
        ai_classification_note TEXT DEFAULT '',
        is_available BOOLEAN DEFAULT 1,
        updated_at DATETIME,
        FOREIGN KEY(lender_id) REFERENCES users(id)
    )''')

    # Safe schema migration for existing v1 databases
    _ensure_column(c, "products", "is_gender_specific", "BOOLEAN DEFAULT 0")
    _ensure_column(c, "products", "target_gender", "TEXT DEFAULT 'Gender Neutral'")
    _ensure_column(c, "products", "ai_classification_note", "TEXT DEFAULT ''")

    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrower_id INTEGER,
        total_fee REAL,
        created_at DATETIME,
        FOREIGN KEY(borrower_id) REFERENCES users(id)
    )''')

    # Default Admin(s) & Settings. Secrets are authoritative: changing a password
    # in secrets.toml is applied to the matching admin on the next app start.
    for admin_username, admin_password in _get_admin_credentials():
        hashed = hash_pw(admin_password)
        existing = c.execute(
            "SELECT password FROM users WHERE username = ?", (admin_username,)
        ).fetchone()
        if existing is None:
            c.execute(
                "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
                (admin_username, hashed),
            )
        elif existing["password"] != hashed:
            c.execute(
                "UPDATE users SET password = ?, is_admin = 1 WHERE username = ?",
                (hashed, admin_username),
            )
    c.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        ("loyalty_discount_pct", "10.0"),
    )

    # Seed starter categories only if table is completely empty
    cat_count = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if cat_count == 0:
        starter_categories = [
            ("Clothing", 2.0, 1.5),
            ("Fashion Accessories", 1.5, 1.0),
            ("Shoes", 2.0, 1.5),
            ("Makeup", 1.5, 1.0),
            ("Self Care", 1.5, 1.0),
            ("Toys & Games", 1.0, 1.0),
            ("Electronics", 3.0, 2.5),
            ("Home & Tools", 2.0, 1.5),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO categories (name, lender_fee, borrower_fee) VALUES (?, ?, ?)",
            starter_categories,
        )

    conn.commit()
    conn.close()


# --- Tiny Local NLP Model for Gender Classification ---
@st.cache_resource(show_spinner="Downloading & loading tiny gender-classification model (first run only)...")
def load_gender_classifier():
    """Loads the ~50MB distilled zero-shot NLI model locally on CPU."""
    if hf_pipeline is None:
        return None
    try:
        has_local_weights = any(
            fname.endswith((".bin", ".safetensors"))
            for fname in os.listdir(MODEL_DIR)
        )
        source = MODEL_DIR if has_local_weights else TINY_MODEL_ID
        clf = hf_pipeline(
            "zero-shot-classification",
            model=source,
            tokenizer=source,
            device=-1,  # CPU execution for EC2 Micro / Raspberry Pi 4B
        )
        if not has_local_weights:
            clf.save_pretrained(MODEL_DIR)
        return clf
    except Exception:
        return None


def _keyword_gender_hints(text_lower):
    tokens = set(re.findall(r"[a-z']+", text_lower))
    specific_hits = any(
        kw in text_lower if " " in kw else kw in tokens
        for kw in GENDER_SPECIFIC_KEYWORDS
    )
    neutral_hits = any(
        kw in text_lower if " " in kw else kw in tokens
        for kw in GENDER_NEUTRAL_KEYWORDS
    )

    suggested = None
    if any(w in tokens for w in ("women", "womens", "women's", "ladies", "female", "girl", "girls", "lipstick", "mascara", "dress", "saree", "blouse", "heels")):
        suggested = "Women's"
    elif any(w in tokens for w in ("men", "mens", "men's", "male", "gents", "boy", "boys", "beard", "necktie")):
        suggested = "Men's"
    elif any(w in tokens for w in ("kid", "kids", "child", "children", "toddler", "baby", "infant")):
        suggested = "Kids"
    elif "unisex" in tokens:
        suggested = "Unisex"

    return specific_hits, neutral_hits, suggested


@st.cache_data(show_spinner=False)
def classify_product_gender(category, title, description):
    """
    Determines whether a product is gender-specific or gender-neutral,
    and suggests Men's / Women's / Kids / Unisex when gender-specific.
    Returns: (is_gender_specific: bool, suggested_gender: str, note: str)
    """
    clean_cat = (category or "").strip()
    clean_title = (title or "").strip()
    clean_desc = (description or "").strip()

    combined_text = (
        f"Category: {clean_cat}. Product: {clean_title}. Details: {clean_desc}"
    )
    text_lower = combined_text.lower()
    specific_hint, neutral_hint, lexical_gender = _keyword_gender_hints(text_lower)

    clf = load_gender_classifier()
    if clf is not None:
        try:
            hypotheses = [
                "a personal wearable, clothing, footwear, makeup, cosmetic, fashion accessory, or self-care product tailored by gender or age group",
                "a gender-neutral general object such as electronics, tools, furniture, appliances, or household equipment",
            ]
            res = clf(
                combined_text,
                candidate_labels=hypotheses,
                hypothesis_template="This listing describes {}.",
            )
            top_label = res["labels"][0]
            top_score = float(res["scores"][0])
            specific_score = (
                top_score
                if top_label == hypotheses[0]
                else float(res["scores"][1])
            )

            # Blend model probability with explicit domain cues
            if specific_hint and not neutral_hint:
                specific_score = max(specific_score, 0.85)
            elif neutral_hint and not specific_hint and not clean_title:
                specific_score = min(specific_score, 0.25)

            is_specific = specific_score >= 0.50

            if not is_specific:
                neutral_conf = (1.0 - specific_score) * 100
                return (
                    False,
                    GENDER_NEUTRAL_LABEL,
                    f"Gender-neutral product ({neutral_conf:.0f}% confidence)",
                )

            # Stage 2: Infer suggested target audience
            if lexical_gender:
                suggested = lexical_gender
                audience_conf = max(specific_score * 100, 88.0)
            else:
                audience_labels = [
                    "Women's product",
                    "Men's product",
                    "Kids or children's product",
                    "Unisex product suitable for everyone",
                ]
                aud_res = clf(
                    combined_text,
                    candidate_labels=audience_labels,
                    hypothesis_template="This item is intended as a {}.",
                )
                label_map = {
                    "Women's product": "Women's",
                    "Men's product": "Men's",
                    "Kids or children's product": "Kids",
                    "Unisex product suitable for everyone": "Unisex",
                }
                suggested = label_map.get(aud_res["labels"][0], "Unisex")
                audience_conf = float(aud_res["scores"][0]) * 100

            return (
                True,
                suggested,
                f"Gender-specific product ({specific_score * 100:.0f}% confidence) — Suggested: {suggested} ({audience_conf:.0f}%)",
            )
        except Exception:
            pass

    # Fallback deterministic classifier if transformer model is unavailable
    if specific_hint and not neutral_hint:
        suggested = lexical_gender or "Unisex"
        return (
            True,
            suggested,
            f"Gender-specific product (rule-based) — Suggested: {suggested}",
        )
    return (
        False,
        GENDER_NEUTRAL_LABEL,
        "Gender-neutral product (rule-based)",
    )


# --- Authentication Helpers ---
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_user(username, password):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hash_pw(password)),
    ).fetchone()
    conn.close()
    return user


def is_lender(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM products WHERE lender_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count > 0


# --- File Upload Helper ---
def save_uploaded_files(uploaded_files):
    _ensure_dirs()
    file_paths = []
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    for idx, f in enumerate(uploaded_files):
        safe_name = f"{stamp}_{idx}_{os.path.basename(f.name)}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        with open(file_path, "wb") as f_out:
            f_out.write(f.getbuffer())
        file_paths.append(file_path)
    return json.dumps(file_paths)


# --- Views ---
def auth_view():
    st.title("Welcome to RentItApp")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state["user"] = dict(user)
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        st.subheader("Register")
        with st.form("register_form"):
            new_user = st.text_input("Username")
            new_pw = st.text_input("Password", type="password")
            email = st.text_input("Email")
            address = st.text_area("Address")
            phone = st.text_input("Phone Number")
            if st.form_submit_button("Register"):
                if not new_user.strip() or not new_pw.strip():
                    st.error("Username and password are required.")
                else:
                    conn = get_db()
                    try:
                        conn.execute(
                            "INSERT INTO users (username, password, email, address, phone) VALUES (?, ?, ?, ?, ?)",
                            (new_user.strip(), hash_pw(new_pw), email, address, phone),
                        )
                        conn.commit()
                        st.success("Registration successful! Please login.")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists.")
                    finally:
                        conn.close()


def admin_portal():
    st.title("Admin Portal")
    conn = get_db()

    st.subheader("Manage Categories & Fees")
    existing_cats = conn.execute(
        "SELECT name AS Category, lender_fee AS 'Lender Fee ($)', borrower_fee AS 'Borrower Fee ($)' FROM categories ORDER BY name"
    ).fetchall()
    if existing_cats:
        st.dataframe([dict(row) for row in existing_cats], width="stretch", hide_index=True)

    with st.form("add_category_form"):
        cat_name = st.text_input("Category Name")
        lender_fee = st.number_input("Lender Convenience Fee ($)", min_value=0.0, step=0.5)
        borrower_fee = st.number_input("Borrower Convenience Fee ($)", min_value=0.0, step=0.5)
        if st.form_submit_button("Add/Update Category"):
            if not cat_name.strip():
                st.error("Category name cannot be empty.")
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO categories (name, lender_fee, borrower_fee) VALUES (?, ?, ?)",
                    (cat_name.strip(), lender_fee, borrower_fee),
                )
                conn.commit()
                st.success(f"Category '{cat_name.strip()}' saved.")
                st.rerun()

    st.subheader("Manage Global Discounts")
    current_discount = conn.execute(
        "SELECT value FROM settings WHERE key = 'loyalty_discount_pct'"
    ).fetchone()[0]
    with st.form("discount_form"):
        new_discount = st.number_input(
            "Loyalty Discount (%) for Lender-Borrowers",
            value=float(current_discount),
            min_value=0.0,
            max_value=100.0,
        )
        if st.form_submit_button("Update Discount"):
            conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'loyalty_discount_pct'",
                (str(new_discount),),
            )
            conn.commit()
            st.success("Discount updated.")
    conn.close()


def lender_portal():
    st.title("Lender Portal")
    st.write("List your extra items for rent.")

    conn = get_db()
    categories = [
        row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    ]

    if not categories:
        st.warning("No categories available. Please ask an admin to add categories.")
        conn.close()
        return

    # Reactive product inputs so the tiny AI model evaluates gender specificity live
    col_left, col_right = st.columns([2, 1])
    with col_left:
        title = st.text_input("Product Title", key="lender_title")
        category = st.selectbox("Category", categories, key="lender_category")
        desc = st.text_area("A few lines about the product", key="lender_desc")

    # Run tiny local classifier on the entered product details
    is_gender_specific, suggested_gender, ai_note = classify_product_gender(
        category, title, desc
    )

    with col_right:
        st.markdown("#### AI Audience Classification")
        if is_gender_specific:
            st.info(f"**Gender-Specific Item Detected**\n\n{ai_note}")
            default_idx = (
                GENDER_OPTIONS.index(suggested_gender)
                if suggested_gender in GENDER_OPTIONS
                else 0
            )
            selected_target_gender = st.selectbox(
                "Assign Target Gender / Audience",
                options=GENDER_OPTIONS,
                index=default_idx,
                key=f"lender_target_gender_{category}_{suggested_gender}",
                help="Automatically enabled because this product/category is gender-specific.",
            )
        else:
            st.success(f"**Gender-Neutral Item Detected**\n\n{ai_note}")
            st.selectbox(
                "Assign Target Gender / Audience",
                options=[GENDER_NEUTRAL_LABEL],
                index=0,
                disabled=True,
                key="lender_target_gender_neutral",
                help="Disabled because the model identified this product as gender-neutral.",
            )
            selected_target_gender = GENDER_NEUTRAL_LABEL

    st.divider()

    rent_price = st.number_input("Rental Price ($)", min_value=0.0, step=1.0, key="lender_price")
    reason = st.text_input("Reason for renting out", key="lender_reason")

    photos = st.file_uploader(
        "Upload Photos (Minimum 3 required)",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="lender_photos",
    )

    c1, c2 = st.columns(2)
    with c1:
        is_consumable = st.checkbox("Is this a consumable product?", key="lender_consumable")
        mfg_date = st.date_input(
            "Manufacturing Date", disabled=not is_consumable, key="lender_mfg"
        )
        exp_date = st.date_input(
            "Expiry Date", disabled=not is_consumable, key="lender_exp"
        )
    with c2:
        usage_status = st.radio("Condition", ["Used", "Unused/New"], key="lender_condition")
        usage_duration = st.text_input(
            "Usage Duration (if used)",
            disabled=(usage_status == "Unused/New"),
            key="lender_duration",
        )
        purchase_date = st.date_input(
            "Purchase Date (if new)",
            disabled=(usage_status == "Used"),
            key="lender_purchase",
        )

    if st.button("List Product & Pay Lender Fee", type="primary"):
        if not photos or len(photos) < 3:
            st.error("You must upload at least 3 photos.")
        elif not title.strip() or not desc.strip():
            st.error("Title and Description are required.")
        elif usage_status == "Used" and not usage_duration.strip():
            st.error("Please specify the usage duration for a used product.")
        else:
            lender_fee = conn.execute(
                "SELECT lender_fee FROM categories WHERE name = ?", (category,)
            ).fetchone()[0]

            # Mock Payment
            st.success(f"Mock Payment Processed: ${lender_fee:.2f} convenience fee paid.")

            photo_paths = save_uploaded_files(photos)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            stored_duration = usage_duration.strip() if usage_status == "Used" else ""
            stored_purchase = str(purchase_date) if usage_status == "Unused/New" else ""
            stored_mfg = str(mfg_date) if is_consumable else ""
            stored_exp = str(exp_date) if is_consumable else ""

            conn.execute(
                '''INSERT INTO products
                (lender_id, title, description, category, rent_price, photos, is_consumable,
                 mfg_date, exp_date, rent_reason, usage_status, usage_duration, purchase_date,
                 is_gender_specific, target_gender, ai_classification_note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    st.session_state["user"]["id"],
                    title.strip(),
                    desc.strip(),
                    category,
                    rent_price,
                    photo_paths,
                    is_consumable,
                    stored_mfg,
                    stored_exp,
                    reason.strip(),
                    usage_status,
                    stored_duration,
                    stored_purchase,
                    int(is_gender_specific),
                    selected_target_gender,
                    ai_note,
                    now,
                ),
            )
            conn.commit()
            st.success("Product successfully listed for rent!")

    conn.close()


def borrower_portal():
    st.title("Borrower Portal")
    conn = get_db()

    if "cart" not in st.session_state:
        st.session_state["cart"] = []

    if st.session_state.get("last_checkout_emails"):
        st.info(
            "📨 **MOCK EMAIL SENT TO YOU:**\n\n"
            + "\n\n---\n\n".join(st.session_state.pop("last_checkout_emails"))
        )

    # --- Sidebar Filters ---
    st.sidebar.subheader("Filters")
    categories = ["All"] + [
        row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    ]
    selected_cat = st.sidebar.selectbox("Category", categories)
    search_term = st.sidebar.text_input("Search")

    # Enable gender filter by default when "All" categories is selected,
    # or when a specific category has gender-specific items/keywords.
    if selected_cat == "All":
        enable_gender_filter = True
    else:
        gender_specific_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE is_available = 1 AND is_gender_specific = 1 AND category = ?",
            (selected_cat,),
        ).fetchone()[0]
        cat_hint_specific, _, _ = _keyword_gender_hints(selected_cat.lower())
        enable_gender_filter = (gender_specific_count > 0) or cat_hint_specific

    if enable_gender_filter:
        selected_gender_filter = st.sidebar.selectbox(
            "Gender / Audience",
            options=["All"] + GENDER_OPTIONS,
            key=f"gender_filter_{selected_cat}",
            help="Filter gender-specific items (clothing, footwear, makeup, accessories, self-care) by target audience.",
        )
    else:
        st.sidebar.selectbox(
            "Gender / Audience",
            options=["Not Applicable (Gender Neutral)"],
            disabled=True,
            key=f"gender_filter_disabled_{selected_cat}",
            help="Enabled automatically when browsing 'All' or gender-specific categories.",
        )
        selected_gender_filter = "All"

    # Dynamic min/max price bounds for the selected category (or all categories)
    bounds_query = (
        "SELECT MIN(rent_price) AS min_price, MAX(rent_price) AS max_price "
        "FROM products WHERE is_available = 1"
    )
    bounds_params = []
    if selected_cat != "All":
        bounds_query += " AND category = ?"
        bounds_params.append(selected_cat)

    price_bounds = conn.execute(bounds_query, bounds_params).fetchone()
    min_price = price_bounds["min_price"]
    max_price = price_bounds["max_price"]

    selected_price_range = None
    if min_price is not None and max_price is not None:
        min_p = float(min_price)
        max_p = float(max_price)
        if min_p < max_p:
            selected_price_range = st.sidebar.slider(
                "Price Range ($)",
                min_value=min_p,
                max_value=max_p,
                value=(min_p, max_p),
                key=f"price_slider_{selected_cat}",
            )
        else:
            st.sidebar.caption(f"Price Range: ${min_p:.2f} (single price in selection)")
            selected_price_range = (min_p, max_p)

    sort_by = st.sidebar.selectbox(
        "Sort By",
        ["Last Updated (Default)", "Price: Low to High", "Price: High to Low"],
    )

    # --- Query Building ---
    query = (
        "SELECT p.*, c.borrower_fee FROM products p "
        "JOIN categories c ON p.category = c.name WHERE p.is_available = 1"
    )
    params = []

    if selected_cat != "All":
        query += " AND p.category = ?"
        params.append(selected_cat)
    if enable_gender_filter and selected_gender_filter != "All":
        query += " AND p.target_gender = ?"
        params.append(selected_gender_filter)
    if selected_price_range is not None:
        query += " AND p.rent_price >= ? AND p.rent_price <= ?"
        params.extend([selected_price_range[0], selected_price_range[1]])
    if search_term:
        query += " AND (p.title LIKE ? OR p.description LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])

    if sort_by == "Price: Low to High":
        query += " ORDER BY p.rent_price ASC"
    elif sort_by == "Price: High to Low":
        query += " ORDER BY p.rent_price DESC"
    else:
        query += " ORDER BY p.updated_at DESC"

    products = conn.execute(query, params).fetchall()

    # --- Display Products ---
    if not products:
        st.info("No products available matching your criteria.")

    for p in products:
        with st.container():
            col1, col2 = st.columns([1, 3])
            photos = json.loads(p["photos"]) if p["photos"] else []
            with col1:
                if photos:
                    st.image(photos[0], width="stretch")
                    if len(photos) > 1:
                        with st.expander(f"More photos ({len(photos) - 1})"):
                            for extra_photo in photos[1:]:
                                st.image(extra_photo, width="stretch")
            with col2:
                st.subheader(p["title"])
                is_spec = bool(p["is_gender_specific"])
                audience_badge = (
                    p["target_gender"] if is_spec else GENDER_NEUTRAL_LABEL
                )
                st.write(
                    f"**Price:** ${p['rent_price']:.2f} | **Category:** {p['category']} | **Audience:** {audience_badge}"
                )

                # Condition and Usage Duration / Purchase Date
                if p["usage_status"] == "Used":
                    duration_display = (
                        p["usage_duration"] if p["usage_duration"] else "Not specified"
                    )
                    st.write(
                        f"**Condition:** Used | **Usage Duration:** {duration_display}"
                    )
                else:
                    purchase_display = (
                        p["purchase_date"] if p["purchase_date"] else "Not specified"
                    )
                    st.write(
                        f"**Condition:** Unused/New | **Purchase Date:** {purchase_display}"
                    )

                # Consumable dates if applicable
                if p["is_consumable"]:
                    st.write(
                        f"**Consumable:** Yes | **Mfg Date:** {p['mfg_date']} | **Expiry Date:** {p['exp_date']}"
                    )

                # Reason for renting out
                if p["rent_reason"]:
                    st.write(f"**Reason for Renting:** {p['rent_reason']}")

                st.write(p["description"])

                # Product Details Screen / Expander with dynamically enabled gender dropdown
                with st.expander("Product Details & Gender Selection", expanded=False):
                    if p["ai_classification_note"]:
                        st.caption(f"Classification: {p['ai_classification_note']}")

                    if is_spec:
                        default_idx = (
                            GENDER_OPTIONS.index(p["target_gender"])
                            if p["target_gender"] in GENDER_OPTIONS
                            else 0
                        )
                        chosen_gender = st.selectbox(
                            "Gender / Audience Specification",
                            options=GENDER_OPTIONS,
                            index=default_idx,
                            key=f"detail_gender_{p['id']}",
                            help="Enabled because this is a gender-specific item.",
                        )
                    else:
                        st.selectbox(
                            "Gender / Audience Specification",
                            options=[GENDER_NEUTRAL_LABEL],
                            index=0,
                            disabled=True,
                            key=f"detail_gender_disabled_{p['id']}",
                            help="Disabled because this product is gender-neutral.",
                        )
                        chosen_gender = GENDER_NEUTRAL_LABEL

                if st.button("Add to Order", key=f"add_{p['id']}"):
                    if p["id"] not in [item["id"] for item in st.session_state["cart"]]:
                        item_dict = dict(p)
                        item_dict["selected_gender"] = chosen_gender
                        st.session_state["cart"].append(item_dict)
                        st.success("Added to order!")
            st.divider()

    # --- Cart & Checkout ---
    if st.session_state["cart"]:
        st.sidebar.subheader("Your Order")
        total_borrower_fees = 0.0
        for item in st.session_state["cart"]:
            gender_tag = f" [{item.get('selected_gender', GENDER_NEUTRAL_LABEL)}]"
            st.sidebar.write(
                f"- {item['title']}{gender_tag} (Fee: ${item['borrower_fee']:.2f})"
            )
            total_borrower_fees += item["borrower_fee"]

        discount_pct = 0.0
        if is_lender(st.session_state["user"]["id"]):
            discount_pct = float(
                conn.execute(
                    "SELECT value FROM settings WHERE key = 'loyalty_discount_pct'"
                ).fetchone()[0]
            )

        discount_amount = total_borrower_fees * (discount_pct / 100.0)
        final_fee = total_borrower_fees - discount_amount

        st.sidebar.write("---")
        st.sidebar.write(f"Total Fees: ${total_borrower_fees:.2f}")
        if discount_pct > 0:
            st.sidebar.write(
                f"Loyalty Discount ({discount_pct}%): -${discount_amount:.2f}"
            )
        st.sidebar.write(f"**Final Convenience Fee: ${final_fee:.2f}**")

        if st.sidebar.button("Checkout & Pay Fee"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (borrower_id, total_fee, created_at) VALUES (?, ?, ?)",
                (st.session_state["user"]["id"], final_fee, now),
            )

            emails_to_send = []
            for item in st.session_state["cart"]:
                cursor.execute(
                    "UPDATE products SET is_available = 0 WHERE id = ?", (item["id"],)
                )
                lender = conn.execute(
                    "SELECT email, address, phone FROM users WHERE id = ?",
                    (item["lender_id"],),
                ).fetchone()
                emails_to_send.append(
                    f"Item: {item['title']} ({item.get('selected_gender', GENDER_NEUTRAL_LABEL)})\n"
                    f"Lender Email: {lender['email']}\n"
                    f"Address: {lender['address']}\n"
                    f"Phone: {lender['phone']}"
                )

            conn.commit()

            st.session_state["last_checkout_emails"] = emails_to_send
            st.session_state["cart"] = []
            st.rerun()

    conn.close()


# --- Main App Routing ---
def main():
    st.set_page_config(page_title="RentItApp", layout="wide")
    init_db()

    if "user" not in st.session_state:
        auth_view()
    else:
        st.sidebar.write(f"Welcome, **{st.session_state['user']['username']}**")
        if st.sidebar.button("Logout"):
            del st.session_state["user"]
            st.rerun()

        st.sidebar.divider()

        # Navigation based on role
        options = ["Borrower Portal", "Lender Portal"]
        if st.session_state["user"]["is_admin"]:
            options.append("Admin Portal")

        choice = st.sidebar.radio("Navigate", options)

        if choice == "Borrower Portal":
            borrower_portal()
        elif choice == "Lender Portal":
            lender_portal()
        elif choice == "Admin Portal":
            admin_portal()


if __name__ == "__main__":
    main()