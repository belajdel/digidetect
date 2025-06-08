from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_approved = db.Column(db.Boolean, default=True)
    full_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_updated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    password_reset_at = db.Column(db.DateTime, nullable=True)  # Track password reset history
    
    # Relationships
    detections = db.relationship('Detection', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_approved': self.is_approved,
            'full_name': self.full_name,
            'email': self.email,
            'department': self.department,
            'phone': self.phone,
            'address': self.address,
            'bio': self.bio,
            'profile_updated_at': self.profile_updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.profile_updated_at else None,
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            'last_login': self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None,
            'password_reset_at': self.password_reset_at.strftime("%Y-%m-%d %H:%M:%S") if self.password_reset_at else None
        }

class Detection(db.Model):
    __tablename__ = 'detections'
    
    id = db.Column(db.Integer, primary_key=True)
    postal_code = db.Column(db.String(10), nullable=False)  # Augmenté pour codes non-tunisiens
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    confidence = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_valid = db.Column(db.Boolean, default=True)  # NOUVEAU: Marque si le code postal est valide
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.postal_code,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'confidence': self.confidence,
            'user_id': self.user_id,
            'is_valid': self.is_valid  # NOUVEAU: Inclure le statut de validité
        }

class SystemStats(db.Model):
    __tablename__ = 'system_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    total_detections = db.Column(db.Integer, default=0)
    unique_codes_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'start_time': self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            'total_detections': self.total_detections,
            'unique_codes_count': self.unique_codes_count,
            'last_updated': self.last_updated.strftime("%Y-%m-%d %H:%M:%S")
        } 