import time
import os
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from textblob import TextBlob  # For sentiment analysis

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class FlipkartProductAnalyzer:
    def _init_(self, driver_path="chromedriver.exe"):
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
    
    def close_driver(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logger.info("Browser closed successfully")
    
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
    
    def search_for_products(self, search_query):
        """Search for products on Flipkart and get all products"""
        logger.info(f"Searching for: {search_query}")
        
        # Handle login first
        if not self.handle_login():
            logger.error("Failed to handle login")
            return []
        
        # Format the search query
        search_query = search_query.replace(' ', '+')
        search_url = f"https://www.flipkart.com/search?q={search_query}"
        
        logger.info(f"Navigating to search URL: {search_url}")
        try:
            self.driver.get(search_url)
            time.sleep(5)  # Wait for page to load
            
            # Try multiple strategies to find product elements
            product_strategies = [
                (By.CSS_SELECTOR, 'div[data-id]'),
                (By.CSS_SELECTOR, 'div._1AtVbE'),
                (By.XPATH, '//div[contains(@class, "product")]'),
                (By.XPATH, '//a[contains(@href, "/p/")]/../..')
            ]
            
            products_found = False
            product_containers = []
            
            for strategy in product_strategies:
                try:
                    product_containers = self.driver.find_elements(*strategy)
                    if product_containers:
                        products_found = True
                        logger.info(f"Found {len(product_containers)} products using {strategy}")
                        break
                except Exception as e:
                    logger.debug(f"Strategy {strategy} failed: {e}")
            
            if not products_found:
                logger.warning("No products found. Saving page source for debugging.")
                with open('debug_page_source.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                return []
            
            products = []
            
            # Process all found products
            for idx, container in enumerate(product_containers, 1):
                try:
                    # More comprehensive title extraction
                    title_selectors = [
                        './/a[contains(@href, "/p/")]//div[@class="_4rR01t"]',
                        './/div[contains(@class, "_4rR01t")]',
                        './/a[contains(@class, "s1Q9rs")]',
                        './/a[contains(@href, "/p/")]',
                        './/div[contains(@class, "product-title")]'
                    ]
                    
                    title = "Title Not Available"
                    for selector in title_selectors:
                        try:
                            title_elem = container.find_element(By.XPATH, selector)
                            candidate_title = title_elem.text.strip()
                            if candidate_title and candidate_title != "Add to Compare":
                                title = candidate_title
                                break
                        except:
                            continue
                    
                    # Price extraction with multiple attempts
                    price = "Price Not Available"
                    try:
                        price_elem = container.find_element(By.XPATH, './/div[contains(@class, "_30jeq3") or contains(text(), "₹")]')
                        price_text = price_elem.text.strip()
                        if price_text:
                            price_num = price_text.replace('₹', '').replace(',', '').strip()
                            # Only add if we can convert it to a number
                            try:
                                price_value = float(price_num)
                                price = price_num
                            except:
                                price = "Price Not Available"
                    except:
                        pass
                    
                    # Link extraction
                    link = "Link Not Available"
                    try:
                        link_elem = container.find_element(By.XPATH, './/a[contains(@href, "/p/")]')
                        link = link_elem.get_attribute('href')
                    except:
                        pass
                    
                    # Only add products with valid prices and links
                    if price != "Price Not Available" and link != "Link Not Available":
                        products.append({
                            "title": title,
                            "price": price,
                            "price_value": float(price) if price != "Price Not Available" else float('inf'),
                            "link": link
                        })
                
                except Exception as e:
                    logger.error(f"Error processing product {idx}: {e}")
            
            return products
            
        except Exception as e:
            logger.error(f"Error during product search: {e}")
            return []
    
    def navigate_to_reviews(self, product_url):
        """Navigate to the reviews section from product page"""
        logger.info(f"Navigating to product: {product_url}")
        try:
            self.driver.get(product_url)
            time.sleep(3)
            logger.info("Successfully loaded product page")
        except Exception as e:
            logger.error(f"Failed to navigate to product: {e}")
            return False
        
        logger.info("Attempting to find and click on reviews section...")
        
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
            
        # Try direct URL approach if all else fails
        try:
            if "/p/" in product_url:
                product_id = product_url.split("/p/")[1].split("?")[0]
                direct_review_url = f"https://www.flipkart.com/product-reviews/{product_id}"
                logger.info(f"Trying direct review URL: {direct_review_url}")
                
                self.driver.get(direct_review_url)
                time.sleep(3)
                return True
        except Exception as e:
            logger.error(f"Error with direct review URL approach: {e}")
            
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
            # Navigate to the product page
            if not self.navigate_to_product(product_url):
                logger.error("Failed to navigate to the product page")
                return [], [], "Error: Failed to load product page", {}
            
            # Extract product info first
            product_info = self.extract_product_info()
            
            # Navigate to reviews page
            self.navigate_to_reviews(product_url)
            
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

def filter_lowest_price_products(products, num_products=3):
    """Get the X lowest priced products from the list"""
    if not products:
        return []
    
    # Sort by price
    sorted_products = sorted(products, key=lambda x: x['price_value'])
    
    # Return the X lowest or all if fewer
    return sorted_products[:min(num_products, len(sorted_products))]

def main():
    print("\n🔍 Flipkart Product Analyzer - Find Lowest Priced Products & Analyze Reviews 🛒")
    print("=" * 80)
    print("This tool finds the lowest priced products on Flipkart and analyzes their reviews to help you make better buying decisions.")
    
    # Get ChromeDriver path
    driver_path = input("\nEnter the path to chromedriver.exe (or press Enter for default 'chromedriver.exe'): ").strip()
    if not driver_path:
        driver_path = "chromedriver.exe"
    
    if not os.path.isfile(driver_path):
        print(f"⚠️ Warning: ChromeDriver not found at '{driver_path}'. The script may fail.")
    
    # Get search query
    search_query = input("\nEnter the product to search for: ").strip()
    if not search_query:
        print("⚠️ Error: Search query cannot be empty.")
        return
    
    # Get number of products to analyze
    num_products = input("\nEnter the number of lowest-priced products to analyze (default is 3): ").strip()
    if not num_products:
        num_products = 3
    else:
        try:
            num_products = int(num_products)
            if num_products < 1:
                print("⚠️ Invalid number. Using default of 3 products.")
                num_products = 3
        except ValueError:
            print("⚠️ Invalid input. Using default of 3 products.")
            num_products = 3
    
    # Get number of review pages to scrape
    review_pages = input("\nEnter the number of review pages to analyze per product (default is 2): ").strip()
    if not review_pages:
        review_pages = 2
    else:
        try:
            review_pages = int(review_pages)
            if review_pages < 1 or review_pages > 10:
                print("⚠️ Invalid number of pages. Using default of 2 pages.")
                review_pages = 2
        except ValueError:
            print("⚠️ Invalid input. Using default of 2 pages.")
            review_pages = 2
    
    print("\n📊 Starting analysis with the following parameters:")
    print(f"- ChromeDriver path: {driver_path}")
    print(f"- Search query: {search_query}")
    print(f"- Products to analyze: {num_products}")
    print(f"- Review pages per product: {review_pages}")
    
    # Initialize the analyzer
    analyzer = None
    try:
        analyzer = FlipkartProductAnalyzer(driver_path)
        
        # Step 1: Search for products
        print("\n🔎 Searching for products... (This may take a moment)")
        all_products = analyzer.search_for_products(search_query)
        
        if not all_products:
            print("❌ No products found for your search query.")
            return
        
        print(f"\n✅ Found {len(all_products)} products.")
        
        # Step 2: Filter products with lowest prices
        lowest_priced_products = filter_lowest_price_products(all_products, num_products)
        
        if not lowest_priced_products:
            print("❌ Could not determine the lowest priced products.")
            return
        
        print(f"\n💰 Top {len(lowest_priced_products)} Lowest Priced Products:")
        print("=" * 80)
        
        for idx, product in enumerate(lowest_priced_products, 1):
            print(f"\n{idx}. {product['title']}")
            print(f"   Price: ₹{product['price']}")
            print(f"   Link: {product['link']}")
        
        # Step 3: Analyze reviews for each low-priced product
        print("\n\n📝 Analyzing Reviews for Lowest Priced Products")
        print("=" * 80)
        
        product_results = []
        
        for idx, product in enumerate(lowest_priced_products, 1):
            print(f"\n\n📌 Analyzing Product {idx}: {product['title']}")
            print("-" * 80)
            
            # Scrape reviews
            all_reviews, all_titles, decision, product_info = analyzer.scrape_reviews(product['link'], review_pages)
            
            # Store results
            product_results.append({
                "product": product,
                "reviews": all_reviews,
                "titles": all_titles,
                "decision": decision,
                "additional_info": product_info
            })
            
            # Display current product results
            print(f"\n📊 Results for {product['title']}:")
            print(f"- Price: ₹{product['price']}")
            print(f"- Review titles found: {len(all_titles)}")
            print(f"- Full reviews found: {len(all_reviews)}")
            
            # Display sample reviews
            if all_titles:
                print(f"\n🔹 Sample Review Titles:")
                for i, title in enumerate(all_titles[:3], start=1):
                    print(f"{i}. {title}")
                if len(all_titles) > 3:
                    print(f"... and {len(all_titles) - 3} more titles")
            
            # Display verdict
            print(f"\n🔍 Verdict: {decision}")
        
        # Step 4: Final comparison and recommendation
        print("\n\n🏆 Final Comparison and Recommendation")
        print("=" * 80)
        
        # Find the best product based on price and reviews
        best_product = None
        best_product_idx = -1
        
        for idx, result in enumerate(product_results):
            decision = result["decision"]
            
            # If this is a "Buy" recommendation, it's a candidate
            if "Buy ✅" in decision:
                if best_product is None or result["product"]["price_value"] < best_product["product"]["price_value"]:
                    best_product = result
                    best_product_idx = idx
        
        # If no "Buy" products, look for "Consider with Caution"
        if best_product is None:
            for idx, result in enumerate(product_results):
                decision = result["decision"]
                
                if "Consider with Caution" in decision:
                    if best_product is None or result["product"]["price_value"] < best_product["product"]["price_value"]:
                        best_product = result
                        best_product_idx = idx
        
        # If still no recommendation, just pick the cheapest
        if best_product is None and product_results:
            best_product = product_results[0]  # Already sorted by price
            best_product_idx = 0
        
        # Present the final recommendation
        if best_product:
            print(f"\n👑 Best Product Recommendation:")
            print(f"Product: {best_product['product']['title']}")
            print(f"Price: ₹{best_product['product']['price']}")
            print(f"Decision: {best_product['decision']}")
            print(f"Link: {best_product['product']['link']}")
            
            print("\nReason for recommendation:")
            if "Buy ✅" in best_product['decision']:
                print("✓ This product has positive reviews and is among the lowest priced options.")
            elif "Consider with Caution" in best_product['decision']:
                print("✓ This product has mixed reviews but offers the best value for money.")
            else:
                print("✓ This product has the lowest price among the options analyzed.")
            
            # Compare with other products
            if len(product_results) > 1:
                print("\nComparison with other products:")
                for idx, result in enumerate(product_results):
                    if idx != best_product_idx:
                        price_diff = result["product"]["price_value"] - best_product["product"]["price_value"]
                        print(f"- {result['product']['title']}: ₹{result['product']['price']} " +
                              f"(₹{price_diff:.2f} more expensive, verdict: {result['decision']})")
        else:
            print("\n❌ Could not determine a best product recommendation.")
        
        # Add a final overall verdict based on all products analyzed
        print("\n🔍 Final Verdict:")
        
        # Count product verdicts
        buy_count = sum(1 for result in product_results if "Buy ✅" in result["decision"])
        dont_buy_count = sum(1 for result in product_results if "Don't Buy ❌" in result["decision"])
        caution_count = sum(1 for result in product_results if "Consider with Caution ⚠️" in result["decision"])
        
        total_products = len(product_results)
        if total_products > 0:
            positive_percentage = (buy_count / total_products) * 100
            negative_percentage = (dont_buy_count / total_products) * 100
            neutral_percentage = (caution_count / total_products) * 100
            
            if buy_count > dont_buy_count and buy_count > caution_count:
                print(f"Buy ✅ ({positive_percentage:.1f}% of analyzed products received positive reviews)")
            elif dont_buy_count > buy_count and dont_buy_count > caution_count:
                print(f"Don't Buy ❌ ({negative_percentage:.1f}% of analyzed products received negative reviews)")
            else:
                print(f"Consider with Caution ⚠️ (Mixed reviews - {positive_percentage:.1f}% positive, {negative_percentage:.1f}% negative, {neutral_percentage:.1f}% neutral)")
        
        print("\n🏁 Analysis complete!")
        
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        # Clean up
        if analyzer:
            analyzer.close_driver()
if __name__ == "__main__":
    main()