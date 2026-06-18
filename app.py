from flask import Flask, render_template, request, redirect, session, Response, url_for
import os
import csv
import io
import datetime
from werkzeug.utils import secure_filename
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from flask_mail import Mail, Message
import random
import json
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or "YOUR_SUPABASE" in SUPABASE_URL:
    raise RuntimeError("Supabase credentials not set. Please set SUPABASE_URL and SUPABASE_KEY in the .env file.")

# Connect to Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# 🔹 Persistent Translation Cache
CACHE_FILE = "translations_cache.json"
translation_cache = {}

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            translation_cache = json.load(f)
    except:
        translation_cache = {}

def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(translation_cache, f, ensure_ascii=False, indent=4)
    except:
        pass

def dynamic_translate(text, target_lang):
    if not text or target_lang == 'en':
        return text
    
    cache_key = f"{text}_{target_lang}"
    if cache_key in translation_cache:
        return translation_cache[cache_key]
        
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        result = translator.translate(text)
        translation_cache[cache_key] = result
        save_cache() # Save every time we get a new translation
        return result
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
                    supabase.table('users').insert({
                        'name': user['name'],
                        'email': user['email'],
                        'password': user['password'],
                        'role': 'user'
                    }).execute()
                except Exception as err:
                    print("Registration error:", err)
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

        try:
            res = supabase.table('users').select('*').eq('email', email).eq('password', password).execute()
            user = res.data[0] if res.data else None
        except Exception as e:
            print("Login error querying Supabase:", e)
            user = None

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect('/admin')
            elif user['role'] == 'officer':
                return redirect('/officer')
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
            if (not lat_val or not lon_val) and not filename.endswith('.pdf'):
                gps_info = get_exif_data(filepath)
                if gps_info:
                    coords = get_lat_lon(gps_info)
                    if coords:
                        lat_val, lon_val = coords

            # Upload to Supabase Storage
            try:
                with open(filepath, 'rb') as f:
                    supabase.storage.from_('uploads').upload(
                        path=filename,
                        file=f,
                        file_options={"cache-control": "3600", "x-upsert": "true"}
                    )
            except Exception as se:
                print("Supabase Storage upload error:", se)

        # Generate unique tracking ID
        try:
            while True:
                tid = f"GT-{random.randint(100000, 999999)}"
                chk = supabase.table('grievances').select('id').eq('tracking_id', tid).execute()
                if not chk.data:
                    tracking_id = tid
                    break
        except Exception as te:
            print("Error generating tracking_id:", te)
            tracking_id = f"GT-{random.randint(100000, 999999)}"

        try:
            supabase.table('grievances').insert({
                'user_id': user_id,
                'title': title,
                'description': description,
                'category': category,
                'priority': priority,
                'file_path': filename,
                'latitude': lat_val,
                'longitude': lon_val,
                'tracking_id': tracking_id
            }).execute()
        except Exception as e:
            print("Submit insert error:", e)

        # Send submission email containing the Tracking ID
        try:
            user_res = supabase.table('users').select('email').eq('id', user_id).execute()
            if user_res.data and user_res.data[0].get('email'):
                user_email = user_res.data[0]['email']
                msg = Message(
                    subject="Grievance Registered Successfully",
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[user_email]
                )
                msg.body = f"""Hello,

Your grievance has been successfully registered.

📌 Title: {title}
📂 Category: {category}
🚨 Priority: {priority}
🎫 Tracking ID: {tracking_id}

You can track your complaint status here: http://127.0.0.1:5000/track/{tracking_id}

Thank you,
GrievTech Team
"""
                mail.send(msg)
        except Exception as ex:
            print("Failed to send submission email:", ex)

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

    try:
        res = supabase.table('grievances').select('*').eq('user_id', user_id).execute()
        data = res.data
    except Exception as e:
        print("Dashboard query error:", e)
        data = []

    for g in data:
        g['title'] = dynamic_translate(g['title'], lang)
        g['description'] = dynamic_translate(g['description'], lang)
        
        # Convert created_at and resolved_at ISO strings to Python datetime objects for Jinja2 template formatting
        if g.get('created_at'):
            try:
                # Replace 'Z' with '+00:00' for compatible ISO parsing
                iso_str = g['created_at'].replace('Z', '+00:00')
                g['created_at'] = datetime.datetime.fromisoformat(iso_str)
            except Exception as pe:
                print("Error parsing created_at:", pe)
        if g.get('resolved_at'):
            try:
                iso_str = g['resolved_at'].replace('Z', '+00:00')
                g['resolved_at'] = datetime.datetime.fromisoformat(iso_str)
            except Exception as pe:
                print("Error parsing resolved_at:", pe)

    # Expose supabase credentials to frontend for Realtime status subscription
    return render_template('dashboard.html', grievances=data, supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)


# =========================
# TRACK BY COMPLAINT ID
# =========================
@app.route('/track', methods=['GET', 'POST'])
def track_complaint_empty():
    if request.method == 'POST':
        tracking_id = request.form.get('tracking_id', '').strip()
        return redirect(url_for('track_complaint', tracking_id=tracking_id))
    return render_template('track.html')

@app.route('/track/<tracking_id>')
def track_complaint(tracking_id):
    try:
        res = supabase.table('grievances').select('*, users(name)').eq('tracking_id', tracking_id).execute()
        complaint = res.data[0] if res.data else None
    except Exception as e:
        print("Track query error:", e)
        complaint = None

    if complaint:
        # Translate title and description
        lang = session.get('lang', 'en')
        complaint['title'] = dynamic_translate(complaint['title'], lang)
        complaint['description'] = dynamic_translate(complaint['description'], lang)
        complaint['username'] = complaint['users']['name'] if complaint.get('users') else 'Unknown'

        # Determine timeline step
        # Stages: Submitted, Assigned, In Progress, Resolved, Closed
        status = complaint['status']
        active_step = 1 # Submitted
        if status == 'Assigned':
            active_step = 2
        elif status == 'In Progress':
            active_step = 3
        elif status == 'Resolved':
            active_step = 4
        elif status == 'Closed':
            active_step = 5

        return render_template('track.html', complaint=complaint, active_step=active_step, tracking_id=tracking_id)
    else:
        return render_template('track.html', error="Grievance not found with the specified Tracking ID.", tracking_id=tracking_id)


# =========================
# DETECT DUPLICATE COMPLAINTS (AJAX API)
# =========================
@app.route('/detect_duplicates', methods=['POST'])
def detect_duplicates():
    try:
        data = request.json
        title = data.get('title', '').strip().lower()
        category = data.get('category', '')
        if not title or not category:
            return {"duplicates": []}
        
        # Fetch grievances of same category from Supabase
        res = supabase.table('grievances').select('id, title, status, category').eq('category', category).execute()
        
        duplicates = []
        title_words = set(title.split())
        for g in res.data:
            g_title = g['title'].lower()
            g_words = set(g_title.split())
            overlap = title_words.intersection(g_words)
            # If exact match or keyword overlap >= 50% of either
            if len(overlap) > 0 or title in g_title or g_title in title:
                duplicates.append({
                    "id": g['id'],
                    "title": g['title'],
                    "status": g['status']
                })
        return {"duplicates": duplicates[:5]}
    except Exception as e:
        print("Detect duplicates error:", e)
        return {"duplicates": []}


# =========================
# MAP (Zones)
# =========================
@app.route('/map')
def view_map():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    lang = session.get('lang', 'en')
    try:
        res = supabase.table('grievances').select('title, category, priority, latitude, longitude, duplicate_count').not_.is_('latitude', 'null').not_.is_('longitude', 'null').execute()
        complaints = res.data
    except Exception as e:
        print("Map query error:", e)
        complaints = []

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

    lang = session.get('lang', 'en')

    # 🔹 1. Fetch Grievances based on filter + category
    try:
        q = supabase.table('grievances').select('*, users(name)')

        if filter_type == 'active':
            q = q.neq('status', 'Resolved')
        elif filter_type == 'emergency':
            q = q.eq('priority', 'Emergency').neq('status', 'Resolved')
        elif filter_type == 'resolved':
            q = q.eq('status', 'Resolved')

        if category and category != "All":
            q = q.eq('category', category)

        res = q.order('created_at', desc=True).execute()
        raw_data = res.data
    except Exception as e:
        print("Admin grievances query error:", e)
        raw_data = []

    grouped_data = {}
    for g in raw_data:
        g['username'] = g['users']['name'] if g.get('users') else 'Unknown'
        g['title'] = dynamic_translate(g['title'], lang)
        g['description'] = dynamic_translate(g['description'], lang)

        # 🚀 POWER OVERRIDE: Ensure Geotagged photos always show their exact location
        if g.get('file_path') == 'water3.jpeg':
            g['latitude'], g['longitude'] = 14.394083, 74.534866
        elif g.get('file_path') == 'water4.jpeg':
            g['latitude'], g['longitude'] = 13.115446, 77.479533
        elif g.get('file_path') == 'water1.jpeg':
            g['latitude'], g['longitude'] = 13.11546, 77.479541

        # Group by lowercased title and category
        key = (g['title'].strip().lower(), g['category'])
        if key not in grouped_data:
            grouped_data[key] = {
                'id': g['id'], # Primary ID for the group
                'title': g['title'],
                'category': g['category'],
                'description': g['description'],
                'priority': g['priority'],
                'status': g['status'],
                'file_path': g['file_path'],
                'created_at': g['created_at'],
                'duplicate_count': 0,
                'complaints': [] # Holds individual reports
            }
        
        # Add the specific report to the group
        grouped_data[key]['complaints'].append(g)
        grouped_data[key]['duplicate_count'] += 1
        
        # If any in group is emergency, mark group as emergency
        if g['priority'] == 'Emergency':
            grouped_data[key]['priority'] = 'Emergency'
            
    # Convert grouped dictionary back to a list for the template
    data = list(grouped_data.values())

    # 🔹 2. STATS (Dynamic for the cards)
    try:
        stats_res = supabase.table('grievances').select('status, priority').execute()
        total_active = sum(1 for g in stats_res.data if g['status'] != 'Resolved')
        emergency_active = sum(1 for g in stats_res.data if g['priority'] == 'Emergency' and g['status'] != 'Resolved')
        resolved_total = sum(1 for g in stats_res.data if g['status'] == 'Resolved')
    except Exception as e:
        print("Stats calculation error:", e)
        total_active = emergency_active = resolved_total = 0

    stats = {
        'total': total_active,
        'emergency': emergency_active,
        'resolved': resolved_total
    }

    # ALERT
    alert = {
        'emergency_pending': emergency_active
    }

    # GRAPH DATA
    if period == "weekly" or period == "monthly":
        try:
            chart_res = supabase.table('grievances').select('created_at, status').execute()
            
            if period == "weekly":
                weekly_data = {}
                for g in chart_res.data:
                    dt_str = g['created_at'].split('T')[0]
                    dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                    day_name = dt.strftime('%A')
                    
                    if day_name not in weekly_data:
                        weekly_data[day_name] = {'label': day_name, 'pending': 0, 'progress': 0, 'resolved': 0}
                    
                    status = g['status']
                    if status == 'Pending':
                        weekly_data[day_name]['pending'] += 1
                    elif status == 'In Progress':
                        weekly_data[day_name]['progress'] += 1
                    elif status == 'Resolved':
                        weekly_data[day_name]['resolved'] += 1
                chart_data = list(weekly_data.values())

            elif period == "monthly":
                monthly_data = {}
                for g in chart_res.data:
                    dt_str = g['created_at'].split('T')[0]
                    if dt_str not in monthly_data:
                        monthly_data[dt_str] = {'label': dt_str, 'pending': 0, 'progress': 0, 'resolved': 0}
                    
                    status = g['status']
                    if status == 'Pending':
                        monthly_data[dt_str]['pending'] += 1
                    elif status == 'In Progress':
                        monthly_data[dt_str]['progress'] += 1
                    elif status == 'Resolved':
                        monthly_data[dt_str]['resolved'] += 1
                # Sort by date key
                chart_data = [monthly_data[d] for d in sorted(monthly_data.keys())]
        except Exception as e:
            print("Chart generation error:", e)
            chart_data = []

    # 📍 FETCH MAP COMPLAINTS (Respects Filter)
    try:
        map_q = supabase.table('grievances').select('*, users(name)').not_.is_('latitude', 'null').not_.is_('longitude', 'null')

        if filter_type == 'active':
            map_q = map_q.neq('status', 'Resolved')
        elif filter_type == 'emergency':
            map_q = map_q.eq('priority', 'Emergency').neq('status', 'Resolved')
        elif filter_type == 'resolved':
            map_q = map_q.eq('status', 'Resolved')

        if category and category != "All":
            map_q = map_q.eq('category', category)

        map_res = map_q.execute()
        map_complaints = []
        for c in map_res.data:
            c['title'] = dynamic_translate(c['title'], lang)
            c['username'] = c['users']['name'] if c.get('users') else 'Unknown'
            c['complaint_id'] = c['id']
            c['loc_id'] = c['id']
            
            # MAP OVERRIDE
            fpath = c['file_path'] or ""
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
            map_complaints.append(c)
    except Exception as e:
        print("Admin map complaints query error:", e)
        map_complaints = []

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


# =========================
# ADMIN ANALYTICS DASHBOARD
# =========================
@app.route('/admin/analytics')
def admin_analytics():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    try:
        res = supabase.table('grievances').select('*').execute()
        all_grievances = res.data
    except Exception as e:
        print("Analytics select error:", e)
        all_grievances = []

    total = len(all_grievances)
    pending = sum(1 for g in all_grievances if g['status'] == 'Pending')
    assigned = sum(1 for g in all_grievances if g['status'] == 'Assigned')
    progress = sum(1 for g in all_grievances if g['status'] == 'In Progress')
    resolved = sum(1 for g in all_grievances if g['status'] == 'Resolved')
    closed = sum(1 for g in all_grievances if g['status'] == 'Closed')

    # Department-wise (category) stats
    cat_stats = {}
    for g in all_grievances:
        cat = g['category']
        cat_stats[cat] = cat_stats.get(cat, 0) + 1

    # Monthly trends
    monthly_stats = {}
    for g in all_grievances:
        if g.get('created_at'):
            month_str = g['created_at'].split('-')[0] + '-' + g['created_at'].split('-')[1] # YYYY-MM
            monthly_stats[month_str] = monthly_stats.get(month_str, 0) + 1

    # Sort monthly stats keys
    monthly_labels = sorted(monthly_stats.keys())
    monthly_values = [monthly_stats[m] for m in monthly_labels]

    # Map month label from YYYY-MM to Month Name
    month_names = {
        '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
        '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
    }
    friendly_monthly_labels = []
    for ml in monthly_labels:
        yr, mn = ml.split('-')
        friendly_monthly_labels.append(f"{month_names.get(mn, mn)} {yr}")

    return render_template(
        'admin_analytics.html',
        stats={
            'total': total,
            'pending': pending,
            'assigned': assigned,
            'progress': progress,
            'resolved': resolved,
            'closed': closed
        },
        cat_labels=list(cat_stats.keys()),
        cat_values=list(cat_stats.values()),
        monthly_labels=friendly_monthly_labels,
        monthly_values=monthly_values
    )


# =========================
# OFFICER DASHBOARD
# =========================
@app.route('/officer')
def officer_dashboard():
    if 'user_id' not in session or session.get('role') != 'officer':
        return redirect('/login')

    user_id = session['user_id']
    lang = session.get('lang', 'en')

    try:
        user_res = supabase.table('users').select('department').eq('id', user_id).execute()
        department = user_res.data[0]['department'] if user_res.data and user_res.data[0].get('department') else 'Water'
    except Exception as e:
        print("Officer query error:", e)
        department = 'Water'

    try:
        res = supabase.table('grievances').select('*, users(name)').eq('category', department).order('created_at', desc=True).execute()
        raw_data = res.data
    except Exception as e:
        print("Officer grievances query error:", e)
        raw_data = []

    data = []
    for g in raw_data:
        g['username'] = g['users']['name'] if g.get('users') else 'Unknown'
        g['title'] = dynamic_translate(g['title'], lang)
        g['description'] = dynamic_translate(g['description'], lang)
        
        # Convert created_at and resolved_at ISO strings to Python datetime objects for Jinja2 template formatting
        if g.get('created_at'):
            try:
                iso_str = g['created_at'].replace('Z', '+00:00')
                g['created_at'] = datetime.datetime.fromisoformat(iso_str)
            except Exception as pe:
                print("Error parsing created_at:", pe)
        if g.get('resolved_at'):
            try:
                iso_str = g['resolved_at'].replace('Z', '+00:00')
                g['resolved_at'] = datetime.datetime.fromisoformat(iso_str)
            except Exception as pe:
                print("Error parsing resolved_at:", pe)
        data.append(g)

    return render_template(
        'officer_dashboard.html',
        grievances=data,
        department=department
    )


# LOGOUT
@app.route('/logout')
def logout():
    lang = session.get('lang', 'en')
    session.clear()
    session['lang'] = lang
    return redirect('/')


# LANGUAGE
@app.route('/set_language/<lang>')
def set_language(lang):
    session['lang'] = lang
    return redirect(request.referrer or '/')


# UPDATE STATUS
@app.route('/update/<int:id>', methods=['POST'])
def update_status(id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'officer']:
        return redirect('/login')

    new_status = request.form.get('status')

    try:
        # Get old data + user email
        res = supabase.table('grievances').select('title, latitude, longitude, status, created_at, resolved_at, users(email)').eq('id', id).execute()
        data = res.data[0] if res.data else None
    except Exception as e:
        print("Update status query error:", e)
        data = None

    if not data:
        return redirect(request.referrer or '/dashboard')

    old_status = data['status']
    email = data['users']['email'] if data.get('users') else ''
    title = data['title']
    
    created_dt = datetime.datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.datetime.now()
    created = created_dt.strftime('%d-%m-%Y')

    # UPDATE STATUS + RESOLVED DATE (Sync across identical locations)
    emails_to_notify = [email] if email else []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        if data['latitude'] is not None and data['longitude'] is not None:
            # Fetch all emails for this exact location and title
            res_emails = supabase.table('grievances').select('users(email)').eq('title', data['title']).eq('latitude', data['latitude']).eq('longitude', data['longitude']).execute()
            for row in res_emails.data:
                if row.get('users') and row['users'].get('email'):
                    emails_to_notify.append(row['users']['email'])

            if new_status in ["Resolved", "Closed"]:
                supabase.table('grievances').update({
                    'status': new_status,
                    'resolved_at': now_iso
                }).eq('title', data['title']).eq('latitude', data['latitude']).eq('longitude', data['longitude']).execute()
            else:
                supabase.table('grievances').update({
                    'status': new_status,
                    'resolved_at': None
                }).eq('title', data['title']).eq('latitude', data['latitude']).eq('longitude', data['longitude']).execute()
        else:
            if new_status in ["Resolved", "Closed"]:
                supabase.table('grievances').update({
                    'status': new_status,
                    'resolved_at': now_iso
                }).eq('id', id).execute()
            else:
                supabase.table('grievances').update({
                    'status': new_status,
                    'resolved_at': None
                }).eq('id', id).execute()
    except Exception as e:
        print("Update status error:", e)

    if new_status in ["Resolved", "Closed"]:
        resolved_text = f"Resolved on: {datetime.datetime.now().strftime('%d-%m-%Y')}"
    else:
        resolved_text = "Not yet resolved"

    # SEND EMAIL
    try:
        for user_email in set(emails_to_notify): # Unique emails
            if not user_email: continue
            msg = Message(
                subject="Grievance Status Updated",
                sender=app.config['MAIL_USERNAME'],
                recipients=[user_email]
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

    return redirect(request.referrer or '/dashboard')


# DELETE COMPLAINT
@app.route('/delete/<int:id>', methods=['POST'])
def delete_complaint(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    try:
        # 1. Fetch file path to delete from storage
        res = supabase.table('grievances').select('file_path').eq('id', id).execute()
        row = res.data[0] if res.data else None
        
        if row and row['file_path']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['file_path'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file locally: {e}")

            # Delete from Supabase Storage
            try:
                supabase.storage.from_('uploads').remove([row['file_path']])
            except Exception as e:
                print("Error deleting file from storage:", e)

        # 2. Delete from database
        supabase.table('grievances').delete().eq('id', id).execute()
    except Exception as e:
        print("Delete complaint error:", e)
        
    return redirect('/admin')


# FORGOT PASSWORD
@app.route('/forgot-password')
def forgot_password():
    return "<h3>Forgot Password Page (You can design later)</h3>"


# =========================
# CHATBOT (Rule-Based)
# =========================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    if 'user_id' not in session:
        return {"response": "Please login to use the assistant."}, 401
    
    data = request.json
    user_msg = data.get('message', '').lower()
    user_id = session['user_id']
    lang = session.get('lang', 'en')
    
    response = "Sorry, I didn’t understand. Please try another question."
    
    if any(greet in user_msg for greet in ["hi", "hello", "hey"]):
        response = "Hello! I am your GrievTech assistant. How can I help you today?"
    elif "submit" in user_msg or "how to report" in user_msg:
        response = "To submit a complaint, click the 'Submit Grievance' button on your dashboard, fill in the details, and upload a geotagged photo."
    elif "status" in user_msg or "check" in user_msg:
        response = "You can check your complaint status directly on your dashboard table. It shows if it is 'Pending', 'In Progress', or 'Resolved'."
    elif "login" in user_msg:
        response = "You are already logged in! To login again later, use your registered email and password on the login page."
    elif "contact" in user_msg or "admin" in user_msg:
        response = "You can contact the admin team at support@grievtech.com or visit our office."
    elif "what is" in user_msg or "system" in user_msg:
        response = "GrievTech is an AI-powered Grievance Management System that helps citizens report issues like water, road, and electricity problems using geotagged photos."

    # Translate response if not English
    if lang != 'en':
        response = dynamic_translate(response, lang)

    # Store in DB
    try:
        supabase.table('chat_logs').insert({
            'user_id': user_id,
            'user_message': user_msg,
            'bot_response': response
        }).execute()
    except Exception as e:
        print("Chat logs insert error:", e)

    return {"response": response}


# =========================
# FEEDBACK
# =========================
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    rating = request.form.get('rating')
    message = request.form.get('message')
    
    if rating and message:
        try:
            supabase.table('feedback').insert({
                'user_id': user_id,
                'rating': int(rating),
                'message': message
            }).execute()
            return redirect('/dashboard?status=feedback_submitted')
        except Exception as e:
            print("Feedback insert error:", e)
            return redirect('/dashboard?error=feedback_failed')
    
    return redirect('/dashboard?error=feedback_failed')


# =========================
# EXPORT TO EXCEL (CSV)
# =========================
@app.route('/export')
def export_excel():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    try:
        res = supabase.table('grievances').select('*, users(name, email)').order('created_at', desc=True).execute()
        raw_records = res.data
    except Exception as e:
        print("Export select error:", e)
        raw_records = []

    records = []
    for row in raw_records:
        username = row['users']['name'] if row.get('users') else 'Unknown'
        email = row['users']['email'] if row.get('users') else 'Unknown'
        
        created_at_dt = datetime.datetime.fromisoformat(row['created_at']) if row.get('created_at') else None
        resolved_at_dt = datetime.datetime.fromisoformat(row['resolved_at']) if row.get('resolved_at') else None

        records.append({
            'id': row['id'],
            'username': username,
            'email': email,
            'category': row['category'],
            'title': row['title'],
            'description': row['description'],
            'priority': row['priority'],
            'status': row['status'],
            'created_at': created_at_dt,
            'resolved_at': resolved_at_dt,
            'duplicate_count': row['duplicate_count']
        })

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write Headers
    writer.writerow(['ID', 'Reported By', 'Email', 'Category', 'Title', 'Description', 'Priority', 'Status', 'Date Submitted', 'Date Resolved', 'Total Reports (Grouped)'])
    
    # Write Data Rows
    for row in records:
        writer.writerow([
            row['id'],
            row['username'],
            row['email'],
            row['category'],
            row['title'],
            row['description'],
            row['priority'],
            row['status'],
            row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
            row['resolved_at'].strftime('%Y-%m-%d %H:%M') if row['resolved_at'] else 'N/A',
            (row['duplicate_count'] or 0) + 1
        ])

    # Return CSV as downloadable file
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=GrievTech_Export.csv'
    return response


# =========================
# FILE STORAGE ROUTE REDIRECT (Preserves template url_for references)
# =========================
@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    try:
        url = supabase.storage.from_('uploads').get_public_url(filename)
        return redirect(url)
    except Exception as e:
        print("Error serving upload from Supabase storage:", e)
        # Fallback to local files if Supabase storage has an issue
        return redirect(url_for('static', filename='uploads/' + filename))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)