# GrievTech - Public Grievance Management System

GrievTech is a production-ready, modern web application designed to help citizens report and track public grievances (such as water shortages, road damage, electricity failures, and garbage disposal issues). The platform connects citizens, officers, and administrators with secure databases, automated notifications, and AI-driven duplicate detection.

---

## 🚀 Key Features

*   **Secure User Authentication**: Complete registration with **OTP verification** sent directly to the user's email.
*   **Grievance Submission & Media Uploads**: Citizens can describe issues, locate them automatically (with EXIF GPS data extraction from photos), and upload attachments (images/videos) securely to cloud storage.
*   **Supabase Database & Storage**: Real-time structured data storage and media management via Supabase buckets.
*   **Double-Fallback Notification System**:
    *   Sends transaction emails (like Tracking IDs and Status Updates) using **Brevo's HTTP API** (port 443) to easily bypass hosting server SMTP port blocks.
    *   Automatically falls back to **Gmail SMTP** when run locally for testing.
*   **Dual-Language Translation**: Real-time translation supporting English, Kannada (ಕನ್ನಡ), Hindi (हिंदी), Tamil (தமிழ்), and Telugu (తెలుగు) using a persistent translation cache to prevent rate-limiting.
*   **Admin & Officer Dashboards**: Manage grievances, update statuses, view unassigned grievance locations on a live map, and group duplicate reports in identical geographical regions.
*   **AI Chatbot Assistant**: An interactive helper available on the user dashboard to answer questions and assist with system navigation.

---

## 🛠️ Tech Stack

*   **Backend Framework**: Python Flask
*   **Database**: Supabase PostgreSQL
*   **Cloud Storage**: Supabase Storage Buckets
*   **Email Deliverability**: Brevo Transactional API & Flask-Mail
*   **Aesthetics & Style**: Responsive Vanilla CSS (with glassmorphism and modern viewport clamping)
*   **Deployments**: Render (configured via blue-print specs)

---

## 💻 Local Setup & Installation

Follow these steps to run the application on your local machine:

### 1. Clone the Repository
```bash
git clone https://github.com/ranganathtg/dbms-project.git
cd dbms-project
```

### 2. Create a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
copy .env.example .env     # Windows
cp .env.example .env       # macOS/Linux
```
Fill in the credentials inside `.env`:
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Flask Secret Key
SECRET_KEY=your-random-secret-key-string

# App Base URL
APP_URL=http://localhost:5000

# Email Configuration (Gmail SMTP for local testing)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# Optional: Brevo API Key (Bypasses SMTP port blocks in production)
BREVO_API_KEY=your-brevo-api-key
```

### 5. Run the Application
```bash
python app.py
```
The server will start at: **`http://localhost:5000`**

---

## ☁️ Deployment on Render

This project includes a `render.yaml` configuration file. This allows you to deploy the project as a **Free Web Service** automatically using Render Blueprints.

### Deployment Steps:
1. Push all code updates to your GitHub repository.
2. Open your [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Blueprint**.
3. Connect your GitHub repository.
4. Render will read `render.yaml` and request the following environment variables:
   *   `SUPABASE_URL`
   *   `SUPABASE_KEY`
   *   `MAIL_USERNAME` (Your verified Brevo sender email)
   *   `MAIL_PASSWORD` (Your Gmail SMTP app password)
   *   `SECRET_KEY` (Any secure random text)
   *   `APP_URL` (Your live Render app link, e.g., `https://grievance-system-g9om.onrender.com`)
   *   `BREVO_API_KEY` (Your Brevo API Key for free tier email routing)
5. Click **Deploy Blueprint**. Your app will build, deploy, and go **Live** automatically!

---

## 👥 Authors & Contributors
*   **Ranganath TG**
*   **Ranjita Naik**

Project developed as part of the Database Management Systems (DBMS) laboratory curriculum.
