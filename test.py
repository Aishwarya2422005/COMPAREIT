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

# Import functions from your existing scripts 
from amaz import setup_chrome_driver, find_lowest_price_product, find_multiple_products, AmazonReviewScraper
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

# User Authentication Database Setup
def create_userdb():
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_user(username, password):
    conn = sqlite3.connect("userdb.db")
    cursor = conn.cursor()
    try:
        hashed_password = sha256(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
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
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    result = cursor.fetchone()
    conn.close()
    return result

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
        new_password = st.text_input("New Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        
        if st.button("Sign Up", key="signup_button"):
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            elif add_user(new_username, new_password):
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
                    amazon_products = find_multiple_products(search_term, driver_path, max_products=5)
                    
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

    # Overall Recommendation Section
    st.markdown("<div class='comparison-header'>🤔 Final Recommendation</div>", unsafe_allow_html=True)

    # Initialize variables to store analysis results
    flipkart_sentiment_score = 0
    amazon_sentiment_score = 0
    flipkart_positive_percent = 0
    amazon_positive_percent = 0
    flipkart_total_reviews = 0
    amazon_total_reviews = 0

    # Get Flipkart sentiment analysis
    if 'all_reviews' in locals() and 'all_titles' in locals():
        flipkart_content = all_reviews + all_titles
        flipkart_total_reviews = len(flipkart_content)
        
        if flipkart_total_reviews > 0:
            flipkart_positive = 0
            flipkart_negative = 0
            
            for review in flipkart_content:
                sentiment = TextBlob(review).sentiment.polarity
                if sentiment > 0.1:
                    flipkart_positive += 1
                elif sentiment < -0.1:
                    flipkart_negative += 1
            
            flipkart_positive_percent = (flipkart_positive / flipkart_total_reviews) * 100
            flipkart_sentiment_score = (flipkart_positive - flipkart_negative) / flipkart_total_reviews

    # Get Amazon sentiment analysis  
    if 'review_titles' in locals():
        amazon_total_reviews = len(review_titles)
        
        if amazon_total_reviews > 0:
            amazon_positive = 0
            amazon_negative = 0
            
            for review in review_titles:
                sentiment = TextBlob(review).sentiment.polarity
                if sentiment > 0.1:
                    amazon_positive += 1
                elif sentiment < -0.1:
                    amazon_negative += 1
            
            amazon_positive_percent = (amazon_positive / amazon_total_reviews) * 100
            amazon_sentiment_score = (amazon_positive - amazon_negative) / amazon_total_reviews

    # Extract and compare prices
    flipkart_price_text = st.session_state.flipkart_selected_product['price_text']
    flipkart_price = float(flipkart_price_text.replace('₹', '').replace(',', '').strip().split('.')[0])
    amazon_price = st.session_state.amazon_selected_product[1]

    price_difference = abs(flipkart_price - amazon_price)
    price_difference_percent = (price_difference / max(flipkart_price, amazon_price)) * 100

    # Determine price winner
    if flipkart_price < amazon_price:
        price_winner = "Flipkart"
        price_savings = amazon_price - flipkart_price
        savings_percent = (price_savings / amazon_price) * 100
    else:
        price_winner = "Amazon" 
        price_savings = flipkart_price - amazon_price
        savings_percent = (price_savings / flipkart_price) * 100

    # Create recommendation analysis
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>📊 Analysis Summary</h3>", unsafe_allow_html=True)
        
        # Price Analysis
        st.markdown("<h4>💰 Price Comparison</h4>", unsafe_allow_html=True)
        st.markdown(f"- **Flipkart:** ₹{flipkart_price:,.2f}")
        st.markdown(f"- **Amazon:** ₹{amazon_price:,.2f}")
        st.markdown(f"- **Price Difference:** ₹{price_difference:,.2f} ({price_difference_percent:.1f}%)")
        st.markdown(f"- **Cheaper on:** {price_winner} (saves ₹{price_savings:,.2f}, {savings_percent:.1f}%)")
        
        # Review Analysis
        st.markdown("<h4>📝 Review Analysis</h4>", unsafe_allow_html=True)
        st.markdown(f"- **Flipkart Reviews:** {flipkart_total_reviews} analyzed")
        st.markdown(f"  - Positive: {flipkart_positive_percent:.1f}%")
        st.markdown(f"  - Sentiment Score: {flipkart_sentiment_score:.2f}")
        
        st.markdown(f"- **Amazon Reviews:** {amazon_total_reviews} analyzed")  
        st.markdown(f"  - Positive: {amazon_positive_percent:.1f}%")
        st.markdown(f"  - Sentiment Score: {amazon_sentiment_score:.2f}")
        
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>🎯 Smart Recommendation</h3>", unsafe_allow_html=True)
        
        # Advanced recommendation logic
        def get_smart_recommendation():
            # Weight factors
            PRICE_WEIGHT = 0.4
            REVIEW_WEIGHT = 0.6
            
            # Normalize scores (0-1 scale)
            # Price score: lower price gets higher score
            if flipkart_price <= amazon_price:
                flipkart_price_score = 1.0
                amazon_price_score = amazon_price / flipkart_price - 1 if flipkart_price > 0 else 0
                amazon_price_score = max(0, 1 - amazon_price_score)
            else:
                amazon_price_score = 1.0
                flipkart_price_score = flipkart_price / amazon_price - 1 if amazon_price > 0 else 0
                flipkart_price_score = max(0, 1 - flipkart_price_score)
            
            # Review score: sentiment score normalized to 0-1
            flipkart_review_score = max(0, min(1, (flipkart_sentiment_score + 1) / 2))
            amazon_review_score = max(0, min(1, (amazon_sentiment_score + 1) / 2))
            
            # Calculate overall scores
            flipkart_overall = (PRICE_WEIGHT * flipkart_price_score) + (REVIEW_WEIGHT * flipkart_review_score)
            amazon_overall = (PRICE_WEIGHT * amazon_price_score) + (REVIEW_WEIGHT * amazon_review_score)
            
            # Determine confidence level based on data quality
            confidence = "High"
            if flipkart_total_reviews < 5 or amazon_total_reviews < 5:
                confidence = "Medium"
            if flipkart_total_reviews < 3 or amazon_total_reviews < 3:
                confidence = "Low"
            
            return flipkart_overall, amazon_overall, flipkart_price_score, amazon_price_score, flipkart_review_score, amazon_review_score, confidence
        
        f_overall, a_overall, f_price, a_price, f_review, a_review, confidence = get_smart_recommendation()
        
        # Display scores
        st.markdown("<h4>📈 Platform Scores</h4>", unsafe_allow_html=True)
        st.markdown(f"**Flipkart Overall:** {f_overall:.2f}/1.0")
        st.markdown(f"- Price Score: {f_price:.2f}")
        st.markdown(f"- Review Score: {f_review:.2f}")
        
        st.markdown(f"**Amazon Overall:** {a_overall:.2f}/1.0")
        st.markdown(f"- Price Score: {a_price:.2f}")
        st.markdown(f"- Review Score: {a_review:.2f}")
        
        st.markdown(f"**Confidence Level:** {confidence}")
        
        # Final verdict
        score_difference = abs(f_overall - a_overall)
        
        if score_difference < 0.1:
            recommendation = "Either Platform ⚖️"
            reason = "Both platforms offer similar value proposition"
            verdict_class = "verdict-neutral"
        elif f_overall > a_overall:
            recommendation = "Buy from Flipkart ✅"
            reason = f"Better overall value (Score: {f_overall:.2f} vs {a_overall:.2f})"
            verdict_class = "verdict-buy"
        else:
            recommendation = "Buy from Amazon ✅"
            reason = f"Better overall value (Score: {a_overall:.2f} vs {f_overall:.2f})"
            verdict_class = "verdict-buy"
        
        # Add specific reasoning
        detailed_reason = []
        
        if abs(f_price - a_price) > 0.2:
            if f_price > a_price:
                detailed_reason.append("Flipkart offers significantly better pricing")
            else:
                detailed_reason.append("Amazon offers significantly better pricing")
        
        if abs(f_review - a_review) > 0.2:
            if f_review > a_review:
                detailed_reason.append("Flipkart has much better reviews")
            else:
                detailed_reason.append("Amazon has much better reviews")
        
        if flipkart_positive_percent > 70 and amazon_positive_percent > 70:
            detailed_reason.append("Both platforms show high customer satisfaction")
        elif flipkart_positive_percent < 50 and amazon_positive_percent < 50:
            detailed_reason.append("⚠️ Both platforms have concerning review patterns")
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Final recommendation display
    st.markdown("<div class='card' style='text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)
    st.markdown(f"<div class='verdict {verdict_class}'>{recommendation}</div>", unsafe_allow_html=True)
    st.markdown(f"<p><strong>Primary Reason:</strong> {reason}</p>", unsafe_allow_html=True)

    if detailed_reason:
        st.markdown("<p><strong>Key Factors:</strong></p>", unsafe_allow_html=True)
        for reason_item in detailed_reason:
            st.markdown(f"• {reason_item}")

    # Risk assessment
    risk_factors = []
    if flipkart_positive_percent < 60:
        risk_factors.append("Flipkart reviews show mixed satisfaction")
    if amazon_positive_percent < 60:
        risk_factors.append("Amazon reviews show mixed satisfaction")
    if price_difference_percent > 25:
        risk_factors.append(f"Large price difference ({price_difference_percent:.1f}%) - verify product specifications")

    if risk_factors:
        st.markdown("<p><strong>⚠️ Consider These Factors:</strong></p>", unsafe_allow_html=True)
        for risk in risk_factors:
            st.markdown(f"• {risk}")

    # Action buttons
    st.markdown("<div style='margin-top: 20px;'>", unsafe_allow_html=True)
    if "Flipkart" in recommendation or "Either" in recommendation:
        st.markdown(f"""
        <a href="{st.session_state.flipkart_selected_product['link']}" target="_blank" style="text-decoration: none; margin-right: 10px;">
            <button style="background-color: #2874F0; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                🛒 Buy on Flipkart
            </button>
        </a>
        """, unsafe_allow_html=True)

    if "Amazon" in recommendation or "Either" in recommendation:
        st.markdown(f"""
        <a href="{st.session_state.amazon_selected_product[2]}" target="_blank" style="text-decoration: none;">
            <button style="background-color: #FF9900; color: black; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                🛒 Buy on Amazon
            </button>
        </a>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

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