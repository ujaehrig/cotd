#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#     "flask>=2.3.0",
#     "flask-login>=0.6.0",
#     "werkzeug>=2.3.0",
#     "requests>=2.25.0",
#     "python-dotenv>=1.0.0"
# ]
# ///

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import check_password_hash, generate_password_hash
import logging
import secrets
import string
import os
from datetime import datetime, date
from dotenv import load_dotenv
from email_service import EmailService
from vacation_webhooks import send_vacation_added_webhook, send_vacation_deleted_webhook
from manage_vacations import (
    get_db_connection,
    add_vacation as add_vacation_db,
    delete_vacation as delete_vacation_db,
)

# Load environment variables from .env file
load_dotenv()

# Constants
DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
DEFAULT_LOG_LEVEL = "INFO"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)

# Warn if using default secret key in production
if app.secret_key == DEFAULT_SECRET_KEY and os.getenv("FLASK_ENV") == "production":
    logging.warning(
        "Using default secret key in production! Please set SECRET_KEY environment variable."
    )

# Configure Flask app from environment variables
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "false").lower() == "true"
app.config["ENV"] = os.getenv("FLASK_ENV", "development")

# Initialize email service
email_service = EmailService()

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

# Configure logging from environment variables
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_file = os.getenv("LOG_FILE", None)

logging_config = {
    "level": getattr(logging, log_level, logging.INFO),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

if log_file:
    logging_config["filename"] = log_file

logging.basicConfig(**logging_config)


# Add custom Jinja2 filter for strptime
@app.template_filter("strptime")
def strptime_filter(date_string, format_string):
    """Convert date string to datetime object"""
    return datetime.strptime(date_string, format_string)


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
                cursor.execute(
                    "SELECT id, mail, weekdays, last_chosen, password_reset_required FROM user WHERE id = ?",
                    (user_id,),
                )
                user_data = cursor.fetchone()
                if user_data:
                    return User(
                        user_data["id"],
                        user_data["mail"],
                        user_data["weekdays"],
                        user_data["last_chosen"],
                        user_data["password_reset_required"],
                    )
        except Exception as e:
            logging.error(f"Error getting user: {e}")
        return None

    @staticmethod
    def get_by_email(email):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, mail, weekdays, last_chosen, password_reset_required FROM user WHERE mail = ?",
                    (email,),
                )
                user_data = cursor.fetchone()
                if user_data:
                    return User(
                        user_data["id"],
                        user_data["mail"],
                        user_data["weekdays"],
                        user_data["last_chosen"],
                        user_data["password_reset_required"],
                    )
        except Exception as e:
            logging.error(f"Error getting user by email: {e}")
        return None

    @staticmethod
    def authenticate(email, password):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, mail, weekdays, last_chosen, password_hash, password_reset_required FROM user WHERE mail = ?",
                    (email,),
                )
                user_data = cursor.fetchone()
                if user_data and check_password_hash(
                    user_data["password_hash"], password
                ):
                    return User(
                        user_data["id"],
                        user_data["mail"],
                        user_data["weekdays"],
                        user_data["last_chosen"],
                        user_data["password_reset_required"],
                    )
        except Exception as e:
            logging.error(f"Error authenticating user: {e}")
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def handle_htmx_error(error_message: str, status_code: int = 400) -> tuple[str, int]:
    """Helper function to handle HTMX error responses"""
    return (
        f'<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>{error_message}</div>',
        status_code,
    )


def is_htmx_request() -> bool:
    """Check if the current request is an HTMX request"""
    return bool(request.headers.get("HX-Request"))


def check_vacation_overlap(user_id: int, start_date: str, end_date: str) -> tuple[bool, str]:
    """
    Check if a vacation period overlaps with existing vacations for a user.
    
    Args:
        user_id: ID of the user
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Tuple of (has_overlap, error_message)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check for overlapping vacations
            # Two date ranges overlap if: start1 <= end2 AND start2 <= end1
            cursor.execute("""
                SELECT start_date, end_date 
                FROM vacation 
                WHERE user_id = ? 
                AND (
                    (start_date <= ? AND end_date >= ?) OR  -- New vacation starts during existing
                    (start_date <= ? AND end_date >= ?) OR  -- New vacation ends during existing
                    (start_date >= ? AND end_date <= ?)     -- New vacation contains existing
                )
            """, (user_id, end_date, start_date, end_date, start_date, start_date, end_date))
            
            overlapping_vacations = cursor.fetchall()
            
            if overlapping_vacations:
                # Format the overlapping vacation dates for the error message
                overlap_dates = []
                for vacation in overlapping_vacations:
                    if vacation['start_date'] == vacation['end_date']:
                        overlap_dates.append(vacation['start_date'])
                    else:
                        overlap_dates.append(f"{vacation['start_date']} to {vacation['end_date']}")
                
                if len(overlap_dates) == 1:
                    error_msg = f"This vacation overlaps with your existing vacation: {overlap_dates[0]}"
                else:
                    error_msg = f"This vacation overlaps with your existing vacations: {', '.join(overlap_dates)}"
                
                return True, error_msg
            
            return False, ""
            
    except Exception as e:
        logging.error(f"Error checking vacation overlap for user {user_id}: {e}")
        return True, "Error checking for vacation conflicts. Please try again."


def check_duplicate_vacation(user_id: int, start_date: str, end_date: str) -> tuple[bool, str]:
    """
    Check if a vacation period is an exact duplicate of an existing vacation.
    
    Args:
        user_id: ID of the user
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Tuple of (is_duplicate, error_message)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check for exact duplicate
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM vacation 
                WHERE user_id = ? AND start_date = ? AND end_date = ?
            """, (user_id, start_date, end_date))
            
            result = cursor.fetchone()
            
            if result['count'] > 0:
                if start_date == end_date:
                    error_msg = f"You already have a vacation on {start_date}"
                else:
                    error_msg = f"You already have a vacation from {start_date} to {end_date}"
                return True, error_msg
            
            return False, ""
            
    except Exception as e:
        logging.error(f"Error checking duplicate vacation for user {user_id}: {e}")
        return True, "Error checking for duplicate vacations. Please try again."


def get_today_date_string() -> str:
    """Get today's date as a string in YYYY-MM-DD format"""
    return datetime.now().strftime("%Y-%m-%d")


@app.before_request
def check_password_reset_required():
    """Check if user needs to change password after reset."""
    if current_user.is_authenticated and hasattr(
        current_user, "password_reset_required"
    ):
        if current_user.password_reset_required and request.endpoint not in [
            "change_password",
            "logout",
            "static",
        ]:
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("change_password"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.authenticate(email, password)
        if user:
            login_user(user)
            next_page = request.args.get("next")
            return (
                redirect(next_page) if next_page else redirect(url_for("my_vacations"))
            )
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/vacation_overview")
@login_required
def vacation_overview():
    """Show vacation overview for all users"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Get all users with their vacation periods
            cursor.execute("""
                SELECT 
                    u.id,
                    u.mail,
                    v.id as vacation_id,
                    v.start_date,
                    v.end_date
                FROM user u
                LEFT JOIN vacation v ON u.id = v.user_id
                ORDER BY u.mail, v.start_date
            """)

            results = cursor.fetchall()

            # Group vacations by user
            users_vacations = {}
            for row in results:
                user_email = row["mail"]
                if user_email not in users_vacations:
                    users_vacations[user_email] = {
                        "user_id": row["id"],
                        "email": user_email,
                        "vacations": [],
                    }

                # Only add vacation if it exists (LEFT JOIN might return NULL)
                if row["vacation_id"]:
                    users_vacations[user_email]["vacations"].append(
                        {
                            "id": row["vacation_id"],
                            "start_date": row["start_date"],
                            "end_date": row["end_date"],
                        }
                    )

            # Convert to list and sort by email
            users_list = list(users_vacations.values())
            users_list.sort(key=lambda x: x["email"])

        return render_template(
            "vacation_overview.html",
            users=users_list,
            today_date=get_today_date_string(),
        )
    except Exception as e:
        logging.error(f"Error loading vacation overview: {e}")
        flash(f"Error loading vacation overview: {str(e)}", "error")
        return render_template(
            "vacation_overview.html", users=[], today_date=get_today_date_string()
        )


@app.route("/my_vacations")
@login_required
def my_vacations():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT v.id, v.start_date, v.end_date
                FROM vacation v
                WHERE v.user_id = ?
                ORDER BY v.start_date
            """,
                (int(current_user.id),),
            )

            vacations_data = cursor.fetchall()

        return render_template(
            "my_vacations.html",
            vacations=vacations_data,
            today_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as e:
        flash(f"Error loading vacations: {str(e)}", "error")
        return render_template(
            "my_vacations.html",
            vacations=[],
            today_date=datetime.now().strftime("%Y-%m-%d"),
        )


@app.route("/vacation_table")
@login_required
def vacation_table():
    """HTMX endpoint to return just the vacation table"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT v.id, v.start_date, v.end_date
                FROM vacation v
                WHERE v.user_id = ?
                ORDER BY v.start_date
            """,
                (int(current_user.id),),
            )

            vacations_data = cursor.fetchall()

        return render_template(
            "partials/vacation_table.html",
            vacations=vacations_data,
            today_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as e:
        return (
            f'<div class="alert alert-danger">Error loading vacations: {str(e)}</div>',
            500,
        )


@app.route("/add_vacation", methods=["GET", "POST"])
@login_required
def add_vacation():
    if request.method == "POST":
        try:
            start_date = request.form["start_date"]
            end_date = request.form.get("end_date", None)

            if not end_date:
                end_date = None

            # Server-side validation: prevent past dates
            today = date.today()

            # Validate start date
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            if start_date_obj < today:
                error_msg = "Start date cannot be in the past. Please select today or a future date."
                if is_htmx_request():
                    return handle_htmx_error(error_msg)
                flash(error_msg, "error")
                return render_template("add_vacation.html")

            # Validate end date if provided
            if end_date:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                if end_date_obj < today:
                    error_msg = "End date cannot be in the past. Please select today or a future date."
                    if is_htmx_request():
                        return handle_htmx_error(error_msg)
                    flash(error_msg, "error")
                    return render_template("add_vacation.html")

                if end_date_obj < start_date_obj:
                    error_msg = "End date cannot be before start date."
                    if is_htmx_request():
                        return handle_htmx_error(error_msg)
                    flash(error_msg, "error")
                    return render_template("add_vacation.html")

            # Use end_date = start_date for single day vacations
            if not end_date:
                end_date = start_date

            # Check for duplicate vacation
            is_duplicate, duplicate_error = check_duplicate_vacation(
                int(current_user.id), start_date, end_date
            )
            if is_duplicate:
                if is_htmx_request():
                    return handle_htmx_error(duplicate_error)
                flash(duplicate_error, "error")
                return render_template("add_vacation.html")

            # Check for overlapping vacations
            has_overlap, overlap_error = check_vacation_overlap(
                int(current_user.id), start_date, end_date
            )
            if has_overlap:
                if is_htmx_request():
                    return handle_htmx_error(overlap_error)
                flash(overlap_error, "error")
                return render_template("add_vacation.html")

            # Use current user's ID instead of selecting from dropdown
            add_vacation_db(int(current_user.id), start_date, end_date)

            # Send webhook notification (non-blocking)
            try:
                send_vacation_added_webhook(
                    user_email=current_user.mail,
                    start_date=start_date,
                    end_date=end_date
                    or start_date,  # Use start_date if end_date is None
                )
            except Exception as e:
                logging.warning(f"Failed to send vacation added webhook: {e}")
                # Don't fail the vacation creation if webhook fails

            # For HTMX requests, return updated vacation table and success message
            if request.headers.get("HX-Request"):
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT v.id, v.start_date, v.end_date
                        FROM vacation v
                        WHERE v.user_id = ?
                        ORDER BY v.start_date
                    """,
                        (int(current_user.id),),
                    )
                    vacations_data = cursor.fetchall()

                # Return updated table for HTMX
                table_html = render_template(
                    "partials/vacation_table.html",
                    vacations=vacations_data,
                    today_date=get_today_date_string(),
                )

                # Use HTMX response headers to update multiple targets
                response = app.response_class(
                    response=table_html, status=200, mimetype="text/html"
                )
                response.headers["HX-Trigger"] = "vacationAdded"
                response.headers["HX-Retarget"] = "#vacation-table"
                response.headers["HX-Reswap"] = "innerHTML"

                # Also clear the form
                return response

            flash("Vacation period added successfully!", "success")
            return redirect(url_for("my_vacations"))
        except ValueError:
            error_msg = "Invalid date format. Please use the date picker."
            if is_htmx_request():
                return handle_htmx_error(error_msg)
            flash(error_msg, "error")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if is_htmx_request():
                return handle_htmx_error(error_msg)
            flash(f"Error adding vacation: {str(e)}", "error")

    # For HTMX requests, return just the form
    if is_htmx_request():
        return render_template("partials/add_vacation_form.html")

    return render_template("add_vacation.html")


@app.route("/delete_vacation/<int:vacation_id>", methods=["POST", "DELETE"])
@login_required
def delete_vacation(vacation_id):
    try:
        # Check if the vacation belongs to the current user and get vacation details
        vacation_details = None
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, start_date, end_date FROM vacation WHERE id = ?",
                (vacation_id,),
            )
            vacation = cursor.fetchone()

            if not vacation:
                if request.headers.get("HX-Request"):
                    return (
                        '<div class="alert alert-danger">Vacation not found.</div>',
                        404,
                    )
                flash("Vacation not found.", "error")
                return redirect(url_for("my_vacations"))

            if str(vacation["user_id"]) != current_user.id:
                if request.headers.get("HX-Request"):
                    return (
                        '<div class="alert alert-danger">You can only delete your own vacations.</div>',
                        403,
                    )
                flash("You can only delete your own vacations.", "error")
                return redirect(url_for("my_vacations"))

            # Store vacation details for webhook
            vacation_details = {
                "start_date": vacation["start_date"],
                "end_date": vacation["end_date"],
            }

        delete_vacation_db(vacation_id)

        # Send webhook notification (non-blocking)
        if vacation_details:
            try:
                send_vacation_deleted_webhook(
                    user_email=current_user.mail,
                    start_date=vacation_details["start_date"],
                    end_date=vacation_details["end_date"],
                )
            except Exception as e:
                logging.warning(f"Failed to send vacation deleted webhook: {e}")
                # Don't fail the vacation deletion if webhook fails

        # For HTMX requests, return empty response to remove the row
        if request.headers.get("HX-Request"):
            response = app.response_class(response="", status=200, mimetype="text/html")
            response.headers["HX-Trigger"] = "vacationDeleted"
            return response

        flash("Vacation period deleted successfully!", "success")
    except Exception as e:
        if request.headers.get("HX-Request"):
            return f'<div class="alert alert-danger">Error: {str(e)}</div>', 500
        flash(f"Error deleting vacation: {str(e)}", "error")

    return redirect(url_for("my_vacations"))


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template("change_password.html")

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("change_password.html")

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT password_hash FROM user WHERE id = ?", (current_user.id,)
                )
                user_data = cursor.fetchone()

                if not check_password_hash(
                    user_data["password_hash"], current_password
                ):
                    flash("Current password is incorrect.", "error")
                    return render_template("change_password.html")

                # If password reset is required, enforce different password
                if current_user.password_reset_required and current_password == new_password:
                    flash("You must choose a different password when a password reset is required.", "error")
                    return render_template("change_password.html")

                new_password_hash = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE user SET password_hash = ?, password_reset_required = 0 WHERE id = ?",
                    (new_password_hash, current_user.id),
                )
                conn.commit()

                flash("Password changed successfully!", "success")
                return redirect(url_for("my_vacations"))
        except Exception as e:
            flash(f"Error changing password: {str(e)}", "error")

    return render_template("change_password.html")


def generate_random_password(length=12):
    """Generate a random password with letters, digits, and special characters."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """Password reset for users who forgot their password."""
    if request.method == "POST":
        email = request.form["email"]

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM user WHERE mail = ?", (email,))
                user_data = cursor.fetchone()

                # Always show the same message to prevent email enumeration
                flash(
                    "If this email exists in our system, a password reset email has been sent.",
                    "info",
                )

                if user_data:
                    # Generate new random password
                    new_password = generate_random_password()
                    password_hash = generate_password_hash(new_password)

                    # Update password and set reset required flag
                    cursor.execute(
                        "UPDATE user SET password_hash = ?, password_reset_required = 1 WHERE mail = ?",
                        (password_hash, email),
                    )
                    conn.commit()

                    # Send password reset email
                    email_sent = email_service.send_password_reset_email(
                        email, new_password
                    )

                    if email_sent:
                        logging.info(f"Password reset email sent to: {email}")
                    else:
                        logging.error(
                            f"Failed to send password reset email to: {email}"
                        )
                        # Don't reveal the failure to the user for security

                return redirect(url_for("login"))

        except Exception as e:
            logging.error(f"Error processing password reset: {str(e)}")
            flash(
                "An error occurred while processing your request. Please try again.",
                "error",
            )

    return render_template("reset_password.html")


@app.route("/forgot_password")
def forgot_password():
    """Redirect to reset password page."""
    return redirect(url_for("reset_password"))


if __name__ == "__main__":
    app.run(
        debug=True,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
