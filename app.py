from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from werkzeug.utils import secure_filename

# ✅ NEW
from flask_mail import Mail, Message
import random

# 🌐 TRANSLATIONS
translations = {
    'en': {
        'register': 'Register',
        'login': 'Login',
        'email': 'Email',
        'password': 'Password',
        'name': 'Name',
        'submit': 'Submit Grievance',
        'logout': 'Logout',
        'dashboard': 'User Dashboard',
        'title': 'Title',
        'description': 'Description',
        'status': 'Status',
        'already_account':'Already have an account?',
        'invalid_login':'Invalid email or password',
        'forgot_password': 'Forgot Password?',
        'back_to_register': 'Back to Register'
    },
    'kn': {
        'register': 'ನೋಂದಣಿ',
        'login': 'ಲಾಗಿನ್',
        'email': 'ಇಮೇಲ್',
        'password': 'ಪಾಸ್‌ವರ್ಡ್',
        'name': 'ಹೆಸರು',
        'submit': 'ಅಭ್ಯರ್ಥನೆ ಸಲ್ಲಿಸಿ',
        'logout': 'ಲಾಗ್ ಔಟ್',
        'dashboard': 'ಬಳಕೆದಾರ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
        'title': 'ಶೀರ್ಷಿಕೆ',
        'description': 'ವಿವರಣೆ',
        'status': 'ಸ್ಥಿತಿ',
        'already_account': 'ಖಾತೆ ಇದೆಯೆ ?',
        'invalid_login': 'ತಪ್ಪಾದ ಇಮೇಲ್ ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್',
        'forgot_password': 'ಪಾಸ್ವರ್ಡ್ ಮರೆತಿರಾ?',
        'back_to_register': 'ನೋಂದಣಿ ಪುಟಕ್ಕೆ ಹಿಂತಿರುಗಿ'
    }
}

app = Flask(__name__)
app.secret_key = "secret123"

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
    return redirect('/login')


# =========================
# REGISTER WITH OTP
# =========================
@app.route('/register', methods=['GET','POST'])
def register():
    lang = session.get('lang', 'en')
    t = translations[lang]

    if request.method == 'POST':
        action = request.form.get('action')

        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        otp_input = request.form.get('otp')

        # 🔹 STEP 1 → SEND OTP
        if action == "send_otp":
            if not name or not email or not password:
                return render_template('register.html', t=t, error="All fields required")

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

            return render_template('register.html', t=t, show_otp=True)

        # 🔹 STEP 2 → VERIFY + REGISTER
        elif action == "verify_otp":
            if otp_input == session.get('otp'):
                user = session.get('temp_user')

                cursor = db.cursor()
                cursor.execute(
                    "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
                    (user['name'], user['email'], user['password'], 'user')
                )
                db.commit()

                session.pop('otp', None)
                session.pop('temp_user', None)

                return redirect('/login')
            else:
                return render_template('register.html', t=t, show_otp=True, error="Invalid OTP")

    return render_template('register.html', t=t)





# =========================
# LOGIN
# =========================
@app.route('/login', methods=['GET','POST'])
def login():
    lang = session.get('lang', 'en')
    t = translations[lang]

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form['password']

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
            return render_template('login.html', t=t, error=t['invalid_login'])

    return render_template('login.html', t=t)


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

        file = request.files['file']
        filename = None

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO grievances (user_id, title, description, category, priority, file_path) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, title, description, category, priority, filename)
        )
        db.commit()

        return redirect('/dashboard')

    lang = session.get('lang', 'en')
    t = translations[lang]

    return render_template('submit.html', t=t)


# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM grievances WHERE user_id=%s", (user_id,))
    data = cursor.fetchall()

    lang = session.get('lang', 'en')
    t = translations[lang]

    return render_template('dashboard.html', grievances=data, t=t)


# =========================
# ADMIN
# =========================
@app.route('/admin')
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/login')

    category = request.args.get('category')
    period = request.args.get('period')

    cursor = db.cursor(dictionary=True)

    data = []
    counts = None
    chart_data = None

    # CATEGORY FILTER
    if category == "All":
        cursor.execute("SELECT * FROM grievances ORDER BY created_at DESC")
        data = cursor.fetchall()

    elif category == "Emergency":
        cursor.execute("SELECT * FROM grievances WHERE priority='Emergency'")
        data = cursor.fetchall()

    elif category:
        cursor.execute("SELECT * FROM grievances WHERE category=%s", (category,))
        data = cursor.fetchall()

    # STATS
    cursor.execute("""
        SELECT 
            COUNT(*) AS total,
            SUM(priority='Emergency') AS emergency,
            SUM(status='Resolved') AS resolved
        FROM grievances
    """)
    stats = cursor.fetchone()

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

    lang = session.get('lang', 'en')
    t = translations[lang]

    return render_template(
        'admin_dashboard.html',
        grievances=data,
        t=t,
        selected_category=category,
        stats=stats,
        alert=alert,
        chart_data=chart_data,
        period=period
    )


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


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