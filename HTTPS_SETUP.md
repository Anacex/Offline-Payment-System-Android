# HTTPS Setup Guide

## Why HTTP vs HTTPS?

### Development (Current Setup)
- **Using**: HTTP (`http://127.0.0.1:9000`)
- **Why**: Testing locally on localhost doesn't require SSL certificates
- **Security**: Safe for local development as traffic doesn't leave your machine

### Production (Required)
- **Must Use**: HTTPS (`https://api.offlinepay.pk`)
- **Why**: 
  - Encrypts all data in transit
  - Prevents man-in-the-middle attacks
  - Required for mobile apps to trust the API
  - Required by payment systems and banks
  - SEO and browser requirements

---

## Setting Up HTTPS for Production

### Option 1: Using Nginx as Reverse Proxy (Recommended)

This is already documented in `PRODUCTION_DEPLOYMENT.md`. Key steps:

1. **Install Certbot** (for free SSL certificates from Let's Encrypt):
   ```bash
   sudo apt install certbot python3-certbot-nginx
   ```

2. **Get SSL Certificate**:
   ```bash
   sudo certbot --nginx -d api.offlinepay.pk
   ```

3. **Nginx Configuration** (auto-configured by Certbot):
   ```nginx
   server {
       listen 443 ssl http2;
       server_name api.offlinepay.pk;
       
       ssl_certificate /etc/letsencrypt/live/api.offlinepay.pk/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/api.offlinepay.pk/privkey.pem;
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

4. **Auto-renewal** (Certbot sets this up automatically):
   ```bash
   sudo certbot renew --dry-run
   ```

---

### Option 2: Using Uvicorn with SSL (For Testing)

For local HTTPS testing, you can generate self-signed certificates:

#### Generate Self-Signed Certificate:

```bash
# Windows (PowerShell)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Linux/Mac
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

#### Run Uvicorn with SSL:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 443 --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem
```

**Note**: Self-signed certificates will show browser warnings. Only use for testing!

---

### Option 3: Using Cloudflare (Easiest for Small Projects)

1. **Sign up** at cloudflare.com
2. **Add your domain** (offlinepay.pk)
3. **Update nameservers** to Cloudflare's
4. **Enable "Full (Strict)" SSL** in Cloudflare dashboard
5. **Cloudflare handles SSL** automatically (free!)

Your API will be accessible at `https://api.offlinepay.pk`

---

## Mobile App Configuration

### For HTTP (Development Only)

**Android** (`AndroidManifest.xml`):
```xml
<application
    android:usesCleartextTraffic="true">
    <!-- Only for development! -->
</application>
```

**iOS** (`Info.plist`):
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
    <!-- Only for development! -->
</dict>
```

### For HTTPS (Production - Required)

Remove the above configurations. Apps will automatically trust valid HTTPS certificates.

**API Base URL in App**:
```kotlin
// Development
const val BASE_URL = "http://10.0.2.2:9000"  // Android emulator

// Production
const val BASE_URL = "https://api.offlinepay.pk"
```

---

## Security Considerations

### Why HTTPS is Critical for Offline Payment System:

1. **Cryptographic Keys**: Public/private keys transmitted must be encrypted
2. **Authentication Tokens**: JWT tokens need protection in transit
3. **Transaction Data**: Payment information must be encrypted
4. **User Credentials**: Passwords and OTPs need secure transmission
5. **Compliance**: Banking regulations require HTTPS
6. **Trust**: Users won't trust a payment app without HTTPS

### Additional Security Layers:

Even with HTTPS, our system has:
- ✅ **End-to-end encryption** (RSA for offline transactions)
- ✅ **Digital signatures** (transaction verification)
- ✅ **Nonce-based replay protection**
- ✅ **Rate limiting**
- ✅ **Security headers** (HSTS, CSP, etc.)
- ✅ **MFA** (Multi-factor authentication)

---

## Testing HTTPS Locally

### Using ngrok (Quick Testing):

```bash
# Install ngrok
# Download from https://ngrok.com/download

# Run your API
python -m uvicorn app.main:app --host 127.0.0.1 --port 9000

# In another terminal, expose via HTTPS
ngrok http 9000
```

You'll get a URL like: `https://abc123.ngrok.io`

This gives you a real HTTPS endpoint for testing!

---

## Production Checklist

Before deploying with HTTPS:

- [ ] Domain name registered (e.g., offlinepay.pk)
- [ ] DNS configured to point to your server
- [ ] SSL certificate obtained (Let's Encrypt or commercial)
- [ ] Nginx configured as reverse proxy
- [ ] Firewall allows ports 80 and 443
- [ ] Auto-renewal configured for SSL certificate
- [ ] HSTS header enabled (already in our middleware)
- [ ] Redirect HTTP to HTTPS (in Nginx config)
- [ ] Test with SSL Labs (https://www.ssllabs.com/ssltest/)
- [ ] Update mobile app to use HTTPS URL
- [ ] Remove `usesCleartextTraffic` from Android manifest

---

## Current Status

✅ **Development**: Running on HTTP (http://127.0.0.1:9000)  
✅ **All security features**: Implemented and tested  
✅ **Production-ready code**: Complete  
⏳ **HTTPS**: Ready to deploy (follow PRODUCTION_DEPLOYMENT.md)

---

## Quick Start for Production HTTPS

```bash
# 1. Deploy to server
scp -r backend-auth-pack user@your-server:/opt/offlinepay

# 2. Install dependencies
cd /opt/offlinepay
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Setup database
python -m app.db_init

# 4. Get SSL certificate
sudo certbot --nginx -d api.offlinepay.pk

# 5. Start service
sudo systemctl start offlinepay

# 6. Verify HTTPS
curl https://api.offlinepay.pk/health
```

Your API is now running securely with HTTPS! 🔒
