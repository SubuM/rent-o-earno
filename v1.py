import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime
import json
import base64

# --- Database Initialization ---
DB_NAME = "rental_app.db"
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
        is_available BOOLEAN DEFAULT 1,
        updated_at DATETIME,
        FOREIGN KEY(lender_id) REFERENCES users(id)
    )''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrower_id INTEGER,
        total_fee REAL,
        created_at DATETIME,
        FOREIGN KEY(borrower_id) REFERENCES users(id)
    )''')
    
    # Default Admin & Settings (credentials live in .streamlit/secrets.toml)
    admin_username = st.secrets["admin"]["username"]
    admin_password = st.secrets["admin"]["password"]
    c.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)", 
              (admin_username, hash_pw(admin_password), 1))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("loyalty_discount_pct", "10.0"))
    
    conn.commit()
    conn.close()

# --- Authentication Helpers ---
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_pw(password))).fetchone()
    conn.close()
    return user

def is_lender(user_id):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM products WHERE lender_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return count > 0

# --- File Upload Helper ---
def save_uploaded_files(uploaded_files):
    file_paths = []
    for f in uploaded_files:
        file_path = os.path.join(UPLOAD_DIR, f.name)
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
                st.session_state['user'] = dict(user)
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
                conn = get_db()
                try:
                    conn.execute("INSERT INTO users (username, password, email, address, phone) VALUES (?, ?, ?, ?, ?)",
                                 (new_user, hash_pw(new_pw), email, address, phone))
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
    with st.form("add_category_form"):
        cat_name = st.text_input("Category Name")
        lender_fee = st.number_input("Lender Convenience Fee ($)", min_value=0.0, step=0.5)
        borrower_fee = st.number_input("Borrower Convenience Fee ($)", min_value=0.0, step=0.5)
        if st.form_submit_button("Add/Update Category"):
            conn.execute("INSERT OR REPLACE INTO categories (name, lender_fee, borrower_fee) VALUES (?, ?, ?)", 
                         (cat_name, lender_fee, borrower_fee))
            conn.commit()
            st.success(f"Category '{cat_name}' saved.")
            
    st.subheader("Manage Global Discounts")
    current_discount = conn.execute("SELECT value FROM settings WHERE key = 'loyalty_discount_pct'").fetchone()[0]
    with st.form("discount_form"):
        new_discount = st.number_input("Loyalty Discount (%) for Lender-Borrowers", value=float(current_discount), min_value=0.0, max_value=100.0)
        if st.form_submit_button("Update Discount"):
            conn.execute("UPDATE settings SET value = ? WHERE key = 'loyalty_discount_pct'", (str(new_discount),))
            conn.commit()
            st.success("Discount updated.")
    conn.close()

def lender_portal():
    st.title("Lender Portal")
    st.write("List your extra items for rent.")
    
    conn = get_db()
    categories = [row['name'] for row in conn.execute("SELECT name FROM categories").fetchall()]
    
    if not categories:
        st.warning("No categories available. Please ask an admin to add categories.")
        return
        
    with st.form("add_product_form"):
        title = st.text_input("Product Title")
        desc = st.text_area("A few lines about the product")
        category = st.selectbox("Category", categories)
        rent_price = st.number_input("Rental Price ($)", min_value=0.0, step=1.0)
        reason = st.text_input("Reason for renting out")
        
        photos = st.file_uploader("Upload Photos (Minimum 3 required)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        is_consumable = st.checkbox("Is this a consumable product?")
        mfg_date = st.date_input("Manufacturing Date", disabled=not is_consumable)
        exp_date = st.date_input("Expiry Date", disabled=not is_consumable)
        
        usage_status = st.radio("Condition", ["Used", "Unused/New"])
        usage_duration = st.text_input("Usage Duration (if used)", disabled=(usage_status=="Unused/New"))
        purchase_date = st.date_input("Purchase Date (if new)", disabled=(usage_status=="Used"))
        
        submitted = st.form_submit_button("List Product & Pay Lender Fee")
        
        if submitted:
            if len(photos) < 3:
                st.error("You must upload at least 3 photos.")
            elif not title or not desc:
                st.error("Title and Description are required.")
            else:
                lender_fee = conn.execute("SELECT lender_fee FROM categories WHERE name = ?", (category,)).fetchone()[0]
                
                # Mock Payment
                st.success(f"Mock Payment Processed: ${lender_fee:.2f} convenience fee paid.")
                
                photo_paths = save_uploaded_files(photos)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                conn.execute('''INSERT INTO products 
                    (lender_id, title, description, category, rent_price, photos, is_consumable, 
                     mfg_date, exp_date, rent_reason, usage_status, usage_duration, purchase_date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (st.session_state['user']['id'], title, desc, category, rent_price, photo_paths, 
                     is_consumable, str(mfg_date), str(exp_date), reason, usage_status, usage_duration, str(purchase_date), now))
                conn.commit()
                st.success("Product successfully listed for rent!")
    conn.close()

def borrower_portal():
    st.title("Borrower Portal")
    conn = get_db()
    
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []
    
    # Filters
    st.sidebar.subheader("Filters")
    categories = ["All"] + [row['name'] for row in conn.execute("SELECT name FROM categories").fetchall()]
    selected_cat = st.sidebar.selectbox("Category", categories)
    search_term = st.sidebar.text_input("Search")
    sort_by = st.sidebar.selectbox("Sort By", ["Last Updated (Default)", "Price: Low to High", "Price: High to Low"])
    
    # Query building
    query = "SELECT p.*, c.borrower_fee FROM products p JOIN categories c ON p.category = c.name WHERE p.is_available = 1"
    params = []
    
    if selected_cat != "All":
        query += " AND p.category = ?"
        params.append(selected_cat)
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
    
    # Display Products
    if not products:
        st.info("No products available matching your criteria.")
    
    for p in products:
        with st.container():
            col1, col2 = st.columns([1, 3])
            photos = json.loads(p['photos'])
            with col1:
                if photos:
                    st.image(photos[0], width="stretch")
            with col2:
                st.subheader(p['title'])
                st.write(f"**Price:** ${p['rent_price']:.2f} | **Category:** {p['category']}")
                st.write(p['description'])
                if st.button(f"Add to Order", key=f"add_{p['id']}"):
                    if p['id'] not in [item['id'] for item in st.session_state['cart']]:
                        st.session_state['cart'].append(dict(p))
                        st.success("Added to order!")
            st.divider()
            
    # Cart & Checkout
    if st.session_state['cart']:
        st.sidebar.subheader("Your Order")
        total_borrower_fees = 0.0
        for item in st.session_state['cart']:
            st.sidebar.write(f"- {item['title']} (Fee: ${item['borrower_fee']:.2f})")
            total_borrower_fees += item['borrower_fee']
            
        discount_pct = 0.0
        if is_lender(st.session_state['user']['id']):
            discount_pct = float(conn.execute("SELECT value FROM settings WHERE key = 'loyalty_discount_pct'").fetchone()[0])
            
        discount_amount = total_borrower_fees * (discount_pct / 100.0)
        final_fee = total_borrower_fees - discount_amount
        
        st.sidebar.write("---")
        st.sidebar.write(f"Total Fees: ${total_borrower_fees:.2f}")
        if discount_pct > 0:
            st.sidebar.write(f"Loyalty Discount ({discount_pct}%): -${discount_amount:.2f}")
        st.sidebar.write(f"**Final Convenience Fee: ${final_fee:.2f}**")
        
        if st.sidebar.button("Checkout & Pay Fee"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (borrower_id, total_fee, created_at) VALUES (?, ?, ?)", 
                           (st.session_state['user']['id'], final_fee, now))
            order_id = cursor.lastrowid
            
            emails_to_send = []
            for item in st.session_state['cart']:
                cursor.execute("UPDATE products SET is_available = 0 WHERE id = ?", (item['id'],))
                lender = conn.execute("SELECT email, address, phone FROM users WHERE id = ?", (item['lender_id'],)).fetchone()
                emails_to_send.append(f"Item: {item['title']}\nLender Email: {lender['email']}\nAddress: {lender['address']}\nPhone: {lender['phone']}")
                
            conn.commit()
            
            # Mock Email Dispatch
            st.sidebar.success(f"Payment of ${final_fee:.2f} successful!")
            st.info("📨 **MOCK EMAIL SENT TO YOU:**\n\n" + "\n\n---\n\n".join(emails_to_send))
            
            st.session_state['cart'] = []
            st.rerun()

    conn.close()

# --- Main App Routing ---
def main():
    st.set_page_config(page_title="RentItApp", layout="wide")
    init_db()
    
    if 'user' not in st.session_state:
        auth_view()
    else:
        st.sidebar.write(f"Welcome, **{st.session_state['user']['username']}**")
        if st.sidebar.button("Logout"):
            del st.session_state['user']
            st.rerun()
            
        st.sidebar.divider()
        
        # Navigation based on role
        options = ["Borrower Portal", "Lender Portal"]
        if st.session_state['user']['is_admin']:
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