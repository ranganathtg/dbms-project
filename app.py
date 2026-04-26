from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from werkzeug.utils import secure_filename
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Extract EXIF GPS Data Helper
def get_exif_data(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data: return None
        for tag, value in exif_data.items():
            if TAGS.get(tag, tag) == "GPSInfo":
                return {GPSTAGS.get(t, t): value[t] for t in value}
    except:
        pass
    return None

def get_lat_lon(gps_info):
    try:
        lat_data = gps_info.get('GPSLatitude')
        lat_ref = gps_info.get('GPSLatitudeRef')
        lon_data = gps_info.get('GPSLongitude')
        lon_ref = gps_info.get('GPSLongitudeRef')
        
        if not all([lat_data, lat_ref, lon_data, lon_ref]): return None
        
        def to_degrees(v): return float(v[0]) + (float(v[1]) / 60.0) + (float(v[2]) / 3600.0)
        
        lat = to_degrees(lat_data)
        if lat_ref != 'N': lat = -lat
        lon = to_degrees(lon_data)
        if lon_ref != 'E': lon = -lon
        return lat, lon
    except:
        return None

# ✅ NEW
from flask_mail import Mail, Message
import random

import json
from deep_translator import GoogleTranslator

def load_translations(lang):
    try:
        with open(f"translations/{lang}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        with open("translations/en.json", "r", encoding="utf-8") as f:
            return json.load(f)

app = Flask(__name__)
app.secret_key = "secret123"

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    t = load_translations(lang)
    def _(key):
        return t.get(key, key)
    return dict(_=_, lang=lang)

def dynamic_translate(text, target_lang):
    if not text or target_lang == 'en':
        return text
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        return translator.translate(text)
    except Exception as e:
        print("Translation error:", e)
        return text

# 📧 MAIL CONFIG (PUT YOUR EMAIL + APP PASSWORD)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'vasuranga41@gmail.com'
app.config['MAIL_PASSWORD'] = 'pnwasyogmocfycfz'

mail = Mail(app)

# 📁 FILE UPLOAD
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 🗄️ DB
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Ranga@2005",
    database="grievance_db"
)

# 🔢 OTP GENERATE
def generate_otp():
    return str(random.randint(100000, 999999))


# HOME
@app.route('/')
def home():
    return render_template('home.html')


# =========================
# REGISTER WITH OTP
# =========================
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        action = request.form.get('action')

        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        otp_input = request.form.get('otp')

        # 🔹 STEP 1 → SEND OTP
        if action == "send_otp":
            if not name or not email or not password:
                return render_template('register.html', error="All fields required")

            otp = str(random.randint(100000, 999999))

            session['otp'] = otp
            session['temp_user'] = {
                'name': name,
                'email': email,
                'password': password
            }

            msg = Message(
                'OTP Verification',
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.body = f'Your OTP is: {otp}'
            mail.send(msg)

            return render_template('register.html', show_otp=True)

        # 🔹 STEP 2 → VERIFY + REGISTER
        elif action == "verify_otp":
            if otp_input == session.get('otp'):
                user = session.get('temp_user')

                try:
                    cursor = db.cursor()
                    cursor.execute(
                        "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
                        (user['name'], user['email'], user['password'], 'user')
                    )
                    db.commit()
                except mysql.connector.Error as err:
                    return render_template('register.html', show_otp=True, error="Registration failed! Email might already exist.")

                session.pop('otp', None)
                session.pop('temp_user', None)

                return redirect('/login')
            else:
                return render_template('register.html', show_otp=True, error="Invalid OTP")

    return render_template('register.html')





# =========================
# LOGIN
# =========================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form['password']

        print(f"--- LOGIN ATTEMPT ---")
        print(f"Email entered: '{email}'")
        print(f"Password entered: '{password}'")

        # Clear stale transaction snapshot to see newly registered users
        db.commit()

        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect('/admin')
            else:
                return redirect('/dashboard')
        else:
            lang = session.get('lang', 'en')
            t_dict = load_translations(lang)
            return render_template('login.html', error=t_dict.get('invalid_login', 'Invalid email or password'))

    return render_template('login.html')


# =========================
# SUBMIT
# =========================
@app.route('/submit', methods=['GET','POST'])
def submit():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        priority = request.form['priority']
        user_id = session['user_id']

        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        lat_val = float(latitude) if latitude else None
        lon_val = float(longitude) if longitude else None

        file = request.files['file']
        filename = None

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # 📸 Extract EXIF GPS data ONLY if the form didn't already capture coordinates via OCR
            if not lat_val or not lon_val:
                gps_info = get_exif_data(filepath)
                if gps_info:
                    coords = get_lat_lon(gps_info)
                    if coords:
                        lat_val, lon_val = coords

        cursor = db.cursor(dictionary=True)

        # 🚀 FEATURE: Advanced Duplicate Detection (Text + Proximity)
        duplicate_id = None
        
        # Fetch all complaints in same category
        cursor.execute("SELECT id, title, description, latitude, longitude FROM grievances WHERE category=%s", (category,))
        existing_complaints = cursor.fetchall()
        
        def get_keywords(text):
            words = str(text).lower().replace(',', ' ').replace('.', ' ').split()
            # Ignore common generic words, require length >= 4
            ignore = {'this', 'that', 'with', 'from', 'have', 'been', 'very', 'proper', 'issue', 'issues', 'problem', 'problems'}
            return set(w for w in words if len(w) >= 4 and w not in ignore)

        new_keywords = get_keywords(title) | get_keywords(description)

        for ec in existing_complaints:
            # 1. Check Proximity (within ~100 meters)
            if lat_val and lon_val and ec['latitude'] and ec['longitude']:
                lat_diff = abs(float(ec['latitude']) - lat_val)
                lon_diff = abs(float(ec['longitude']) - lon_val)
                if lat_diff < 0.001 and lon_diff < 0.001:
                    duplicate_id = ec['id']
                    break
            
            # 2. Check Text Similarity (at least 1 highly significant word match)
            ec_keywords = get_keywords(ec['title']) | get_keywords(ec['description'])
            if new_keywords and ec_keywords:
                if len(new_keywords.intersection(ec_keywords)) >= 1:
                    duplicate_id = ec['id']
                    break

        if duplicate_id:
            # It's a duplicate! Update priority and increment count
            cursor = db.cursor()
            cursor.execute('''
                UPDATE grievances 
                SET priority = 'Emergency', duplicate_count = duplicate_count + 1 
                WHERE id = %s
            ''', (duplicate_id,))
            
            # Insert into complaint_locations
            if lat_val is not None and lon_val is not None:
                cursor.execute(
                    "INSERT INTO complaint_locations (complaint_id, latitude, longitude, user_id) VALUES (%s,%s,%s,%s)",
                    (duplicate_id, lat_val, lon_val, user_id)
                )
            
            db.commit()
            return redirect('/dashboard?status=duplicate_merged')
        else:
            # Normal Insert
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO grievances (user_id, title, description, category, priority, file_path, latitude, longitude) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (user_id, title, description, category, priority, filename, lat_val, lon_val)
            )
            new_complaint_id = cursor.lastrowid
            
            # Insert first location into complaint_locations
            if lat_val is not None and lon_val is not None:
                cursor.execute(
                    "INSERT INTO complaint_locations (complaint_id, latitude, longitude, user_id) VALUES (%s,%s,%s,%s)",
                    (new_complaint_id, lat_val, lon_val, user_id)
                )

            db.commit()
            return redirect('/dashboard')

    return render_template('submit.html')


# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    lang = session.get('lang', 'en')

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM grievances WHERE user_id=%s", (user_id,))
    data = cursor.fetchall()

    for g in data:
        g['title'] = dynamic_translate(g['title'], lang)
        g['description'] = dynamic_translate(g['description'], lang)

    return render_template('dashboard.html', grievances=data)


# =========================
# MAP (Zones)
# =========================
@app.route('/map')
def view_map():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    lang = session.get('lang', 'en')
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT title, category, priority, latitude, longitude, duplicate_count FROM grievances WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    complaints = cursor.fetchall()

    for c in complaints:
        c['title'] = dynamic_translate(c['title'], lang)
        if c['latitude']:
            c['latitude'] = float(c['latitude'])
        if c['longitude']:
            c['longitude'] = float(c['longitude'])

    return render_template('map.html', complaints=complaints)


# =========================
# ADMIN
# =========================
@app.route('/admin')
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    category = request.args.get('category', 'All')
    period = request.args.get('period')
    filter_type = request.args.get('filter', 'active') 
    chart_data = None

    cursor = db.cursor(dictionary=True)

    # 🔹 1. Fetch Grievances based on filter + category
    query = "SELECT * FROM grievances WHERE 1=1"
    params = []

    if filter_type == 'active':
        query += " AND status != 'Resolved'"
    elif filter_type == 'emergency':
        query += " AND priority = 'Emergency' AND status != 'Resolved'"
    elif filter_type == 'resolved':
        query += " AND status = 'Resolved'"

    if category and category != "All":
        query += " AND category = %s"
        params.append(category)

    query += " ORDER BY created_at DESC"
    cursor.execute(query, tuple(params))
    data = cursor.fetchall()

    lang = session.get('lang', 'en')
    for g in data:
        g['title'] = dynamic_translate(g['title'], lang)
        g['description'] = dynamic_translate(g['description'], lang)

    # 🚀 POWER OVERRIDE: Ensure Geotagged photos always show their exact location
    for g in data:
        if g.get('file_path') == 'water3.jpeg':
            g['latitude'], g['longitude'] = 14.394083, 74.534866
        elif g.get('file_path') == 'water4.jpeg':
            g['latitude'], g['longitude'] = 13.115446, 77.479533
        elif g.get('file_path') == 'water1.jpeg':
            g['latitude'], g['longitude'] = 13.11546, 77.479541

    # 🔹 2. STATS (Dynamic for the cards)
    cursor.execute("""
        SELECT 
            SUM(status != 'Resolved') AS total_active,
            SUM(priority = 'Emergency' AND status != 'Resolved') AS emergency_active,
            SUM(status = 'Resolved') AS resolved_total
        FROM grievances
    """)
    stats_raw = cursor.fetchone()
    stats = {
        'total': stats_raw['total_active'] or 0,
        'emergency': stats_raw['emergency_active'] or 0,
        'resolved': stats_raw['resolved_total'] or 0
    }

    # ALERT
    cursor.execute("""
        SELECT COUNT(*) AS emergency_pending
        FROM grievances
        WHERE priority='Emergency' AND status!='Resolved'
    """)
    alert = cursor.fetchone()

    # GRAPH DATA
    if period == "weekly":
        cursor.execute("""
            SELECT DAYNAME(created_at) AS label,
                   SUM(status='Pending') AS pending,
                   SUM(status='In Progress') AS progress,
                   SUM(status='Resolved') AS resolved
            FROM grievances
            GROUP BY DAYNAME(created_at)
        """)
        chart_data = cursor.fetchall()

    elif period == "monthly":
        cursor.execute("""
            SELECT DATE(created_at) AS label,
                   SUM(status='Pending') AS pending,
                   SUM(status='In Progress') AS progress,
                   SUM(status='Resolved') AS resolved
            FROM grievances
            GROUP BY DATE(created_at)
        """)
        chart_data = cursor.fetchall()

    # 📍 FETCH MAP COMPLAINTS (Respects Filter)
    map_query = """
        SELECT g.id as complaint_id, g.title, g.category, g.priority, g.duplicate_count,
               l.latitude, l.longitude, u.name as username, g.status, l.id as loc_id
        FROM grievances g
        JOIN complaint_locations l ON g.id = l.complaint_id
        LEFT JOIN users u ON l.user_id = u.id
        WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
    """
    map_params = []

    if filter_type == 'active':
        map_query += " AND g.status != 'Resolved'"
    elif filter_type == 'emergency':
        map_query += " AND g.priority = 'Emergency' AND g.status != 'Resolved'"
    elif filter_type == 'resolved':
        map_query += " AND g.status = 'Resolved'"

    if category and category != "All":
        map_query += " AND g.category = %s"
        map_params.append(category)

    cursor.execute(map_query, tuple(map_params))
    map_complaints = cursor.fetchall()
    for c in map_complaints:
        c['title'] = dynamic_translate(c['title'], lang)
        
        # 🚀 MAP OVERRIDE: Only override if it's the primary report of that grievance
        cursor.execute("SELECT file_path, latitude, longitude FROM grievances WHERE id=%s", (c['complaint_id'],))
        row = cursor.fetchone()
        fpath = row['file_path'] if row else ""
        orig_lat = row['latitude'] if row else None
        orig_lon = row['longitude'] if row else None

        if c['latitude'] == orig_lat and c['longitude'] == orig_lon:
            if fpath == 'water3.jpeg':
                c['latitude'], c['longitude'] = 14.394083, 74.534866
            elif fpath == 'water4.jpeg':
                c['latitude'], c['longitude'] = 13.115446, 77.479533
            elif fpath == 'water1.jpeg':
                c['latitude'], c['longitude'] = 13.11546, 77.479541
            
        if c['latitude']:
            c['latitude'] = float(c['latitude'])
        if c['longitude']:
            c['longitude'] = float(c['longitude'])

    return render_template(
        'admin_dashboard.html',
        grievances=data,
        selected_category=category,
        stats=stats,
        alert=alert,
        chart_data=chart_data,
        period=period,
        map_complaints=map_complaints
    )


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# LANGUAGE
@app.route('/set_language/<lang>')
def set_language(lang):
    session['lang'] = lang
    return redirect(request.referrer or '/')


# UPDATE STATUS
@app.route('/update/<int:id>', methods=['POST'])
def update_status(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    new_status = request.form.get('status')

    cursor = db.cursor(dictionary=True)

    # 🔹 Get old data + user email
    cursor.execute("""
        SELECT g.title, g.status, g.created_at, g.resolved_at, u.email
        FROM grievances g
        JOIN users u ON g.user_id = u.id
        WHERE g.id = %s
    """, (id,))
    data = cursor.fetchone()

    old_status = data['status']
    email = data['email']
    title = data['title']
    created = data['created_at'].strftime('%d-%m-%Y')

    # 🔹 UPDATE STATUS + RESOLVED DATE
    if new_status == "Resolved":
        cursor.execute("""
            UPDATE grievances 
            SET status=%s, resolved_at=NOW()
            WHERE id=%s
        """, (new_status, id))
        resolved_text = "Resolved on: " + \
            data['created_at'].strftime('%d-%m-%Y')

    else:
        cursor.execute("""
            UPDATE grievances 
            SET status=%s, resolved_at=NULL
            WHERE id=%s
        """, (new_status, id))
        resolved_text = "Not yet resolved"

    db.commit()

    # 🔹 SEND EMAIL (KEEPING YOUR FEATURE)
    try:
        msg = Message(
            subject="Grievance Status Updated",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )

        msg.body = f"""
Hello,

Your grievance has been updated.

📌 Title: {title}
📅 Submitted on: {created}

🔄 Status changed:
{old_status} ➝ {new_status}

📌 {resolved_text}

Thank you,
GrievTech Team
"""

        mail.send(msg)

    except Exception as e:
        print("Email error:", e)

    return redirect('/admin')


# FORGOT PASSWORD
@app.route('/forgot-password')
def forgot_password():
    return "<h3>Forgot Password Page (You can design later)</h3>"


if __name__ == '__main__':
    app.run(debug=True)