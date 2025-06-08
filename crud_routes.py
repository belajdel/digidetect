"""
CRUD Routes for Postal Code Detector Database
Provides comprehensive Create, Read, Update, Delete operations for all entities
"""

from flask import request, jsonify, session
from datetime import datetime
from functools import wraps
from models import db, User, Detection, SystemStats

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
        elif session.get('role') != 'admin':
            return jsonify({'status': 'error', 'message': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def register_crud_routes(app):
    """Register all CRUD routes with the Flask app"""
    
    # ====================== USER CRUD OPERATIONS ======================
    
    @app.route('/api/users', methods=['GET'])
    @admin_required
    def crud_get_all_users():
        """GET: Retrieve all users"""
        try:
            users = User.query.all()
            user_list = [user.to_dict() for user in users]
            return jsonify({
                'status': 'success',
                'data': user_list,
                'count': len(user_list)
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/users/<int:user_id>', methods=['GET'])
    @admin_required
    def crud_get_user_by_id(user_id):
        """GET: Retrieve specific user by ID"""
        try:
            user = User.query.get_or_404(user_id)
            return jsonify({
                'status': 'success',
                'data': user.to_dict()
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 404

    @app.route('/api/users', methods=['POST'])
    @admin_required
    def crud_create_user():
        """POST: Create new user"""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['username', 'password', 'role']
            for field in required_fields:
                if field not in data:
                    return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
            
            # Check if username already exists
            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user:
                return jsonify({'status': 'error', 'message': 'Username already exists'}), 400
            
            # Create new user
            new_user = User(
                username=data['username'],
                role=data['role'],
                is_approved=data.get('is_approved', True),
                full_name=data.get('full_name', ''),
                email=data.get('email', ''),
                department=data.get('department', ''),
                created_at=datetime.now()
            )
            new_user.set_password(data['password'])
            
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'User created successfully',
                'data': new_user.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    @admin_required
    def crud_update_user(user_id):
        """PUT: Update existing user"""
        try:
            user = User.query.get_or_404(user_id)
            data = request.get_json()
            
            # Update user fields
            if 'username' in data and data['username'] != user.username:
                # Check if new username already exists
                existing = User.query.filter_by(username=data['username']).first()
                if existing:
                    return jsonify({'status': 'error', 'message': 'Username already exists'}), 400
                user.username = data['username']
            
            if 'password' in data:
                user.set_password(data['password'])
            if 'role' in data:
                user.role = data['role']
            if 'is_approved' in data:
                user.is_approved = data['is_approved']
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'email' in data:
                user.email = data['email']
            if 'department' in data:
                user.department = data['department']
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'User updated successfully',
                'data': user.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    @admin_required
    def crud_delete_user(user_id):
        """DELETE: Remove user"""
        try:
            user = User.query.get_or_404(user_id)
            
            # Prevent deleting admin user
            if user.username == 'admin':
                return jsonify({'status': 'error', 'message': 'Cannot delete admin user'}), 400
            
            # Also delete user's detections
            Detection.query.filter_by(user_id=user_id).delete()
            
            db.session.delete(user)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'User deleted successfully'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ====================== DETECTION CRUD OPERATIONS ======================
    
    @app.route('/api/detections', methods=['GET'])
    @login_required
    def crud_get_all_detections():
        """GET: Retrieve all detections with pagination"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 50, type=int)
            
            detections = Detection.query.order_by(Detection.timestamp.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            detection_list = [detection.to_dict() for detection in detections.items]
            
            return jsonify({
                'status': 'success',
                'data': detection_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': detections.total,
                    'pages': detections.pages,
                    'has_next': detections.has_next,
                    'has_prev': detections.has_prev
                }
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/detections/<int:detection_id>', methods=['GET'])
    @login_required
    def crud_get_detection_by_id(detection_id):
        """GET: Retrieve specific detection by ID"""
        try:
            detection = Detection.query.get_or_404(detection_id)
            return jsonify({
                'status': 'success',
                'data': detection.to_dict()
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 404

    @app.route('/api/detections', methods=['POST'])
    @admin_required
    def crud_create_detection():
        """POST: Create new detection manually"""
        try:
            data = request.get_json()
            
            # Validate required fields
            if 'postal_code' not in data:
                return jsonify({'status': 'error', 'message': 'Missing required field: postal_code'}), 400
            
            # Create new detection
            new_detection = Detection(
                postal_code=data['postal_code'],
                timestamp=datetime.now() if 'timestamp' not in data else datetime.fromisoformat(data['timestamp']),
                confidence=data.get('confidence', 65),
                user_id=data.get('user_id', session.get('user_id'))
            )
            
            db.session.add(new_detection)
            
            # Update system stats
            stats = SystemStats.query.first()
            if stats:
                stats.total_detections += 1
                stats.last_updated = datetime.now()
                unique_count = db.session.query(Detection.postal_code).distinct().count()
                stats.unique_codes_count = unique_count + 1
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Detection created successfully',
                'data': new_detection.to_dict()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/detections/<int:detection_id>', methods=['PUT'])
    @admin_required
    def crud_update_detection(detection_id):
        """PUT: Update existing detection"""
        try:
            detection = Detection.query.get_or_404(detection_id)
            data = request.get_json()
            
            # Update detection fields
            if 'postal_code' in data:
                detection.postal_code = data['postal_code']
            if 'confidence' in data:
                detection.confidence = data['confidence']
            if 'timestamp' in data:
                detection.timestamp = datetime.fromisoformat(data['timestamp'])
            if 'user_id' in data:
                detection.user_id = data['user_id']
            
            db.session.commit()
            
            # Update system stats
            stats = SystemStats.query.first()
            if stats:
                unique_count = db.session.query(Detection.postal_code).distinct().count()
                stats.unique_codes_count = unique_count
                stats.last_updated = datetime.now()
                db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Detection updated successfully',
                'data': detection.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/detections/<int:detection_id>', methods=['DELETE'])
    @admin_required
    def crud_delete_detection(detection_id):
        """DELETE: Remove detection"""
        try:
            detection = Detection.query.get_or_404(detection_id)
            
            db.session.delete(detection)
            
            # Update system stats
            stats = SystemStats.query.first()
            if stats:
                stats.total_detections = max(0, stats.total_detections - 1)
                unique_count = db.session.query(Detection.postal_code).distinct().count()
                stats.unique_codes_count = unique_count - 1 if unique_count > 0 else 0
                stats.last_updated = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Detection deleted successfully'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/detections/bulk-delete', methods=['DELETE'])
    @admin_required
    def crud_bulk_delete_detections():
        """DELETE: Remove multiple detections"""
        try:
            data = request.get_json()
            detection_ids = data.get('detection_ids', [])
            
            if not detection_ids:
                return jsonify({'status': 'error', 'message': 'No detection IDs provided'}), 400
            
            # Delete detections
            deleted_count = Detection.query.filter(Detection.id.in_(detection_ids)).delete(synchronize_session=False)
            
            # Update system stats
            stats = SystemStats.query.first()
            if stats:
                stats.total_detections = max(0, stats.total_detections - deleted_count)
                unique_count = db.session.query(Detection.postal_code).distinct().count()
                stats.unique_codes_count = unique_count
                stats.last_updated = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'Successfully deleted {deleted_count} detections'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ====================== SYSTEM STATS CRUD OPERATIONS ======================
    
    @app.route('/api/stats', methods=['GET'])
    @login_required
    def crud_get_system_stats():
        """GET: Retrieve system statistics"""
        try:
            stats = SystemStats.query.first()
            if not stats:
                return jsonify({
                    'status': 'success',
                    'data': {
                        'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'total_detections': 0,
                        'unique_codes_count': 0,
                        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                })
            
            return jsonify({
                'status': 'success',
                'data': stats.to_dict()
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/stats', methods=['PUT'])
    @admin_required
    def crud_update_system_stats():
        """PUT: Update system statistics"""
        try:
            stats = SystemStats.query.first()
            if not stats:
                stats = SystemStats()
                db.session.add(stats)
            
            data = request.get_json()
            
            # Update stats fields
            if 'total_detections' in data:
                stats.total_detections = data['total_detections']
            if 'unique_codes_count' in data:
                stats.unique_codes_count = data['unique_codes_count']
            if 'start_time' in data:
                stats.start_time = datetime.fromisoformat(data['start_time'])
            
            stats.last_updated = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'System stats updated successfully',
                'data': stats.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/stats/reset', methods=['POST'])
    @admin_required
    def crud_reset_system_stats():
        """POST: Reset all system statistics"""
        try:
            stats = SystemStats.query.first()
            if stats:
                stats.total_detections = 0
                stats.unique_codes_count = 0
                stats.start_time = datetime.now()
                stats.last_updated = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'System stats reset successfully',
                'data': stats.to_dict() if stats else None
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ====================== SEARCH AND FILTER OPERATIONS ======================
    
    @app.route('/api/detections/search', methods=['GET'])
    @login_required
    def crud_search_detections():
        """GET: Search detections by postal code or date range"""
        try:
            postal_code = request.args.get('postal_code')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            user_id = request.args.get('user_id')
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 50, type=int)
            
            query = Detection.query
            
            # Apply filters
            if postal_code:
                query = query.filter(Detection.postal_code.like(f'%{postal_code}%'))
            
            if start_date:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(Detection.timestamp >= start_dt)
            
            if end_date:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(Detection.timestamp <= end_dt)
            
            if user_id:
                query = query.filter(Detection.user_id == user_id)
            
            # Apply pagination and ordering
            detections = query.order_by(Detection.timestamp.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            detection_list = [detection.to_dict() for detection in detections.items]
            
            return jsonify({
                'status': 'success',
                'data': detection_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': detections.total,
                    'pages': detections.pages,
                    'has_next': detections.has_next,
                    'has_prev': detections.has_prev
                },
                'filters': {
                    'postal_code': postal_code,
                    'start_date': start_date,
                    'end_date': end_date,
                    'user_id': user_id
                }
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/users/search', methods=['GET'])
    @admin_required
    def crud_search_users():
        """GET: Search users by username, role, or department"""
        try:
            username = request.args.get('username')
            role = request.args.get('role')
            department = request.args.get('department')
            is_approved = request.args.get('is_approved')
            
            query = User.query
            
            # Apply filters
            if username:
                query = query.filter(User.username.like(f'%{username}%'))
            
            if role:
                query = query.filter(User.role == role)
            
            if department:
                query = query.filter(User.department.like(f'%{department}%'))
            
            if is_approved is not None:
                query = query.filter(User.is_approved == (is_approved.lower() == 'true'))
            
            users = query.order_by(User.created_at.desc()).all()
            user_list = [user.to_dict() for user in users]
            
            return jsonify({
                'status': 'success',
                'data': user_list,
                'count': len(user_list),
                'filters': {
                    'username': username,
                    'role': role,
                    'department': department,
                    'is_approved': is_approved
                }
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # ====================== EXPORT OPERATIONS ======================
    
    @app.route('/api/export/detections', methods=['GET'])
    @admin_required
    def crud_export_detections():
        """GET: Export detections data"""
        try:
            detections = Detection.query.order_by(Detection.timestamp.desc()).all()
            detection_list = [detection.to_dict() for detection in detections]
            
            return jsonify({
                'status': 'success',
                'data': detection_list,
                'count': len(detection_list),
                'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/export/users', methods=['GET'])
    @admin_required
    def crud_export_users():
        """GET: Export users data"""
        try:
            users = User.query.all()
            user_list = [user.to_dict() for user in users]
            
            return jsonify({
                'status': 'success',
                'data': user_list,
                'count': len(user_list),
                'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500 