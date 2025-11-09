@echo off
REM Database Initialization Script for Offline Payment System
REM This script creates the database and initializes tables

echo ========================================
echo Database Setup - Offline Payment System
echo ========================================
echo.

REM Set PostgreSQL password
set PGPASSWORD=postgres

echo Creating database 'offlinepay'...
psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS offlinepay;" 2>nul
psql -U postgres -h localhost -c "CREATE DATABASE offlinepay;"

if errorlevel 1 (
    echo ERROR: Failed to create database
    echo Please ensure PostgreSQL is running and credentials are correct
    pause
    exit /b 1
)

echo Database created successfully!
echo.

echo Installing PostgreSQL extensions...
psql -U postgres -h localhost -d offlinepay -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
psql -U postgres -h localhost -d offlinepay -c "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"

echo.
echo Initializing database tables...
python -m app.db_init

if errorlevel 1 (
    echo ERROR: Failed to initialize tables
    pause
    exit /b 1
)

echo.
echo ========================================
echo Database setup complete!
echo ========================================
echo.
echo Database: offlinepay
echo Host: localhost
echo Port: 5432
echo User: postgres
echo.
pause
