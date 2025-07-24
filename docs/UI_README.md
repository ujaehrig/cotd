# Vacation Management Web UI

A secure web-based user interface for managing vacation periods in the "Catcher Of The Day" system.

## Features

- **User Authentication**: Secure login/logout with password protection
- **Personal Vacation Management**: View, add, and delete your own vacation periods
- **Password Management**: Change your password functionality
- **Password Reset**: Reset forgotten passwords via web interface or command-line
- **Responsive Design**: Works on desktop and mobile devices
- **Form Validation**: Client-side and server-side validation
- **Security**: Users can only manage their own vacation periods

## Installation

1. Install dependencies:
```bash
uv sync
```

2. Configure environment variables:
```bash
# Copy the example configuration file
cp .env.example .env

# Edit .env file with your settings (optional for development)
# The default settings work for development/testing
```

3. Set up the database:
```bash
sqlite3 user.db < setup.sql
uv run add_auth_migration.py
uv run add_password_reset_tracking.py
```

4. Add some test users with passwords:
```bash
# The migration script sets default password 'changeme123' for existing users
sqlite3 user.db "INSERT INTO user (mail, weekdays) VALUES ('newuser@example.com', '0,1,2,3,4');"
uv run add_auth_migration.py  # This will add password to new users
```

## Usage

1. Start the web server:
```bash
uv run app.py
```

2. Open your browser and go to:
```
http://localhost:5000
```

3. Login with:
   - **Email**: test@example.com or admin@example.com
   - **Password**: changeme123
   
4. **Important**: Change your password after first login!

## Password Reset

If you forget your password, you have two options:

### Option 1: Web Interface
1. Go to the login page
2. Click "Forgot Password?"
3. Enter your email address
4. A new random password will be sent to your email
5. Check your email for the new password
6. Use the new password to log in
7. You will be required to change your password immediately

### Option 2: Command-Line (Administrator)
```bash
# Generate a random password for a user
uv run reset_password.py --email user@example.com --generate

# Interactive mode for guided password reset
uv run reset_password.py --interactive

# List all users
uv run reset_password.py --list
```

See `PASSWORD_RESET_GUIDE.md` for complete password reset documentation.

## Configuration

The system uses a `.env` file for all configuration. Key settings include:

### Email Configuration
For development (default):
```bash
USE_FILE_EMAIL=true  # Saves emails to files instead of sending
```

For production:
```bash
USE_FILE_EMAIL=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Vacation Manager
```

### Flask Configuration
```bash
SECRET_KEY=your-secret-key-change-this-in-production
FLASK_ENV=development
FLASK_DEBUG=true
```

### Testing Configuration
```bash
# Test your configuration
uv run test_env_config.py

# Test email service
uv run email_service.py
```

## Features Overview

### Home Page
- Overview of the system
- Quick navigation to personal vacation management
- Login prompt for unauthenticated users

### Login Page
- Secure user authentication
- Default credentials displayed for convenience

### My Vacations Page
- List your personal vacation periods
- Delete your vacation periods with confirmation
- Shows duration and status for multi-day vacations
- Secure - only shows your own vacations

### Add Vacation Page
- Form to add new vacation periods for yourself
- Support for single-day and multi-day vacations
- Date validation
- Automatic user assignment (current logged-in user)

### Change Password Page
- Secure password change functionality
- Current password verification
- Password strength validation

### Reset Password Page
- Forgot password functionality
- Generates new random password
- Secure password reset process

## API Endpoints

- `GET /` - Home page
- `GET /login` - Login page
- `POST /login` - Process login
- `GET /logout` - Logout user
- `GET /my_vacations` - Personal vacations list (requires login)
- `GET /add_vacation` - Add vacation form (requires login)
- `POST /add_vacation` - Submit new vacation (requires login)
- `POST /delete_vacation/<id>` - Delete vacation (requires login, own vacations only)
- `GET /change_password` - Change password form (requires login)
- `POST /change_password` - Process password change (requires login)
- `GET /reset_password` - Password reset form
- `POST /reset_password` - Process password reset
- `GET /forgot_password` - Redirect to password reset

## Technical Details

- **Framework**: Flask with Flask-Login for authentication
- **Database**: SQLite (shared with existing system)
- **Frontend**: Bootstrap 5 with Font Awesome icons
- **Templates**: Jinja2 templating engine
- **Authentication**: Password hashing with Werkzeug
- **Validation**: Client-side JavaScript + server-side Python
- **Security**: Session-based authentication, user isolation

## Security Features

- **Password Hashing**: All passwords are securely hashed using Werkzeug
- **User Isolation**: Users can only view and manage their own vacation periods
- **Session Management**: Secure session handling with Flask-Login
- **Access Control**: All vacation management routes require authentication
- **CSRF Protection**: Forms protected against cross-site request forgery

## Integration

The web UI integrates seamlessly with the existing command-line `manage_vacations.py` script by:
- Using the same database (`user.db`) with added password authentication
- Importing and using the same core functions
- Maintaining the same data validation rules
- Supporting the same vacation period logic
- Adding secure user authentication layer