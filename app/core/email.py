"""
Email service module for sending OTP and verification emails.
Supports multiple email providers with fallback options.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import httpx
from app.core.logging_config import app_logger

# Email provider configuration
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp")  # Options: smtp, resend, sendgrid, console
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
# EMAIL_FROM defaults to SMTP_USER if not set (for Gmail, use the same email)
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER or "noreply@yourdomain.com")


async def send_email_async(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """
    Send email asynchronously using the configured provider.
    Returns True if successful, False otherwise.
    """
    try:
        if EMAIL_PROVIDER == "resend":
            return await _send_via_resend(recipient, subject, body, html_body)
        elif EMAIL_PROVIDER == "sendgrid":
            return await _send_via_sendgrid(recipient, subject, body, html_body)
        elif EMAIL_PROVIDER == "smtp":
            return await _send_via_smtp(recipient, subject, body, html_body)
        else:
            # Fallback to console logging
            _send_via_console(recipient, subject, body)
            return True
    except Exception as e:
        app_logger.error(f"Failed to send email to {recipient}: {str(e)}")
        # Fallback to console if email service fails
        _send_via_console(recipient, subject, body)
        return False


def send_email(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """
    Synchronous wrapper for send_email_async.
    Use this from sync code. Fire-and-forget in async contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a task (fire-and-forget)
        if loop and loop.is_running():
            asyncio.create_task(send_email_async(recipient, subject, body, html_body))
            return True
    except RuntimeError:
        # No event loop running, create a new one
        pass
    
    # If no event loop, run synchronously
    try:
        return asyncio.run(send_email_async(recipient, subject, body, html_body))
    except Exception as e:
        app_logger.error(f"Failed to send email: {str(e)}")
        _send_via_console(recipient, subject, body)
        return False


async def _send_via_resend(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """Send email via Resend API (recommended - 100 emails/day free)"""
    if not RESEND_API_KEY:
        app_logger.warning("RESEND_API_KEY not set, falling back to console")
        _send_via_console(recipient, subject, body)
        return False
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": EMAIL_FROM,
                "to": [recipient],
                "subject": subject,
                "text": body,
                "html": html_body or body.replace("\n", "<br>"),
            },
            timeout=10.0,
        )
        
        if response.status_code == 200:
            app_logger.info(f"Email sent via Resend to {recipient}")
            return True
        else:
            error_text = response.text
            app_logger.error(f"Resend API error: {response.status_code} - {error_text}")
            
            # Log to Supabase for monitoring
            try:
                import sys
                from pathlib import Path
                ROOT = Path(__file__).resolve().parents[2]
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from log_to_supabase import log_event
                log_event("error", "Resend email send failed", {
                    "recipient": recipient,
                    "status_code": response.status_code,
                    "error": error_text[:200],  # First 200 chars
                    "from": EMAIL_FROM
                })
            except Exception:
                pass
            
            # If 403 error, provide helpful message
            if response.status_code == 403:
                app_logger.warning(
                    "Resend 403: Free tier only allows sending to your verified email. "
                    "Verify a domain at resend.com/domains to send to any email."
                )
            
            # Fallback to console
            _send_via_console(recipient, subject, body)
            return False


async def _send_via_sendgrid(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """Send email via SendGrid API (100 emails/day free)"""
    if not SENDGRID_API_KEY:
        app_logger.warning("SENDGRID_API_KEY not set, falling back to console")
        _send_via_console(recipient, subject, body)
        return False
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": recipient}]}],
                "from": {"email": EMAIL_FROM},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": body},
                    {"type": "text/html", "value": html_body or body.replace("\n", "<br>")},
                ],
            },
            timeout=10.0,
        )
        
        if response.status_code == 202:
            app_logger.info(f"Email sent via SendGrid to {recipient}")
            return True
        else:
            app_logger.error(f"SendGrid API error: {response.status_code} - {response.text}")
            return False


async def _send_via_smtp(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """Send email via SMTP (Gmail, etc.) - async version with timeout"""
    if not SMTP_USER or not SMTP_PASSWORD:
        app_logger.warning("SMTP credentials not set, falling back to console")
        _send_via_console(recipient, subject, body)
        return False
    
    try:
        # Run SMTP in thread pool with timeout to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        # Use asyncio.wait_for to add timeout
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _send_via_smtp_sync, recipient, subject, body, html_body),
            timeout=15.0  # 15 second timeout
        )
        if result:
            app_logger.info(f"Email sent via SMTP ({SMTP_HOST}) to {recipient}")
        return result
    except asyncio.TimeoutError:
        error_msg = "SMTP connection timeout (15s)"
        app_logger.error(f"SMTP error: {error_msg}")
        _log_email_error(recipient, error_msg)
        _send_via_console(recipient, subject, body)
        return False
    except Exception as e:
        error_msg = str(e)
        app_logger.error(f"SMTP error: {error_msg}")
        _log_email_error(recipient, error_msg)
        _send_via_console(recipient, subject, body)
        return False


def _send_via_smtp_sync(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """Synchronous SMTP send (used in thread pool)"""
    try:
        msg = MIMEMultipart("alternative")
        from_email = EMAIL_FROM if EMAIL_FROM and EMAIL_FROM != SMTP_USER else SMTP_USER
        msg["From"] = from_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        
        # Use shorter timeout to fail fast
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False


def _log_email_error(recipient: str, error_msg: str) -> None:
    """Log email errors to Supabase for monitoring"""
    try:
        import sys
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[2]
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from log_to_supabase import log_event
        log_event("error", "Email send failed", {
            "recipient": recipient,
            "error": error_msg,
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT
        })
    except Exception:
        pass  # Silently fail if logging fails


def _send_via_console(recipient: str, subject: str, body: str) -> None:
    """Fallback: Print email to console (for development)"""
    print(f"\n{'='*60}")
    print(f"[EMAIL] To: {recipient}")
    print(f"[EMAIL] Subject: {subject}")
    print(f"{'='*60}")
    print(body)
    print(f"{'='*60}\n")

