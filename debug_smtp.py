import os
from dotenv import load_dotenv
import smtplib
import ssl
import socket

# Load environment variables
load_dotenv()

# Email configuration
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = os.getenv('SMTP_PORT')

print(f"Environment variables:")
print(f"SMTP_SERVER: {SMTP_SERVER}")
print(f"SMTP_PORT: {SMTP_PORT}")
print(f"SENDER_EMAIL: {SENDER_EMAIL}")
print(f"RECEIVER_EMAIL: {RECEIVER_EMAIL}")

def test_smtp_connection(server, port, use_ssl=False, timeout=10):
    print(f"\nTesting connection to {server} on port {port} {'with SSL' if use_ssl else 'without SSL'}...")
    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(server, port, context=context, timeout=timeout) as server:
                server.ehlo()
                print(f"Successfully connected to {server} on port {port} with SSL")
                try:
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    print("Login successful")
                except smtplib.SMTPAuthenticationError:
                    print("Login failed: Authentication error")
                except Exception as e:
                    print(f"Login failed: {str(e)}")
        else:
            with smtplib.SMTP(server, port, timeout=timeout) as server:
                server.ehlo()
                print(f"Successfully connected to {server} on port {port}")
                if port != 25:  # Port 25 doesn't typically use TLS
                    server.starttls()
                    print("Started TLS")
                try:
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    print("Login successful")
                except smtplib.SMTPAuthenticationError:
                    print("Login failed: Authentication error")
                except Exception as e:
                    print(f"Login failed: {str(e)}")
        return True
    except socket.timeout:
        print(f"Connection to {server} on port {port} timed out")
    except ConnectionRefusedError:
        print(f"Connection to {server} on port {port} was refused")
    except ssl.SSLError as e:
        print(f"SSL error when connecting to {server} on port {port}: {str(e)}")
    except Exception as e:
        print(f"Error connecting to {server} on port {port}: {str(e)}")
    return False

# Test connections
test_smtp_connection(SMTP_SERVER, 587)
test_smtp_connection(SMTP_SERVER, 465, use_ssl=True)
test_smtp_connection(SMTP_SERVER, int(SMTP_PORT), use_ssl=(SMTP_PORT == '465'))

print("\nIf all connections failed, please check your firewall settings and internet connection.")
print("If SSL connection succeeded but non-SSL failed, update your code to use SSL (port 465).")
print("If you're using Gmail, ensure that 'Less secure app access' is turned on or use an App Password.")