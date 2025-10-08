import streamlit as st
import time
import pandas as pd
import plotly.express as px
from pathlib import Path
import os
import sys
import logging
import random
from textblob import TextBlob
from hashlib import sha256
import sqlite3
from price_predictor import PricePredictor, PricePredictionDatabase
import plotly.graph_objects as go
from price_alert_system import PriceAlertSystem

# Import functions from your existing scripts 
from amaz import setup_chrome_driver, find_lowest_price_product, find_multiple_products, AmazonReviewScraper,find_multiple_products_improved
from flipAPI import FlipkartProductSearch, FlipkartReviewScraper

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEBUG = True

def log_debug(message):
    if DEBUG:
        print(f"[DEBUG] {message}")

# Configure page
st.set_page_config(
    page_title="CompareIt - Amazon vs Flipkart",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)
SMTP_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'from_email': 'compareshoppingassitant@gmail.com',  # Replace with your email
    'password': 'xmjx aanv vhsz tjjb'  # Replace with Gmail app password
}

# User Authentication Database Setup
# User Authentication Database Setup
def create_userdb():
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_user(username, password, email):
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    try:
        hashed_password = sha256(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", 
                      (username, hashed_password, email))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def authenticate_user(username, password):
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    hashed_password = sha256(password.encode()).hexdigest()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                  (username, hashed_password))
    result = cursor.fetchone()
    conn.close()
    return result

def get_user_email(username):
    """Get the email address for a given username"""
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Create user database on startup
create_userdb()

# Initialize session states
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'flipkart_selected_product' not in st.session_state:
    st.session_state.flipkart_selected_product = None
if 'amazon_selected_product' not in st.session_state:
    st.session_state.amazon_selected_product = None
if 'analyze_reviews_clicked' not in st.session_state:
    st.session_state.analyze_reviews_clicked = False
if 'flipkart_products' not in st.session_state:
    st.session_state.flipkart_products = None
if 'amazon_products' not in st.session_state:
    st.session_state.amazon_products = None
if 'max_review_pages' not in st.session_state:
    st.session_state.max_review_pages = 2
if 'driver_path' not in st.session_state:
    st.session_state.driver_path = "chromedriver.exe"
# ADD THESE NEW SESSION STATES HERE:
if 'price_predictions_flipkart' not in st.session_state:
    st.session_state.price_predictions_flipkart = None
if 'price_predictions_amazon' not in st.session_state:
    st.session_state.price_predictions_amazon = None
if 'predictor' not in st.session_state:
    st.session_state.predictor = PricePredictor()
if 'alert_system' not in st.session_state:
    st.session_state.alert_system = PriceAlertSystem()

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
        padding: 10px;
        font-weight: bold;
        color: #000;
    }
    .sub-header {
        font-size: 1.5rem;
        margin-bottom: 1rem;
    }
    .platform-header {
        font-size: 1.8rem;
        text-align: center;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: white;
    }
    .flipkart-header {
        background-color: #2874F0;
    }
    .amazon-header {
        background-color: #FF9900;
    }
    .platform-container {
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        height: 100%;
    }
    .flipkart-container {
        border: 2px solid #2874F0;
        background-color: #F5F7FF;
    }
    .amazon-container {
        border: 2px solid #FF9900;
        background-color: #FFF8E1;
    }
    .card {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .price-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 15px;
        color: white;
        font-weight: bold;
        font-size: 0.9rem;
        margin-bottom: 10px;
    }
    .flipkart-price {
        background-color: #2874F0;
    }
    .amazon-price {
        background-color: #FF9900;
    }
    .winner-badge {
        display: inline-block;
        padding: 8px 15px;
        border-radius: 20px;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        font-size: 1rem;
        margin-bottom: 10px;
    }
    .positive {
        color: #2E7D32;
        font-weight: bold;
    }
    .negative {
        color: #C62828;
        font-weight: bold;
    }
    .neutral {
        color: #757575;
        font-weight: bold;
    }
    .verdict {
        font-size: 1.3rem;
        text-align: center;
        padding: 10px;
        border-radius: 5px;
        margin-top: 10px;
        font-weight: bold;
    }
    .verdict-buy {
        background-color: #E8F5E9;
        color: #2E7D32;
    }
    .verdict-dont-buy {
        background-color: #FFEBEE;
        color: #C62828;
    }
    .verdict-neutral {
        background-color: #F5F5F5;
        color: #757575;
    }
    .comparison-header {
        background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        font-size: 1.5rem;
        font-weight: bold;
    }
    .footer {
        text-align: center;
        margin-top: 30px;
        color: #757575;
        font-size: 0.8rem;
        padding: 20px;
        border-top: 1px solid #DDD;
    }
    .prediction-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .prediction-insight {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 10px;
        margin: 10px 0;
    }
    .trend-up {
        color: #dc3545;
        font-weight: bold;
    }
    .trend-down {
        color: #28a745;
        font-weight: bold;
    }
    .platform-logo {
        display: block;
        margin: 0 auto;
        max-height: 60px;
        margin-bottom: 10px;
    }
    .product-title {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .search-btn-flipkart {
        background-color: #2874F0;
        color: white;
    }
    .search-btn-amazon {
        background-color: #FF9900;
        color: black;
    }
    .review-btn-combined {
        background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
        text-align: center;
        font-weight: bold;
        margin: 10px auto;
        display: block;
        width: 100%;
    }
    .price-win {
        font-size: 1.3rem;
        font-weight: bold;
        color: #4CAF50;
    }
    .price-lose {
        font-size: 1.1rem;
        color: #757575;
    }
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 30px;
        border-radius: 10px;
        background-color: #FFFFFF;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        color: #333;
    }
    .login-header {
        font-size: 1.8rem;
        text-align: center;
        margin-bottom: 20px;
        background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
    }
    .login-btn {
        background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
        text-align: center;
        font-weight: bold;
        width: 100%;
        margin-top: 10px;
    }
    .tab-container {
        margin-bottom: 20px;
    }
    
    /* Hide default Streamlit elements on login page */
    .css-18e3th9.egzxvld2 {
        padding-top: 0;
    }
    
    /* Full-screen login container styles */
    .full-screen-login {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #f5f7fb;
        z-index: 1000;
        padding: 20px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Hide sidebar when on login page */
    div[data-testid="stSidebarUserContent"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

def show_login_page():
    st.markdown("<h1 class='main-header'>🔍 CompareIT: Amazon vs Flipkart</h1>", unsafe_allow_html=True)
    
    # Create login container
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 class='login-header'>Welcome to CompareIT</h2>", unsafe_allow_html=True)
    
    # Create login/signup tabs
    tab1, tab2 = st.tabs(["Login", "Signup"])
    
    with tab1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button"):
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")
    
    with tab2:
        new_username = st.text_input("New Username", key="signup_username")
        new_email = st.text_input("Email Address", key="signup_email", 
                                   placeholder="your.email@example.com")
        new_password = st.text_input("New Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", 
                                        key="confirm_password")
        
        if st.button("Sign Up", key="signup_button"):
            if not new_email or "@" not in new_email or "." not in new_email:
                st.error("Please enter a valid email address.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters long.")
            elif add_user(new_username, new_password, new_email):
                st.success("Account created successfully! You can now login.")
            else:
                st.error("Username already exists. Please choose a different one.")
    
    st.markdown("</div>", unsafe_allow_html=True)
def show_main_app():
    st.markdown("<h1 class='main-header' style='color: black; -webkit-text-fill-color: black;'>🔍 CompareIT: Amazon vs Flipkart</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Find the best deals across platforms and analyze review sentiment</p>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        div[data-testid="stSidebarUserContent"] {
            display: block !important;
        }
        </style>
        """, 
        unsafe_allow_html=True
    )
    def show_price_alerts_section():
        st.markdown("---")
        st.markdown("### 🔔 Price Alerts")
        
        if st.session_state.logged_in:
            user_email = get_user_email(st.session_state.username)
            
            if not user_email:
                st.warning("⚠️ No email found. Please contact support.")
                return
            
            alerts = st.session_state.alert_system.get_user_alerts(user_email)
            
            if alerts:
                st.write(f"You have {len(alerts)} active alert(s)")
                st.caption(f"Alerts sent to: {user_email}")
                
                with st.expander("Manage Alerts"):
                    for alert in alerts:
                        alert_id, product_name, platform, current_price, target_price, product_url = alert
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{product_name[:30]}...**")
                            st.write(f"{platform} - ₹{current_price:,.2f}")
                            if target_price:
                                st.write(f"Target: ₹{target_price:,.2f}")
                        
                        with col2:
                            if st.button("🗑️", key=f"delete_{alert_id}"):
                                st.session_state.alert_system.delete_alert(alert_id)
                                st.success("Alert deleted!")
                                st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No active alerts")
                st.caption(f"Alerts will be sent to: {user_email}")
        else:
            st.info("Login to set up price alerts")
    # Sidebar configuration
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        # Search settings
        st.markdown("#### 🔎 Search Configuration")
        max_products = st.slider("Maximum products to display", 3, 10, 5)
        
        # Review settings
        st.markdown("#### 📊 Review Analysis")
        max_review_pages = st.slider("Maximum review pages to scrape", 1, 5, 2)
        
        # Chrome driver path
        st.markdown("#### 🌐 Browser Configuration")
        driver_path = st.text_input("ChromeDriver path", value="chromedriver.exe")
        
        # Advanced options (collapsible)
        with st.expander("Advanced Options"):
            wait_time = st.slider("Page load wait time (seconds)", 2, 10, 5)
            debug_mode = st.checkbox("Enable debug mode", False)
        
        show_price_alerts_section()
        
        
        st.markdown("---")
        st.markdown("### 📖 How to use")
        st.markdown("""
        1. Enter product name in the search box
        2. Click 'Compare Prices' button
        3. View products from both platforms
        4. Compare prices and see the best deal
        5. Click 'Analyze Reviews' to see sentiment from both platforms
        6. Make your final buying decision based on price and sentiment
        """)
        
    # Initialize session state for both platforms
    if 'flipkart_selected_product' not in st.session_state:
        st.session_state.flipkart_selected_product = None

    if 'amazon_selected_product' not in st.session_state:
        st.session_state.amazon_selected_product = None

    if 'analyze_reviews_clicked' not in st.session_state:
        st.session_state.analyze_reviews_clicked = False

    if 'flipkart_products' not in st.session_state:
        st.session_state.flipkart_products = None

    if 'amazon_products' not in st.session_state:
        st.session_state.amazon_products = None

    if 'max_review_pages' not in st.session_state:
        st.session_state.max_review_pages = max_review_pages

    if 'driver_path' not in st.session_state:
        st.session_state.driver_path = driver_path

    # Set max review pages when slider changes
    st.session_state.max_review_pages = max_review_pages
    st.session_state.driver_path = driver_path

    # Main search section
    st.markdown("<div class='comparison-header'>🔎 Search Products Across Platforms</div>", unsafe_allow_html=True)

    # Search input
    search_term = st.text_input("What product are you looking for?")

    # Compare button
    if st.button("Compare Prices", key="compare_button") and search_term:
        col1, col2 = st.columns(2)
        
        with col1:
            with st.status("Searching Flipkart...") as status:
                st.write(f"Searching for: {search_term}")
                
                # Setup chrome driver path
                if not os.path.isfile(driver_path):
                    st.warning(f"ChromeDriver not found at '{driver_path}'. The search may fail.")
                
                # Find products
                try:
                    product_searcher = FlipkartProductSearch(driver_path)
                    flipkart_products = product_searcher.search_products(search_term)
                    
                    if flipkart_products:
                        lowest_price_product = product_searcher.get_lowest_price_product()
                        st.session_state.flipkart_products = flipkart_products
                        status.update(label="Flipkart search complete!", state="complete")
                    else:
                        status.update(label="No products found on Flipkart", state="error")
                        st.session_state.flipkart_products = None
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    status.update(label="Flipkart search failed", state="error")
                    st.session_state.flipkart_products = None
        
        with col2:
            with st.status("Searching Amazon...") as status:
                st.write(f"Searching for: {search_term}")
                
                # Find multiple products from Amazon
                try:
                    amazon_products = find_multiple_products_improved(search_term, driver_path, max_products=5)
                    
                    if amazon_products:
                        st.session_state.amazon_products = amazon_products
                        status.update(label="Amazon search complete!", state="complete")
                        st.write(f"Found {len(amazon_products)} products")
                    else:
                        status.update(label="No products found on Amazon", state="error")
                        st.session_state.amazon_products = None
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    status.update(label="Amazon search failed", state="error")
                    st.session_state.amazon_products = None

    # Display comparison if products are available from both platforms
    if st.session_state.flipkart_products is not None or st.session_state.amazon_products is not None:
        st.markdown("<div class='comparison-header'>📊 Price Comparison Results</div>", unsafe_allow_html=True)
        
        flipkart_col, amazon_col = st.columns(2)
        
        # FLIPKART SECTION
        with flipkart_col:
            st.markdown("<div class='platform-container flipkart-container'>", unsafe_allow_html=True)
            st.markdown("<h2 class='platform-header flipkart-header'>Flipkart</h2>", unsafe_allow_html=True)
            st.image("https://logos-world.net/wp-content/uploads/2020/11/Flipkart-Emblem.png", width=150, use_column_width=False)
            
            if st.session_state.flipkart_products:
                # Display the lowest price product from Flipkart
                lowest_product = st.session_state.flipkart_products[0]  # Assuming products are sorted by price
                
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown("<span class='price-badge flipkart-price'>Best Price on Flipkart</span>", unsafe_allow_html=True)
                st.markdown(f"<p class='product-title'>{lowest_product['title']}</p>", unsafe_allow_html=True)
                st.markdown(f"<p class='price-win'>{lowest_product['price_text']}</p>", unsafe_allow_html=True)
                st.markdown(f"[View on Flipkart]({lowest_product['link']})")
                st.session_state.flipkart_selected_product = lowest_product
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Show all products from Flipkart in an expander
                with st.expander("View All Flipkart Products"):
                    for idx, product in enumerate(st.session_state.flipkart_products):
                        st.markdown(f"{idx+1}. **{product['title']}** - {product['price_text']}")
                        st.markdown(f"[View on Flipkart]({product['link']})")
                        st.markdown("---")
            else:
                st.info("No products found on Flipkart for this search term.")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # AMAZON SECTION
        with amazon_col:
            st.markdown("<div class='platform-container amazon-container'>", unsafe_allow_html=True)
            st.markdown("<h2 class='platform-header amazon-header'>Amazon</h2>", unsafe_allow_html=True)
            st.image("https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg", width=100, use_column_width=False)
            
            if st.session_state.amazon_products:
                # Display the lowest price product from Amazon
                lowest_product = st.session_state.amazon_products[0]  # Assuming products are sorted by price
                
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown("<span class='price-badge amazon-price'>Best Price on Amazon</span>", unsafe_allow_html=True)
                st.markdown(f"<p class='product-title'>{lowest_product[0]}</p>", unsafe_allow_html=True)
                st.markdown(f"<p class='price-win'>₹{lowest_product[1]:,.2f}</p>", unsafe_allow_html=True)
                st.markdown(f"[View on Amazon]({lowest_product[2]})")
                st.session_state.amazon_selected_product = lowest_product
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Show all products from Amazon in an expander
                with st.expander("View All Amazon Products"):
                    for idx, product in enumerate(st.session_state.amazon_products):
                        st.markdown(f"{idx+1}. **{product[0]}** - ₹{product[1]:,.2f}")
                        st.markdown(f"[View on Amazon]({product[2]})")
                        st.markdown("---")
            else:
                st.info("No products found on Amazon for this search term.")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        def add_alert_button(product_name, product_url, platform, current_price):
            if st.session_state.logged_in:
                with st.expander("🔔 Set Price Alert"):
                    st.write("Get notified when the price drops!")
                    
                    # Get user's real email
                    user_email = get_user_email(st.session_state.username)
                    
                    if not user_email:
                        st.error("❌ Email not found in your account. Please contact support.")
                        return
                    
                    st.info(f"📧 Alerts will be sent to: **{user_email}**")
                    
                    # Option to set target price
                    use_target = st.checkbox("Set target price", value=False, 
                                            key=f"target_check_{platform}_{product_name[:10]}")
                    
                    if use_target:
                        target_price = st.number_input(
                            "Alert me when price drops below:",
                            min_value=0.0,
                            value=current_price * 0.9,
                            step=100.0,
                            key=f"target_price_{platform}_{product_name[:10]}"
                        )
                    else:
                        target_price = None
                        st.info("You'll be notified of any price drop")
                    
                    if st.button("Set Alert", key=f"alert_{platform}_{product_name[:20]}"):
                        alert_id = st.session_state.alert_system.add_price_alert(
                            user_email=user_email,
                            product_name=product_name,
                            product_url=product_url,
                            platform=platform,
                            current_price=current_price,
                            target_price=target_price
                        )
                        
                        st.success(f"✅ Price alert created! We'll email you at **{user_email}** when the price drops.")
            else:
                with st.expander("🔔 Set Price Alert"):
                    st.warning("Please login to set price alerts")
        
        # Combined Review Analysis Button (shown only if both products are selected)
        if st.session_state.flipkart_selected_product and st.session_state.amazon_selected_product:
            st.markdown("<div style='text-align: center; margin: 20px 0;'>", unsafe_allow_html=True)
            if st.button("Analyze Reviews on Both Platforms", key="analyze_both", use_container_width=True, 
                    help="This will analyze reviews from both Amazon and Flipkart"):
                st.session_state.analyze_reviews_clicked = True

            st.markdown("</div>", unsafe_allow_html=True)
        
        # WINNER SECTION - Show the best deal across platforms
        if st.session_state.flipkart_products and st.session_state.amazon_products:
            st.markdown("<div class='comparison-header'>🏆 Best Deal Overall</div>", unsafe_allow_html=True)
            
            # Get lowest price from each platform
            flipkart_lowest = st.session_state.flipkart_products[0]
            amazon_lowest = st.session_state.amazon_products[0]
            
            # Extract and clean prices for comparison
            # Assuming Flipkart price format is like "₹12,345" or "₹12,345.00"
            flipkart_price_text = flipkart_lowest['price_text']
            flipkart_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
            amazon_price = amazon_lowest[1]
            
            # Compare prices
            winner_col1, winner_col2 = st.columns(2)
            
            if flipkart_price < amazon_price:
                # Flipkart wins
                with winner_col1:
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    st.markdown("<span class='winner-badge'>BEST DEAL 🏆</span>", unsafe_allow_html=True)
                    st.image("https://logos-world.net/wp-content/uploads/2020/11/Flipkart-Emblem.png", width=120)
                    st.markdown(f"<p class='product-title'>{flipkart_lowest['title']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='price-win'>{flipkart_lowest['price_text']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p>You save: ₹{(amazon_price - flipkart_price):.2f} ({((amazon_price - flipkart_price) / amazon_price * 100):.1f}%)</p>", unsafe_allow_html=True)
                    st.markdown(f"[View on Flipkart]({flipkart_lowest['link']})")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with winner_col2:
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg", width=80)
                    st.markdown(f"<p class='product-title'>{amazon_lowest[0]}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='price-lose'>₹{amazon_price:,.2f}</p>", unsafe_allow_html=True)
                    st.markdown(f"[View on Amazon]({amazon_lowest[2]})")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                if st.session_state.flipkart_selected_product:
                    flipkart_product = st.session_state.flipkart_selected_product
                    flipkart_price = float(flipkart_product['price_text'].replace('₹', '').replace(',', '').strip().split('.')[0])
                    
                    add_alert_button(
                        product_name=flipkart_product['title'],
                        product_url=flipkart_product['link'],
                        platform="Flipkart",
                        current_price=flipkart_price
                    )
            else:
                # Amazon wins
                with winner_col1:
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    st.image("https://logos-world.net/wp-content/uploads/2020/11/Flipkart-Emblem.png", width=120)
                    st.markdown(f"<p class='product-title'>{flipkart_lowest['title']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='price-lose'>{flipkart_lowest['price_text']}</p>", unsafe_allow_html=True)
                    st.markdown(f"[View on Flipkart]({flipkart_lowest['link']})")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with winner_col2:
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    st.markdown("<span class='winner-badge'>BEST DEAL 🏆</span>", unsafe_allow_html=True)
                    st.image("https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg", width=80)
                    st.markdown(f"<p class='product-title'>{amazon_lowest[0]}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='price-win'>₹{amazon_price:,.2f}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p>You save: ₹{(flipkart_price - amazon_price):.2f} ({((flipkart_price - amazon_price) / flipkart_price * 100):.1f}%)</p>", unsafe_allow_html=True)
                    st.markdown(f"[View on Amazon]({amazon_lowest[2]})")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                if st.session_state.amazon_selected_product:
                    amazon_product = st.session_state.amazon_selected_product
                    
                    add_alert_button(
                        product_name=amazon_product[0],
                        product_url=amazon_product[2],
                        platform="Amazon",
                        current_price=amazon_product[1]
                    )

    # Combined review analysis - Execute when the analyze button is clicked
    if st.session_state.analyze_reviews_clicked and st.session_state.flipkart_selected_product and st.session_state.amazon_selected_product:
        st.markdown("<div class='comparison-header'>📊 Combined Review Analysis</div>", unsafe_allow_html=True)
        
        # Create columns for side-by-side analysis
        flipkart_review_col, amazon_review_col = st.columns(2)
        
        # FLIPKART REVIEW ANALYSIS
        with flipkart_review_col:
            st.markdown("<div class='platform-container flipkart-container'>", unsafe_allow_html=True)
            st.markdown("<h2 class='platform-header flipkart-header'>Flipkart Reviews</h2>", unsafe_allow_html=True)
            
            with st.status("Analyzing Flipkart reviews...") as status:
                st.write(f"Setting up for: {st.session_state.flipkart_selected_product['title']}")
                
                # Use chrome driver path from session state
                driver_path = st.session_state.driver_path
                
                # Initialize review scraper and analyze reviews
                try:
                    scraper = FlipkartReviewScraper(driver_path)
                    
                    st.write("Navigating to product page...")
                    all_reviews, all_titles, decision, product_info = scraper.scrape_reviews(
                        st.session_state.flipkart_selected_product['link'], 
                        pages_to_scrape=st.session_state.max_review_pages
                    )
                    
                    status.update(label="Flipkart analysis complete!", state="complete")
                except Exception as e:
                    st.error(f"An error occurred during review analysis: {str(e)}")
                    status.update(label="Analysis failed", state="error")
                    all_reviews, all_titles, decision = [], [], "Unable to determine"
            
            # Display review data
            if all_reviews or all_titles:
                # Create combined list of all review content
                all_content = all_reviews + all_titles
                
                # Create DataFrame for reviews with sentiment
                reviews_data = []
                positive_count = 0
                negative_count = 0
                neutral_count = 0
                
                for review in all_content:
                    sentiment = TextBlob(review).sentiment.polarity
                    sentiment_label = ""
                    
                    if sentiment > 0.1:
                        sentiment_label = "Positive 👍"
                        positive_count += 1
                    elif sentiment < -0.1:
                        sentiment_label = "Negative 👎"
                        negative_count += 1
                    else:
                        sentiment_label = "Neutral 😐"
                        neutral_count += 1
                        
                    reviews_data.append({
                        "Review": review[:100] + "..." if len(review) > 100 else review,
                        "Sentiment": sentiment_label,
                        "Score": round(sentiment, 2)
                    })
                
                reviews_df = pd.DataFrame(reviews_data)
                
                # Display tabs for different review content
                tab1, tab2 = st.tabs(["Review Sentiment", "All Reviews"])
                
                with tab1:
                    # Calculate statistics
                    total = positive_count + negative_count + neutral_count
                    
                    # Create sentiment distribution chart
                    if total > 0:
                        dist_data = {
                            "Sentiment": ["Positive 👍", "Neutral 😐", "Negative 👎"],
                            "Count": [positive_count, neutral_count, negative_count],
                            "Percentage": [
                                positive_count/total*100 if total > 0 else 0,
                                neutral_count/total*100 if total > 0 else 0,
                                negative_count/total*100 if total > 0 else 0
                            ]
                        }
                        
                        dist_df = pd.DataFrame(dist_data)
                        
                        # Display pie chart
                        colors = {
                            "Positive 👍": "#4CAF50", 
                            "Neutral 😐": "#9E9E9E", 
                            "Negative 👎": "#F44336"
                        }
                        
                        fig = px.pie(
                            dist_df, 
                            values="Count", 
                            names="Sentiment", 
                            title="Flipkart Review Sentiment",
                            color="Sentiment",
                            color_discrete_map=colors
                        )
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Display verdict
                        verdict_class = ""
                        if "Buy ✅" in decision:
                            verdict_class = "verdict verdict-buy"
                        elif "Don't Buy ❌" in decision:
                            verdict_class = "verdict verdict-dont-buy"
                        else:
                            verdict_class = "verdict verdict-neutral"
                        
                        st.markdown(f"<div class='{verdict_class}'>{decision}</div>", unsafe_allow_html=True)
                
                with tab2:
                    st.write(f"Total content analyzed: {len(all_content)}")
                    st.dataframe(reviews_df, use_container_width=True)
            
            else:
                st.warning("No reviews were found for this product on Flipkart.")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # AMAZON REVIEW ANALYSIS
        with amazon_review_col:
            st.markdown("<div class='platform-container amazon-container'>", unsafe_allow_html=True)
            st.markdown("<h2 class='platform-header amazon-header'>Amazon Reviews</h2>", unsafe_allow_html=True)
            
            with st.status("Analyzing Amazon reviews...") as status:
                st.write(f"Setting up for: {st.session_state.amazon_selected_product[0]}")
                
                # Setup chrome driver path
                driver_path = st.session_state.driver_path
                
                # Initialize review scraper and analyze reviews
                try:
                    scraper = AmazonReviewScraper(driver_path)
                    
                    st.write("Navigating to product page...")
                    review_titles, decision = scraper.scrape_review_titles(
                        st.session_state.amazon_selected_product[2], 
                        max_pages=st.session_state.max_review_pages
                    )
                    
                    status.update(label="Amazon analysis complete!", state="complete")
                except Exception as e:
                    st.error(f"An error occurred during review analysis: {str(e)}")
                    status.update(label="Analysis failed", state="error")
                    review_titles, decision = [], "Unable to determine"
            
            # Display review data
            if review_titles:
                # Create DataFrame for reviews with sentiment
                reviews_data = []
                positive_count = 0
                negative_count = 0
                neutral_count = 0
                
                for review in review_titles:
                    sentiment = TextBlob(review).sentiment.polarity
                    sentiment_label = ""
                    
                    if sentiment > 0.1:
                        sentiment_label = "Positive 👍"
                        positive_count += 1
                    elif sentiment < -0.1:
                        sentiment_label = "Negative 👎"
                        negative_count += 1
                    else:
                        sentiment_label = "Neutral 😐"
                        neutral_count += 1
                        
                    reviews_data.append({
                        "Review": review,
                        "Sentiment": sentiment_label,
                        "Score": round(sentiment, 2)
                    })
                
                reviews_df = pd.DataFrame(reviews_data)
                
                # Display tabs for different review content
                tab1, tab2 = st.tabs(["Review Sentiment", "All Reviews"])
                
                with tab1:
                    # Calculate statistics
                    total = positive_count + negative_count + neutral_count
                    
                    # Create sentiment distribution chart
                    if total > 0:
                        dist_data = {
                            "Sentiment": ["Positive 👍", "Neutral 😐", "Negative 👎"],
                            "Count": [positive_count, neutral_count, negative_count],
                            "Percentage": [
                                positive_count/total*100 if total > 0 else 0,
                                neutral_count/total*100 if total > 0 else 0,
                                negative_count/total*100 if total > 0 else 0
                            ]
                        }
                        
                        dist_df = pd.DataFrame(dist_data)
                        
                        # Display pie chart
                        colors = {
                            "Positive 👍": "#4CAF50", 
                            "Neutral 😐": "#9E9E9E", 
                            "Negative 👎": "#F44336"
                        }
                        
                        fig = px.pie(
                            dist_df, 
                            values="Count", 
                            names="Sentiment", 
                            title="Amazon Review Sentiment",
                            color="Sentiment",
                            color_discrete_map=colors
                        )
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Display verdict
                        verdict_class = ""
                        if "Buy ✅" in decision:
                            verdict_class = "verdict verdict-buy"
                        elif "Don't Buy ❌" in decision:
                            verdict_class = "verdict verdict-dont-buy"
                        else:
                            verdict_class = "verdict verdict-neutral"
                        
                        st.markdown(f"<div class='{verdict_class}'>{decision}</div>", unsafe_allow_html=True)
                
                with tab2:
                    st.write(f"Total reviews analyzed: {len(review_titles)}")
                    st.dataframe(reviews_df, use_container_width=True)
            
            else:
                st.warning("No reviews were found for this product on Amazon.")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Overall Recommendation Section
        # Replace the Final Recommendation Section in your pricefull.py
# Around lines 450-550, replace the existing recommendation logic with this:

    st.markdown("<div class='comparison-header'>🤔 Final Recommendation</div>", unsafe_allow_html=True)
            
    # Get data from both analyses
    flipkart_decision = decision if 'decision' in locals() else "Unable to determine"
    amazon_decision = decision if 'decision' in locals() else "Unable to determine"
    
    # Display combined recommendation
    rec_col1, rec_col2, rec_col3 = st.columns([1, 2, 1])
    
    with rec_col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        # Extract price data
        flipkart_price_text = st.session_state.flipkart_selected_product['price_text']
        flipkart_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
        amazon_price = st.session_state.amazon_selected_product[1]
        
        # Analyze price difference
        price_diff = abs(flipkart_price - amazon_price)
        price_diff_percent = price_diff / max(flipkart_price, amazon_price) * 100
        
        # Determine where to buy based on price and reviews
        if flipkart_price < amazon_price:
            price_winner = "Flipkart"
            price_loser = "Amazon"
            price_save = price_diff
            price_save_percent = price_diff / amazon_price * 100
        else:
            price_winner = "Amazon"
            price_loser = "Flipkart"
            price_save = price_diff
            price_save_percent = price_diff / flipkart_price * 100
        
        # Make final recommendation
        st.markdown("<h2 style='text-align: center;'>Our Recommendation</h2>", unsafe_allow_html=True)
        
        # Show price comparison summary
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 20px;'>
            <p><strong>Price Difference:</strong> ₹{price_diff:.2f} ({price_diff_percent:.1f}%)</p>
            <p><strong>Best Price on:</strong> {price_winner} (saves ₹{price_save:.2f}, {price_save_percent:.1f}%)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Combined verdict based on price and reviews
        if "Buy" in flipkart_decision and "Buy" in amazon_decision:
            # Both recommend buying
            if price_diff_percent > 10:
                final_verdict = f"Buy from {price_winner} ✅"
                verdict_reason = f"Both platforms have positive reviews, but {price_winner} offers significantly better pricing"
                verdict_class = "verdict verdict-buy"
            else:
                final_verdict = f"Buy from either platform ✅"
                verdict_reason = "Both platforms have positive reviews with similar pricing"
                verdict_class = "verdict verdict-buy"
        elif "Don't Buy" in flipkart_decision and "Don't Buy" in amazon_decision:
            # Both recommend not buying
            final_verdict = "Consider other products ❌"
            verdict_reason = "Reviews suggest quality issues across both platforms"
            verdict_class = "verdict verdict-dont-buy"
        elif "Buy" in amazon_decision and "Don't Buy" in flipkart_decision:
            # Amazon yes, Flipkart no
            if price_winner == "Amazon":
                final_verdict = "Buy from Amazon ✅"
                verdict_reason = "Better reviews and better price on Amazon"
                verdict_class = "verdict verdict-buy"
            else:
                # Flipkart cheaper but bad reviews
                if price_diff_percent > 20:
                    final_verdict = "Consider Flipkart, but be cautious ⚠️"
                    verdict_reason = "Flipkart has significantly better price but mixed reviews"
                    verdict_class = "verdict verdict-neutral"
                else:
                    final_verdict = "Buy from Amazon ✅"
                    verdict_reason = "Better reviews on Amazon with reasonable price"
                    verdict_class = "verdict verdict-buy"
        elif "Buy" in flipkart_decision and "Don't Buy" in amazon_decision:
            # Flipkart yes, Amazon no
            if price_winner == "Flipkart":
                final_verdict = "Buy from Flipkart ✅"
                verdict_reason = "Better reviews and better price on Flipkart"
                verdict_class = "verdict verdict-buy"
            else:
                # Amazon cheaper but bad reviews
                if price_diff_percent > 20:
                    final_verdict = "Consider Amazon, but be cautious ⚠️"
                    verdict_reason = "Amazon has significantly better price but mixed reviews"
                    verdict_class = "verdict verdict-neutral"
                else:
                    final_verdict = "Buy from Flipkart ✅"
                    verdict_reason = "Better reviews on Flipkart with reasonable price"
                    verdict_class = "verdict verdict-buy"
        else:
            # Neutral or mixed verdicts
            if price_diff_percent > 15:
                final_verdict = f"Consider {price_winner} for better price ⚠️"
                verdict_reason = f"Reviews are mixed but {price_winner} offers better value"
                verdict_class = "verdict verdict-neutral"
            else:
                final_verdict = "Research more before buying ⚠️"
                verdict_reason = "Mixed reviews with similar pricing across platforms"
                verdict_class = "verdict verdict-neutral"
        
        st.markdown(f"<div class='{verdict_class}'>{final_verdict}</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center;'><em>{verdict_reason}</em></p>", unsafe_allow_html=True)
        
        # Add direct links
        st.markdown("""
        <div style='display: flex; justify-content: space-around; margin-top: 20px;'>
        """, unsafe_allow_html=True)
        
        if "Buy from Flipkart" in final_verdict or "Consider Flipkart" in final_verdict:
            st.markdown(f"""
            <a href="{st.session_state.flipkart_selected_product['link']}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #2874F0; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    Buy on Flipkart
                </button>
            </a>
            """, unsafe_allow_html=True)
        
        if "Buy from Amazon" in final_verdict or "Consider Amazon" in final_verdict:
            st.markdown(f"""
            <a href="{st.session_state.amazon_selected_product[2]}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #FF9900; color: black; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    Buy on Amazon
                </button>
            </a>
            """, unsafe_allow_html=True)
        
        if "Buy from either" in final_verdict:
            st.markdown(f"""
            <a href="{st.session_state.flipkart_selected_product['link']}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #2874F0; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    Buy on Flipkart
                </button>
            </a>
            <a href="{st.session_state.amazon_selected_product[2]}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #FF9900; color: black; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                    Buy on Amazon
                </button>
            </a>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Add this code to your pricefull.py file after the price prediction button click

# PRICE PREDICTIONS DISPLAY SECTION - Add this after the predict prices button
    if st.session_state.price_predictions_flipkart is not None or st.session_state.price_predictions_amazon is not None:
        st.markdown("<div class='comparison-header'>📊 Price Predictions - Next 30 Days</div>", unsafe_allow_html=True)
        
        # Create columns for side-by-side predictions
        pred_col1, pred_col2 = st.columns(2)
        
        # FLIPKART PREDICTIONS
        with pred_col1:
            if st.session_state.price_predictions_flipkart is not None:
                st.markdown("<div class='platform-container flipkart-container'>", unsafe_allow_html=True)
                st.markdown("<h3 class='platform-header flipkart-header'>Flipkart Price Forecast</h3>", unsafe_allow_html=True)
                
                predictions = st.session_state.price_predictions_flipkart
                if predictions:
                    # Get current price
                    flipkart_product = st.session_state.flipkart_selected_product
                    flipkart_price_text = flipkart_product['price_text']
                    current_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
                    
                    # Get insights
                    insights = st.session_state.predictor.get_price_insights(predictions, current_price)
                    
                    # Display current vs predicted price
                    future_price = predictions[-1]['predicted_price']
                    price_change = future_price - current_price
                    price_change_percent = (price_change / current_price) * 100
                    
                    # Price trend card
                    st.markdown(f"""
                    <div class='prediction-card'>
                        <h4>📈 Price Trend Analysis</h4>
                        <p><strong>Current Price:</strong> ₹{current_price:,.2f}</p>
                        <p><strong>Predicted Price (30 days):</strong> ₹{future_price:,.2f}</p>
                        <p><strong>Expected Change:</strong> 
                            <span class='{"trend-up" if price_change > 0 else "trend-down"}'>
                                ₹{abs(price_change):,.2f} ({abs(price_change_percent):.1f}% {"↗️" if price_change > 0 else "↘️"})
                            </span>
                        </p>
                        <p><strong>Confidence:</strong> {insights['confidence']*100:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Best buy recommendation
                    if insights['potential_savings'] > 0:
                        st.markdown(f"""
                        <div class='prediction-insight'>
                            <h4>💡 Best Time to Buy</h4>
                            <p><strong>Recommended Date:</strong> {insights['best_buy_date']}</p>
                            <p><strong>Expected Price:</strong> ₹{insights['best_buy_price']:,.2f}</p>
                            <p><strong>Potential Savings:</strong> ₹{insights['potential_savings']:,.2f} ({insights['potential_savings_percent']:.1f}%)</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Create price chart
                    dates = [pred['date'].strftime('%m/%d') for pred in predictions[:15]]  # Show first 15 days
                    prices = [pred['predicted_price'] for pred in predictions[:15]]
                    
                    chart_data = pd.DataFrame({
                        'Date': dates,
                        'Predicted Price': prices
                    })
                    
                    fig = px.line(chart_data, x='Date', y='Predicted Price', 
                                title='Flipkart Price Forecast (15 days)',
                                color_discrete_sequence=['#2874F0'])
                    fig.add_hline(y=current_price, line_dash="dash", 
                                annotation_text="Current Price", annotation_position="bottom right")
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Recommendation based on trend
                    if price_change_percent < -5:
                        st.success("🎯 Recommendation: Wait to buy! Price is expected to drop significantly.")
                    elif price_change_percent > 5:
                        st.error("⏰ Recommendation: Buy now! Price is expected to increase.")
                    else:
                        st.info("💭 Recommendation: Price is expected to remain stable. Buy when convenient.")
                else:
                    st.warning("No predictions available for Flipkart product.")
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        # AMAZON PREDICTIONS
        with pred_col2:
            if st.session_state.price_predictions_amazon is not None:
                st.markdown("<div class='platform-container amazon-container'>", unsafe_allow_html=True)
                st.markdown("<h3 class='platform-header amazon-header'>Amazon Price Forecast</h3>", unsafe_allow_html=True)
                
                predictions = st.session_state.price_predictions_amazon
                if predictions:
                    # Get current price
                    amazon_product = st.session_state.amazon_selected_product
                    current_price = amazon_product[1]
                    
                    # Get insights
                    insights = st.session_state.predictor.get_price_insights(predictions, current_price)
                    
                    # Display current vs predicted price
                    future_price = predictions[-1]['predicted_price']
                    price_change = future_price - current_price
                    price_change_percent = (price_change / current_price) * 100
                    
                    # Price trend card
                    st.markdown(f"""
                    <div class='prediction-card'>
                        <h4>📈 Price Trend Analysis</h4>
                        <p><strong>Current Price:</strong> ₹{current_price:,.2f}</p>
                        <p><strong>Predicted Price (30 days):</strong> ₹{future_price:,.2f}</p>
                        <p><strong>Expected Change:</strong> 
                            <span class='{"trend-up" if price_change > 0 else "trend-down"}'>
                                ₹{abs(price_change):,.2f} ({abs(price_change_percent):.1f}% {"↗️" if price_change > 0 else "↘️"})
                            </span>
                        </p>
                        <p><strong>Confidence:</strong> {insights['confidence']*100:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Best buy recommendation
                    if insights['potential_savings'] > 0:
                        st.markdown(f"""
                        <div class='prediction-insight'>
                            <h4>💡 Best Time to Buy</h4>
                            <p><strong>Recommended Date:</strong> {insights['best_buy_date']}</p>
                            <p><strong>Expected Price:</strong> ₹{insights['best_buy_price']:,.2f}</p>
                            <p><strong>Potential Savings:</strong> ₹{insights['potential_savings']:,.2f} ({insights['potential_savings_percent']:.1f}%)</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Create price chart
                    dates = [pred['date'].strftime('%m/%d') for pred in predictions[:15]]  # Show first 15 days
                    prices = [pred['predicted_price'] for pred in predictions[:15]]
                    
                    chart_data = pd.DataFrame({
                        'Date': dates,
                        'Predicted Price': prices
                    })
                    
                    fig = px.line(chart_data, x='Date', y='Predicted Price', 
                                title='Amazon Price Forecast (15 days)',
                                color_discrete_sequence=['#FF9900'])
                    fig.add_hline(y=current_price, line_dash="dash", 
                                annotation_text="Current Price", annotation_position="bottom right")
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Recommendation based on trend
                    if price_change_percent < -5:
                        st.success("🎯 Recommendation: Wait to buy! Price is expected to drop significantly.")
                    elif price_change_percent > 5:
                        st.error("⏰ Recommendation: Buy now! Price is expected to increase.")
                    else:
                        st.info("💭 Recommendation: Price is expected to remain stable. Buy when convenient.")
                else:
                    st.warning("No predictions available for Amazon product.")
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        # COMBINED PREDICTION SUMMARY
        if (st.session_state.price_predictions_flipkart is not None and 
            st.session_state.price_predictions_amazon is not None):
            
            st.markdown("<div class='comparison-header'>🔮 Platform Comparison Forecast</div>", unsafe_allow_html=True)
            
            # Get both insights
            flipkart_product = st.session_state.flipkart_selected_product
            amazon_product = st.session_state.amazon_selected_product
            
            flipkart_current = float(flipkart_product['price_text'].replace('₹', '').replace(',', '').strip().split('.')[0])
            amazon_current = amazon_product[1]
            
            flipkart_insights = st.session_state.predictor.get_price_insights(
                st.session_state.price_predictions_flipkart, flipkart_current)
            amazon_insights = st.session_state.predictor.get_price_insights(
                st.session_state.price_predictions_amazon, amazon_current)
            
            # Create comparison
            comparison_col1, comparison_col2 = st.columns(2)
            
            with comparison_col1:
                st.metric(
                    "Flipkart - Best Future Price",
                    f"₹{flipkart_insights['best_buy_price']:,.2f}",
                    f"{flipkart_insights['price_change_percent']:+.1f}%"
                )
            
            with comparison_col2:
                st.metric(
                    "Amazon - Best Future Price", 
                    f"₹{amazon_insights['best_buy_price']:,.2f}",
                    f"{amazon_insights['price_change_percent']:+.1f}%"
                )
            
            # Overall recommendation
            flipkart_best = flipkart_insights['best_buy_price']
            amazon_best = amazon_insights['best_buy_price']
            
            if flipkart_best < amazon_best:
                st.success(f"🏆 Best Overall Forecast: Flipkart will likely have the lowest price (₹{flipkart_best:,.2f}) on {flipkart_insights['best_buy_date']}")
            elif amazon_best < flipkart_best:
                st.success(f"🏆 Best Overall Forecast: Amazon will likely have the lowest price (₹{amazon_best:,.2f}) on {amazon_insights['best_buy_date']}")
            else:
                st.info("📊 Both platforms are expected to have similar pricing in the future.")

    # Also add this improved error handling for the predict prices button
    if st.button("🔮 Predict Future Prices", key="predict_prices", use_container_width=True,
                help="Predict price trends for the next 30 days"):
        try:
            with st.spinner("Generating price predictions..."):
                # Get Flipkart predictions
                if st.session_state.flipkart_selected_product:
                    flipkart_product = st.session_state.flipkart_selected_product
                    flipkart_price_text = flipkart_product['price_text']
                    flipkart_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
                    
                    try:
                        st.session_state.price_predictions_flipkart = st.session_state.predictor.predict_future_price(
                            product_name=flipkart_product['title'][:50],
                            platform="Flipkart",
                            current_price=flipkart_price,
                            days_ahead=30
                        )
                    except Exception as e:
                        st.error(f"Error predicting Flipkart prices: {str(e)}")
                        st.session_state.price_predictions_flipkart = None
                
                # Get Amazon predictions  
                if st.session_state.amazon_selected_product:
                    amazon_product = st.session_state.amazon_selected_product
                    amazon_price = amazon_product[1]
                    
                    try:
                        st.session_state.price_predictions_amazon = st.session_state.predictor.predict_future_price(
                            product_name=amazon_product[0][:50],
                            platform="Amazon", 
                            current_price=amazon_price,
                            days_ahead=30
                        )
                    except Exception as e:
                        st.error(f"Error predicting Amazon prices: {str(e)}")
                        st.session_state.price_predictions_amazon = None
                
                # Check if any predictions were successful
                if (st.session_state.price_predictions_flipkart is None and 
                    st.session_state.price_predictions_amazon is None):
                    st.error("Failed to generate price predictions for both platforms.")
                else:
                    st.success("Price predictions generated successfully! Scroll down to view the forecasts.")
                    
        except Exception as e:
            st.error(f"An error occurred while generating predictions: {str(e)}")
            st.session_state.price_predictions_flipkart = None
            st.session_state.price_predictions_amazon = None


    # Price history simulation (only shown when products are selected)
    if st.session_state.flipkart_selected_product and st.session_state.amazon_selected_product:
        with st.expander("📈 View Price History Trends"):
            st.write("Simulated price history for the past 30 days")
            
            # Generate simulated price history data
            dates = pd.date_range(end=pd.Timestamp.now(), periods=30)
            
            # Extract base prices
            flipkart_price_text = st.session_state.flipkart_selected_product['price_text']
            flipkart_current_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
            amazon_current_price = st.session_state.amazon_selected_product[1]
            
            # Create price fluctuations (add some randomness)
            flipkart_prices = [flipkart_current_price * (1 + 0.05 * (random.random() - 0.5)) for _ in range(30)]
            amazon_prices = [amazon_current_price * (1 + 0.05 * (random.random() - 0.5)) for _ in range(30)]
            
            # Set current prices at the end
            flipkart_prices[-1] = flipkart_current_price
            amazon_prices[-1] = amazon_current_price
            
            # Create DataFrame
            price_history = pd.DataFrame({
                'Date': dates,
                'Flipkart': flipkart_prices,
                'Amazon': amazon_prices
            })
            
            # Create and display line chart
            fig = px.line(
                price_history, 
                x='Date', 
                y=['Flipkart', 'Amazon'],
                title='Price Trends (30 Days)',
                labels={'value': 'Price (₹)', 'variable': 'Platform'},
                color_discrete_map={'Flipkart': '#2874F0', 'Amazon': '#FF9900'}
            )
            
            fig.update_layout(
                legend_title='Platform',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show simple price statistics
            price_stats = pd.DataFrame({
                'Metric': ['Current Price', 'Lowest Price', 'Highest Price', 'Average Price'],
                'Flipkart': [
                    f"₹{flipkart_current_price:,.2f}",
                    f"₹{min(flipkart_prices):,.2f}",
                    f"₹{max(flipkart_prices):,.2f}",
                    f"₹{sum(flipkart_prices)/len(flipkart_prices):,.2f}"
                ],
                'Amazon': [
                    f"₹{amazon_current_price:,.2f}",
                    f"₹{min(amazon_prices):,.2f}",
                    f"₹{max(amazon_prices):,.2f}",
                    f"₹{sum(amazon_prices)/len(amazon_prices):,.2f}"
                ]
            })
            
            st.table(price_stats)
            
            

    # Add footer
    st.markdown("<div class='footer'>", unsafe_allow_html=True)
    st.markdown("Price Comparison Tool | © 2025 | Developed with Streamlit", unsafe_allow_html=True)
    st.markdown("Disclaimer: This tool is for educational purposes only. Prices and reviews are scraped from platforms and analyzed in real-time.", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Add about section in the sidebar
    with st.sidebar:
        with st.expander("About this App"):
            st.markdown("""
            This application helps you compare prices and reviews across two major e-commerce platforms in India - Amazon and Flipkart.
            
            **Features:**
            - Real-time price comparison
            - Product reviews sentiment analysis
            - Price history trends
            - Buy/Don't Buy recommendations
            
            **Technologies Used:**
            - Streamlit
            - Selenium for web scraping
            - TextBlob for sentiment analysis
            - Plotly for interactive visualizations
            
            For issues or feedback, please contact the developer.
            """)
if __name__ == "__main__":
    if st.session_state.logged_in:
        show_main_app()
    else:
        show_login_page()
