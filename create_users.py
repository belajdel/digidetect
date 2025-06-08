#!/usr/bin/env python3
"""
Script to create default users for the postal code detection app
"""

from app_working import app
from models import db, User, SystemStats
from datetime import datetime

def create_default_users():
    """Create default admin and user accounts"""
    
    print("🚀 Creating default users...")
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user already exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            # Create admin user
            admin_user = User(
                username='admin',
                role='admin',
                is_approved=True,
                full_name='Administrator',
                email='admin@postal-detector.com',
                department='Administration',
                created_at=datetime.now()
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            print("✅ Admin user created: admin/admin123")
        else:
            print("✅ Admin user already exists")
        
        # Check if test user already exists
        test_user = User.query.filter_by(username='user').first()
        if not test_user:
            # Create test user
            test_user = User(
                username='user',
                role='user',
                is_approved=True,
                full_name='Test User',
                email='user@postal-detector.com',
                department='Testing',
                created_at=datetime.now()
            )
            test_user.set_password('user123')
            db.session.add(test_user)
            print("✅ Test user created: user/user123")
        else:
            print("✅ Test user already exists")
        
        # Create system stats if not exists
        stats = SystemStats.query.first()
        if not stats:
            system_stats = SystemStats(
                start_time=datetime.now(),
                total_detections=0,
                unique_codes_count=0,
                last_updated=datetime.now()
            )
            db.session.add(system_stats)
            print("✅ System stats initialized")
        else:
            print("✅ System stats already exist")
        
        # Commit all changes
        db.session.commit()
        
        print("\n📋 ACCOUNTS READY:")
        print("   👨‍💼 Admin: admin / admin123")
        print("   👤 User:  user / user123")
        print("\n🌐 You can now access: http://127.0.0.1:5000")

if __name__ == "__main__":
    create_default_users() 