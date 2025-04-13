import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def test_email_connection():
    # SMTP Settings
    smtp_server = 'mail.smtp2go.com'
    smtp_port = 2525
    smtp_username = 'Cmpro@cmpro'
    smtp_password = 'w7n0w0IBE5QYvpHP'
    sender_email = 'Cmpro@gmail.com'  # Using a Gmail domain which might be pre-verified in the account
    recipient_email = 'test@example.com'  # Replace with a real email for testing
    
    # Create message
    subject = 'Test Email from Construction Timesheet System'
    body = 'This is a test email to verify SMTP configuration.'
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        print(f"Connecting to {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        print("Starting TLS...")
        server.starttls()  # Secure the connection
        
        print(f"Logging in as {smtp_username}...")
        server.login(smtp_username, smtp_password)
        
        print(f"Sending email to {recipient_email}...")
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # Add specific error handling
        if "authentication failed" in str(e).lower():
            print("Authentication failed. Please check SMTP_USERNAME and SMTP_PASSWORD.")
        elif "connection refused" in str(e).lower():
            print(f"Connection to {smtp_server}:{smtp_port} refused. Check SMTP_SERVER and SMTP_PORT.")
        elif "timeout" in str(e).lower():
            print(f"Connection to {smtp_server}:{smtp_port} timed out. Check network settings.")
        return False

if __name__ == "__main__":
    test_email_connection()