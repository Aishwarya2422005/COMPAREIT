import streamlit as st
import pandas as pd
import concurrent.futures
import time
from pathlib import Path
# Import the functions directly from the second file instead of using 'amaz'
# Assuming you've renamed the second file to 'amaz.py'
from flipAPI import FlipkartProductSearch, FlipkartReviewScraper

# Set ChromeDriver path
DRIVER_PATH = str(Path('chromedriver.exe').resolve())

# Streamlit UI Setup
st.set_page_config(page_title="PriceIT - Compare Prices & Reviews", layout="wide")
st.title("🛒 PriceIT: Online Shopping Assistant")
st.write("Compare product prices and analyze reviews from Amazon and Flipkart.")

# User Input
search_term = st.text_input("🔎 Enter the product name:", "")

# Cache the search results to avoid redundant scraping
@st.cache_data(ttl=3600)  # Cache results for 1 hour
def get_amazon_products(search_term):
    """Fetches the top 5 products from Amazon using a single search"""
    try:
        # Updated to match the function signature in the second file
        # The original function returns a single product, not a list of products
        product = find_lowest_price_product(search_term, DRIVER_PATH)
        
        # Create a list of 5 products by calling the function multiple times
        # or modify the find_lowest_price_product function to return multiple products
        # For now, we'll return a list containing just the lowest price product
        return [product] if product else []
    except Exception as e:
        st.error(f"Error fetching Amazon products: {str(e)}")
        return []

@st.cache_data(ttl=3600)  # Cache results for 1 hour
def get_flipkart_products(search_term):
    """Fetches the top 5 products from Flipkart"""
    try:
        flipkart_searcher = FlipkartProductSearch(DRIVER_PATH)
        all_products = flipkart_searcher.search_products(search_term)
        return all_products[:5] if all_products else []
    except Exception as e:
        st.error(f"Error fetching Flipkart products: {str(e)}")
        return []

# Add a spinner to show progress
if st.button("Search 🔍"):
    if not search_term:
        st.warning("Please enter a product name to search.")
    else:
        with st.spinner("Searching for products..."):
            start_time = time.time()
            
            # Run Amazon & Flipkart scraping simultaneously
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_amazon = executor.submit(get_amazon_products, search_term)
                future_flipkart = executor.submit(get_flipkart_products, search_term)
                
                # Wait for both futures to complete
                amazon_products = future_amazon.result()
                flipkart_products = future_flipkart.result()
            
            end_time = time.time()
            st.info(f"Search completed in {end_time - start_time:.2f} seconds")

        # Create tabs for better organization
        tab1, tab2 = st.tabs(["Product Comparison", "Review Analysis"])
        
        with tab1:
            col1, col2 = st.columns(2)  # Two-column layout for Amazon & Flipkart

            # **Amazon Scraping Results**
            with col1:
                st.subheader("🟠 Amazon Top Products")
                if amazon_products:
                    # Create a DataFrame for Amazon products
                    # The structure is different from the original code because find_lowest_price_product
                    # returns a single product as [title, price, link]
                    amazon_df = pd.DataFrame(amazon_products, columns=["Title", "Price", "Link"])
                    st.dataframe(amazon_df)  # Use dataframe instead of table for better performance
                else:
                    st.error("No products found on Amazon.")

            # **Flipkart Scraping Results**
            with col2:
                st.subheader("🔵 Flipkart Top Products")
                if flipkart_products:
                    flipkart_df = pd.DataFrame(flipkart_products)
                    st.dataframe(flipkart_df[["title", "price_text", "link"]])  # Use dataframe for better performance
                else:
                    st.error("No products found on Flipkart.")

            # **Finding the Lowest Price Product from Each Platform**
            # For Amazon, we're already getting the lowest price product
            lowest_amazon = amazon_products[0] if amazon_products else None
                
            if flipkart_products:
                try:
                    lowest_flipkart = min(flipkart_products, key=lambda x: float(str(x["price_text"]).replace('₹', '').replace(',', '').strip()))
                except (ValueError, TypeError):
                    lowest_flipkart = flipkart_products[0]  # Fallback if price parsing fails
            else:
                lowest_flipkart = None

            # Display the best deals
            st.subheader("💰 Best Deals")
            col3, col4 = st.columns(2)  # Two-column layout for lowest price products

            with col3:
                if lowest_amazon:
                    st.subheader("🟠 Amazon Best Deal")
                    st.write(f"**{lowest_amazon[0]}** - ₹{lowest_amazon[1]}")
                    st.markdown(f"[🔗 View on Amazon]({lowest_amazon[2]})", unsafe_allow_html=True)

            with col4:
                if lowest_flipkart:
                    st.subheader("🔵 Flipkart Best Deal")
                    st.write(f"**{lowest_flipkart['title']}** - ₹{lowest_flipkart['price_text']}")
                    st.markdown(f"[🔗 View on Flipkart]({lowest_flipkart['link']})", unsafe_allow_html=True)
        
        # Review analysis in a separate tab
        with tab2:
            if lowest_amazon or lowest_flipkart:
                st.subheader("📝 Review Sentiment Analysis")
                
                # Cache the review analysis to avoid redundant scraping
                @st.cache_data(ttl=3600)  # Cache results for 1 hour
                def analyze_amazon_reviews(url):
                    """Scrape and analyze Amazon reviews"""
                    try:
                        amazon_scraper = AmazonReviewScraper(DRIVER_PATH)
                        # The scrape_review_titles function returns two values
                        _, verdict = amazon_scraper.scrape_review_titles(url, max_pages=1)  # Reduced to 1 page for faster results
                        return verdict
                    except Exception as e:
                        return f"Error analyzing Amazon reviews: {e}"

                @st.cache_data(ttl=3600)  # Cache results for 1 hour
                def analyze_flipkart_reviews(url):
                    """Scrape and analyze Flipkart reviews"""
                    try:
                        flipkart_scraper = FlipkartReviewScraper(DRIVER_PATH)
                        _, _, verdict, _ = flipkart_scraper.scrape_reviews(url, pages_to_scrape=1)  # Reduced to 1 page for faster results
                        return verdict
                    except Exception as e:
                        return f"Error analyzing Flipkart reviews: {e}"
                
                with st.spinner("Analyzing reviews..."):
                    # Run review analysis in parallel
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future_amazon_review = executor.submit(analyze_amazon_reviews, lowest_amazon[2]) if lowest_amazon else None
                        future_flipkart_review = executor.submit(analyze_flipkart_reviews, lowest_flipkart["link"]) if lowest_flipkart else None

                        amazon_verdict = future_amazon_review.result() if future_amazon_review else "No Amazon product available for review."
                        flipkart_verdict = future_flipkart_review.result() if future_flipkart_review else "No Flipkart product available for review."

                col5, col6 = st.columns(2)  # Two-column layout for review analysis

                with col5:
                    st.subheader("🔸 Amazon Review Analysis")
                    st.write(f"**Verdict:** {amazon_verdict}")

                with col6:
                    st.subheader("🔹 Flipkart Review Analysis")
                    st.write(f"**Verdict:** {flipkart_verdict}")

                st.success("✅ Analysis completed! Compare reviews to make an informed decision.")
            else:
                st.warning("No products found for review analysis.")

# Need to define these functions to match what's expected in the app
# If the amaz.py file exists and contains these functions, you should import them instead
# Adding this separately for completeness
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import random
import time
from bs4 import BeautifulSoup
from textblob import TextBlob

def get_random_user_agent():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    return random.choice(user_agents)

def setup_chrome_driver(driver_path, headless=False):
    """Setup Chrome driver with anti-detection measures"""
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={get_random_user_agent()}')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    
    # Only add headless mode if specified - visible browser helps with manual login
    if headless:
        chrome_options.add_argument('--headless')
    
    try:
        service = Service(driver_path)
        browser = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        if "This version of ChromeDriver only supports Chrome version" in str(e):
            print("ChromeDriver version mismatch. Please update ChromeDriver.")
            raise
        else:
            raise e
    
    browser.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": get_random_user_agent()
    })
    browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    browser.set_window_size(1920, 1080)
    return browser

def find_lowest_price_product(search_term, driver_path, num_products=1):
    """
    Modified version of find_lowest_price_product that can return multiple products
    """
    search_term = search_term.replace(' ', '+')
    amazon_link = f"https://www.amazon.in/s?k={search_term}"
    
    try:
        # Set up headless browser
        driver = setup_chrome_driver(driver_path, headless=True)
        driver.get(amazon_link)
        time.sleep(5)  # Wait for page to load
        
        # Get page source and parse with BeautifulSoup
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find product cards
        product_cards = soup.select('div[data-component-type="s-search-result"]')
        
        products = []
        for card in product_cards[:10]:  # Process first 10 results
            try:
                # Extract title
                title_elem = card.select_one('h2 a span') or card.select_one('h2 span.a-text-normal')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                # Extract price
                price_elem = card.select_one('span.a-price span.a-offscreen')
                if not price_elem:
                    continue
                price_text = price_elem.text.strip()
                # Convert price text to a number
                price = float(price_text.replace('₹', '').replace(',', '').strip())
                
                # Extract link
                link_elem = card.select_one('h2 a')
                if not link_elem:
                    continue
                link = "https://www.amazon.in" + link_elem.get('href', '')
                
                products.append([title, price, link])
                
                if len(products) >= num_products:
                    break
            except Exception as e:
                continue
        
        driver.quit()
        
        if not products:
            return None
        
        # Sort by price and return
        products.sort(key=lambda x: x[1])
        
        if num_products == 1:
            return products[0]
        return products
        
    except Exception as e:
        print(f"Error in Amazon search: {e}")
        return None

class AmazonReviewScraper:
    def __init__(self, driver_path):
        self.driver_path = driver_path
    
    def scrape_review_titles(self, product_url, max_pages=2):
        """Simple stub for AmazonReviewScraper"""
        driver = setup_chrome_driver(self.driver_path, headless=True)
        try:
            driver.get(product_url)
            time.sleep(5)
            
            # Look for review section
            review_content = driver.page_source
            
            # Use TextBlob for simple sentiment analysis
            blob = TextBlob(review_content)
            sentiment = blob.sentiment.polarity
            
            if sentiment > 0.2:
                verdict = "Buy ✅ (Mostly positive reviews)"
            elif sentiment < -0.2:
                verdict = "Don't Buy ❌ (Mostly negative reviews)"
            else:
                verdict = "Neutral ⚖️ (Mixed reviews)"
                
            return [], verdict
        finally:
            driver.quit()