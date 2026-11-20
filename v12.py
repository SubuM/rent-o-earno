import streamlit as st
import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
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
SESSION_TTL_DAYS = 7

GENDER_OPTIONS = ["Women's", "Men's", "Kids", "Unisex"]
GENDER_NEUTRAL_LABEL = "Gender Neutral"
ADDRESS_LABEL_OPTIONS = ["Home", "Office", "Other"]
MANDATORY_FIELD_LEGEND = ":red[*] indicates mandatory fields to be filled in"
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

    # Persistent Browser Sessions table (survives browser reloads)
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        active_page TEXT DEFAULT 'Borrower Portal',
        created_at DATETIME,
        expires_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # User Address Book table
    c.execute('''CREATE TABLE IF NOT EXISTS user_addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT DEFAULT 'Home',
        custom_label TEXT DEFAULT '',
        recipient_name TEXT DEFAULT '',
        house_no TEXT DEFAULT '',
        street_address TEXT NOT NULL,
        landmark TEXT DEFAULT '',
        city TEXT DEFAULT '',
        state_postal TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        is_default BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Safe schema migration for user_addresses
    _ensure_column(c, "user_addresses", "custom_label", "TEXT DEFAULT ''")
    _ensure_column(c, "user_addresses", "house_no", "TEXT DEFAULT ''")
    _ensure_column(c, "user_addresses", "landmark", "TEXT DEFAULT ''")

    # Migrate legacy rows where custom text was saved directly in `label`
    c.execute(
        """
        UPDATE user_addresses
        SET custom_label = label,
            label = 'Other'
        WHERE label IS NOT NULL
          AND TRIM(label) != ''
          AND label NOT IN ('Home', 'Office', 'Other')
          AND (custom_label IS NULL OR TRIM(custom_label) = '')
        """
    )

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
        selected_address TEXT DEFAULT '',
        created_at DATETIME,
        FOREIGN KEY(borrower_id) REFERENCES users(id)
    )''')
    _ensure_column(c, "orders", "items_summary", "TEXT DEFAULT ''")
    _ensure_column(c, "orders", "selected_address", "TEXT DEFAULT ''")

    # Order Line Items table for detailed Order History
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_title TEXT,
        category TEXT,
        target_gender TEXT DEFAULT 'Gender Neutral',
        rent_price REAL DEFAULT 0.0,
        borrower_fee REAL DEFAULT 0.0,
        lender_id INTEGER,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(lender_id) REFERENCES users(id)
    )''')

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


@st.cache_resource(show_spinner=False)
def ensure_demo_data():
    """Seed the demo dataset once on a fresh deployment.

    Streamlit Cloud builds from the repo only, and ``*.db`` is git-ignored, so the
    deployed app starts with an empty database. The committed seed scripts are
    used here to rebuild the same sample data locally and in the cloud.
    """
    init_db()  # seed_v9.seed() expects the schema to already exist
    conn = get_db()
    try:
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        regular_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 0"
        ).fetchone()[0]
    except sqlite3.Error:
        products = regular_users = 0
    finally:
        conn.close()

    # Never overwrite an existing dataset (e.g. real sign-ups or listings).
    if products > 0 or regular_users > 0:
        return

    try:
        import seed_v10

        seed_v10.seed()
    except Exception as exc:
        st.warning(
            "Demo sample data was not seeded. Make sure `seed_v9.py` and "
            "`seed_v10.py` are in the repo and add a `[demo_users]` section with "
            "the test logins to Streamlit Cloud Secrets, then reboot the app. "
            f"Details: {exc}"
        )


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


# --- Authentication, Persistent Session & Navigation Helpers ---
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


def create_user_session(user_id, active_page="Borrower Portal"):
    """Create a persistent DB-backed login session token for browser reload survival."""
    conn = get_db()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = (now + timedelta(days=SESSION_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    token = secrets.token_urlsafe(32)

    # Prune expired sessions opportunistically
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_str,))
    conn.execute(
        """
        INSERT INTO sessions (token, user_id, active_page, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, user_id, active_page, now_str, expires_str),
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_session_token(token):
    """Validate a persistent session token and return (user_dict, saved_active_page)."""
    if not token or not isinstance(token, str):
        return None, "Borrower Portal"

    conn = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        """
        SELECT s.active_page AS session_active_page,
               s.expires_at AS session_expires_at,
               u.*
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()

    if row is None:
        conn.close()
        return None, "Borrower Portal"

    if row["session_expires_at"] and row["session_expires_at"] <= now_str:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None, "Borrower Portal"

    saved_page = row["session_active_page"] or "Borrower Portal"
    user_dict = {k: row[k] for k in row.keys() if not k.startswith("session_")}
    conn.close()
    return user_dict, saved_page


def update_session_page(token, page_name):
    """Persist the user's current portal view so browser refresh stays on the same page."""
    if not token or not page_name:
        return
    conn = get_db()
    conn.execute(
        "UPDATE sessions SET active_page = ? WHERE token = ?",
        (page_name, token),
    )
    conn.commit()
    conn.close()


def delete_user_session(token):
    """Revoke a session token on explicit logout."""
    if not token:
        return
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def is_lender(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM products WHERE lender_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count > 0


def navigate_to_page(page_name):
    """Callback to safely update navigation state before widgets instantiate."""
    st.session_state["nav_radio"] = page_name
    st.session_state["active_page"] = page_name
    update_session_page(st.session_state.get("session_token"), page_name)


def redirect_to_address_book(return_page=None):
    """Queue a safe redirect to Address Book from inside any portal action."""
    st.session_state["address_required_prompt"] = True
    if return_page:
        st.session_state["return_after_address"] = return_page
    st.session_state["pending_nav_target"] = "Address Book"
    update_session_page(st.session_state.get("session_token"), "Address Book")
    st.rerun()


# --- Address Book Data Helpers ---
def get_user_addresses(conn, user_id):
    """Return all saved addresses for a user, default address first."""
    return conn.execute(
        """
        SELECT *
        FROM user_addresses
        WHERE user_id = ?
        ORDER BY is_default DESC, id ASC
        """,
        (user_id,),
    ).fetchall()


def get_address_count(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM user_addresses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def extract_label_parts(addr_row):
    """Return normalized (label_type, custom_label_text) for any user_addresses row."""
    raw_label = (addr_row["label"] or "Home").strip()
    raw_custom = (
        (addr_row["custom_label"] or "").strip()
        if "custom_label" in addr_row.keys()
        else ""
    )
    if raw_label not in ADDRESS_LABEL_OPTIONS:
        return "Other", raw_custom or raw_label
    if raw_label == "Other":
        return "Other", raw_custom
    return raw_label, ""


def format_address_label(addr_row):
    """Human-readable label including custom text when marked as 'Other'."""
    label_type, custom_text = extract_label_parts(addr_row)
    if label_type == "Other" and custom_text:
        return f"Other ({custom_text})"
    return label_type


def format_address_line(addr_row):
    """Format a user_addresses row into a clean, human-readable address string."""
    parts = []
    if addr_row["recipient_name"]:
        parts.append(addr_row["recipient_name"].strip())

    house_street = []
    if "house_no" in addr_row.keys() and addr_row["house_no"] and addr_row["house_no"].strip():
        house_street.append(f"House No. {addr_row['house_no'].strip()}")
    if addr_row["street_address"] and addr_row["street_address"].strip():
        house_street.append(addr_row["street_address"].strip().replace("\n", ", "))
    if house_street:
        parts.append(", ".join(house_street))

    if "landmark" in addr_row.keys() and addr_row["landmark"] and addr_row["landmark"].strip():
        parts.append(f"Landmark: {addr_row['landmark'].strip()}")

    city_zip = " ".join(
        p.strip()
        for p in (addr_row["city"] or "", addr_row["state_postal"] or "")
        if p.strip()
    )
    if city_zip:
        parts.append(city_zip)

    summary = ", ".join(parts)
    if addr_row["phone"]:
        summary += f" (Phone: {addr_row['phone'].strip()})"
    label_display = format_address_label(addr_row)
    default_prefix = "⭐ [Default] " if bool(addr_row["is_default"]) else ""
    return f"{default_prefix}{label_display}: {summary}"


def add_user_address(
    conn,
    user_id,
    label,
    recipient_name,
    house_no,
    street_address,
    landmark,
    city,
    state_postal,
    phone,
    set_default=False,
    custom_label="",
):
    """Insert a new address into user_addresses, preserving both label type and custom 'Other' text."""
    raw_label = (label or "").strip() or "Home"
    raw_custom = (custom_label or "").strip()

    if raw_label not in ADDRESS_LABEL_OPTIONS:
        stored_label = "Other"
        stored_custom = raw_custom or raw_label
    elif raw_label == "Other":
        stored_label = "Other"
        stored_custom = raw_custom
    else:
        stored_label = raw_label
        stored_custom = ""

    cursor = conn.cursor()
    if set_default:
        cursor.execute(
            "UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,)
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO user_addresses
        (user_id, label, custom_label, recipient_name, house_no, street_address, landmark, city, state_postal, phone, is_default, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            stored_label,
            stored_custom,
            (recipient_name or "").strip(),
            (house_no or "").strip(),
            (street_address or "").strip(),
            (landmark or "").strip(),
            (city or "").strip(),
            (state_postal or "").strip(),
            (phone or "").strip(),
            int(bool(set_default)),
            now,
        ),
    )
    conn.commit()


def set_default_address(conn, user_id, address_id):
    """Set a specific address as the user's single default address."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,)
    )
    cursor.execute(
        "UPDATE user_addresses SET is_default = 1 WHERE id = ? AND user_id = ?",
        (address_id, user_id),
    )
    conn.commit()


def clear_default_address(conn, user_id):
    """Unset default address so none is marked default (optional default behavior)."""
    conn.execute(
        "UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,)
    )
    conn.commit()


def delete_user_address(conn, user_id, address_id):
    conn.execute(
        "DELETE FROM user_addresses WHERE id = ? AND user_id = ?",
        (address_id, user_id),
    )
    conn.commit()


def render_order_address_selector(conn, user_id, widget_key, label="Select Your Address for This Order :red[*]"):
    """
    Render a dropdown of the user's saved addresses (pre-selecting the default address).
    Returns the formatted selected address string, or None if the address book is empty.
    """
    addresses = get_user_addresses(conn, user_id)
    if not addresses:
        return None

    options = [format_address_line(a) for a in addresses]
    default_idx = 0
    for idx, a in enumerate(addresses):
        if bool(a["is_default"]):
            default_idx = idx
            break

    chosen = st.selectbox(
        label,
        options=options,
        index=default_idx,
        placeholder="Choose a saved address from your Address Book",
        key=widget_key,
        help="Choose one address from your Address Book. Your default address is pre-selected if set.",
    )
    st.caption(MANDATORY_FIELD_LEGEND)
    return chosen


def render_admin_address_books_section(conn, key_prefix="admin_addr"):
    """Render all Regular and Admin users' Address Books, including custom 'Other' label inputs."""
    st.subheader("🛡️ Admin Overview: All Users' Address Books")
    st.caption(
        "Viewing saved address books across all Regular and Admin users, including custom labels entered for 'Other'."
    )

    all_addresses = conn.execute(
        """
        SELECT ua.*,
               u.username AS owner_username,
               u.email AS owner_email,
               u.is_admin AS owner_is_admin
        FROM user_addresses ua
        JOIN users u ON ua.user_id = u.id
        ORDER BY u.username ASC, ua.is_default DESC, ua.id ASC
        """
    ).fetchall()

    if not all_addresses:
        st.info("No users have saved addresses in their Address Books yet.")
        return

    total_addrs = len(all_addresses)
    distinct_owners = len({a["user_id"] for a in all_addresses})
    admin_addrs = sum(1 for a in all_addresses if bool(a["owner_is_admin"]))
    regular_addrs = total_addrs - admin_addrs

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Saved Addresses", total_addrs)
    m2.metric("Users with Addresses", distinct_owners)
    m3.metric("Regular User Addresses", regular_addrs)
    m4.metric("Admin User Addresses", admin_addrs)

    f1, f2, f3 = st.columns(3)
    with f1:
        role_filter = st.selectbox(
            "Filter by User Type",
            ["All Users", "Regular", "Admin"],
            placeholder="Select user type",
            key=f"{key_prefix}_role_filter",
        )
    with f2:
        owner_names = ["All"] + sorted(
            {a["owner_username"] for a in all_addresses}
        )
        owner_filter = st.selectbox(
            "Filter by Username",
            owner_names,
            placeholder="Select username",
            key=f"{key_prefix}_user_filter",
        )
    with f3:
        label_filter = st.selectbox(
            "Filter by Address Label",
            ["All Labels", "Home", "Office", "Other"],
            placeholder="Select address label",
            key=f"{key_prefix}_label_filter",
        )

    filtered_addrs = []
    for a in all_addresses:
        u_type = "Admin" if bool(a["owner_is_admin"]) else "Regular"
        lbl_type, _ = extract_label_parts(a)
        if role_filter != "All Users" and u_type != role_filter:
            continue
        if owner_filter != "All" and a["owner_username"] != owner_filter:
            continue
        if label_filter != "All Labels" and lbl_type != label_filter:
            continue
        filtered_addrs.append(a)

    if not filtered_addrs:
        st.info("No saved addresses match the selected filters.")
        return

    table_rows = []
    for a in filtered_addrs:
        u_type = "Admin" if bool(a["owner_is_admin"]) else "Regular"
        lbl_type, custom_text = extract_label_parts(a)
        city_zip = " ".join(
            p for p in (a["city"] or "", a["state_postal"] or "") if p.strip()
        )
        house_val = a["house_no"] if "house_no" in a.keys() and a["house_no"] else "—"
        landmark_val = a["landmark"] if "landmark" in a.keys() and a["landmark"] else "—"
        table_rows.append(
            {
                "User": a["owner_username"],
                "User Type": u_type,
                "Address Label": lbl_type,
                "Custom Label ('Other' Input)": custom_text if custom_text else "—",
                "Recipient": a["recipient_name"] or "—",
                "House No.": house_val,
                "Street Address": a["street_address"].replace("\n", ", "),
                "Landmark": landmark_val,
                "City / Postal": city_zip or "—",
                "Phone": a["phone"] or "—",
                "Default": "Yes ⭐" if bool(a["is_default"]) else "No",
            }
        )
    st.dataframe(table_rows, width="stretch", hide_index=True)


# --- Shopping Cart & Order History Data Helpers ---
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


def get_order_count(user_id, is_admin):
    """Return total visible orders (all users for admin, own orders for regular user)."""
    conn = get_db()
    if is_admin:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE borrower_id = ?", (user_id,)
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


def execute_order(conn, user_id, items, selected_address):
    """Process checkout atomically, record order, selected address & line items, and build emails."""
    if not selected_address or not selected_address.strip():
        return False, "Please select an address from your Address Book before placing an order."

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
        """
        INSERT INTO orders (borrower_id, total_fee, items_summary, selected_address, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, final_fee, summary, selected_address.strip(), now),
    )
    order_id = cursor.lastrowid

    emails_to_send = []
    for item in available_items:
        audience_label = (
            item["target_gender"]
            if bool(item["is_gender_specific"])
            else GENDER_NEUTRAL_LABEL
        )
        cursor.execute(
            """
            INSERT INTO order_items
            (order_id, product_id, product_title, category, target_gender, rent_price, borrower_fee, lender_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                item["id"],
                item["title"],
                item["category"],
                audience_label,
                float(item["rent_price"]),
                float(item["borrower_fee"]),
                item["lender_id"],
            ),
        )
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
        lender_name = lender["username"] if lender and lender["username"] else "Lender"
        lender_email = lender["email"] if lender and lender["email"] else "Not provided"
        lender_addr = lender["address"] if lender and lender["address"] else "Not provided"
        lender_phone = lender["phone"] if lender and lender["phone"] else "Not provided"

        emails_to_send.append(
            f"Item: {item['title']} ({audience_label})\n"
            f"Rental Price (payable at pickup): ${float(item['rent_price']):.2f}\n"
            f"Your Selected Order Address: {selected_address.strip()}\n"
            f"Lender: {lender_name}\n"
            f"Lender Email: {lender_email}\n"
            f"Lender Pickup Address: {lender_addr}\n"
            f"Lender Phone: {lender_phone}"
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
        with st.form("login_form"):
            username = st.text_input(
                "Username :red[*]",
                placeholder="e.g., choose_a_username",
                key="login_user",
            )
            password = st.text_input(
                "Password :red[*]",
                type="password",
                placeholder="Enter your account password",
                key="login_pw",
            )
            st.caption(MANDATORY_FIELD_LEGEND)
            submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            if not username.strip() or not password.strip():
                st.error("Username and password are required.")
            else:
                user = login_user(username.strip(), password)
                if user:
                    user_dict = dict(user)
                    token = create_user_session(user_dict["id"], "Borrower Portal")
                    st.session_state["user"] = user_dict
                    st.session_state["session_token"] = token
                    st.session_state["active_page"] = "Borrower Portal"
                    st.query_params["session"] = token
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with tab2:
        st.subheader("Register")
        with st.form("register_form"):
            new_user = st.text_input(
                "Username :red[*]",
                placeholder="e.g., choose_a_username",
            )
            new_pw = st.text_input(
                "Password :red[*]",
                type="password",
                placeholder="Choose a strong password (min. 6 characters)",
            )
            email = st.text_input(
                "Email :red[*]",
                placeholder="e.g., name@example.invalid",
            )
            address = st.text_area(
                "Address (Optional)",
                placeholder="e.g., 1 Sample Street, Example City",
            )
            phone = st.text_input(
                "Phone Number :red[*]",
                placeholder="e.g., +1 (555) 000-0000",
            )
            st.caption(MANDATORY_FIELD_LEGEND)
            if st.form_submit_button("Register"):
                missing = []
                if not new_user.strip():
                    missing.append("Username")
                if not new_pw.strip():
                    missing.append("Password")
                if not email.strip():
                    missing.append("Email")
                if not phone.strip():
                    missing.append("Phone Number")

                if missing:
                    st.error(f"Please fill in all mandatory fields: {', '.join(missing)}.")
                else:
                    conn = get_db()
                    try:
                        conn.execute(
                            "INSERT INTO users (username, password, email, address, phone) VALUES (?, ?, ?, ?, ?)",
                            (
                                new_user.strip(),
                                hash_pw(new_pw),
                                email.strip(),
                                address.strip(),
                                phone.strip(),
                            ),
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
        cat_name = st.text_input(
            "Category Name :red[*]",
            placeholder="e.g., Seasonal Items, Hobbies, Specialty Gear",
        )
        lender_fee = st.number_input(
            "Lender Convenience Fee ($) :red[*]",
            min_value=0.0,
            step=0.5,
            placeholder="e.g., 2.00",
        )
        borrower_fee = st.number_input(
            "Borrower Convenience Fee ($) :red[*]",
            min_value=0.0,
            step=0.5,
            placeholder="e.g., 1.50",
        )
        st.caption(MANDATORY_FIELD_LEGEND)
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
            "Loyalty Discount (%) for Lender-Borrowers :red[*]",
            value=float(current_discount),
            min_value=0.0,
            max_value=100.0,
            placeholder="e.g., 10.0",
        )
        st.caption(MANDATORY_FIELD_LEGEND)
        if st.form_submit_button("Update Discount"):
            conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'loyalty_discount_pct'",
                (str(new_discount),),
            )
            conn.commit()
            st.success("Discount updated.")

    # --- All Users' Address Books (including 'Other' custom label inputs) ---
    st.divider()
    render_admin_address_books_section(conn, key_prefix="admin_portal_addr")

    # --- Demo Dataset Overview (populated by seed_v8.py) ---
    st.divider()
    st.subheader("🧪 Demo Dataset Overview")
    st.caption(
        "Sample data is seeded automatically on a fresh deployment from the committed "
        "`seed_v9.py` / `seed_v10.py` scripts. Test passwords live in "
        "`[demo_users]` of Streamlit Cloud Secrets (locally: `.streamlit/secrets.toml`)."
    )
    demo_stats = [
        ("Users", "SELECT COUNT(*) FROM users"),
        ("Admins", "SELECT COUNT(*) FROM users WHERE is_admin = 1"),
        ("Regular users", "SELECT COUNT(*) FROM users WHERE is_admin = 0"),
        ("Categories", "SELECT COUNT(*) FROM categories"),
        ("Products available", "SELECT COUNT(*) FROM products WHERE is_available = 1"),
        ("Products rented out", "SELECT COUNT(*) FROM products WHERE is_available = 0"),
        ("Saved addresses", "SELECT COUNT(*) FROM user_addresses"),
        ("Cart items", "SELECT COUNT(*) FROM shopping_list"),
        ("Orders", "SELECT COUNT(*) FROM orders"),
        ("Order line items", "SELECT COUNT(*) FROM order_items"),
    ]
    stat_cols = st.columns(5)
    for idx, (label, query) in enumerate(demo_stats):
        with stat_cols[idx % 5]:
            st.metric(label, conn.execute(query).fetchone()[0])

    demo_account_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_admin = 0"
    ).fetchone()[0]
    if demo_account_count:
        st.caption(
            f"Regular test accounts: {demo_account_count}. "
            "Credentials are documented in `.streamlit/secrets.toml`."
        )
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
        title = st.text_input(
            "Product Title :red[*]",
            placeholder="e.g., Everyday Garment / Utility Tool",
            key="lender_title",
        )
        category = st.selectbox(
            "Category :red[*]",
            categories,
            placeholder="Select a product category",
            key="lender_category",
        )
        desc = st.text_area(
            "A few lines about the product :red[*]",
            placeholder="e.g., Gently used, clean, and ready to borrow. Includes original accessories.",
            key="lender_desc",
        )

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
                "Assign Target Gender / Audience (manual) :red[*]",
                options=GENDER_OPTIONS,
                placeholder="Select target audience (Women's, Men's, Kids, Unisex)",
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
                "Assign Target Gender / Audience :red[*]",
                options=GENDER_OPTIONS,
                index=default_idx,
                placeholder="Select target audience",
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
                placeholder="Gender Neutral",
                key="lender_target_gender_neutral",
                help="Disabled because the model identified this product as gender-neutral.",
            )
            selected_target_gender = GENDER_NEUTRAL_LABEL

    st.divider()

    rent_price = st.number_input(
        "Rental Price ($) :red[*]",
        min_value=0.0,
        step=1.0,
        placeholder="e.g., 15.00",
        key="lender_price",
    )
    reason = st.text_input(
        "Reason for renting out :red[*]",
        placeholder="e.g., Bought for a one-time project and no longer needed",
        key="lender_reason",
    )

    photos = st.file_uploader(
        "Upload Photos (Minimum 3 required) :red[*]",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="lender_photos",
    )

    c1, c2 = st.columns(2)
    with c1:
        is_consumable = st.checkbox("Is this a consumable product?", key="lender_consumable")
        mfg_date = st.date_input(
            "Manufacturing Date :red[*]" if is_consumable else "Manufacturing Date",
            disabled=not is_consumable,
            key="lender_mfg",
        )
        exp_date = st.date_input(
            "Expiry Date :red[*]" if is_consumable else "Expiry Date",
            disabled=not is_consumable,
            key="lender_exp",
        )
    with c2:
        usage_status = st.radio(
            "Condition :red[*]",
            ["Used", "Unused/New"],
            key="lender_condition",
        )
        is_used = usage_status == "Used"
        usage_duration = st.text_input(
            "Usage Duration (if used) :red[*]" if is_used else "Usage Duration (if used)",
            disabled=not is_used,
            placeholder="e.g., Used a few times over several months",
            key="lender_duration",
        )
        purchase_date = st.date_input(
            "Purchase Date (if new) :red[*]" if not is_used else "Purchase Date (if new)",
            disabled=is_used,
            key="lender_purchase",
        )

    st.caption(MANDATORY_FIELD_LEGEND)

    if st.button("List Product & Pay Lender Fee", type="primary"):
        if not photos or len(photos) < 3:
            st.error("You must upload at least 3 photos.")
        elif not title.strip() or not desc.strip():
            st.error("Title and Description are required.")
        elif not reason.strip():
            st.error("Reason for renting out is required.")
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

    # --- Active Address Selection Bar for Instant "Order Now" Actions ---
    selected_order_address = render_order_address_selector(
        conn,
        user_id,
        widget_key="borrower_portal_order_address",
        label="📍 Selected Address for Direct Orders (from your Address Book) :red[*]",
    )
    if selected_order_address is None:
        addr_warn_col, addr_btn_col = st.columns([4, 1.5])
        with addr_warn_col:
            st.warning(
                "Your **Address Book** is currently empty. Create an address before placing an order."
            )
        with addr_btn_col:
            st.button(
                "➕ Create Address",
                key="borrower_empty_addr_btn",
                use_container_width=True,
                on_click=navigate_to_page,
                args=("Address Book",),
            )

    st.divider()

    # --- Sidebar Filters ---
    st.sidebar.subheader("Filters")
    categories = ["All"] + [
        row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    ]
    selected_cat = st.sidebar.selectbox(
        "Category",
        categories,
        placeholder="Choose a category",
    )
    search_term = st.sidebar.text_input(
        "Search",
        placeholder="Search by title or description",
    )

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
            placeholder="Filter by gender/audience",
            key=f"gender_filter_{selected_cat}",
            help="Filter gender-specific items (clothing, footwear, makeup, accessories, self-care) by target audience.",
        )
    else:
        st.sidebar.selectbox(
            "Gender / Audience",
            options=["Not Applicable (Gender Neutral)"],
            disabled=True,
            placeholder="Not Applicable (Gender Neutral)",
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
        placeholder="Select sort order",
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
                        if selected_order_address is None:
                            conn.close()
                            redirect_to_address_book(return_page="Borrower Portal")
                        else:
                            ok, outcome = execute_order(
                                conn, user_id, [dict(p)], selected_order_address
                            )
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
            args=("Shopping Cart",),
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
        args=("Borrower Portal",),
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
        "Review the items in your shopping cart below, select an address from your Address Book, and check out all products at once."
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

    # Consolidated Order Summary & Address Selection
    total_rental_price = sum(float(i["rent_price"]) for i in items)
    total_fees, discount_pct, discount_amt, final_fee = calculate_fee_breakdown(
        conn, user_id, items
    )

    st.subheader("Order Summary & Address Selection")
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

    st.write("")
    selected_cart_address = render_order_address_selector(
        conn,
        user_id,
        widget_key="cart_checkout_address",
        label="📍 Choose 1 Address from Your Address Book for This Order :red[*]",
    )

    if selected_cart_address is None:
        st.warning(
            "Your Address Book is empty. Please create an address before checking out."
        )
        c_create, c_clear, _ = st.columns([1.8, 1.2, 3])
        with c_create:
            if st.button(
                "Create Address to Checkout",
                type="primary",
                key="cart_create_address_btn",
            ):
                conn.close()
                redirect_to_address_book(return_page="Shopping Cart")
        with c_clear:
            if st.button("Clear Shopping Cart"):
                clear_shopping_list(user_id)
                st.rerun()
    else:
        c_checkout, c_manage_addr, c_clear, _ = st.columns([1.8, 1.4, 1.2, 1.6])
        with c_checkout:
            if st.button("Checkout All Products & Pay Fee", type="primary"):
                ok, outcome = execute_order(
                    conn, user_id, items, selected_cart_address
                )
                if ok:
                    st.session_state["last_checkout_emails"] = outcome
                    st.rerun()
                else:
                    st.error(outcome)

        with c_manage_addr:
            st.button(
                "Manage Address Book",
                key="cart_manage_addr_btn",
                on_click=navigate_to_page,
                args=("Address Book",),
            )

        with c_clear:
            if st.button("Clear Shopping Cart"):
                clear_shopping_list(user_id)
                st.rerun()

    conn.close()


def address_book_portal():
    """Manage the logged-in user's Address Book, plus Admin overview of all users' Address Books."""
    user = st.session_state["user"]
    user_id = user["id"]
    is_admin = bool(user["is_admin"])

    st.title("📒 Address Book")

    if st.session_state.pop("address_required_prompt", False):
        st.warning(
            "📍 **Address Required:** Your Address Book is empty. Please add an address below before placing your order."
        )

    conn = get_db()
    my_addresses = get_user_addresses(conn, user_id)

    return_target = st.session_state.get("return_after_address")
    if return_target and len(my_addresses) > 0:
        if st.button(
            f"← Return to {return_target} to Complete Your Order",
            type="primary",
            key="return_after_addr_btn",
        ):
            target = st.session_state.pop("return_after_address")
            conn.close()
            update_session_page(st.session_state.get("session_token"), target)
            st.session_state["pending_nav_target"] = target
            st.rerun()
    else:
        st.button(
            "← Back to Borrower Portal",
            key="addr_back_to_browse",
            on_click=navigate_to_page,
            args=("Borrower Portal",),
        )

    st.subheader(f"My Saved Addresses ({user['username']})")
    st.caption(
        "Address Label (defaults to Home) and Landmark are optional. "
        "When multiple addresses exist, you can optionally mark any 1 address as your Default."
    )

    if "addr_form_ver" not in st.session_state:
        st.session_state["addr_form_ver"] = 0
    fver = st.session_state["addr_form_ver"]

    with st.expander("➕ Add a New Address", expanded=(len(my_addresses) == 0)):
        lbl_col1, lbl_col2 = st.columns([1.2, 2.8])
        with lbl_col1:
            selected_label_choice = st.selectbox(
                "Address Label (Optional)",
                options=ADDRESS_LABEL_OPTIONS,
                index=0,
                placeholder="Select label (Home, Office, Other)",
                key=f"addr_label_select_{fver}",
                help="Defaults to Home. Choose 'Other' to enter a custom label.",
            )
        with lbl_col2:
            if selected_label_choice == "Other":
                custom_label_input = st.text_input(
                    "Specify Custom Address Label (Optional)",
                    placeholder="e.g., Shared, Guest, Secondary",
                    key=f"addr_custom_label_{fver}",
                )
            else:
                custom_label_input = ""

        a1, a2 = st.columns(2)
        with a1:
            recipient_name = st.text_input(
                "Recipient Name :red[*]",
                value="",
                placeholder="e.g., Full Name",
                key=f"addr_recipient_{fver}",
            )
            house_no = st.text_input(
                "House No. :red[*]",
                placeholder="e.g., Building 1, Unit 2",
                key=f"addr_house_no_{fver}",
            )
            street_address = st.text_area(
                "Street Address :red[*]",
                placeholder="e.g., Sample Street, Suite 100",
                key=f"addr_street_{fver}",
            )
        with a2:
            landmark = st.text_input(
                "Landmark (Optional)",
                placeholder="e.g., Near the main square, Opposite the park",
                key=f"addr_landmark_{fver}",
            )
            city = st.text_input(
                "City :red[*]",
                placeholder="e.g., Example City",
                key=f"addr_city_{fver}",
            )
            state_postal = st.text_input(
                "State / Postal Code :red[*]",
                placeholder="e.g., XX 00000",
                key=f"addr_state_postal_{fver}",
            )
            phone = st.text_input(
                "Contact Phone :red[*]",
                value="",
                placeholder="e.g., +1 (555) 000-0000",
                key=f"addr_phone_{fver}",
            )

        set_as_default = st.checkbox(
            "Set as my default address (optional)",
            value=False,
            key=f"addr_is_default_{fver}",
            help="Only 1 address can be marked as Default at a time.",
        )

        st.caption(MANDATORY_FIELD_LEGEND)

        if st.button("Save Address", type="primary", key=f"save_addr_btn_{fver}"):
            missing_fields = []
            if not recipient_name.strip():
                missing_fields.append("Recipient Name")
            if not house_no.strip():
                missing_fields.append("House No.")
            if not street_address.strip():
                missing_fields.append("Street Address")
            if not city.strip():
                missing_fields.append("City")
            if not state_postal.strip():
                missing_fields.append("State / Postal Code")
            if not phone.strip():
                missing_fields.append("Contact Phone")

            if missing_fields:
                st.error(
                    f"Please fill in all mandatory fields: {', '.join(missing_fields)}."
                )
            else:
                add_user_address(
                    conn,
                    user_id=user_id,
                    label=selected_label_choice,
                    custom_label=custom_label_input if selected_label_choice == "Other" else "",
                    recipient_name=recipient_name,
                    house_no=house_no,
                    street_address=street_address,
                    landmark=landmark,
                    city=city,
                    state_postal=state_postal,
                    phone=phone,
                    set_default=set_as_default,
                )
                st.session_state["addr_form_ver"] = fver + 1
                st.session_state["toast_msg"] = "Address saved to your Address Book!"
                st.rerun()

    if not my_addresses:
        st.info(
            "You have no saved addresses yet. Use the form above to create your first address."
        )
    else:
        for addr in my_addresses:
            is_def = bool(addr["is_default"])
            with st.container():
                c_details, c_actions = st.columns([3.5, 1.5])
                with c_details:
                    badge = " ⭐ **DEFAULT ADDRESS**" if is_def else ""
                    lbl_type, custom_text = extract_label_parts(addr)
                    heading_label = (
                        f"Other — {custom_text}"
                        if lbl_type == "Other" and custom_text
                        else lbl_type
                    )
                    st.markdown(f"#### {heading_label}{badge}")
                    if addr["recipient_name"]:
                        st.write(f"**Recipient:** {addr['recipient_name']}")
                    house_val = addr["house_no"] if "house_no" in addr.keys() else ""
                    if house_val:
                        st.write(f"**House No.:** {house_val}")
                    st.write(f"**Street Address:** {addr['street_address']}")
                    landmark_val = addr["landmark"] if "landmark" in addr.keys() else ""
                    if landmark_val:
                        st.write(f"**Landmark:** {landmark_val}")
                    city_zip = " ".join(
                        p
                        for p in (addr["city"] or "", addr["state_postal"] or "")
                        if p.strip()
                    )
                    if city_zip:
                        st.write(f"**City / Postal:** {city_zip}")
                    if addr["phone"]:
                        st.write(f"**Phone:** {addr['phone']}")

                with c_actions:
                    st.write("")
                    if not is_def:
                        if st.button(
                            "Set as Default",
                            key=f"set_def_addr_{addr['id']}",
                            use_container_width=True,
                        ):
                            set_default_address(conn, user_id, addr["id"])
                            st.rerun()
                    else:
                        if st.button(
                            "Unset Default",
                            key=f"unset_def_addr_{addr['id']}",
                            use_container_width=True,
                        ):
                            clear_default_address(conn, user_id)
                            st.rerun()

                    if st.button(
                        "Delete",
                        key=f"del_addr_{addr['id']}",
                        use_container_width=True,
                    ):
                        delete_user_address(conn, user_id, addr["id"])
                        st.rerun()
                st.divider()

    # --- Admin Section: View All Address Books Across All Users (Regular & Admin) ---
    if is_admin:
        st.divider()
        render_admin_address_books_section(conn, key_prefix="addr_book_admin")

    conn.close()


def order_history_portal():
    """Role-aware Order History view: personal orders for regular users, all users + user types for admins."""
    user = st.session_state["user"]
    user_id = user["id"]
    is_admin = bool(user["is_admin"])

    st.title("📜 Order History")
    st.button(
        "← Back to Borrower Portal",
        key="orders_back_to_browse",
        on_click=navigate_to_page,
        args=("Borrower Portal",),
    )

    conn = get_db()

    if is_admin:
        st.caption(
            "Administrator View: Showing order histories across all registered users and administrators."
        )
        orders = conn.execute(
            """
            SELECT o.id,
                   o.borrower_id,
                   o.total_fee,
                   o.items_summary,
                   o.selected_address,
                   o.created_at,
                   u.username AS borrower_username,
                   u.email AS borrower_email,
                   u.is_admin AS borrower_is_admin
            FROM orders o
            LEFT JOIN users u ON o.borrower_id = u.id
            ORDER BY o.created_at DESC, o.id DESC
            """
        ).fetchall()

        if not orders:
            st.info("No orders have been placed on the platform yet.")
            conn.close()
            return

        total_orders = len(orders)
        admin_orders = sum(1 for o in orders if bool(o["borrower_is_admin"]))
        regular_orders = total_orders - admin_orders
        total_fees_collected = sum(float(o["total_fee"] or 0.0) for o in orders)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders", total_orders)
        m2.metric("Regular User Orders", regular_orders)
        m3.metric("Admin Orders", admin_orders)
        m4.metric("Total Convenience Fees", f"${total_fees_collected:.2f}")

        f1, f2 = st.columns(2)
        with f1:
            role_filter = st.selectbox(
                "Filter by User Type",
                ["All Users", "Regular", "Admin"],
                placeholder="Select user type",
                key="admin_order_role_filter",
            )
        with f2:
            usernames = ["All"] + sorted(
                {o["borrower_username"] or "Unknown User" for o in orders}
            )
            user_filter = st.selectbox(
                "Filter by Username",
                usernames,
                placeholder="Select username",
                key="admin_order_user_filter",
            )

        filtered_orders = []
        for o in orders:
            u_type = "Admin" if bool(o["borrower_is_admin"]) else "Regular"
            u_name = o["borrower_username"] or "Unknown User"
            if role_filter != "All Users" and u_type != role_filter:
                continue
            if user_filter != "All" and u_name != user_filter:
                continue
            filtered_orders.append(o)

        if not filtered_orders:
            st.info("No orders match the selected filters.")
            conn.close()
            return

        table_rows = []
        for o in filtered_orders:
            u_type = "Admin" if bool(o["borrower_is_admin"]) else "Regular"
            u_name = o["borrower_username"] or "Unknown User"
            table_rows.append(
                {
                    "Order #": o["id"],
                    "User": u_name,
                    "User Type": u_type,
                    "Items Ordered": o["items_summary"] or "—",
                    "Selected Address": o["selected_address"] or "—",
                    "Convenience Fee Paid ($)": round(float(o["total_fee"] or 0.0), 2),
                    "Order Date": o["created_at"],
                }
            )
        st.subheader("All Users Order Overview")
        st.dataframe(table_rows, width="stretch", hide_index=True)

        st.subheader("Detailed Order Receipts")
        for o in filtered_orders:
            u_type = "Admin" if bool(o["borrower_is_admin"]) else "Regular"
            u_name = o["borrower_username"] or "Unknown User"
            header = (
                f"Order #{o['id']} — {u_name} ({u_type} User) | "
                f"Fee Paid: ${float(o['total_fee'] or 0.0):.2f} | {o['created_at']}"
            )
            with st.expander(header, expanded=False):
                st.write(
                    f"**Ordered By:** {u_name} | **User Type:** `{u_type}` | "
                    f"**Email:** {o['borrower_email'] or 'Not provided'}"
                )
                if o["selected_address"]:
                    st.write(f"**Selected Order Address:** {o['selected_address']}")

                line_items = conn.execute(
                    """
                    SELECT oi.*, u.username AS lender_name, u.email AS lender_email,
                           u.address AS lender_address, u.phone AS lender_phone
                    FROM order_items oi
                    LEFT JOIN users u ON oi.lender_id = u.id
                    WHERE oi.order_id = ?
                    """,
                    (o["id"],),
                ).fetchall()

                if line_items:
                    for li in line_items:
                        st.markdown(
                            f"- **{li['product_title']}** ({li['category']} · {li['target_gender']}) — "
                            f"Rental Price: `${float(li['rent_price']):.2f}` | "
                            f"Convenience Fee: `${float(li['borrower_fee']):.2f}` | "
                            f"Lender: `{li['lender_name'] or 'Lender'}`"
                        )
                else:
                    st.write(f"**Items Summary:** {o['items_summary'] or 'Details unavailable'}")

    else:
        st.caption(
            f"Showing order history for **{user['username']}** (`Regular` user)."
        )
        orders = conn.execute(
            """
            SELECT id, total_fee, items_summary, selected_address, created_at
            FROM orders
            WHERE borrower_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

        if not orders:
            st.info(
                "You haven't placed any orders yet. Browse the **Borrower Portal** to rent your first item!"
            )
            conn.close()
            return

        total_spent_fees = sum(float(o["total_fee"] or 0.0) for o in orders)
        m1, m2 = st.columns(2)
        m1.metric("Your Total Orders", len(orders))
        m2.metric("Total Convenience Fees Paid", f"${total_spent_fees:.2f}")

        st.divider()
        for o in orders:
            header = (
                f"Order #{o['id']} — {o['items_summary'] or 'Rental Order'} | "
                f"Fee Paid: ${float(o['total_fee'] or 0.0):.2f} | {o['created_at']}"
            )
            with st.expander(header, expanded=True):
                if o["selected_address"]:
                    st.write(f"**Your Selected Order Address:** {o['selected_address']}")

                line_items = conn.execute(
                    """
                    SELECT oi.*, u.username AS lender_name, u.email AS lender_email,
                           u.address AS lender_address, u.phone AS lender_phone
                    FROM order_items oi
                    LEFT JOIN users u ON oi.lender_id = u.id
                    WHERE oi.order_id = ?
                    """,
                    (o["id"],),
                ).fetchall()

                if line_items:
                    for li in line_items:
                        st.markdown(
                            f"**{li['product_title']}** ({li['category']} · {li['target_gender']})\n"
                            f"- Rental Price (payable at pickup): `${float(li['rent_price']):.2f}` | "
                            f"Convenience Fee: `${float(li['borrower_fee']):.2f}`\n"
                            f"- Lender Contact: **{li['lender_name'] or 'Lender'}** | "
                            f"Email: `{li['lender_email'] or 'Not provided'}` | "
                            f"Phone: `{li['lender_phone'] or 'Not provided'}` | "
                            f"Pickup Address: {li['lender_address'] or 'Not provided'}"
                        )
                        st.write("---")
                else:
                    st.write(f"**Items Ordered:** {o['items_summary'] or 'Details unavailable'}")
                st.write(f"**Total Convenience Fee Paid:** ${float(o['total_fee'] or 0.0):.2f}")

    conn.close()


def _on_nav_radio_change():
    new_page = st.session_state["nav_radio"]
    st.session_state["active_page"] = new_page
    update_session_page(st.session_state.get("session_token"), new_page)


# --- Main App Routing ---
def main():
    st.set_page_config(page_title="RentItApp", layout="wide")
    init_db()
    ensure_demo_data()

    if st.session_state.get("toast_msg"):
        st.toast(st.session_state.pop("toast_msg"))

    # Restore authenticated session across browser refreshes via URL session token
    if "user" not in st.session_state:
        url_token = st.query_params.get("session")
        if isinstance(url_token, list):
            url_token = url_token[0] if url_token else None
        if url_token:
            restored_user, saved_page = get_user_by_session_token(url_token)
            if restored_user:
                st.session_state["user"] = restored_user
                st.session_state["session_token"] = url_token
                st.session_state["active_page"] = saved_page
                st.session_state["nav_radio"] = saved_page
            else:
                st.query_params.pop("session", None)

    if "user" not in st.session_state:
        auth_view()
    else:
        user = st.session_state["user"]
        is_admin = bool(user["is_admin"])

        # Keep query parameter synchronized on subsequent widget reruns
        session_token = st.session_state.get("session_token")
        if session_token and st.query_params.get("session") != session_token:
            st.query_params["session"] = session_token

        st.sidebar.write(f"Welcome, **{user['username']}**")
        if st.sidebar.button("Logout"):
            delete_user_session(session_token)
            st.query_params.pop("session", None)
            del st.session_state["user"]
            st.session_state.pop("session_token", None)
            st.session_state.pop("active_page", None)
            st.session_state.pop("nav_radio", None)
            st.session_state.pop("pending_nav_target", None)
            st.rerun()

        st.sidebar.divider()

        list_count = get_shopping_list_count(user["id"])
        order_count = get_order_count(user["id"], is_admin)
        addr_count = get_address_count(user["id"])

        # Navigation available to registered users and admins
        options = [
            "Borrower Portal",
            "Shopping Cart",
            "Order History",
            "Address Book",
            "Lender Portal",
        ]
        if is_admin:
            options.append("Admin Portal")

        # Apply any queued navigation redirect BEFORE instantiating nav_radio
        if "pending_nav_target" in st.session_state:
            target = st.session_state.pop("pending_nav_target")
            if target in options:
                st.session_state["active_page"] = target
                st.session_state["nav_radio"] = target
                update_session_page(session_token, target)

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

        # Top-right header bar: Address Book, Order History, and Shopping Cart
        hdr_left, hdr_addr, hdr_orders, hdr_cart = st.columns([4.2, 1.5, 1.4, 1.4])
        with hdr_left:
            st.caption("RentItApp · Peer-to-Peer Rental Marketplace")
        with hdr_addr:
            st.button(
                f"📒 Addresses ({addr_count})",
                key="top_right_addr_btn",
                help="Manage your saved addresses",
                use_container_width=True,
                type="secondary",
                on_click=navigate_to_page,
                args=("Address Book",),
            )
        with hdr_orders:
            st.button(
                f"📜 Orders ({order_count})",
                key="top_right_orders_btn",
                help="View your order history" if not is_admin else "View order history for all users",
                use_container_width=True,
                type="secondary",
                on_click=navigate_to_page,
                args=("Order History",),
            )
        with hdr_cart:
            st.button(
                f"🛒 Cart ({list_count})",
                key="top_right_cart_btn",
                help="Click to view your Shopping Cart and check out",
                use_container_width=True,
                type="primary" if list_count > 0 else "secondary",
                on_click=navigate_to_page,
                args=("Shopping Cart",),
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
        elif choice == "Order History":
            order_history_portal()
        elif choice == "Address Book":
            address_book_portal()
        elif choice == "Lender Portal":
            lender_portal()
        elif choice == "Admin Portal":
            admin_portal()


if __name__ == "__main__":
    main()