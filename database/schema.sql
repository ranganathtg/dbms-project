-- 🔹 USER TABLE
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255),
    role ENUM('user','admin') DEFAULT 'user'
);

-- 🔹 GRIEVANCES TABLE
CREATE TABLE grievances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    title VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    priority VARCHAR(50),
    file_path VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    status ENUM('Pending', 'In Progress', 'Resolved') DEFAULT 'Pending',
    remarks TEXT,
    duplicate_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 🔹 CHATBOT LOGS
CREATE TABLE IF NOT EXISTS chat_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    user_message TEXT,
    bot_response TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 🔹 FEEDBACK & RATINGS
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 🔹 COMPLAINT LOCATIONS (For Individual Merged Reports)
CREATE TABLE complaint_locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT,
    user_id INT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES grievances(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);