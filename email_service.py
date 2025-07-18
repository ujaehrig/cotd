#!/usr/bin/env python3

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import os
from typing import Optional
from dotenv import load_dotenv

# Configure logging (will be configured by main app)
# logging.basicConfig(level=logging.INFO)

class EmailService:
    """Email service for sending password reset emails."""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Email configuration from environment variables
        self.smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@vacation-manager.local')
        self.from_name = os.getenv('FROM_NAME', 'Vacation Manager')
        
        # For development/testing - use file-based email
        self.use_file_email = os.getenv('USE_FILE_EMAIL', 'true').lower() == 'true'
        self.email_file_path = Path(__file__).parent / "sent_emails"
        
        if self.use_file_email:
            self.email_file_path.mkdir(exist_ok=True)
    
    def send_password_reset_email(self, to_email: str, new_password: str) -> bool:
        """Send password reset email to user."""
        try:
            subject = "Password Reset - Vacation Manager"
            
            # Create email content
            html_content = f"""
            <html>
            <head></head>
            <body>
                <h2>Password Reset - Vacation Manager</h2>
                <p>Hello,</p>
                <p>Your password has been reset as requested. Here are your new login credentials:</p>
                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Email:</strong> {to_email}</p>
                    <p><strong>New Password:</strong> <code>{new_password}</code></p>
                </div>
                <p><strong>Important Security Notice:</strong></p>
                <ul>
                    <li>You will be required to change this password immediately after logging in</li>
                    <li>Please log in and change your password as soon as possible</li>
                    <li>This temporary password is only valid for your next login</li>
                    <li>Do not share this password with anyone</li>
                </ul>
                <p>To log in:</p>
                <ol>
                    <li>Go to the vacation management system</li>
                    <li>Use your email and the new password above</li>
                    <li>You will be prompted to change your password immediately</li>
                </ol>
                <p>If you did not request this password reset, please contact your system administrator immediately.</p>
                <p>Best regards,<br>Vacation Manager System</p>
            </body>
            </html>
            """
            
            text_content = f"""
            Password Reset - Vacation Manager
            
            Hello,
            
            Your password has been reset as requested. Here are your new login credentials:
            
            Email: {to_email}
            New Password: {new_password}
            
            IMPORTANT SECURITY NOTICE:
            - You will be required to change this password immediately after logging in
            - Please log in and change your password as soon as possible
            - This temporary password is only valid for your next login
            - Do not share this password with anyone
            
            To log in:
            1. Go to the vacation management system
            2. Use your email and the new password above
            3. You will be prompted to change your password immediately
            
            If you did not request this password reset, please contact your system administrator immediately.
            
            Best regards,
            Vacation Manager System
            """
            
            if self.use_file_email:
                # Development mode - save to file
                return self._save_email_to_file(to_email, subject, html_content, text_content)
            else:
                # Production mode - send actual email
                return self._send_smtp_email(to_email, subject, html_content, text_content)
                
        except Exception as e:
            logging.error(f"Error sending password reset email: {e}")
            return False
    
    def _save_email_to_file(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        """Save email to file for development/testing."""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"password_reset_{to_email.replace('@', '_').replace('.', '_')}_{timestamp}.txt"
            filepath = self.email_file_path / filename
            
            with open(filepath, 'w') as f:
                f.write(f"TO: {to_email}\n")
                f.write(f"FROM: {self.from_name} <{self.from_email}>\n")
                f.write(f"SUBJECT: {subject}\n")
                f.write(f"DATE: {datetime.datetime.now()}\n")
                f.write("-" * 50 + "\n")
                f.write(text_content)
                f.write("\n" + "=" * 50 + "\n")
                f.write("HTML VERSION:\n")
                f.write(html_content)
            
            logging.info(f"Password reset email saved to file: {filepath}")
            print(f"📧 Password reset email saved to: {filepath}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving email to file: {e}")
            return False
    
    def _send_smtp_email(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Create text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                server.send_message(msg)
            
            logging.info(f"Password reset email sent to: {to_email}")
            return True
            
        except Exception as e:
            logging.error(f"Error sending SMTP email: {e}")
            return False
    
    def test_email_config(self) -> bool:
        """Test email configuration."""
        try:
            if self.use_file_email:
                print("✅ Email service configured for file-based delivery (development mode)")
                print(f"📁 Emails will be saved to: {self.email_file_path}")
                return True
            else:
                print("✅ Email service configured for SMTP delivery")
                print(f"📧 SMTP Server: {self.smtp_server}:{self.smtp_port}")
                print(f"📧 From: {self.from_name} <{self.from_email}>")
                
                # Test SMTP connection
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.smtp_use_tls:
                        server.starttls()
                    
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                
                print("✅ SMTP connection successful")
                return True
                
        except Exception as e:
            print(f"❌ Email configuration test failed: {e}")
            return False

if __name__ == "__main__":
    # Test email service
    email_service = EmailService()
    email_service.test_email_config()
    
    # Test sending an email
    test_email = "test@example.com"
    test_password = "TestPassword123!"
    
    print(f"\n🧪 Testing password reset email to: {test_email}")
    success = email_service.send_password_reset_email(test_email, test_password)
    
    if success:
        print("✅ Test email sent successfully")
    else:
        print("❌ Test email failed")