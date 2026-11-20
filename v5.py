import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime
import json

try:
    from transformers import pipeline as hf_pipeline
except ImportError as exc:
    raise RuntimeError(
        "This version needs the transformer dependencies. Run: pip install -r requirements.txt"
    ) from exc

# --- Configuration & Directories ---
DB_NAME = "rental_app.db"
UPLOAD_DIR = "uploads"
MODEL_DIR = os.path.join("models", "gender-nli")
DEFAULT_MODEL_ID = "MoritzLaurer/xtremedistil-l6-h256-mnli-fever-anli-ling-binary"

GENDER_OPTIONS = ["Women's", "Men's", "Kids", "Unisex"]
GENDER_NEUTRAL_LABEL = "Gender Neutral"
# Used only to decide whether the audience filter is relevant in a category.
GENDERED_CATEGORIES = {"Clothing", "Fashion Accessories", "Shoes", "Makeup", "Self Care"}


def _model_id():
    """Allow the NLI model to be swapped without editing code."""
    try:
        override = st.secrets.get("model", {}).get("gender_model")
        if override:
            return override
    except Exception:
        pass
    return os.environ.get("RENTIT_GENDER_MODEL", DEFAULT_MODEL_ID)


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
    """Return all admin (username, password) pairs from secrets."""
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

    # Safe schema migration for existing databases
    _ensure_column(c, "products", "is_gender_specific", "BOOLEAN DEFAULT 0")
    _ensure_column(c, "products", "target_gender", "TEXT DEFAULT 'Gender Neutral'")
    _ensure_column(c, "products", "ai_classification_note", "TEXT DEFAULT ''")

    # Persistent Shopping List / Cart table for registered users & admins
    c.execute('''CREATE TABLE IF NOT EXISTS shopping_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        added_at DATETIME,
        UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')

    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrower_id INTEGER,
        total_fee REAL,
        items_summary TEXT DEFAULT '',
        created_at DATETIME,
        FOREIGN KEY(borrower_id) REFERENCES users(id)
    )''')
    _ensure_column(c, "orders", "items_summary", "TEXT DEFAULT ''")

    # Default Admin(s) & Settings
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


# --- Transformer-based Gender Classification (zero-shot NLI) ---
@st.cache_resource(show_spinner="Downloading & loading the gender-classification transformer (first run only)...")
def load_gender_classifier():
    """Load the distilled zero-shot NLI transformer on CPU."""
    if hf_pipeline is None:
        raise RuntimeError(
            "The gender classifier needs transformers/torch. "
            "Run: pip install -r requirements.txt"
        )

    os.makedirs(MODEL_DIR, exist_ok=True)
    has_local_weights = any(
        fname.endswith((".bin", ".safetensors"))
        for fname in os.listdir(MODEL_DIR)
    )
    source = MODEL_DIR if has_local_weights else _model_id()
    try:
        clf = hf_pipeline(
            "zero-shot-classification",
            model=source,
            tokenizer=source,
            device=-1,  # CPU execution: no GPU required
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not load the gender model '{_model_id()}'. Check your internet "
            "connection, Hugging Face access and free disk space, or point "
            "RENTIT_GENDER_MODEL at another NLI model. "
            f"Details: {exc}"
        ) from exc

    if not has_local_weights:
        try:
            clf.save_pretrained(MODEL_DIR)
        except Exception:
            pass
    return clf


_SPECIFIC_HYPOTHESES = [
    "a gender-specific item such as clothing, footwear, makeup, jewellery or a fashion accessory intended for a particular audience",
    "a general-purpose gender-neutral item such as electronics, tools, books, furniture, appliances or household equipment",
]
_AUDIENCE_HYPOTHESES = {
    "women's clothing or accessory": "Women's",
    "men's clothing or accessory": "Men's",
    "children's clothing or toy": "Kids",
    "unisex item for everyone": "Unisex",
}


def _nli_scores(clf, text, hypotheses, template):
    """Return {hypothesis: entailment_probability} for the given text."""
    result = clf(
        text,
        candidate_labels=list(hypotheses),
        hypothesis_template=template,
        multi_label=False,
    )
    positions = {label: i for i, label in enumerate(result["labels"])}
    return {h: float(result["scores"][positions[h]]) for h in hypotheses}


@st.cache_data(show_spinner=False)
def classify_product_gender(category, title, description):
    """Classify a listing as gender-specific or neutral, then infer its audience."""
    text = (
        f"Category: {(category or '').strip()}. "
        f"Product: {(title or '').strip()}. "
        f"Details: {(description or '').strip()}"
    )
    clf = load_gender_classifier()
    model_id = _model_id()

    try:
        stage1 = _nli_scores(
            clf, text, _SPECIFIC_HYPOTHESES, "This listing describes {}."
        )
        specific_score = stage1[_SPECIFIC_HYPOTHESES[0]]
        neutral_score = stage1[_SPECIFIC_HYPOTHESES[1]]

        if neutral_score > specific_score:
            return (
                False,
                GENDER_NEUTRAL_LABEL,
                f"Gender-neutral (transformer, {neutral_score * 100:.0f}% confidence) — {model_id}",
            )

        stage2 = _nli_scores(
            clf,
            text,
            _AUDIENCE_HYPOTHESES.keys(),
            "This listing is a {}.",
        )
        best_hypothesis = max(stage2, key=stage2.get)
        suggested = _AUDIENCE_HYPOTHESES[best_hypothesis]
        audience_conf = stage2[best_hypothesis]

        return (
            True,
            suggested,
            f"Gender-specific (transformer, {specific_score * 100:.0f}% confidence) — "
            f"Suggested: {suggested} ({audience_conf * 100:.0f}%) — {model_id}",
        )
    except Exception as exc:
        raise RuntimeError(
            f"The transformer '{model_id}' could not classify this product. "
            f"Details: {exc}"
        ) from exc


# --- Authentication & Navigation Helpers ---
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


def navigate_to_page(page_name):
    """Callback to robustly update navigation state without widget conflict errors."""
    st.session_state["nav_radio"] = page_name
    st.session_state["active_page"] = page_name


# --- Shopping Cart Data Helpers ---
def get_shopping_list_items(conn, user_id):
    """Fetch all currently available items in the user's shopping cart/list."""
    return conn.execute(
        """
        SELECT sl.id AS list_entry_id,
               sl.product_id AS product_id,
               sl.added_at,
               p.*,
               c.borrower_fee,
               u.username AS lender_username
        FROM shopping_list sl
        JOIN products p ON sl.product_id = p.id
        JOIN categories c ON p.category = c.name
        LEFT JOIN users u ON p.lender_id = u.id
        WHERE sl.user_id = ? AND p.is_available = 1
        ORDER BY sl.added_at DESC
        """,
        (user_id,),
    ).fetchall()


def get_shopping_list_count(user_id):
    conn = get_db()
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM shopping_list sl
        JOIN products p ON sl.product_id = p.id
        WHERE sl.user_id = ? AND p.is_available = 1
        """,
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return count


def add_to_shopping_list(user_id, product_id):
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO shopping_list (user_id, product_id, added_at) VALUES (?, ?, ?)",
        (user_id, product_id, now),
    )
    added = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return added


def remove_from_shopping_list(user_id, product_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM shopping_list WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    conn.commit()
    conn.close()


def clear_shopping_list(user_id):
    conn = get_db()
    conn.execute("DELETE FROM shopping_list WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def calculate_fee_breakdown(conn, user_id, items):
    """Compute total borrower convenience fees, loyalty discount, and final payable fee."""
    total_fees = sum(float(item["borrower_fee"]) for item in items)
    discount_pct = 0.0
    if is_lender(user_id):
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'loyalty_discount_pct'"
        ).fetchone()
        if row:
            discount_pct = float(row[0])
    discount_amount = total_fees * (discount_pct / 100.0)
    final_fee = max(0.0, total_fees - discount_amount)
    return total_fees, discount_pct, discount_amount, final_fee


def execute_order(conn, user_id, items):
    """Process checkout for one or more products atomically and build lender contact emails."""
    if not items:
        return False, "No items selected to order."

    cursor = conn.cursor()
    available_items = []
    for item in items:
        fresh = cursor.execute(
            """
            SELECT p.*, c.borrower_fee
            FROM products p
            JOIN categories c ON p.category = c.name
            WHERE p.id = ? AND p.is_available = 1
            """,
            (item["id"],),
        ).fetchone()
        if fresh is not None:
            available_items.append(dict(fresh))

    if not available_items:
        return False, "Selected item(s) are no longer available."

    _, _, _, final_fee = calculate_fee_breakdown(conn, user_id, available_items)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = ", ".join(item["title"] for item in available_items)

    cursor.execute(
        "INSERT INTO orders (borrower_id, total_fee, items_summary, created_at) VALUES (?, ?, ?, ?)",
        (user_id, final_fee, summary, now),
    )

    emails_to_send = []
    for item in available_items:
        cursor.execute(
            "UPDATE products SET is_available = 0, updated_at = ? WHERE id = ?",
            (now, item["id"]),
        )
        # Remove purchased item from all users' shopping lists
        cursor.execute(
            "DELETE FROM shopping_list WHERE product_id = ?", (item["id"],)
        )
        lender = cursor.execute(
            "SELECT username, email, address, phone FROM users WHERE id = ?",
            (item["lender_id"],),
        ).fetchone()
        audience_label = (
            item["target_gender"]
            if bool(item["is_gender_specific"])
            else GENDER_NEUTRAL_LABEL
        )
        lender_name = lender["username"] if lender and lender["username"] else "Lender"
        lender_email = lender["email"] if lender and lender["email"] else "Not provided"
        lender_addr = lender["address"] if lender and lender["address"] else "Not provided"
        lender_phone = lender["phone"] if lender and lender["phone"] else "Not provided"

        emails_to_send.append(
            f"Item: {item['title']} ({audience_label})\n"
            f"Rental Price (payable at pickup): ${float(item['rent_price']):.2f}\n"
            f"Lender: {lender_name}\n"
            f"Lender Email: {lender_email}\n"
            f"Address: {lender_addr}\n"
            f"Phone: {lender_phone}"
        )

    conn.commit()
    return True, (final_fee, emails_to_send)


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


# --- Read-Only Product Details Renderer ---
def render_readonly_product_details(product_row):
    """Display complete product metadata strictly as read-only information."""
    is_spec = bool(product_row["is_gender_specific"])
    audience_display = (
        product_row["target_gender"] if is_spec else GENDER_NEUTRAL_LABEL
    )
    lender_name = (
        product_row["lender_username"]
        if "lender_username" in product_row.keys() and product_row["lender_username"]
        else "Registered Lender"
    )

    with st.expander("View Product Details (Read-Only)", expanded=False):
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**Title:** {product_row['title']}")
            st.markdown(f"**Category:** {product_row['category']}")
            st.markdown(f"**Rental Price:** ${float(product_row['rent_price']):.2f}")
            st.markdown(
                f"**Borrower Convenience Fee:** ${float(product_row['borrower_fee']):.2f}"
            )
            st.markdown(f"**Gender / Audience:** {audience_display}")
        with d2:
            st.markdown(f"**Listed By:** {lender_name}")
            st.markdown(f"**Condition:** {product_row['usage_status']}")
            if product_row["usage_status"] == "Used":
                dur = product_row["usage_duration"] or "Not specified"
                st.markdown(f"**Usage Duration:** {dur}")
            else:
                p_date = product_row["purchase_date"] or "Not specified"
                st.markdown(f"**Purchase Date:** {p_date}")

            if product_row["is_consumable"]:
                st.markdown(
                    f"**Consumable:** Yes (Mfg: {product_row['mfg_date']} | Exp: {product_row['exp_date']})"
                )
            else:
                st.markdown("**Consumable:** No")
            st.markdown(f"**Last Updated:** {product_row['updated_at']}")

        if product_row["rent_reason"]:
            st.markdown(f"**Reason for Renting Out:** {product_row['rent_reason']}")

        st.markdown("**Full Description:**")
        st.write(product_row["description"])

        if product_row["ai_classification_note"]:
            st.caption(f"Audience Classification: {product_row['ai_classification_note']}")


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
                st.session_state["active_page"] = "Borrower Portal"
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

    col_left, col_right = st.columns([2, 1])
    with col_left:
        title = st.text_input("Product Title", key="lender_title")
        category = st.selectbox("Category", categories, key="lender_category")
        desc = st.text_area("A few lines about the product", key="lender_desc")

    classification_error = None
    try:
        is_gender_specific, suggested_gender, ai_note = classify_product_gender(
            category, title, desc
        )
    except RuntimeError as exc:
        classification_error = str(exc)
        is_gender_specific, suggested_gender, ai_note = True, GENDER_NEUTRAL_LABEL, ""

    with col_right:
        st.markdown("#### AI Audience Classification")
        if classification_error:
            st.error(
                f"**AI classification unavailable**\n\n{classification_error}\n\n"
                "Choose the audience manually below."
            )
            selected_target_gender = st.selectbox(
                "Assign Target Gender / Audience (manual)",
                options=GENDER_OPTIONS,
                key="lender_target_gender_manual",
            )
        elif is_gender_specific:
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
    user_id = st.session_state["user"]["id"]

    if st.session_state.get("last_checkout_emails"):
        paid_fee, emails = st.session_state.pop("last_checkout_emails")
        st.success(f"Payment of ${paid_fee:.2f} successful! Your order has been confirmed.")
        st.info(
            "📨 **MOCK EMAIL SENT TO YOU:**\n\n"
            + "\n\n---\n\n".join(emails)
        )

    # --- Sidebar Filters ---
    st.sidebar.subheader("Filters")
    categories = ["All"] + [
        row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    ]
    selected_cat = st.sidebar.selectbox("Category", categories)
    search_term = st.sidebar.text_input("Search")

    if selected_cat == "All":
        enable_gender_filter = True
    else:
        gender_specific_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE is_available = 1 AND is_gender_specific = 1 AND category = ?",
            (selected_cat,),
        ).fetchone()[0]
        enable_gender_filter = (gender_specific_count > 0) or (
            selected_cat in GENDERED_CATEGORIES
        )

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
        "SELECT p.*, c.borrower_fee, u.username AS lender_username "
        "FROM products p "
        "JOIN categories c ON p.category = c.name "
        "LEFT JOIN users u ON p.lender_id = u.id "
        "WHERE p.is_available = 1"
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
    saved_ids = {
        row["product_id"] for row in get_shopping_list_items(conn, user_id)
    }

    # --- Display Products (Strictly Read-Only Details + Order / Shopping Cart Actions) ---
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

                if p["is_consumable"]:
                    st.write(
                        f"**Consumable:** Yes | **Mfg Date:** {p['mfg_date']} | **Expiry Date:** {p['exp_date']}"
                    )

                if p["rent_reason"]:
                    st.write(f"**Reason for Renting:** {p['rent_reason']}")

                st.write(p["description"])

                render_readonly_product_details(p)

                act1, act2, _ = st.columns([1.2, 1.5, 2.3])
                with act1:
                    if st.button("Order Now", type="primary", key=f"order_now_{p['id']}"):
                        ok, outcome = execute_order(conn, user_id, [dict(p)])
                        if ok:
                            st.session_state["last_checkout_emails"] = outcome
                            st.rerun()
                        else:
                            st.error(outcome)

                with act2:
                    already_in_list = p["id"] in saved_ids
                    btn_label = (
                        "In Shopping Cart ✓"
                        if already_in_list
                        else "Add to Shopping List"
                    )
                    if st.button(
                        btn_label,
                        disabled=already_in_list,
                        key=f"add_list_{p['id']}",
                    ):
                        if add_to_shopping_list(user_id, p["id"]):
                            st.session_state["toast_msg"] = (
                                f"Added '{p['title']}' to your shopping cart."
                            )
                            st.rerun()
            st.divider()

    # --- Sidebar Quick Summary of User's Persistent Shopping Cart ---
    shopping_items = get_shopping_list_items(conn, user_id)
    if shopping_items:
        st.sidebar.divider()
        st.sidebar.subheader(f"🛒 Cart Summary ({len(shopping_items)})")
        for item in shopping_items:
            aud = (
                item["target_gender"]
                if bool(item["is_gender_specific"])
                else GENDER_NEUTRAL_LABEL
            )
            st.sidebar.write(
                f"- {item['title']} [{aud}] (Fee: ${float(item['borrower_fee']):.2f})"
            )

        total_fees, discount_pct, discount_amt, final_fee = calculate_fee_breakdown(
            conn, user_id, shopping_items
        )
        st.sidebar.write("---")
        st.sidebar.write(f"Total Convenience Fees: ${total_fees:.2f}")
        if discount_pct > 0:
            st.sidebar.write(
                f"Loyalty Discount ({discount_pct:.1f}%): -${discount_amt:.2f}"
            )
        st.sidebar.write(f"**Payable Convenience Fee: ${final_fee:.2f}**")
        
        st.sidebar.button(
            "Open Shopping Cart", 
            key="sidebar_open_cart", 
            on_click=navigate_to_page, 
            args=("Shopping Cart",)
        )

    conn.close()


def shopping_cart_portal():
    st.title("🛒 Shopping Cart")
    conn = get_db()
    user_id = st.session_state["user"]["id"]

    st.button(
        "← Continue Browsing Products", 
        key="cart_back_to_browse", 
        on_click=navigate_to_page, 
        args=("Borrower Portal",)
    )

    if st.session_state.get("last_checkout_emails"):
        paid_fee, emails = st.session_state.pop("last_checkout_emails")
        st.success(f"Payment of ${paid_fee:.2f} successful! All items in your order are confirmed.")
        st.info(
            "📨 **MOCK EMAIL SENT TO YOU:**\n\n"
            + "\n\n---\n\n".join(emails)
        )

    # Clean up stale entries whose products were already rented out
    stale_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM shopping_list sl
        JOIN products p ON sl.product_id = p.id
        WHERE sl.user_id = ? AND p.is_available = 0
        """,
        (user_id,),
    ).fetchone()[0]
    if stale_count > 0:
        conn.execute(
            """
            DELETE FROM shopping_list
            WHERE user_id = ? AND product_id IN (
                SELECT id FROM products WHERE is_available = 0
            )
            """,
            (user_id,),
        )
        conn.commit()
        st.warning(
            f"{stale_count} item(s) in your shopping cart became unavailable and were removed."
        )

    items = get_shopping_list_items(conn, user_id)

    if not items:
        st.info(
            "Your shopping cart is currently empty. Browse the **Borrower Portal** to add products you want to rent."
        )
        conn.close()
        return

    st.write(
        "Review the items in your shopping cart below, remove any you no longer want, and check out all products at once."
    )

    for item in items:
        with st.container():
            col_img, col_info, col_action = st.columns([1, 3, 1])
            photos = json.loads(item["photos"]) if item["photos"] else []
            with col_img:
                if photos:
                    st.image(photos[0], width="stretch")
            with col_info:
                st.subheader(item["title"])
                aud = (
                    item["target_gender"]
                    if bool(item["is_gender_specific"])
                    else GENDER_NEUTRAL_LABEL
                )
                st.write(
                    f"**Rental Price:** ${float(item['rent_price']):.2f} | "
                    f"**Category:** {item['category']} | **Audience:** {aud}"
                )
                st.write(
                    f"**Borrower Convenience Fee:** ${float(item['borrower_fee']):.2f}"
                )
                if item["usage_status"] == "Used":
                    st.write(
                        f"**Condition:** Used | **Usage Duration:** {item['usage_duration'] or 'Not specified'}"
                    )
                else:
                    st.write(
                        f"**Condition:** Unused/New | **Purchase Date:** {item['purchase_date'] or 'Not specified'}"
                    )
                render_readonly_product_details(item)

            with col_action:
                st.write("")
                if st.button("Remove", key=f"remove_sl_{item['id']}"):
                    remove_from_shopping_list(user_id, item["id"])
                    st.rerun()
            st.divider()

    # Consolidated Order Summary & Checkout
    total_rental_price = sum(float(i["rent_price"]) for i in items)
    total_fees, discount_pct, discount_amt, final_fee = calculate_fee_breakdown(
        conn, user_id, items
    )

    st.subheader("Order Summary")
    s1, s2, s3 = st.columns(3)
    s1.metric("Items in Order", len(items))
    s2.metric("Total Rental Value (Payable at Pickup)", f"${total_rental_price:.2f}")
    s3.metric("Final Convenience Fee", f"${final_fee:.2f}")

    st.write(f"- **Subtotal Convenience Fees:** ${total_fees:.2f}")
    if discount_pct > 0:
        st.write(
            f"- **Lender-Borrower Loyalty Discount ({discount_pct:.1f}%):** -${discount_amt:.2f}"
        )
    st.write(f"- **Total Convenience Fee Payable Now:** **${final_fee:.2f}**")

    c_checkout, c_clear, _ = st.columns([1.6, 1.2, 3])
    with c_checkout:
        if st.button("Checkout All Products & Pay Fee", type="primary"):
            ok, outcome = execute_order(conn, user_id, items)
            if ok:
                st.session_state["last_checkout_emails"] = outcome
                st.rerun()
            else:
                st.error(outcome)

    with c_clear:
        if st.button("Clear Shopping Cart"):
            clear_shopping_list(user_id)
            st.rerun()

    conn.close()


def _on_nav_radio_change():
    st.session_state["active_page"] = st.session_state["nav_radio"]


# --- Main App Routing ---
def main():
    st.set_page_config(page_title="RentItApp", layout="wide")
    init_db()

    if st.session_state.get("toast_msg"):
        st.toast(st.session_state.pop("toast_msg"))

    if "user" not in st.session_state:
        auth_view()
    else:
        user = st.session_state["user"]
        st.sidebar.write(f"Welcome, **{user['username']}**")
        if st.sidebar.button("Logout"):
            del st.session_state["user"]
            st.session_state.pop("active_page", None)
            st.session_state.pop("nav_radio", None)
            st.rerun()

        st.sidebar.divider()

        list_count = get_shopping_list_count(user["id"])

        # Navigation available to registered users and admins
        options = ["Borrower Portal", "Shopping Cart", "Lender Portal"]
        if user["is_admin"]:
            options.append("Admin Portal")

        if (
            "active_page" not in st.session_state
            or st.session_state["active_page"] not in options
        ):
            st.session_state["active_page"] = "Borrower Portal"

        if (
            "nav_radio" not in st.session_state
            or st.session_state["nav_radio"] not in options
        ):
            st.session_state["nav_radio"] = st.session_state["active_page"]

        # Top-right Shopping Cart icon header bar
        hdr_left, hdr_right = st.columns([6.5, 1.5])
        with hdr_left:
            st.caption("RentItApp · Peer-to-Peer Rental Marketplace")
        with hdr_right:
            cart_btn_label = f"🛒 Cart ({list_count})"
            st.button(
                cart_btn_label,
                key="top_right_cart_btn",
                help="Click to view your Shopping Cart and check out",
                use_container_width=True,
                type="primary" if list_count > 0 else "secondary",
                on_click=navigate_to_page,
                args=("Shopping Cart",)
            )

        choice = st.sidebar.radio(
            "Navigate",
            options,
            key="nav_radio",
            on_change=_on_nav_radio_change,
        )

        if choice == "Borrower Portal":
            borrower_portal()
        elif choice == "Shopping Cart":
            shopping_cart_portal()
        elif choice == "Lender Portal":
            lender_portal()
        elif choice == "Admin Portal":
            admin_portal()


if __name__ == "__main__":
    main()