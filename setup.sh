#!/bin/bash

# Offline Payment System - Quick Setup Script
# This script sets up the development environment

echo "🚀 Offline Payment System - Setup Script"
echo "=========================================="

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ required. Current version: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Check PostgreSQL
echo ""
echo "📋 Checking PostgreSQL..."
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL not found. Please install PostgreSQL 14+"
    echo "   Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "   macOS: brew install postgresql"
    exit 1
fi
echo "✅ PostgreSQL found"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Create .env file
echo ""
echo "⚙️  Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env file created from template"
    echo "⚠️  Please update .env with your database credentials"
else
    echo "ℹ️  .env file already exists"
fi

# Create database
echo ""
echo "🗄️  Setting up database..."
read -p "Create database 'offlinepay'? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo -u postgres psql -c "CREATE DATABASE offlinepay;" 2>/dev/null || echo "Database may already exist"
    echo "✅ Database setup complete"
fi

# Initialize database tables
echo ""
echo "📊 Initializing database tables..."
python -m app.db_init
echo "✅ Database tables created"

# Generate secret key
echo ""
echo "🔐 Generating secure SECRET_KEY..."
secret_key=$(openssl rand -hex 32)
echo "Add this to your .env file:"
echo "SECRET_KEY=$secret_key"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Update .env with your configuration"
echo "2. Update SECRET_KEY in .env with: $secret_key"
echo "3. Run the server: uvicorn app.main:app --reload --port 8000"
echo "4. Access API docs: http://localhost:8000/docs"
echo ""
echo "📚 Documentation:"
echo "- README.md - Getting started guide"
echo "- API_DOCUMENTATION.md - Complete API reference"
echo "- THREAT_MODEL.md - Security analysis"
echo "- MOBILE_APP_GUIDE.md - Mobile app implementation"
echo ""
echo "Happy coding! 🎉"
