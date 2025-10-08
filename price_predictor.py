import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import sqlite3
import datetime
import logging
import random
from textblob import TextBlob

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PricePredictionDatabase:
    def __init__(self, db_name="price_history.db"):
        self.db_name = db_name
        self.create_tables()
    
    def create_tables(self):
        """Create tables for storing price history and predictions"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Create price history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                price REAL NOT NULL,
                date TEXT NOT NULL,
                search_term TEXT,
                product_url TEXT,
                UNIQUE(product_name, platform, date)
            )
        """)
        
        # Create predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                current_price REAL NOT NULL,
                predicted_price REAL NOT NULL,
                prediction_date TEXT NOT NULL,
                target_date TEXT NOT NULL,
                confidence_score REAL,
                model_used TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_price_history(self, product_name, platform, price, search_term=None, product_url=None):
        """Add a new price point to history"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO price_history 
                (product_name, platform, price, date, search_term, product_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_name, platform, price, date_str, search_term, product_url))
            
            conn.commit()
            logger.info(f"Added price history: {product_name} - {platform} - ₹{price}")
        except Exception as e:
            logger.error(f"Error adding price history: {e}")
        finally:
            conn.close()
    
    def get_price_history(self, product_name=None, platform=None, days=30):
        """Retrieve price history for analysis"""
        conn = sqlite3.connect(self.db_name)
        
        query = """
            SELECT product_name, platform, price, date 
            FROM price_history 
            WHERE date >= datetime('now', '-{} days')
        """.format(days)
        
        conditions = []
        params = []
        
        if product_name:
            conditions.append("product_name LIKE ?")
            params.append(f"%{product_name}%")
        
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY date ASC"
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df
        except Exception as e:
            logger.error(f"Error retrieving price history: {e}")
            conn.close()
            return pd.DataFrame()

class PricePredictor:
    def __init__(self, db_name="price_history.db"):
        self.db = PricePredictionDatabase(db_name)
        self.models = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'linear_regression': LinearRegression()
        }
        self.scaler = StandardScaler()
    
    def generate_synthetic_data(self, product_name, current_price, platform, days=90):
        """Generate realistic synthetic historical data for new products"""
        logger.info(f"Generating realistic synthetic data for {product_name}")
        
        # Create realistic price variations
        base_price = current_price
        dates = pd.date_range(end=datetime.datetime.now(), periods=days, freq='D')
        
        # Generate prices with realistic patterns
        prices = []
        for i, date in enumerate(dates):
            # Much smaller variations - electronics typically don't have huge price swings
            # Add seasonal trends (very small - 1-2% max)
            seasonal_factor = 1 + 0.01 * np.sin(2 * np.pi * i / 365)  # 1% yearly cycle
            
            # Add weekly patterns (very slight price drops on weekends)
            weekly_factor = 0.995 if date.weekday() >= 5 else 1.0  # 0.5% weekend discount
            
            # Add much smaller random noise (0.5% standard deviation instead of 2%)
            noise = np.random.normal(0, 0.005)  # 0.5% standard deviation
            
            # Add very gradual trend (small decrease over time for electronics)
            # 0.01% daily decrease instead of 0.1%
            trend = -0.0001 * i if platform.lower() == 'amazon' else -0.00005 * i
            
            price = base_price * (1 + trend) * seasonal_factor * weekly_factor * (1 + noise)
            
            # Don't allow prices to go below 85% of original (instead of 70%)
            # Don't allow prices to go above 115% of original
            price = max(price, base_price * 0.85)
            price = min(price, base_price * 1.15)
            prices.append(price)
        
        # Store synthetic data
        for date, price in zip(dates, prices):
            date_str = date.strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(self.db.db_name)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO price_history 
                    (product_name, platform, price, date, search_term)
                    VALUES (?, ?, ?, ?, ?)
                """, (product_name, platform, price, date_str, "synthetic_data"))
                conn.commit()
            except:
                pass
            finally:
                conn.close()
        
        return pd.DataFrame({
            'date': dates,
            'price': prices,
            'product_name': product_name,
            'platform': platform
        })
    


    def create_features(self, df):
        """Create features for machine learning model"""
        if df.empty:
            return pd.DataFrame()
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Create time-based features
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['days_since_start'] = (df['date'] - df['date'].min()).dt.days
        
        # Create price-based features
        df['price_lag_1'] = df['price'].shift(1)
        df['price_lag_7'] = df['price'].shift(7)
        df['price_ma_7'] = df['price'].rolling(window=7, min_periods=1).mean()
        df['price_ma_14'] = df['price'].rolling(window=14, min_periods=1).mean()
        df['price_std_7'] = df['price'].rolling(window=7, min_periods=1).std()
        
        # Fill NaN values
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        return df
    
    def train_model(self, product_name, platform):
        """Train prediction model for a specific product"""
        # Get historical data
        df = self.db.get_price_history(product_name, platform, days=90)
        
        # If no data, generate synthetic data
        if df.empty or len(df) < 10:
            logger.info(f"Insufficient data for {product_name}. Generating synthetic data.")
            # We need current price - let's estimate it
            estimated_price = random.uniform(1000, 50000)  # Random price for demo
            df = self.generate_synthetic_data(product_name, estimated_price, platform)
        
        # Create features
        df_features = self.create_features(df)
        
        if df_features.empty or len(df_features) < 5:
            logger.warning(f"Insufficient data for training model for {product_name}")
            return None, 0
        
        # Prepare training data
        feature_columns = [
            'day_of_week', 'day_of_month', 'month', 'days_since_start',
            'price_lag_1', 'price_lag_7', 'price_ma_7', 'price_ma_14', 'price_std_7'
        ]
        
        # Ensure we have all required columns
        for col in feature_columns:
            if col not in df_features.columns:
                df_features[col] = df_features['price'].iloc[0]  # Use current price as fallback
        
        X = df_features[feature_columns].values
        y = df_features['price'].values
        
        # Split into train/test
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        if len(X_train) < 3:
            logger.warning("Insufficient training data")
            return None, 0
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test) if len(X_test) > 0 else None
        
        # Train models and select best one
        best_model = None
        best_score = float('inf')
        best_model_name = None
        
        for name, model in self.models.items():
            try:
                model.fit(X_train_scaled, y_train)
                
                if X_test_scaled is not None and len(X_test_scaled) > 0:
                    predictions = model.predict(X_test_scaled)
                    score = mean_absolute_error(y_test, predictions)
                else:
                    # Use training error if no test data
                    predictions = model.predict(X_train_scaled)
                    score = mean_absolute_error(y_train, predictions)
                
                if score < best_score:
                    best_score = score
                    best_model = model
                    best_model_name = name
                    
            except Exception as e:
                logger.error(f"Error training {name}: {e}")
                continue
        
        confidence = max(0, 1 - (best_score / df['price'].mean())) if best_model else 0
        logger.info(f"Best model for {product_name}: {best_model_name} (MAE: {best_score:.2f}, Confidence: {confidence:.2f})")
        
        return best_model, confidence
    
    def predict_future_price(self, product_name, platform, current_price, days_ahead=30):
        """Predict future price for a product with realistic constraints"""
        # First, add current price to history
        self.db.add_price_history(product_name, platform, current_price)
        
        # Train model
        model, confidence = self.train_model(product_name, platform)
        
        if model is None:
            logger.warning("Could not train model, using simple trend prediction")
            return self.simple_trend_prediction(product_name, platform, current_price, days_ahead)
        
        # Get recent data for prediction
        df = self.db.get_price_history(product_name, platform, days=90)
        df_features = self.create_features(df)
        
        if df_features.empty:
            return self.simple_trend_prediction(product_name, platform, current_price, days_ahead)
        
        # Create future dates
        future_dates = pd.date_range(
            start=datetime.datetime.now() + datetime.timedelta(days=1),
            periods=days_ahead,
            freq='D'
        )
        
        predictions = []
        last_row = df_features.iloc[-1].copy()
        
        feature_columns = [
            'day_of_week', 'day_of_month', 'month', 'days_since_start',
            'price_lag_1', 'price_lag_7', 'price_ma_7', 'price_ma_14', 'price_std_7'
        ]
        
        for i, future_date in enumerate(future_dates):
            # Update time features
            last_row['day_of_week'] = future_date.dayofweek
            last_row['day_of_month'] = future_date.day
            last_row['month'] = future_date.month
            last_row['days_since_start'] = last_row['days_since_start'] + i + 1
            
            # Prepare features
            X_future = last_row[feature_columns].values.reshape(1, -1)
            X_future_scaled = self.scaler.transform(X_future)
            
            # Make prediction
            predicted_price = model.predict(X_future_scaled)[0]
            
            # Apply realistic constraints to predictions
            # Don't predict more than 10% change from current price over 30 days
            max_change_percent = 0.10 * (i + 1) / days_ahead  # Gradual change over time
            min_price = current_price * (1 - max_change_percent)
            max_price = current_price * (1 + max_change_percent)
            
            predicted_price = max(min_price, min(predicted_price, max_price))
            
            predictions.append({
                'date': future_date,
                'predicted_price': predicted_price,
                'confidence': confidence
            })
            
            # Update lagged features for next prediction
            last_row['price_lag_1'] = predicted_price
        
        return predictions

    def simple_trend_prediction(self, product_name, platform, current_price, days_ahead=30):
        """Simple trend-based prediction as fallback with realistic constraints"""
        logger.info("Using simple trend prediction with realistic constraints")
        
        # Get any available data
        df = self.db.get_price_history(product_name, platform, days=30)
        
        if len(df) > 1:
            # Calculate trend
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Simple linear trend
            days = (df['date'].max() - df['date'].min()).days
            price_change = df['price'].iloc[-1] - df['price'].iloc[0]
            daily_change = price_change / days if days > 0 else 0
            
            # Limit daily change to be realistic (max 0.1% per day)
            max_daily_change = current_price * 0.001  # 0.1% daily change
            daily_change = max(min(daily_change, max_daily_change), -max_daily_change)
        else:
            # No historical data, assume very slight downward trend
            daily_change = -current_price * 0.0005  # 0.05% daily decrease
        
        # Generate predictions
        predictions = []
        future_dates = pd.date_range(
            start=datetime.datetime.now() + datetime.timedelta(days=1),
            periods=days_ahead,
            freq='D'
        )
        
        for i, future_date in enumerate(future_dates):
            predicted_price = current_price + (daily_change * (i + 1))
            
            # Apply realistic bounds - maximum 8% change over 30 days
            max_change = current_price * 0.08
            predicted_price = max(current_price - max_change, 
                                min(predicted_price, current_price + max_change))
            
            predictions.append({
                'date': future_date,
                'predicted_price': predicted_price,
                'confidence': 0.4  # Medium confidence for simple trend
            })
        
        return predictions
    
    def get_price_insights(self, predictions, current_price):
        """Generate insights from predictions"""
        if not predictions:
            return "No predictions available"
        
        # Calculate trends
        future_price = predictions[-1]['predicted_price']
        price_change = future_price - current_price
        price_change_percent = (price_change / current_price) * 100
        
        # Find best time to buy (lowest predicted price)
        best_day = min(predictions, key=lambda x: x['predicted_price'])
        best_price = best_day['predicted_price']
        best_date = best_day['date'].strftime('%Y-%m-%d')
        
        # Calculate potential savings
        savings = current_price - best_price
        savings_percent = (savings / current_price) * 100
        
        insights = {
            'trend': 'increasing' if price_change > 0 else 'decreasing',
            'price_change': price_change,
            'price_change_percent': price_change_percent,
            'best_buy_date': best_date,
            'best_buy_price': best_price,
            'potential_savings': savings,
            'potential_savings_percent': savings_percent,
            'confidence': np.mean([p['confidence'] for p in predictions])
        }
        
        return insights