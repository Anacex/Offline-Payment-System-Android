-- Offline Payment System - Database Setup Script
-- Run this script to create the database and user

-- Create database
CREATE DATABASE offlinepay;

-- Connect to the database
\c offlinepay;

-- Create extensions for better performance and security
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Grant privileges (adjust username as needed)
-- GRANT ALL PRIVILEGES ON DATABASE offlinepay TO postgres;

-- Create indexes for better performance (will be created by SQLAlchemy, but listed here for reference)
-- These will be automatically created by the models

-- Display success message
SELECT 'Database setup complete!' as status;
