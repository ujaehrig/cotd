#!/usr/bin/env python3

import os
import shutil
from pathlib import Path

def setup_environment():
    """Set up the environment for the vacation management system."""
    
    print("🚀 Setting up Vacation Management System Environment")
    print("=" * 55)
    
    # Check if .env already exists
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("📄 .env file already exists")
        
        # Ask if user wants to overwrite
        response = input("Do you want to overwrite it with the example template? (y/N): ").lower()
        if response in ['y', 'yes']:
            shutil.copy(env_example, env_file)
            print("✅ .env file updated with example template")
        else:
            print("📄 Keeping existing .env file")
    else:
        # Copy example to .env
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("✅ Created .env file from example template")
        else:
            print("❌ .env.example file not found!")
            return False
    
    # Set proper permissions on .env file
    try:
        os.chmod(env_file, 0o600)  # rw-------
        print("🔒 Set secure permissions on .env file")
    except Exception as e:
        print(f"⚠️  Warning: Could not set permissions on .env file: {e}")
    
    # Create sent_emails directory
    sent_emails_dir = Path("sent_emails")
    sent_emails_dir.mkdir(exist_ok=True)
    print("📁 Created sent_emails directory")
    
    # Test configuration
    print("\n🧪 Testing configuration...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test basic settings
        secret_key = os.getenv('SECRET_KEY')
        use_file_email = os.getenv('USE_FILE_EMAIL')
        
        if secret_key == 'your-secret-key-change-this-in-production':
            print("⚠️  WARNING: Please change SECRET_KEY in your .env file for production!")
        
        if use_file_email == 'true':
            print("📧 Email configured for file-based delivery (development mode)")
        else:
            print("📧 Email configured for SMTP delivery (production mode)")
            
        print("✅ Configuration test passed")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    print("\n" + "=" * 55)
    print("🎯 Environment setup complete!")
    print("\nNext steps:")
    print("1. Review and customize your .env file:")
    print("   - Change SECRET_KEY for production")
    print("   - Configure email settings if needed")
    print("2. Set up the database:")
    print("   sqlite3 user.db < setup.sql")
    print("   uv run add_auth_migration.py")
    print("   uv run add_password_reset_tracking.py")
    print("3. Start the application:")
    print("   uv run app.py")
    print("4. Test your configuration:")
    print("   uv run test_env_config.py")
    
    return True

if __name__ == "__main__":
    setup_environment()