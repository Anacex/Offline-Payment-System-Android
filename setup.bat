@echo off
REM Offline Payment System - Quick Setup Script for Windows
REM This script sets up the development environment

echo ========================================
echo Offline Payment System - Setup Script
echo ========================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM Check PostgreSQL
echo Checking PostgreSQL...
where psql >nul 2>&1
if errorlevel 1 (
    echo WARNING: PostgreSQL not found in PATH
    echo Please install PostgreSQL 14+ from: https://www.postgresql.org/download/windows/
    echo.
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

REM Create .env file
echo Setting up environment configuration...
if not exist .env (
    copy .env.example .env
    echo .env file created from template
    echo WARNING: Please update .env with your database credentials
) else (
    echo .env file already exists
)
echo.

REM Database setup instructions
echo ========================================
echo Database Setup Instructions
echo ========================================
echo.
echo 1. Make sure PostgreSQL is running
echo 2. Open pgAdmin or psql and run:
echo    CREATE DATABASE offlinepay;
echo.
echo 3. Update DATABASE_URL in .env file with your credentials
echo    Example: postgresql+psycopg2://postgres:yourpassword@localhost:5432/offlinepay
echo.
set /p continue="Press Enter after creating the database..."
echo.

REM Initialize database tables
echo Initializing database tables...
python -m app.db_init
if errorlevel 1 (
    echo ERROR: Failed to initialize database
    echo Please check your DATABASE_URL in .env file
    pause
    exit /b 1
)
echo Database tables created successfully
echo.

REM Generate secret key
echo ========================================
echo Security Configuration
echo ========================================
echo.
echo IMPORTANT: Update your SECRET_KEY in .env file
echo Generate a secure key using:
echo   python -c "import secrets; print(secrets.token_hex(32))"
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Update .env with your configuration
echo 2. Generate and update SECRET_KEY in .env
echo 3. Run the server:
echo    venv\Scripts\activate
echo    uvicorn app.main:app --reload --port 8000
echo 4. Access API docs: http://localhost:8000/docs
echo.
echo Documentation:
echo - README.md - Getting started guide
echo - API_DOCUMENTATION.md - Complete API reference
echo - THREAT_MODEL.md - Security analysis
echo - MOBILE_APP_GUIDE.md - Mobile app implementation
echo.
echo Happy coding!
echo.
pause
