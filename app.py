import streamlit as st
import pandas as pd
import numpy as np
import time
import datetime
import hashlib
import json
import os
import shutil
import zipfile
from PIL import Image
import fpdf as FPDF
import io
import base64
import uuid
import serial
import serial.tools.list_ports
import subprocess
import threading
import platform
import pytz
from datetime import timedelta

# Constants
DATA_DIR = "data"
BACKUP_DIR = "backups"
TEMPLATE_DIR = "templates"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")
DISCOUNTS_FILE = os.path.join(DATA_DIR, "discounts.json")
OFFERS_FILE = os.path.join(DATA_DIR, "offers.json")
LOYALTY_FILE = os.path.join(DATA_DIR, "loyalty.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SUPPLIERS_FILE = os.path.join(DATA_DIR, "suppliers.json")
SHIFTS_FILE = os.path.join(DATA_DIR, "shifts.json")
CASH_DRAWER_FILE = os.path.join(DATA_DIR, "cash_drawer.json")
RETURNS_FILE = os.path.join(DATA_DIR, "returns.json")

# Authentication functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    users = load_data(USERS_FILE)
    if username in users:
        if users[username]["password"] == hash_password(password):
            return users[username]
    return None

def get_current_user_role():
    if 'user_info' in st.session_state:
        return st.session_state.user_info.get('role')
    return None

def is_admin():
    return get_current_user_role() == 'admin'

def is_manager():
    return get_current_user_role() in ['admin', 'manager']

def is_cashier():
    return get_current_user_role() in ['admin', 'manager', 'cashier']

# Ensure data and template directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# Data loading and saving functions
def load_data(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data, file):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize empty data files if they don't exist
def initialize_empty_data():
    default_data = {
        USERS_FILE: {
            "admin": {
                "username": "admin",
                "password": hash_password("admin123"),
                "role": "admin",
                "full_name": "Administrator",
                "email": "admin@supermarket.com",
                "active": True,
                "date_created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": "system"
            }
        },
        PRODUCTS_FILE: {},
        INVENTORY_FILE: {},
        TRANSACTIONS_FILE: {},
        DISCOUNTS_FILE: {},
        OFFERS_FILE: {},
        LOYALTY_FILE: {
            "tiers": {},
            "customers": {},
            "rewards": {}
        },
        CATEGORIES_FILE: {
            "categories": [],
            "subcategories": {}
        },
        SETTINGS_FILE: {
            "store_name": "Supermarket POS",
            "store_address": "",
            "store_phone": "",
            "store_email": "",
            "store_logo": "",
            "tax_rate": 0.0,
            "tax_inclusive": False,
            "receipt_template": "Simple",
            "theme": "Light",
            "session_timeout": 30,
            "printer_name": "Browser Printer",
            "barcode_scanner": "keyboard",
            "timezone": "UTC",
            "currency_symbol": "$",
            "decimal_places": 2,
            "auto_logout": True,
            "cash_drawer_enabled": False,
            "cash_drawer_command": "",
            "barcode_scanner_port": "auto",
            "receipt_header": "",
            "receipt_footer": "",
            "receipt_print_logo": False
        },
        SUPPLIERS_FILE: {},
        SHIFTS_FILE: {},
        CASH_DRAWER_FILE: {
            "current_balance": 0.0,
            "transactions": []
        },
        RETURNS_FILE: {}
    }
    
    for file, data in default_data.items():
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump(data, f, indent=4)

initialize_empty_data()

# Hardware functions
def get_available_printers():
    printers = []
    try:
        if platform.system() == "Windows":
            try:
                result = subprocess.run(['wmic', 'printer', 'get', 'name'], capture_output=True, text=True)
                if result.returncode == 0:
                    printers = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            except:
                pass
        else:
            try:
                result = subprocess.run(['lpstat', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    printers = [line.split()[0] for line in result.stdout.splitlines()]
            except:
                pass
    except:
        printers = ["No printers found"]
    return printers if printers else ["No printers found"]

def get_available_com_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports] + ["auto"]

def print_receipt(receipt_text):
    settings = load_data(SETTINGS_FILE)
    
    # 1. Browser-based printing
    try:
        js = f"""
        <script>
        function printReceipt() {{
            var win = window.open('', '', 'height=400,width=600');
            win.document.write(`<pre>{receipt_text}</pre>`);
            win.document.close();
            win.print();
        }}
        printReceipt();
        </script>
        """
        st.components.v1.html(js, height=0)
        return True
    except:
        pass
    
    # 2. PDF fallback
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, receipt_text)
        pdf_path = "receipt.pdf"
        pdf.output(pdf_path)
        with open(pdf_path, "rb") as f:
            st.download_button("Download Receipt (PDF)", f, "receipt.pdf")
        return True
    except Exception as e:
        st.error(f"Printing failed: {str(e)}")
        return False

def open_cash_drawer():
    settings = load_data(SETTINGS_FILE)
    if not settings.get('cash_drawer_enabled', False):
        return False
    
    command = settings.get('cash_drawer_command', '')
    if not command:
        return False
    
    try:
        subprocess.run(command, shell=True)
        return True
    except Exception as e:
        st.error(f"Failed to open cash drawer: {str(e)}")
        return False

# Improved Barcode Scanner
class BarcodeScanner:
    def __init__(self):
        self.scanner = None
        self.scanner_thread = None
        self.running = False
        self.last_barcode = ""
        self.last_scan_time = 0
        self.scan_buffer = ""
    
    def init_serial_scanner(self, port='auto'):
        if port == 'auto':
            ports = serial.tools.list_ports.comports()
            if not ports:
                st.warning("No serial ports found")
                return False
            port = ports[0].device
        
        try:
            self.scanner = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            return True
        except Exception as e:
            st.error(f"Failed to open serial port {port}: {str(e)}")
            return False
    
    def start_serial_scanning(self):
        self.running = True
        while self.running:
            try:
                if self.scanner.in_waiting > 0:
                    data = self.scanner.readline().decode('utf-8').strip()
                    if data:
                        self.last_barcode = data
                        self.last_scan_time = time.time()
                        st.session_state.scanned_barcode = data
            except Exception as e:
                time.sleep(0.1)
    
    def stop_scanning(self):
        self.running = False
        if self.scanner and hasattr(self.scanner, 'close'):
            self.scanner.close()
        if self.scanner_thread and self.scanner_thread.is_alive():
            self.scanner_thread.join()
    
    def get_barcode(self):
        if time.time() - self.last_scan_time < 1:  # 1 second debounce
            barcode = self.last_barcode
            self.last_barcode = ""
            return barcode
        return None

# Initialize barcode scanner
barcode_scanner = BarcodeScanner()

def setup_barcode_scanner():
    settings = load_data(SETTINGS_FILE)
    scanner_type = settings.get('barcode_scanner', 'keyboard')
    port = settings.get('barcode_scanner_port', 'auto')
    
    if scanner_type == 'serial':
        if barcode_scanner.init_serial_scanner(port):
            barcode_scanner.scanner_thread = threading.Thread(
                target=barcode_scanner.start_serial_scanning, 
                daemon=True
            )
            barcode_scanner.scanner_thread.start()
            st.session_state.barcode_scanner_setup = True
            st.session_state.scanner_status = "Connected"
        else:
            st.session_state.scanner_status = "Disconnected"
    else:
        st.session_state.scanner_status = "Keyboard Mode"

# Backup and Restore functions
def create_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"pos_backup_{timestamp}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    with zipfile.ZipFile(backup_path, 'w') as zipf:
        for root, _, files in os.walk(DATA_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, DATA_DIR))
    
    return backup_path

def restore_backup(backup_file):
    with zipfile.ZipFile(backup_file, 'r') as zipf:
        zipf.extractall(DATA_DIR)
    return True

# Utility functions
def generate_barcode():
    return str(uuid.uuid4().int)[:12]

def generate_short_id():
    return str(uuid.uuid4())[:8]

def format_currency(amount):
    settings = load_data(SETTINGS_FILE)
    symbol = settings.get('currency_symbol', '$')
    decimals = settings.get('decimal_places', 2)
    return f"{symbol}{amount:.{decimals}f}"

def get_current_datetime():
    settings = load_data(SETTINGS_FILE)
    tz = pytz.timezone(settings.get('timezone', 'UTC'))
    return datetime.datetime.now(tz)

# Session state initialization
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Login"
if 'shift_started' not in st.session_state:
    st.session_state.shift_started = False
if 'shift_id' not in st.session_state:
    st.session_state.shift_id = None
if 'last_activity' not in st.session_state:
    st.session_state.last_activity = time.time()
if 'barcode_scanner_setup' not in st.session_state:
    st.session_state.barcode_scanner_setup = False
if 'scanned_barcode' not in st.session_state:
    st.session_state.scanned_barcode = None
if 'scanner_status' not in st.session_state:
    st.session_state.scanner_status = "Not Connected"
if 'pos_mode' not in st.session_state:
    st.session_state.pos_mode = 'scan'
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = None
if 'selected_subcategory' not in st.session_state:
    st.session_state.selected_subcategory = None
if 'return_reason' not in st.session_state:
    st.session_state.return_reason = ""

# Setup barcode scanner if not already done
if not st.session_state.barcode_scanner_setup:
    setup_barcode_scanner()

# Login Page
def login_page():
    st.title("Supermarket POS - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            user = verify_user(username, password)
            if user:
                if not user.get('active', True):
                    st.error("This account is inactive. Please contact administrator.")
                else:
                    st.session_state.user_info = user
                    st.session_state.current_page = "Dashboard"
                    st.session_state.last_activity = time.time()
                    st.rerun()
            else:
                st.error("Invalid username or password")

# Shift Management
def start_shift():
    shifts = load_data(SHIFTS_FILE)
    shift_id = generate_short_id()
    current_time = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
    
    shifts[shift_id] = {
        'shift_id': shift_id,
        'user_id': st.session_state.user_info['username'],
        'start_time': current_time,
        'end_time': None,
        'starting_cash': 0.0,
        'ending_cash': 0.0,
        'transactions': [],
        'status': 'active'
    }
    
    save_data(shifts, SHIFTS_FILE)
    st.session_state.shift_started = True
    st.session_state.shift_id = shift_id
    return shift_id

def end_shift():
    if not st.session_state.shift_started:
        return False
    
    shifts = load_data(SHIFTS_FILE)
    shift_id = st.session_state.shift_id
    
    if shift_id in shifts:
        current_time = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
        shifts[shift_id]['end_time'] = current_time
        shifts[shift_id]['status'] = 'completed'
        
        transactions = load_data(TRANSACTIONS_FILE)
        shift_transactions = [t for t in transactions.values() 
                            if t.get('shift_id') == shift_id and t['payment_method'] == 'Cash']
        total_cash = sum(t['total'] for t in shift_transactions)
        
        shifts[shift_id]['ending_cash'] = total_cash
        
        save_data(shifts, SHIFTS_FILE)
        st.session_state.shift_started = False
        st.session_state.shift_id = None
        return True
    return False

# Dashboard
def dashboard():
    settings = load_data(SETTINGS_FILE)
    if settings.get('auto_logout', True):
        inactive_time = time.time() - st.session_state.last_activity
        timeout_minutes = settings.get('session_timeout', 30)
        if inactive_time > timeout_minutes * 60:
            st.session_state.user_info = None
            st.session_state.current_page = "Login"
            st.rerun()
    
    st.session_state.last_activity = time.time()
    
    st.title("Supermarket POS Dashboard")
    st.sidebar.title("Navigation")
    
    # Shift management for cashiers
    if is_cashier() and not st.session_state.shift_started:
        with st.sidebar:
            st.subheader("Shift Management")
            starting_cash = st.number_input("Starting Cash Amount", min_value=0.0, value=0.0, step=1.0)
            if st.button("Start Shift"):
                shift_id = start_shift()
                shifts = load_data(SHIFTS_FILE)
                shifts[shift_id]['starting_cash'] = starting_cash
                save_data(shifts, SHIFTS_FILE)
                st.success("Shift started successfully")
                st.rerun()
    
    # Navigation
    pages = {
        "Dashboard": dashboard_content,
        "POS Terminal": pos_terminal,
        "Product Management": product_management,
        "Inventory Management": inventory_management,
        "User Management": user_management,
        "Discounts & Promotions": discounts_management,
        "Offers Management": offers_management,
        "Loyalty Program": loyalty_management,
        "Categories": categories_management,
        "Suppliers": suppliers_management,
        "Reports & Analytics": reports_analytics,
        "Shifts Management": shifts_management,
        "Returns & Refunds": returns_management,
        "System Settings": system_settings,
        "Backup & Restore": backup_restore
    }
    
    if is_admin():
        pass  # All pages already included
    elif is_manager():
        pages.pop("User Management", None)
        pages.pop("Backup & Restore", None)
    elif is_cashier():
        pages = {
            "Dashboard": dashboard_content,
            "POS Terminal": pos_terminal,
            "Shifts Management": shifts_management,
            "Returns & Refunds": returns_management
        }
    
    selected_page = st.sidebar.radio("Go to", list(pages.keys()))
    
    if st.sidebar.button("Logout"):
        if is_cashier() and st.session_state.shift_started:
            st.warning("Please end your shift before logging out")
        else:
            st.session_state.user_info = None
            st.session_state.current_page = "Login"
            st.rerun()
    
    # Display selected page
    pages[selected_page]()

def dashboard_content():
    st.header("Overview")
    
    col1, col2, col3 = st.columns(3)
    
    products = load_data(PRODUCTS_FILE)
    inventory = load_data(INVENTORY_FILE)
    transactions = load_data(TRANSACTIONS_FILE)
    
    total_products = len(products)
    low_stock_items = sum(1 for item in inventory.values() if item.get('quantity', 0) < item.get('reorder_point', 10))
    
    today_sales = 0
    today = datetime.date.today()
    for t in transactions.values():
        try:
            trans_date = datetime.datetime.strptime(t.get('date', ''), "%Y-%m-%d %H:%M:%S").date()
            if trans_date == today:
                today_sales += t.get('total', 0)
        except (ValueError, KeyError):
            continue
    
    col1.metric("Total Products", total_products)
    col2.metric("Low Stock Items", low_stock_items)
    col3.metric("Today's Sales", format_currency(today_sales))
    
    st.subheader("Recent Transactions")
    
    def get_transaction_date(t):
        try:
            return datetime.datetime.strptime(t.get('date', ''), "%Y-%m-%d %H:%M:%S")
        except (ValueError, KeyError):
            return datetime.datetime.min
    
    recent_transactions = sorted(transactions.values(), 
                               key=get_transaction_date, 
                               reverse=True)[:5]
    
    if recent_transactions:
        display_data = []
        for t in recent_transactions:
            display_data.append({
                'transaction_id': t.get('transaction_id', 'N/A'),
                'date': t.get('date', 'N/A'),
                'total': format_currency(t.get('total', 0)),
                'cashier': t.get('cashier', 'N/A')
            })
        
        trans_df = pd.DataFrame(display_data)
        st.dataframe(trans_df)
    else:
        st.info("No recent transactions")

# POS Terminal - Main Page
def pos_terminal():
    if is_cashier() and not st.session_state.shift_started:
        st.warning("Please start your shift before using the POS terminal")
        return
    
    st.title("POS Terminal")
    
    # Scanner status indicator
    if 'scanner_status' in st.session_state:
        status_color = "green" if st.session_state.scanner_status == "Connected" else "red"
        st.markdown(f"**Scanner Status:** <span style='color:{status_color}'>{st.session_state.scanner_status}</span>", 
                   unsafe_allow_html=True)
    
    # POS Mode Selection
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Barcode Scan Mode", use_container_width=True):
            st.session_state.pos_mode = 'scan'
            st.rerun()
    with col2:
        if st.button("Manual Entry Mode", use_container_width=True):
            st.session_state.pos_mode = 'manual'
            st.rerun()
    
    if st.session_state.pos_mode == 'scan':
        pos_scan_mode()
    else:
        pos_manual_mode()

# POS Terminal - Scan Mode
def pos_scan_mode():
    products = load_data(PRODUCTS_FILE)
    inventory = load_data(INVENTORY_FILE)
    settings = load_data(SETTINGS_FILE)
    
    st.header("Barcode Scan Mode")
    
    # Barcode scanning section
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search Products (name or barcode)", key="scan_search")
    with col2:
        st.info("Use connected barcode scanner to scan products")
    
    # Check for barcode scanner input
    if st.session_state.scanner_status == "Connected":
        barcode = barcode_scanner.get_barcode()
        if barcode:
            if barcode in products:
                product = products[barcode]
                if barcode in st.session_state.cart:
                    st.session_state.cart[barcode]['quantity'] += 1
                else:
                    st.session_state.cart[barcode] = {
                        'name': product['name'],
                        'price': product['price'],
                        'quantity': 1,
                        'description': product.get('description', '')
                    }
                st.success(f"Added {product['name']} to cart")
                st.rerun()
            else:
                st.error("Product not found with this barcode")
    
    # Product search results
    if search_term:
        filtered_products = {k: v for k, v in products.items() 
                           if search_term.lower() in v['name'].lower() or 
                           search_term.lower() in v['barcode']}
    else:
        filtered_products = products
    
    # Display products in a grid layout
    st.subheader("Products")
    cols_per_row = 4
    product_list = list(filtered_products.items())
    
    for i in range(0, len(product_list), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            if i + col_idx < len(product_list):
                barcode, product = product_list[i + col_idx]
                with cols[col_idx]:
                    with st.container():
                        if 'image' in product and os.path.exists(product['image']):
                            try:
                                img = Image.open(product['image'])
                                img.thumbnail((150, 150))
                                st.image(img, use_column_width=True)
                            except:
                                pass
                        
                        st.subheader(product['name'])
                        st.text(f"Price: {format_currency(product['price'])}")
                        
                        stock = inventory.get(barcode, {}).get('quantity', 0)
                        status = "In Stock" if stock > 0 else "Out of Stock"
                        color = "green" if stock > 0 else "red"
                        st.markdown(f"Status: <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)
                        
                        if st.button(f"Add to Cart", key=f"add_{barcode}", use_container_width=True):
                            if barcode in st.session_state.cart:
                                st.session_state.cart[barcode]['quantity'] += 1
                            else:
                                st.session_state.cart[barcode] = {
                                    'name': product['name'],
                                    'price': product['price'],
                                    'quantity': 1,
                                    'description': product.get('description', '')
                                }
                            st.success(f"Added {product['name']} to cart")
                            st.rerun()
    
    # Display cart and checkout
    display_cart_and_checkout()

# POS Terminal - Manual Mode
def pos_manual_mode():
    products = load_data(PRODUCTS_FILE)
    inventory = load_data(INVENTORY_FILE)
    categories = load_data(CATEGORIES_FILE)
    
    st.header("Manual Entry Mode")
    
    # Category and subcategory selection
    col1, col2 = st.columns(2)
    with col1:
        selected_category = st.selectbox(
            "Select Category", 
            [""] + categories.get('categories', []),
            key="manual_category"
        )
    with col2:
        if selected_category:
            subcategories = categories.get('subcategories', {}).get(selected_category, [])
            selected_subcategory = st.selectbox(
                "Select Subcategory", 
                [""] + subcategories,
                key="manual_subcategory"
            )
        else:
            selected_subcategory = None
    
    # Display products based on category/subcategory selection
    st.subheader("Products")
    
    if selected_category:
        filtered_products = {}
        for barcode, product in products.items():
            if product.get('category') == selected_category:
                if not selected_subcategory or product.get('subcategory') == selected_subcategory:
                    filtered_products[barcode] = product
        
        if not filtered_products:
            st.info("No products found in this category")
        else:
            cols_per_row = 4
            product_list = list(filtered_products.items())
            
            for i in range(0, len(product_list), cols_per_row):
                cols = st.columns(cols_per_row)
                for col_idx in range(cols_per_row):
                    if i + col_idx < len(product_list):
                        barcode, product = product_list[i + col_idx]
                        with cols[col_idx]:
                            with st.container():
                                if 'image' in product and os.path.exists(product['image']):
                                    try:
                                        img = Image.open(product['image'])
                                        img.thumbnail((150, 150))
                                        st.image(img, use_column_width=True)
                                    except:
                                        pass
                                
                                st.subheader(product['name'])
                                st.text(f"Price: {format_currency(product['price'])}")
                                
                                if product.get('description'):
                                    with st.expander("Description"):
                                        st.write(product['description'])
                                
                                stock = inventory.get(barcode, {}).get('quantity', 0)
                                status = "In Stock" if stock > 0 else "Out of Stock"
                                color = "green" if stock > 0 else "red"
                                st.markdown(f"Status: <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)
                                
                                quantity = st.number_input(
                                    "Quantity", 
                                    min_value=1, 
                                    max_value=100, 
                                    value=1, 
                                    key=f"qty_{barcode}"
                                )
                                
                                if st.button(f"Add to Cart", key=f"add_manual_{barcode}", use_container_width=True):
                                    if barcode in st.session_state.cart:
                                        st.session_state.cart[barcode]['quantity'] += quantity
                                    else:
                                        st.session_state.cart[barcode] = {
                                            'name': product['name'],
                                            'price': product['price'],
                                            'quantity': quantity,
                                            'description': product.get('description', '')
                                        }
                                    st.success(f"Added {quantity} {product['name']} to cart")
                                    st.rerun()
    else:
        st.info("Please select a category to view products")
    
    display_cart_and_checkout()

# Common cart and checkout display
def display_cart_and_checkout():
    settings = load_data(SETTINGS_FILE)
    
    st.header("Current Sale")
    if st.session_state.cart:
        for barcode, item in st.session_state.cart.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
                with col1:
                    st.write(f"**{item['name']}**")
                    if item.get('description'):
                        with st.expander("Description"):
                            st.write(item['description'])
                with col2:
                    new_qty = st.number_input(
                        "Qty", 
                        min_value=1, 
                        max_value=100, 
                        value=item['quantity'], 
                        key=f"edit_{barcode}"
                    )
                    if new_qty != item['quantity']:
                        st.session_state.cart[barcode]['quantity'] = new_qty
                        st.rerun()
                with col3:
                    st.write(f"{format_currency(item['price'] * item['quantity'])}")
                with col4:
                    if st.button("❌", key=f"remove_{barcode}"):
                        del st.session_state.cart[barcode]
                        st.rerun()
        
        subtotal = sum(item['price'] * item['quantity'] for item in st.session_state.cart.values())
        tax_rate = settings.get('tax_rate', 0.0)
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Summary")
            st.write(f"Subtotal: {format_currency(subtotal)}")
            st.write(f"Tax ({tax_rate*100}%): {format_currency(tax_amount)}")
            st.write(f"Total: {format_currency(total)}")
        
        discounts = load_data(DISCOUNTS_FILE)
        active_discounts = [d for d in discounts.values() if d['active']]
        
        if active_discounts:
            discount_options = {d['name']: d for d in active_discounts}
            selected_discount = st.selectbox("Apply Discount", [""] + list(discount_options.keys()))
            
            if selected_discount:
                discount = discount_options[selected_discount]
                if discount['type'] == 'percentage':
                    discount_amount = total * (discount['value'] / 100)
                else:
                    discount_amount = discount['value']
                
                total -= discount_amount
                st.write(f"Discount Applied: -{format_currency(discount_amount)}")
                st.write(f"New Total: {format_currency(total)}")
        
        offers = load_data(OFFERS_FILE)
        active_offers = [o for o in offers.values() if o['active']]
        
        for offer in active_offers:
            if offer['type'] == 'bogo':
                for barcode, item in st.session_state.cart.items():
                    if barcode in offer.get('products', []):
                        if item['quantity'] >= offer['buy_quantity']:
                            free_qty = (item['quantity'] // offer['buy_quantity']) * offer['get_quantity']
                            st.info(f"BOGO Offer Applied: Buy {offer['buy_quantity']} Get {offer['get_quantity']} Free on {item['name']}")
                            st.info(f"You get {free_qty} {item['name']} free")
                            total -= free_qty * item['price']
        
        with col2:
            st.subheader("Payment")
            payment_method = st.selectbox("Payment Method", ["Cash", "Credit Card", "Debit Card", "Mobile Payment"])
            amount_tendered = st.number_input("Amount Tendered", min_value=0.0, value=total, step=1.0)
            
            if st.button("Complete Sale", use_container_width=True):
                if amount_tendered < total:
                    st.error("Amount tendered is less than total")
                else:
                    transactions = load_data(TRANSACTIONS_FILE)
                    transaction_id = generate_short_id()
                    
                    transactions[transaction_id] = {
                        'transaction_id': transaction_id,
                        'date': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                        'items': st.session_state.cart,
                        'subtotal': subtotal,
                        'tax': tax_amount,
                        'discount': total - (subtotal + tax_amount),
                        'total': total,
                        'payment_method': payment_method,
                        'amount_tendered': amount_tendered,
                        'change': amount_tendered - total,
                        'cashier': st.session_state.user_info['username'],
                        'shift_id': st.session_state.shift_id if is_cashier() else None
                    }
                    
                    inventory = load_data(INVENTORY_FILE)
                    for barcode, item in st.session_state.cart.items():
                        if barcode in inventory:
                            inventory[barcode]['quantity'] -= item['quantity']
                        else:
                            inventory[barcode] = {'quantity': -item['quantity']}
                    
                    save_data(transactions, TRANSACTIONS_FILE)
                    save_data(inventory, INVENTORY_FILE)
                    
                    receipt = generate_receipt(transactions[transaction_id])
                    st.subheader("Receipt")
                    st.text(receipt)
                    
                    if print_receipt(receipt):
                        st.success("Receipt printed successfully")
                    else:
                        st.warning("Receipt could not be printed automatically")
                    
                    if payment_method == "Cash" and settings.get('cash_drawer_enabled', False):
                        open_cash_drawer()
                    
                    st.session_state.cart = {}
                    st.success("Sale completed successfully!")
                    
    else:
        st.info("Cart is empty")

def generate_receipt(transaction):
    settings = load_data(SETTINGS_FILE)
    receipt = ""
    
    # Header
    receipt += f"{settings.get('store_name', 'Supermarket POS')}\n"
    receipt += f"{settings.get('store_address', '')}\n"
    receipt += f"{settings.get('store_phone', '')}\n"
    receipt += "=" * 40 + "\n"
    
    if settings.get('receipt_header', ''):
        receipt += f"{settings['receipt_header']}\n"
        receipt += "=" * 40 + "\n"
    
    receipt += f"Date: {transaction['date']}\n"
    receipt += f"Cashier: {transaction['cashier']}\n"
    receipt += f"Transaction ID: {transaction['transaction_id']}\n"
    receipt += "=" * 40 + "\n"
    
    # Items
    for barcode, item in transaction['items'].items():
        receipt += f"{item['name']} x{item['quantity']}: {format_currency(item['price'] * item['quantity'])}\n"
    
    receipt += "=" * 40 + "\n"
    receipt += f"Subtotal: {format_currency(transaction['subtotal'])}\n"
    receipt += f"Tax: {format_currency(transaction['tax'])}\n"
    if transaction['discount'] != 0:
        receipt += f"Discount: -{format_currency(abs(transaction['discount']))}\n"
    receipt += f"Total: {format_currency(transaction['total'])}\n"
    receipt += f"Payment Method: {transaction['payment_method']}\n"
    receipt += f"Amount Tendered: {format_currency(transaction['amount_tendered'])}\n"
    receipt += f"Change: {format_currency(transaction['change'])}\n"
    receipt += "=" * 40 + "\n"
    
    if settings.get('receipt_footer', ''):
        receipt += f"{settings['receipt_footer']}\n"
        receipt += "=" * 40 + "\n"
    
    receipt += "Thank you for shopping with us!\n"
    
    return receipt

# Returns & Refunds Management
def returns_management():
    st.title("Returns & Refunds")
    
    tab1, tab2, tab3 = st.tabs(["Process Return", "View Returns", "Refund History"])
    
    with tab1:
        st.header("Process Return")
        
        transactions = load_data(TRANSACTIONS_FILE)
        products = load_data(PRODUCTS_FILE)
        
        transaction_id = st.text_input("Enter Transaction ID")
        
        if transaction_id:
            if transaction_id in transactions:
                transaction = transactions[transaction_id]
                
                st.subheader("Transaction Details")
                st.write(f"Date: {transaction['date']}")
                st.write(f"Total: {format_currency(transaction['total'])}")
                st.write(f"Payment Method: {transaction['payment_method']}")
                
                st.subheader("Items Purchased")
                for barcode, item in transaction['items'].items():
                    with st.container():
                        col1, col2, col3 = st.columns([4, 2, 2])
                        with col1:
                            st.write(f"**{item['name']}**")
                        with col2:
                            st.write(f"Qty: {item['quantity']}")
                        with col3:
                            return_qty = st.number_input(
                                "Return Qty", 
                                min_value=0, 
                                max_value=item['quantity'], 
                                value=0, 
                                key=f"return_{barcode}"
                            )
                
                return_reason = st.selectbox(
                    "Reason for Return",
                    ["", "Defective", "Wrong Item", "Customer Changed Mind", "Other"]
                )
                
                if return_reason == "Other":
                    return_reason = st.text_input("Please specify reason")
                
                if st.button("Process Return"):
                    returned_items = {}
                    total_refund = 0
                    
                    for barcode, item in transaction['items'].items():
                        return_qty = st.session_state.get(f"return_{barcode}", 0)
                        if return_qty > 0:
                            returned_items[barcode] = {
                                'name': item['name'],
                                'quantity': return_qty,
                                'price': item['price'],
                                'subtotal': return_qty * item['price']
                            }
                            total_refund += return_qty * item['price']
                    
                    if not returned_items:
                        st.error("No items selected for return")
                    else:
                        original_tax_rate = transaction['tax'] / transaction['subtotal']
                        tax_refund = total_refund * original_tax_rate
                        total_refund += tax_refund
                        
                        returns = load_data(RETURNS_FILE)
                        return_id = generate_short_id()
                        
                        returns[return_id] = {
                            'return_id': return_id,
                            'transaction_id': transaction_id,
                            'original_date': transaction['date'],
                            'return_date': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                            'items': returned_items,
                            'total_refund': total_refund,
                            'tax_refund': tax_refund,
                            'reason': return_reason,
                            'processed_by': st.session_state.user_info['username'],
                            'shift_id': st.session_state.shift_id if is_cashier() else None
                        }
                        
                        inventory = load_data(INVENTORY_FILE)
                        for barcode, item in returned_items.items():
                            if barcode in inventory:
                                inventory[barcode]['quantity'] += item['quantity']
                            else:
                                inventory[barcode] = {'quantity': item['quantity']}
                        
                        refund_method = transaction['payment_method']
                        
                        if refund_method == "Cash":
                            returns[return_id]['refund_method'] = "Cash"
                            returns[return_id]['status'] = "Completed"
                            
                            if is_cashier() and st.session_state.shift_started:
                                cash_drawer = load_data(CASH_DRAWER_FILE)
                                cash_drawer['current_balance'] -= total_refund
                                cash_drawer['transactions'].append({
                                    'type': 'refund',
                                    'amount': -total_refund,
                                    'date': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                                    'return_id': return_id,
                                    'processed_by': st.session_state.user_info['username']
                                })
                                save_data(cash_drawer, CASH_DRAWER_FILE)
                            
                            st.success(f"Cash refund processed: {format_currency(total_refund)}")
                        else:
                            returns[return_id]['refund_method'] = refund_method
                            returns[return_id]['status'] = "Pending"
                            st.success(f"Refund request for {format_currency(total_refund)} to original payment method has been submitted")
                        
                        save_data(returns, RETURNS_FILE)
                        save_data(inventory, INVENTORY_FILE)
                        
                        return_receipt = generate_return_receipt(returns[return_id])
                        st.subheader("Return Receipt")
                        st.text(return_receipt)
                        
                        if st.button("Print Return Receipt"):
                            if print_receipt(return_receipt):
                                st.success("Return receipt printed successfully")
                            else:
                                st.error("Failed to print return receipt")
            else:
                st.error("Transaction not found")

    with tab2:
        st.header("View Returns")
        
        returns = load_data(RETURNS_FILE)
        
        if not returns:
            st.info("No returns processed")
        else:
            col1, col2 = st.columns(2)
            with col1:
                status_filter = st.selectbox("Filter by Status", ["All", "Completed", "Pending"])
            with col2:
                user_filter = st.selectbox("Filter by User", ["All"] + list(set(r['processed_by'] for r in returns.values())))
            
            filtered_returns = returns.values()
            if status_filter != "All":
                filtered_returns = [r for r in filtered_returns if r['status'] == status_filter]
            if user_filter != "All":
                filtered_returns = [r for r in filtered_returns if r['processed_by'] == user_filter]
            
            if not filtered_returns:
                st.info("No returns match the filters")
            else:
                for return_data in filtered_returns:
                    with st.expander(f"Return #{return_data['return_id']} - {return_data['status']}"):
                        st.write(f"Original Transaction: {return_data['transaction_id']}")
                        st.write(f"Date: {return_data['return_date']}")
                        st.write(f"Processed by: {return_data['processed_by']}")
                        st.write(f"Reason: {return_data['reason']}")
                        st.write(f"Total Refund: {format_currency(return_data['total_refund'])}")
                        st.write(f"Refund Method: {return_data['refund_method']}")
                        
                        st.subheader("Returned Items")
                        for barcode, item in return_data['items'].items():
                            st.write(f"{item['name']} x{item['quantity']}: {format_currency(item['subtotal'])}")
                        
                        if return_data['status'] == "Pending" and is_manager():
                            if st.button("Mark as Completed", key=f"complete_{return_data['return_id']}"):
                                returns[return_data['return_id']]['status'] = "Completed"
                                returns[return_data['return_id']]['completed_date'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                                save_data(returns, RETURNS_FILE)
                                st.success("Return marked as completed")
                                st.rerun()
    
    with tab3:
        st.header("Refund History")
        
        returns = load_data(RETURNS_FILE)
        
        if not returns:
            st.info("No refunds processed")
        else:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", value=datetime.date.today())
            
            filtered_returns = []
            for return_data in returns.values():
                return_date = datetime.datetime.strptime(return_data['return_date'], "%Y-%m-%d %H:%M:%S").date()
                if start_date <= return_date <= end_date:
                    filtered_returns.append(return_data)
            
            if not filtered_returns:
                st.info("No refunds in selected date range")
            else:
                refund_summary = {
                    'Total Refunds': len(filtered_returns),
                    'Total Amount Refunded': sum(r['total_refund'] for r in filtered_returns),
                    'Cash Refunds': sum(1 for r in filtered_returns if r['refund_method'] == "Cash"),
                    'Card Refunds': sum(1 for r in filtered_returns if r['refund_method'] in ["Credit Card", "Debit Card"]),
                    'Pending Refunds': sum(1 for r in filtered_returns if r['status'] == "Pending")
                }
                
                st.subheader("Refund Summary")
                st.write(refund_summary)
                
                st.subheader("Refund Details")
                refund_df = pd.DataFrame(filtered_returns)
                st.dataframe(refund_df[['return_id', 'return_date', 'total_refund', 'refund_method', 'status']])

def generate_return_receipt(return_data):
    settings = load_data(SETTINGS_FILE)
    receipt = ""
    
    receipt += f"{settings.get('store_name', 'Supermarket POS')}\n"
    receipt += "RETURN RECEIPT\n"
    receipt += "=" * 40 + "\n"
    
    receipt += f"Return ID: {return_data['return_id']}\n"
    receipt += f"Original Transaction: {return_data['transaction_id']}\n"
    receipt += f"Date: {return_data['return_date']}\n"
    receipt += f"Processed by: {return_data['processed_by']}\n"
    receipt += f"Reason: {return_data['reason']}\n"
    receipt += "=" * 40 + "\n"
    
    receipt += "RETURNED ITEMS:\n"
    for barcode, item in return_data['items'].items():
        receipt += f"{item['name']} x{item['quantity']}: {format_currency(item['subtotal'])}\n"
    
    receipt += "=" * 40 + "\n"
    receipt += f"Subtotal Refund: {format_currency(return_data['total_refund'] - return_data['tax_refund'])}\n"
    receipt += f"Tax Refund: {format_currency(return_data['tax_refund'])}\n"
    receipt += f"Total Refund: {format_currency(return_data['total_refund'])}\n"
    receipt += f"Refund Method: {return_data['refund_method']}\n"
    receipt += f"Status: {return_data['status']}\n"
    receipt += "=" * 40 + "\n"
    receipt += "Thank you for your business!\n"
    
    return receipt
# Product Management
def product_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Product Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Add Product", "View/Edit Products", "Delete Product", "Bulk Import"])
    
    with tab1:
        st.header("Add New Product")
        
        with st.form("add_product_form"):
            name = st.text_input("Product Name*")
            description = st.text_area("Description")
            price = st.number_input("Price*", min_value=0.01, step=1.0, value=1.0)
            cost = st.number_input("Cost", min_value=0.01, step=1.0, value=1.0)
            
            categories = load_data(CATEGORIES_FILE)
            category = st.selectbox("Category", [""] + categories.get('categories', []))
            
            subcategory = st.selectbox("Subcategory", [""] + categories.get('subcategories', {}).get(category, []))
            
            barcode = st.text_input("Barcode (leave blank to generate)", value="")
            image = st.file_uploader("Product Image", type=['jpg', 'png', 'jpeg'])
            
            submit_button = st.form_submit_button("Add Product")
            
            if submit_button:
                if not name or price <= 0:
                    st.error("Name and price are required")
                else:
                    products = load_data(PRODUCTS_FILE)
                    inventory = load_data(INVENTORY_FILE)
                    
                    if not barcode:
                        barcode = generate_barcode()
                    
                    if barcode in products:
                        st.error("Product with this barcode already exists")
                    else:
                        # Save product
                        products[barcode] = {
                            'barcode': barcode,
                            'name': name,
                            'description': description,
                            'price': price,
                            'cost': cost,
                            'category': category,
                            'subcategory': subcategory,
                            'date_added': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                            'added_by': st.session_state.user_info['username']
                        }
                        
                        # Save image if provided
                        if image:
                            image_path = os.path.join(DATA_DIR, f"product_{barcode}.{image.name.split('.')[-1]}")
                            with open(image_path, 'wb') as f:
                                f.write(image.getbuffer())
                            products[barcode]['image'] = image_path
                        
                        # Initialize inventory
                        inventory[barcode] = {
                            'quantity': 0,
                            'reorder_point': 10,
                            'last_updated': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        save_data(products, PRODUCTS_FILE)
                        save_data(inventory, INVENTORY_FILE)
                        st.success(f"Product '{name}' added successfully with barcode: {barcode}")
    
    with tab2:
        st.header("View/Edit Products")
        
        products = load_data(PRODUCTS_FILE)
        if not products:
            st.info("No products available")
        else:
            search_term = st.text_input("Search Products (name or barcode)")
            
            if search_term:
                filtered_products = {k: v for k, v in products.items() 
                                   if search_term.lower() in v['name'].lower() or 
                                   search_term.lower() in k.lower()}
            else:
                filtered_products = products
            
            for barcode, product in filtered_products.items():
                with st.expander(f"{product['name']} - {barcode}"):
                    with st.form(key=f"edit_{barcode}"):
                        name = st.text_input("Name", value=product.get('name', ''))
                        description = st.text_area("Description", value=product.get('description', ''))
                        price = st.number_input("Price", value=product.get('price', 1.0), min_value=0.01, step=1.0)
                        cost = st.number_input("Cost", value=product.get('cost', 1.0), min_value=0.01, step=1.0)
                        
                        categories = load_data(CATEGORIES_FILE)
                        category = st.selectbox("Category", 
                                              [""] + categories.get('categories', []), 
                                              index=categories.get('categories', []).index(product.get('category', '')) + 1 
                                              if product.get('category', '') in categories.get('categories', []) else 0)
                        
                        subcategory = st.selectbox("Subcategory", 
                                                 [""] + categories.get('subcategories', {}).get(category, []), 
                                                 index=categories.get('subcategories', {}).get(category, []).index(product.get('subcategory', '')) + 1 
                                                 if product.get('subcategory', '') in categories.get('subcategories', {}).get(category, []) else 0)
                        
                        new_image = st.file_uploader("Update Image", type=['jpg', 'png', 'jpeg'], key=f"img_{barcode}")
                        
                        if st.form_submit_button("Update Product"):
                            products[barcode]['name'] = name
                            products[barcode]['description'] = description
                            products[barcode]['price'] = price
                            products[barcode]['cost'] = cost
                            products[barcode]['category'] = category
                            products[barcode]['subcategory'] = subcategory
                            products[barcode]['last_updated'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            products[barcode]['updated_by'] = st.session_state.user_info['username']
                            
                            if new_image:
                                # Remove old image if exists
                                if 'image' in products[barcode]:
                                    old_image_path = products[barcode]['image']
                                    if os.path.exists(old_image_path):
                                        os.remove(old_image_path)
                                
                                # Save new image
                                image_path = os.path.join(DATA_DIR, f"product_{barcode}.{new_image.name.split('.')[-1]}")
                                with open(image_path, 'wb') as f:
                                    f.write(new_image.getbuffer())
                                products[barcode]['image'] = image_path
                            
                            save_data(products, PRODUCTS_FILE)
                            st.success("Product updated successfully")
    
    with tab3:
        st.header("Delete Product")
        
        products = load_data(PRODUCTS_FILE)
        if not products:
            st.info("No products available to delete")
        else:
            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
            selected_product = st.selectbox("Select Product to Delete", [""] + list(product_options.keys()))
            
            if selected_product:
                barcode = product_options[selected_product]
                product = products[barcode]
                
                st.warning(f"You are about to delete: {product['name']} ({barcode})")
                st.write(f"Price: {format_currency(product['price'])}")
                st.write(f"Category: {product.get('category', 'N/A')}")
                
                if st.button("Confirm Delete"):
                    # Remove product image if exists
                    if 'image' in product and os.path.exists(product['image']):
                        os.remove(product['image'])
                    
                    # Remove from products and inventory
                    del products[barcode]
                    inventory = load_data(INVENTORY_FILE)
                    if barcode in inventory:
                        del inventory[barcode]
                    
                    save_data(products, PRODUCTS_FILE)
                    save_data(inventory, INVENTORY_FILE)
                    st.success("Product deleted successfully")
    
    with tab4:
        st.header("Bulk Import Products")
        
        st.info("Download the template file to prepare your product data")
        
        # Generate template file
        template_data = {
            "barcode": ["123456789012", ""],
            "name": ["Sample Product", ""],
            "description": ["Product description", ""],
            "price": [10.0, ""],
            "cost": [5.0, ""],
            "category": ["Groceries", ""],
            "subcategory": ["Snacks", ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="product_import_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Import Products"):
                    products = load_data(PRODUCTS_FILE)
                    inventory = load_data(INVENTORY_FILE)
                    imported = 0
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            if pd.isna(row['barcode']) or str(row['barcode']).strip() == "":
                                barcode = generate_barcode()
                            else:
                                barcode = str(row['barcode']).strip()
                            
                            if pd.isna(row['name']) or str(row['name']).strip() == "":
                                errors += 1
                                continue
                            
                            product_data = {
                                'barcode': barcode,
                                'name': str(row['name']).strip(),
                                'description': str(row['description']).strip() if not pd.isna(row['description']) else "",
                                'price': float(row['price']) if not pd.isna(row['price']) else 0.0,
                                'cost': float(row['cost']) if not pd.isna(row['cost']) else 0.0,
                                'category': str(row['category']).strip() if not pd.isna(row['category']) else "",
                                'subcategory': str(row['subcategory']).strip() if not pd.isna(row['subcategory']) else "",
                                'date_added': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                                'added_by': st.session_state.user_info['username']
                            }
                            
                            if barcode in products:
                                products[barcode].update(product_data)
                                updated += 1
                            else:
                                products[barcode] = product_data
                                imported += 1
                            
                            # Initialize inventory if not exists
                            if barcode not in inventory:
                                inventory[barcode] = {
                                    'quantity': 0,
                                    'reorder_point': 10,
                                    'last_updated': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                                }
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    save_data(products, PRODUCTS_FILE)
                    save_data(inventory, INVENTORY_FILE)
                    st.success(f"Import completed: {imported} new products, {updated} updated, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

# Inventory Management
def inventory_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Inventory Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Current Inventory", "Stock Adjustment", "Inventory Reports", "Bulk Update"])
    
    with tab1:
        st.header("Current Inventory")
        
        inventory = load_data(INVENTORY_FILE)
        products = load_data(PRODUCTS_FILE)
        
        if not inventory:
            st.info("No inventory items available")
        else:
            # Merge product info with inventory
            inventory_list = []
            for barcode, inv_data in inventory.items():
                product = products.get(barcode, {'name': 'Unknown Product', 'price': 0})
                inventory_list.append({
                    'product': product['name'],
                    'barcode': barcode,
                    'quantity': inv_data.get('quantity', 0),
                    'reorder_point': inv_data.get('reorder_point', 10),
                    'status': 'Low Stock' if inv_data.get('quantity', 0) < inv_data.get('reorder_point', 10) else 'OK',
                    'last_updated': inv_data.get('last_updated', 'N/A')
                })
            
            inventory_df = pd.DataFrame(inventory_list)
            
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                show_low_stock = st.checkbox("Show Only Low Stock Items")
            with col2:
                sort_by = st.selectbox("Sort By", ["Product Name", "Quantity", "Status"])
            
            if show_low_stock:
                inventory_df = inventory_df[inventory_df['status'] == 'Low Stock']
            
            if sort_by == "Product Name":
                inventory_df = inventory_df.sort_values('product')
            elif sort_by == "Quantity":
                inventory_df = inventory_df.sort_values('quantity')
            else:
                inventory_df = inventory_df.sort_values('status')
            
            st.dataframe(inventory_df)
            
            # Export option
            if st.button("Export Inventory to CSV"):
                csv = inventory_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"inventory_report_{datetime.date.today()}.csv",
                    mime="text/csv"
                )
    
    with tab2:
        st.header("Stock Adjustment")
        
        products = load_data(PRODUCTS_FILE)
        if not products:
            st.info("No products available")
        else:
            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
            selected_product = st.selectbox("Select Product", [""] + list(product_options.keys()))
            
            if selected_product:
                barcode = product_options[selected_product]
                inventory = load_data(INVENTORY_FILE)
                current_qty = inventory.get(barcode, {}).get('quantity', 0)
                current_reorder = inventory.get(barcode, {}).get('reorder_point', 10)
                
                st.write(f"Current Stock: {current_qty}")
                st.write(f"Current Reorder Point: {current_reorder}")
                
                with st.form(key=f"adjust_{barcode}"):
                    adjustment_type = st.radio("Adjustment Type", ["Add Stock", "Remove Stock", "Set Stock", "Transfer Stock"])
                    
                    if adjustment_type in ["Add Stock", "Remove Stock", "Set Stock"]:
                        quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
                    else:
                        quantity = st.number_input("Quantity to Transfer", min_value=1, value=1, step=1)
                        transfer_to = st.text_input("Transfer To (Location/Branch)")
                    
                    new_reorder = st.number_input("Reorder Point", min_value=0, value=current_reorder, step=1)
                    notes = st.text_area("Notes")
                    
                    if st.form_submit_button("Submit Adjustment"):
                        if barcode not in inventory:
                            inventory[barcode] = {'quantity': 0, 'reorder_point': new_reorder}
                        
                        if adjustment_type == "Add Stock":
                            inventory[barcode]['quantity'] += quantity
                        elif adjustment_type == "Remove Stock":
                            inventory[barcode]['quantity'] -= quantity
                        elif adjustment_type == "Set Stock":
                            inventory[barcode]['quantity'] = quantity
                        elif adjustment_type == "Transfer Stock":
                            inventory[barcode]['quantity'] -= quantity
                            # Note: In a full system, we'd update the destination inventory too
                        
                        inventory[barcode]['reorder_point'] = new_reorder
                        inventory[barcode]['last_updated'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                        inventory[barcode]['updated_by'] = st.session_state.user_info['username']
                        
                        # Record adjustment
                        adjustments = inventory[barcode].get('adjustments', [])
                        adjustments.append({
                            'date': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                            'type': adjustment_type,
                            'quantity': quantity,
                            'previous_qty': current_qty,
                            'new_qty': inventory[barcode]['quantity'],
                            'notes': notes,
                            'user': st.session_state.user_info['username']
                        })
                        inventory[barcode]['adjustments'] = adjustments
                        
                        save_data(inventory, INVENTORY_FILE)
                        st.success("Inventory updated successfully")
    
    with tab3:
        st.header("Inventory Reports")
        
        inventory = load_data(INVENTORY_FILE)
        products = load_data(PRODUCTS_FILE)
        
        if not inventory:
            st.info("No inventory data available")
        else:
            report_type = st.selectbox("Inventory Report Type", [
                "Stock Value Report",
                "Low Stock Report",
                "Stock Movement Report",
                "Inventory Audit"
            ])
            
            if report_type == "Stock Value Report":
                # Calculate total value of inventory
                total_value = 0
                report_data = []
                
                for barcode, inv_data in inventory.items():
                    product = products.get(barcode, {'name': 'Unknown', 'cost': 0})
                    value = inv_data.get('quantity', 0) * product.get('cost', 0)
                    total_value += value
                    report_data.append({
                        'Product': product['name'],
                        'Barcode': barcode,
                        'Quantity': inv_data.get('quantity', 0),
                        'Unit Cost': product.get('cost', 0),
                        'Total Value': value
                    })
                
                st.write(f"Total Inventory Value: {format_currency(total_value)}")
                st.dataframe(pd.DataFrame(report_data))
            
            elif report_type == "Low Stock Report":
                low_stock_items = []
                
                for barcode, inv_data in inventory.items():
                    if inv_data.get('quantity', 0) < inv_data.get('reorder_point', 10):
                        product = products.get(barcode, {'name': 'Unknown'})
                        low_stock_items.append({
                            'Product': product['name'],
                            'Barcode': barcode,
                            'Current Stock': inv_data.get('quantity', 0),
                            'Reorder Point': inv_data.get('reorder_point', 10)
                        })
                
                if low_stock_items:
                    st.dataframe(pd.DataFrame(low_stock_items))
                else:
                    st.info("No low stock items")
            
            elif report_type == "Stock Movement Report":
                st.info("Select a product to view its movement history")
                
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_product = st.selectbox("Select Product", [""] + list(product_options.keys()))
                
                if selected_product:
                    barcode = product_options[selected_product]
                    inventory = load_data(INVENTORY_FILE)
                    
                    if barcode in inventory and 'adjustments' in inventory[barcode]:
                        adjustments = inventory[barcode]['adjustments']
                        st.dataframe(pd.DataFrame(adjustments))
                    else:
                        st.info("No adjustment history for this product")
            
            elif report_type == "Inventory Audit":
                st.info("Inventory audit would compare physical counts with system records")
                if st.button("Generate Audit Sheet"):
                    audit_data = []
                    for barcode, inv_data in inventory.items():
                        product = products.get(barcode, {'name': 'Unknown'})
                        audit_data.append({
                            'Product': product['name'],
                            'Barcode': barcode,
                            'System Quantity': inv_data.get('quantity', 0),
                            'Physical Count': "",
                            'Variance': "",
                            'Notes': ""
                        })
                    
                    audit_df = pd.DataFrame(audit_data)
                    st.dataframe(audit_df)
                    
                    csv = audit_df.to_csv(index=False)
                    st.download_button(
                        label="Download Audit Sheet",
                        data=csv,
                        file_name=f"inventory_audit_{datetime.date.today()}.csv",
                        mime="text/csv"
                    )
    
    with tab4:
        st.header("Bulk Inventory Update")
        
        st.info("Download the template file to prepare your inventory data")
        
        # Generate template file
        template_data = {
            "barcode": ["123456789012", ""],
            "quantity": [10, ""],
            "reorder_point": [5, ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="inventory_update_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Update Inventory"):
                    inventory = load_data(INVENTORY_FILE)
                    products = load_data(PRODUCTS_FILE)
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            barcode = str(row['barcode']).strip()
                            
                            if barcode not in products:
                                errors += 1
                                continue
                            
                            if barcode not in inventory:
                                inventory[barcode] = {
                                    'quantity': 0,
                                    'reorder_point': 10
                                }
                            
                            if not pd.isna(row['quantity']):
                                inventory[barcode]['quantity'] = int(row['quantity'])
                            
                            if not pd.isna(row['reorder_point']):
                                inventory[barcode]['reorder_point'] = int(row['reorder_point'])
                            
                            inventory[barcode]['last_updated'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            inventory[barcode]['updated_by'] = st.session_state.user_info['username']
                            
                            updated += 1
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    save_data(inventory, INVENTORY_FILE)
                    st.success(f"Update completed: {updated} items updated, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

# User Management
def user_management():
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("User Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Add User", "View/Edit Users", "Delete User", "Bulk Import"])
    
    with tab1:
        st.header("Add New User")
        
        with st.form("add_user_form"):
            username = st.text_input("Username*")
            password = st.text_input("Password*", type="password")
            confirm_password = st.text_input("Confirm Password*", type="password")
            full_name = st.text_input("Full Name*")
            email = st.text_input("Email")
            role = st.selectbox("Role*", ["admin", "manager", "cashier"])
            active = st.checkbox("Active", value=True)
            
            submit_button = st.form_submit_button("Add User")
            
            if submit_button:
                if not username or not password or not full_name:
                    st.error("Fields marked with * are required")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    users = load_data(USERS_FILE)
                    
                    if username in users:
                        st.error("Username already exists")
                    else:
                        users[username] = {
                            'username': username,
                            'password': hash_password(password),
                            'role': role,
                            'full_name': full_name,
                            'email': email,
                            'active': active,
                            'date_created': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                            'created_by': st.session_state.user_info['username']
                        }
                        
                        save_data(users, USERS_FILE)
                        st.success(f"User '{username}' added successfully")
    
    with tab2:
        st.header("View/Edit Users")
        
        users = load_data(USERS_FILE)
        if not users:
            st.info("No users available")
        else:
            search_term = st.text_input("Search Users")
            
            if search_term:
                filtered_users = {k: v for k, v in users.items() 
                                 if search_term.lower() in k.lower() or 
                                 search_term.lower() in v['full_name'].lower()}
            else:
                filtered_users = users
            
            for username, user in filtered_users.items():
                if username == "admin" and st.session_state.user_info['username'] != "admin":
                    continue  # Only admin can edit admin account
                
                with st.expander(f"{user['full_name']} ({username}) - {user['role']}"):
                    with st.form(key=f"edit_{username}"):
                        full_name = st.text_input("Full Name", value=user.get('full_name', ''))
                        email = st.text_input("Email", value=user.get('email', ''))
                        
                        if username == "admin":
                            role = "admin"
                            st.text("Role: admin (cannot be changed)")
                        else:
                            role = st.selectbox("Role", ["admin", "manager", "cashier"], 
                                               index=["admin", "manager", "cashier"].index(user['role']))
                        
                        active = st.checkbox("Active", value=user.get('active', True))
                        
                        password = st.text_input("New Password (leave blank to keep current)", type="password")
                        confirm_password = st.text_input("Confirm New Password", type="password")
                        
                        if st.form_submit_button("Update User"):
                            users[username]['full_name'] = full_name
                            users[username]['email'] = email
                            users[username]['role'] = role
                            users[username]['active'] = active
                            users[username]['last_updated'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                            users[username]['updated_by'] = st.session_state.user_info['username']
                            
                            if password:
                                if password == confirm_password:
                                    users[username]['password'] = hash_password(password)
                                else:
                                    st.error("Passwords do not match")
                                    continue
                            
                            save_data(users, USERS_FILE)
                            st.success("User updated successfully")
    
    with tab3:
        st.header("Delete User")
        
        users = load_data(USERS_FILE)
        if not users:
            st.info("No users available to delete")
        else:
            current_user = st.session_state.user_info['username']
            user_options = {f"{v['full_name']} ({k})": k for k, v in users.items() 
                          if k != current_user and k != "admin"}  # Can't delete self or admin
            
            if not user_options:
                st.info("No users available to delete (cannot delete yourself or admin)")
            else:
                selected_user = st.selectbox("Select User to Delete", [""] + list(user_options.keys()))
                
                if selected_user:
                    username = user_options[selected_user]
                    user = users[username]
                    
                    st.warning(f"You are about to delete: {user['full_name']} ({username})")
                    st.write(f"Role: {user['role']}")
                    st.write(f"Status: {'Active' if user['active'] else 'Inactive'}")
                    
                    if st.button("Confirm Delete"):
                        del users[username]
                        save_data(users, USERS_FILE)
                        st.success("User deleted successfully")
    
    with tab4:
        st.header("Bulk Import Users")
        
        st.info("Download the template file to prepare your user data")
        
        # Generate template file
        template_data = {
            "username": ["user1", ""],
            "password": ["password123", ""],
            "full_name": ["User One", ""],
            "email": ["user1@example.com", ""],
            "role": ["cashier", ""],
            "active": [True, ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="user_import_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Import Users"):
                    users = load_data(USERS_FILE)
                    imported = 0
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            username = str(row['username']).strip()
                            if not username:
                                errors += 1
                                continue
                            
                            password = str(row['password']).strip()
                            if not password:
                                errors += 1
                                continue
                            
                            full_name = str(row['full_name']).strip()
                            if not full_name:
                                errors += 1
                                continue
                            
                            user_data = {
                                'username': username,
                                'password': hash_password(password),
                                'full_name': full_name,
                                'email': str(row['email']).strip() if not pd.isna(row['email']) else "",
                                'role': str(row['role']).strip().lower() if not pd.isna(row['role']) else "cashier",
                                'active': bool(row['active']) if not pd.isna(row['active']) else True,
                                'date_created': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                                'created_by': st.session_state.user_info['username']
                            }
                            
                            if username in users:
                                users[username].update(user_data)
                                updated += 1
                            else:
                                users[username] = user_data
                                imported += 1
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    save_data(users, USERS_FILE)
                    st.success(f"Import completed: {imported} new users, {updated} updated, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

# Discounts & Promotions
def discounts_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Discounts & Promotions")
    
    tab1, tab2, tab3 = st.tabs(["Add Discount", "View/Edit Discounts", "Bulk Import"])
    
    with tab1:
        st.header("Add New Discount")
        
        with st.form("add_discount_form"):
            name = st.text_input("Discount Name*")
            description = st.text_area("Description")
            
            col1, col2 = st.columns(2)
            with col1:
                discount_type = st.selectbox("Discount Type*", ["Percentage", "Fixed Amount"])
            with col2:
                if discount_type == "Percentage":
                    value = st.number_input("Value*", min_value=1, max_value=100, value=10, step=1)
                else:
                    value = st.number_input("Value*", min_value=0.01, value=1.0, step=1.0)
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date*", value=datetime.date.today())
            with col2:
                end_date = st.date_input("End Date*", value=datetime.date.today() + datetime.timedelta(days=7))
            
            apply_to = st.selectbox("Apply To*", ["All Products", "Specific Categories", "Specific Products"])
            
            if apply_to == "Specific Categories":
                categories = load_data(CATEGORIES_FILE).get('categories', [])
                selected_categories = st.multiselect("Select Categories*", categories)
            elif apply_to == "Specific Products":
                products = load_data(PRODUCTS_FILE)
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_products = st.multiselect("Select Products*", list(product_options.keys()))
            
            active = st.checkbox("Active", value=True)
            
            submit_button = st.form_submit_button("Add Discount")
            
            if submit_button:
                if not name:
                    st.error("Discount name is required")
                elif apply_to == "Specific Categories" and not selected_categories:
                    st.error("Please select at least one category")
                elif apply_to == "Specific Products" and not selected_products:
                    st.error("Please select at least one product")
                else:
                    discounts = load_data(DISCOUNTS_FILE)
                    discount_id = str(uuid.uuid4())
                    
                    discount_data = {
                        'id': discount_id,
                        'name': name,
                        'description': description,
                        'type': 'percentage' if discount_type == "Percentage" else 'fixed',
                        'value': value,
                        'start_date': start_date.strftime("%Y-%m-%d"),
                        'end_date': end_date.strftime("%Y-%m-%d"),
                        'apply_to': apply_to,
                        'active': active,
                        'created_by': st.session_state.user_info['username'],
                        'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if apply_to == "Specific Categories":
                        discount_data['categories'] = selected_categories
                    elif apply_to == "Specific Products":
                        discount_data['products'] = [product_options[p] for p in selected_products]
                    
                    discounts[discount_id] = discount_data
                    save_data(discounts, DISCOUNTS_FILE)
                    st.success("Discount added successfully")
    
    with tab2:
        st.header("View/Edit Discounts")
        
        discounts = load_data(DISCOUNTS_FILE)
        if not discounts:
            st.info("No discounts available")
        else:
            for discount_id, discount in discounts.items():
                with st.expander(f"{discount['name']} - {'Active' if discount['active'] else 'Inactive'}"):
                    with st.form(key=f"edit_{discount_id}"):
                        name = st.text_input("Name", value=discount.get('name', ''))
                        description = st.text_area("Description", value=discount.get('description', ''))
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            discount_type = st.selectbox("Type", 
                                                       ["Percentage", "Fixed Amount"], 
                                                       index=0 if discount.get('type') == 'percentage' else 1)
                        with col2:
                            if discount_type == "Percentage":
                                value = st.number_input("Value", 
                                                      min_value=1, 
                                                      max_value=100, 
                                                      value=int(discount.get('value', 10)),
                                                      step=1)
                            else:
                                value = st.number_input("Value", 
                                                      min_value=0.01, 
                                                      value=float(discount.get('value', 1.0)), 
                                                      step=1.0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            start_date = st.date_input("Start Date", 
                                                     value=datetime.datetime.strptime(discount.get('start_date'), "%Y-%m-%d").date())
                        with col2:
                            end_date = st.date_input("End Date", 
                                                   value=datetime.datetime.strptime(discount.get('end_date'), "%Y-%m-%d").date())
                        
                        apply_to = st.selectbox("Apply To", 
                                              ["All Products", "Specific Categories", "Specific Products"], 
                                              index=["All Products", "Specific Categories", "Specific Products"].index(discount.get('apply_to')))
                        
                        if apply_to == "Specific Categories":
                            categories = load_data(CATEGORIES_FILE).get('categories', [])
                            selected_categories = st.multiselect("Categories", 
                                                              categories, 
                                                              default=discount.get('categories', []))
                        elif apply_to == "Specific Products":
                            products = load_data(PRODUCTS_FILE)
                            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                            selected_products = st.multiselect("Products", 
                                                             list(product_options.keys()), 
                                                             default=[f"{products[p]['name']} ({p})" for p in discount.get('products', [])])
                        
                        active = st.checkbox("Active", value=discount.get('active', True))
                        
                        if st.form_submit_button("Update Discount"):
                            discounts[discount_id]['name'] = name
                            discounts[discount_id]['description'] = description
                            discounts[discount_id]['type'] = 'percentage' if discount_type == "Percentage" else 'fixed'
                            discounts[discount_id]['value'] = value
                            discounts[discount_id]['start_date'] = start_date.strftime("%Y-%m-%d")
                            discounts[discount_id]['end_date'] = end_date.strftime("%Y-%m-%d")
                            discounts[discount_id]['apply_to'] = apply_to
                            discounts[discount_id]['active'] = active
                            discounts[discount_id]['updated_by'] = st.session_state.user_info['username']
                            discounts[discount_id]['updated_at'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            
                            if apply_to == "Specific Categories":
                                discounts[discount_id]['categories'] = selected_categories
                                discounts[discount_id].pop('products', None)
                            elif apply_to == "Specific Products":
                                discounts[discount_id]['products'] = [product_options[p] for p in selected_products]
                                discounts[discount_id].pop('categories', None)
                            else:
                                discounts[discount_id].pop('categories', None)
                                discounts[discount_id].pop('products', None)
                            
                            save_data(discounts, DISCOUNTS_FILE)
                            st.success("Discount updated successfully")
    
    with tab3:
        st.header("Bulk Import Discounts")
        
        st.info("Download the template file to prepare your discount data")
        
        # Generate template file
        template_data = {
            "name": ["Summer Sale", ""],
            "description": ["Summer discount on all items", ""],
            "type": ["percentage", ""],
            "value": [10, ""],
            "start_date": ["2023-06-01", ""],
            "end_date": ["2023-08-31", ""],
            "apply_to": ["All Products", ""],
            "categories": ["Groceries,Dairy", ""],
            "products": ["123456789012,987654321098", ""],
            "active": [True, ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="discount_import_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Import Discounts"):
                    discounts = load_data(DISCOUNTS_FILE)
                    products = load_data(PRODUCTS_FILE)
                    categories = load_data(CATEGORIES_FILE).get('categories', [])
                    imported = 0
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            if pd.isna(row['name']) or str(row['name']).strip() == "":
                                errors += 1
                                continue
                            
                            discount_id = str(uuid.uuid4())
                            
                            discount_data = {
                                'id': discount_id,
                                'name': str(row['name']).strip(),
                                'description': str(row['description']).strip() if not pd.isna(row['description']) else "",
                                'type': str(row['type']).strip().lower() if not pd.isna(row['type']) else "percentage",
                                'value': float(row['value']) if not pd.isna(row['value']) else 0.0,
                                'start_date': str(row['start_date']).strip() if not pd.isna(row['start_date']) else datetime.date.today().strftime("%Y-%m-%d"),
                                'end_date': str(row['end_date']).strip() if not pd.isna(row['end_date']) else (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                                'apply_to': str(row['apply_to']).strip() if not pd.isna(row['apply_to']) else "All Products",
                                'active': bool(row['active']) if not pd.isna(row['active']) else True,
                                'created_by': st.session_state.user_info['username'],
                                'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            if discount_data['apply_to'] == "Specific Categories":
                                if pd.isna(row['categories']):
                                    errors += 1
                                    continue
                                cat_list = [c.strip() for c in str(row['categories']).split(',')]
                                valid_cats = [c for c in cat_list if c in categories]
                                if not valid_cats:
                                    errors += 1
                                    continue
                                discount_data['categories'] = valid_cats
                            
                            elif discount_data['apply_to'] == "Specific Products":
                                if pd.isna(row['products']):
                                    errors += 1
                                    continue
                                prod_list = [p.strip() for p in str(row['products']).split(',')]
                                valid_prods = [p for p in prod_list if p in products]
                                if not valid_prods:
                                    errors += 1
                                    continue
                                discount_data['products'] = valid_prods
                            
                            discounts[discount_id] = discount_data
                            imported += 1
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    save_data(discounts, DISCOUNTS_FILE)
                    st.success(f"Import completed: {imported} new discounts, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

# Offers Management
def offers_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Offers Management")
    
    tab1, tab2, tab3 = st.tabs(["Add Offer", "View/Edit Offers", "Bulk Import"])
    
    with tab1:
        st.header("Add New Offer")
        
        with st.form("add_offer_form"):
            name = st.text_input("Offer Name*")
            description = st.text_area("Description")
            
            offer_type = st.selectbox("Offer Type*", ["BOGO", "Bundle", "Special Price"])
            
            if offer_type == "BOGO":
                col1, col2 = st.columns(2)
                with col1:
                    buy_quantity = st.number_input("Buy Quantity*", min_value=1, value=1, step=1)
                with col2:
                    get_quantity = st.number_input("Get Quantity Free*", min_value=1, value=1, step=1)
                
                products = load_data(PRODUCTS_FILE)
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_products = st.multiselect("Select Products*", list(product_options.keys()))
            
            elif offer_type == "Bundle":
                products = load_data(PRODUCTS_FILE)
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_products = st.multiselect("Select Bundle Products*", list(product_options.keys()), max_selections=5)
                bundle_price = st.number_input("Bundle Price*", min_value=0.01, value=0.0, step=1.0)
            
            elif offer_type == "Special Price":
                products = load_data(PRODUCTS_FILE)
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_product = st.selectbox("Select Product*", [""] + list(product_options.keys()))
                special_price = st.number_input("Special Price*", min_value=0.01, value=0.0, step=1.0)
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date*", value=datetime.date.today())
            with col2:
                end_date = st.date_input("End Date*", value=datetime.date.today() + datetime.timedelta(days=7))
            
            active = st.checkbox("Active", value=True)
            
            submit_button = st.form_submit_button("Add Offer")
            
            if submit_button:
                if not name:
                    st.error("Offer name is required")
                elif offer_type in ["BOGO", "Bundle"] and not selected_products:
                    st.error("Please select at least one product")
                elif offer_type == "Special Price" and not selected_product:
                    st.error("Please select a product")
                else:
                    offers = load_data(OFFERS_FILE)
                    offer_id = str(uuid.uuid4())
                    
                    offer_data = {
                        'id': offer_id,
                        'name': name,
                        'description': description,
                        'type': offer_type.lower(),
                        'start_date': start_date.strftime("%Y-%m-%d"),
                        'end_date': end_date.strftime("%Y-%m-%d"),
                        'active': active,
                        'created_by': st.session_state.user_info['username'],
                        'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if offer_type == "BOGO":
                        offer_data['buy_quantity'] = buy_quantity
                        offer_data['get_quantity'] = get_quantity
                        offer_data['products'] = [product_options[p] for p in selected_products]
                    elif offer_type == "Bundle":
                        offer_data['products'] = [product_options[p] for p in selected_products]
                        offer_data['bundle_price'] = bundle_price
                    elif offer_type == "Special Price":
                        offer_data['product'] = product_options[selected_product]
                        offer_data['special_price'] = special_price
                    
                    offers[offer_id] = offer_data
                    save_data(offers, OFFERS_FILE)
                    st.success("Offer added successfully")
    
    with tab2:
        st.header("View/Edit Offers")
        
        offers = load_data(OFFERS_FILE)
        products = load_data(PRODUCTS_FILE)
        
        if not offers:
            st.info("No offers available")
        else:
            for offer_id, offer in offers.items():
                with st.expander(f"{offer['name']} - {'Active' if offer['active'] else 'Inactive'}"):
                    with st.form(key=f"edit_{offer_id}"):
                        name = st.text_input("Name", value=offer.get('name', ''))
                        description = st.text_area("Description", value=offer.get('description', ''))
                        
                        offer_type = st.selectbox("Type", 
                                                ["BOGO", "Bundle", "Special Price"], 
                                                index=["BOGO", "Bundle", "Special Price"].index(offer['type'].title()))
                        
                        if offer['type'] == "bogo":
                            col1, col2 = st.columns(2)
                            with col1:
                                buy_quantity = st.number_input("Buy Quantity", 
                                                             min_value=1, 
                                                             value=offer.get('buy_quantity', 1), 
                                                             step=1)
                            with col2:
                                get_quantity = st.number_input("Get Quantity Free", 
                                                             min_value=1, 
                                                             value=offer.get('get_quantity', 1), 
                                                             step=1)
                            
                            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                            selected_products = st.multiselect("Products", 
                                                             list(product_options.keys()), 
                                                             default=[f"{products[p]['name']} ({p})" for p in offer.get('products', [])])
                        
                        elif offer['type'] == "bundle":
                            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                            selected_products = st.multiselect("Bundle Products", 
                                                             list(product_options.keys()), 
                                                             default=[f"{products[p]['name']} ({p})" for p in offer.get('products', [])],
                                                             max_selections=5)
                            bundle_price = st.number_input("Bundle Price", 
                                                         min_value=0.01, 
                                                         value=offer.get('bundle_price', 0.0), 
                                                         step=1.0)
                        
                        elif offer['type'] == "special_price":
                            product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                            selected_product = st.selectbox("Product", 
                                                          [""] + list(product_options.keys()), 
                                                          index=list(product_options.keys()).index(f"{products[offer['product']]['name']} ({offer['product']})") + 1 
                                                          if offer.get('product') in products else 0)
                            special_price = st.number_input("Special Price", 
                                                          min_value=0.01, 
                                                          value=offer.get('special_price', 0.0), 
                                                          step=1.0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            start_date = st.date_input("Start Date", 
                                                     value=datetime.datetime.strptime(offer.get('start_date'), "%Y-%m-%d").date())
                        with col2:
                            end_date = st.date_input("End Date", 
                                                   value=datetime.datetime.strptime(offer.get('end_date'), "%Y-%m-%d").date())
                        
                        active = st.checkbox("Active", value=offer.get('active', True))
                        
                        if st.form_submit_button("Update Offer"):
                            offers[offer_id]['name'] = name
                            offers[offer_id]['description'] = description
                            offers[offer_id]['type'] = offer_type.lower()
                            offers[offer_id]['start_date'] = start_date.strftime("%Y-%m-%d")
                            offers[offer_id]['end_date'] = end_date.strftime("%Y-%m-%d")
                            offers[offer_id]['active'] = active
                            offers[offer_id]['updated_by'] = st.session_state.user_info['username']
                            offers[offer_id]['updated_at'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            
                            if offer['type'] == "bogo":
                                offers[offer_id]['buy_quantity'] = buy_quantity
                                offers[offer_id]['get_quantity'] = get_quantity
                                offers[offer_id]['products'] = [product_options[p] for p in selected_products]
                            elif offer['type'] == "bundle":
                                offers[offer_id]['products'] = [product_options[p] for p in selected_products]
                                offers[offer_id]['bundle_price'] = bundle_price
                            elif offer['type'] == "special_price":
                                offers[offer_id]['product'] = product_options[selected_product]
                                offers[offer_id]['special_price'] = special_price
                            
                            save_data(offers, OFFERS_FILE)
                            st.success("Offer updated successfully")
    
    with tab3:
        st.header("Bulk Import Offers")
        
        st.info("Download the template file to prepare your offer data")
        
        # Generate template file
        template_data = {
            "name": ["Summer BOGO", ""],
            "description": ["Buy 2 Get 1 Free", ""],
            "type": ["BOGO", ""],
            "buy_quantity": [2, ""],
            "get_quantity": [1, ""],
            "products": ["123456789012,987654321098", ""],
            "bundle_price": ["", ""],
            "special_price": ["", ""],
            "start_date": ["2023-06-01", ""],
            "end_date": ["2023-08-31", ""],
            "active": [True, ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="offer_import_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Import Offers"):
                    offers = load_data(OFFERS_FILE)
                    products = load_data(PRODUCTS_FILE)
                    imported = 0
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            if pd.isna(row['name']) or str(row['name']).strip() == "":
                                errors += 1
                                continue
                            
                            if pd.isna(row['type']) or str(row['type']).strip().lower() not in ["bogo", "bundle", "special_price"]:
                                errors += 1
                                continue
                            
                            offer_id = str(uuid.uuid4())
                            offer_type = str(row['type']).strip().lower()
                            
                            offer_data = {
                                'id': offer_id,
                                'name': str(row['name']).strip(),
                                'description': str(row['description']).strip() if not pd.isna(row['description']) else "",
                                'type': offer_type,
                                'start_date': str(row['start_date']).strip() if not pd.isna(row['start_date']) else datetime.date.today().strftime("%Y-%m-%d"),
                                'end_date': str(row['end_date']).strip() if not pd.isna(row['end_date']) else (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                                'active': bool(row['active']) if not pd.isna(row['active']) else True,
                                'created_by': st.session_state.user_info['username'],
                                'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            if offer_type == "bogo":
                                if pd.isna(row['buy_quantity']) or pd.isna(row['get_quantity']):
                                    errors += 1
                                    continue
                                
                                offer_data['buy_quantity'] = int(row['buy_quantity'])
                                offer_data['get_quantity'] = int(row['get_quantity'])
                                
                                if pd.isna(row['products']):
                                    errors += 1
                                    continue
                                
                                prod_list = [p.strip() for p in str(row['products']).split(',')]
                                valid_prods = [p for p in prod_list if p in products]
                                if not valid_prods:
                                    errors += 1
                                    continue
                                offer_data['products'] = valid_prods
                            
                            elif offer_type == "bundle":
                                if pd.isna(row['bundle_price']):
                                    errors += 1
                                    continue
                                
                                offer_data['bundle_price'] = float(row['bundle_price'])
                                
                                if pd.isna(row['products']):
                                    errors += 1
                                    continue
                                
                                prod_list = [p.strip() for p in str(row['products']).split(',')]
                                valid_prods = [p for p in prod_list if p in products]
                                if not valid_prods:
                                    errors += 1
                                    continue
                                offer_data['products'] = valid_prods
                            
                            elif offer_type == "special_price":
                                if pd.isna(row['special_price']):
                                    errors += 1
                                    continue
                                
                                offer_data['special_price'] = float(row['special_price'])
                                
                                if pd.isna(row['products']):
                                    errors += 1
                                    continue
                                
                                product_id = str(row['products']).strip()
                                if product_id not in products:
                                    errors += 1
                                    continue
                                offer_data['product'] = product_id
                            
                            offers[offer_id] = offer_data
                            imported += 1
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    save_data(offers, OFFERS_FILE)
                    st.success(f"Import completed: {imported} new offers, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")
                
# Loyalty Program Management
def loyalty_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Loyalty Program Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Tier Management", "Customer Points", "Rewards", "Bulk Import"])
    
    with tab1:
        st.header("Loyalty Tiers")
        
        loyalty = load_data(LOYALTY_FILE)
        tiers = loyalty.get('tiers', {})
        
        st.subheader("Current Tiers")
        if not tiers:
            st.info("No loyalty tiers defined")
        else:
            tier_df = pd.DataFrame.from_dict(tiers, orient='index')
            tier_df['discount'] = tier_df['discount'].apply(lambda x: f"{x*100}%")
            st.dataframe(tier_df)
        
        st.subheader("Add/Edit Tier")
        with st.form("tier_form"):
            tier_name = st.text_input("Tier Name*")
            min_points = st.number_input("Minimum Points Required*", min_value=0, value=1000, step=1)
            discount = st.number_input("Discount Percentage*", min_value=0, max_value=100, value=5, step=1)
            
            submit_button = st.form_submit_button("Save Tier")
            
            if submit_button:
                if not tier_name:
                    st.error("Tier name is required")
                else:
                    tiers[tier_name] = {
                        'min_points': min_points,
                        'discount': discount / 100  # Store as decimal
                    }
                    loyalty['tiers'] = tiers
                    save_data(loyalty, LOYALTY_FILE)
                    st.success("Tier saved successfully")
    
    with tab2:
        st.header("Customer Points")
        
        loyalty = load_data(LOYALTY_FILE)
        customers = loyalty.get('customers', {})
        
        st.subheader("Customer List")
        if not customers:
            st.info("No customers in loyalty program")
        else:
            customer_df = pd.DataFrame.from_dict(customers, orient='index')
            st.dataframe(customer_df[['name', 'phone', 'email', 'points', 'tier']])
        
        st.subheader("Add/Edit Customer")
        with st.form("customer_form"):
            name = st.text_input("Customer Name*")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email")
            points = st.number_input("Points*", min_value=0, value=0, step=1)
            
            tiers = loyalty.get('tiers', {})
            if tiers:
                current_tier = None
                for tier_name, tier_data in tiers.items():
                    if points >= tier_data['min_points']:
                        current_tier = tier_name
                
                tier_options = list(tiers.keys())
                tier = st.selectbox("Tier", tier_options, index=tier_options.index(current_tier) if current_tier else 0)
            else:
                tier = st.text_input("Tier (no tiers defined yet)")
            
            if st.form_submit_button("Save Customer"):
                customer_id = str(uuid.uuid4())
                customers[customer_id] = {
                    'id': customer_id,
                    'name': name,
                    'phone': phone,
                    'email': email,
                    'points': points,
                    'tier': tier,
                    'last_updated': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                }
                loyalty['customers'] = customers
                save_data(loyalty, LOYALTY_FILE)
                st.success("Customer saved successfully")
    
    with tab3:
        st.header("Rewards Management")
        
        loyalty = load_data(LOYALTY_FILE)
        rewards = loyalty.get('rewards', {})
        
        st.subheader("Current Rewards")
        if not rewards:
            st.info("No rewards defined")
        else:
            reward_df = pd.DataFrame.from_dict(rewards, orient='index')
            st.dataframe(reward_df)
        
        st.subheader("Add/Edit Reward")
        with st.form("reward_form"):
            name = st.text_input("Reward Name*")
            points_required = st.number_input("Points Required*", min_value=1, value=100, step=1)
            description = st.text_area("Description")
            active = st.checkbox("Active", value=True)
            
            submit_button = st.form_submit_button("Save Reward")
            
            if submit_button:
                if not name:
                    st.error("Reward name is required")
                else:
                    reward_id = str(uuid.uuid4())
                    rewards[reward_id] = {
                        'name': name,
                        'points': points_required,
                        'description': description,
                        'active': active,
                        'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    loyalty['rewards'] = rewards
                    save_data(loyalty, LOYALTY_FILE)
                    st.success("Reward saved successfully")
    
    with tab4:
        st.header("Bulk Import Customers")
        
        st.info("Download the template file to prepare your customer data")
        
        # Generate template file
        template_data = {
            "name": ["John Doe", ""],
            "phone": ["1234567890", ""],
            "email": ["john@example.com", ""],
            "points": [100, ""],
            "tier": ["Silver", ""]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="Download Template",
            data=template_df.to_csv(index=False).encode('utf-8'),
            file_name="loyalty_customer_import_template.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df)
                
                if st.button("Import Customers"):
                    loyalty = load_data(LOYALTY_FILE)
                    customers = loyalty.get('customers', {})
                    tiers = loyalty.get('tiers', {})
                    imported = 0
                    updated = 0
                    errors = 0
                    
                    for _, row in df.iterrows():
                        try:
                            if pd.isna(row['name']) or str(row['name']).strip() == "":
                                errors += 1
                                continue
                            
                            customer_id = str(uuid.uuid4())
                            
                            customer_data = {
                                'id': customer_id,
                                'name': str(row['name']).strip(),
                                'phone': str(row['phone']).strip() if not pd.isna(row['phone']) else "",
                                'email': str(row['email']).strip() if not pd.isna(row['email']) else "",
                                'points': int(row['points']) if not pd.isna(row['points']) else 0,
                                'tier': str(row['tier']).strip() if not pd.isna(row['tier']) else "",
                                'last_updated': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            # Validate tier
                            if customer_data['tier'] and customer_data['tier'] not in tiers:
                                errors += 1
                                continue
                            
                            customers[customer_id] = customer_data
                            imported += 1
                        
                        except Exception as e:
                            errors += 1
                            continue
                    
                    loyalty['customers'] = customers
                    save_data(loyalty, LOYALTY_FILE)
                    st.success(f"Import completed: {imported} new customers, {errors} errors")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

# Categories Management
def categories_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Categories Management")
    
    tab1, tab2 = st.tabs(["Manage Categories", "Manage Subcategories"])
    
    with tab1:
        st.header("Manage Categories")
        
        categories_data = load_data(CATEGORIES_FILE)
        categories = categories_data.get('categories', [])
        subcategories = categories_data.get('subcategories', {})
        
        st.subheader("Current Categories")
        if not categories:
            st.info("No categories defined")
        else:
            st.dataframe(pd.DataFrame(categories, columns=["Categories"]))
        
        st.subheader("Add/Edit Category")
        with st.form("category_form"):
            new_category = st.text_input("Category Name")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Add Category"):
                    if new_category and new_category not in categories:
                        categories.append(new_category)
                        categories_data['categories'] = categories
                        if new_category not in subcategories:
                            subcategories[new_category] = []
                        categories_data['subcategories'] = subcategories
                        save_data(categories_data, CATEGORIES_FILE)
                        st.success("Category added successfully")
                        st.rerun()
            with col2:
                if categories and st.form_submit_button("Remove Selected"):
                    category_to_remove = st.selectbox("Select Category to Remove", [""] + categories)
                    if category_to_remove:
                        categories.remove(category_to_remove)
                        categories_data['categories'] = categories
                        if category_to_remove in subcategories:
                            del subcategories[category_to_remove]
                        categories_data['subcategories'] = subcategories
                        save_data(categories_data, CATEGORIES_FILE)
                        st.success("Category removed successfully")
                        st.rerun()
    
    with tab2:
        st.header("Manage Subcategories")
        
        categories_data = load_data(CATEGORIES_FILE)
        categories = categories_data.get('categories', [])
        subcategories = categories_data.get('subcategories', {})
        
        if not categories:
            st.info("No categories available to add subcategories")
        else:
            selected_category = st.selectbox("Select Category", categories)
            
            if selected_category:
                if selected_category not in subcategories:
                    subcategories[selected_category] = []
                
                st.subheader(f"Subcategories for {selected_category}")
                if not subcategories[selected_category]:
                    st.info("No subcategories defined for this category")
                else:
                    st.dataframe(pd.DataFrame(subcategories[selected_category], columns=["Subcategories"]))
                
                st.subheader("Add/Edit Subcategory")
                with st.form("subcategory_form"):
                    new_subcategory = st.text_input("Subcategory Name")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Add Subcategory"):
                            if new_subcategory and new_subcategory not in subcategories[selected_category]:
                                subcategories[selected_category].append(new_subcategory)
                                categories_data['subcategories'] = subcategories
                                save_data(categories_data, CATEGORIES_FILE)
                                st.success("Subcategory added successfully")
                                st.rerun()
                    with col2:
                        if subcategories[selected_category] and st.form_submit_button("Remove Selected"):
                            subcategory_to_remove = st.selectbox("Select Subcategory to Remove", 
                                                               [""] + subcategories[selected_category])
                            if subcategory_to_remove:
                                subcategories[selected_category].remove(subcategory_to_remove)
                                categories_data['subcategories'] = subcategories
                                save_data(categories_data, CATEGORIES_FILE)
                                st.success("Subcategory removed successfully")
                                st.rerun()

# Suppliers Management
def suppliers_management():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Suppliers Management")
    
    tab1, tab2, tab3 = st.tabs(["Add Supplier", "View/Edit Suppliers", "Delete Supplier"])
    
    with tab1:
        st.header("Add New Supplier")
        
        with st.form("add_supplier_form"):
            name = st.text_input("Supplier Name*")
            contact_person = st.text_input("Contact Person")
            phone = st.text_input("Phone Number*")
            email = st.text_input("Email")
            address = st.text_area("Address")
            products_supplied = st.text_area("Products Supplied (comma separated)")
            payment_terms = st.text_input("Payment Terms")
            
            submit_button = st.form_submit_button("Add Supplier")
            
            if submit_button:
                if not name or not phone:
                    st.error("Name and phone are required")
                else:
                    suppliers = load_data(SUPPLIERS_FILE)
                    supplier_id = str(uuid.uuid4())
                    
                    suppliers[supplier_id] = {
                        'id': supplier_id,
                        'name': name,
                        'contact_person': contact_person,
                        'phone': phone,
                        'email': email,
                        'address': address,
                        'products_supplied': [p.strip() for p in products_supplied.split(',')] if products_supplied else [],
                        'payment_terms': payment_terms,
                        'date_added': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S"),
                        'added_by': st.session_state.user_info['username']
                    }
                    
                    save_data(suppliers, SUPPLIERS_FILE)
                    st.success("Supplier added successfully")
    
    with tab2:
        st.header("View/Edit Suppliers")
        
        suppliers = load_data(SUPPLIERS_FILE)
        if not suppliers:
            st.info("No suppliers available")
        else:
            search_term = st.text_input("Search Suppliers")
            
            if search_term:
                filtered_suppliers = {k: v for k, v in suppliers.items() 
                                    if search_term.lower() in v['name'].lower() or 
                                    search_term.lower() in v['phone'].lower()}
            else:
                filtered_suppliers = suppliers
            
            for supplier_id, supplier in filtered_suppliers.items():
                with st.expander(f"{supplier['name']} - {supplier['phone']}"):
                    with st.form(key=f"edit_{supplier_id}"):
                        name = st.text_input("Name", value=supplier.get('name', ''))
                        contact_person = st.text_input("Contact Person", value=supplier.get('contact_person', ''))
                        phone = st.text_input("Phone Number", value=supplier.get('phone', ''))
                        email = st.text_input("Email", value=supplier.get('email', ''))
                        address = st.text_area("Address", value=supplier.get('address', ''))
                        products_supplied = st.text_area("Products Supplied", 
                                                        value=", ".join(supplier.get('products_supplied', [])))
                        payment_terms = st.text_input("Payment Terms", value=supplier.get('payment_terms', ''))
                        
                        if st.form_submit_button("Update Supplier"):
                            suppliers[supplier_id]['name'] = name
                            suppliers[supplier_id]['contact_person'] = contact_person
                            suppliers[supplier_id]['phone'] = phone
                            suppliers[supplier_id]['email'] = email
                            suppliers[supplier_id]['address'] = address
                            suppliers[supplier_id]['products_supplied'] = [p.strip() for p in products_supplied.split(',')] if products_supplied else []
                            suppliers[supplier_id]['payment_terms'] = payment_terms
                            suppliers[supplier_id]['last_updated'] = get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
                            suppliers[supplier_id]['updated_by'] = st.session_state.user_info['username']
                            
                            save_data(suppliers, SUPPLIERS_FILE)
                            st.success("Supplier updated successfully")
    
    with tab3:
        st.header("Delete Supplier")
        
        suppliers = load_data(SUPPLIERS_FILE)
        if not suppliers:
            st.info("No suppliers available to delete")
        else:
            supplier_options = {f"{v['name']} ({v['phone']})": k for k, v in suppliers.items()}
            selected_supplier = st.selectbox("Select Supplier to Delete", [""] + list(supplier_options.keys()))
            
            if selected_supplier:
                supplier_id = supplier_options[selected_supplier]
                supplier = suppliers[supplier_id]
                
                st.warning(f"You are about to delete: {supplier['name']}")
                st.write(f"Phone: {supplier['phone']}")
                st.write(f"Contact: {supplier.get('contact_person', 'N/A')}")
                
                if st.button("Confirm Delete"):
                    del suppliers[supplier_id]
                    save_data(suppliers, SUPPLIERS_FILE)
                    st.success("Supplier deleted successfully")

# Reports & Analytics
def reports_analytics():
    if not is_manager():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Reports & Analytics")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Sales Reports", 
        "Inventory Reports", 
        "Customer Reports", 
        "Payment Analysis",
        "Custom Reports"
    ])
    
    with tab1:
        st.header("Sales Reports")
        
        transactions = load_data(TRANSACTIONS_FILE)
        if not transactions:
            st.info("No sales data available")
        else:
            report_type = st.selectbox("Sales Report Type", [
                "Daily Sales",
                "Weekly Sales",
                "Monthly Sales",
                "Product Sales",
                "Category Sales",
                "Cashier Performance"
            ])
            
            # Date range filter
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", value=datetime.date.today())
            
            # Convert transactions to DataFrame
            trans_list = []
            for t in transactions.values():
                trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                if start_date <= trans_date <= end_date:
                    trans_list.append({
                        'date': t['date'],
                        'transaction_id': t['transaction_id'],
                        'total': t['total'],
                        'cashier': t['cashier'],
                        'payment_method': t['payment_method']
                    })
            
            if not trans_list:
                st.info("No transactions in selected date range")
            else:
                trans_df = pd.DataFrame(trans_list)
                trans_df['date'] = pd.to_datetime(trans_df['date'])
                
                if report_type == "Daily Sales":
                    trans_df['date_group'] = trans_df['date'].dt.date
                    report_df = trans_df.groupby('date_group').agg({
                        'total': 'sum',
                        'transaction_id': 'count'
                    }).rename(columns={'transaction_id': 'transactions'})
                    
                    st.subheader("Daily Sales Summary")
                    st.dataframe(report_df)
                    
                    st.subheader("Daily Sales Chart")
                    st.line_chart(report_df['total'])
                
                elif report_type == "Weekly Sales":
                    trans_df['week'] = trans_df['date'].dt.strftime('%Y-%U')
                    report_df = trans_df.groupby('week').agg({
                        'total': 'sum',
                        'transaction_id': 'count'
                    }).rename(columns={'transaction_id': 'transactions'})
                    
                    st.subheader("Weekly Sales Summary")
                    st.dataframe(report_df)
                    
                    st.subheader("Weekly Sales Chart")
                    st.bar_chart(report_df['total'])
                
                elif report_type == "Monthly Sales":
                    trans_df['month'] = trans_df['date'].dt.strftime('%Y-%m')
                    report_df = trans_df.groupby('month').agg({
                        'total': 'sum',
                        'transaction_id': 'count'
                    }).rename(columns={'transaction_id': 'transactions'})
                    
                    st.subheader("Monthly Sales Summary")
                    st.dataframe(report_df)
                    
                    st.subheader("Monthly Sales Chart")
                    st.area_chart(report_df['total'])
                
                elif report_type == "Product Sales":
                    # Product sales analysis
                    products = load_data(PRODUCTS_FILE)
                    product_sales = {}
                    
                    for t in transactions.values():
                        trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                        if start_date <= trans_date <= end_date:
                            for barcode, item in t['items'].items():
                                if barcode not in product_sales:
                                    product_sales[barcode] = {
                                        'name': products.get(barcode, {}).get('name', 'Unknown'),
                                        'quantity': 0,
                                        'revenue': 0.0
                                    }
                                
                                product_sales[barcode]['quantity'] += item['quantity']
                                product_sales[barcode]['revenue'] += item['price'] * item['quantity']
                    
                    if not product_sales:
                        st.info("No product sales in selected date range")
                    else:
                        sales_df = pd.DataFrame.from_dict(product_sales, orient='index')
                        sales_df = sales_df.sort_values('revenue', ascending=False)
                        
                        st.subheader("Product Sales Summary")
                        st.dataframe(sales_df)
                        
                        st.subheader("Top Selling Products")
                        top_n = st.slider("Show Top", 1, 20, 5)
                        st.bar_chart(sales_df.head(top_n)['revenue'])
                
                elif report_type == "Category Sales":
                    # Category sales analysis
                    products = load_data(PRODUCTS_FILE)
                    categories = load_data(CATEGORIES_FILE).get('categories', [])
                    category_sales = {}
                    
                    for cat in categories:
                        category_sales[cat] = {'revenue': 0.0, 'quantity': 0}
                    
                    for t in transactions.values():
                        trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                        if start_date <= trans_date <= end_date:
                            for barcode, item in t['items'].items():
                                product = products.get(barcode, {})
                                category = product.get('category', 'Unknown')
                                
                                if category not in category_sales:
                                    category_sales[category] = {'revenue': 0.0, 'quantity': 0}
                                
                                category_sales[category]['quantity'] += item['quantity']
                                category_sales[category]['revenue'] += item['price'] * item['quantity']
                    
                    if not category_sales:
                        st.info("No category sales in selected date range")
                    else:
                        sales_df = pd.DataFrame.from_dict(category_sales, orient='index')
                        sales_df = sales_df.sort_values('revenue', ascending=False)
                        
                        st.subheader("Category Sales Summary")
                        st.dataframe(sales_df)
                        
                        st.subheader("Sales by Category")
                        st.bar_chart(sales_df['revenue'])
                
                elif report_type == "Cashier Performance":
                    # Cashier performance analysis
                    cashier_performance = {}
                    
                    for t in transactions.values():
                        trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                        if start_date <= trans_date <= end_date:
                            cashier = t['cashier']
                            if cashier not in cashier_performance:
                                cashier_performance[cashier] = {
                                    'transactions': 0,
                                    'total_sales': 0.0,
                                    'avg_sale': 0.0
                                }
                            
                            cashier_performance[cashier]['transactions'] += 1
                            cashier_performance[cashier]['total_sales'] += t['total']
                    
                    for cashier, data in cashier_performance.items():
                        if data['transactions'] > 0:
                            data['avg_sale'] = data['total_sales'] / data['transactions']
                    
                    if not cashier_performance:
                        st.info("No cashier data in selected date range")
                    else:
                        performance_df = pd.DataFrame.from_dict(cashier_performance, orient='index')
                        performance_df = performance_df.sort_values('total_sales', ascending=False)
                        
                        st.subheader("Cashier Performance Summary")
                        st.dataframe(performance_df)
                        
                        st.subheader("Sales by Cashier")
                        st.bar_chart(performance_df['total_sales'])
                
                # Export option
                csv = trans_df.to_csv(index=False)
                st.download_button(
                    label="Export Sales Data",
                    data=csv,
                    file_name=f"sales_report_{start_date}_to_{end_date}.csv",
                    mime="text/csv"
                )
    
    with tab2:
        st.header("Inventory Reports")
        
        inventory = load_data(INVENTORY_FILE)
        products = load_data(PRODUCTS_FILE)
        
        if not inventory:
            st.info("No inventory data available")
        else:
            report_type = st.selectbox("Inventory Report Type", [
                "Stock Levels",
                "Stock Value",
                "Stock Movement",
                "Inventory Audit"
            ])
            
            if report_type == "Stock Levels":
                # Current stock levels
                inventory_list = []
                for barcode, inv_data in inventory.items():
                    product = products.get(barcode, {'name': 'Unknown'})
                    inventory_list.append({
                        'product': product['name'],
                        'barcode': barcode,
                        'quantity': inv_data.get('quantity', 0),
                        'reorder_point': inv_data.get('reorder_point', 10)
                    })
                
                inv_df = pd.DataFrame(inventory_list)
                st.dataframe(inv_df)
            
            elif report_type == "Stock Value":
                # Stock value report
                value_list = []
                for barcode, inv_data in inventory.items():
                    product = products.get(barcode, {'name': 'Unknown', 'cost': 0})
                    value_list.append({
                        'product': product['name'],
                        'barcode': barcode,
                        'quantity': inv_data.get('quantity', 0),
                        'unit_cost': product.get('cost', 0),
                        'total_value': inv_data.get('quantity', 0) * product.get('cost', 0)
                    })
                
                value_df = pd.DataFrame(value_list)
                total_value = value_df['total_value'].sum()
                
                st.write(f"Total Inventory Value: {format_currency(total_value)}")
                st.dataframe(value_df.sort_values('total_value', ascending=False))
            
            elif report_type == "Stock Movement":
                # Stock movement report
                st.info("Select a product to view movement history")
                
                product_options = {f"{v['name']} ({k})": k for k, v in products.items()}
                selected_product = st.selectbox("Select Product", [""] + list(product_options.keys()))
                
                if selected_product:
                    barcode = product_options[selected_product]
                    inventory = load_data(INVENTORY_FILE)
                    
                    if barcode in inventory and 'adjustments' in inventory[barcode]:
                        adjustments = inventory[barcode]['adjustments']
                        st.dataframe(pd.DataFrame(adjustments))
                    else:
                        st.info("No adjustment history for this product")
            
            elif report_type == "Inventory Audit":
                st.info("Inventory audit would compare physical counts with system records")
                if st.button("Generate Audit Sheet"):
                    audit_data = []
                    for barcode, inv_data in inventory.items():
                        product = products.get(barcode, {'name': 'Unknown'})
                        audit_data.append({
                            'Product': product['name'],
                            'Barcode': barcode,
                            'System Quantity': inv_data.get('quantity', 0),
                            'Physical Count': "",
                            'Variance': "",
                            'Notes': ""
                        })
                    
                    audit_df = pd.DataFrame(audit_data)
                    st.dataframe(audit_df)
                    
                    csv = audit_df.to_csv(index=False)
                    st.download_button(
                        label="Download Audit Sheet",
                        data=csv,
                        file_name=f"inventory_audit_{datetime.date.today()}.csv",
                        mime="text/csv"
                    )
    
    with tab3:
        st.header("Customer Reports")
        
        loyalty = load_data(LOYALTY_FILE)
        customers = loyalty.get('customers', {})
        transactions = load_data(TRANSACTIONS_FILE)
        
        if not customers:
            st.info("No customer data available")
        else:
            report_type = st.selectbox("Customer Report Type", [
                "Customer Spending",
                "Loyalty Members",
                "Customer Segmentation"
            ])
            
            # Date range filter
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=30), key="cust_start_date")
            with col2:
                end_date = st.date_input("End Date", value=datetime.date.today(), key="cust_end_date")
            
            if report_type == "Customer Spending":
                # Customer spending analysis
                customer_spending = {}
                
                for cust_id, customer in customers.items():
                    customer_spending[cust_id] = {
                        'name': customer['name'],
                        'email': customer['email'],
                        'transactions': 0,
                        'total_spent': 0.0,
                        'avg_spend': 0.0
                    }
                
                for t in transactions.values():
                    trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                    if 'customer_id' in t and start_date <= trans_date <= end_date:
                        cust_id = t['customer_id']
                        if cust_id in customer_spending:
                            customer_spending[cust_id]['transactions'] += 1
                            customer_spending[cust_id]['total_spent'] += t['total']
                
                for cust_id, data in customer_spending.items():
                    if data['transactions'] > 0:
                        data['avg_spend'] = data['total_spent'] / data['transactions']
                
                if not customer_spending:
                    st.info("No customer spending data in selected date range")
                else:
                    spending_df = pd.DataFrame.from_dict(customer_spending, orient='index')
                    spending_df = spending_df.sort_values('total_spent', ascending=False)
                    
                    st.subheader("Customer Spending Summary")
                    st.dataframe(spending_df)
                    
                    st.subheader("Top Spending Customers")
                    top_n = st.slider("Show Top", 1, 20, 5, key="cust_top")
                    st.bar_chart(spending_df.head(top_n)['total_spent'])
            
            elif report_type == "Loyalty Members":
                # Loyalty members report
                loyalty_df = pd.DataFrame.from_dict(customers, orient='index')
                st.dataframe(loyalty_df[['name', 'email', 'points', 'tier']].sort_values('points', ascending=False))
            
            elif report_type == "Customer Segmentation":
                st.info("Customer segmentation would analyze purchasing patterns")
                if st.button("Generate Segmentation Report"):
                    st.warning("Segmentation analysis would be implemented here")
    
    with tab4:
        st.header("Payment Analysis")
        
        transactions = load_data(TRANSACTIONS_FILE)
        if not transactions:
            st.info("No transaction data available")
        else:
            # Date range filter
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=30), key="pay_start_date")
            with col2:
                end_date = st.date_input("End Date", value=datetime.date.today(), key="pay_end_date")
            
            # Payment method analysis
            payment_methods = {}
            
            for t in transactions.values():
                trans_date = datetime.datetime.strptime(t['date'], "%Y-%m-%d %H:%M:%S").date()
                if start_date <= trans_date <= end_date:
                    method = t['payment_method']
                    if method not in payment_methods:
                        payment_methods[method] = {'count': 0, 'total': 0.0}
                    
                    payment_methods[method]['count'] += 1
                    payment_methods[method]['total'] += t['total']
            
            if not payment_methods:
                st.info("No payment data in selected date range")
            else:
                payment_df = pd.DataFrame.from_dict(payment_methods, orient='index')
                payment_df = payment_df.sort_values('total', ascending=False)
                
                st.subheader("Payment Method Summary")
                st.dataframe(payment_df)
                
                st.subheader("Payment Method Distribution")
                st.bar_chart(payment_df['total'])
    
    with tab5:
        st.header("Custom Reports")
        
        st.info("Create custom reports with specific filters")
        
        with st.form("custom_report_form"):
            report_name = st.text_input("Report Name")
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=30), key="custom_start_date")
            with col2:
                end_date = st.date_input("End Date", value=datetime.date.today(), key="custom_end_date")
            
            report_type = st.selectbox("Report Type", [
                "Sales by Product",
                "Sales by Category",
                "Sales by Cashier",
                "Inventory Status"
            ])
            
            if st.form_submit_button("Generate Report"):
                st.success(f"Custom report '{report_name}' would be generated here")

# Shifts Management
def shifts_management():
    st.title("Shifts Management")
    
    shifts = load_data(SHIFTS_FILE)
    
    if is_cashier():
        # Cashier view - only show their shifts
        user_shifts = [s for s in shifts.values() if s['user_id'] == st.session_state.user_info['username']]
        user_shifts = sorted(user_shifts, key=lambda x: x['start_time'], reverse=True)
        
        st.header("Your Shifts")
        
        if not user_shifts:
            st.info("No shifts recorded")
        else:
            shift_df = pd.DataFrame(user_shifts)
            st.dataframe(shift_df[['start_time', 'end_time', 'starting_cash', 'ending_cash', 'status']])
        
        # Current shift actions
        if st.session_state.shift_started:
            st.subheader("Current Shift")
            current_shift = shifts.get(st.session_state.shift_id, {})
            
            st.write(f"Started at: {current_shift.get('start_time', 'N/A')}")
            st.write(f"Starting Cash: {format_currency(current_shift.get('starting_cash', 0))}")
            
            # Calculate current cash
            transactions = load_data(TRANSACTIONS_FILE)
            shift_transactions = [t for t in transactions.values() 
                                if t.get('shift_id') == st.session_state.shift_id and t['payment_method'] == 'Cash']
            total_cash = sum(t['total'] for t in shift_transactions)
            st.write(f"Current Cash: {format_currency(total_cash)}")
            
            if st.button("End Shift"):
                if end_shift():
                    st.success("Shift ended successfully")
                    st.rerun()
                else:
                    st.error("Failed to end shift")
        else:
            st.info("No active shift")
    
    else:
        # Manager/Admin view - show all shifts
        st.header("All Shifts")
        
        if not shifts:
            st.info("No shifts recorded")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                user_filter = st.selectbox("Filter by User", ["All"] + list(set(s['user_id'] for s in shifts.values())))
            with col2:
                status_filter = st.selectbox("Filter by Status", ["All", "active", "completed"])
            
            # Apply filters
            filtered_shifts = shifts.values()
            if user_filter != "All":
                filtered_shifts = [s for s in filtered_shifts if s['user_id'] == user_filter]
            if status_filter != "All":
                filtered_shifts = [s for s in filtered_shifts if s['status'] == status_filter]
            
            if not filtered_shifts:
                st.info("No shifts match the filters")
            else:
                shift_df = pd.DataFrame(filtered_shifts)
                shift_df = shift_df.sort_values('start_time', ascending=False)
                st.dataframe(shift_df[['user_id', 'start_time', 'end_time', 'starting_cash', 'ending_cash', 'status']])
        
        # Shift details
        if shifts:
            selected_shift = st.selectbox("View Shift Details", [""] + [f"{s['user_id']} - {s['start_time']}" for s in shifts.values()])
            
            if selected_shift:
                shift_id = [k for k, v in shifts.items() if f"{v['user_id']} - {v['start_time']}" == selected_shift][0]
                shift = shifts[shift_id]
                
                st.subheader("Shift Details")
                st.write(f"User: {shift['user_id']}")
                st.write(f"Start Time: {shift['start_time']}")
                st.write(f"End Time: {shift.get('end_time', 'Still active')}")
                st.write(f"Starting Cash: {format_currency(shift.get('starting_cash', 0))}")
                st.write(f"Ending Cash: {format_currency(shift.get('ending_cash', 0))}")
                st.write(f"Status: {shift['status']}")
                
                # Show transactions for this shift
                transactions = load_data(TRANSACTIONS_FILE)
                shift_transactions = [t for t in transactions.values() if t.get('shift_id') == shift_id]
                
                if shift_transactions:
                    st.subheader("Shift Transactions")
                    trans_df = pd.DataFrame(shift_transactions)
                    st.dataframe(trans_df[['transaction_id', 'date', 'total', 'payment_method']])

# System Settings
def system_settings():
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("System Settings")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Store Settings", "POS Configuration", "Tax Settings", "Printer Settings", "Hardware Settings"])
    
    with tab1:
        st.header("Store Information")
        
        settings = load_data(SETTINGS_FILE)
        
        with st.form("store_settings_form"):
            store_name = st.text_input("Store Name", value=settings.get('store_name', ''))
            store_address = st.text_area("Store Address", value=settings.get('store_address', ''))
            store_phone = st.text_input("Store Phone", value=settings.get('store_phone', ''))
            store_email = st.text_input("Store Email", value=settings.get('store_email', ''))
            
            logo = st.file_uploader("Store Logo", type=['jpg', 'png', 'jpeg'])
            if logo and 'logo' in settings and os.path.exists(settings['logo']):
                st.image(settings['logo'], width=150)
            
            receipt_header = st.text_area("Receipt Header Text", value=settings.get('receipt_header', ''))
            receipt_footer = st.text_area("Receipt Footer Text", value=settings.get('receipt_footer', ''))
            print_logo = st.checkbox("Print Logo on Receipt", value=settings.get('receipt_print_logo', False))
            
            if st.form_submit_button("Save Store Settings"):
                settings['store_name'] = store_name
                settings['store_address'] = store_address
                settings['store_phone'] = store_phone
                settings['store_email'] = store_email
                settings['receipt_header'] = receipt_header
                settings['receipt_footer'] = receipt_footer
                settings['receipt_print_logo'] = print_logo
                
                if logo:
                    # Remove old logo if exists
                    if 'logo' in settings and os.path.exists(settings['logo']):
                        os.remove(settings['logo'])
                    
                    # Save new logo
                    logo_path = os.path.join(DATA_DIR, f"store_logo.{logo.name.split('.')[-1]}")
                    with open(logo_path, 'wb') as f:
                        f.write(logo.getbuffer())
                    settings['logo'] = logo_path
                
                save_data(settings, SETTINGS_FILE)
                st.success("Store settings saved successfully")
    
    with tab2:
        st.header("POS Configuration")
        
        settings = load_data(SETTINGS_FILE)
        
        with st.form("pos_config_form"):
            receipt_template = st.selectbox(
                "Receipt Template",
                ["Simple", "Detailed", "Modern"],
                index=["Simple", "Detailed", "Modern"].index(settings.get('receipt_template', 'Simple'))
            )
            
            theme = st.selectbox(
                "Theme",
                ["Light", "Dark", "Blue"],
                index=["Light", "Dark", "Blue"].index(settings.get('theme', 'Light'))
            )
            
            timeout = st.number_input(
                "Session Timeout (minutes)",
                min_value=1,
                max_value=120,
                value=settings.get('session_timeout', 30)
            )
            
            timezone = st.selectbox(
                "Timezone",
                pytz.all_timezones,
                index=pytz.all_timezones.index(settings.get('timezone', 'UTC'))
            )
            
            currency_symbol = st.text_input(
                "Currency Symbol",
                value=settings.get('currency_symbol', '$')
            )
            
            decimal_places = st.number_input(
                "Decimal Places",
                min_value=0,
                max_value=4,
                value=settings.get('decimal_places', 2)
            )
            
            auto_logout = st.checkbox(
                "Enable Auto Logout",
                value=settings.get('auto_logout', True)
            )
            
            if st.form_submit_button("Save POS Configuration"):
                settings['receipt_template'] = receipt_template
                settings['theme'] = theme
                settings['session_timeout'] = timeout
                settings['timezone'] = timezone
                settings['currency_symbol'] = currency_symbol
                settings['decimal_places'] = decimal_places
                settings['auto_logout'] = auto_logout
                save_data(settings, SETTINGS_FILE)
                st.success("POS configuration saved successfully")
                st.rerun()  # Refresh to apply theme changes
    
    with tab3:
        st.header("Tax Settings")
        
        settings = load_data(SETTINGS_FILE)
        
        with st.form("tax_settings_form"):
            tax_rate = st.number_input(
                "Tax Rate (%)",
                min_value=0.0,
                max_value=25.0,
                value=settings.get('tax_rate', 0.0) * 100,
                step=0.1
            )
            
            tax_inclusive = st.checkbox(
                "Prices Include Tax",
                value=settings.get('tax_inclusive', False)
            )
            
            if st.form_submit_button("Save Tax Settings"):
                settings['tax_rate'] = tax_rate / 100
                settings['tax_inclusive'] = tax_inclusive
                save_data(settings, SETTINGS_FILE)
                st.success("Tax settings saved successfully")
    
   # In the System Settings section (tab4), replace the printer settings with:

    with tab4:
       st.header("Printer Settings")
    
       settings = load_data(SETTINGS_FILE)
    
       with st.form("printer_settings_form"):
         printer_name = st.text_input(
            "Printer Name (for reference only)",
            value=settings.get('printer_name', 'Browser Printer')
         )
        
         test_print = st.text_area("Test Receipt Text", 
                                value="POS System Test Receipt\n====================\nTest Line 1\nTest Line 2\n====================")
        
         col1, col2 = st.columns(2)
         with col1:
            if st.form_submit_button("Save Printer Settings"):
                settings['printer_name'] = printer_name
                save_data(settings, SETTINGS_FILE)
                st.success("Printer settings saved successfully")
         with col2:
            if st.form_submit_button("Test Print"):
                if print_receipt(test_print):
                    st.success("Test receipt printed successfully")
                else:
                    st.error("Failed to print test receipt")
    
   # In the system_settings function, replace the hardware settings section with:

    with tab5:
     st.header("Hardware Settings")
    
     settings = load_data(SETTINGS_FILE)
     com_ports = get_available_com_ports()
    
     with st.form("hardware_settings_form"):
        barcode_scanner_type = st.selectbox(
            "Barcode Scanner Type",
            ["Keyboard", "Serial Scanner"],
            index=0 if settings.get('barcode_scanner', 'keyboard') == 'keyboard' else 1
        )
        
        barcode_scanner_port = st.selectbox(
            "Barcode Scanner Port (for serial scanners)",
            com_ports,
            index=com_ports.index(settings.get('barcode_scanner_port', 'auto'))
        )
        
        cash_drawer_enabled = st.checkbox(
            "Enable Cash Drawer",
            value=settings.get('cash_drawer_enabled', False)
        )
        
        cash_drawer_command = st.text_input(
            "Cash Drawer Command",
            value=settings.get('cash_drawer_command', '')
        )
        
        if st.form_submit_button("Save Hardware Settings"):
            # Stop any existing scanner
            if 'barcode_scanner' in globals() and hasattr(barcode_scanner, 'stop_scanning'):
                barcode_scanner.stop_scanning()
            
            # Update settings
            settings['barcode_scanner'] = barcode_scanner_type.lower().replace(' ', '_')
            settings['barcode_scanner_port'] = barcode_scanner_port
            settings['cash_drawer_enabled'] = cash_drawer_enabled
            settings['cash_drawer_command'] = cash_drawer_command
            save_data(settings, SETTINGS_FILE)
            
            # Reinitialize scanner with new settings
            setup_barcode_scanner()
            st.success("Hardware settings saved successfully")

# Backup & Restore
def backup_restore():
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    st.title("Backup & Restore")
    
    tab1, tab2 = st.tabs(["Create Backup", "Restore Backup"])
    
    with tab1:
        st.header("Create System Backup")
        
        st.info("This will create a complete backup of all system data")
        
        if st.button("Create Backup Now"):
            backup_path = create_backup()
            st.success(f"Backup created successfully at: {backup_path}")
            
            with open(backup_path, 'rb') as f:
                st.download_button(
                    label="Download Backup",
                    data=f,
                    file_name=os.path.basename(backup_path),
                    mime="application/zip"
                )
    
    with tab2:
        st.header("Restore System Backup")
        
        st.warning("Restoring a backup will overwrite all current data. Proceed with caution.")
        
        backup_file = st.file_uploader("Upload Backup File", type=['zip'])
        
        if backup_file and st.button("Restore Backup"):
            try:
                # Save the uploaded file temporarily
                temp_backup = os.path.join(BACKUP_DIR, "temp_restore.zip")
                with open(temp_backup, 'wb') as f:
                    f.write(backup_file.getbuffer())
                
                # Restore from the temporary file
                if restore_backup(temp_backup):
                    st.success("Backup restored successfully")
                    st.rerun()  # Refresh to load the restored data
                else:
                    st.error("Failed to restore backup")
                
                # Clean up
                os.remove(temp_backup)
            except Exception as e:
                st.error(f"Error during restore: {str(e)}")

# Main App
def main():
    # Set page config
    st.set_page_config(
        page_title="Supermarket POS",
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply theme from settings
    settings = load_data(SETTINGS_FILE)
    if settings.get('theme') == 'Dark':
        dark_theme = """
        <style>
        .stApp { background-color: #1E1E1E; color: white; }
        .st-bb { background-color: #1E1E1E; }
        .st-at { background-color: #2E2E2E; }
        </style>
        """
        st.markdown(dark_theme, unsafe_allow_html=True)
    elif settings.get('theme') == 'Blue':
        blue_theme = """
        <style>
        .stApp { background-color: #E6F3FF; }
        </style>
        """
        st.markdown(blue_theme, unsafe_allow_html=True)
    
    # Page routing
    if st.session_state.current_page == "Login":
        login_page()
    else:
        dashboard()

if __name__ == "__main__":
    main()                                                      