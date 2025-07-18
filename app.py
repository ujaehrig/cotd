#!/usr/bin/env python3

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import logging
import secrets
import string
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from email_service import EmailService
from manage_vacations import (
    get_db_connection, 
    validate_date, 
    get_user_id_by_email,
    add_vacation as add_vacation_db,
    delete_vacation as delete_vacation_db
)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Configure Flask app from environment variables
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
app.config['ENV'] = os.getenv('FLASK_ENV', 'development')

# Initialize email service
email_service = EmailService()

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Configure logging from environment variables
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
log_file = os.getenv('LOG_FILE', None)

logging_config = {
    'level': getattr(logging, log_level, logging.INFO),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

if log_file:
    logging_config['filename'] = log_file

logging.basicConfig(**logging_config)

class User(UserMixin):
    def __init__(self, id, mail, weekdays, last_chosen, password_reset_required=False):
        self.id = str(id)
        self.mail = mail
        self.weekdays = weekdays
        self.last_chosen = last_chosen
        self.password_reset_required = password_reset_required

    @staticmethod
    def get(user_id):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, mail, weekdays, last_chosen, password_reset_required FROM user WHERE id = ?", (user_id,))
                user_data = cursor.fetchone()
                if user_data:
                    return User(user_data['id'], user_data['mail'], user_data['weekdays'], user_data['last_chosen'], user_data['password_reset_required'])
        except Exception as e:
            logging.error(f"Error getting user: {e}")
        return None

    @staticmethod
    def get_by_email(email):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, mail, weekdays, last_chosen, password_reset_required FROM user WHERE mail = ?", (email,))
                user_data = cursor.fetchone()
                if user_data:
                    return User(user_data['id'], user_data['mail'], user_data['weekdays'], user_data['last_chosen'], user_data['password_reset_required'])
        except Exception as e:
            logging.error(f"Error getting user by email: {e}")
        return None

    @staticmethod
    def authenticate(email, password):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, mail, weekdays, last_chosen, password_hash, password_reset_required FROM user WHERE mail = ?", (email,))
                user_data = cursor.fetchone()
                if user_data and check_password_hash(user_data['password_hash'], password):
                    return User(user_data['id'], user_data['mail'], user_data['weekdays'], user_data['last_chosen'], user_data['password_reset_required'])
        except Exception as e:
            logging.error(f"Error authenticating user: {e}")
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.before_request
def check_password_reset_required():
    """Check if user needs to change password after reset."""
    if current_user.is_authenticated and hasattr(current_user, 'password_reset_required'):
        if current_user.password_reset_required and request.endpoint not in ['change_password', 'logout', 'static']:
            flash('You must change your password before continuing.', 'warning')
            return redirect(url_for('change_password'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.authenticate(email, password)
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('my_vacations'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/my_vacations')
@login_required
def my_vacations():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.start_date, v.end_date
                FROM vacation v
                WHERE v.user_id = ?
                ORDER BY v.start_date
            """, (current_user.id,))
            
            vacations_data = cursor.fetchall()
            
        return render_template('my_vacations.html', vacations=vacations_data)
    except Exception as e:
        flash(f'Error loading vacations: {str(e)}', 'error')
        return render_template('my_vacations.html', vacations=[])

@app.route('/add_vacation', methods=['GET', 'POST'])
@login_required
def add_vacation():
    if request.method == 'POST':
        try:
            start_date = request.form['start_date']
            end_date = request.form.get('end_date', None)
            
            if not end_date:
                end_date = None
            
            # Use current user's ID instead of selecting from dropdown
            add_vacation_db(current_user.id, start_date, end_date)
            flash('Vacation period added successfully!', 'success')
            return redirect(url_for('my_vacations'))
        except Exception as e:
            flash(f'Error adding vacation: {str(e)}', 'error')
    
    return render_template('add_vacation.html')

@app.route('/delete_vacation/<int:vacation_id>', methods=['POST'])
@login_required
def delete_vacation(vacation_id):
    try:
        # Check if the vacation belongs to the current user
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM vacation WHERE id = ?", (vacation_id,))
            vacation = cursor.fetchone()
            
            if not vacation:
                flash('Vacation not found.', 'error')
                return redirect(url_for('my_vacations'))
            
            if str(vacation['user_id']) != current_user.id:
                flash('You can only delete your own vacations.', 'error')
                return redirect(url_for('my_vacations'))
        
        delete_vacation_db(vacation_id)
        flash('Vacation period deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting vacation: {str(e)}', 'error')
    
    return redirect(url_for('my_vacations'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('change_password.html')
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM user WHERE id = ?", (current_user.id,))
                user_data = cursor.fetchone()
                
                if not check_password_hash(user_data['password_hash'], current_password):
                    flash('Current password is incorrect.', 'error')
                    return render_template('change_password.html')
                
                new_password_hash = generate_password_hash(new_password)
                cursor.execute("UPDATE user SET password_hash = ?, password_reset_required = 0 WHERE id = ?", (new_password_hash, current_user.id))
                conn.commit()
                
                flash('Password changed successfully!', 'success')
                return redirect(url_for('my_vacations'))
        except Exception as e:
            flash(f'Error changing password: {str(e)}', 'error')
    
    return render_template('change_password.html')

def generate_random_password(length=12):
    """Generate a random password with letters, digits, and special characters."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """Password reset for users who forgot their password."""
    if request.method == 'POST':
        email = request.form['email']
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM user WHERE mail = ?", (email,))
                user_data = cursor.fetchone()
                
                # Always show the same message to prevent email enumeration
                flash('If this email exists in our system, a password reset email has been sent.', 'info')
                
                if user_data:
                    # Generate new random password
                    new_password = generate_random_password()
                    password_hash = generate_password_hash(new_password)
                    
                    # Update password and set reset required flag
                    cursor.execute("UPDATE user SET password_hash = ?, password_reset_required = 1 WHERE mail = ?", (password_hash, email))
                    conn.commit()
                    
                    # Send password reset email
                    email_sent = email_service.send_password_reset_email(email, new_password)
                    
                    if email_sent:
                        logging.info(f"Password reset email sent to: {email}")
                    else:
                        logging.error(f"Failed to send password reset email to: {email}")
                        # Don't reveal the failure to the user for security
                
                return redirect(url_for('login'))
                
        except Exception as e:
            logging.error(f'Error processing password reset: {str(e)}')
            flash('An error occurred while processing your request. Please try again.', 'error')
    
    return render_template('reset_password.html')

@app.route('/forgot_password')
def forgot_password():
    """Redirect to reset password page."""
    return redirect(url_for('reset_password'))

if __name__ == '__main__':
    app.run(debug=True, host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '5000')))