#!/usr/bin/env python3

import os
from dotenv import load_dotenv

def test_env_config():
    """Test that .env file is properly loaded and configuration is working."""
    
    # Load environment variables from .env file
    load_dotenv()
    
    print("🧪 Testing .env file configuration")
    print("=" * 50)
    
    # Test Flask configuration
    print("\n📱 Flask Configuration:")
    print(f"  SECRET_KEY: {'✅ Set' if os.getenv('SECRET_KEY') else '❌ Not set'}")
    print(f"  FLASK_ENV: {os.getenv('FLASK_ENV', 'Not set')}")
    print(f"  FLASK_DEBUG: {os.getenv('FLASK_DEBUG', 'Not set')}")
    
    # Test Email configuration
    print("\n📧 Email Configuration:")
    print(f"  USE_FILE_EMAIL: {os.getenv('USE_FILE_EMAIL', 'Not set')}")
    print(f"  SMTP_SERVER: {os.getenv('SMTP_SERVER', 'Not set')}")
    print(f"  SMTP_PORT: {os.getenv('SMTP_PORT', 'Not set')}")
    print(f"  FROM_EMAIL: {os.getenv('FROM_EMAIL', 'Not set')}")
    print(f"  FROM_NAME: {os.getenv('FROM_NAME', 'Not set')}")
    
    # Test Database configuration
    print("\n🗄️ Database Configuration:")
    print(f"  DB_PATH: {os.getenv('DB_PATH', 'Not set (using default)')}")
    
    # Test Security configuration
    print("\n🔒 Security Configuration:")
    print(f"  MIN_PASSWORD_LENGTH: {os.getenv('MIN_PASSWORD_LENGTH', 'Not set (using default)')}")
    print(f"  SESSION_TIMEOUT: {os.getenv('SESSION_TIMEOUT', 'Not set (using default)')}")
    
    # Test Logging configuration
    print("\n📝 Logging Configuration:")
    print(f"  LOG_LEVEL: {os.getenv('LOG_LEVEL', 'Not set (using default)')}")
    print(f"  LOG_FILE: {os.getenv('LOG_FILE', 'Not set (using console)')}")
    
    print("\n" + "=" * 50)
    
    # Check if critical settings are configured
    critical_settings = ['SECRET_KEY', 'USE_FILE_EMAIL']
    missing_critical = [setting for setting in critical_settings if not os.getenv(setting)]
    
    if missing_critical:
        print(f"⚠️  WARNING: Missing critical settings: {', '.join(missing_critical)}")
        print("   Please review your .env file configuration.")
    else:
        print("✅ All critical settings are configured!")
    
    # Test email service initialization
    print("\n🔧 Testing Email Service Integration:")
    try:
        from email_service import EmailService
        email_service = EmailService()
        print("✅ Email service initialized successfully")
        
        # Test email configuration
        config_test = email_service.test_email_config()
        if config_test:
            print("✅ Email configuration is valid")
        else:
            print("❌ Email configuration test failed")
            
    except Exception as e:
        print(f"❌ Error initializing email service: {e}")
    
    print("\n🎯 Configuration Test Complete!")
    print("If you see any issues above, please review your .env file.")

if __name__ == "__main__":
    test_env_config()