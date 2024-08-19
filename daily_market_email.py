import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time
from market_analysis import analyze_market
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Email configuration
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

def send_market_analysis_email():
    logging.info("Starting market analysis...")
    analysis_result = analyze_market()
    
    if analysis_result['status'] == 'success':
        market_analysis = analysis_result['market_analysis']
        
        # Create the email content
        message = MIMEMultipart("alternative")
        message["Subject"] = "Daily Market Analysis"
        message["From"] = SENDER_EMAIL
        message["To"] = RECEIVER_EMAIL

        # Create the HTML version of the email
        html = f"""
        <html>
        <body>
            <h1>Daily Market Analysis</h1>
            <div style="white-space: pre-wrap; font-family: monospace; background-color: #f8f8f8; padding: 15px; border-radius: 5px;">
            {market_analysis}
            </div>
        </body>
        </html>
        """

        # Turn these into plain/html MIMEText objects
        part = MIMEText(html, "html")

        # Add HTML part to MIMEMultipart message
        message.attach(part)

        # Create secure connection with server and send email
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.ehlo()  # Can be omitted
                server.starttls(context=context)
                server.ehlo()  # Can be omitted
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            logging.info("Email sent successfully")
        except Exception as e:
            logging.error(f"Error sending email: {str(e)}")
    else:
        logging.error(f"Market analysis failed: {analysis_result.get('error', 'Unknown error')}")

def run_daily_task():
    logging.info("Running daily market analysis task")
    send_market_analysis_email()

# Schedule the task to run every day at 8:00 AM
schedule.every().day.at("08:00").do(run_daily_task)

if __name__ == "__main__":
    logging.info("Starting daily market analysis email service")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Wait for 60 seconds before checking schedule again