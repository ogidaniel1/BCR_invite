import os
from flask_wtf import CSRFProtect, FlaskForm
from werkzeug.utils import secure_filename
from functools import wraps
from flask_wtf.csrf import generate_csrf, validate_csrf,CSRFError
from flask_paginate import Pagination, get_page_parameter
from flask import Flask, render_template, request, redirect, url_for, flash,jsonify, abort,Response, session
from flask_sqlalchemy import SQLAlchemy
from Crypto.Hash import SHA256
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from alembic import op
from datetime import datetime, timezone
import json
import logging
import pandas as pd
from wtforms import SubmitField
from wtforms import StringField, SubmitField,SelectField, FloatField,PasswordField
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
# from flask import Flask, send_from_static
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import io
from flask_mail import  Mail,Message
from email.mime.image import MIMEImage
import smtplib
import base64
import cv2
import subprocess
from sqlalchemy.exc import IntegrityError,OperationalError
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
app.config['SQLALCHEMY_POOL_RECYCLE'] = 3600  # Recycle connections every hour
app.config['SQLALCHEMY_POOL_PRE_PING'] = True  # Pre-ping connections to verify they're still valid
app.config['UPLOAD_FOLDER'] = 'static/qr_codes'



# config.py or app setup
# Looking to send emails in production? Check out our Email API/SMTP product!
app.config['MAIL_SERVER']='sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = '2d210b819d0f12'
app.config['MAIL_PASSWORD'] = '804323d6c92a70'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

application = app

mail = Mail(app)
#####################################################################

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
    email = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    state = db.Column(db.String(100), nullable=True)
    lga = db.Column(db.String(100), nullable=True)
    position = db.Column(db.String(50), nullable=False)
    deleted = db.Column(db.Boolean, default=False)
    qr_code_path = db.Column(db.String(200), nullable=True)
    confirmed = db.Column(db.String(20), default='Absent')  # New field to track confirmation


class DeleteLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_type = db.Column(db.String(50), nullable=False)  # E.g., 'admin', 'invitee'
    record_id = db.Column(db.Integer, nullable=False)  # ID of the deleted record
    deleted_by = db.Column(db.Integer, db.ForeignKey('admin.id'))  # ID of the webmaster who deleted
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationship with Webmaster
    deleted_by_admin = db.relationship('Admin', foreign_keys=[deleted_by])

    def __repr__(self):
        return f'<DeleteLog {self.record_type} {self.record_id} deleted by {self.deleted_by} at {self.deleted_at}>'

#############################################

def fetch_lgas(state):
    # Mock LGA data for each state
    state_lgas = {
    'Abia': ['Aba North', 'Aba South', 'Arochukwu', 'Bende', 'Ikwuano', 'Isiala Ngwa North', 'Isiala Ngwa South', 'Isuikwuato', 'Obi Ngwa', 'Ohafia', 'Osisioma', 'Ugwunagbo', 'Ukwa East', 'Ukwa West', 'Umuahia North', 'Umuahia South', 'Umu Nneochi'],
    'Adamawa': ['Demsa', 'Fufore', 'Ganye', 'Gayuk', 'Gombi', 'Grie', 'Hong', 'Jada', 'Lamurde', 'Madagali', 'Maiha', 'Mayo-Belwa', 'Michika', 'Mubi North', 'Mubi South', 'Numan', 'Shelleng', 'Song', 'Toungo', 'Yola North', 'Yola South'],
    'Akwa Ibom': ['Abak', 'Eastern Obolo', 'Eket', 'Esit Eket', 'Essien Udim', 'Etim Ekpo', 'Etinan', 'Ibeno', 'Ibesikpo Asutan', 'Ibiono Ibom', 'Ika', 'Ikono', 'Ikot Abasi', 'Ikot Ekpene', 'Ini', 'Itu', 'Mbo', 'Mkpat-Enin', 'Nsit-Atai', 'Nsit-Ibom', 'Nsit-Ubium', 'Obot Akara', 'Okobo', 'Onna', 'Oron', 'Oruk Anam', 'Udung-Uko', 'Ukanafun', 'Uruan', 'Urue-Offong/Oruko', 'Uyo'],
    'Anambra': ['Aguata', 'Anambra East', 'Anambra West', 'Anaocha', 'Awka North', 'Awka South', 'Ayamelum', 'Dunukofia', 'Ekwusigo', 'Idemili North', 'Idemili South', 'Ihiala', 'Njikoka', 'Nnewi North', 'Nnewi South', 'Ogbaru', 'Onitsha North', 'Onitsha South', 'Orumba North', 'Orumba South', 'Oyi'],
    'Bauchi': ['Alkaleri', 'Bauchi', 'Bogoro', 'Damban', 'Darazo', 'Dass', 'Gamawa', 'Ganjuwa', 'Giade', 'Itas/Gadau', 'Jama\'are', 'Katagum', 'Kirfi', 'Misau', 'Ningi', 'Shira', 'Tafawa Balewa', 'Toro', 'Warji', 'Zaki'],
    'Bayelsa': ['Brass', 'Ekeremor', 'Kolokuma/Opokuma', 'Nembe', 'Ogbia', 'Sagbama', 'Southern Ijaw', 'Yenagoa'],
    'Benue': ['Ado', 'Agatu', 'Apa', 'Buruku', 'Gboko', 'Guma', 'Gwer East', 'Gwer West', 'Katsina-Ala', 'Konshisha', 'Kwande', 'Logo', 'Makurdi', 'Obi', 'Ogbadibo', 'Ohimini', 'Oju', 'Okpokwu', 'Otukpo', 'Tarka', 'Ukum', 'Ushongo', 'Vandeikya'],
    'Borno': ['Abadam', 'Askira/Uba', 'Bama', 'Bayo', 'Biu', 'Chibok', 'Damboa', 'Dikwa', 'Gubio', 'Guzamala', 'Gwoza', 'Hawul', 'Jere', 'Kaga', 'Kala/Balge', 'Konduga', 'Kukawa', 'Kwaya Kusar', 'Mafa', 'Magumeri', 'Maiduguri', 'Marte', 'Mobbar', 'Monguno', 'Ngala', 'Nganzai', 'Shani'],
    'Cross River': ['Abi', 'Akamkpa', 'Akpabuyo', 'Bakassi', 'Bekwarra', 'Biase', 'Boki', 'Calabar Municipal', 'Calabar South', 'Etung', 'Ikom', 'Obanliku', 'Obubra', 'Obudu', 'Odukpani', 'Ogoja', 'Yakuur', 'Yala'],
    'Delta': ['Aniocha North', 'Aniocha South', 'Bomadi', 'Burutu', 'Ethiope East', 'Ethiope West', 'Ika North East', 'Ika South', 'Isoko North', 'Isoko South', 'Ndokwa East', 'Ndokwa West', 'Okpe', 'Oshimili North', 'Oshimili South', 'Patani', 'Sapele', 'Udu', 'Ughelli North', 'Ughelli South', 'Ukwuani', 'Uvwie', 'Warri North', 'Warri South', 'Warri South West'],
    'Ebonyi': ['Abakaliki', 'Afikpo North', 'Afikpo South (Edda)', 'Ebonyi', 'Ezza North', 'Ezza South', 'Ikwo', 'Ishielu', 'Ivo', 'Izzi', 'Ohaozara', 'Ohaukwu', 'Onicha'],
    'Edo': ['Akoko-Edo', 'Egor', 'Esan Central', 'Esan North-East', 'Esan South-East', 'Esan West', 'Etsako Central', 'Etsako East', 'Etsako West', 'Igueben', 'Ikpoba-Okha', 'Oredo', 'Orhionmwon', 'Ovia North-East', 'Ovia South-West', 'Owan East', 'Owan West', 'Uhunmwonde'],
    'Ekiti': ['Ado Ekiti', 'Efon', 'Ekiti East', 'Ekiti South-West', 'Ekiti West', 'Emure', 'Gbonyin', 'Ido Osi', 'Ijero', 'Ikere', 'Ikole', 'Ilejemeje', 'Irepodun/Ifelodun', 'Ise/Orun', 'Moba', 'Oye'],
    'Enugu': ['Aninri', 'Awgu', 'Enugu East', 'Enugu North', 'Enugu South', 'Ezeagu', 'Igbo Etiti', 'Igbo Eze North', 'Igbo Eze South', 'Isi Uzo', 'Nkanu East', 'Nkanu West', 'Nsukka', 'Oji River', 'Udenu', 'Udi', 'Uzo Uwani'],
    'Gombe': ['Akko', 'Balanga', 'Billiri', 'Dukku', 'Funakaye', 'Gombe', 'Kaltungo', 'Kwami', 'Nafada', 'Shongom', 'Yamaltu/Deba'],
    'Imo': ['Aboh Mbaise', 'Ahiazu Mbaise', 'Ehime Mbano', 'Ezinihitte', 'Ideato North', 'Ideato South', 'Ihitte/Uboma', 'Ikeduru', 'Isiala Mbano', 'Isu', 'Mbaitoli', 'Ngor Okpala', 'Njaba', 'Nkwerre', 'Nwangele', 'Obowo', 'Oguta', 'Ohaji/Egbema', 'Okigwe', 'Onuimo', 'Orlu', 'Orsu', 'Oru East', 'Oru West', 'Owerri Municipal', 'Owerri North', 'Owerri West'],
    'Jigawa': ['Auyo', 'Babura', 'Biriniwa', 'Birnin Kudu', 'Buji', 'Dutse', 'Gagarawa', 'Garki', 'Gumel', 'Guri', 'Gwaram', 'Gwiwa', 'Hadejia', 'Jahun', 'Kafin Hausa', 'Kaugama', 'Kazaure', 'Kiri Kasama', 'Kiyawa', 'Maigatari', 'Malam Madori', 'Miga', 'Ringim', 'Roni', 'Sule Tankarkar', 'Taura', 'Yankwashi'],
    'Kaduna': ['Birnin Gwari', 'Chikun', 'Giwa', 'Igabi', 'Ikara', 'Jaba', 'Jema\'a', 'Kachia', 'Kaduna North', 'Kaduna South', 'Kagarko', 'Kajuru', 'Kaura', 'Kauru', 'Kubau', 'Kudan', 'Lere', 'Makarfi', 'Sabon Gari', 'Sanga', 'Soba', 'Zangon Kataf', 'Zaria'],
    'Kano': ['Ajingi', 'Albasu', 'Bagwai', 'Bebeji', 'Bichi', 'Bunkure', 'Dala', 'Dambatta', 'Dawakin Kudu', 'Dawakin Tofa', 'Doguwa', 'Fagge', 'Gabasawa', 'Garko', 'Garun Mallam', 'Gaya', 'Gezawa', 'Gwale', 'Gwarzo', 'Kabo', 'Kano Municipal', 'Karaye', 'Kibiya', 'Kiru', 'Kumbotso', 'Kunchi', 'Kura', 'Madobi', 'Makoda', 'Minjibir', 'Nasarawa', 'Rano', 'Rimin Gado', 'Rogo', 'Shanono', 'Sumaila', 'Takai', 'Tarauni', 'Tofa', 'Tsanyawa', 'Tudun Wada', 'Ungogo', 'Warawa', 'Wudil'],
    'Katsina': ['Bakori', 'Batagarawa', 'Batsari', 'Baure', 'Bindawa', 'Charanchi', 'Dandume', 'Danja', 'Dan Musa', 'Daura', 'Dutsi', 'Dutsin Ma', 'Faskari', 'Funtua', 'Ingawa', 'Jibia', 'Kafur', 'Kaita', 'Kankara', 'Kankia', 'Katsina', 'Kurfi', 'Kusada', 'Mai\'Adua', 'Malumfashi', 'Mani', 'Mashi', 'Matazu', 'Musawa', 'Rimi', 'Sabuwa', 'Safana', 'Sandamu', 'Zango'],
    'Kebbi': ['Aleiro', 'Arewa Dandi', 'Argungu', 'Augie', 'Bagudo', 'Birnin Kebbi', 'Bunza', 'Dandi', 'Fakai', 'Gwandu', 'Jega', 'Kalgo', 'Koko/Besse', 'Maiyama', 'Ngaski', 'Sakaba', 'Shanga', 'Suru', 'Danko/Wasagu', 'Yauri', 'Zuru'],
    'Kogi': ['Adavi', 'Ajaokuta', 'Ankpa', 'Bassa', 'Dekina', 'Ibaji', 'Idah', 'Igalamela Odolu', 'Ijumu', 'Kabba/Bunu', 'Kogi', 'Lokoja', 'Mopa-Muro', 'Ofu', 'Ogori/Magongo', 'Okehi', 'Okene', 'Olamaboro', 'Omala', 'Yagba East', 'Yagba West'],
    'Kwara': ['Asa', 'Baruten', 'Edu', 'Ekiti', 'Ifelodun', 'Ilorin East', 'Ilorin South', 'Ilorin West', 'Irepodun', 'Isin', 'Kaiama', 'Moro', 'Offa', 'Oke Ero', 'Oyun', 'Pategi'],
    'Lagos': ['Agege', 'Ajeromi-Ifelodun', 'Alimosho', 'Amuwo-Odofin', 'Apapa', 'Badagry', 'Epe', 'Eti-Osa', 'Ibeju-Lekki', 'Ifako-Ijaiye', 'Ikeja', 'Ikorodu', 'Kosofe', 'Lagos Island', 'Lagos Mainland', 'Mushin', 'Ojo', 'Oshodi-Isolo', 'Shomolu', 'Surulere'],
    'Nasarawa': ['Akwanga', 'Awe', 'Doma', 'Karu', 'Keana', 'Keffi', 'Kokona', 'Lafia', 'Nasarawa', 'Nasarawa Egon', 'Obi', 'Toto', 'Wamba'],
    'Niger': ['Agaie', 'Agwara', 'Bida', 'Borgu', 'Bosso', 'Chanchaga', 'Edati', 'Gbako', 'Gurara', 'Katcha', 'Kontagora', 'Lapai', 'Lavun', 'Magama', 'Mariga', 'Mashegu', 'Mokwa', 'Muya', 'Paikoro', 'Rafi', 'Rijau', 'Shiroro', 'Suleja', 'Tafa', 'Wushishi'],
    'Ogun': ['Abeokuta North', 'Abeokuta South', 'Ado-Odo/Ota', 'Ewekoro', 'Ifo', 'Ijebu East', 'Ijebu North', 'Ijebu North East', 'Ijebu Ode', 'Ikenne', 'Imeko Afon', 'Ipokia', 'Obafemi Owode', 'Odeda', 'Odogbolu', 'Ogun Waterside', 'Remo North', 'Shagamu', 'Yewa North', 'Yewa South'],
    'Ondo': ['Akoko North-East', 'Akoko North-West', 'Akoko South-East', 'Akoko South-West', 'Akure North', 'Akure South', 'Ese Odo', 'Idanre', 'Ifedore', 'Ilaje', 'Ile Oluji/Okeigbo', 'Irele', 'Odigbo', 'Okitipupa', 'Ondo East', 'Ondo West', 'Ose', 'Owo'],
    'Osun': ['Aiyedaade', 'Aiyedire', 'Atakunmosa East', 'Atakunmosa West', 'Boluwaduro', 'Boripe', 'Ede North', 'Ede South', 'Egbedore', 'Ejigbo', 'Ife Central', 'Ife East', 'Ife North', 'Ife South', 'Ifedayo', 'Ifelodun', 'Ila', 'Ilesha East', 'Ilesha West', 'Irepodun', 'Irewole', 'Isokan', 'Iwo', 'Obokun', 'Odo Otin', 'Ola Oluwa', 'Olorunda', 'Oriade', 'Orolu', 'Osogbo'],
    'Oyo': ['Afijio', 'Akinyele', 'Atiba', 'Atisbo', 'Egbeda', 'Ibadan North', 'Ibadan North-East', 'Ibadan North-West', 'Ibadan South-East', 'Ibadan South-West', 'Ibarapa Central', 'Ibarapa East', 'Ibarapa North', 'Ido', 'Irepo', 'Iseyin', 'Itesiwaju', 'Iwajowa', 'Kajola', 'Lagelu', 'Ogo Oluwa', 'Ogbomosho North', 'Ogbomosho South', 'Olorunsogo', 'Oluyole', 'Ona Ara', 'Orelope', 'Ori Ire', 'Oyo East', 'Oyo West', 'Saki East', 'Saki West', 'Surulere'],
    'Plateau': ['Barkin Ladi', 'Bassa', 'Bokkos', 'Jos East', 'Jos North', 'Jos South', 'Kanam', 'Kanke', 'Langtang North', 'Langtang South', 'Mangu', 'Mikang', 'Pankshin', 'Qua\'an Pan', 'Riyom', 'Shendam', 'Wase'],
    'Rivers': ['Abua/Odual', 'Ahoada East', 'Ahoada West', 'Akuku Toru', 'Andoni', 'Asari-Toru', 'Bonny', 'Degema', 'Eleme', 'Emohua', 'Etche', 'Gokana', 'Ikwerre', 'Khana', 'Obio-Akpor', 'Ogba/Egbema/Ndoni', 'Ogu/Bolo', 'Okrika', 'Omuma', 'Opobo/Nkoro', 'Oyigbo', 'Port Harcourt', 'Tai'],
    'Sokoto': ['Binji', 'Bodinga', 'Dange Shuni', 'Gada', 'Goronyo', 'Gudu', 'Gwadabawa', 'Illela', 'Isa', 'Kebbe', 'Kware', 'Rabah', 'Sabon Birni', 'Shagari', 'Silame', 'Sokoto North', 'Sokoto South', 'Tambuwal', 'Tangaza', 'Tureta', 'Wamako', 'Wurno', 'Yabo'],
    'Taraba': ['Ardo Kola', 'Bali', 'Donga', 'Gashaka', 'Gassol', 'Ibi', 'Jalingo', 'Karim Lamido', 'Kurmi', 'Lau', 'Sardauna', 'Takum', 'Ussa', 'Wukari', 'Yorro', 'Zing'],
    'Yobe': ['Bade', 'Bursari', 'Damaturu', 'Fika', 'Fune', 'Geidam', 'Gujba', 'Gulani', 'Jakusko', 'Karasuwa', 'Machina', 'Nangere', 'Nguru', 'Potiskum', 'Tarmuwa', 'Yunusari', 'Yusufari'],
    'Zamfara': ['Anka', 'Bakura', 'Birnin Magaji/Kiyaw', 'Bukkuyum', 'Bungudu', 'Chafe', 'Gummi', 'Gusau', 'Kaura Namoda', 'Maradun', 'Maru', 'Shinkafi', 'Talata Mafara', 'Zurmi'],
    'Fct': ['Abaji', 'Bwari', 'Gwagwalada', 'Kuje', 'Kwali', 'Municipal Area Council (AMAC)'],
   
}
    
    return state_lgas.get(state, [])

###########################################################

@app.route('/get_lgas', methods=['GET'])
def get_lgas():
    state = request.args.get('state')
    state = state.title() if state else ""

    lga = fetch_lgas(state)
    
    if lga:
        return jsonify({'lga': lga})
    else:
        return jsonify({'error': 'State not found'}), 404

    
#####################################################################

class InviteeForm(FlaskForm):
    name = StringField('Member Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(message="Invalid email address")])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=11, max=15), Regexp(regex=r'^\+?\d{11,15}$', message="Phone number must contain only digits")
]) # State SelectField
    state = SelectField('State', choices=[
        ('Abia', 'Abia'), ('Adamawa', 'Adamawa'), ('Akwa Ibom', 'Akwa Ibom'),
        ('Anambra', 'Anambra'), ('Bauchi', 'Bauchi'), ('Bayelsa', 'Bayelsa'),
        ('Benue', 'Benue'), ('Borno', 'Borno'), ('Cross River', 'Cross River'),
        ('Delta', 'Delta'), ('Ebonyi', 'Ebonyi'), ('Edo', 'Edo'), ('Ekiti', 'Ekiti'),
        ('Enugu', 'Enugu'), ('Gombe', 'Gombe'), ('Imo', 'Imo'), ('Jigawa', 'Jigawa'),
        ('Kaduna', 'Kaduna'), ('Kano', 'Kano'), ('Katsina', 'Katsina'), ('Kebbi', 'Kebbi'),
        ('Kogi', 'Kogi'), ('Kwara', 'Kwara'), ('Lagos', 'Lagos'), ('Nasarawa', 'Nasarawa'),
        ('Niger', 'Niger'), ('Ogun', 'Ogun'), ('Ondo', 'Ondo'), ('Osun', 'Osun'),
        ('Oyo', 'Oyo'), ('Plateau', 'Plateau'), ('Rivers', 'Rivers'), ('Sokoto', 'Sokoto'),
        ('Taraba', 'Taraba'), ('Yobe', 'Yobe'), ('Zamfara', 'Zamfara'), ('Fct', 'FCT'),
    ], validators=[DataRequired()])
    
    # LGA SelectField (empty initially, will be populated dynamically)
    lga = SelectField('LGA', choices=[],  validators=[Optional()])
    position = StringField('Position', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

#######################################################
class DeleteInviteeForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Delete Invitee')


######################################################

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
            # flash('Login successful!', 'success')
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

######################...helper...#########################

#Helper Function for Logging Actions
def log_action(action_type, user_id, record_type=None, record_id=None):
    print(f'Action Type: {action_type}, User ID: {user_id}, Record Type: {record_type}, Record ID: {record_id}')
    
    # Check if record_type is provided only for delete actions
    if action_type == 'delete' and record_type is None:
        raise ValueError("record_type must be provided for logging deletions.")

    try:
        if action_type == 'delete':
            # Create a DeleteLog entry only for deletions
            delete_log = DeleteLog(
                record_type=record_type,
                record_id=record_id,
                deleted_by=user_id
            )
            db.session.add(delete_log)
        else:
            # Handle other actions (like 'edit', 'create', etc.)
            # You can create separate logs for these actions if needed
            # For now, it's a placeholder print statement
            print(f"Action {action_type} performed by user {user_id}")

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging action: {e}")


##################################################
# ............delete function..................

@app.route('/del_invitee/<int:invitee_id>', methods=['POST'])
@login_required
def del_invitee(invitee_id):
    
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'You do not have access to this action'}), 403

    try:
        # Get CSRF token from the headers
        csrf_token = request.headers.get('X-CSRFToken')
        validate_csrf(csrf_token)  # Validate the token
        
        invitee = Invitee.query.get_or_404(invitee_id)
        
        # Delete associated attendance records if necessary (update this part as needed)
        Invitee.query.filter_by(id=invitee_id).delete()

        # Log the deletion
        log_action('del_invitee', current_user.id, record_type='invitee', record_id=invitee.id)
 
        # Delete the invitee record
        db.session.delete(invitee)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Invitee deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
##################################################
# ............mark attendance function..................

@app.route('/mark_invitee/<int:invitee_id>', methods=['POST'])
@login_required
def mark_invitee(invitee_id):
    
       
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'You do not have access to this action'}), 403
    

    try:

        # Get CSRF token from the headers
        csrf_token = request.headers.get('X-CSRFToken')
        validate_csrf(csrf_token)  # Validate the token

        invitee = Invitee.query.get_or_404(invitee_id)

        if not invitee_id:
            return jsonify({'status': 'error', 'message':'invitee ID is required '}),400
        
        if not invitee:
            return jsonify({'status': 'error', 'message':'invitee not found '}),400
        
        if invitee.confirmed == 'Present':
            return jsonify({'status': 'error', 'message': 'Invitee has already been marked as Present'}), 400

        # Mark the invitee as present
        invitee.confirmed = 'Present'
    
        # Log the deletion
        log_action('del_invitee', current_user.id, record_type='invitee', record_id=invitee.id)
               
        db.session.add(invitee)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Invitee marked Present successfully'}), 200
        
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/manage_invitee', methods=['POST','GET'])
@login_required
def manage_invitee():

    # Ensure only admins can view the page
    if not current_user.is_admin:
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('login'))

    # Get search query and pagination parameters
    search = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Filter based on search input
    if search:
        # user = User.query.filter((Invitee.id== search) | (Invitee.phone_number == search_term)).first()
        invitees_query = Invitee.query.filter(
            (Invitee.id.ilike(f'%{search}%')) | 
            (Invitee.phone_number.ilike(f'%{search}%'))
        )
        if not search:
            flash('Invitee not found', 'danger')
    else:
        invitees_query = Invitee.query

    # Apply pagination
    pagination = invitees_query.order_by(Invitee.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    invitees = pagination.items

     # Render the invitees list
    return render_template('del_inv.html', invitees=invitees, pagination=pagination, search=search)


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

####################################################################

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = InviteeForm()
    
    # Populate LGA choices if state is selected
    if form.state.data:
        form.lga.choices = [(lga, lga) for lga in fetch_lgas(form.state.data)]
    
    if form.validate_on_submit():
        # Get form data
        name = form.name.data.title()
        email = form.email.data.title() 
        phone_number = form.phone_number.data
        state = form.state.data
        lga = form.lga.data  # This is where you capture LGA
        position = form.position.data.title()
        
        # Check for duplicates
        existing_invitee = Invitee.query.filter_by(phone_number=phone_number).first() \
                            or Invitee.query.filter_by(email=email).first()
        if existing_invitee:
            flash("An invitee with this phone number already exists.", "error")
            return redirect(url_for('register'))
        
        if "@" not in form.email.data:
            flash("Invalid email address.", "error")
            return redirect(url_for('register'))

        # Create a new invitee
        new_invitee = Invitee(name=name, phone_number=phone_number, state=state, position=position, lga=lga)
        
        try:
            # Add to session and commit to the database
            db.session.add(new_invitee)
            db.session.commit()

            # Generate QR code after commit
            qr_code_path = generate_qr_code(new_invitee.id)

            #send Qr image via email..
            send_qr_code_email(new_invitee, qr_code_path)

            flash("Registration successful! A confirmation email has been sent!", "success")
            return redirect(url_for('success', qr_code_path=qr_code_path))
        

        except smtplib.SMTPException as e:
            db.session.rollback()
            flash(f"Registration successful, but an error occurred while sending the email: {str(e)}", "error")
            return redirect(url_for('register'))
        
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving to database: {str(e)}", "error")
            return redirect(url_for('register'))
    
    # Render the registration form
    return render_template('register.html', form=form)


@app.route('/success')
def success():
    qr_code_path = request.args.get('qr_code_path')
    if not qr_code_path:
        return 'QR code path is missing', 400
    return render_template('success.html', qr_code_path=qr_code_path)


############################.....................##############

@app.route('/confirm_qr_code', methods=['POST'])
@login_required
@csrf.exempt
def confirm_qr_code():
    qr_code_data = request.json.get('qr_code_data')

    if not qr_code_data:
        return jsonify({'error': 'QR code data is missing'}), 400

    try:
        invitee = Invitee.query.get(qr_code_data)
        if invitee:

            #avoiding reassigning of deleted QR code to invitee
            if invitee.deleted:
                return jsonify({'error': 'Invitee is deleted'}), 400
            
            if invitee.confirmed == "Present":
                return jsonify({
                    'message': 'Invitee already confirmed',
                    'invitee_name': invitee.name,
                    'invitee_phone_number': invitee.phone_number,
                    'invitee_position': invitee.position,
                    'already_confirmed': True,
                }), 200
            else:
                # Confirm the invitee
                invitee.confirmed = "Present"
                db.session.commit()

                return jsonify({
                    'message': 'Invitee confirmed',
                    'invitee_name': invitee.name,
                    'invitee_phone_number': invitee.phone_number,
                    'invitee_position': invitee.position,
                }), 200
        else:
            return jsonify({'error': 'Invitee not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Error confirming invitee'}), 500
    
##############################################

@app.route('/scan_qr')
@admin_required
def scan_qr():
    
    return render_template('scan_qr.html')

###############################################

@app.route('/get_qr_code/<int:invitee_id>')
def get_qr_code(invitee_id):
    qr_code_path = generate_qr_code(invitee_id)
    return jsonify({'qr_code_path': qr_code_path})

################################################################


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

# ##################for opencv...............

@app.route('/scanqrh5')
@admin_required
def scanqrh5():

    return render_template('scanqrh5.html')
##########################################################

 

def send_qr_code_email(invitee, qr_code_path):
    try:
        msg = Message(subject="Registration Confirmation and QR Code",
                      recipients=[invitee.email])
        msg.body = f"Dear {invitee.name},\n\nThank you for registering. Please find your QR code attached."
        
        with app.open_resource(qr_code_path) as qr_code:
            msg.attach("qr_code.png", "image/png", qr_code.read())
        
        mail.send(msg)
        print("Email sent successfully!")

    except smtplib.SMTPException as e:
        # Log the error or handle it (e.g., retry logic)
        print(f"Error sending email: {e}")
        raise e  # Raise the exception back so it can be caught in the calling function
    

#######################################################

# @app.route('/test_email')
# def test_email():
#     try:
#         msg = Message(subject="Test Email",
#                       sender="danwebit@gmail.com",
#                       recipients=["hoghidan1@gmail.com"],
#                       body="This is a test email from Flask.")
#         mail.send(msg)
#         return "Email sent successfully!"
#     except Exception as e:
#         return str(e)

######################################################

if __name__ == '__main__':
        
    # Ensure that the application context is active
    with app.app_context():
        if not os.path.exists('static/qr_codes'):
            os.makedirs('static/qr_codes')
        db.create_all()
        #create default admin
        create_default_admin()
#host='0.0.0.0', enables the app run locally or remotely on a local network
    app.run(host='0.0.0.0',debug=True)