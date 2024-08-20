import os
from dotenv import load_dotenv
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from market_analysis import analyze_market
import logging
import re

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

def format_analysis_as_html(analysis_text):
    sections = analysis_text.split('\n\n')
    
    html_content = "<div class='content'>"
    
    for section in sections:
        if section.strip():
            lines = section.split('\n')
            title = lines[0].strip()
            content = '\n'.join(lines[1:])
            
            if title == "Elite Market Analysis Daily Briefing":
                html_content += f"<h1>{title}</h1>"
            elif title.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.')):
                html_content += f"<h2>{title}</h2>"
            else:
                html_content += f"<h3>{title}</h3>"
            
            if "The table below" in content:
                # Handle the table
                table_content = content.split('The table below')[1].strip()
                html_content += "<p>The table below" + table_content.split('\n')[0] + "</p>"
                html_content += format_table(table_content)
            elif content.startswith('- '):
                # Handle bullet points
                html_content += "<ul class='bullet-points'>"
                for point in content.split('\n'):
                    if point.strip().startswith('- '):
                        html_content += f"<li>{point.strip('- ')}</li>"
                html_content += "</ul>"
            elif "Setup Quality Score:" in content:
                # Handle trading opportunities
                html_content += format_trading_opportunities(content)
            else:
                html_content += f"<p>{content}</p>"
    
    html_content += "</div>"
    return html_content

def format_table(table_content):
    # Extract table rows
    rows = re.findall(r'\|(.*?)\|', table_content)
    
    html_table = "<table class='asset-performance'><thead><tr>"
    headers = rows[0].split('|')
    for header in headers:
        html_table += f"<th>{header.strip()}</th>"
    html_table += "</tr></thead><tbody>"
    
    for row in rows[1:]:
        html_table += "<tr>"
        cells = row.split('|')
        for i, cell in enumerate(cells):
            if i == 0:  # Asset name
                html_table += f"<td>{cell.strip()}</td>"
            else:  # Percentage changes
                html_table += f"<td class='number'>{cell.strip()}</td>"
        html_table += "</tr>"
    
    html_table += "</tbody></table>"
    return html_table

def format_trading_opportunities(content):
    opportunities = content.split('\n\n')
    html_opportunities = "<div class='trading-opportunities'>"
    for opportunity in opportunities:
        if opportunity.strip():
            lines = opportunity.split('\n')
            title = lines[0].strip()
            details = '\n'.join(lines[1:])
            html_opportunities += f"""
            <div class='opportunity-card'>
                <h4>{title}</h4>
                <p>{details}</p>
            </div>
            """
    html_opportunities += "</div>"
    return html_opportunities

def send_market_analysis_email():
    logging.info("Starting market analysis...")
    analysis_result = analyze_market()
    
    if analysis_result['status'] == 'success':
        market_analysis = analysis_result['market_analysis']
        
        # Format the analysis as HTML
        formatted_content = format_analysis_as_html(market_analysis)
        
        # Create the email content
        message = MIMEMultipart("alternative")
        message["Subject"] = "Daily Market Analysis"
        message["From"] = SENDER_EMAIL
        message["To"] = RECEIVER_EMAIL

        # Create the HTML version of the email
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #000000;
                    font-size: 18px;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .content {{
                    background-color: #ffffff;
                    padding: 20px;
                    border-radius: 5px;
                }}
                h1 {{
                    font-size: 24px;
                    font-weight: bold;
                    border-bottom: 2px solid #000000;
                    padding-bottom: 10px;
                }}
                h2 {{
                    font-size: 20px;
                    font-weight: bold;
                    margin-top: 30px;
                }}
                h3 {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-top: 20px;
                }}
                h4 {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-top: 15px;
                    margin-bottom: 5px;
                }}
                p, li {{
                    font-size: 18px;
                    font-weight: normal;
                    margin-bottom: 10px;
                }}
                ul.bullet-points {{
                    padding-left: 20px;
                    margin-bottom: 15px;
                }}
                .bullet-points li {{
                    margin-bottom: 5px;
                }}
                .asset-performance {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                .asset-performance th, .asset-performance td {{
                    border: 1px solid #000000;
                    padding: 8px;
                    text-align: left;
                }}
                .asset-performance th {{
                    font-weight: bold;
                    background-color: #f2f2f2;
                }}
                .number {{
                    text-align: right;
                }}
                .trading-opportunities {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-top: 15px;
                }}
                .opportunity-card {{
                    flex: 1 1 300px;
                    border: 1px solid #000000;
                    border-radius: 5px;
                    padding: 15px;
                    background-color: #f9f9f9;
                }}
            </style>
        </head>
        <body>
            {formatted_content}
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