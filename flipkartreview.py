import time
import pickle
import os
import sys
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from textblob import TextBlob  # For sentiment analysis

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class FlipkartReviewScraper:
    def __init__(self, driver_path="chromedriver.exe"):
        self.driver_path = driver_path
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome driver with anti-detection measures"""
        chrome_options = Options()
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        try:
            service = Service(executable_path=self.driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Additional anti-detection measures
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("WebDriver set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up WebDriver: {e}")
            raise
    
    def handle_login(self):
        """Simple login handling - just close the popup if present"""
        logger.info("Handling login popup...")
        try:
            self.driver.get("https://www.flipkart.com")
            logger.info("Loaded Flipkart homepage")
            
            # Try to close login popup if it appears
            try:
                close_buttons = self.driver.find_elements(By.XPATH, "//button[@class='_2KpZ6l _2doB4z']")
                if close_buttons:
                    close_buttons[0].click()
                    logger.info("Closed login popup")
                    time.sleep(1)
            except Exception as e:
                logger.info(f"No login popup or couldn't close: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error during login handling: {e}")
            return False
            
    def navigate_to_product(self, product_url):
        """Navigate directly to the product URL"""
        logger.info(f"Navigating to product: {product_url}")
        try:
            self.driver.get(product_url)
            time.sleep(3)
            logger.info("Successfully loaded product page")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to product: {e}")
            return False
    
    def navigate_to_reviews(self):
        """Navigate to the reviews section from product page"""
        logger.info("Attempting to find and click on reviews section...")
        
        # First, make sure we're on a product page by checking for common elements
        try:
            product_title = self.driver.find_elements(By.XPATH, "//span[@class='B_NuCI']")
            if not product_title:
                logger.warning("This doesn't appear to be a product page")
        except:
            pass
        
        # Take a screenshot for debugging
        try:
            self.driver.save_screenshot("product_page.png")
            logger.info("Saved screenshot of product page")
        except:
            logger.warning("Could not save screenshot")
        
        # Scroll down to make review section visible
        for _ in range(3):
            self.driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(1)
        
        # Try various review section selectors
        review_selectors = [
            "//div[text()='Ratings & Reviews']",
            "//div[contains(text(), 'Ratings & Reviews')]",
            "//div[contains(@class, '_3UAT2v')]",
            "//div[contains(text(), 'Customer Reviews')]",
            "//div[contains(text(), 'All Reviews')]",
            "//a[contains(text(), 'All reviews')]",
            "//button[contains(text(), 'All reviews')]"
        ]
        
        for selector in review_selectors:
            try:
                review_elements = self.driver.find_elements(By.XPATH, selector)
                for element in review_elements:
                    try:
                        if element.is_displayed():
                            logger.info(f"Found reviews section: {element.text}")
                            element.click()
                            logger.info("Clicked on reviews section")
                            time.sleep(3)
                            return True
                    except:
                        continue
            except:
                continue
        
        # If we can't find a review section, try to find a direct "All Reviews" link
        try:
            # Search for text containing review counts
            review_count_elements = self.driver.find_elements(By.XPATH, 
                "//span[contains(text(), 'Reviews') and contains(text(), ',')]")
            
            if review_count_elements:
                for elem in review_count_elements:
                    try:
                        if elem.is_displayed():
                            logger.info(f"Found review count: {elem.text}")
                            elem.click()
                            logger.info("Clicked on review count")
                            time.sleep(3)
                            return True
                    except:
                        continue
        except:
            pass
        
        # If we're already on a review page, return true
        if "product-reviews" in self.driver.current_url:
            logger.info("Already on reviews page")
            return True
            
        logger.warning("Could not navigate to reviews section. Will try to extract reviews from current page.")
        return False
    
    def extract_review_titles(self):
        """Extract review titles from the current page"""
        review_titles = []
        
        # Scroll to load all content
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        
        # Try different selectors for review titles
        title_selectors = [
            "//p[@class='_2-N8zT']",
            "//div[@class='_2sc7ZR _2V5EHH']",
            "//div[contains(@class, '_2sc7ZR')]",
            "//p[contains(@class, '_2-N8zT')]",
            "//div[contains(@class, 't-ZTKy')]/div[1]"
        ]
        
        for selector in title_selectors:
            try:
                title_elements = self.driver.find_elements(By.XPATH, selector)
                if title_elements:
                    logger.info(f"Found {len(title_elements)} review titles using selector: {selector}")
                    for title_element in title_elements:
                        title = title_element.text.strip()
                        if title and len(title) > 3:  # Ensure it's a meaningful title
                            review_titles.append(title)
                    break
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
        
        return review_titles
    
    def extract_reviews(self):
        """Extract full reviews from the current page"""
        reviews = []
        
        # Scroll to ensure all reviews are loaded
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Try different review selectors
        review_selectors = [
            "//div[@class='t-ZTKy']",
            "//div[@class='_6K-7Co']",
            "//div[contains(@class, 't-ZTKy')]",
            "//div[contains(@class, '_6K-7Co')]"
        ]
        
        review_elements = []
        for selector in review_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements:
                    logger.info(f"Found {len(elements)} reviews using selector: {selector}")
                    review_elements = elements
                    break
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
        
        # Extract text from the found elements
        for element in review_elements:
            try:
                review_text = element.text.strip()
                if review_text and len(review_text) > 10:
                    reviews.append(review_text)
            except Exception as e:
                logger.debug(f"Error extracting review text: {e}")
        
        # If we found no reviews, take a more aggressive approach
        if not reviews:
            logger.warning("No reviews found with specific selectors. Trying general text elements...")
            try:
                # Look for any elements with substantial text
                text_elements = self.driver.find_elements(By.XPATH, 
                    "//div[string-length(text()) > 30]")
                
                for element in text_elements:
                    try:
                        text = element.text.strip()
                        if text and len(text) > 30 and text not in reviews:
                            reviews.append(text)
                    except:
                        continue
            except Exception as e:
                logger.error(f"Error finding text elements: {e}")
        
        # If we're on a product page, not a review page, try to extract the review summary
        if not reviews:
            logger.warning("No reviews found. Checking if we can extract product ratings...")
            try:
                rating_elements = self.driver.find_elements(By.XPATH, 
                    "//div[contains(@class, '_3LWZlK')]")
                
                for element in rating_elements:
                    try:
                        rating = element.text.strip()
                        if rating:
                            reviews.append(f"Product Rating: {rating}")
                    except:
                        continue
            except:
                pass
                
        return reviews
    
    def go_to_next_page(self):
        """Attempt to go to the next page of reviews"""
        try:
            # Take screenshot of bottom of page
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            next_button_selectors = [
                "//a[@class='_1LKTO3']",
                "//span[contains(text(), 'Next')]//parent::a",
                "//a[contains(text(), 'Next')]",
                "//a[contains(@class, '_1LKTO3') and contains(text(), 'Next')]"
            ]
            
            for selector in next_button_selectors:
                next_buttons = self.driver.find_elements(By.XPATH, selector)
                for button in next_buttons:
                    try:
                        if button.is_displayed() and "Next" in button.text:
                            logger.info(f"Found Next button: {button.text}")
                            button.click()
                            logger.info("Clicked Next button")
                            time.sleep(3)
                            return True
                    except:
                        continue
            
            logger.info("No Next button found or couldn't click it")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False
    
    def analyze_sentiment(self, reviews):
        """Analyze sentiment and determine if the product is worth buying"""
        if not reviews:
            return "No reviews available for analysis"
            
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        logger.info("Performing sentiment analysis...")
        for review in reviews:
            sentiment = TextBlob(review).sentiment.polarity
            if sentiment > 0.1:
                positive_count += 1
            elif sentiment < -0.1:
                negative_count += 1
            else:
                neutral_count += 1
        
        total_reviews = len(reviews)
        positive_percentage = (positive_count / total_reviews * 100) if total_reviews > 0 else 0
        negative_percentage = (negative_count / total_reviews * 100) if total_reviews > 0 else 0
        neutral_percentage = (neutral_count / total_reviews * 100) if total_reviews > 0 else 0
        
        logger.info(f"Sentiment analysis results: Positive: {positive_percentage:.1f}%, Negative: {negative_percentage:.1f}%, Neutral: {neutral_percentage:.1f}%")
        
        # Determine final decision
        if positive_percentage >= 60:
            return f"Buy ✅ ({positive_count}/{total_reviews} or {positive_percentage:.1f}% reviews are positive)"
        elif negative_percentage >= 40:
            return f"Don't Buy ❌ ({negative_count}/{total_reviews} or {negative_percentage:.1f}% reviews are negative)"
        else:
            return f"Consider with Caution ⚠️ (Mixed reviews - {positive_percentage:.1f}% positive, {negative_percentage:.1f}% negative, {neutral_percentage:.1f}% neutral)"
    
    def extract_product_info(self):
        """Extract basic product information like name and price"""
        product_info = {}
        
        try:
            # Try to extract product name
            name_selectors = [
                "//span[@class='B_NuCI']",
                "//h1[@class='yhB1nd']",
                "//span[contains(@class, 'B_NuCI')]",
                "//h1[contains(@class, 'yhB1nd')]"
            ]
            
            for selector in name_selectors:
                try:
                    name_element = self.driver.find_element(By.XPATH, selector)
                    product_info['name'] = name_element.text.strip()
                    logger.info(f"Found product name: {product_info['name']}")
                    break
                except:
                    continue
            
            # Try to extract product price
            price_selectors = [
                "//div[@class='_30jeq3 _16Jk6d']",
                "//div[contains(@class, '_30jeq3')]",
                "//div[contains(@class, 'price')]"
            ]
            
            for selector in price_selectors:
                try:
                    price_element = self.driver.find_element(By.XPATH, selector)
                    product_info['price'] = price_element.text.strip()
                    logger.info(f"Found product price: {product_info['price']}")
                    break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
        
        return product_info
    
    def scrape_reviews(self, product_url, pages_to_scrape=3):
        """
        Extract reviews from a Flipkart product page and perform sentiment analysis
        
        Args:
            product_url: URL of the Flipkart product page
            pages_to_scrape: Number of review pages to scrape
        """
        all_reviews = []
        all_titles = []
        
        try:
            # Handle login (close popup)
            if not self.handle_login():
                logger.error("Login handling failed")
                return [], [], "Error: Login handling failed", {}
            
            # Navigate to the product page
            if not self.navigate_to_product(product_url):
                logger.error("Failed to navigate to the product page")
                return [], [], "Error: Failed to load product page", {}
            
            # Extract product info first
            product_info = self.extract_product_info()
            
            # Navigate to reviews page
            self.navigate_to_reviews()
            
            # Main review extraction loop
            for page in range(1, pages_to_scrape + 1):
                logger.info(f"\n--- Processing Page {page}/{pages_to_scrape} ---")
                
                # First extract titles which are usually more reliable
                page_titles = self.extract_review_titles()
                if page_titles:
                    all_titles.extend(page_titles)
                    logger.info(f"Extracted {len(page_titles)} review titles from page {page}")
                
                # Then extract full reviews
                page_reviews = self.extract_reviews()
                if page_reviews:
                    all_reviews.extend(page_reviews)
                    logger.info(f"Extracted {len(page_reviews)} full reviews from page {page}")
                
                # Check if we found anything on this page
                if not page_reviews and not page_titles:
                    logger.warning(f"No content found on page {page}")
                
                # Go to next page if available
                if page < pages_to_scrape:
                    if not self.go_to_next_page():
                        logger.info("No more pages available. Stopping.")
                        break
            
            # Remove duplicates
            all_reviews = list(set(all_reviews))
            all_titles = list(set(all_titles))
            
            # If we haven't got any reviews, try one more approach - if the URL is not a review URL,
            # try to convert it to a reviews URL directly
            if not all_reviews and not all_titles and "product-reviews" not in product_url:
                try:
                    logger.info("Attempting to construct a direct review URL...")
                    # Extract product ID from URL
                    if "/p/" in product_url:
                        product_id = product_url.split("/p/")[1].split("?")[0]
                        direct_review_url = f"https://www.flipkart.com/product-reviews/{product_id}"
                        logger.info(f"Trying direct review URL: {direct_review_url}")
                        
                        self.driver.get(direct_review_url)
                        time.sleep(3)
                        
                        # Try again to extract reviews from this page
                        direct_titles = self.extract_review_titles()
                        direct_reviews = self.extract_reviews()
                        
                        if direct_titles:
                            all_titles.extend(direct_titles)
                        if direct_reviews:
                            all_reviews.extend(direct_reviews)
                except Exception as e:
                    logger.error(f"Error with direct review URL approach: {e}")
            
            # Sentiment analysis based on combined reviews and titles
            all_content = all_reviews + all_titles
            
            if all_content:
                decision = self.analyze_sentiment(all_content)
            else:
                decision = "Could not find any reviews to analyze"
            
            logger.info("\n--- Review Summary ---")
            logger.info(f"Total full reviews extracted: {len(all_reviews)}")
            logger.info(f"Total review titles extracted: {len(all_titles)}")
            logger.info(f"Final decision: {decision}")
            
            return all_reviews, all_titles, decision, product_info
            
        except Exception as e:
            logger.error(f"An error occurred during scraping: {e}")
            return [], [], f"Error: {e}", {}
        
        finally:
            # Clean up resources
            self.driver.quit()
            logger.info("Browser closed successfully")

def main():
    print("\n🔍 Flipkart Review Analyzer - Should You Buy It? 🛒")
    print("=" * 60)
    print("This tool analyzes Flipkart product reviews to determine if a product is worth buying.")
    
    # Get input from user
    driver_path = input("\nEnter the path to chromedriver.exe (or press Enter for default 'chromedriver.exe'): ").strip()
    if not driver_path:
        driver_path = "chromedriver.exe"
    
    if not os.path.isfile(driver_path):
        print(f"⚠️ Warning: ChromeDriver not found at '{driver_path}'. The script may fail.")
    
    product_url = input("\nEnter the Flipkart product URL: ").strip()
    
    # Basic validation for Flipkart URL
    if not product_url or "flipkart.com" not in product_url:
        print("⚠️ Invalid URL. Please enter a valid Flipkart product URL.")
        return
    
    max_pages = input("\nEnter the maximum number of review pages to scrape (1-10, default is 3): ").strip()
    if not max_pages:
        max_pages = 3
    else:
        try:
            max_pages = int(max_pages)
            if max_pages < 1 or max_pages > 10:
                print("⚠️ Invalid number of pages. Using default of 3 pages.")
                max_pages = 3
        except ValueError:
            print("⚠️ Invalid input. Using default of 3 pages.")
            max_pages = 3
    
    print("\n📊 Starting analysis with the following parameters:")
    print(f"- ChromeDriver path: {driver_path}")
    print(f"- Product URL: {product_url}")
    print(f"- Maximum pages to scrape: {max_pages}")
    
    # Initialize and run the scraper
    print("\n🔄 Scraping reviews... (This may take a few moments)")
    try:
        scraper = FlipkartReviewScraper(driver_path)
        all_reviews, all_titles, decision, product_info = scraper.scrape_reviews(product_url, max_pages)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return
    
    # Display results
    print("\n💫 Analysis Results 💫")
    print("=" * 60)
    
    # Display product info
    if product_info:
        print("\n📦 Product Information:")
        if 'name' in product_info:
            print(f"- Name: {product_info['name']}")
        if 'price' in product_info:
            print(f"- Price: {product_info['price']}")
    
    # Display stats
    print(f"\n📊 Statistics:")
    print(f"- Review titles found: {len(all_titles)}")
    print(f"- Full reviews found: {len(all_reviews)}")
    print(f"- Total content analyzed: {len(all_titles) + len(all_reviews)}")
    
    # Display review titles
    if all_titles:
        print(f"\n🔹 Sample Review Titles:")
        for i, title in enumerate(all_titles[:5], start=1):
            print(f"{i}. {title}")
        if len(all_titles) > 5:
            print(f"... and {len(all_titles) - 5} more titles")
    
    # Display reviews
    if all_reviews:
        print(f"\n📝 Sample Full Reviews:")
        for i, review in enumerate(all_reviews[:3], start=1):
            # Truncate long reviews for display
            if len(review) > 100:
                print(f"{i}. {review[:100]}...")
            else:
                print(f"{i}. {review}")
        if len(all_reviews) > 3:
            print(f"... and {len(all_reviews) - 3} more reviews")
    
    # Display decision
    print("\n🔍 Final Verdict:", decision)
    
    if not all_titles and not all_reviews:
        print("\n⚠️ Warning: No reviews were found. The product may be new or have limited reviews.")
        print("Suggestions:")
        print("- Try a different product")
        print("- Check if the product URL is correct")
        print("- Check if your internet connection is stable")
    
    print("\n💡 Thank you for using the Flipkart Review Analyzer!")

if __name__ == "__main__":
    main()