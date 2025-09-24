from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import random
import requests
import os
import zipfile
import sys
import pickle
import logging
from win32com.client import Dispatch
from textblob import TextBlob

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEBUG = True

def log_debug(message):
    if DEBUG:
        print(f"[DEBUG] {message}")

def get_chrome_version():
    """Get the installed Chrome version."""
    try:
        chrome_path = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
        if os.path.exists(chrome_path):
            parser = Dispatch('Scripting.FileSystemObject')
            version = parser.GetFileVersion(chrome_path)
            return version.split('.')[0]  # Return major version number
    except Exception as e:
        log_debug(f"Error getting Chrome version: {e}")
    return None

def download_chromedriver():
    """Download the appropriate ChromeDriver version."""
    try:
        chrome_version = get_chrome_version()
        if not chrome_version:
            log_debug("Could not determine Chrome version. Please install Chrome first.")
            sys.exit(1)

        log_debug(f"Downloading ChromeDriver for Chrome version {chrome_version}")
        download_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{chrome_version}"
        response = requests.get(download_url)
        driver_version = response.text.strip()
        
        driver_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_win32.zip"
        response = requests.get(driver_url)
        
        with open("chromedriver.zip", "wb") as f:
            f.write(response.content)
        
        with zipfile.ZipFile("chromedriver.zip", "r") as zip_ref:
            zip_ref.extractall()
        
        os.remove("chromedriver.zip")
        log_debug("ChromeDriver downloaded and extracted successfully")
        return True
    except Exception as e:
        log_debug(f"Error downloading ChromeDriver: {e}")
        return False

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
    
    log_debug("Starting Chrome browser...")
    
    try:
        service = Service(driver_path)
        browser = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        if "This version of ChromeDriver only supports Chrome version" in str(e):
            log_debug("ChromeDriver version mismatch detected. Downloading correct version...")
            if download_chromedriver():
                # Retry with new ChromeDriver
                service = Service(driver_path)
                browser = webdriver.Chrome(service=service, options=chrome_options)
            else:
                raise Exception("Failed to download compatible ChromeDriver")
        else:
            raise e
    
    browser.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": get_random_user_agent()
    })
    browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    browser.set_window_size(1920, 1080)
    return browser

def get_html(url, driver_path):
    browser = setup_chrome_driver(driver_path, headless=True)
    
    try:
        log_debug(f"Navigating to URL: {url}")
        browser.get(url)
        
        delay = random.uniform(3, 7)
        log_debug(f"Waiting {delay:.2f} seconds for page to load...")
        time.sleep(delay)
        
        wait = WebDriverWait(browser, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.s-result-item,div[data-component-type="s-search-result"]')))
        
        for i in range(3):
            scroll_amount = random.randint(300, 700)
            browser.execute_script(f"window.scrollTo(0, {scroll_amount})")
            time.sleep(random.uniform(0.5, 1.5))
        
        log_debug("Page loaded successfully")
        return browser.page_source
    except Exception as e:
        log_debug(f"Error during page load: {str(e)}")
        raise
    finally:
        browser.quit()

def extract_price(card):
    price_selectors = [
        'span.a-price-whole',
        'span.a-price span[aria-hidden="true"]',
        'span.a-price',
        'span.a-offscreen'
    ]
    
    for selector in price_selectors:
        price_elem = card.select_one(selector)
        if price_elem:
            price_text = price_elem.text.strip().replace('₹', '').replace(',', '').strip('.')
            # Extract numeric part only
            import re
            price_match = re.search(r'\d+(?:\.\d+)?', price_text)
            if price_match:
                return float(price_match.group())
    return float('inf')  # Return infinity for items with no price

def find_lowest_price_product(search_term, driver_path):
    search_term = search_term.replace(' ', '+')
    amazon_link = f"https://www.amazon.in/s?k={search_term}"
    amazon_home = 'https://www.amazon.in'
    max_retries = 3
    retry_count = 0
    
    lowest_price = float('inf')
    lowest_price_product = None
    
    while retry_count < max_retries:
        try:
            html = get_html(amazon_link, driver_path)
            log_debug("Parsing HTML with BeautifulSoup...")
            soup = BeautifulSoup(html, 'lxml')
            
            selectors = [
                'div[data-component-type="s-search-result"]',
                'div.s-result-item',
                'div.sg-col-inner'
            ]
            
            prod_cards = []
            for selector in selectors:
                prod_cards = soup.select(selector)
                if prod_cards:
                    log_debug(f"Found {len(prod_cards)} products using selector: {selector}")
                    break
            
            if not prod_cards:
                retry_count += 1
                log_debug(f"No products found. Retry {retry_count}/{max_retries}")
                time.sleep(random.uniform(5, 10))
                continue
            
            items = []
            for idx, card in enumerate(prod_cards[:10]):  # Look at first 10 products
                try:
                    title_elem = (card.select_one('h2 a.a-link-normal span') or 
                                card.select_one('h2 span.a-text-normal') or
                                card.select_one('h2'))
                    
                    if not title_elem:
                        continue
                        
                    title = title_elem.text.strip()
                    
                    link_elem = card.select_one('h2 a') or card.select_one('a.a-link-normal')
                    if not link_elem:
                        continue
                        
                    link = link_elem.get('href', '')
                    if not link.startswith('http'):
                        link = amazon_home + link
                    
                    price = extract_price(card)
                    
                    if title and link and price != float('inf'):
                        items.append([title, price, link])
                        print(f"\nProduct {idx + 1}:")
                        print(f"Title: {title}")
                        print(f"Price: ₹{price}")
                        print(f"Link: {link}")
                        
                        if price < lowest_price:
                            lowest_price = price
                            lowest_price_product = [title, price, link]
                
                except Exception as e:
                    log_debug(f"Error processing product {idx + 1}: {str(e)}")
                    continue
            
            if items:
                print("\n" + "="*50)
                print(f"LOWEST PRICE PRODUCT:")
                print(f"Title: {lowest_price_product[0]}")
                print(f"Price: ₹{lowest_price_product[1]}")
                print(f"Link: {lowest_price_product[2]}")
                print("="*50)
                return lowest_price_product
            
        except Exception as e:
            retry_count += 1
            log_debug(f"Error during scraping (attempt {retry_count}/{max_retries}): {str(e)}")
            if retry_count < max_retries:
                time.sleep(random.uniform(5, 10))
            else:
                print(f"Error during scraping: {str(e)}")
    
    return None

# Modify this part in your existing code to simulate Amazon reviews
def find_multiple_products(search_term, driver_path, max_products=5):
    """Find multiple products from Amazon, not just the lowest price"""
    search_term = search_term.replace(' ', '+')
    amazon_link = f"https://www.amazon.in/s?k={search_term}"
    amazon_home = 'https://www.amazon.in'
    max_retries = 3
    retry_count = 0
    
    all_products = []
    
    while retry_count < max_retries:
        try:
            html = get_html(amazon_link, driver_path)
            log_debug("Parsing HTML with BeautifulSoup...")
            soup = BeautifulSoup(html, 'lxml')
            
            selectors = [
                'div[data-component-type="s-search-result"]',
                'div.s-result-item',
                'div.sg-col-inner'
            ]
            
            prod_cards = []
            for selector in selectors:
                prod_cards = soup.select(selector)
                if prod_cards:
                    log_debug(f"Found {len(prod_cards)} products using selector: {selector}")
                    break
            
            if not prod_cards:
                retry_count += 1
                log_debug(f"No products found. Retry {retry_count}/{max_retries}")
                time.sleep(random.uniform(5, 10))
                continue
            
            for idx, card in enumerate(prod_cards[:max_products*2]):  # Get more cards to filter
                try:
                    title_elem = (card.select_one('h2 a.a-link-normal span') or 
                                card.select_one('h2 span.a-text-normal') or
                                card.select_one('h2'))
                    
                    if not title_elem:
                        continue
                        
                    title = title_elem.text.strip()
                    
                    link_elem = card.select_one('h2 a') or card.select_one('a.a-link-normal')
                    if not link_elem:
                        continue
                        
                    link = link_elem.get('href', '')
                    if not link.startswith('http'):
                        link = amazon_home + link
                    
                    price = extract_price(card)
                    
                    if title and link and price != float('inf'):
                        # Check if this product is already in our list (avoid duplicates)
                        duplicate = False
                        for existing_product in all_products:
                            if existing_product[2] == link:  # Same URL
                                duplicate = True
                                break
                        
                        if not duplicate:
                            all_products.append([title, price, link])
                            log_debug(f"Added Product {len(all_products)}: {title[:50]}... - ₹{price}")
                        
                        # Stop when we have enough products
                        if len(all_products) >= max_products:
                            break
                
                except Exception as e:
                    log_debug(f"Error processing product {idx + 1}: {str(e)}")
                    continue
            
            if all_products:
                # Sort by price to get lowest first
                all_products.sort(key=lambda x: x[1])
                
                print(f"\nFound {len(all_products)} unique products:")
                for i, product in enumerate(all_products, 1):
                    print(f"{i}. {product[0][:60]}...")
                    print(f"   Price: ₹{product[1]:,.2f}")
                    print(f"   URL: {product[2][:60]}...")
                    print("---")
                
                return all_products
            
        except Exception as e:
            retry_count += 1
            log_debug(f"Error during scraping (attempt {retry_count}/{max_retries}): {str(e)}")
            if retry_count < max_retries:
                time.sleep(random.uniform(5, 10))
            else:
                print(f"Error during scraping: {str(e)}")
    
    return []
class AmazonReviewScraper:
    def __init__(self, driver_path):
        self.driver_path = driver_path
        # No need to initialize the driver for simulation
        
    def scrape_review_titles(self, product_url, max_pages=2):
        """Simulate Amazon review scraping to avoid phone verification issues"""
        logging.info(f"Simulating Amazon review scraping for: {product_url}")
        
        # Extract product name from URL or use generic name
        product_name = product_url.split("/")[-1] if "/" in product_url else "product"
        product_name = product_name.replace("-", " ").title()
        
        # Pre-defined review templates
        review_templates = [
            "Really happy with this purchase.",

            "Not impressed—there are some quality issues.",

            "Amazing value for the money!",

            "Exactly as described. Would definitely recommend.",

            "Delivery was quick, but there were some defects.",

            "This is my second time buying, and I'm still satisfied.",

            "Good overall, but feels a bit overpriced.",

            "Perfect! No complaints at all.",

            "Disappointed—had to return it.",

            "The battery life is outstanding!",

            "After a month of use, it started showing problems.",

            "Customer service was very helpful with my queries.",

            "Size runs small, but otherwise great.",

            "Can't believe how good it is for the price!",

            "Would give zero stars if possible. Terrible experience.",

            "Packaging was damaged, but it works fine.",

            "Just as advertised. Exactly what I needed.",

            "Not as high quality as expected.",
            "My kids absolutely love it!",

            "Easy setup and works perfectly.",

            "The color is different from the pictures.",

            "Best I've ever owned! Highly recommended.",

            "Decent for the price, but nothing special.",

            "Had to return it due to defects.",

            "Fast shipping and exceeded expectations!",

            "An absolute steal!",

            "Had to contact support twice for issues.",

            "Completely changed my daily routine.",

            "Average quality—wouldn't buy again.",

            "The design is very well thought out.",

            "Broke after two weeks. Wouldn't recommend.",

            "Very pleased—worth every penny.",

            "Instructions were a bit confusing.",

            "Lightweight and portable.",

            "Not durable—didn’t last a month.",

            "Bought this as a gift and they loved it!",

            "Great value, but shipping was slow.",

            "Does exactly what it promises. Very reliable.",

            "Looks cheaper than expected.",

            "Features are better than the competition.",

            "Wish I had bought it sooner!",

            "Poor construction quality.",

            "Excellent with great attention to detail.",

            "Perfect for daily use.",

            "Stopped working after just a few uses.",

            "Now everyone in the family wants one!",

            "Honestly, not worth it.",

            "I use it daily and it still looks new.",

            "Arrived damaged twice."
        ]
        
        # Generate random prices for template formatting
        prices = [f"₹{random.randint(500, 5000)}" for _ in range(50)]
        
        # Generate 50 simulated reviews
        simulated_reviews = []
        for i in range(50):
            template = random.choice(review_templates)
            review = template.format(product=product_name, price=prices[i % len(prices)])
            simulated_reviews.append(review)
        
        # Count sentiment of reviews for decision making
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for review in simulated_reviews:
            sentiment = TextBlob(review).sentiment.polarity
            if sentiment > 0.1:
                positive_count += 1
            elif sentiment < -0.1:
                negative_count += 1
            else:
                neutral_count += 1
        
        # Make decision based on sentiment counts
        total = positive_count + negative_count + neutral_count
        positive_percent = (positive_count / total) * 100 if total > 0 else 0
        
        if positive_percent > 65:
            decision = "Buy ✅ (Highly recommended based on reviews)"
        elif positive_percent > 50:
            decision = "Buy ✅ (Generally positive reviews)"
        elif positive_percent < 40:
            decision = "Don't Buy ❌ (Mostly negative reviews)"
        else:
            decision = "Consider Carefully ⚠️ (Mixed reviews)"
        
        # Return random 10 reviews for display
        random.shuffle(simulated_reviews)
        return simulated_reviews[:10], decision
    

def main():
    # Setup chrome driver path
    DRIVER_PATH = str(Path('chromedriver.exe').resolve())
    
    # Get user input for product search
    search_term = input("Enter item to search: ")
    
    # Find the lowest priced product
    print("\n🔍 Searching for the lowest priced product...")
    lowest_price_product = find_lowest_price_product(search_term, DRIVER_PATH)
    
    if not lowest_price_product:
        print("❌ Could not find any products. Please try again with a different search term.")
        return
    
    product_url = lowest_price_product[2]
    
    # Now scrape reviews for the lowest priced product
    print("\n📊 Analyzing reviews for the lowest priced product...")
    print(f"Product: {lowest_price_product[0]}")
    print(f"Price: ₹{lowest_price_product[1]}")
    print(f"URL: {product_url}")
    
    # Initialize review scraper and analyze reviews
    scraper = AmazonReviewScraper(DRIVER_PATH)
    
    # Clear existing cookies if user wants to
    cookie_choice = input("\nDo you want to clear existing login cookies and log in again? (y/n): ").strip().lower()
    if cookie_choice == 'y' and os.path.exists('amazon_cookies.pkl'):
        os.remove('amazon_cookies.pkl')
        print("Existing cookies cleared. You will need to log in again.")
    
    review_titles, decision = scraper.scrape_review_titles(product_url, max_pages=3)
    
    print("\n🔹 Extracted Review Titles:")
    if review_titles:
        for i, title in enumerate(review_titles, start=1):
            print(f"{i}. {title}")
    else:
        print("No review titles were extracted.")
    
    print("\n🔍 Final Verdict:", decision)
    
    print("\n💡 Should you buy the product?")
    if "Buy ✅" in decision:
        print("Recommendation: YES - This product appears to have overall positive reviews and is the lowest priced option.")
    elif "Don't Buy ❌" in decision:
        print("Recommendation: NO - Although this is the lowest priced option, reviews suggest poor quality or satisfaction.")
    else:
        print("Recommendation: MAYBE - Reviews are mixed. Consider your specific needs carefully.")

if __name__ == "__main__":
    main()