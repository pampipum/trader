import os
from dotenv import load_dotenv
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from market_analysis import analyze_market
import logging
import re
import markdown2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Email configuration
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

def format_asset_table(asset_data):
    table_html = """
    <table>
        <tr>
            <th>Asset</th>
            <th>1-Day % Change</th>
            <th>5-Day % Change</th>
            <th>1-Month % Change</th>
        </tr>
    """
    for asset, changes in asset_data.items():
        table_html += f"""
        <tr>
            <td>{asset}</td>
            <td class="{'positive' if float(changes['1D'].rstrip('%')) >= 0 else 'negative'}">{changes['1D']}</td>
            <td class="{'positive' if float(changes['5D'].rstrip('%')) >= 0 else 'negative'}">{changes['5D']}</td>
            <td class="{'positive' if float(changes['1M'].rstrip('%')) >= 0 else 'negative'}">{changes['1M']}</td>
        </tr>
        """
    table_html += "</table>"
    return table_html

def convert_markdown_to_html(markdown_content):
    # Convert Markdown to HTML
    html_content = markdown2.markdown(markdown_content)
    
    # Replace the asset performance table
    asset_table_match = re.search(r'\| Asset \| 1-Day % Change \| 5-Day % Change \| 1-Month % Change \|([\s\S]*?)\n\n', markdown_content)
    if asset_table_match:
        asset_data = {}
        for line in asset_table_match.group(1).strip().split('\n'):
            parts = line.split('|')
            if len(parts) == 6:
                asset = parts[1].strip()
                asset_data[asset] = {
                    '1D': parts[2].strip(),
                    '5D': parts[3].strip(),
                    '1M': parts[4].strip()
                }
        asset_table_html = format_asset_table(asset_data)
        html_content = html_content.replace(asset_table_match.group(0), asset_table_html)
    
    return html_content

def send_market_analysis_email():
    logging.info("Starting market analysis...")
    analysis_result = analyze_market()
    
    if analysis_result['status'] == 'success':
        market_analysis = analysis_result['market_analysis']
        
        # Convert Markdown to HTML
        html_content = convert_markdown_to_html(market_analysis)
        
        # Read the email template
        with open('email_template.html', 'r') as template_file:
            email_template = template_file.read()
        
        # Insert the HTML content into the template
        email_html = email_template.replace('{{REPORT_CONTENT}}', html_content)
        
        # Create the email content
        message = MIMEMultipart("alternative")
        message["Subject"] = "Daily Market Analysis (Test)"
        message["From"] = SENDER_EMAIL
        message["To"] = RECEIVER_EMAIL

        # Add HTML part to MIMEMultipart message
        message.attach(MIMEText(email_html, "html"))

        # Create secure connection with server and send email
        context = ssl.create_default_context()
        try:
            logging.info(f"Attempting to connect to {SMTP_SERVER} on port {SMTP_PORT}...")
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                logging.info("SSL connection established. Attempting to login...")
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                logging.info("Login successful. Sending email...")
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            logging.info("Market analysis email sent successfully")
        except Exception as e:
            logging.error(f"Error sending email: {str(e)}")
    else:
        logging.error(f"Market analysis failed: {analysis_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    send_market_analysis_email()