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

# Cache search results to avoid redundant scraping
@st.cache_data(ttl=3600)
def get_amazon_products(search_term):
    try:
        product = find_lowest_price_product(search_term, DRIVER_PATH, num_products=5)
        return product if isinstance(product, list) else [product] if product else []
    except Exception as e:
        st.error(f"Error fetching Amazon products: {str(e)}")
        return []

@st.cache_data(ttl=3600)
def get_flipkart_products(search_term):
    try:
        flipkart_searcher = FlipkartProductSearch(DRIVER_PATH)
        all_products = flipkart_searcher.search_products(search_term)
        return all_products[:5] if all_products else []
    except Exception as e:
        st.error(f"Error fetching Flipkart products: {str(e)}")
        return []

if st.button("Search 🔍"):
    if not search_term:
        st.warning("Please enter a product name to search.")
    else:
        with st.spinner("Searching for products..."):
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_amazon = executor.submit(get_amazon_products, search_term)
                future_flipkart = executor.submit(get_flipkart_products, search_term)
                amazon_products = future_amazon.result()
                flipkart_products = future_flipkart.result()
            end_time = time.time()
            st.info(f"Search completed in {end_time - start_time:.2f} seconds")

        tab1, tab2 = st.tabs(["Product Comparison", "Review Analysis"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🟠 Amazon Top Products")
                st.dataframe(pd.DataFrame(amazon_products, columns=["Title", "Price", "Link"])) if amazon_products else st.error("No products found on Amazon.")
            with col2:
                st.subheader("🔵 Flipkart Top Products")
                st.dataframe(pd.DataFrame(flipkart_products)[["title", "price_text", "link"]]) if flipkart_products else st.error("No products found on Flipkart.")
        
        with tab2:
            if amazon_products or flipkart_products:
                st.subheader("📝 Review Sentiment Analysis")
                
                @st.cache_data(ttl=3600)
                def analyze_amazon_reviews(url):
                    try:
                        amazon_scraper = AmazonReviewScraper(DRIVER_PATH)
                        _, verdict = amazon_scraper.scrape_review_titles(url, max_pages=1)
                        return verdict
                    except Exception as e:
                        return f"Error analyzing Amazon reviews: {e}"
                
                @st.cache_data(ttl=3600)
                def analyze_flipkart_reviews(url):
                    try:
                        flipkart_scraper = FlipkartReviewScraper(DRIVER_PATH)
                        _, _, verdict, _ = flipkart_scraper.scrape_reviews(url, pages_to_scrape=1)
                        return verdict
                    except Exception as e:
                        return f"Error analyzing Flipkart reviews: {e}"
                
                with st.spinner("Analyzing reviews..."):
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        amazon_verdict = executor.submit(analyze_amazon_reviews, amazon_products[0][2]).result() if amazon_products else "No Amazon product available."
                        flipkart_verdict = executor.submit(analyze_flipkart_reviews, flipkart_products[0]["link"]).result() if flipkart_products else "No Flipkart product available."
                
                col3, col4 = st.columns(2)
                with col3:
                    st.subheader("🔸 Amazon Review Analysis")
                    st.write(f"**Verdict:** {amazon_verdict}")
                with col4:
                    st.subheader("🔹 Flipkart Review Analysis")
                    st.write(f"**Verdict:** {flipkart_verdict}")
                
                st.success("✅ Analysis completed! Compare reviews to make an informed decision.")
            else:
                st.warning("No products found for review analysis.")
