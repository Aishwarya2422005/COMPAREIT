import streamlit as st
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
import pandas as pd
import concurrent.futures
from textblob import TextBlob

# Utility Functions
def get_random_user_agent():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    return random.choice(user_agents)

def create_browser(driver_path):
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument(f'user-agent={get_random_user_agent()}')
    
    service = Service(driver_path)
    browser = webdriver.Chrome(service=service, options=chrome_options)
    return browser

# Amazon Scraping Function
def scrape_amazon(name, driver_path):
    name = name.replace(' ', '+')
    URL = f"https://www.amazon.in/s?k={name}"
    amazon_home = 'https://www.amazon.in'
    
    browser = create_browser(driver_path)
    
    try:
        browser.get(URL)
        time.sleep(random.uniform(3, 7))
        
        # Wait for search results
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
        )
        
        # Scroll to load more results
        for _ in range(3):
            browser.execute_script("window.scrollBy(0, 500);")
            time.sleep(random.uniform(0.5, 1.5))
        
        html = browser.page_source
        soup = BeautifulSoup(html, 'lxml')
        
        amazon_results = []
        for card in soup.select('div[data-component-type="s-search-result"]')[:5]:
            try:
                # Title extraction
                title_elem = (card.select_one('h2 a.a-link-normal span') or 
                            card.select_one('h2 span.a-text-normal') or
                            card.select_one('h2'))
                
                if not title_elem:
                    continue
                    
                title = title_elem.text.strip()
                
                # Link extraction
                link_elem = card.select_one('h2 a') or card.select_one('a.a-link-normal')
                if not link_elem:
                    continue
                    
                link = amazon_home + link_elem.get('href', '')
                
                # Price extraction
                price_selectors = [
                    'span.a-price-whole',
                    'span.a-price span[aria-hidden="true"]',
                    'span.a-price',
                    'span.a-offscreen'
                ]
                
                price = 'Not Available'
                for selector in price_selectors:
                    price_elem = card.select_one(selector)
                    if price_elem:
                        price = price_elem.text.strip().replace('₹', '').replace(',', '').strip('.')
                        break
                
                amazon_results.append({
                    'title': title,
                    'price': price,
                    'link': link
                })
                
            except Exception as e:
                st.warning(f"Amazon scraping error: {e}")
        
        return amazon_results
    
    except Exception as e:
        st.error(f"Amazon scraping failed: {e}")
        return []
    
    finally:
        browser.quit()

# Flipkart Scraping Function
def scrape_flipkart(name, driver_path):
    name = name.replace(' ', '+')
    URL = f"https://www.flipkart.com/search?q={name}"
    
    browser = create_browser(driver_path)
    
    try:
        browser.get(URL)
        time.sleep(10)  # Extended wait time
        
        # Try multiple strategies to find product elements
        product_strategies = [
            (By.CSS_SELECTOR, 'div[data-id]'),
            (By.CSS_SELECTOR, 'div._1AtVbE'),
            (By.XPATH, '//div[contains(@class, "product")]'),
            (By.XPATH, '//a[contains(@href, "/p/")]/../..')
        ]
        
        product_containers = []
        for strategy in product_strategies:
            try:
                product_containers = browser.find_elements(*strategy)
                if product_containers:
                    break
            except Exception:
                continue
        
        flipkart_results = []
        for container in product_containers[:5]:
            try:
                # Title extraction
                try:
                    title = container.find_element(By.XPATH, './/div[contains(@class, "_4rR01t") or contains(text(), "iPhone")]').text
                except:
                    title = "Title Not Available"
                
                # Price extraction
                try:
                    price_elem = container.find_element(By.XPATH, './/div[contains(@class, "_30jeq3") or contains(text(), "₹")]')
                    price = price_elem.text.replace('₹','').replace(',','')
                except:
                    price = "Price Not Available"
                
                # Link extraction
                try:
                    link_elem = container.find_element(By.XPATH, './/a[contains(@href, "/p/")]')
                    link = link_elem.get_attribute('href')
                except:
                    link = "Link Not Available"
                
                flipkart_results.append({
                    'title': title,
                    'price': price,
                    'link': link
                })
            
            except Exception as e:
                st.warning(f"Flipkart product processing error: {e}")
        
        return flipkart_results
    
    except Exception as e:
        st.error(f"Flipkart scraping failed: {e}")
        return []
    
    finally:
        browser.quit()

# Review Analysis Functions
def scrape_amazon_reviews(product_link, driver_path):
    browser = create_browser(driver_path)
    review_url = product_link.split('/dp/')[0] + '/product-reviews/' + product_link.split('/dp/')[1].split('/')[0]
    
    try:
        browser.get(review_url)
        time.sleep(random.uniform(3, 5))
        
        # Wait for reviews to load
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.ID, 'cm_cr-review_list'))
        )
        
        html = browser.page_source
        soup = BeautifulSoup(html, 'lxml')
        
        reviews = []
        for review in soup.select('div[data-hook="review"]')[:10]:
            try:
                title = review.select_one('a[data-hook="review-title"]')
                if not title:
                    title = review.select_one('span[data-hook="review-title"]')
                
                title_text = title.text.strip() if title else "No title"
                
                body = review.select_one('span[data-hook="review-body"]')
                body_text = body.text.strip() if body else "No body"
                
                rating_elem = review.select_one('i[data-hook="review-star-rating"]')
                if not rating_elem:
                    rating_elem = review.select_one('i[data-hook="cmps-review-star-rating"]')
                
                rating = rating_elem.text.strip().split(' ')[0] if rating_elem else "No rating"
                
                reviews.append({
                    'title': title_text,
                    'body': body_text,
                    'rating': rating
                })
            except Exception as e:
                st.warning(f"Amazon review processing error: {e}")
        
        # Sentiment analysis
        if reviews:
            # Calculate sentiment
            sentiments = []
            for review in reviews:
                analysis = TextBlob(review['title'] + " " + review['body'])
                sentiments.append(analysis.sentiment.polarity)
            
            avg_sentiment = sum(sentiments) / len(sentiments)
            
            if avg_sentiment >= 0.3:
                verdict = "Highly Positive"
            elif avg_sentiment >= 0.1:
                verdict = "Positive"
            elif avg_sentiment >= -0.1:
                verdict = "Neutral"
            elif avg_sentiment >= -0.3:
                verdict = "Negative"
            else:
                verdict = "Highly Negative"
            
            return reviews, verdict
        
        return reviews, "No reviews found"
    
    except Exception as e:
        st.error(f"Amazon review scraping failed: {e}")
        return [], "Error analyzing reviews"
    
    finally:
        browser.quit()

def scrape_flipkart_reviews(product_link, driver_path):
    browser = create_browser(driver_path)
    review_url = product_link + '/product-reviews'
    
    try:
        browser.get(review_url)
        time.sleep(random.uniform(3, 5))
        
        html = browser.page_source
        soup = BeautifulSoup(html, 'lxml')
        
        reviews = []
        for review in soup.select('div._1AtVbE')[:10]:
            try:
                title_elem = review.select_one('p._2-N8zT')
                title = title_elem.text.strip() if title_elem else "No title"
                
                body_elem = review.select_one('div.t-ZTKy')
                body = body_elem.text.strip() if body_elem else "No body"
                
                rating_elem = review.select_one('div._3LWZlK')
                rating = rating_elem.text.strip() if rating_elem else "No rating"
                
                reviews.append({
                    'title': title,
                    'body': body,
                    'rating': rating
                })
            except Exception as e:
                pass
        
        # Sentiment analysis
        if reviews:
            # Calculate sentiment
            sentiments = []
            for review in reviews:
                analysis = TextBlob(review['title'] + " " + review['body'])
                sentiments.append(analysis.sentiment.polarity)
            
            avg_sentiment = sum(sentiments) / len(sentiments)
            
            if avg_sentiment >= 0.3:
                verdict = "Highly Positive"
            elif avg_sentiment >= 0.1:
                verdict = "Positive"
            elif avg_sentiment >= -0.1:
                verdict = "Neutral"
            elif avg_sentiment >= -0.3:
                verdict = "Negative"
            else:
                verdict = "Highly Negative"
            
            return reviews, verdict
        
        return reviews, "No reviews found"
    
    except Exception as e:
        st.error(f"Flipkart review scraping failed: {e}")
        return [], "Error analyzing reviews"
    
    finally:
        browser.quit()

# Cache the search results to avoid redundant scraping
@st.cache_data(ttl=3600)  # Cache results for 1 hour
def get_amazon_products(search_term, driver_path):
    return scrape_amazon(search_term, driver_path)

@st.cache_data(ttl=3600)  # Cache results for 1 hour
def get_flipkart_products(search_term, driver_path):
    return scrape_flipkart(search_term, driver_path)

@st.cache_data(ttl=3600)  # Cache results for 1 hour
def analyze_amazon_reviews(url, driver_path):
    reviews, verdict = scrape_amazon_reviews(url, driver_path)
    return reviews, verdict

@st.cache_data(ttl=3600)  # Cache results for 1 hour
def analyze_flipkart_reviews(url, driver_path):
    reviews, verdict = scrape_flipkart_reviews(url, driver_path)
    return reviews, verdict

# Streamlit App with Enhanced UI
def main():
    # Page config
    st.set_page_config(
        page_title="PriceIT - Price Comparison & Review Analysis",
        page_icon="🔍",
        layout="wide"
    )

    # Custom CSS
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stAlert {
            padding: 1rem;
            border-radius: 0.5rem;
        }
        .product-card {
            padding: 1.5rem;
            border-radius: 0.5rem;
            border: 1px solid #e0e0e0;
            margin: 1rem 0;
            background-color: white;
        }
        .price-tag {
            font-size: 1.5rem;
            color: #2ecc71;
            font-weight: bold;
        }
        .company-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        .review-card {
            padding: 1rem;
            border-radius: 0.5rem;
            border: 1px solid #e0e0e0;
            margin: 0.5rem 0;
            background-color: #f9f9f9;
        }
        .verdict-positive {
            color: #2ecc71;
            font-weight: bold;
        }
        .verdict-neutral {
            color: #f39c12;
            font-weight: bold;
        }
        .verdict-negative {
            color: #e74c3c;
            font-weight: bold;
        }
        .best-deal {
            background-color: #e8f5e9;
            border-left: 4px solid #2ecc71;
            padding: 1rem;
            margin-top: 1rem;
        }
        .tab-content {
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header Section
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title('🛒 PriceIT: Online Shopping Assistant')
        st.markdown('### Compare prices and analyze reviews across Amazon and Flipkart')

    # Search Section
    search_container = st.container()
    with search_container:
        col1, col2 = st.columns([3,1])
        with col1:
            search_query = st.text_input('', placeholder='Enter product name (e.g., iPhone 13, Samsung TV, Laptop...)')
        with col2:
            search_button = st.button('Search 🔍', use_container_width=True)

    # ChromeDriver path
    DRIVER_PATH = str(Path('chromedriver.exe').resolve())

    if search_button and search_query:
        start_time = time.time()
        progress_text = "Searching across platforms..."
        progress_bar = st.progress(0)
        
        # Searching animation
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
            
        # Run Amazon & Flipkart scraping simultaneously
        with st.spinner('Fetching results...'):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_amazon = executor.submit(get_amazon_products, search_query, DRIVER_PATH)
                future_flipkart = executor.submit(get_flipkart_products, search_query, DRIVER_PATH)
                
                # Wait for both futures to complete
                amazon_results = future_amazon.result()
                flipkart_results = future_flipkart.result()
        
        end_time = time.time()
        progress_bar.empty()
        st.info(f"Search completed in {end_time - start_time:.2f} seconds")
        
        # Create tabs for better organization
        tab1, tab2 = st.tabs(["Product Comparison", "Review Analysis"])
        
        with tab1:
            # Results Section
            if amazon_results or flipkart_results:
                st.markdown("### 📊 Comparison Results")
                
                # Create columns for side-by-side comparison
                amazon_col, flipkart_col = st.columns(2)

                # Amazon Results
                with amazon_col:
                    st.markdown("""
                        <div class="company-header">
                            <h3>🟠 Amazon</h3>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    for product in amazon_results:
                        st.markdown(f"""
                            <div class="product-card">
                                <h4>{product['title']}</h4>
                                <p class="price-tag">₹{product['price']}</p>
                                <a href="{product['link']}" target="_blank">View on Amazon →</a>
                            </div>
                        """, unsafe_allow_html=True)

                # Flipkart Results
                with flipkart_col:
                    st.markdown("""
                        <div class="company-header">
                            <h3>🔵 Flipkart</h3>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    for product in flipkart_results:
                        st.markdown(f"""
                            <div class="product-card">
                                <h4>{product['title']}</h4>
                                <p class="price-tag">₹{product['price']}</p>
                                <a href="{product['link']}" target="_blank">View on Flipkart →</a>
                            </div>
                        """, unsafe_allow_html=True)

                # Finding the best deals
                st.markdown("### 💰 Best Deals")
                
                # Convert prices to numeric values for comparison
                amazon_prices = []
                for product in amazon_results:
                    try:
                        if product['price'] != 'Not Available':
                            price = float(product['price'].replace('₹', '').replace(',', '').strip())
                            amazon_prices.append((product, price))
                    except (ValueError, TypeError):
                        pass
                
                flipkart_prices = []
                for product in flipkart_results:
                    try:
                        if product['price'] != 'Not Available' and product['price'] != 'Price Not Available':
                            price = float(product['price'].replace('₹', '').replace(',', '').strip())
                            flipkart_prices.append((product, price))
                    except (ValueError, TypeError):
                        pass
                
                # Display best deals
                col3, col4 = st.columns(2)
                
                with col3:
                    if amazon_prices:
                        lowest_amazon = min(amazon_prices, key=lambda x: x[1])
                        st.markdown(f"""
                            <div class="best-deal">
                                <h4>🟠 Amazon Best Deal</h4>
                                <h5>{lowest_amazon[0]['title']}</h5>
                                <p class="price-tag">₹{lowest_amazon[0]['price']}</p>
                                <a href="{lowest_amazon[0]['link']}" target="_blank">View on Amazon →</a>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("No valid Amazon prices found.")
                
                with col4:
                    if flipkart_prices:
                        lowest_flipkart = min(flipkart_prices, key=lambda x: x[1])
                        st.markdown(f"""
                            <div class="best-deal">
                                <h4>🔵 Flipkart Best Deal</h4>
                                <h5>{lowest_flipkart[0]['title']}</h5>
                                <p class="price-tag">₹{lowest_flipkart[0]['price']}</p>
                                <a href="{lowest_flipkart[0]['link']}" target="_blank">View on Flipkart →</a>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("No valid Flipkart prices found.")
                
                # Price Analysis
                st.markdown("### 💡 Price Analysis")
                
                if amazon_prices and flipkart_prices:
                    analysis_cols = st.columns(3)
                    
                    with analysis_cols[0]:
                        st.metric("Lowest Price on Amazon", f"₹{lowest_amazon[1]:,.2f}")
                    
                    with analysis_cols[1]:
                        st.metric("Lowest Price on Flipkart", f"₹{lowest_flipkart[1]:,.2f}")
                    
                    with analysis_cols[2]:
                        price_diff = lowest_amazon[1] - lowest_flipkart[1]
                        better_platform = "Flipkart" if price_diff > 0 else "Amazon"
                        st.metric("Potential Savings", 
                                f"₹{abs(price_diff):,.2f}",
                                f"Better price on {better_platform}")
            else:
                st.error("No results found. Please try a different search term.")
        
        # Review Analysis
        with tab2:
            st.markdown("### 📝 Review Analysis")
            
            if not amazon_results and not flipkart_results:
                st.error("No products found for review analysis.")
            else:
                # Find products for review analysis
                amazon_product = amazon_results[0] if amazon_results else None
                flipkart_product = flipkart_results[0] if flipkart_results else None
                
                if amazon_prices:
                    amazon_product = lowest_amazon[0]
                
                if flipkart_prices:
                    flipkart_product = lowest_flipkart[0]
                
                with st.spinner("Analyzing reviews..."):
                    # Run review analysis in parallel
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future_amazon_review = executor.submit(analyze_amazon_reviews, amazon_product['link'], DRIVER_PATH) if amazon_product else None
                        future_flipkart_review = executor.submit(analyze_flipkart_reviews, flipkart_product['link'], DRIVER_PATH) if flipkart_product else None
                        
                        amazon_reviews, amazon_verdict = future_amazon_review.result() if future_amazon_review else ([], "No Amazon product available")
                        flipkart_reviews, flipkart_verdict = future_flipkart_review.result() if future_flipkart_review else ([], "No Flipkart product available")
                
                # Display review analysis
                col5, col6 = st.columns(2)
                
                with col5:
                    st.subheader("🟠 Amazon Review Analysis")
                    
                    verdict_class = "verdict-positive" if "Positive" in amazon_verdict else "verdict-negative" if "Negative" in amazon_verdict else "verdict-neutral"
                    st.markdown(f"<p><strong>Verdict:</strong> <span class='{verdict_class}'>{amazon_verdict}</span></p>", unsafe_allow_html=True)
                    
                    if amazon_reviews:
                        st.markdown("#### Top Reviews")
                        for review in amazon_reviews[:5]:
                            st.markdown(f"""
                                <div class="review-card">
                                    <h5>{review['title']}</h5>
                                    <p>Rating: {review['rating']}</p>
                                    <p>{review['body'][:200]}...</p>
                                </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("No reviews found for this product on Amazon.")
                
                with col6:
                    st.subheader("🔵 Flipkart Review Analysis")
                    
                    verdict_class = "verdict-positive" if "Positive" in flipkart_verdict else "verdict-negative" if "Negative" in flipkart_verdict else "verdict-neutral"
                    st.markdown(f"<p><strong>Verdict:</strong> <span class='{verdict_class}'>{flipkart_verdict}</span></p>", unsafe_allow_html=True)
                    
                    if flipkart_reviews:
                        st.markdown("#### Top Reviews")
                        for review in flipkart_reviews[:5]:
                            st.markdown(f"""
                                <div class="review-card">
                                    <h5>{review['title']}</h5>
                                    <p>Rating: {review['rating']}</p>
                                    <p>{review['body'][:200]}...</p>
                                </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("No reviews found for this product on Flipkart.")
                
                # Overall recommendation
                st.markdown("### 🏆 Overall Recommendation")
                
                if amazon_prices and flipkart_prices:
                    # Calculate a score based on price and reviews
                    amazon_score = 0
                    flipkart_score = 0
                    
                    # Price factor
                    if lowest_amazon[1] < lowest_flipkart[1]:
                        amazon_score += 2
                    else:
                        flipkart_score += 2
                    
                    # Review factor
                    if "Positive" in amazon_verdict:
                        amazon_score += 1
                    if "Highly Positive" in amazon_verdict:
                        amazon_score += 1
                    
                    if "Positive" in flipkart_verdict:
                        flipkart_score += 1
                    if "Highly Positive" in flipkart_verdict:
                        flipkart_score += 1
                    
                    if amazon_score > flipkart_score:
                        recommend = "Amazon"
                        reason = "Better price and/or more positive reviews"
                    elif flipkart_score > amazon_score:
                        recommend = "Flipkart"
                        reason = "Better price and/or more positive reviews"
                    else:
                        recommend = "Either platform"
                        reason = "Similar prices and review sentiment"
                    
                    st.success(f"Based on price and reviews, we recommend buying from **{recommend}**. Reason: {reason}.")
                else:
                    st.info("Not enough data to make a comprehensive recommendation.")

    # Footer
    st.markdown("""
        ---
        <div style='text-align: center; color: #666;'>
            Made with ❤️ | Data sourced from Amazon.in and Flipkart.com
        </div>
    """, unsafe_allow_html=True)

if __name__ == '__main__':
    main()