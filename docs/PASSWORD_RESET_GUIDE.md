# Secure Password Reset Guide

This guide explains how to securely reset passwords for the Vacation Management System with email delivery and mandatory password changes.

## 🔧 **Command-Line Password Reset (Administrator)**

### Basic Usage

```bash
# List all users
uv run reset_password.py --list

# Reset password for a specific user (will prompt for new password)
uv run reset_password.py --email user@example.com

# Reset password with a specific password
uv run reset_password.py --email user@example.com --password newpassword123

# Generate a random password
uv run reset_password.py --email user@example.com --generate
```

### Interactive Mode

```bash
# Run interactive mode for guided password reset
uv run reset_password.py --interactive
```

Interactive mode will:
1. Show all users in the system
2. Ask for the user's email address
3. Offer options to manually enter a password or generate a random one
4. Process the password reset

### Examples

```bash
# Reset password for test@example.com with a generated password
uv run reset_password.py --email test@example.com --generate

# Reset password interactively
uv run reset_password.py --interactive

# List all users first, then reset a specific user
uv run reset_password.py --list
uv run reset_password.py --email admin@example.com --password mysecurepassword
```

## 🌐 **Web Interface Password Reset**

### For Users Who Forgot Their Password

1. Go to the login page: `http://localhost:5000/login`
2. Click "Forgot Password?" button
3. Enter your email address
4. A new random password will be generated and sent to your email
5. Check your email for the new password
6. Use the new password to log in
7. **Required**: You will be forced to change your password immediately after logging in

### For Logged-in Users

1. Log in to your account
2. Click on your email in the top-right corner
3. Select "Reset Password" from the dropdown menu
4. Enter your email address to get a new random password sent via email
5. Check your email for the new password
6. Use the new password to log in again
7. You will be forced to change your password immediately after logging in

## 🔒 **Security Features**

### Password Requirements
- Minimum 6 characters long
- Generated passwords include letters, numbers, and special characters
- All passwords are securely hashed using Werkzeug

### Security Measures
- **Email Delivery**: Passwords are sent via email, never displayed on screen
- **Mandatory Password Change**: Users MUST change their password after reset
- **Cryptographically Secure**: Generated passwords use Python's `secrets` module
- **Password Hashing**: All passwords are securely hashed, never stored in plain text
- **Email Enumeration Protection**: Same message shown regardless of email validity
- **Database Tracking**: Password reset status tracked in database
- **Session Security**: Users cannot access other pages until password is changed

## 📧 **Email Configuration**

### Development Mode (Default)
By default, the system saves emails to files in the `sent_emails/` directory instead of sending actual emails. This is perfect for development and testing.

### Production Mode
To send real emails, edit your `.env` file:

```bash
# Copy the example configuration (if not already done)
cp .env.example .env

# Edit the .env file with your email settings
# Set USE_FILE_EMAIL=false for production
```

### Email Configuration Options

**For Gmail:**
```bash
USE_FILE_EMAIL=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Vacation Manager
```

**For Office 365:**
```bash
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@company.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
```

### Testing Email Configuration

```bash
# Test all configuration settings
uv run test_env_config.py

# Test email service specifically
uv run email_service.py
```

## 📋 **Common Use Cases**

### 1. User Forgot Password
**Web Interface:**
- User goes to login page
- Clicks "Forgot Password?"
- Enters email, gets new password sent via email
- Logs in and is forced to change password

**Administrator Help:**
```bash
uv run reset_password.py --email user@example.com --generate
```

### 2. New User Setup
**Administrator sets up new user:**
```bash
# Add user to database first (if not already added)
sqlite3 user.db "INSERT INTO user (mail, weekdays) VALUES ('newuser@example.com', '0,1,2,3,4');"

# Set initial password
uv run reset_password.py --email newuser@example.com --password welcome123
```

### 3. Bulk Password Reset
**Administrator resets multiple users:**
```bash
uv run reset_password.py --email user1@example.com --generate
uv run reset_password.py --email user2@example.com --generate
uv run reset_password.py --email user3@example.com --generate
```

### 4. Interactive Setup
**Administrator uses interactive mode:**
```bash
uv run reset_password.py --interactive
```

## 🛠️ **Troubleshooting**

### Common Issues

**"User not found" error:**
- Check if the email address is correct
- Use `--list` to see all users in the system
- Verify the user exists in the database

**Database connection error:**
- Ensure `user.db` exists in the same directory
- Check file permissions
- Verify the database schema is correct

**Permission errors:**
- Make sure the script has read/write access to the database
- Run with appropriate user permissions

### Verification

**Check if password reset worked:**
1. Try logging in with the new password
2. Check the database directly:
```bash
sqlite3 user.db "SELECT mail FROM user WHERE mail = 'user@example.com';"
```

**Verify password hash:**
```bash
sqlite3 user.db "SELECT mail, password_hash FROM user WHERE mail = 'user@example.com';"
```

## 🔐 **Best Practices**

1. **Always change generated passwords** after first login
2. **Use strong passwords** (minimum 8 characters with mixed case, numbers, symbols)
3. **Keep passwords secure** - don't share them via insecure channels
4. **Regular password updates** - encourage users to change passwords periodically
5. **Administrator access** - limit who can run the password reset script
6. **Audit trail** - the script logs all password reset operations

## 📞 **Support**

If you need help with password reset:
1. Check this guide first
2. Try the interactive mode: `uv run reset_password.py --interactive`
3. Use the `--list` option to verify user emails
4. Contact your system administrator if you're still having issues

## 🔄 **Integration with Existing System**

The password reset system integrates seamlessly with:
- Existing user database
- Web interface authentication
- Command-line vacation management tools
- All existing functionality remains unchanged