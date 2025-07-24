# Environment Configuration Guide

This guide explains how to configure the Vacation Management System using `.env` files.

## 🎯 **Overview**

The system now uses a `.env` file for all configuration instead of hardcoded values or scattered `os.getenv()` calls. This provides:

- **Security**: Sensitive data (passwords, keys) stored in .env file
- **Flexibility**: Easy configuration changes without code modifications
- **Environment Separation**: Different settings for development/production
- **Best Practices**: Industry-standard configuration management

## 📋 **Configuration Files**

### `.env.example`
Complete template with all available configuration options and documentation.

### `.env`
Your actual configuration file (created from `.env.example`).
**Important**: This file is excluded from version control and contains sensitive data.

## 🚀 **Quick Setup**

```bash
# 1. Copy the example configuration
cp .env.example .env

# 2. Edit .env with your settings (optional for development)
# The default settings work for development/testing

# 3. Test your configuration
uv run test_env_config.py

# 4. Start the application
uv run app.py
```

## ⚙️ **Configuration Categories**

### 1. Flask Application Settings
```bash
# Required: Flask secret key for session management
SECRET_KEY=your-secret-key-change-this-in-production

# Optional: Flask environment and debug mode
FLASK_ENV=development
FLASK_DEBUG=true
```

### 2. Email Configuration
```bash
# Email delivery mode
USE_FILE_EMAIL=true  # true=files, false=SMTP

# SMTP settings (only needed if USE_FILE_EMAIL=false)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true

# Email sender information
FROM_EMAIL=noreply@vacation-manager.local
FROM_NAME=Vacation Manager
```

### 3. Database Configuration
```bash
# Optional: Database file path
DB_PATH=user.db
```

### 4. Security Settings
```bash
# Optional: Password and session settings
MIN_PASSWORD_LENGTH=6
SESSION_TIMEOUT=3600
```

### 5. Logging Configuration
```bash
# Optional: Logging level and file
LOG_LEVEL=INFO
LOG_FILE=vacation_manager.log  # Omit for console logging
```

## 🔒 **Security Best Practices**

### File Permissions
```bash
# Set secure permissions on .env file
chmod 600 .env
```

### Secret Key Generation
```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Production Settings
```bash
# For production, ensure:
SECRET_KEY=<strong-random-key>
FLASK_ENV=production
FLASK_DEBUG=false
USE_FILE_EMAIL=false
# ... configure SMTP settings
```

## 📧 **Email Provider Examples**

### Gmail
```bash
USE_FILE_EMAIL=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password
SMTP_USE_TLS=true
```

### Office 365
```bash
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@company.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
```

### Yahoo
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
```

## 🧪 **Testing Configuration**

### Test All Settings
```bash
uv run test_env_config.py
```

### Test Email Service
```bash
uv run email_service.py
```

### Test Flask App
```bash
uv run app.py
```

## 🔧 **Development vs Production**

### Development (Default)
- `USE_FILE_EMAIL=true` (emails saved to files)
- `FLASK_DEBUG=true` (debug mode enabled)
- `SECRET_KEY` can be simple (but change for production)
- Logging to console

### Production
- `USE_FILE_EMAIL=false` (real email sending)
- `FLASK_DEBUG=false` (debug mode disabled)
- `SECRET_KEY` must be cryptographically secure
- Configure proper SMTP settings
- Consider file-based logging

## 🛠️ **Environment Variables Loaded**

The system automatically loads these from `.env`:

**Flask App (`app.py`)**:
- `SECRET_KEY`
- `FLASK_ENV`
- `FLASK_DEBUG`
- `LOG_LEVEL`
- `LOG_FILE`

**Email Service (`email_service.py`)**:
- `USE_FILE_EMAIL`
- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `FROM_EMAIL`
- `FROM_NAME`

## 🚨 **Important Notes**

1. **Never commit `.env` files** to version control
2. **Always use `.env.example`** as a template
3. **Set proper file permissions** on `.env` (600)
4. **Use strong secret keys** in production
5. **Test configuration** before deployment
6. **Use App Passwords** for Gmail (not regular passwords)

## 🎯 **Migration from os.getenv()**

The system was updated to use proper `.env` file loading:

**Before:**
```python
# Scattered throughout code
smtp_server = os.getenv('SMTP_SERVER', 'localhost')
```

**After:**
```python
# Centralized loading
load_dotenv()
smtp_server = os.getenv('SMTP_SERVER', 'localhost')
```

This ensures:
- Consistent configuration loading
- Proper .env file support
- Better development workflow
- Easier deployment management

## 📞 **Support**

If you have configuration issues:
1. Run `uv run test_env_config.py` to diagnose problems
2. Check file permissions on `.env`
3. Verify `.env` file syntax
4. Review logs for error messages
5. Compare with `.env.example` template