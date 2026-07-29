"""
Email utility — sends transactional emails via SMTP.

Dev mode  : logs the link to console (no SMTP needed).
Prod mode : uses SMTP credentials from settings.

Configure in backend/.env:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@gmail.com
    SMTP_PASSWORD=your_app_password
    SMTP_FROM=you@gmail.com
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_reset_email(to_email: str, reset_link: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset Your TriAnSec Password"
    msg["From"] = f"TriAnSec <{settings.SMTP_FROM}>"
    msg["To"] = to_email

    text = f"""Password Reset - TriAnSec

Hi,

You requested a password reset for your TriAnSec account.

Reset your password here (link expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):
{reset_link}

If you did not request this, you can safely ignore this email.

- TriAnSec Security Team
"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f4f4f4; font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <tr>
          <td style="background:#1a1a2e; padding:28px 32px; text-align:center;">
            <span style="color:#00e676; font-size:22px; font-weight:bold; letter-spacing:1px;">&#128274; TriAnSec</span>
          </td>
        </tr>
        
        <!-- Body -->
        <tr>
          <td style="padding:36px 32px; color:#333333;">
            <h2 style="margin:0 0 16px; font-size:22px; color:#111111;">Reset Your Password</h2>
            <p style="margin:0 0 12px; font-size:15px; line-height:1.6; color:#555555;">
              You requested a password reset for your <strong>TriAnSec</strong> account.
            </p>
            <p style="margin:0 0 28px; font-size:15px; line-height:1.6; color:#555555;">
              Click the button below to set a new password. This link expires in
              <strong>{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes</strong>.
            </p>
            
            <!-- Button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
              <tr>
                <td style="background:#00c853; border-radius:6px;">
                  <a href="{reset_link}" target="_blank"
                     style="display:inline-block; padding:14px 36px; color:#ffffff;
                            font-size:16px; font-weight:bold; text-decoration:none;
                            border-radius:6px;">
                    Reset Password
                  </a>
                </td>
              </tr>
            </table>
            
            <!-- Fallback link -->
            <p style="margin:0 0 8px; font-size:13px; color:#888888;">Or copy this link into your browser:</p>
            <p style="margin:0; font-size:12px; word-break:break-all;">
              <a href="{reset_link}" style="color:#1565c0;">{reset_link}</a>
            </p>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td style="background:#f9f9f9; padding:20px 32px; border-top:1px solid #eeeeee; text-align:center;">
            <p style="margin:0; font-size:12px; color:#aaaaaa;">
              If you did not request this, you can safely ignore this email.<br>
              This link will expire automatically.
            </p>
          </td>
        </tr>
        
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _build_email_change_email(to_email: str, verify_link: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Confirm Your New Email — TriAnSec"
    msg["From"] = f"TriAnSec <{settings.SMTP_FROM}>"
    msg["To"] = to_email

    text = f"""Confirm Email Change - TriAnSec

Hi,

You requested an email address change for your TriAnSec account.

Confirm your new email here (link expires in 30 minutes):
{verify_link}

If you did not request this, please contact support immediately.

- TriAnSec Security Team
"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f4f4f4; font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <tr>
          <td style="background:#1a1a2e; padding:28px 32px; text-align:center;">
            <span style="color:#64b5f6; font-size:22px; font-weight:bold; letter-spacing:1px;">&#128231; TriAnSec</span>
          </td>
        </tr>
        
        <!-- Body -->
        <tr>
          <td style="padding:36px 32px; color:#333333;">
            <h2 style="margin:0 0 16px; font-size:22px; color:#111111;">Confirm Email Change</h2>
            <p style="margin:0 0 12px; font-size:15px; line-height:1.6; color:#555555;">
              You requested an email address change for your <strong>TriAnSec</strong> account.
            </p>
            <p style="margin:0 0 28px; font-size:15px; line-height:1.6; color:#555555;">
              Click the button below to confirm your new email address.
              This link expires in <strong>30 minutes</strong>.
            </p>
            
            <!-- Button -->
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
              <tr>
                <td style="background:#1565c0; border-radius:6px;">
                  <a href="{verify_link}" target="_blank"
                     style="display:inline-block; padding:14px 36px; color:#ffffff;
                            font-size:16px; font-weight:bold; text-decoration:none;
                            border-radius:6px;">
                    Confirm Email
                  </a>
                </td>
              </tr>
            </table>
            
            <!-- Fallback link -->
            <p style="margin:0 0 8px; font-size:13px; color:#888888;">Or copy this link into your browser:</p>
            <p style="margin:0; font-size:12px; word-break:break-all;">
              <a href="{verify_link}" style="color:#1565c0;">{verify_link}</a>
            </p>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td style="background:#f9f9f9; padding:20px 32px; border-top:1px solid #eeeeee; text-align:center;">
            <p style="margin:0; font-size:12px; color:#aaaaaa;">
              If you did not request this, please ignore this email and contact support.<br>
              This link will expire automatically.
            </p>
          </td>
        </tr>
        
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _smtp_send(msg: MIMEMultipart, to_email: str) -> bool:
    """Send email via SMTP. Returns True on success, False on failure."""
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send a password reset email.
    - SMTP configured : sends real email (works in both dev and prod).
    - No SMTP         : logs the link to console only.
    """
    logger.info(f"[RESET LINK] → {reset_link}")

    if not settings.SMTP_HOST:
        # No SMTP configured — just log (pure dev/local mode)
        logger.info(
            f"[NO SMTP] Password reset for {to_email}.\n"
            f"          Copy this link: {reset_link}"
        )
        return True

    msg = _build_reset_email(to_email, reset_link)
    return _smtp_send(msg, to_email)


def send_email_change_email(to_email: str, verify_link: str) -> bool:
    """
    Send an email-change confirmation email.
    - SMTP configured : sends real email (works in both dev and prod).
    - No SMTP         : logs the link to console only.
    """
    logger.info(f"[EMAIL CHANGE LINK] → {verify_link}")

    if not settings.SMTP_HOST:
        logger.info(
            f"[NO SMTP] Email change for {to_email}.\n"
            f"          Copy this link: {verify_link}"
        )
        return True

    msg = _build_email_change_email(to_email, verify_link)
    return _smtp_send(msg, to_email)
