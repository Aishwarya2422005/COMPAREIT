import time
import pickle
import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from textblob import TextBlob  # Import TextBlob for sentiment analysis

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)  # Fixed: Use double underscores

class AmazonReviewScraper:
    def __init__(self, driver_path):  # Fixed: Use double underscores
        self.driver_path = driver_path
        self.setup_driver()

    def setup_driver(self):
        """Setup Chrome driver with anti-detection measures"""
        chrome_options = Options()
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

        service = Service(executable_path=self.driver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def handle_login(self):
        """Handle Amazon login process"""
        if os.path.exists('amazon_cookies.pkl'):
            self.driver.get("https://www.amazon.in")
            cookies = pickle.load(open("amazon_cookies.pkl", "rb"))
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            return True

        self.driver.get("https://www.amazon.in")
        print("\nPlease log in to Amazon manually and press Enter to continue...")
        input()
        pickle.dump(self.driver.get_cookies(), open("amazon_cookies.pkl", "wb"))
        return True

    def navigate_to_reviews(self, product_url):
        """Navigate to the full review page by clicking 'See more reviews'"""
        self.driver.get(product_url)
        time.sleep(3)

        try:
            see_more_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "See all reviews"))  # Fixed: Corrected link text
            )
            see_more_button.click()
            logger.info("Clicked 'See all reviews' to access the full review page.")
            time.sleep(3)
            return True
        except TimeoutException:
            logger.error("Could not find 'See all reviews' button. Proceeding with main product page.")
            return False

    def extract_review_titles(self):
        """Extract only bolded review titles from the current page"""
        review_titles = []
        time.sleep(2)

        try:
            # Fixed: Updated selector to match Amazon's current structure
            review_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a.review-title-content span')

            for review in review_elements:
                title = review.text.strip()
                if title:
                    review_titles.append(title)

            return review_titles

        except Exception as e:
            logger.error(f"Error extracting review titles: {e}")
            return []

    def go_to_next_page(self):
        """Attempt to go to the next page of reviews"""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, 'li.a-last a')
            next_button.click()
            time.sleep(2)
            return True
        except NoSuchElementException:
            return False

    def analyze_sentiment(self, reviews):
        """Analyze sentiment and determine if the product is worth buying"""
        positive_count = 0
        negative_count = 0
        neutral_count = 0  # Added: Track neutral reviews

        for review in reviews:
            sentiment = TextBlob(review).sentiment.polarity  # Get sentiment score
            if sentiment > 0.1:  # Fixed: Added threshold for better classification
                positive_count += 1
            elif sentiment < -0.1:  # Fixed: Added threshold for better classification
                negative_count += 1
            else:
                neutral_count += 1

        # Added: Include total reviews in decision
        total_reviews = len(reviews)
        positive_percentage = (positive_count / total_reviews * 100) if total_reviews > 0 else 0
        
        # Determine final decision with more details
        if positive_count > negative_count:
            return f"Buy ✅ ({positive_count}/{total_reviews} or {positive_percentage:.1f}% reviews are positive)"
        else:
            negative_percentage = (negative_count / total_reviews * 100) if total_reviews > 0 else 0
            return f"Don't Buy ❌ ({negative_count}/{total_reviews} or {negative_percentage:.1f}% reviews are negative)"

    def scrape_review_titles(self, product_url, max_pages=2):
        """Scrape up to max_pages review titles from Amazon and analyze sentiment"""
        all_titles = []
        page_number = 1

        if not self.handle_login():
            logger.error("Login failed")
            return [], "Error: Login failed"  # Fixed: Return tuple with error message

        self.navigate_to_reviews(product_url)

        while page_number <= max_pages:
            logger.info(f"Scraping page {page_number}")

            page_titles = self.extract_review_titles()
            all_titles.extend(page_titles)
            logger.info(f"Collected {len(page_titles)} titles from page {page_number}")

            if not self.go_to_next_page():
                logger.info("No more pages available")
                break

            page_number += 1
            time.sleep(2)

        self.driver.quit()

        # Check if we collected any reviews
        if not all_titles:
            return [], "Error: No reviews collected"  # Fixed: Return tuple with error message

        # Perform sentiment analysis
        final_decision = self.analyze_sentiment(all_titles)
        return all_titles, final_decision

def main():
    driver_path = "chromedriver.exe"  # Update this path if needed
    product_url = "https://www.amazon.in/iPhone-16-128-Plus-Ultrmarine/dp/B0DGJ65N7V/"  # Simplified URL

    scraper = AmazonReviewScraper(driver_path)
    review_titles, decision = scraper.scrape_review_titles(product_url, max_pages=3)

    # Fixed: Check if reviews were collected
    if not review_titles:
        print("\n❌ Error: Failed to collect reviews. Please check the URL or your network connection.")
        return

    print(f"\n🔹 Extracted {len(review_titles)} Bolded Review Titles:")
    for i, title in enumerate(review_titles, start=1):
        print(f"{i}. {title}")

    print("\n🔍 Final Verdict:", decision)

if __name__ == "__main__":  # Fixed: Use double underscores
    main()