import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import re

# Mock Future Price Prediction Feature
def show_price_prediction_feature():
    """Mock implementation of future price prediction feature"""
    st.markdown("<div class='comparison-header'>🔮 AI Price Prediction</div>", unsafe_allow_html=True)
    
    # Prediction settings
    col1, col2 = st.columns([1, 1])
    
    with col1:
        prediction_days = st.selectbox(
            "Prediction Period",
            [7, 14, 30, 60],
            index=1,
            help="Select how many days ahead to predict prices"
        )
    
    with col2:
        prediction_model = st.selectbox(
            "AI Model",
            ["Prophet", "ARIMA", "LSTM Neural Network", "Random Forest"],
            index=2,
            help="Select the AI model for price prediction"
        )
    
    # Mock prediction button
    if st.button("🚀 Generate Price Prediction", key="predict_price", use_container_width=True):
        # Show loading animation
        with st.spinner("AI is analyzing market trends and historical data..."):
            # Simulate processing time
            import time
            time.sleep(2)
            
            # Mock current prices (you would get these from your existing product data)
            current_flipkart_price = 15999.0
            current_amazon_price = 16499.0
            
            # Generate mock prediction data
            dates = pd.date_range(start=datetime.now(), periods=prediction_days + 1)
            
            # Create realistic price fluctuations with some trend
            flipkart_predictions = []
            amazon_predictions = []
            
            # Add some market logic to predictions
            base_trend = random.choice([-0.02, -0.01, 0.01, 0.02])  # Overall market trend
            
            for i in range(prediction_days + 1):
                if i == 0:
                    flipkart_predictions.append(current_flipkart_price)
                    amazon_predictions.append(current_amazon_price)
                else:
                    # Add trend + some random variation
                    flipkart_change = base_trend + random.uniform(-0.03, 0.03)
                    amazon_change = base_trend + random.uniform(-0.03, 0.03)
                    
                    flipkart_predictions.append(
                        flipkart_predictions[-1] * (1 + flipkart_change)
                    )
                    amazon_predictions.append(
                        amazon_predictions[-1] * (1 + amazon_change)
                    )
            
            # Create prediction DataFrame
            prediction_df = pd.DataFrame({
                'Date': dates,
                'Flipkart_Predicted': flipkart_predictions,
                'Amazon_Predicted': amazon_predictions
            })
            
            # Display prediction chart
            fig = go.Figure()
            
            # Add current price line
            fig.add_trace(go.Scatter(
                x=[dates[0], dates[0]], 
                y=[current_flipkart_price, current_amazon_price],
                mode='markers',
                marker=dict(size=10, color=['#2874F0', '#FF9900']),
                name='Current Price',
                showlegend=False
            ))
            
            # Add prediction lines
            fig.add_trace(go.Scatter(
                x=prediction_df['Date'], 
                y=prediction_df['Flipkart_Predicted'],
                mode='lines+markers',
                line=dict(color='#2874F0', width=3),
                name='Flipkart Predicted',
                hovertemplate='<b>Flipkart</b><br>Date: %{x}<br>Price: ₹%{y:,.0f}<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=prediction_df['Date'], 
                y=prediction_df['Amazon_Predicted'],
                mode='lines+markers',
                line=dict(color='#FF9900', width=3),
                name='Amazon Predicted',
                hovertemplate='<b>Amazon</b><br>Date: %{x}<br>Price: ₹%{y:,.0f}<extra></extra>'
            ))
            
            # Add confidence intervals (mock)
            upper_bound_f = [p * 1.05 for p in flipkart_predictions]
            lower_bound_f = [p * 0.95 for p in flipkart_predictions]
            
            fig.add_trace(go.Scatter(
                x=list(dates) + list(dates[::-1]),
                y=upper_bound_f + lower_bound_f[::-1],
                fill='toself',
                fillcolor='rgba(40, 116, 240, 0.1)',
                line=dict(color='rgba(255,255,255,0)'),
                name='Flipkart Confidence',
                showlegend=False
            ))
            
            fig.update_layout(
                title=f'AI Price Prediction - Next {prediction_days} Days',
                xaxis_title='Date',
                yaxis_title='Price (₹)',
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Prediction insights
            col1, col2, col3 = st.columns(3)
            
            final_flipkart = flipkart_predictions[-1]
            final_amazon = amazon_predictions[-1]
            
            flipkart_change = ((final_flipkart - current_flipkart_price) / current_flipkart_price) * 100
            amazon_change = ((final_amazon - current_amazon_price) / current_amazon_price) * 100
            
            with col1:
                st.metric(
                    "Flipkart Prediction",
                    f"₹{final_flipkart:,.0f}",
                    f"{flipkart_change:+.1f}%"
                )
            
            with col2:
                st.metric(
                    "Amazon Prediction", 
                    f"₹{final_amazon:,.0f}",
                    f"{amazon_change:+.1f}%"
                )
            
            with col3:
                savings = abs(final_flipkart - final_amazon)
                better_platform = "Flipkart" if final_flipkart < final_amazon else "Amazon"
                st.metric(
                    "Predicted Savings",
                    f"₹{savings:,.0f}",
                    f"Buy from {better_platform}"
                )
            
            # AI Insights
            st.markdown("### 🤖 AI Insights")
            
            insights = []
            if abs(flipkart_change) > 5:
                insights.append(f"📈 Significant price movement expected on Flipkart ({flipkart_change:+.1f}%)")
            if abs(amazon_change) > 5:
                insights.append(f"📈 Significant price movement expected on Amazon ({amazon_change:+.1f}%)")
            
            if flipkart_change < -3:
                insights.append("🔥 Great time to buy from Flipkart - prices expected to drop!")
            elif amazon_change < -3:
                insights.append("🔥 Great time to buy from Amazon - prices expected to drop!")
            
            if len(insights) == 0:
                insights.append("📊 Prices are expected to remain relatively stable")
                insights.append(f"💡 Best platform: {better_platform} (₹{savings:,.0f} savings)")
            
            for insight in insights:
                st.info(insight)
            
            # Model confidence
            confidence = random.randint(75, 95)
            st.progress(confidence / 100.0)
            st.caption(f"Model Confidence: {confidence}% | Based on {prediction_model} algorithm")


# Mock Email Alert Feature  
def show_email_alert_feature():
    """Mock implementation of email drop notification feature"""
    st.markdown("<div class='comparison-header'>📧 Price Drop Alerts</div>", unsafe_allow_html=True)
    
    # Email alert setup
    with st.expander("⚙️ Setup Price Alert", expanded=True):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**📧 Notification Settings**")
            email = st.text_input(
                "Email Address",
                placeholder="your.email@example.com",
                help="We'll send price drop notifications to this email"
            )
            
            phone = st.text_input(
                "Phone Number (Optional)",
                placeholder="+91 9876543210",
                help="Get SMS alerts for urgent price drops"
            )
            
        with col2:
            st.markdown("**💰 Price Thresholds**")
            
            # Mock current prices
            current_flipkart = 15999
            current_amazon = 16499
            
            flipkart_target = st.number_input(
                f"Flipkart Alert Price (Current: ₹{current_flipkart:,})",
                min_value=1000,
                max_value=current_flipkart,
                value=int(current_flipkart * 0.9),
                step=100,
                help="Get notified when Flipkart price drops to this level"
            )
            
            amazon_target = st.number_input(
                f"Amazon Alert Price (Current: ₹{current_amazon:,})",
                min_value=1000, 
                max_value=current_amazon,
                value=int(current_amazon * 0.9),
                step=100,
                help="Get notified when Amazon price drops to this level"
            )
    
    # Alert preferences
    st.markdown("**🔔 Alert Preferences**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        instant_alerts = st.checkbox("⚡ Instant Alerts", value=True, 
                                   help="Get notified immediately when price drops")
        
    with col2:
        daily_summary = st.checkbox("📊 Daily Summary", value=True,
                                  help="Daily email with price changes summary")
        
    with col3:
        weekly_report = st.checkbox("📈 Weekly Report", value=False,
                                  help="Weekly trend analysis and recommendations")
    
    # Advanced alert options
    with st.expander("🎯 Advanced Alert Options"):
        percentage_drop = st.slider(
            "Alert on percentage drop (%)",
            min_value=1, max_value=30, value=10,
            help="Get notified when price drops by this percentage"
        )
        
        competitor_alert = st.checkbox(
            "Cross-platform comparison alerts",
            value=True,
            help="Alert when one platform becomes significantly cheaper"
        )
        
        stock_alert = st.checkbox(
            "Stock availability alerts", 
            value=True,
            help="Alert when out-of-stock items come back in stock"
        )
    
    # Validate email format
    def is_valid_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    # Setup alert button
    if st.button("🚀 Setup Price Alerts", key="setup_alerts", use_container_width=True):
        if email and is_valid_email(email):
            # Mock alert setup process
            with st.spinner("Setting up your price alerts..."):
                import time
                time.sleep(2)  # Simulate setup time
                
                # Show success message
                st.success("✅ Price alerts successfully configured!")
                
                # Display alert summary
                st.markdown("### 📋 Alert Summary")
                
                alert_data = {
                    "Platform": ["Flipkart", "Amazon"],
                    "Current Price": [f"₹{current_flipkart:,}", f"₹{current_amazon:,}"],
                    "Alert Price": [f"₹{flipkart_target:,}", f"₹{amazon_target:,}"],
                    "Discount Needed": [
                        f"{((current_flipkart - flipkart_target) / current_flipkart * 100):.1f}%",
                        f"{((current_amazon - amazon_target) / current_amazon * 100):.1f}%"
                    ],
                    "Status": ["🟢 Active", "🟢 Active"]
                }
                
                alert_df = pd.DataFrame(alert_data)
                st.table(alert_df)
                
                # Show mock notification preview
                st.markdown("### 📧 Email Preview")
                st.info(f"""
**Subject:** 🔥 Price Drop Alert - Your watched item is now cheaper!

Hi there! 👋

Great news! The price of your watched item has dropped:

**iPhone 15 Pro Max 256GB**
🏷️ **Flipkart**: ₹{flipkart_target:,} (was ₹{current_flipkart:,}) - **SAVE ₹{current_flipkart - flipkart_target:,}!**

🛒 **[Buy Now on Flipkart](https://flipkart.com/example)**

This alert was triggered because the price dropped below your target of ₹{flipkart_target:,}.

---
*You're receiving this because you set up price alerts on CompareIT. Unsubscribe anytime.*
                """)
                
        else:
            st.error("Please enter a valid email address")
    
    # Show existing alerts (mock)
    if email and is_valid_email(email):
        st.markdown("### 📊 Your Active Alerts")
        
        # Mock existing alerts data
        existing_alerts = pd.DataFrame({
            "Product": [
                "iPhone 15 Pro Max 256GB",
                "Samsung Galaxy S24 Ultra", 
                "MacBook Air M3 13-inch"
            ],
            "Platform": ["Both", "Flipkart", "Amazon"],
            "Target Price": ["₹15,999 / ₹16,499", "₹89,999", "₹1,14,900"],
            "Current Price": ["₹15,999 / ₹16,499", "₹95,999", "₹1,19,900"], 
            "Status": ["🟢 Active", "🟡 Monitoring", "🟡 Monitoring"],
            "Actions": ["Edit | Delete", "Edit | Delete", "Edit | Delete"]
        })
        
        st.dataframe(existing_alerts, use_container_width=True)
        
        # Alert statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Active Alerts", "3")
        with col2:
            st.metric("Alerts Triggered", "12")
        with col3:
            st.metric("Money Saved", "₹8,450")
        with col4:
            st.metric("Success Rate", "89%")


# Example usage in your main app:
if __name__ == "__main__":
    st.set_page_config(page_title="Price Features Demo", layout="wide")
    
    # Add the CSS from your main app here for styling
    st.markdown("""
    <style>
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
    </style>
    """, unsafe_allow_html=True)
    
    # Demo the features
    tab1, tab2 = st.tabs(["🔮 Price Prediction", "📧 Email Alerts"])
    
    with tab1:
        show_price_prediction_feature()
    
    with tab2:
        show_email_alert_feature()