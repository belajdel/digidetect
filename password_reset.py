"""
Password Reset Module
Handles password reset workflow with email verification
"""

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for, render_template_string
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models import db, User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PasswordResetManager:
    def __init__(self, app=None):
        self.app = app
        self.mail = None
        self.serializer = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the password reset manager with Flask app"""
        self.app = app
        
        # Configure Flask-Mail
        app.config.setdefault('MAIL_SERVER', 'smtp.gmail.com')
        app.config.setdefault('MAIL_PORT', 587)
        app.config.setdefault('MAIL_USE_TLS', True)
        app.config.setdefault('MAIL_USE_SSL', False)
        app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME'))
        app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD'))
        app.config.setdefault('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME'))
        
        # Token expiration time (1 hour)
        app.config.setdefault('PASSWORD_RESET_TOKEN_EXPIRATION', 3600)
        
        self.mail = Mail(app)
        self.serializer = URLSafeTimedSerializer(app.secret_key)
    
    def generate_reset_token(self, user_id):
        """Generate a secure password reset token"""
        try:
            token = self.serializer.dumps({'user_id': user_id}, salt='password-reset')
            logger.info(f"Generated reset token for user ID: {user_id}")
            return token
        except Exception as e:
            logger.error(f"Error generating reset token: {e}")
            return None
    
    def verify_reset_token(self, token, max_age=3600):
        """Verify and decode a password reset token"""
        try:
            data = self.serializer.loads(
                token, 
                salt='password-reset', 
                max_age=max_age
            )
            user_id = data.get('user_id')
            logger.info(f"Token verified for user ID: {user_id}")
            return user_id
        except SignatureExpired:
            logger.warning("Password reset token has expired")
            return None
        except BadSignature:
            logger.warning("Invalid password reset token")
            return None
        except Exception as e:
            logger.error(f"Error verifying reset token: {e}")
            return None
    
    def send_reset_email(self, user_email, reset_token):
        """Send password reset email to user"""
        try:
            # Check if mail is configured
            if not self.app.config.get('MAIL_USERNAME'):
                # Fallback to console logging for development
                reset_url = url_for('reset_password', token=reset_token, _external=True)
                logger.info(f"Password reset email would be sent to: {user_email}")
                logger.info(f"Reset URL: {reset_url}")
                return True, "Email configuration not found. Reset link logged to console."
            
            reset_url = url_for('reset_password', token=reset_token, _external=True)
            
            # Create email message
            msg = Message(
                subject='Password Reset Request - Postal Code Detector',
                sender=self.app.config['MAIL_DEFAULT_SENDER'],
                recipients=[user_email]
            )
            
            # Email template
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Password Reset</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #007bff; color: white; padding: 20px; text-align: center; }}
                    .content {{ background: #f8f9fa; padding: 30px; }}
                    .button {{ background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                    .footer {{ background: #6c757d; color: white; padding: 10px; text-align: center; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <h2>Hello!</h2>
                        <p>You recently requested to reset your password for your Postal Code Detector account.</p>
                        <p>Click the button below to reset your password:</p>
                        <p style="text-align: center;">
                            <a href="{reset_url}" class="button">Reset Password</a>
                        </p>
                        <p><strong>This link will expire in 1 hour.</strong></p>
                        <p>If you did not request this password reset, please ignore this email or contact support if you have concerns.</p>
                        <p>For security reasons, please do not share this link with anyone.</p>
                        <hr>
                        <p><small>If the button doesn't work, copy and paste this URL into your browser:</small></p>
                        <p><small>{reset_url}</small></p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2025 Postal Code Detector. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
            Password Reset Request
            
            Hello!
            
            You recently requested to reset your password for your Postal Code Detector account.
            
            Click the link below to reset your password:
            {reset_url}
            
            This link will expire in 1 hour.
            
            If you did not request this password reset, please ignore this email.
            
            For security reasons, please do not share this link with anyone.
            """
            
            msg.body = text_body
            msg.html = html_body
            
            # Send email
            self.mail.send(msg)
            logger.info(f"Password reset email sent successfully to: {user_email}")
            return True, "Password reset email sent successfully."
            
        except Exception as e:
            logger.error(f"Error sending reset email to {user_email}: {e}")
            return False, f"Failed to send email: {str(e)}"
    
    def update_user_password(self, user_id, new_password):
        """Update user password in database"""
        try:
            user = User.query.get(user_id)
            if not user:
                logger.warning(f"User not found for password update: {user_id}")
                return False, "User not found."
            
            # Update password
            user.set_password(new_password)
            user.password_reset_at = datetime.now()
            
            db.session.commit()
            logger.info(f"Password updated successfully for user: {user.username}")
            return True, "Password updated successfully."
            
        except Exception as e:
            logger.error(f"Error updating password for user {user_id}: {e}")
            db.session.rollback()
            return False, f"Database error: {str(e)}"

# Global instance
password_reset_manager = PasswordResetManager() 