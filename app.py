from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import mysql.connector
import os
from werkzeug.utils import secure_filename
from decimal import Decimal
import sys


# Flask App & Mail
app = Flask(__name__)
app.secret_key = 'secret123'

# MAIL CONFIG
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'thakuraashik27@gmail.com'
app.config['MAIL_PASSWORD'] = 'hjvcmjbsdynldohr'
app.config['MAIL_DEFAULT_SENDER'] = 'thakuraashik27@gmail.com'
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.secret_key)

# Database connection function - NOT connecting at module level
def get_db_connection():
    """Create a new database connection"""
    try:
        return mysql.connector.connect(
            host="24071256.tbcstudentserver.com",
            user="sacstrsx_24071256",
            password="wP]]9YuH;?n3R{UI",
            database="sacstrsx_24071256",
            port=3306,
            connection_timeout=30,
            buffered=True
        )
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Initialize database connections lazily
db = None

def get_db():
    """Get database connection (lazy initialization)"""
    global db
    if db is None or not db.is_connected():
        db = get_db_connection()
    return db

# profile for the users and admin
@app.context_processor
def inject_user():
    """
    Injects user info into all templates
    """
    if 'loggedin' in session:
        username = session.get('username', 'User')
        role = session.get('role', 'user')
        
        # Default profile pic
        profile_pic = 'images/default.jpg'
        
        # Try to get actual profile pic from database
        user_id = session.get('id')
        if user_id:
            db_conn = get_db()
            if db_conn:
                cursor = db_conn.cursor(dictionary=True)
                try:
                    cursor.execute("SELECT profile_picture FROM user_profile WHERE user_id=%s", (user_id,))
                    profile = cursor.fetchone()
                    if profile and profile.get('profile_picture'):
                        # Ensure we use the correct path
                        profile_pic = profile['profile_picture']
                        # If it's empty or null, use default
                        if not profile_pic or profile_pic == '':
                            profile_pic = 'images/default.jpg'
                except Exception as e:
                    print(f"Error fetching profile picture: {e}")
                finally:
                    cursor.close()
        
        return {
            'loggedin': True,
            'username': username,
            'role': role,
            'profile_pic': profile_pic
        }
    
    return {
        'loggedin': False,
        'username': None,
        'role': None,
        'profile_pic': 'images/default.jpg'
    }

#home
@app.route('/')
def home():
    search_msg = session.pop('search_msg', None)
    return render_template('home.html', search_msg=search_msg)

#about
@app.route('/about')
def about():
    return render_template('about.html')

#contact
@app.route('/contact')
def contact():
    return render_template('contact.html')

#blog
@app.route('/blog')
def blog():
    return render_template('blog.html')

# ------------------ Signin ------------------
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if 'loggedin' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))

    msg = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            msg = 'All fields are required!'
            return render_template('signin.html', msg=msg)

        db_conn = get_db()
        if db_conn is None:
            msg = 'Database connection error. Please try again later.'
            return render_template('signin.html', msg=msg)

        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE username=%s AND status=1", (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                # DEBUG: Print what we're storing
                print(f"DEBUG SIGNIN: Logging in user: {user['username']} (ID: {user['id']})")
                
                # SESSION
                session['loggedin'] = True
                session['id'] = user['id']
                session['username'] = user['username']  # Make sure this is correct
                session['role'] = user['role']
                
                # Also store firstname if available
                if user.get('firstname'):
                    session['firstname'] = user['firstname']
                
                print(f"DEBUG SIGNIN: Session stored - username: {session['username']}, id: {session['id']}")

                # ROLE BASED REDIRECT
                redirect_url = url_for('admin_dashboard') if user['role'] == 'admin' else url_for('user_dashboard')

                # COOKIE
                response = make_response(redirect(redirect_url))
                response.set_cookie('username', user['username'], max_age=60*60*24*15)
                return response
            else:
                msg = 'Invalid username or password, or account not activated!'
        finally:
            cursor.close()

    return render_template('signin.html', msg=msg)

# ------------------ Forgot Password ------------------
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ''

    if request.method == 'POST':
        email = request.form.get('email')

        db_conn = get_db()
        if db_conn is None:
            msg = 'Database connection error. Please try again later.'
            return render_template('forgot.html', msg=msg)

        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email=%s AND status=1", (email,))
            user = cursor.fetchone()

            if not user:
                msg = 'Email not found or account inactive!'
                return render_template('forgot.html', msg=msg)

            # Generate 4-digit code
            code = str(random.randint(1000, 9999))
            expiry = datetime.now() + timedelta(minutes=10)

            cursor.execute(
                "UPDATE users SET reset_code=%s, reset_expiry=%s WHERE id=%s",
                (code, expiry, user['id'])
            )
            db_conn.commit()

            # Send email
            message = Message(
                subject="Password Reset Code",
                sender=app.config['MAIL_USERNAME'],
                recipients=[email],
                body=f"Your password reset code is: {code}\nThis code expires in 10 minutes."
            )
            mail.send(message)

            return redirect(url_for('reset_password'))
        finally:
            cursor.close()

    return render_template('forgot.html', msg=msg)

# ------------------ Reset Password ------------------
@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    msg = ''

    if request.method == 'POST':
        code = request.form.get('code')
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password != confirm:
            msg = 'Passwords do not match!'
            return render_template('reset.html', msg=msg)

        db_conn = get_db()
        if db_conn is None:
            msg = 'Database connection error. Please try again later.'
            return render_template('reset.html', msg=msg)

        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id FROM users WHERE reset_code=%s AND reset_expiry > NOW()",
                (code,)
            )
            user = cursor.fetchone()

            if not user:
                msg = 'Invalid or expired code!'
                return render_template('reset.html', msg=msg)

            hashed = generate_password_hash(password)

            cursor.execute(
                "UPDATE users SET password=%s, reset_code=NULL, reset_expiry=NULL WHERE id=%s",
                (hashed, user['id'])
            )
            db_conn.commit()

            return redirect(url_for('signin'))
        finally:
            cursor.close()

    return render_template('reset.html', msg=msg)

# ------------------ Create Account ------------------
@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        privacy = request.form.get('privacy')

        # Validate all fields including privacy checkbox
        if not all([firstname, lastname, username, email, password, confirm, privacy]):
            flash("Please fill in all fields and accept the privacy policy!", "error")
            return render_template('create.html')

        # Validate privacy checkbox explicitly
        if privacy != 'on':
            flash("You must accept the Terms of Service and Privacy Policy!", "error")
            return render_template('create.html')

        # Validate password match
        if password != confirm:
            flash("Passwords do not match!", "error")
            return render_template('create.html')

        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later!", "error")
            return render_template('create.html')

        # Check if user already exists
        cursor = db_conn.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email=%s OR username=%s", (email, username))
            if cursor.fetchone():
                flash("User with this email or username already exists!", "error")
                return render_template('create.html')

            # Hash password and insert user
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (firstname, lastname, username, email, password, role, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (firstname, lastname, username, email, hashed_password, 'user', 0))
            db_conn.commit()

            # Send activation email - FIXED: Use consistent URL format
            token = serializer.dumps(email, salt='email-confirm')
            
            # IMPORTANT: Use the same URL format as your working setup
            # For local development:
            # link = url_for('activate', token=token, _external=True)
            
            # For production on your server:
            link = f"http://24071256.tbcstudentserver.com/activate/{token}"
            
            # OR if it was working before with localhost:
            # link = f"http://127.0.0.1:5000/activate/{token}"

            msg = Message("Activate Your Account", recipients=[email])
            
            # HTML email template (keep your existing template)
            msg.html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Activate Your Account</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; border-collapse: collapse; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); border-radius: 8px; overflow: hidden;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">Welcome to Our Platform!</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #333333; font-size: 24px;">Hi {firstname},</h2>
                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 16px; line-height: 1.6;">
                                Thank you for signing up! We're excited to have you on board.
                            </p>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 16px; line-height: 1.6;">
                                To complete your registration and activate your account, please click the button below:
                            </p>
                            
                            <!-- Button -->
                            <table role="presentation" style="margin: 0 auto;">
                                <tr>
                                    <td style="border-radius: 4px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                        <a href="{link}" style="display: inline-block; padding: 16px 40px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold; border-radius: 4px;">
                                            Activate Your Account
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 0 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                If the button doesn't work, copy and paste this link into your browser:
                            </p>
                            <p style="margin: 10px 0 0 0; color: #667eea; font-size: 14px; word-break: break-all;">
                                {link}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e9ecef;">
                            <p style="margin: 0 0 10px 0; color: #999999; font-size: 14px;">
                                If you didn't create an account, please ignore this email.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                © 2024 Your Company. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """
            
            # Plain text fallback
            msg.body = f"Hi {firstname},\n\nClick the link below to activate your account:\n{link}\n\nThank you!"
            
            mail.send(msg)

            flash("Account created successfully! Please check your email to activate.", "success")
            return render_template('create.html')
        finally:
            cursor.close()

    return render_template('create.html')

# ------------------ Activate Account ------------------
@app.route('/activate/<token>')
def activate(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)
    except:
        return "Activation link expired or invalid! <a href='/signin'>Back to Login</a>"

    db_conn = get_db()
    if db_conn is None:
        return "Database connection error. Please try again later. <a href='/signin'>Back to Login</a>"

    cursor = db_conn.cursor()
    try:
        cursor.execute("UPDATE users SET status=1 WHERE email=%s", (email,))
        db_conn.commit()
    finally:
        cursor.close()

    return "Account activated successfully! You can now login. <a href='/signin'>Login here</a>"
        
# ------------------ Privacy ------------------
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# ------------------ Book ------------------
@app.route('/book/<city>', methods=['GET', 'POST'])
def book(city):
    if 'loggedin' not in session:
        flash("Please login to book a room!")
        return redirect(url_for('signin'))

    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('home'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # GET BOOKING RULES FROM DATABASE
        cursor.execute('SELECT rule_name, rule_value FROM booking_rules')
        rules_rows = cursor.fetchall()
        booking_rules = {row['rule_name']: row['rule_value'] for row in rules_rows}
        
        max_booking_days = booking_rules.get('max_booking_days', 30)
        max_advance_days = booking_rules.get('max_advance_days', 90)
        
        if request.method == 'POST':
            checkin_str = request.form.get('trip-start')
            checkout_str = request.form.get('trip-end')
            guests = request.form.get('guests')

            # Validate dates
            try:
                checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d')
                checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d')
            except ValueError:
                flash("Invalid date format!")
                return redirect(url_for('book', city=city))

            if checkout_date <= checkin_date:
                flash("Check-out must be after check-in!")
                return redirect(url_for('book', city=city))

            # USE DYNAMIC MAX BOOKING DAYS
            booking_duration = (checkout_date - checkin_date).days
            if booking_duration > max_booking_days:
                flash(f"You can only book for up to {max_booking_days} days!")
                return redirect(url_for('book', city=city))
            
            # VALIDATE ADVANCE BOOKING LIMIT
            today = datetime.today()
            days_in_advance = (checkin_date - today).days
            if days_in_advance > max_advance_days:
                flash(f"You can only book up to {max_advance_days} days in advance!")
                return redirect(url_for('book', city=city))

            # Get logged-in user info
            user_id = session['id']
            cursor.execute("""
                SELECT u.firstname, u.lastname, u.username, u.email, up.fullname 
                FROM users u
                LEFT JOIN user_profile up ON u.id = up.user_id
                WHERE u.id=%s
            """, (user_id,))
            user = cursor.fetchone()

            if not user:
                flash("User not found!")
                return redirect(url_for('book', city=city))

            # Redirect to confirm_booking page
            return redirect(url_for(
                'confirm_booking',
                checkin=checkin_str,
                checkout=checkout_str,
                guests=guests,
                firstname=user['firstname'],
                lastname=user['lastname'],
                username=user['username'],
                email=user['email'],
                fullname=user['fullname'] if user['fullname'] else f"{user['firstname']} {user['lastname']}",
                location=city.title()
            ))

        # GET request: Calculate date ranges using dynamic rules
        today = datetime.today().strftime('%Y-%m-%d')
        max_date = (datetime.today() + timedelta(days=max_advance_days)).strftime('%Y-%m-%d')

        return render_template('book.html', 
                             today=today, 
                             max_date=max_date, 
                             city=city,
                             max_booking_days=max_booking_days,
                             max_advance_days=max_advance_days)
    finally:
        cursor.close()

# ------------------ User Booking ------------------
@app.route('/user/bookings')
def user_bookings():
    if 'loggedin' not in session or session['role'] != 'user':
        return redirect(url_for('signin'))

    user_id = session['id']
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('user_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.booking_id, b.check_in, b.check_out, r.room_name, h.hotel_name, h.location, r.price
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            JOIN hotels h ON r.hotel_id = h.hotel_id
            WHERE b.user_id=%s
            ORDER BY b.check_in DESC
        """, (user_id,))
        bookings = cursor.fetchall()
        
        # Calculate total price for each booking
        for booking in bookings:
            try:
                # Handle both date objects and strings
                if isinstance(booking['check_in'], str):
                    check_in = datetime.strptime(booking['check_in'], '%Y-%m-%d')
                    check_out = datetime.strptime(booking['check_out'], '%Y-%m-%d')
                else:
                    check_in = booking['check_in']
                    check_out = booking['check_out']
                
                num_days = (check_out - check_in).days
                booking['total_price'] = booking['price'] * num_days
            except Exception as e:
                print(f"Error calculating price: {e}")
                booking['total_price'] = booking['price']
        
        return render_template('user/user_bookings.html', bookings=bookings)
    finally:
        cursor.close()

# ------------------ Cancellation charge calculation ------------------
def calculate_cancellation_charge(check_in_date, booking_price):
    """
    Calculate cancellation charges based on days until check-in.
    Returns: (charge_amount, charge_percentage, days_until_checkin)
    """
    today = datetime.today().date()
    if isinstance(check_in_date, str):
        check_in_date = datetime.strptime(check_in_date, '%Y-%m-%d').date()
    elif isinstance(check_in_date, datetime):
        check_in_date = check_in_date.date()
    
    days_until_checkin = (check_in_date - today).days
    
    if days_until_checkin >= 60:
        # No charges
        return Decimal('0.00'), 0, days_until_checkin
    elif 30 <= days_until_checkin < 60:
        # 50% charges
        charge = (Decimal(str(booking_price)) * Decimal('0.50')).quantize(Decimal('0.01'))
        return charge, 50, days_until_checkin
    else:
        # 100% charges (within 30 days)
        charge = Decimal(str(booking_price)).quantize(Decimal('0.01'))
        return charge, 100, days_until_checkin

# ------------------ User cancel booking ------------------
@app.route('/user/cancel-booking/<int:booking_id>', methods=['GET', 'POST'])
def cancel_booking(booking_id):
    if 'loggedin' not in session or session['role'] != 'user':
        return redirect(url_for('signin'))

    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('user_bookings'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Get booking details including user email and calculate total price
        cursor.execute("""
            SELECT b.booking_id, b.room_id, b.customer_name, b.check_in, b.check_out,
                   r.room_name, r.price, h.hotel_name, h.location,
                   u.email, u.username,
                   DATEDIFF(b.check_out, b.check_in) as num_days
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            JOIN hotels h ON r.hotel_id = h.hotel_id
            JOIN users u ON b.user_id = u.id
            WHERE b.booking_id=%s AND b.user_id=%s
        """, (booking_id, session['id']))
        
        booking = cursor.fetchone()
        
        if not booking:
            flash("Booking not found or cannot be cancelled.", "error")
            return redirect(url_for('user_bookings'))

        # Calculate total booking price
        total_price = booking['price'] * booking['num_days']
        
        # Calculate cancellation charges
        charge_amount, charge_percentage, days_until = calculate_cancellation_charge(
            booking['check_in'], 
            total_price
        )
        
        refund_amount = total_price - charge_amount

        # Handle GET request - show cancellation form
        if request.method == 'GET':
            return render_template('user/cancel_booking_form.html', 
                                 booking=booking, 
                                 charge_amount=charge_amount,
                                 charge_percentage=charge_percentage,
                                 refund_amount=refund_amount,
                                 total_price=total_price,
                                 days_until=days_until)

        # Handle POST request - process cancellation
        cancellation_reason = request.form.get('cancellation_reason', '').strip()
        
        if not cancellation_reason:
            flash("Please provide a reason for cancellation.", "error")
            return redirect(url_for('cancel_booking', booking_id=booking_id))

        # Record cancellation in database
        cursor.execute("""
            INSERT INTO booking_cancellations 
            (booking_id, user_id, cancellation_date, days_before_checkin, 
             booking_amount, cancellation_charge, refund_amount, cancellation_reason)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
        """, (booking_id, session['id'], days_until, total_price, charge_amount, refund_amount, cancellation_reason))
        
        # Increase room availability
        cursor.execute("UPDATE rooms SET room_count = room_count + 1 WHERE room_id=%s", (booking['room_id'],))
        
        # Delete booking
        cursor.execute("DELETE FROM booking WHERE booking_id=%s", (booking_id,))
        
        db_conn.commit()

        # Send Beautiful Cancellation Email
        try:
            msg = Message(
                subject="Booking Cancellation Confirmation - World Hotel",
                recipients=[booking['email']],
                sender=app.config['MAIL_USERNAME']
            )
            
            # Determine charge color and message
            if charge_percentage == 0:
                charge_color = "#28a745"
                charge_message = "Good news! Since you cancelled more than 60 days before check-in, no cancellation charges apply."
            elif charge_percentage == 50:
                charge_color = "#ffc107"
                charge_message = "As per our cancellation policy, 50% charges apply for cancellations between 30-60 days before check-in."
            else:
                charge_color = "#dc3545"
                charge_message = "As per our cancellation policy, full charges apply for cancellations within 30 days of check-in."
            
            msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .cancel-icon {{
            font-size: 50px;
            margin-bottom: 10px;
        }}
        .content {{
            padding: 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        .booking-details {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .booking-details h2 {{
            color: #dc3545;
            margin-top: 0;
            font-size: 20px;
            border-bottom: 2px solid #dc3545;
            padding-bottom: 10px;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: 600;
            color: #555;
        }}
        .detail-value {{
            color: #333;
        }}
        .financial-section {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .financial-section h3 {{
            margin-top: 0;
            color: #856404;
        }}
        .refund-amount {{
            font-size: 28px;
            font-weight: bold;
            color: #28a745;
            text-align: center;
            margin: 15px 0;
        }}
        .charge-badge {{
            background: {charge_color};
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            display: inline-block;
            font-weight: 600;
        }}
        .alert-box {{
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .reason-box {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #6c757d;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        table td {{
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }}
        table tr:last-child td {{
            border-bottom: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="cancel-icon">❌</div>
            <h1>Booking Cancelled</h1>
        </div>
        
        <div class="content">
            <p class="greeting">Dear {booking['customer_name']},</p>
            
            <p class="message">
                Your booking has been successfully cancelled. We're sorry to see you go, but we hope to serve you again in the future.
            </p>
            
            <div class="booking-details">
                <h2>📋 Cancelled Booking Details</h2>
                
                <div class="detail-row">
                    <span class="detail-label">🆔 Booking ID:</span>
                    <span class="detail-value">#{booking_id}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">🏨 Hotel:</span>
                    <span class="detail-value">{booking['hotel_name']}, {booking['location']}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">🛏️ Room:</span>
                    <span class="detail-value">{booking['room_name']}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">📅 Check-in Date:</span>
                    <span class="detail-value">{booking['check_in'].strftime('%A, %B %d, %Y')}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">📅 Check-out Date:</span>
                    <span class="detail-value">{booking['check_out'].strftime('%A, %B %d, %Y')}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">⏰ Days Until Check-in:</span>
                    <span class="detail-value">{days_until} days</span>
                </div>
            </div>
            
            <div class="reason-box">
                <strong>📝 Cancellation Reason:</strong><br>
                <p style="margin: 10px 0 0 0; color: #666;">{cancellation_reason}</p>
            </div>
            
            <div class="financial-section">
                <h3>💰 Financial Summary</h3>
                
                <table>
                    <tr>
                        <td style="font-weight: 600;">Original Booking Amount:</td>
                        <td style="text-align: right;">£{total_price:.2f}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: 600;">Cancellation Charge ({charge_percentage}%):</td>
                        <td style="text-align: right; color: #dc3545;">£{charge_amount:.2f}</td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td style="font-weight: 600; font-size: 18px;">Refund Amount:</td>
                        <td style="text-align: right; font-weight: bold; font-size: 18px; color: #28a745;">£{refund_amount:.2f}</td>
                    </tr>
                </table>
                
                <center>
                    <span class="charge-badge">{charge_percentage}% Cancellation Fee</span>
                </center>
            </div>
            
            <div class="alert-box">
                <strong>ℹ️ Cancellation Policy:</strong><br>
                {charge_message}
            </div>
            
            <div class="alert-box">
                <strong>💳 Refund Processing:</strong><br>
                Your refund of <strong>£{refund_amount:.2f}</strong> will be processed within 5-7 business days and credited back to your original payment method.
            </div>
        </div>
        
        <div class="footer">
            <p>Thank you for considering <strong>World Hotel</strong>!</p>
            <p>We hope to welcome you in the future. If you have any questions, please contact us at 
                <a href="mailto:support@worldhotel.com">support@worldhotel.com</a>
            </p>
            <p style="margin-top: 20px; font-size: 12px; color: #999;">
                This is an automated email. Please do not reply directly to this message.
            </p>
        </div>
    </div>
</body>
</html>
            """
            mail.send(msg)
        except Exception as e:
            print(f"Error sending cancellation email: {e}")

        flash(f"Booking cancelled successfully! Cancellation charge: £{charge_amount:.2f}, Refund: £{refund_amount:.2f}", "success")
        return redirect(url_for('user_bookings'))
    finally:
        cursor.close()

# ------------------ Search ------------------
@app.route('/search', methods=['GET'])
def search():
    city = request.args.get('city', '').lower().strip()
    if not city:
        return redirect(url_for('home'))

    cities = [
        'aberdeen','belfast','birmingham','bristol','cardiff','edinburgh',
        'glasgow','london','manchester','newcastle','norwich','nottingham',
        'oxford','plymouth','swansea','bournemouth','kent'
    ]

    if city in cities:
        return redirect(url_for('location', city=city))
    else:
        session['search_msg'] = f"No hotels found in {city.title()}"
        return redirect(url_for('home'))

# ------------------ Location ------------------
@app.route('/location/<city>')
def location(city):
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('home'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Fetch hotels in this city/location
        cursor.execute("SELECT hotel_id, hotel_name FROM hotels WHERE LOWER(location)=LOWER(%s) LIMIT 1", (city,))
        hotel = cursor.fetchone()
        
        rooms_data = []
        
        if hotel:
            # Fetch all rooms for this hotel WITH IMAGES - ADD 'images' to SELECT
            cursor.execute("""
                SELECT room_name, price, peak_season, status, room_count, images
                FROM rooms 
                WHERE hotel_id=%s
                ORDER BY price ASC
            """, (hotel['hotel_id'],))
            rooms_data = cursor.fetchall()
        
        # Pass city and rooms data to template
        return render_template(f'location/{city}.html', city=city, rooms=rooms_data)
    finally:
        cursor.close()

# ------------------ User Dashboard ------------------
@app.route('/user/dashboard')
def user_dashboard():
    if 'loggedin' in session and session['role'] == 'user':
        user_id = session['id']
        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('signin'))

        cursor = db_conn.cursor(dictionary=True)
        try:
            # Get profile picture
            cursor.execute("SELECT profile_picture FROM user_profile WHERE user_id=%s", (user_id,))
            profile = cursor.fetchone()
            
            # Get username from session (what they typed when logging in)
            username = session.get('username', 'User')
            
            # Determine profile_pic
            if profile and profile.get('profile_picture'):
                profile_pic = profile['profile_picture']
            else:
                profile_pic = 'images/default.jpg'
            
            # PASS THE 3 VARIABLES YOUR TEMPLATE NEEDS
            return render_template('user/user_dashboard.html', 
                                 username=username,            # Required for welcome message
                                 profile_pic=profile_pic,      # Required for profile picture  
                                 role=session.get('role', 'user'))  # Required for role display
        finally:
            cursor.close()
    return redirect(url_for('signin'))

# ------------------ Edit Profile ------------------
@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'id' not in session:
        return redirect(url_for('signin'))

    user_id = session['id']
    role = session.get('role')
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('signin'))
    
    cursor = db_conn.cursor(dictionary=True)

    if request.method == 'POST':
        fullname = request.form.get('fullname')
        file = request.files.get('profile_picture')
        
        # Password fields
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Get current profile info
        cursor.execute("SELECT fullname, profile_picture FROM user_profile WHERE user_id=%s", (user_id,))
        profile = cursor.fetchone()
        
        # FIXED PROFILE PICTURE LOGIC
        profile_picture_path = None
        
        if file and file.filename:
            # User uploaded a new image - use it
            filename = secure_filename(file.filename)
            folder = os.path.join('static/uploads', f'{role}')
            os.makedirs(folder, exist_ok=True)
            file_path = os.path.join(folder, filename)
            file.save(file_path)
            profile_picture_path = f'uploads/{role}/{filename}'
        elif profile and profile.get('profile_picture'):
            # No new file uploaded, but user has existing profile picture - keep it
            profile_picture_path = profile['profile_picture']
        else:
            # No file uploaded and no existing picture - use default
            profile_picture_path = 'images/default.jpg'

        # Handle password change if provided
        if current_password:
            # Verify current password
            cursor.execute("SELECT password FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found!', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            # Check if user has a password set
            if not user.get('password'):
                flash('Your account does not have a password set. Please contact admin.', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            # Verify current password
            if not check_password_hash(user['password'], current_password):
                flash('Current password is incorrect!', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            # Validate new password
            if not new_password:
                flash('New password is required!', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long!', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            if new_password != confirm_password:
                flash('New passwords do not match!', 'error')
                cursor.close()
                return redirect(url_for('edit_profile'))
            
            # Update password
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, user_id))
            flash('Password updated successfully!', 'success')
        
        # If current password is empty but new password is provided
        elif new_password or confirm_password:
            flash('Please enter your current password to change your password.', 'error')
            cursor.close()
            return redirect(url_for('edit_profile'))

        # Update or Insert profile information
        if profile:
            # Update existing profile
            cursor.execute("UPDATE user_profile SET fullname=%s, profile_picture=%s WHERE user_id=%s",
                           (fullname, profile_picture_path, user_id))
        else:
            # Insert new profile (first time user edits profile)
            cursor.execute("INSERT INTO user_profile (user_id, fullname, profile_picture) VALUES (%s, %s, %s)",
                           (user_id, fullname, profile_picture_path))
        
        db_conn.commit()
        cursor.close()

        flash('Profile updated successfully!', 'success')
        
        # Redirect based on role
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))

    # GET request - display current profile
    cursor.execute("SELECT fullname, profile_picture FROM user_profile WHERE user_id=%s", (user_id,))
    profile = cursor.fetchone()
    
    # Get username from users table to use as default for fullname
    cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    username = user['username'] if user else ''
    
    cursor.close()
    return render_template('edit_profile.html', profile=profile, username=username)

# ------------------ Logout ------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))

# ------------------ Booking by admin ------------------
@app.route('/admin/my-bookings')
def admin_my_bookings():
    try:
        if 'loggedin' not in session or session['role'] != 'admin':
            return redirect(url_for('signin'))

        user_id = session['id']
        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('admin_dashboard'))

        cursor = db_conn.cursor(dictionary=True)

        try:
            # Get admin's personal bookings
            cursor.execute("""
                SELECT 
                    b.booking_id,
                    h.hotel_name,
                    r.room_name,
                    b.booking_date,
                    b.check_in,
                    b.check_out,
                    (r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_price
                FROM booking b
                INNER JOIN rooms r ON b.room_id = r.room_id
                INNER JOIN hotels h ON r.hotel_id = h.hotel_id
                WHERE b.user_id = %s
                ORDER BY b.booking_date DESC
            """, (user_id,))
            admin_bookings = cursor.fetchall()

            return render_template('admin/my_bookings.html', admin_bookings=admin_bookings)
        finally:
            cursor.close()

    except Exception as e:
        print(f"My bookings error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

# ------------------ Cancel Booking by admin ------------------
@app.route('/admin/cancel-booking/<int:booking_id>', methods=['GET', 'POST'])
def admin_cancel_booking(booking_id):
    try:
        if 'loggedin' not in session or session['role'] != 'admin':
            return redirect(url_for('signin'))

        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('admin_my_bookings'))

        cursor = db_conn.cursor(dictionary=True)

        try:
            # Get booking details
            cursor.execute("""
                SELECT b.booking_id, b.room_id, b.user_id, b.customer_name, b.check_in, b.check_out,
                       r.room_name, r.price, h.hotel_name, h.location,
                       u.email, u.username,
                       DATEDIFF(b.check_out, b.check_in) as num_days
                FROM booking b
                JOIN rooms r ON b.room_id = r.room_id
                JOIN hotels h ON r.hotel_id = h.hotel_id
                JOIN users u ON b.user_id = u.id
                WHERE b.booking_id=%s AND b.user_id=%s
            """, (booking_id, session['id']))
            
            booking = cursor.fetchone()

            if not booking:
                flash('Booking not found or you do not have permission to cancel it.', 'error')
                return redirect(url_for('admin_my_bookings'))

            # Calculate total and cancellation charges
            total_price = booking['price'] * booking['num_days']
            charge_amount, charge_percentage, days_until = calculate_cancellation_charge(
                booking['check_in'], 
                total_price
            )
            refund_amount = total_price - charge_amount

            # Handle GET request - show cancellation form
            if request.method == 'GET':
                return render_template('admin/cancel_booking_form.html', 
                                     booking=booking, 
                                     charge_amount=charge_amount,
                                     charge_percentage=charge_percentage,
                                     refund_amount=refund_amount,
                                     total_price=total_price,
                                     days_until=days_until)

            # Handle POST request - process cancellation
            cancellation_reason = request.form.get('cancellation_reason', '').strip()
            
            if not cancellation_reason:
                flash("Please provide a reason for cancellation.", "error")
                return redirect(url_for('admin_cancel_booking', booking_id=booking_id))

            # Record cancellation
            cursor.execute("""
                INSERT INTO booking_cancellations 
                (booking_id, user_id, cancellation_date, days_before_checkin, 
                 booking_amount, cancellation_charge, refund_amount, cancellation_reason)
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
            """, (booking_id, session['id'], days_until, total_price, charge_amount, refund_amount, cancellation_reason))

            # Increase room availability
            cursor.execute("UPDATE rooms SET room_count = room_count + 1 WHERE room_id = %s", (booking['room_id'],))
            
            # Delete the booking
            cursor.execute("DELETE FROM booking WHERE booking_id = %s", (booking_id,))
            
            db_conn.commit()

            # Send cancellation email
            try:
                msg = Message(
                    subject="Booking Cancellation Confirmation - World Hotel",
                    recipients=[booking['email']],
                    sender=app.config['MAIL_USERNAME']
                )
                
                msg.body = f"""
Dear {booking['customer_name']},

Your booking has been cancelled.

Cancellation Details:
- Booking ID: {booking_id}
- Hotel: {booking['hotel_name']}, {booking['location']}
- Room: {booking['room_name']}
- Check-in Date: {booking['check_in'].strftime('%Y-%m-%d')}
- Check-out Date: {booking['check_out'].strftime('%Y-%m-%d')}
- Days until Check-in: {days_until}

Cancellation Reason:
{cancellation_reason}

Financial Details:
- Original Booking Amount: £{total_price:.2f}
- Cancellation Charge ({charge_percentage}%): £{charge_amount:.2f}
- Refund Amount: £{refund_amount:.2f}

"""
                if charge_percentage == 0:
                    msg.body += "Good news! Since the cancellation is more than 60 days before check-in, no cancellation charges apply.\n"
                elif charge_percentage == 50:
                    msg.body += "As per our cancellation policy, 50% charges apply for cancellations between 30-60 days before check-in.\n"
                else:
                    msg.body += "As per our cancellation policy, full charges apply for cancellations within 30 days of check-in.\n"
                
                msg.body += "\nThe refund will be processed within 5-7 business days.\n\nThank you for choosing World Hotel."
                
                mail.send(msg)
            except Exception as e:
                print(f"Error sending cancellation email: {e}")

            flash(f'Booking cancelled successfully! Cancellation charge: £{charge_amount:.2f}, Refund: £{refund_amount:.2f}', 'success')
            return redirect(url_for('admin_my_bookings'))
        finally:
            cursor.close()

    except Exception as e:
        print(f"Cancel booking error: {e}")
        flash('Error cancelling booking.', 'error')
        return redirect(url_for('admin_my_bookings'))
    
# ------------------ Admin to see all Booking ------------------
@app.route('/admin/all-bookings')
def admin_all_bookings():
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Fetch all ACTIVE bookings (excluding cancelled ones)
        cursor.execute("""
            SELECT 
                b.booking_id,
                b.user_id,
                b.room_id,
                b.check_in,
                b.check_out,
                b.customer_name,
                b.booking_date,
                u.username,
                u.email,
                h.hotel_name,
                h.location,
                r.room_name,
                r.price,
                DATEDIFF(b.check_out, b.check_in) as num_days,
                (r.price * DATEDIFF(b.check_out, b.check_in)) as total_price
            FROM booking b
            JOIN users u ON b.user_id = u.id
            JOIN rooms r ON b.room_id = r.room_id
            JOIN hotels h ON r.hotel_id = h.hotel_id
            WHERE b.booking_id NOT IN (
                SELECT booking_id FROM booking_cancellations
            )
            ORDER BY b.booking_date DESC
        """)
        
        bookings = cursor.fetchall()
        
        # Get booking statistics (only active bookings)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COALESCE(SUM(r.price * DATEDIFF(b.check_out, b.check_in)), 0) as total_revenue
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            WHERE b.booking_id NOT IN (
                SELECT booking_id FROM booking_cancellations
            )
        """)
        
        stats = cursor.fetchone()
        
        return render_template('admin/admin_all_bookings.html', 
                             bookings=bookings,
                             stats=stats)
    except Exception as e:
        print(f"Error fetching bookings: {e}")
        flash("Error fetching bookings. Please try again later.", "error")
        return render_template('admin/admin_all_bookings.html', 
                             bookings=[], 
                             stats={'total_bookings': 0, 'total_revenue': 0})
    finally:
        cursor.close()

#admin cancel all booking
@app.route('/admin/cancel-booking-management/<int:booking_id>', methods=['GET', 'POST'])
def admin_cancel_booking_management(booking_id):
    if 'loggedin' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('signin'))
     
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_all_bookings'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Get booking details including user information
        cursor.execute("""
            SELECT b.booking_id, b.room_id, b.user_id, b.customer_name, b.check_in, b.check_out,
                   r.room_name, r.price, h.hotel_name, h.location,
                   u.email, u.username,
                   DATEDIFF(b.check_out, b.check_in) as num_days
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            JOIN hotels h ON r.hotel_id = h.hotel_id
            JOIN users u ON b.user_id = u.id
            WHERE b.booking_id = %s
        """, (booking_id,))
        
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found!', 'error')
            return redirect(url_for('admin_all_bookings'))
        
        # Calculate total price
        total_price = booking['price'] * booking['num_days']
        
        # FOR ADMIN CANCELLATIONS - NO CHARGES AT ALL
        charge_amount = Decimal('0.00')  # NO CHARGES
        charge_percentage = 0  # NO CHARGES
        refund_amount = total_price  # FULL REFUND
        
        # Calculate days until check-in for record keeping only
        today = datetime.today().date()
        if isinstance(booking['check_in'], str):
            check_in_date = datetime.strptime(booking['check_in'], '%Y-%m-%d').date()
        else:
            check_in_date = booking['check_in'].date()
        days_until = (check_in_date - today).days

        # Handle GET request - show cancellation form
        if request.method == 'GET':
            return render_template('admin/cancel_booking_management_form.html', 
                                 booking=booking, 
                                 charge_amount=charge_amount,
                                 charge_percentage=charge_percentage,
                                 refund_amount=refund_amount,
                                 total_price=total_price,
                                 days_until=days_until)

        # Handle POST request - process cancellation
        cancellation_reason = request.form.get('cancellation_reason', '').strip()
        
        if not cancellation_reason:
            flash("Please provide a reason for cancellation.", "error")
            return redirect(url_for('admin_cancel_booking_management', booking_id=booking_id))

        # Record cancellation with admin flag - NO CHARGES
        cursor.execute("""
            INSERT INTO booking_cancellations 
            (booking_id, user_id, cancellation_date, days_before_checkin, 
             booking_amount, cancellation_charge, refund_amount, cancellation_reason, cancelled_by_admin)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, 1)
        """, (booking_id, booking['user_id'], days_until, total_price, charge_amount, refund_amount, cancellation_reason))
        
        # Increase room availability
        cursor.execute("UPDATE rooms SET room_count = room_count + 1 WHERE room_id = %s", (booking['room_id'],))
        
        # Delete booking
        cursor.execute("DELETE FROM booking WHERE booking_id = %s", (booking_id,))
        
        db_conn.commit()
        
        # Verify deletion was successful
        cursor.execute("SELECT booking_id FROM booking WHERE booking_id = %s", (booking_id,))
        if cursor.fetchone():
            flash('Error: Booking was not deleted properly!', 'error')
            return redirect(url_for('admin_all_bookings'))

        # Send Cancellation Email (Admin-initiated) - NO CHARGES
        try:
            msg = Message(
                subject="Booking Cancellation Notice - World Hotel",
                recipients=[booking['email']],
                sender=app.config['MAIL_USERNAME']
            )
            
            # Plain text version (simple and reliable)
            msg.body = f"""
Booking Cancellation Notice - World Hotel

Dear {booking['customer_name']},

IMPORTANT NOTICE: Your booking has been cancelled by our administration team.

We regret to inform you that your booking has been cancelled. 
This cancellation was initiated by our management team.

CANCELLED BOOKING DETAILS:
• Booking ID: #{booking_id}
• Hotel: {booking['hotel_name']}, {booking['location']}
• Room: {booking['room_name']}
• Check-in Date: {booking['check_in'].strftime('%A, %B %d, %Y')}
• Check-out Date: {booking['check_out'].strftime('%A, %B %d, %Y')}
• Days Until Check-in: {days_until} days

REASON FOR CANCELLATION:
{cancellation_reason}

FINANCIAL SUMMARY:
• Original Booking Amount: £{total_price:.2f}
• Cancellation Charge: £0.00 (No charges applied)
• Full Refund Amount: £{total_price:.2f}

IMPORTANT INFORMATION:
As this cancellation was initiated by our administration team, 
no cancellation charges will be applied. A full refund will be processed.

REFUND PROCESSING:
A full refund of £{total_price:.2f} will be processed within 
5-7 business days and credited back to your original payment method.

NEED ASSISTANCE?
If you have any questions or concerns about this cancellation, 
please contact our support team at support@worldhotel.com or call +44 123 456 7890.

We apologize for any inconvenience caused.

Thank you,
World Hotel Team
            """
            
            # HTML version (simple and clean)
            msg.html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif;">
    <h2>Booking Cancellation Notice - World Hotel</h2>
    
    <p><strong>Dear {booking['customer_name']},</strong></p>
    
    <div style="background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">
        <strong>⚠️ IMPORTANT NOTICE:</strong> Your booking has been cancelled by our administration team.
    </div>
    
    <p>We regret to inform you that your booking has been cancelled. This cancellation was initiated by our management team.</p>
    
    <h3>Cancelled Booking Details</h3>
    <ul>
        <li><strong>Booking ID:</strong> #{booking_id}</li>
        <li><strong>Hotel:</strong> {booking['hotel_name']}, {booking['location']}</li>
        <li><strong>Room:</strong> {booking['room_name']}</li>
        <li><strong>Check-in Date:</strong> {booking['check_in'].strftime('%A, %B %d, %Y')}</li>
        <li><strong>Check-out Date:</strong> {booking['check_out'].strftime('%A, %B %d, %Y')}</li>
        <li><strong>Days Until Check-in:</strong> {days_until} days</li>
    </ul>
    
    <h3>Reason for Cancellation</h3>
    <p><em>{cancellation_reason}</em></p>
    
    <h3>Financial Summary</h3>
    <table style="border-collapse: collapse; width: 100%;">
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">Original Booking Amount:</td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd; text-align: right;">£{total_price:.2f}</td>
        </tr>
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">Cancellation Charge:</td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd; text-align: right; color: green;">£0.00</td>
        </tr>
        <tr style="background: #d4edda;">
            <td style="padding: 10px; font-weight: bold;">Full Refund Amount:</td>
            <td style="padding: 10px; font-weight: bold; text-align: right; color: green;">£{total_price:.2f}</td>
        </tr>
    </table>
    
    <p style="background: #28a745; color: white; padding: 8px; border-radius: 4px; display: inline-block;">
        No Charges Applied
    </p>
    
    <div style="background: #e3f2fd; padding: 10px; border-left: 4px solid #2196F3; margin: 10px 0;">
        <strong>Important Information:</strong><br>
        As this cancellation was initiated by our administration team, no cancellation charges will be applied. A full refund will be processed.
    </div>
    
    <div style="background: #e3f2fd; padding: 10px; border-left: 4px solid #2196F3; margin: 10px 0;">
        <strong>Refund Processing:</strong><br>
        A full refund of <strong>£{total_price:.2f}</strong> will be processed within 5-7 business days.
    </div>
    
    <p><strong>Need Assistance?</strong><br>
    Contact support: <a href="mailto:support@worldhotel.com">support@worldhotel.com</a> or call +44 123 456 7890</p>
    
    <p>We apologize for any inconvenience caused.</p>
    
    <hr>
    <p><em>World Hotel Team</em></p>
</body>
</html>"""
            
            mail.send(msg)
            print(f"Email sent successfully to {booking['email']}")
        except Exception as e:
            print(f"Error sending cancellation email: {e}")
            # Don't flash error to user, just log it

        flash(f'Booking cancelled successfully! No cancellation charges applied. Full refund: £{refund_amount:.2f}', 'success')
        return redirect(url_for('admin_all_bookings'))
    
    except Exception as e:
        db_conn.rollback()
        flash(f'Error cancelling booking: {str(e)}', 'error')
        return redirect(url_for('admin_all_bookings'))
    finally:
        cursor.close()

# ------------------ admin to see cancel history ------------------
@app.route('/admin/cancellation-history')
def cancellation_history():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                bc.*,
                u.username,
                u.email
            FROM booking_cancellations bc
            JOIN users u ON bc.user_id = u.id
            ORDER BY bc.cancellation_date DESC
        """)
        
        cancellations = cursor.fetchall()
        return render_template('admin/cancellation_history.html', cancellations=cancellations)
    finally:
        cursor.close()

# ------------------ Monthly report ------------------
@app.route('/admin/reports/monthly', methods=['GET', 'POST'])
def monthly_report():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Get selected month/year from form, default to current month
        selected_month = request.args.get('month') or request.form.get('month')
        selected_year = request.args.get('year') or request.form.get('year')
        
        # Default to current month if not provided
        from datetime import datetime
        if not selected_month or not selected_year:
            now = datetime.now()
            selected_month = str(now.month)
            selected_year = str(now.year)
        
        # Get available months (all months that have bookings)
        cursor.execute("""
            SELECT DISTINCT 
                YEAR(booking_date) as year,
                MONTH(booking_date) as month,
                DATE_FORMAT(booking_date, '%%M %%Y') as month_name
            FROM booking
            ORDER BY year DESC, month DESC
        """)
        available_months = cursor.fetchall()
        
        # Get data for selected month
        cursor.execute("""
            SELECT 
                DATE_FORMAT(b.booking_date, '%%Y-%%m') as month,
                DATE_FORMAT(b.booking_date, '%%M %%Y') as month_name,
                COUNT(*) as total_bookings,
                SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_revenue,
                AVG(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as avg_booking_value,
                MIN(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as min_booking_value,
                MAX(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as max_booking_value
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            WHERE MONTH(b.booking_date) = %s AND YEAR(b.booking_date) = %s
            GROUP BY month, month_name
        """, (selected_month, selected_year))
        monthly_summary = cursor.fetchone()
        
        # Get daily breakdown for selected month
        cursor.execute("""
            SELECT 
                DATE(b.booking_date) as booking_day,
                COUNT(*) as daily_bookings,
                SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as daily_revenue
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            WHERE MONTH(b.booking_date) = %s AND YEAR(b.booking_date) = %s
            GROUP BY booking_day
            ORDER BY booking_day
        """, (selected_month, selected_year))
        daily_data = cursor.fetchall()
        
        # Get bookings by hotel for selected month
        cursor.execute("""
            SELECT 
                h.hotel_name,
                h.location,
                COUNT(b.booking_id) as bookings,
                SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as revenue
            FROM booking b
            JOIN rooms r ON b.room_id = r.room_id
            JOIN hotels h ON r.hotel_id = h.hotel_id
            WHERE MONTH(b.booking_date) = %s AND YEAR(b.booking_date) = %s
            GROUP BY h.hotel_id, h.hotel_name, h.location
            ORDER BY revenue DESC
        """, (selected_month, selected_year))
        hotel_breakdown = cursor.fetchall()
        
        return render_template('admin/monthly_report.html', 
                             monthly_summary=monthly_summary,
                             daily_data=daily_data,
                             hotel_breakdown=hotel_breakdown,
                             available_months=available_months,
                             selected_month=selected_month,
                             selected_year=selected_year)
    finally:
        cursor.close()

# ------------------ Hotel reports ------------------
@app.route('/admin/reports/hotels', methods=['GET', 'POST'])
def hotel_report():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    try:
        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('admin_dashboard'))

        cursor = db_conn.cursor(dictionary=True)
        
        try:
            # Get selected hotel if any
            selected_hotel_id = request.args.get('hotel_id') or request.form.get('hotel_id')
            
            # Get all hotels for dropdown
            cursor.execute("SELECT hotel_id, hotel_name, location FROM hotels ORDER BY hotel_name")
            all_hotels = cursor.fetchall()
            
            if selected_hotel_id:
                # Get detailed report for selected hotel
                cursor.execute("""
                    SELECT 
                        h.hotel_name,
                        h.location,
                        COUNT(DISTINCT b.booking_id) as total_bookings,
                        SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_revenue,
                        AVG(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as avg_booking_value,
                        COUNT(DISTINCT b.user_id) as unique_customers
                    FROM hotels h
                    LEFT JOIN rooms r ON h.hotel_id = r.hotel_id
                    LEFT JOIN booking b ON r.room_id = b.room_id
                    WHERE h.hotel_id = %s AND b.booking_id IS NOT NULL
                    GROUP BY h.hotel_id, h.hotel_name, h.location
                """, (selected_hotel_id,))
                hotel_summary = cursor.fetchone()
                
                # Get monthly breakdown for selected hotel
                cursor.execute("""
                    SELECT 
                        DATE_FORMAT(b.booking_date, '%%M %%Y') as month_name,
                        COUNT(b.booking_id) as bookings,
                        SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as revenue
                    FROM booking b
                    JOIN rooms r ON b.room_id = r.room_id
                    WHERE r.hotel_id = %s
                    GROUP BY YEAR(b.booking_date), MONTH(b.booking_date), month_name
                    ORDER BY YEAR(b.booking_date) DESC, MONTH(b.booking_date) DESC
                    LIMIT 12
                """, (selected_hotel_id,))
                monthly_breakdown = cursor.fetchall()
                
                # Get room type breakdown for selected hotel
                cursor.execute("""
                    SELECT 
                        r.room_name,
                        r.price,
                        COUNT(b.booking_id) as bookings,
                        SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as revenue
                    FROM rooms r
                    LEFT JOIN booking b ON r.room_id = b.room_id
                    WHERE r.hotel_id = %s
                    GROUP BY r.room_id, r.room_name, r.price
                    ORDER BY revenue DESC
                """, (selected_hotel_id,))
                room_breakdown = cursor.fetchall()
                
                return render_template('admin/hotel_report.html', 
                                     hotel_data=None,
                                     all_hotels=all_hotels,
                                     selected_hotel_id=int(selected_hotel_id),
                                     hotel_summary=hotel_summary,
                                     monthly_breakdown=monthly_breakdown,
                                     room_breakdown=room_breakdown)
            else:
                # Get report for all hotels
                cursor.execute("""
                    SELECT 
                        h.hotel_id,
                        h.hotel_name,
                        h.location,
                        COUNT(DISTINCT b.booking_id) as total_bookings,
                        SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_revenue,
                        AVG(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as avg_booking_value,
                        COUNT(DISTINCT b.user_id) as unique_customers
                    FROM hotels h
                    LEFT JOIN rooms r ON h.hotel_id = r.hotel_id
                    LEFT JOIN booking b ON r.room_id = b.room_id
                    WHERE b.booking_id IS NOT NULL
                    GROUP BY h.hotel_id, h.hotel_name, h.location
                    ORDER BY total_revenue DESC
                """)
                hotel_data = cursor.fetchall()
                
                return render_template('admin/hotel_report.html', 
                                     hotel_data=hotel_data,
                                     all_hotels=all_hotels,
                                     selected_hotel_id=None,
                                     hotel_summary=None,
                                     monthly_breakdown=None,
                                     room_breakdown=None)
        finally:
            cursor.close()
    except Exception as e:
        print(f"Hotel report error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

# ------------------ Customer reports ------------------
@app.route('/admin/reports/customers')
def customer_report():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    try:
        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('admin_dashboard'))

        cursor = db_conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    u.id,
                    u.username,
                    u.email,
                    COUNT(b.booking_id) as total_bookings,
                    SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_spent,
                    AVG(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as avg_booking_value,
                    MIN(b.booking_date) as first_booking,
                    MAX(b.booking_date) as last_booking
                FROM users u
                INNER JOIN booking b ON u.id = b.user_id
                INNER JOIN rooms r ON b.room_id = r.room_id
                GROUP BY u.id, u.username, u.email
                ORDER BY total_spent DESC
            """)
            customer_data = cursor.fetchall()
            
            return render_template('admin/customer_report.html', customer_data=customer_data)
        finally:
            cursor.close()
    except Exception as e:
        print(f"Customer report error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

# ------------------ View hotel ------------------
@app.route('/admin/hotel/<int:hotel_id>/rooms')
def view_hotel_rooms(hotel_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Get hotel info
        cursor.execute("SELECT * FROM hotels WHERE hotel_id=%s", (hotel_id,))
        hotel = cursor.fetchone()
        
        # Get all rooms for this hotel
        cursor.execute("SELECT * FROM rooms WHERE hotel_id=%s ORDER BY room_id", (hotel_id,))
        rooms = cursor.fetchall()
        
        return render_template('admin/hotel_rooms.html', hotel=hotel, rooms=rooms)
    finally:
        cursor.close()

# ------------------ Add rooms ------------------
@app.route('/admin/hotel/<int:hotel_id>/add_room', methods=['GET', 'POST'])
def add_room(hotel_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('view_hotel_rooms', hotel_id=hotel_id))

    if request.method == 'POST':
        room_name = request.form['room_name']
        room_count = request.form['room_count']
        price = request.form['price']
        status = request.form.get('status', 'Available')
        
        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO rooms (hotel_id, room_name, room_count, price, status) 
                VALUES (%s, %s, %s, %s, %s)
            """, (hotel_id, room_name, room_count, price, status))
            db_conn.commit()
            
            flash('Room added successfully!', 'success')
            return redirect(url_for('view_hotel_rooms', hotel_id=hotel_id))
        finally:
            cursor.close()
    
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM hotels WHERE hotel_id=%s", (hotel_id,))
        hotel = cursor.fetchone()
        return render_template('admin/add_room.html', hotel=hotel)
    finally:
        cursor.close()

# ------------------ Edit rooms ------------------
@app.route('/admin/room/<int:room_id>/edit', methods=['GET', 'POST'])
def edit_room(room_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        room_name = request.form['room_name']
        room_count = request.form['room_count']
        price = request.form['price']
        peak_season = request.form['peak_season']
        status = request.form['status']
        
        try:
            cursor.execute("""
                UPDATE rooms 
                SET room_name=%s, room_count=%s, price=%s, peak_season=%s, status=%s 
                WHERE room_id=%s
            """, (room_name, room_count, price, peak_season, status, room_id))
            db_conn.commit()
            
            cursor.execute("SELECT hotel_id FROM rooms WHERE room_id=%s", (room_id,))
            hotel_id = cursor.fetchone()['hotel_id']
            
            flash('Room updated successfully!', 'success')
            return redirect(url_for('view_hotel_rooms', hotel_id=hotel_id))
        finally:
            cursor.close()
    
    try:
        cursor.execute("SELECT * FROM rooms WHERE room_id=%s", (room_id,))
        room = cursor.fetchone()
        return render_template('admin/edit_room.html', room=room)
    finally:
        cursor.close()

# ------------------ Delete rooms ------------------
@app.route('/admin/room/<int:room_id>/delete')
def delete_room(room_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT hotel_id FROM rooms WHERE room_id=%s", (room_id,))
        result = cursor.fetchone()
        if result:
            hotel_id = result['hotel_id']
            
            cursor.execute("DELETE FROM rooms WHERE room_id=%s", (room_id,))
            db_conn.commit()
            
            flash('Room deleted successfully!', 'success')
            return redirect(url_for('view_hotel_rooms', hotel_id=hotel_id))
        else:
            flash('Room not found!', 'error')
            return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

# ------------------ Update rooms availability ------------------
@app.route('/admin/room/<int:room_id>/update_status', methods=['POST'])
def update_room_status(room_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    new_status = request.form['status']
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return jsonify({'success': False, 'message': 'Database error'}), 500

    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Update status
        cursor.execute("""
            UPDATE rooms 
            SET status=%s 
            WHERE room_id=%s
        """, (new_status, room_id))
        db_conn.commit()
        
        # Get hotel_id to redirect back
        cursor.execute("SELECT hotel_id FROM rooms WHERE room_id=%s", (room_id,))
        result = cursor.fetchone()
        if result:
            hotel_id = result['hotel_id']
            flash(f'Room status updated to {new_status}!', 'success')
            return redirect(url_for('view_hotel_rooms', hotel_id=hotel_id))
        else:
            flash('Room not found!', 'error')
            return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

# ------------------ Add hotel ------------------
@app.route('/admin/add_hotel', methods=['GET', 'POST'])
def add_hotel():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        hotel_name = request.form['hotel_name']
        location = request.form['location']
        
        cursor = db_conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO hotels (hotel_name, location) 
                VALUES (%s, %s)
            """, (hotel_name, location))
            db_conn.commit()
            
            flash('Hotel added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        finally:
            cursor.close()
    
    return render_template('admin/add_hotel.html')

# ------------------ Edit hotel ------------------
@app.route('/admin/edit_hotel/<int:hotel_id>', methods=['GET', 'POST'])
def edit_hotel(hotel_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        hotel_name = request.form['hotel_name']
        location = request.form['location']
        
        try:
            cursor.execute("""
                UPDATE hotels 
                SET hotel_name=%s, location=%s 
                WHERE hotel_id=%s
            """, (hotel_name, location, hotel_id))
            db_conn.commit()
            
            flash('Hotel updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        finally:
            cursor.close()
    
    try:
        cursor.execute("SELECT * FROM hotels WHERE hotel_id=%s", (hotel_id,))
        hotel = cursor.fetchone()
        return render_template('admin/edit_hotel.html', hotel=hotel)
    finally:
        cursor.close()

# ------------------ Delete Hotel ------------------
@app.route('/admin/delete_hotel/<int:hotel_id>')
def delete_hotel(hotel_id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))
    
    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor()
    try:
        # Delete rooms first (foreign key constraint)
        cursor.execute("DELETE FROM rooms WHERE hotel_id=%s", (hotel_id,))
        # Then delete hotel
        cursor.execute("DELETE FROM hotels WHERE hotel_id=%s", (hotel_id,))
        db_conn.commit()
        
        flash('Hotel and all its rooms deleted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

# ------------------ Admin add user ------------------
@app.route('/admin/add-user', methods=['GET', 'POST'])
def add_user():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))

    msg = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # default to user

        if not all([username, email, password]):
            msg = "All fields are required!"
        else:
            db_conn = get_db()
            if db_conn is None:
                msg = "Database connection error. Please try again later."
            else:
                cursor = db_conn.cursor(dictionary=True)
                try:
                    cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
                    if cursor.fetchone():
                        msg = "User with this username or email already exists!"
                    else:
                        hashed = generate_password_hash(password)
                        cursor.execute(
                            "INSERT INTO users (username, email, password, role, status) VALUES (%s,%s,%s,%s,%s)",
                            (username, email, hashed, role, 1)
                        )
                        db_conn.commit()
                        return redirect(url_for('admin_dashboard'))
                finally:
                    cursor.close()

    return render_template('admin/add_user.html', msg=msg)

# ------------------ Edit user by admin ------------------
@app.route('/admin/edit-user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))

    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE id=%s", (id,))
        user = cursor.fetchone()
        if not user:
            return "User not found!"

        msg = ''
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            role = request.form.get('role', 'user')
            status = int(request.form.get('status', 1))
            new_password = request.form.get('new_password')

            # Check if password field has a value
            if new_password and new_password.strip():
                # Hash the new password
                hashed_password = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE users SET username=%s, email=%s, role=%s, status=%s, password=%s WHERE id=%s",
                    (username, email, role, status, hashed_password, id)
                )
            else:
                # Update without changing password
                cursor.execute(
                    "UPDATE users SET username=%s, email=%s, role=%s, status=%s WHERE id=%s",
                    (username, email, role, status, id)
                )
            
            db_conn.commit()
            return redirect(url_for('admin_dashboard'))

        return render_template('admin/edit_user.html', user=user, msg=msg)
    finally:
        cursor.close()

# ------------------ delete user admin ------------------
@app.route('/admin/delete-user/<int:id>')
def delete_user(id):
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))

    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('admin_dashboard'))

    cursor = db_conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id=%s", (id,))
        db_conn.commit()
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

# ------------------ Confirm booking ------------------
@app.route('/confirm-booking')
def confirm_booking():
    try:
        # GET parameters
        checkin = request.args.get('checkin')
        checkout = request.args.get('checkout')
        location = request.args.get('location')
        guests = request.args.get('guests')
        firstname = request.args.get('firstname')
        lastname = request.args.get('lastname')
        fullname = request.args.get('fullname')
        username = request.args.get('username')
        email = request.args.get('email')

        if not all([checkin, checkout, location, guests]):
            return "Missing booking data! Please go back and try again."

        db_conn = get_db()
        if db_conn is None:
            return "Database connection error. Please try again later."

        cursor = db_conn.cursor(dictionary=True)

        try:
            # GET BOOKING RULES FROM DATABASE
            cursor.execute('SELECT rule_name, rule_value FROM booking_rules')
            rules_rows = cursor.fetchall()
            booking_rules = {row['rule_name']: row['rule_value'] for row in rules_rows}
            
            max_booking_days = booking_rules.get('max_booking_days', 30)

            # Fetch hotels
            cursor.execute("SELECT hotel_id, hotel_name, location FROM hotels WHERE LOWER(location)=LOWER(%s)", (location,))
            hotels = cursor.fetchall()

            if not hotels:
                return f"No hotels found in {location}."

            hotel_rooms = {}
            checkin_date = datetime.strptime(checkin, '%Y-%m-%d')
            today = datetime.today()
            days_before_checkin = (checkin_date - today).days

            # Determine discount based on advance booking
            if 80 <= days_before_checkin <= 90:
                discount_percentage = 30
            elif 60 <= days_before_checkin <= 79:
                discount_percentage = 20
            elif 45 <= days_before_checkin <= 59:
                discount_percentage = 10
            else:
                discount_percentage = 0

            # Check if check-in date falls in peak season
            # Peak Season: April-August (4-8) and November-December (11-12)
            checkin_month = checkin_date.month
            is_peak_season = checkin_month in [4, 5, 6, 7, 8, 11, 12]

            for hotel in hotels:
                # Fetch rooms with both price and peak_season columns
                cursor.execute("""
                    SELECT room_id, room_name, room_count, price, peak_season
                    FROM rooms
                    WHERE hotel_id=%s
                """, (hotel['hotel_id'],))
                rooms = cursor.fetchall()

                for room in rooms:
                    # Determine base price: use peak_season price if in peak season, otherwise normal price
                    if is_peak_season and room['peak_season'] is not None:
                        base_price = room['peak_season']
                    else:
                        base_price = room['price']
                    
                    # Apply discount on the selected base price
                    room['discount'] = discount_percentage
                    discount = Decimal(discount_percentage) / Decimal(100)
                    room['final_price'] = (base_price * (Decimal("1") - discount)).quantize(Decimal("0.01"))

                hotel_rooms[hotel['hotel_id']] = rooms

            checkout_date = datetime.strptime(checkout, '%Y-%m-%d')
            num_days = max((checkout_date - checkin_date).days, 1)

            return render_template(
                'confirm_booking.html',
                checkin=checkin,
                checkout=checkout,
                location=location,
                guests=guests,
                fullname=fullname,
                email=email,
                hotels=hotels,
                hotel_rooms=hotel_rooms,
                num_days=num_days,
                max_booking_days=max_booking_days  # Pass this to template
            )
        finally:
            cursor.close()
    
    except Exception as e:
        print(f"Error in confirm_booking: {e}")
        import traceback
        traceback.print_exc()
        return f"An error occurred: {str(e)}", 500

# ------------------ Billing page ------------------
@app.route('/billing')
def billing():
    # Get parameters from the URL
    room_id = request.args.get('room_id')
    room_name = request.args.get('room_name')
    hotel_name = request.args.get('hotel_name')
    price = request.args.get('price')
    currency = request.args.get('currency', 'GBP')  # Add currency parameter with default
    checkin = request.args.get('checkin')
    checkout = request.args.get('checkout')
    guests = request.args.get('guests')
    firstname = request.args.get('firstname')
    lastname = request.args.get('lastname')
    fullname = request.args.get('fullname')
    username = request.args.get('username')
    email = request.args.get('email')
    location = request.args.get('location')
    num_days = request.args.get('num_days')

    if not all([room_id, room_name, hotel_name, price, checkin, checkout, guests]):
        return "Missing booking information! Please go back and try again."

    try:
        price = Decimal(price)
        num_days = Decimal(num_days)
        total_price = (price * num_days).quantize(Decimal("0.01"))

        return render_template(
            'billing.html',
            room_id=room_id,
            room_name=room_name,
            hotel_name=hotel_name,
            price=price,
            currency=currency,  # Pass currency to template
            total_price=total_price,
            checkin=checkin,
            checkout=checkout,
            guests=guests,
            firstname=firstname,
            lastname=lastname,
            fullname=fullname,
            username=username,
            email=email,
            location=location,
            num_days=num_days
        )
    except Exception as e:
        return f"Error processing booking data: {str(e)}", 500

# ------------------ Final payment ------------------
@app.route('/finalize_booking', methods=['POST'])
def finalize_booking():
    if 'loggedin' not in session:
        flash("Please login first!")
        return redirect(url_for('signin'))

    # Get form data
    room_id = request.form.get('room_id')
    checkin_str = request.form.get('checkin')
    checkout_str = request.form.get('checkout')
    fullname = request.form.get('fullname')
    guests = request.form.get('guests')
    email = request.form.get('email')
    hotel_name = request.form.get('hotel_name')
    room_name = request.form.get('room_name')
    price_per_night = Decimal(request.form.get('price'))
    currency = request.form.get('currency', 'GBP')

    if not room_id:
        flash("Please select a room to continue!")
        return redirect(request.referrer)

    # Convert dates
    checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d')
    checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d')
    today = datetime.today()
    num_days = max((checkout_date - checkin_date).days, 1)

    # Calculate Early Booking Discount
    days_before_checkin = (checkin_date - today).days
    discount_percentage = 0
    if 80 <= days_before_checkin <= 90:
        discount_percentage = 30
    elif 60 <= days_before_checkin <= 79:
        discount_percentage = 20
    elif 45 <= days_before_checkin <= 59:
        discount_percentage = 10

    discount = Decimal(discount_percentage) / Decimal(100)
    discounted_price_per_night = price_per_night * (Decimal("1") - discount)
    total_price = (discounted_price_per_night * Decimal(num_days)).quantize(Decimal("0.01"))

    # Currency symbols
    CURRENCY_SYMBOLS = {
        'GBP': '£',
        'USD': '$',
        'NPR': '₨',
        'AUD': '$',
        'INR': '₹'
    }
    
    currency_symbol = CURRENCY_SYMBOLS.get(currency, '£')

    db_conn = get_db()
    if db_conn is None:
        flash("Database connection error. Please try again later.")
        return redirect(url_for('user_dashboard'))

    # Save Booking
    cursor = db_conn.cursor()
    try:
        user_id = session['id']
        cursor.execute("""
            INSERT INTO booking (room_id, customer_name, user_id, check_in, check_out)
            VALUES (%s, %s, %s, %s, %s)
        """, (room_id, fullname, user_id, checkin_date, checkout_date))
        
        # Decrease room availability
        cursor.execute("UPDATE rooms SET room_count = room_count - 1 WHERE room_id=%s", (room_id,))
        db_conn.commit()

        # Send Beautiful HTML Confirmation Email
        try:
            msg = Message(
                subject="🎉 Booking Confirmed - World Hotel",
                recipients=[email],
                sender=app.config['MAIL_USERNAME']
            )
            
            # HTML Email Template
            msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .success-icon {{
            font-size: 50px;
            margin-bottom: 10px;
        }}
        .content {{
            padding: 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        .booking-details {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .booking-details h2 {{
            color: #667eea;
            margin-top: 0;
            font-size: 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: 600;
            color: #555;
        }}
        .detail-value {{
            color: #333;
        }}
        .total-section {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }}
        .total-section h3 {{
            margin: 0 0 10px 0;
            font-size: 18px;
        }}
        .total-amount {{
            font-size: 32px;
            font-weight: bold;
        }}
        .discount-badge {{
            background: #28a745;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 10px;
            font-size: 14px;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 20px 0;
            font-weight: 600;
        }}
        .info-box {{
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="success-icon">✅</div>
            <h1>Booking Confirmed!</h1>
        </div>
        
        <div class="content">
            <p class="greeting">Dear {fullname},</p>
            
            <p class="message">
                Great news! Your booking has been successfully confirmed at <strong>{hotel_name}</strong>. 
                We can't wait to welcome you!
            </p>
            
            <div class="booking-details">
                <h2>📋 Booking Details</h2>
                
                <div class="detail-row">
                    <span class="detail-label">🏨 Hotel:</span>
                    <span class="detail-value">{hotel_name}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">🛏️ Room Type:</span>
                    <span class="detail-value">{room_name}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">📅 Check-in:</span>
                    <span class="detail-value">{checkin_date.strftime('%A, %B %d, %Y')}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">📅 Check-out:</span>
                    <span class="detail-value">{checkout_date.strftime('%A, %B %d, %Y')}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">🌙 Number of Nights:</span>
                    <span class="detail-value">{num_days}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">👥 Number of Guests:</span>
                    <span class="detail-value">{guests}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">💵 Price per Night:</span>
                    <span class="detail-value">{currency_symbol}{price_per_night:.2f} {currency}</span>
                </div>
            </div>
            
            {"<div class='info-box'><strong>🎉 Early Booking Discount Applied!</strong><br>You saved " + str(discount_percentage) + "% by booking in advance.</div>" if discount_percentage > 0 else ""}
            
            <div class="total-section">
                <h3>Total Amount</h3>
                <div class="total-amount">{currency_symbol}{total_price:.2f} {currency}</div>
                {f'<div class="discount-badge">Saved {discount_percentage}%</div>' if discount_percentage > 0 else ''}
            </div>
        </div>
    </div>
</body>
</html>
            """
            mail.send(msg)
        except Exception as e:
            print("Error sending email:", e)
            flash("Booking confirmed, but email could not be sent.")

        flash(f"Booking confirmed successfully! Total: {currency_symbol}{total_price:.2f} {currency}")
        return redirect(url_for('user_dashboard'))
    finally:
        cursor.close()

# ------------------ Exchange rates ------------------
def init_exchange_rates_table():
    """Initialize the exchange_rates table if it doesn't exist"""
    db_conn = get_db()
    if db_conn is None:
        print("ERROR: Cannot initialize exchange rates - database connection failed")
        return
    
    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                currency VARCHAR(10) NOT NULL UNIQUE,
                rate DECIMAL(10, 2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_currency (currency)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Check if table is empty
        cursor.execute('SELECT COUNT(*) as count FROM exchange_rates')
        result = cursor.fetchone()
        
        if result['count'] == 0:
            # Insert default rates
            default_rates = [
                ('USD', 1.27),
                ('NPR', 171.50),
                ('AUD', 1.93),
                ('INR', 106.50)
            ]
            
            cursor.executemany(
                'INSERT INTO exchange_rates (currency, rate) VALUES (%s, %s)',
                default_rates
            )
            print(f"INFO: Inserted {len(default_rates)} default exchange rates")
        
        db_conn.commit()
        print("INFO: Exchange rates table initialized successfully!")
        
    except Exception as e:
        print(f"ERROR: Database error: {e}")
    finally:
        cursor.close()

# ------------------ Admin dashboard ------------------
@app.route('/admin/dashboard')
def admin_dashboard():
    try:
        if 'loggedin' not in session or session['role'] != 'admin':
            return redirect(url_for('signin'))

        user_id = session['id']
        db_conn = get_db()
        if db_conn is None:
            flash("Database connection error. Please try again later.")
            return redirect(url_for('signin'))

        cursor = db_conn.cursor(dictionary=True)

        try:
            # Admin profile
            cursor.execute("SELECT fullname, profile_picture FROM user_profile WHERE user_id=%s", (user_id,))
            profile = cursor.fetchone()

            # All users
            cursor.execute("SELECT id, username, email, role, status FROM users")
            users = cursor.fetchall()
            total_users = len(users)

            # All hotels with room count
            cursor.execute("""
                SELECT h.hotel_id, h.hotel_name, h.location, 
                       COUNT(DISTINCT r.room_id) as total_rooms,
                       SUM(r.room_count) as total_room_count,
                       MIN(r.price) as min_price,
                       MAX(r.price) as max_price
                FROM hotels h
                LEFT JOIN rooms r ON h.hotel_id = r.hotel_id
                GROUP BY h.hotel_id, h.hotel_name, h.location
            """)
            hotels = cursor.fetchall()
            total_hotels = len(hotels)

            # === REPORTING DATA ===
            
            # Monthly Sales (Current Month)
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(b.booking_date, '%%Y-%%m') as month,
                    COUNT(*) as total_bookings,
                    SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_revenue
                FROM booking b
                JOIN rooms r ON b.room_id = r.room_id
                WHERE MONTH(b.booking_date) = MONTH(CURRENT_DATE())
                    AND YEAR(b.booking_date) = YEAR(CURRENT_DATE())
                GROUP BY month
            """)
            monthly_sales = cursor.fetchone()

            # Sales by Hotel
            cursor.execute("""
                SELECT 
                    h.hotel_name,
                    COUNT(b.booking_id) as total_bookings,
                    SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_revenue,
                    AVG(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as avg_booking_value
                FROM hotels h
                LEFT JOIN rooms r ON h.hotel_id = r.hotel_id
                LEFT JOIN booking b ON r.room_id = b.room_id
                WHERE b.booking_id IS NOT NULL
                GROUP BY h.hotel_id, h.hotel_name
                ORDER BY total_revenue DESC
            """)
            hotel_sales = cursor.fetchall()

            # Top Customers (by total spending)
            cursor.execute("""
                SELECT 
                    u.username,
                    u.email,
                    COUNT(b.booking_id) as total_bookings,
                    SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_spent,
                    MAX(b.booking_date) as last_booking_date
                FROM users u
                INNER JOIN booking b ON u.id = b.user_id
                INNER JOIN rooms r ON b.room_id = r.room_id
                GROUP BY u.id, u.username, u.email
                ORDER BY total_spent DESC
                LIMIT 10
            """)
            top_customers = cursor.fetchall()

            # Recent Bookings (last 10)
            cursor.execute("""
                SELECT 
                    b.booking_id,
                    u.username,
                    h.hotel_name,
                    r.room_name,
                    b.booking_date,
                    b.check_in,
                    b.check_out,
                    (r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total_price,
                    CASE 
                        WHEN b.check_out < CURDATE() THEN 'completed'
                        WHEN b.check_in <= CURDATE() AND b.check_out >= CURDATE() THEN 'active'
                        ELSE 'upcoming'
                    END as status
                FROM booking b
                INNER JOIN users u ON b.user_id = u.id
                INNER JOIN rooms r ON b.room_id = r.room_id
                INNER JOIN hotels h ON r.hotel_id = h.hotel_id
                ORDER BY b.booking_date DESC
                LIMIT 10
            """)
            recent_bookings = cursor.fetchall()

            # Overall Statistics
            cursor.execute("SELECT COUNT(*) as total FROM booking")
            total_bookings = cursor.fetchone()['total']

            cursor.execute("""
                SELECT SUM(r.price * CAST(DATEDIFF(b.check_out, b.check_in) AS DECIMAL(10,2))) as total 
                FROM booking b
                JOIN rooms r ON b.room_id = r.room_id
            """)
            total_revenue = cursor.fetchone()['total'] or 0

            # GET EXCHANGE RATES
            cursor.execute(
                'SELECT currency, rate, updated_at FROM exchange_rates ORDER BY currency'
            )
            exchange_rates_rows = cursor.fetchall()
            
            exchange_rates = {
                row['currency']: {
                    'rate': float(row['rate']),
                    'updated_at': row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if row['updated_at'] else ''
                } for row in exchange_rates_rows
            }
            cursor.execute('SELECT rule_name, rule_value FROM booking_rules')
            rules_rows = cursor.fetchall()
            booking_rules = {row['rule_name']: row['rule_value'] for row in rules_rows}

            return render_template('admin/admin_dashboard.html',
                                   profile=profile, 
                                   users=users, 
                                   total_users=total_users,
                                   hotels=hotels,
                                   total_hotels=total_hotels,
                                   monthly_sales=monthly_sales,
                                   hotel_sales=hotel_sales,
                                   top_customers=top_customers,
                                   recent_bookings=recent_bookings,
                                   total_bookings=total_bookings,
                                   total_revenue=total_revenue,
                                   exchange_rates=exchange_rates,
                                   booking_rules=booking_rules)
        finally:
            cursor.close()
    
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

# ------------------ Get all exchange rate ------------------
@app.route('/api/get-exchange-rates', methods=['GET'])
def get_exchange_rates():
    """Get all current exchange rates"""
    try:
        db_conn = get_db()
        if db_conn is None:
            return jsonify({
                'success': False,
                'message': 'Database connection error'
            }), 500

        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT currency, rate FROM exchange_rates')
            rates = cursor.fetchall()
            
            rates_dict = {row['currency']: float(row['rate']) for row in rates}
            
            return jsonify({
                'success': True,
                'rates': rates_dict
            })
        finally:
            cursor.close()
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ------------------ Update exchange rate by admin ------------------
@app.route('/api/update-exchange-rate', methods=['POST'])
def update_exchange_rate():
    """Update a single exchange rate"""
    if 'loggedin' not in session or session['role'] != 'admin':
        return jsonify({
            'success': False,
            'message': 'Admin access required'
        }), 403
    
    try:
        data = request.get_json()
        currency = data.get('currency')
        rate = float(data.get('rate'))
        
        if not currency or rate <= 0:
            return jsonify({
                'success': False,
                'message': 'Invalid currency or rate'
            }), 400
        
        db_conn = get_db()
        if db_conn is None:
            return jsonify({
                'success': False,
                'message': 'Database connection error'
            }), 500

        cursor = db_conn.cursor()
        
        try:
            # Insert or update rate using INSERT ... ON DUPLICATE KEY UPDATE
            cursor.execute('''
                INSERT INTO exchange_rates (currency, rate, updated_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    rate = VALUES(rate),
                    updated_at = NOW()
            ''', (currency, rate))
            
            db_conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'{currency} rate updated successfully',
                'currency': currency,
                'rate': rate
            })
        finally:
            cursor.close()
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Update all exchange rates (admin only)
@app.route('/api/update-all-exchange-rates', methods=['POST'])
def update_all_exchange_rates():
    """Update all exchange rates at once"""
    if 'loggedin' not in session or session['role'] != 'admin':
        return jsonify({
            'success': False,
            'message': 'Admin access required'
        }), 403
    
    try:
        data = request.get_json()
        rates = data.get('rates', {})
        
        if not rates:
            return jsonify({
                'success': False,
                'message': 'No rates provided'
            }), 400
        
        # Validate all rates
        for currency, rate in rates.items():
            if float(rate) <= 0:
                return jsonify({
                    'success': False,
                    'message': f'Invalid rate for {currency}'
                }), 400
        
        db_conn = get_db()
        if db_conn is None:
            return jsonify({
                'success': False,
                'message': 'Database connection error'
            }), 500

        cursor = db_conn.cursor()
        
        try:
            # Update all rates
            for currency, rate in rates.items():
                cursor.execute('''
                    INSERT INTO exchange_rates (currency, rate, updated_at)
                    VALUES (%s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        rate = VALUES(rate),
                        updated_at = NOW()
                ''', (currency, float(rate)))
            
            db_conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'All exchange rates updated successfully',
                'rates': rates
            })
        finally:
            cursor.close()
    
    except Exception as e:
        if db_conn:
            db_conn.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

#settings
def init_booking_rules_table():
    """Initialize the booking_rules table if it doesn't exist"""
    db_conn = get_db()
    if db_conn is None:
        print("ERROR: Cannot initialize booking rules - database connection failed")
        return
    
    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS booking_rules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rule_name VARCHAR(50) NOT NULL UNIQUE,
                rule_value INT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # Check if table is empty
        cursor.execute('SELECT COUNT(*) as count FROM booking_rules')
        result = cursor.fetchone()
        
        if result['count'] == 0:
            # Insert default rules
            default_rules = [
                ('max_booking_days', 30),      # Maximum 30 days per booking
                ('max_advance_days', 90)       # Can book up to 90 days (3 months) in advance
            ]
            
            cursor.executemany(
                'INSERT INTO booking_rules (rule_name, rule_value) VALUES (%s, %s)',
                default_rules
            )
            print(f"INFO: Inserted {len(default_rules)} default booking rules")
        
        db_conn.commit()
        print("INFO: Booking rules table initialized successfully!")
        
    except Exception as e:
        print(f"ERROR: Database error: {e}")
    finally:
        cursor.close()

#update the settings rules by admin
@app.route('/api/update-booking-rules', methods=['POST'])
def update_booking_rules():
    """Update booking rules (admin only)"""
    if 'loggedin' not in session or session['role'] != 'admin':
        return jsonify({
            'success': False,
            'message': 'Admin access required'
        }), 403
    
    try:
        data = request.get_json()
        max_booking_days = int(data.get('max_booking_days', 30))
        max_advance_days = int(data.get('max_advance_days', 90))
        
        # Validation
        if max_booking_days < 1 or max_booking_days > 365:
            return jsonify({
                'success': False,
                'message': 'Maximum booking days must be between 1 and 365'
            }), 400
        
        if max_advance_days < 1 or max_advance_days > 730:
            return jsonify({
                'success': False,
                'message': 'Maximum advance days must be between 1 and 730'
            }), 400
        
        db_conn = get_db()
        if db_conn is None:
            return jsonify({
                'success': False,
                'message': 'Database connection error'
            }), 500

        cursor = db_conn.cursor()
        
        try:
            # Update max_booking_days
            cursor.execute('''
                INSERT INTO booking_rules (rule_name, rule_value, updated_at)
                VALUES ('max_booking_days', %s, NOW())
                ON DUPLICATE KEY UPDATE
                    rule_value = VALUES(rule_value),
                    updated_at = NOW()
            ''', (max_booking_days,))
            
            # Update max_advance_days
            cursor.execute('''
                INSERT INTO booking_rules (rule_name, rule_value, updated_at)
                VALUES ('max_advance_days', %s, NOW())
                ON DUPLICATE KEY UPDATE
                    rule_value = VALUES(rule_value),
                    updated_at = NOW()
            ''', (max_advance_days,))
            
            db_conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Booking rules updated successfully',
                'max_booking_days': max_booking_days,
                'max_advance_days': max_advance_days
            })
        finally:
            cursor.close()
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

#get booking rules
@app.route('/api/get-booking-rules', methods=['GET'])
def get_booking_rules():
    """Get current booking rules"""
    try:
        db_conn = get_db()
        if db_conn is None:
            return jsonify({
                'success': False,
                'message': 'Database connection error'
            }), 500

        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT rule_name, rule_value FROM booking_rules')
            rules = cursor.fetchall()
            
            rules_dict = {row['rule_name']: row['rule_value'] for row in rules}
            
            return jsonify({
                'success': True,
                'rules': rules_dict
            })
        finally:
            cursor.close()
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ------------------ Initialize database tables ------------------
def initialize_database():
    """Initialize database tables on startup"""
    try:
        print("INFO: Initializing database tables...")
        init_exchange_rates_table()
        init_booking_rules_table()
        print("INFO: Database initialization complete!")
    except Exception as e:
        print(f"ERROR: Database initialization failed: {e}")

#clear session
@app.route('/clear-session')
def clear_session():
    session.clear()
    return redirect(url_for('signin'))

# ------------------ Run App ------------------
if __name__ == "__main__":
    # Initialize database tables
    initialize_database()
    app.run(debug=True)