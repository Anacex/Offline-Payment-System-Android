# Production Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Offline Payment System to a production environment with enterprise-grade security and reliability.

---

## Pre-Deployment Checklist

### Security
- [ ] Generate new `SECRET_KEY` (use `openssl rand -hex 32`)
- [ ] Set `DEBUG=false` in production
- [ ] Configure proper CORS origins (remove wildcards)
- [ ] Enable HTTPS/TLS with valid SSL certificates
- [ ] Set up firewall rules
- [ ] Configure rate limiting
- [ ] Enable security headers
- [ ] Set up intrusion detection
- [ ] Configure backup encryption

### Database
- [ ] Use strong PostgreSQL password
- [ ] Enable SSL for database connections
- [ ] Set up automated backups
- [ ] Configure replication (optional)
- [ ] Set up monitoring
- [ ] Optimize indexes
- [ ] Configure connection pooling

### Infrastructure
- [ ] Set up load balancer
- [ ] Configure CDN (if needed)
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure logging aggregation
- [ ] Set up alerting
- [ ] Configure auto-scaling
- [ ] Set up disaster recovery

---

## Deployment Steps

### 1. Server Setup

#### Requirements
- **OS**: Ubuntu 22.04 LTS or Windows Server 2022
- **RAM**: Minimum 4GB (8GB recommended)
- **CPU**: 2+ cores
- **Storage**: 50GB+ SSD
- **Network**: Static IP, firewall configured

#### Install Dependencies (Ubuntu)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Nginx (reverse proxy)
sudo apt install nginx -y

# Install Certbot (SSL certificates)
sudo apt install certbot python3-certbot-nginx -y

# Install Redis (optional, for caching)
sudo apt install redis-server -y
```

---

### 2. Database Configuration

```bash
# Switch to postgres user
sudo -u postgres psql

# Create production database
CREATE DATABASE offlinepay_prod;

# Create dedicated user
CREATE USER offlinepay_user WITH ENCRYPTED PASSWORD 'STRONG_PASSWORD_HERE';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE offlinepay_prod TO offlinepay_user;

# Enable extensions
\c offlinepay_prod
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

# Exit
\q
```

#### Configure PostgreSQL for Production

Edit `/etc/postgresql/14/main/postgresql.conf`:

```conf
# Connection Settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB

# Security
ssl = on
ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key'
```

Edit `/etc/postgresql/14/main/pg_hba.conf`:

```conf
# Allow SSL connections only
hostssl offlinepay_prod offlinepay_user 0.0.0.0/0 md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

### 3. Application Deployment

#### Clone and Setup

```bash
# Create application directory
sudo mkdir -p /opt/offlinepay
cd /opt/offlinepay

# Clone repository (or upload files)
# git clone <your-repo-url> .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install production server
pip install gunicorn
```

#### Configure Environment

Create `/opt/offlinepay/.env`:

```bash
# Database
DATABASE_URL=postgresql+psycopg2://offlinepay_user:STRONG_PASSWORD@localhost:5432/offlinepay_prod

# Security - CRITICAL: Generate new key!
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ALGORITHM=HS256

# Token Expiration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# CORS - Restrict to your domain
CORS_ORIGINS=https://app.offlinepay.pk,https://www.offlinepay.pk

# Application
APP_NAME=Offline Payment System
DEBUG=false
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30

# Email (configure with your SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_ENABLED=true

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
```

#### Initialize Database

```bash
python -m app.db_init
```

---

### 4. Systemd Service Configuration

Create `/etc/systemd/system/offlinepay.service`:

```ini
[Unit]
Description=Offline Payment System API
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/offlinepay
Environment="PATH=/opt/offlinepay/venv/bin"
ExecStart=/opt/offlinepay/venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/offlinepay/access.log \
    --error-logfile /var/log/offlinepay/error.log \
    --log-level info
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGQUIT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create log directory:
```bash
sudo mkdir -p /var/log/offlinepay
sudo chown www-data:www-data /var/log/offlinepay
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable offlinepay
sudo systemctl start offlinepay
sudo systemctl status offlinepay
```

---

### 5. Nginx Configuration

Create `/etc/nginx/sites-available/offlinepay`:

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_status 429;

# Upstream
upstream offlinepay_backend {
    server 127.0.0.1:8000 fail_timeout=0;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.offlinepay.pk;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    server_name api.offlinepay.pk;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.offlinepay.pk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.offlinepay.pk/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;

    # Logging
    access_log /var/log/nginx/offlinepay_access.log;
    error_log /var/log/nginx/offlinepay_error.log;

    # Max body size (for file uploads)
    client_max_body_size 10M;

    # Rate limiting
    limit_req zone=api_limit burst=20 nodelay;

    # Proxy settings
    location / {
        proxy_pass http://offlinepay_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (no rate limit)
    location /health {
        limit_req off;
        proxy_pass http://offlinepay_backend;
        access_log off;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/offlinepay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### 6. SSL Certificate Setup

```bash
# Obtain SSL certificate
sudo certbot --nginx -d api.offlinepay.pk

# Auto-renewal (already configured by certbot)
sudo certbot renew --dry-run
```

---

### 7. Firewall Configuration

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow PostgreSQL (only from localhost)
# Don't expose PostgreSQL to internet

# Enable firewall
sudo ufw enable
sudo ufw status
```

---

### 8. Monitoring Setup

#### Install Prometheus (Optional)

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Configure prometheus.yml
# Add your application metrics endpoint

# Run Prometheus
./prometheus --config.file=prometheus.yml
```

#### Install Grafana (Optional)

```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

---

### 9. Backup Configuration

#### Automated Database Backups

Create `/opt/offlinepay/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/offlinepay"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="offlinepay_backup_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

# Backup database
PGPASSWORD=STRONG_PASSWORD pg_dump -U offlinepay_user -h localhost offlinepay_prod | gzip > $BACKUP_DIR/$FILENAME

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $FILENAME"
```

Add to crontab:
```bash
sudo crontab -e

# Add this line (daily backup at 2 AM)
0 2 * * * /opt/offlinepay/backup.sh
```

---

### 10. Security Hardening

#### Fail2Ban Configuration

```bash
sudo apt install fail2ban -y

# Create jail for API
sudo nano /etc/fail2ban/jail.local
```

Add:
```ini
[offlinepay-api]
enabled = true
port = 443
filter = offlinepay-api
logpath = /var/log/nginx/offlinepay_access.log
maxretry = 5
bantime = 3600
```

#### AppArmor/SELinux

Enable and configure AppArmor or SELinux for additional security.

---

## Post-Deployment

### 1. Verify Deployment

```bash
# Check service status
sudo systemctl status offlinepay

# Check logs
sudo journalctl -u offlinepay -f

# Test API
curl https://api.offlinepay.pk/health
```

### 2. Performance Testing

```bash
# Install Apache Bench
sudo apt install apache2-utils -y

# Load test
ab -n 1000 -c 10 https://api.offlinepay.pk/health
```

### 3. Security Audit

```bash
# SSL test
openssl s_client -connect api.offlinepay.pk:443

# Port scan
nmap -sV api.offlinepay.pk

# Vulnerability scan (use professional tools)
```

---

## Maintenance

### Daily
- Monitor logs for errors
- Check system resources
- Review security alerts

### Weekly
- Review backup integrity
- Check SSL certificate expiry
- Update dependencies (security patches)

### Monthly
- Full security audit
- Performance optimization
- Database maintenance (VACUUM, ANALYZE)

---

## Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u offlinepay -n 50

# Check permissions
ls -la /opt/offlinepay

# Test manually
cd /opt/offlinepay
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Database Connection Issues
```bash
# Test connection
psql -U offlinepay_user -h localhost -d offlinepay_prod

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### High Memory Usage
```bash
# Check processes
htop

# Restart service
sudo systemctl restart offlinepay
```

---

## Rollback Procedure

```bash
# Stop service
sudo systemctl stop offlinepay

# Restore database backup
gunzip < /backups/offlinepay/offlinepay_backup_YYYYMMDD.sql.gz | psql -U offlinepay_user -d offlinepay_prod

# Restore code (from git)
cd /opt/offlinepay
git checkout <previous-version>

# Restart service
sudo systemctl start offlinepay
```

---

## Support Contacts

- **Technical Support**: tech@offlinepay.pk
- **Security Issues**: security@offlinepay.pk
- **Emergency**: +92-XXX-XXXXXXX

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Next Review**: Quarterly
