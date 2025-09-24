import streamlit as st
import pandas as pd
import concurrent.futures
import time
from pathlib import Path
from amaz import find_lowest_price_product, AmazonReviewScraper
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
        product = find_lowest_price_product(search_term, DRIVER_PATH, num_products=5)
        return product if isinstance(product, list) else [product] if product else []
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
            if amazon_products:
                try:
                    lowest_amazon = min(amazon_products, key=lambda x: float(str(x[1]).replace('₹', '').replace(',', '').strip()))
                except (ValueError, TypeError):
                    lowest_amazon = amazon_products[0]  # Fallback if price parsing fails
            else:
                lowest_amazon = None
                
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