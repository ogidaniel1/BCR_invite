import os
from flask_wtf import CSRFProtect, FlaskForm
from functools import wraps
from flask_paginate import Pagination, get_page_parameter
from flask import Flask, render_template, request, redirect, url_for, flash,jsonify, abort,Response, session
from flask_sqlalchemy import SQLAlchemy
from Crypto.Hash import SHA256
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from alembic import op
import json
import pandas as pd
from wtforms import SubmitField
from wtforms import StringField, SubmitField, FloatField,PasswordField
from wtforms.validators import DataRequired, Email, EqualTo,Length,ValidationError,Optional,Regexp
# from utils import load_config, generate_db_uri
from dotenv import load_dotenv
import random, time
from datetime import timedelta
from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import qrcode
from flask_login import LoginManager, login_user, login_required, current_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import io
import base64
import cv2
import subprocess
# from pyzbar 
import pyzbar
from pyzbar.pyzbar import decode

# Load environment variables
load_dotenv()

# Configuration
DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invitees.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

application = app


class InviteeForm(FlaskForm):
    name = StringField('Member Name', validators=[Optional(), Length(min=2, max=100)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(max=11), Regexp(regex='^\d+$', message="Phone number must contain only digits")])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# Models
class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    admin_name = db.Column(db.String(120), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)


class Invitee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    qr_code_path = db.Column(db.String(200), nullable=True)
    confirmed = db.Column(db.String(20), default=None)  # New field to track confirmation


login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(admin_id):
    return Admin.query.get(int(admin_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        # Add any additional admin checks here if necessary
        return f(*args, **kwargs)
    return decorated_function


def create_default_admin():
    default_admin = Admin.query.filter_by(email=DEFAULT_ADMIN_EMAIL).first()
    if not default_admin:
        hashed_password = generate_password_hash(DEFAULT_ADMIN_PASSWORD, method='pbkdf2:sha256')
        new_admin = Admin(
            email=DEFAULT_ADMIN_EMAIL,
            password=hashed_password,
            admin_name='Default Admin',
            is_admin=True
        )
        db.session.add(new_admin)
        db.session.commit()
        print("Default admin created")
    else:
        print("Default admin already exists")


# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(email=form.email.data).first()
        if admin and check_password_hash(admin.password, form.password.data):
            login_user(admin)
            flash('Login successful!', 'success')
            return redirect(url_for('scan_qr'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
# @login_required
def logout():
    session.clear()
    flash('You have been Logged out!', 'success')
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
def home():
    form = InviteeForm()
    return render_template('register.html', form=form)

###############################################

def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    byte_arr.seek(0)
    return base64.b64encode(byte_arr.getvalue()).decode('utf-8')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = InviteeForm()
    if form.validate_on_submit():
        name = form.name.data.title() 
        phone_number = form.phone_number.data
        
        # Check for duplicates
        existing_invitee = Invitee.query.filter_by(phone_number=phone_number).first()
        if existing_invitee:
            # If an invitee with the same phone number exists, show an error message
            return render_template('register.html', form=form, error="An invitee with this phone number already exists.")
        
        # Create a new invitee
        new_invitee = Invitee(name=name, phone_number=phone_number)
        db.session.add(new_invitee)
        db.session.commit()
        
        # Generate QR code
        qr_code_path = generate_qr_code(new_invitee.id)
        
        return redirect(url_for('success', qr_code_path=qr_code_path))
    
    return render_template('register.html', form=form)


@app.route('/success')
def success():
    qr_code_path = request.args.get('qr_code_path')
    if not qr_code_path:
        return 'QR code path is missing', 400
    return render_template('success.html', qr_code_path=qr_code_path)
###############################################

@app.route('/confirm_qr_code', methods=['POST'])
def confirm_qr_code():
    qr_code_data = request.json.get('qr_code_data')
    
    if not qr_code_data:
        return jsonify({'error': 'QR code data is missing'}), 400

    # Assuming the QR code data is the invitee's ID
    invitee = Invitee.query.get(qr_code_data)
    
    if not invitee:
        return jsonify({'error': 'Invitee not found'}), 404
    
    if invitee.confirmed == "Present":
        return jsonify({
            'message': 'You have already been confirmed',
            'invitee_name': invitee.name
        }), 200
    
    # Confirm the invitee by setting "confirmed" to "Present"
    invitee.confirmed = "Present"
    db.session.commit()
    
    # Return confirmation details
    return jsonify({
        'message': 'Invitee confirmed',
        'invitee_name': invitee.name
    }), 200

   
@app.route('/scan_qr')
@admin_required
def scan_qr():

    return render_template('scan_qr.html')

###############################################

@app.route('/get_qr_code/<int:invitee_id>')
def get_qr_code(invitee_id):
    qr_code_path = generate_qr_code(invitee_id)
    return jsonify({'qr_code_path': qr_code_path})


@app.route('/invitees')
@admin_required
def show_invitees():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('login'))
    
    search = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    if search:
        invitees_query = Invitee.query.filter(
            (Invitee.id.ilike(f'%{search}%')) | 
            (Invitee.phone_number.ilike(f'%{search}%'))
        )
    else:
        invitees_query = Invitee.query

    pagination = invitees_query.order_by(Invitee.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    invitees = pagination.items

    return render_template('invitees.html', invitees=invitees, pagination=pagination, search=search)

# @app.route('/attended_invitees')
# def attended_invitees():
#     # Query all invitees who have "attended"
#     attended_invitees = Invitee.query.filter_by(confirmed="attended").all()
    
#     # You can pass this to a template or return as JSON, depending on your application
#     return render_template('attended_invitees.html', invitees=attended_invitees)

#################################################################

# scan_qr_code function..........################################
#a Python Script for QR Code Scanning: This script will use OpenCV to access the webcam, detect QR codes, and decode them

# def scan_qr_code():
#     # Initialize the camera (0 is the default camera)
#     cap = cv2.VideoCapture(0)
    
#     if not cap.isOpened():
#         print("Error: Could not open the camera.")
#         return None

#     while True:
#         # Capture frame-by-frame
#         ret, frame = cap.read()
        
#         if not ret:
#             print("Error: Could not read a frame from the camera.")
#             continue

#         # Decode QR codes in the frame
#         qr_codes = decode(frame)

#         for qr_code in qr_codes:
#             # Extract the QR code data
#             qr_data = qr_code.data.decode('utf-8')
#             print(f"QR Code detected: {qr_data}")

#             # Draw a rectangle around the QR code
#             (x, y, w, h) = qr_code.rect
#             cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

#             # Display the QR code data on the screen
#             cv2.putText(frame, qr_data, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

#             # Release the camera and close windows after detecting the first QR code
#             cap.release()
#             cv2.destroyAllWindows()
#             return qr_data

#         # Display the resulting frame
#         cv2.imshow('QR Code Scanner', frame)

#         # Break the loop on 'q' key press
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     # Release the capture and close any OpenCV windows
#     cap.release()
#     cv2.destroyAllWindows()
#     return None

def scan_qr_code(camera_index=1):  # Default to the second camera (index 1)
    # Initialize the camera with the specified index
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"Error: Could not open the camera with index {camera_index}.")
        return None

    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Could not read a frame from the camera.")
            continue

        # Decode QR codes in the frame
        qr_codes = decode(frame)

        for qr_code in qr_codes:
            # Extract the QR code data
            qr_data = qr_code.data.decode('utf-8')
            print(f"QR Code detected: {qr_data}")

            # Draw a rectangle around the QR code
            (x, y, w, h) = qr_code.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Display the QR code data on the screen
            cv2.putText(frame, qr_data, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Release the camera and close windows after detecting the first QR code
            cap.release()
            cv2.destroyAllWindows()
            return qr_data

        # Display the resulting frame
        cv2.imshow('QR Code Scanner', frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the capture and close any OpenCV windows
    cap.release()
    cv2.destroyAllWindows()
    return None

# Example usage:
# To use the rear camera, specify the camera index. You may need to experiment with the index value.
qr_data = scan_qr_code(camera_index=1)
if qr_data:
    print(f"Scanned QR Code data: {qr_data}")


if __name__ == '__main__':
        
    # Ensure that the application context is active
    with app.app_context():
        if not os.path.exists('static/qr_codes'):
            os.makedirs('static/qr_codes')
        db.create_all()
        #create default admin
        create_default_admin()

    app.run(debug=True)