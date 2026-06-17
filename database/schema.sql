-- 🔹 CREATE CUSTOM FUNCTIONS FOR MYSQL COMPATIBILITY
CREATE OR REPLACE FUNCTION dayname(ts timestamp) RETURNS text AS $$
BEGIN
    RETURN to_char(ts, 'FMDay');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION date(ts timestamp) RETURNS date AS $$
BEGIN
    RETURN ts::date;
END;
$$ LANGUAGE plpgsql;

-- 🔹 USER TABLE
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user'
);

-- 🔹 GRIEVANCES TABLE
CREATE TABLE IF NOT EXISTS grievances (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    priority VARCHAR(50),
    file_path VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    status VARCHAR(50) DEFAULT 'Pending',
    remarks TEXT,
    duplicate_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL DEFAULT NULL
);

-- 🔹 CHATBOT LOGS
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    user_message TEXT,
    bot_response TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🔹 FEEDBACK & RATINGS
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🔹 COMPLAINT LOCATIONS (For Individual Merged Reports)
CREATE TABLE IF NOT EXISTS complaint_locations (
    id SERIAL PRIMARY KEY,
    complaint_id INT REFERENCES grievances(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🔹 DISABLE RLS FOR SUPABASE (Ensures API keys can access tables without complex policies)
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE grievances DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE feedback DISABLE ROW LEVEL SECURITY;
ALTER TABLE complaint_locations DISABLE ROW LEVEL SECURITY;