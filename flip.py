import streamlit as st
import sqlite3
from hashlib import sha256
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import random
import logging
from amaz import find_lowest_price_product, AmazonReviewScraper
from flipAPI import FlipkartProductSearch, FlipkartReviewScraper
from textblob import TextBlob  # Sentiment analysis library

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Functions
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
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      (username, hashed_password))
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

# Sentiment Analysis Function
def analyze_sentiment(reviews):
    if not reviews:
        return "No reviews available"
    
    total_polarity = sum(TextBlob(review).sentiment.polarity for review in reviews)
    avg_polarity = total_polarity / len(reviews)
    
    if avg_polarity > 0.1:
        return "Mostly Positive 😊"
    elif avg_polarity < -0.1:
        return "Mostly Negative 😞"
    else:
        return "Neutral 😐"

# Streamlit UI
st.set_page_config(page_title="PriceIT - Compare Prices & Reviews", layout="wide")
st.title("🛒 PriceIT: Online Shopping Assistant")

# Authentication System
create_userdb()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if st.session_state.logged_in:
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
else:
    tab1, tab2 = st.tabs(["Login", "Signup"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            if submit and authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
    with tab2:
        with st.form("signup_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up")
            if submit and new_password == confirm_password and len(new_password) >= 6:
                if add_user(new_username, new_password):
                    st.success("Account created successfully! Please login.")
                else:
                    st.error("Username already exists.")

# If logged in, proceed to price comparison
if st.session_state.logged_in:
    search_term = st.text_input("🔎 Enter the product name:", "")
    if st.button("Search 🔍") and search_term:
        DRIVER_PATH = str(Path('chromedriver.exe').resolve())
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🟠 Amazon Results")
            try:
                amazon_result = find_lowest_price_product(search_term, DRIVER_PATH)
                if amazon_result:
                    st.write(f"Product: {amazon_result[0]}")
                    st.write(f"Price: ₹{amazon_result[1]}")
                    st.markdown(f"[🔗 View on Amazon]({amazon_result[2]})", unsafe_allow_html=True)
                    with st.spinner("Analyzing Amazon reviews..."):
                        amazon_scraper = AmazonReviewScraper(DRIVER_PATH)
                        reviews, amazon_decision = amazon_scraper.scrape_review_titles(amazon_result[2], max_pages=2)
                    st.write("Final Verdict:", amazon_decision)
                    st.write("Sentiment Analysis:", analyze_sentiment(reviews))
                else:
                    st.error("No products found on Amazon.")
            except Exception as e:
                st.error(f"Error with Amazon scraping: {e}")
        
        with col2:
            st.subheader("🔵 Flipkart Results")
            try:
                flipkart_searcher = FlipkartProductSearch(DRIVER_PATH)
                products = flipkart_searcher.search_products(search_term)
                if products:
                    lowest_product = flipkart_searcher.get_lowest_price_product()
                    st.write(f"Product: {lowest_product['title']}")
                    st.write(f"Price: {lowest_product['price_text']}")
                    st.markdown(f"[🔗 View on Flipkart]({lowest_product['link']})", unsafe_allow_html=True)
                    with st.spinner("Analyzing Flipkart reviews..."):
                        flipkart_scraper = FlipkartReviewScraper(DRIVER_PATH)
                        reviews, _, flipkart_decision, _ = flipkart_scraper.scrape_reviews(lowest_product['link'], pages_to_scrape=2)
                    st.write("Final Verdict:", flipkart_decision)
                    st.write("Sentiment Analysis:", analyze_sentiment(reviews))
                else:
                    st.error("No products found on Flipkart.")
            except Exception as e:
                st.error(f"Error with Flipkart scraping: {e}")
        
        st.success("✅ Search completed! Compare and choose the best deal.")