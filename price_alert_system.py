import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import schedule
import time
import threading

class PriceAlertSystem:
    def __init__(self, db_name="price_alerts.db"):
        self.db_name = db_name
        self.create_tables()
        
    def create_tables(self):
        """Create tables for price alerts"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Table for user alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                current_price REAL NOT NULL,
                target_price REAL,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Table for price history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                price REAL NOT NULL,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alert_id) REFERENCES price_alerts(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_price_alert(self, user_email, product_name, product_url, platform, current_price, target_price=None):
        """Add a new price alert for a user"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO price_alerts 
            (user_email, product_name, product_url, platform, current_price, target_price, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_email, product_name, product_url, platform, current_price, target_price, datetime.now()))
        
        alert_id = cursor.lastrowid
        
        # Add to price history
        cursor.execute("""
            INSERT INTO price_history (alert_id, price)
            VALUES (?, ?)
        """, (alert_id, current_price))
        
        conn.commit()
        conn.close()
        
        return alert_id
    
    def get_user_alerts(self, user_email):
        """Get all active alerts for a user"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, product_name, platform, current_price, target_price, product_url
            FROM price_alerts
            WHERE user_email = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (user_email,))
        
        alerts = cursor.fetchall()
        conn.close()
        
        return alerts
    
    def update_price(self, alert_id, new_price):
        """Update the price for an alert"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Get old price
        cursor.execute("SELECT current_price FROM price_alerts WHERE id = ?", (alert_id,))
        old_price = cursor.fetchone()[0]
        
        # Update alert
        cursor.execute("""
            UPDATE price_alerts
            SET current_price = ?, last_checked = ?
            WHERE id = ?
        """, (new_price, datetime.now(), alert_id))
        
        # Add to history
        cursor.execute("""
            INSERT INTO price_history (alert_id, price)
            VALUES (?, ?)
        """, (alert_id, new_price))
        
        conn.commit()
        conn.close()
        
        return old_price, new_price
    
    def delete_alert(self, alert_id):
        """Deactivate an alert"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE price_alerts
            SET is_active = 0
            WHERE id = ?
        """, (alert_id,))
        
        conn.commit()
        conn.close()
    
    def send_email_alert(self, to_email, product_name, platform, old_price, new_price, product_url, smtp_config):
        """Send email notification for price drop"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Price Drop Alert: {product_name}'
            msg['From'] = smtp_config['from_email']
            msg['To'] = to_email
            
            # Calculate savings
            savings = old_price - new_price
            savings_percent = (savings / old_price) * 100
            
            # Create HTML email
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="background: linear-gradient(90deg, #2874F0 0%, #FF9900 100%); color: white; padding: 20px; border-radius: 10px;">
                  <h1>Price Drop Alert!</h1>
                </div>
                
                <div style="margin: 20px 0; padding: 20px; border: 2px solid #4CAF50; border-radius: 10px; background-color: #E8F5E9;">
                  <h2 style="color: #2E7D32;">Great News! The price has dropped!</h2>
                  
                  <p><strong>Product:</strong> {product_name}</p>
                  <p><strong>Platform:</strong> {platform}</p>
                  
                  <div style="margin: 15px 0;">
                    <p style="text-decoration: line-through; color: #999;">Old Price: ₹{old_price:,.2f}</p>
                    <p style="font-size: 24px; color: #4CAF50; font-weight: bold;">New Price: ₹{new_price:,.2f}</p>
                  </div>
                  
                  <div style="background-color: #FFF3E0; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p style="color: #FF6F00; font-size: 18px; font-weight: bold; margin: 0;">
                      You Save: ₹{savings:,.2f} ({savings_percent:.1f}%)
                    </p>
                  </div>
                  
                  <a href="{product_url}" 
                     style="display: inline-block; background-color: #4CAF50; color: white; padding: 15px 30px; 
                            text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 15px;">
                    Buy Now
                  </a>
                </div>
                
                <p style="color: #666; font-size: 12px; margin-top: 20px;">
                  This is an automated alert from CompareIT. 
                  To manage your alerts, log in to your account.
                </p>
              </body>
            </html>
            """
            
            # Attach HTML content
            html_part = MIMEText(html, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port']) as server:
                server.starttls()
                server.login(smtp_config['from_email'], smtp_config['password'])
                server.send_message(msg)
            
            print(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
    
    def check_price_drops(self, smtp_config):
        """Check all active alerts for price drops"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_email, product_name, product_url, platform, current_price, target_price
            FROM price_alerts
            WHERE is_active = 1
        """)
        
        alerts = cursor.fetchall()
        conn.close()
        
        for alert in alerts:
            alert_id, user_email, product_name, product_url, platform, current_price, target_price = alert
            
            # In a real implementation, you would scrape the current price here
            # For now, we'll simulate a price check
            # new_price = scrape_current_price(product_url, platform)
            
            # Simulated: randomly decide if price dropped (for testing)
            import random
            if random.random() < 0.1:  # 10% chance of price drop
                new_price = current_price * 0.9  # 10% discount
                
                # Check if price dropped below target or just dropped in general
                should_alert = False
                if target_price:
                    if new_price <= target_price:
                        should_alert = True
                elif new_price < current_price:
                    should_alert = True
                
                if should_alert:
                    self.send_email_alert(
                        user_email, product_name, platform, 
                        current_price, new_price, product_url, smtp_config
                    )
                    self.update_price(alert_id, new_price)


# Configuration for SMTP (you need to fill these)
SMTP_CONFIG = {
    'smtp_server': 'smtp.gmail.com',  # For Gmail
    'smtp_port': 587,
    'from_email': 'your-email@gmail.com',  # Your email
    'password': 'your-app-password'  # App password (not regular password)
}

# Usage example
if __name__ == "__main__":
    alert_system = PriceAlertSystem()
    
    # Example: Add a price alert
    alert_system.add_price_alert(
        user_email="user@example.com",
        product_name="Samsung Galaxy S24",
        product_url="https://www.amazon.in/...",
        platform="Amazon",
        current_price=75000.0,
        target_price=70000.0  # Optional: alert only if price drops below this
    )
    
    print("Price alert system initialized!")