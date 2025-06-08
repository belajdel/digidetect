import cv2
import time
import threading
import pytesseract
import re
import os
import json
import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session, flash
import numpy as np
from io import BytesIO
from PIL import Image
from functools import wraps
from models import db, User, Detection, SystemStats
from tunisia_postal_codes import POSTAL_CODES as TUNISIA_POSTAL_CODES
from crud_routes import register_crud_routes
from password_reset import password_reset_manager
from profile_forms import ProfileUpdateForm, PasswordChangeForm, AdminUserEditForm, AdminUserAddForm
from flask_wtf.csrf import CSRFProtect
import platform
import random

# Configuration Tesseract pour Windows
if platform.system() == "Windows":
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "tesseract"  # Si dans le PATH
    ]
    
    tesseract_path = None
    for path in possible_paths:
        try:
            if path == "tesseract":
                pytesseract.pytesseract.tesseract_cmd = path
                pytesseract.image_to_string(np.zeros((100, 100), dtype=np.uint8))
                tesseract_path = path
                break
            elif os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_path = path
                break
        except:
            continue
    
    if not tesseract_path:
        print("⚠️  ATTENTION: Tesseract OCR n'est pas installé!")
        print("📥 Veuillez installer Tesseract pour l'OCR: https://github.com/UB-Mannheim/tesseract/wiki")
        SIMULATION_MODE = False  # Force real mode even without Tesseract
    else:
        print(f"✅ Tesseract trouvé: {tesseract_path}")
        SIMULATION_MODE = False  # Force real camera mode

# Configuration
CAMERA_ID = 0
DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480
MIN_CONFIDENCE = 50
SCAN_INTERVAL = 1.0
DETECTION_TIMEOUT = 15
MAX_HISTORY_SIZE = 10

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize CSRF protection (disabled for now)
# csrf = CSRFProtect(app)

# Flask configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///detector.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SERVER_NAME'] = '127.0.0.1:5000'  # Added to fix URL building
app.config['APPLICATION_ROOT'] = '/'
app.config['PREFERRED_URL_SCHEME'] = 'http'

# Initialize database
db.init_app(app)

# Initialize password reset manager
password_reset_manager.init_app(app)

# Global variables
frame = None
latest_postal_code = None
latest_detection_time = None
latest_postal_code_valid = True
last_postal_code_time = 0
processing_active = True
camera_lock = threading.Lock()

# Check camera availability and set simulation mode accordingly
def check_camera_availability():
    """Check if camera is available and set simulation mode if needed"""
    global SIMULATION_MODE
    
    try:
        # Try to open camera
        test_camera = cv2.VideoCapture(CAMERA_ID)
        if test_camera.isOpened():
            # Camera is available
            test_camera.release()
            print(f"✅ Camera {CAMERA_ID} is available")
            # Force real camera mode (disable simulation)
            if hasattr(globals(), 'SIMULATION_MODE'):
                SIMULATION_MODE = False
            return True
        else:
            print(f"⚠️  Camera {CAMERA_ID} is not available")
            return False
    except Exception as e:
        print(f"⚠️  Camera error: {e}")
        return False

# Check camera availability during startup
CAMERA_AVAILABLE = check_camera_availability()

# Force real camera mode if camera is available
if CAMERA_AVAILABLE:
    SIMULATION_MODE = False
    print("🎥 REAL CAMERA MODE ENABLED - No simulation")

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('login'))
        elif session.get('role') != 'admin':
            flash('You need admin privileges to access this page', 'danger')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def preprocess_image(frame):
    """Apply preprocessing techniques to improve OCR accuracy"""
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply different preprocessing approaches
    processed_images = []
    
    # Method 1: Basic threshold
    _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    processed_images.append(('basic_threshold', thresh1))
    
    # Method 2: Adaptive threshold
    thresh2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    processed_images.append(('adaptive_threshold', thresh2))
    
    # Method 3: Gaussian blur + threshold
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh3 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_images.append(('otsu_threshold', thresh3))
    
    # Method 4: Morphological operations
    kernel = np.ones((2, 2), np.uint8)
    morph = cv2.morphologyEx(thresh2, cv2.MORPH_CLOSE, kernel)
    processed_images.append(('morphological', morph))
    
    # Method 5: Enhanced contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    _, thresh_enhanced = cv2.threshold(enhanced, 127, 255, cv2.THRESH_BINARY)
    processed_images.append(('enhanced_contrast', thresh_enhanced))
    
    return processed_images

def extract_postal_code(text):
    """Extract 4-digit postal codes from text"""
    text = str(text).strip()
    if not text:
        return []
    
    # Clean the text - remove extra spaces and special characters
    import string
    cleaned_text = ''.join(c if c.isdigit() or c.isspace() else ' ' for c in text)
    
    # Multiple patterns to try
    patterns = [
        r'\b\d{4}\b',           # Exact 4 digits
        r'\b\d{4}(?=\s|$)',     # 4 digits at word boundary
        r'(?<!\d)\d{4}(?!\d)',  # 4 digits not part of longer number
        r'\d{4}',               # Any 4 consecutive digits
    ]
    
    postal_codes = []
    
    # Try each pattern
    for pattern in patterns:
        matches = re.findall(pattern, cleaned_text)
        postal_codes.extend(matches)
        if postal_codes:
            break  # Use first successful pattern
    
    # Also try finding digits in the original text
    if not postal_codes:
        # Extract all digit sequences
        digit_sequences = re.findall(r'\d+', text)
        for seq in digit_sequences:
            if len(seq) == 4:
                postal_codes.append(seq)
            elif len(seq) > 4:
                # Try to extract 4-digit subsequences
                for i in range(len(seq) - 3):
                    four_digit = seq[i:i+4]
                    if 1000 <= int(four_digit) <= 9999:
                        postal_codes.append(four_digit)
    
    # Filter valid ranges (Tunisia postal codes are 1000-9999)
    valid_codes = []
    for code in postal_codes:
        try:
            code_int = int(code)
            if 1000 <= code_int <= 9999:
                valid_codes.append(code)
        except ValueError:
            continue
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for code in valid_codes:
        if code not in seen:
            seen.add(code)
            result.append(code)
    
    return result

def validate_postal_code(postal_code):
    """Validate if postal code exists in Tunisia postal codes database"""
    return postal_code in TUNISIA_POSTAL_CODES.keys()

def get_postal_code_info(postal_code):
    """Get region and location info for a postal code"""
    if postal_code in TUNISIA_POSTAL_CODES:
        return TUNISIA_POSTAL_CODES[postal_code]
    return None

def process_frames():
    """Thread function to continuously process frames for OCR"""
    global frame, latest_postal_code, latest_detection_time, processing_active, last_postal_code_time, latest_postal_code_valid
    
    last_scan_time = 0
    detection_cycle = 0
    
    print(f"🚀 Starting REAL OCR detection process...")
    print(f"📊 Mode: REAL CAMERA + OCR (No simulation)")
    
    while processing_active:
        try:
            current_time = time.time()
            
            # Clear detection display if timeout exceeded
            if latest_postal_code and (current_time - last_postal_code_time) > DETECTION_TIMEOUT:
                latest_postal_code = None
                latest_detection_time = None
                latest_postal_code_valid = True
            
            # Process frame for detection at specified intervals
            if current_time - last_scan_time >= SCAN_INTERVAL:
                detection_cycle += 1
                detected_codes = []
                
                # Real OCR processing (no simulation)
                if frame is not None:
                    try:
                        with camera_lock:
                            current_frame = frame.copy()
                        
                        # Preprocess image for better OCR
                        processed_images = preprocess_image(current_frame)
                        
                        # Try multiple OCR configurations
                        ocr_configs = [
                            ('digits_only', r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'),
                            ('single_block', r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'),
                            ('single_line', r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
                            ('word_detection', r'--oem 3 --psm 8'),
                            ('auto_detection', r'--oem 3 --psm 3 -c tessedit_char_whitelist=0123456789')
                        ]
                        
                        all_detected_codes = []
                        best_text = ""
                        
                        # Try each preprocessing method with each OCR config
                        for method, processed in processed_images:
                            for config_name, custom_config in ocr_configs:
                                try:
                                    text = pytesseract.image_to_string(processed, config=custom_config).strip()
                                    if text:
                                        codes = extract_postal_code(text)
                                        if codes:
                                            all_detected_codes.extend(codes)
                                            best_text = text
                                            print(f"🔍 SUCCESS with {method} + {config_name}: '{text}' -> {codes}")
                                            break
                                except:
                                    continue
                            if all_detected_codes:
                                break
                        
                        # Use the best detected codes
                        detected_codes = list(set(all_detected_codes))  # Remove duplicates
                        
                        if detection_cycle % 5 == 0:  # Log every 5 cycles
                            if detected_codes:
                                print(f"📫 OCR Cycle {detection_cycle}: FOUND postal codes: {detected_codes}")
                            elif best_text:
                                print(f"📖 OCR Cycle {detection_cycle}: Text found but no postal codes: '{best_text}'")
                            else:
                                print(f"⭕ OCR Cycle {detection_cycle}: No text detected")
                        
                    except Exception as e:
                        print(f"❌ OCR Error in cycle {detection_cycle}: {e}")
                        detected_codes = []
                else:
                    if detection_cycle % 20 == 0:  # Log every 20 cycles when no frame
                        print(f"⏳ Cycle {detection_cycle}: Waiting for camera frame...")
                
                # Process detected codes
                if detected_codes:
                    new_postal_code = detected_codes[0]
                    current_datetime = datetime.now()
                    
                    # Validate the postal code
                    is_valid = validate_postal_code(new_postal_code)
                    
                    # Update global variables
                    latest_postal_code = new_postal_code
                    latest_detection_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    latest_postal_code_valid = is_valid
                    last_postal_code_time = current_time
                    
                    # Save to database
                    try:
                        with app.app_context():
                            detection = Detection(
                                postal_code=new_postal_code,
                                timestamp=current_datetime,
                                confidence=MIN_CONFIDENCE,
                                user_id=None,
                                is_valid=is_valid
                            )
                            db.session.add(detection)
                            
                            # Update system statistics
                            stats = SystemStats.query.first()
                            if stats:
                                stats.total_detections += 1
                                stats.last_updated = current_datetime
                                unique_count = db.session.query(Detection.postal_code).distinct().count()
                                stats.unique_codes_count = unique_count
                            else:
                                new_stats = SystemStats(
                                    start_time=current_datetime,
                                    total_detections=1,
                                    unique_codes_count=1,
                                    last_updated=current_datetime
                                )
                                db.session.add(new_stats)
                            
                            db.session.commit()
                            
                            # Display detection info
                            postal_info = get_postal_code_info(new_postal_code)
                            location = postal_info['location'] if postal_info else "Unknown location"
                            region = postal_info['region'] if postal_info else "Unknown region"
                            
                            if is_valid:
                                print(f"✅ 🔍 REAL OCR: VALID postal code detected: {new_postal_code} ({region} - {location}) - SAVED")
                            else:
                                print(f"⚠️  🔍 REAL OCR: INVALID postal code detected: {new_postal_code} - SAVED")
                    
                    except Exception as e:
                        print(f"❌ Database save error: {e}")
                        db.session.rollback()
                
                last_scan_time = current_time
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"💥 Critical processing error: {e}")
            time.sleep(1)

def generate_frames():
    """Generator function for video streaming"""
    global frame, latest_postal_code, latest_postal_code_valid, camera_lock, CAMERA_AVAILABLE
    
    camera = None
    retry_count = 0
    max_retries = 5
    
    # Try to open camera with retries
    while retry_count < max_retries:
        try:
            print(f"🎥 Attempting to open camera {CAMERA_ID} (attempt {retry_count + 1}/{max_retries})")
            camera = cv2.VideoCapture(CAMERA_ID)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, DISPLAY_WIDTH)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, DISPLAY_HEIGHT)
            
            if camera.isOpened():
                print(f"✅ Camera {CAMERA_ID} opened successfully!")
                break
            else:
                print(f"❌ Camera {CAMERA_ID} failed to open")
                camera.release()
                camera = None
                retry_count += 1
                time.sleep(1)  # Wait before retry
        except Exception as e:
            print(f"❌ Camera exception: {e}")
            if camera:
                camera.release()
            camera = None
            retry_count += 1
            time.sleep(1)
    
    if not camera or not camera.isOpened():
        print("💥 CRITICAL: No camera available after all retries!")
        # Create error message image
        error_image = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
        error_image[:] = (0, 0, 50)  # Dark red background
        
        cv2.putText(error_image, "CAMERA ERROR", (DISPLAY_WIDTH//2 - 120, DISPLAY_HEIGHT//2 - 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
        cv2.putText(error_image, "No camera detected", (DISPLAY_WIDTH//2 - 100, DISPLAY_HEIGHT//2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 255), 1)
        cv2.putText(error_image, "Check camera connection", (DISPLAY_WIDTH//2 - 120, DISPLAY_HEIGHT//2 + 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 255), 1)
        
        # Send error frame and return
        ret, buffer = cv2.imencode('.jpg', error_image)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        return
    
    print("🎥 Starting video stream...")
    frame_count = 0
    
    while True:
        try:
            success, img = camera.read()
            if not success:
                print("⚠️  Frame read failed, retrying...")
                time.sleep(0.1)
                continue
                
            frame_count += 1
            if frame_count % 100 == 0:  # Log every 100 frames
                print(f"📹 Processed {frame_count} frames successfully")
            
            with camera_lock:
                frame = img.copy()
            
            # Draw detected postal code on frame
            if latest_postal_code:
                overlay = img.copy()
                cv2.rectangle(overlay, (0, 0), (img.shape[1], 80), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
                
                if latest_postal_code_valid:
                    color = (0, 255, 0)  # Green
                    status_text = "VALID"
                    postal_info = get_postal_code_info(latest_postal_code)
                    region_text = f"{postal_info['region']} - {postal_info['location']}" if postal_info else "Tunisia"
                else:
                    color = (0, 0, 255)  # Red
                    status_text = "UNKNOWN"
                    region_text = "Not in Tunisia Database"
                
                cv2.putText(img, f"Detected: {latest_postal_code} ({status_text})", (10, 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.putText(img, region_text, (10, 55), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Add camera info overlay
            cv2.putText(img, f"Camera {CAMERA_ID} - LIVE", (10, img.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            ret, buffer = cv2.imencode('.jpg', img)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
        except Exception as e:
            print(f"❌ Frame processing error: {e}")
            time.sleep(0.1)
            continue
        
        time.sleep(0.03)  # ~30 FPS

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.is_approved:
                session['username'] = user.username
                session['role'] = user.role
                session['user_id'] = user.id
                
                user.last_login = datetime.now()
                db.session.commit()
                
                flash(f'Welcome, {user.full_name}!', 'success')
                
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('user_dashboard'))
            else:
                flash('Your account is pending approval. Please contact an administrator.', 'warning')
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Route for user registration"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        email = request.form['email']
        department = request.form.get('department', '')
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            role='user',
            is_approved=True,  # Auto-approve for demo
            full_name=full_name,
            email=email,
            department=department,
            created_at=datetime.now()
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Route for password reset request"""
    if request.method == 'POST':
        email = request.form.get('email')
        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/dashboard')
@login_required
def user_dashboard():
    """Main user dashboard - temporarily redirected to simplified version"""
    return redirect(url_for('user_dashboard_simple'))

@app.route('/dashboard_simple')
@login_required  
def user_dashboard_simple():
    """Simplified user dashboard as backup"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return "<h1>Error</h1><p>User not found. Please login again.</p>"
        
        # System status
        system_status = {
            'mode': 'production',
            'database': 'connected',
            'processing': 'active' if processing_active else 'inactive'
        }
        
        # Simplified data
        camera_status = {'status': 'active', 'mode': 'real_camera', 'error': None}
        user_stats = {'total_detections': 0, 'valid_detections': 0, 'invalid_detections': 0, 'success_rate': 0, 'today_detections': 0, 'favorite_region': 'Aucune'}
        recent_detections = []
        current_detection = {'postal_code': None, 'timestamp': None, 'valid': True}
        
        return render_template('user_dashboard.html',
                             user=user,
                             system_status=system_status,
                             camera_status=camera_status,
                             user_stats=user_stats,
                             recent_detections=recent_detections,
                             current_detection=current_detection)
    except Exception as e:
        return f"<h1>Dashboard Error</h1><p>{str(e)}</p><a href='/'>Back to Home</a>"

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_postal_code')
def get_postal_code():
    global latest_postal_code, latest_detection_time, latest_postal_code_valid
    
    response_data = {
        'postal_code': latest_postal_code,
        'timestamp': latest_detection_time,
        'status': 'detected' if latest_postal_code else 'scanning',
        'valid': latest_postal_code_valid if latest_postal_code else None,
        'region': None,
        'location': None
    }
    
    if latest_postal_code and latest_postal_code_valid:
        postal_info = get_postal_code_info(latest_postal_code)
        if postal_info:
            response_data['region'] = postal_info['region']
            response_data['location'] = postal_info['location']
    
    return jsonify(response_data)

@app.route('/get_history')
@login_required
def get_history():
    """Get detection history with regional information"""
    try:
        detections = Detection.query.order_by(Detection.timestamp.desc()).limit(MAX_HISTORY_SIZE).all()
        history = []
        
        for detection in detections:
            detection_data = {
                'postal_code': detection.postal_code,
                'timestamp': detection.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'is_valid': detection.is_valid,
                'confidence': detection.confidence
            }
            
            # Add region and location info for valid codes
            if detection.is_valid:
                postal_info = get_postal_code_info(detection.postal_code)
                if postal_info:
                    detection_data['region'] = postal_info['region']
                    detection_data['location'] = postal_info['location']
                else:
                    detection_data['region'] = 'Unknown'
                    detection_data['location'] = 'Unknown'
            else:
                detection_data['region'] = 'Non-Tunisia'
                detection_data['location'] = 'Outside Database'
            
            history.append(detection_data)
        
        return jsonify({
            'history': history,
            'count': len(history)
        })
        
    except Exception as e:
        print(f"Error fetching history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/users')
@admin_required
def admin_users_list():
    """Route for administrators to view the list of all users"""
    try:
        # Get page number from query parameters (default: 1)
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Number of users per page
        
        # Get search and filter parameters
        search_query = request.args.get('search', '', type=str)
        role_filter = request.args.get('role', '', type=str)
        
        # Build the query with filters
        query = User.query
        
        # Apply search filter (search in username, full_name, email)
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    User.username.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
        
        # Apply role filter
        if role_filter and role_filter != 'all':
            query = query.filter(User.role == role_filter)
        
        # Order by creation date (newest first)
        query = query.order_by(User.created_at.desc())
        
        # Paginate results
        users_pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = users_pagination.items
        
        # Get statistics for dashboard
        total_users = User.query.count()
        admin_count = User.query.filter_by(role='admin').count()
        user_count = User.query.filter_by(role='user').count()
        approved_count = User.query.filter_by(is_approved=True).count()
        pending_count = User.query.filter_by(is_approved=False).count()
        
        stats = {
            'total_users': total_users,
            'admin_count': admin_count,
            'user_count': user_count,
            'approved_count': approved_count,
            'pending_count': pending_count
        }
        
        return render_template('users_list.html', 
                             users=users,
                             pagination=users_pagination,
                             stats=stats,
                             search_query=search_query,
                             role_filter=role_filter)
        
    except Exception as e:
        # Log the error
        print(f"Error fetching users list: {e}")
        
        # Flash error message to user
        flash('Error fetching users list. Please try again.', 'error')
        
        # Redirect to admin dashboard
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/system/reset', methods=['GET', 'POST'])
@admin_required
def admin_system_reset():
    """Route for system reset (dangerous operation)"""
    if request.method == 'POST':
        try:
            # Clear all detections
            Detection.query.delete()
            
            # Reset system statistics
            SystemStats.query.delete()
            
            # Create fresh system stats
            new_stats = SystemStats(
                start_time=datetime.now(),
                total_detections=0,
                unique_codes_count=0,
                last_updated=datetime.now()
            )
            db.session.add(new_stats)
            
            # Commit changes
            db.session.commit()
            
            flash('System has been reset successfully. All detection data has been cleared.', 'success')
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            # Rollback on error
            db.session.rollback()
            print(f"System reset error: {e}")
            flash(f'Error resetting system: {str(e)}', 'error')
            return redirect(url_for('admin_dashboard'))
    
    # GET request - show confirmation page
    return render_template('admin_system_reset.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Route for user profile management"""
    user = User.query.filter_by(username=session['username']).first()
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    # Handle different form submissions
    action = request.form.get('action', 'view')
    
    # Initialize forms
    try:
        profile_form = ProfileUpdateForm(user)
        password_form = PasswordChangeForm(user)
    except:
        # Simple fallback if forms don't work
        profile_form = None
        password_form = None
    
    # Handle profile update
    if request.method == 'POST' and action == 'update_profile':
        try:
            # Update user profile fields
            user.full_name = request.form.get('full_name', user.full_name)
            user.email = request.form.get('email', user.email)
            user.department = request.form.get('department', user.department)
            user.phone = request.form.get('phone', user.phone)
            user.address = request.form.get('address', user.address)
            user.bio = request.form.get('bio', user.bio)
            user.profile_updated_at = datetime.now()
            
            # Commit changes to database
            db.session.commit()
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            print(f"Profile update error: {e}")
    
    # Handle password change
    elif request.method == 'POST' and action == 'change_password':
        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Validate current password
            if not user.check_password(current_password):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters long', 'error')
            else:
                # Update password
                user.set_password(new_password)
                user.password_reset_at = datetime.now()
                
                # Commit changes to database
                db.session.commit()
                
                flash('Password changed successfully!', 'success')
                return redirect(url_for('profile'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'error')
            print(f"Password change error: {e}")
    
    return render_template('profile.html', 
                         user=user, 
                         profile_form=profile_form, 
                         password_form=password_form)

@app.route('/api/user_stats')
@login_required
def api_user_stats():
    """API endpoint for user-specific statistics"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        from datetime import date, timedelta
        
        # Calculate statistics (ALL detections - valid and invalid)
        total_detections = Detection.query.filter_by(user_id=user.id).count()
        valid_detections = Detection.query.filter_by(user_id=user.id, is_valid=True).count()
        invalid_detections = Detection.query.filter_by(user_id=user.id, is_valid=False).count()
        
        # Today's detections (all)
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_detections = Detection.query.filter(
            Detection.user_id == user.id,
            Detection.timestamp >= today_start
        ).count()
        
        # Success rate (valid / total)
        success_rate = round((valid_detections / total_detections) * 100, 1) if total_detections > 0 else 0
        
        # Most detected region (only from valid detections)
        favorite_region = 'None'
        user_postal_codes = db.session.query(
            Detection.postal_code,
            db.func.count(Detection.id).label('count')
        ).filter_by(user_id=user.id, is_valid=True).group_by(Detection.postal_code).order_by(
            db.func.count(Detection.id).desc()
        ).first()
        
        if user_postal_codes:
            postal_code = user_postal_codes[0]
            postal_info = get_postal_code_info(postal_code)
            if postal_info:
                favorite_region = postal_info['region']
        
        return jsonify({
            'total_detections': total_detections,
            'valid_detections': valid_detections,
            'invalid_detections': invalid_detections,
            'today_detections': today_detections,
            'success_rate': success_rate,
            'favorite_region': favorite_region,
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': f'Error calculating statistics: {str(e)}'}), 500

@app.route('/api/system_stats')
@login_required
def api_system_stats():
    """API endpoint for system-wide statistics"""
    try:
        # Get system statistics
        stats = SystemStats.query.first()
        
        # Count totals from database
        total_detections = Detection.query.count()
        valid_detections = Detection.query.filter_by(is_valid=True).count()
        invalid_detections = Detection.query.filter_by(is_valid=False).count()
        unique_codes = db.session.query(Detection.postal_code).distinct().count()
        
        # Calculate uptime if stats exist
        uptime_hours = 0
        if stats and stats.start_time:
            uptime = datetime.now() - stats.start_time
            uptime_hours = round(uptime.total_seconds() / 3600, 1)
        
        return jsonify({
            'total_detections': total_detections,
            'valid_detections': valid_detections,
            'invalid_detections': invalid_detections,
            'unique_codes': unique_codes,
            'uptime_hours': uptime_hours,
            'start_time': stats.start_time.strftime('%Y-%m-%d %H:%M:%S') if stats else None,
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching system statistics: {str(e)}'}), 500

@app.route('/user/history')
@login_required
def user_history():
    """Route for user detection history with pagination"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Get page number from query parameters (default: 1)
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Number of detections per page
        
        # Get user's detections with pagination
        detections_pagination = Detection.query.filter_by(user_id=user.id).order_by(
            Detection.timestamp.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        detections = detections_pagination.items
        
        # Add postal code info to each detection
        enriched_detections = []
        for detection in detections:
            detection_data = detection.to_dict()
            if detection.is_valid:
                postal_info = get_postal_code_info(detection.postal_code)
                detection_data['region'] = postal_info['region'] if postal_info else 'Unknown'
                detection_data['location'] = postal_info['location'] if postal_info else 'Unknown'
            else:
                detection_data['region'] = 'Non-Tunisian Code'
                detection_data['location'] = 'Outside database'
            detection_data['is_valid'] = detection.is_valid
            enriched_detections.append(detection_data)
        
        # Calculate user statistics
        total_detections = Detection.query.filter_by(user_id=user.id).count()
        valid_detections = Detection.query.filter_by(user_id=user.id, is_valid=True).count()
        invalid_detections = Detection.query.filter_by(user_id=user.id, is_valid=False).count()
        
        user_stats = {
            'total_detections': total_detections,
            'valid_detections': valid_detections,
            'invalid_detections': invalid_detections,
            'success_rate': round((valid_detections / total_detections) * 100, 1) if total_detections > 0 else 0
        }
        
        return render_template('user_history.html',
                             user=user,
                             detections=enriched_detections,
                             pagination=detections_pagination,
                             user_stats=user_stats)
        
    except Exception as e:
        print(f"User history error: {e}")
        flash('Error loading detection history', 'error')
        return redirect(url_for('user_dashboard'))

@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    """Route for administrators to add new users"""
    if request.method == 'POST':
        try:
            # Get form data
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            role = request.form.get('role', 'user')
            department = request.form.get('department', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            
            # Validation
            if not username or not password or not full_name or not email:
                flash('Username, password, full name, and email are required', 'error')
                return render_template('admin_add_user.html')
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long', 'error')
                return render_template('admin_add_user.html')
            
            # Check if user already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists', 'error')
                return render_template('admin_add_user.html')
            
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash('Email already exists', 'error')
                return render_template('admin_add_user.html')
            
            # Create new user
            new_user = User(
                username=username,
                role=role,
                is_approved=True,  # Admin-created users are automatically approved
                full_name=full_name,
                email=email,
                department=department,
                phone=phone,
                address=address,
                created_at=datetime.now()
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'User {username} has been created successfully!', 'success')
            return redirect(url_for('admin_users_list'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Add user error: {e}")
            flash(f'Error creating user: {str(e)}', 'error')
            return render_template('admin_add_user.html')
    
    # GET request - show add user form
    return render_template('admin_add_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    """Route for administrators to edit existing users"""
    try:
        # Get the user to edit
        user = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            # Get form data
            username = request.form.get('username', '').strip()
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            role = request.form.get('role', user.role)
            department = request.form.get('department', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            is_approved = request.form.get('is_approved') == 'on'
            new_password = request.form.get('new_password', '').strip()
            
            # Validation
            if not username or not full_name or not email:
                flash('Username, full name, and email are required', 'error')
                return render_template('admin_edit_user.html', user=user)
            
            # Check if username is taken by another user
            existing_user = User.query.filter(User.username == username, User.id != user.id).first()
            if existing_user:
                flash('Username already exists', 'error')
                return render_template('admin_edit_user.html', user=user)
            
            # Check if email is taken by another user
            existing_email = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_email:
                flash('Email already exists', 'error')
                return render_template('admin_edit_user.html', user=user)
            
            # Update user data
            user.username = username
            user.full_name = full_name
            user.email = email
            user.role = role
            user.department = department
            user.phone = phone
            user.address = address
            user.is_approved = is_approved
            user.profile_updated_at = datetime.now()
            
            # Update password if provided
            if new_password:
                if len(new_password) < 6:
                    flash('Password must be at least 6 characters long', 'error')
                    return render_template('admin_edit_user.html', user=user)
                user.set_password(new_password)
                user.password_reset_at = datetime.now()
            
            db.session.commit()
            
            flash(f'User {username} has been updated successfully!', 'success')
            return redirect(url_for('admin_users_list'))
            
        # GET request - show edit form
        return render_template('admin_edit_user.html', user=user)
        
    except Exception as e:
        print(f"Edit user error: {e}")
        flash(f'Error editing user: {str(e)}', 'error')
        return redirect(url_for('admin_users_list'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Route for administrators to delete users"""
    try:
        # Get the user to delete
        user = User.query.get_or_404(user_id)
        
        # Prevent deletion of current admin user
        current_admin = User.query.filter_by(username=session['username']).first()
        if user.id == current_admin.id:
            flash('You cannot delete your own account', 'error')
            return redirect(url_for('admin_users_list'))
        
        # Prevent deletion of the last admin
        admin_count = User.query.filter_by(role='admin').count()
        if user.role == 'admin' and admin_count <= 1:
            flash('Cannot delete the last administrator account', 'error')
            return redirect(url_for('admin_users_list'))
        
        username = user.username
        
        # Delete user's detections (optional - you might want to keep them)
        # Detection.query.filter_by(user_id=user.id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {username} has been deleted successfully', 'success')
        return redirect(url_for('admin_users_list'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete user error: {e}")
        flash(f'Error deleting user: {str(e)}', 'error')
        return redirect(url_for('admin_users_list'))

@app.route('/api/user_detections_chart')
@login_required
def api_user_detections_chart():
    """API endpoint for user detections chart data"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        from datetime import date, timedelta
        import calendar
        
        # Get last 30 days of data
        end_date = date.today()
        start_date = end_date - timedelta(days=29)
        
        # Query detections by day
        daily_detections = []
        current_date = start_date
        
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            count = Detection.query.filter(
                Detection.user_id == user.id,
                Detection.timestamp >= day_start,
                Detection.timestamp <= day_end
            ).count()
            
            daily_detections.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'day': current_date.strftime('%d'),
                'month': current_date.strftime('%b'),
                'detections': count
            })
            
            current_date += timedelta(days=1)
        
        return jsonify({
            'daily_data': daily_detections,
            'total_days': len(daily_detections)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generating chart data: {str(e)}'}), 500

@app.route('/api/camera_status')
@login_required
def api_camera_status():
    """API endpoint for camera status"""
    global processing_active, latest_detection_time, SIMULATION_MODE
    
    try:
        return jsonify({
            'status': 'active' if processing_active else 'inactive',
            'mode': 'real_camera',  # Always real camera mode
            'last_detection': latest_detection_time,
            'error': None,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching camera status: {str(e)}'}), 500

@app.route('/api/simulate_detection', methods=['POST'])
@login_required
def api_simulate_detection():
    """API endpoint to simulate a postal code detection"""
    global latest_postal_code, latest_detection_time, latest_postal_code_valid, last_postal_code_time
    
    try:
        data = request.get_json()
        postal_code = data.get('postal_code', '1000')
        
        # Validate the postal code format
        if not re.match(r'^\d{4}$', postal_code):
            return jsonify({'error': 'Invalid postal code format'}), 400
        
        # Check if it's a valid Tunisia postal code
        is_valid = validate_postal_code(postal_code)
        current_datetime = datetime.now()
        
        # Update global variables
        latest_postal_code = postal_code
        latest_detection_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        latest_postal_code_valid = is_valid
        last_postal_code_time = time.time()
        
        # Save to database
        user = User.query.filter_by(username=session['username']).first()
        if user:
            detection = Detection(
                postal_code=postal_code,
                timestamp=current_datetime,
                confidence=95,  # High confidence for manual simulation
                user_id=user.id,
                is_valid=is_valid
            )
            db.session.add(detection)
            
            # Update system statistics
            stats = SystemStats.query.first()
            if stats:
                stats.total_detections += 1
                stats.last_updated = current_datetime
                unique_count = db.session.query(Detection.postal_code).distinct().count()
                stats.unique_codes_count = unique_count
            else:
                new_stats = SystemStats(
                    start_time=current_datetime,
                    total_detections=1,
                    unique_codes_count=1,
                    last_updated=current_datetime
                )
                db.session.add(new_stats)
            
            db.session.commit()
        
        # Get postal info
        postal_info = get_postal_code_info(postal_code) if is_valid else None
        
        return jsonify({
            'success': True,
            'postal_code': postal_code,
            'is_valid': is_valid,
            'region': postal_info['region'] if postal_info else None,
            'location': postal_info['location'] if postal_info else None,
            'timestamp': latest_detection_time
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error simulating detection: {str(e)}'}), 500

@app.route('/api/users', methods=['GET'])
@admin_required
def api_users_list():
    """API endpoint to get users list"""
    try:
        users = User.query.all()
        users_data = []
        
        for user in users:
            user_data = {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'is_approved': user.is_approved,
                'department': user.department,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
            }
            users_data.append(user_data)
        
        return jsonify({
            'users': users_data,
            'total': len(users_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching users: {str(e)}'}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
@admin_required
def api_user_detail(user_id):
    """API endpoint to get specific user details"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get user statistics
        total_detections = Detection.query.filter_by(user_id=user.id).count()
        valid_detections = Detection.query.filter_by(user_id=user.id, is_valid=True).count()
        
        user_data = {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role,
            'is_approved': user.is_approved,
            'department': user.department,
            'phone': user.phone,
            'address': user.address,
            'bio': user.bio,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'profile_updated_at': user.profile_updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.profile_updated_at else None,
            'statistics': {
                'total_detections': total_detections,
                'valid_detections': valid_detections,
                'success_rate': round((valid_detections / total_detections) * 100, 1) if total_detections > 0 else 0
            }
        }
        
        return jsonify(user_data)
        
    except Exception as e:
        return jsonify({'error': f'Error fetching user details: {str(e)}'}), 500

@app.route('/get_stats')
@login_required
def get_stats():
    """Legacy API endpoint for system statistics (used by admin dashboard JS)"""
    try:
        # Get system statistics
        stats = SystemStats.query.first()
        
        # Count totals from database
        total_detections = Detection.query.count()
        valid_detections = Detection.query.filter_by(is_valid=True).count()
        invalid_detections = Detection.query.filter_by(is_valid=False).count()
        unique_codes = db.session.query(Detection.postal_code).distinct().count()
        
        # User statistics
        total_users = User.query.count()
        admin_users = User.query.filter_by(role='admin').count()
        regular_users = User.query.filter_by(role='user').count()
        
        # Calculate uptime if stats exist
        uptime_hours = 0
        if stats and stats.start_time:
            uptime = datetime.now() - stats.start_time
            uptime_hours = round(uptime.total_seconds() / 3600, 1)
        
        return jsonify({
            'total_detections': total_detections,
            'valid_detections': valid_detections,
            'invalid_detections': invalid_detections,
            'unique_codes': unique_codes,
            'uptime_hours': uptime_hours,
            'total_users': total_users,
            'admin_users': admin_users,
            'regular_users': regular_users,
            'start_time': stats.start_time.strftime('%Y-%m-%d %H:%M:%S') if stats else None,
            'last_updated': datetime.now().strftime('%H:%M:%S'),
            'success_rate': round((valid_detections / total_detections) * 100, 1) if total_detections > 0 else 0
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching system statistics: {str(e)}'}), 500

@app.route('/manage_users')
@admin_required
def manage_users():
    """Legacy API endpoint for user management (used by admin dashboard JS)"""
    try:
        users = User.query.all()
        users_data = []
        
        for user in users:
            # Get user statistics
            total_detections = Detection.query.filter_by(user_id=user.id).count()
            valid_detections = Detection.query.filter_by(user_id=user.id, is_valid=True).count()
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'is_approved': user.is_approved,
                'department': user.department,
                'phone': user.phone,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Never',
                'total_detections': total_detections,
                'valid_detections': valid_detections,
                'success_rate': round((valid_detections / total_detections) * 100, 1) if total_detections > 0 else 0
            }
            users_data.append(user_data)
        
        # Sort by last login (most recent first)
        users_data.sort(key=lambda x: x['last_login'] if x['last_login'] != 'Never' else '1900-01-01', reverse=True)
        
        return jsonify({
            'users': users_data,
            'total': len(users_data),
            'approved': len([u for u in users_data if u['is_approved']]),
            'pending': len([u for u in users_data if not u['is_approved']]),
            'admins': len([u for u in users_data if u['role'] == 'admin']),
            'regular_users': len([u for u in users_data if u['role'] == 'user'])
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching users: {str(e)}'}), 500

@app.route('/get_regional_stats')
@login_required
def get_regional_stats():
    """API endpoint for Tunisia regional postal code statistics"""
    try:
        # Get all valid detections with postal codes
        valid_detections = Detection.query.filter_by(is_valid=True).all()
        
        # Count detections by region
        region_counts = {}
        total_valid_detections = len(valid_detections)
        
        for detection in valid_detections:
            postal_info = get_postal_code_info(detection.postal_code)
            if postal_info:
                region = postal_info['region']
                if region in region_counts:
                    region_counts[region] += 1
                else:
                    region_counts[region] = 1
        
        # Convert to list format and calculate percentages
        regional_stats = []
        for region, count in region_counts.items():
            percentage = round((count / total_valid_detections) * 100, 1) if total_valid_detections > 0 else 0
            regional_stats.append({
                'region': region,
                'detections': count,
                'percentage': percentage
            })
        
        # Sort by detection count (highest first)
        regional_stats.sort(key=lambda x: x['detections'], reverse=True)
        
        # Get unique regions detected vs total Tunisia regions
        unique_regions_detected = len(region_counts)
        total_tunisia_regions = 24  # Tunisia has 24 governorates
        coverage_percentage = round((unique_regions_detected / total_tunisia_regions) * 100, 1)
        
        # Get top 5 regions for summary
        top_regions = regional_stats[:5] if regional_stats else []
        
        return jsonify({
            'regional_stats': regional_stats,
            'top_regions': top_regions,
            'total_regions_detected': unique_regions_detected,
            'total_tunisia_regions': total_tunisia_regions,
            'coverage_percentage': coverage_percentage,
            'total_valid_detections': total_valid_detections,
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching regional statistics: {str(e)}'}), 500

@app.route('/api/camera_control', methods=['GET', 'POST'])
@admin_required
def api_camera_control():
    """API endpoint to control camera settings"""
    global SIMULATION_MODE, CAMERA_AVAILABLE, CAMERA_ID
    
    if request.method == 'POST':
        try:
            action = request.json.get('action')
            
            if action == 'toggle_simulation':
                SIMULATION_MODE = not SIMULATION_MODE
                status = 'enabled' if SIMULATION_MODE else 'disabled'
                return jsonify({
                    'success': True,
                    'message': f'Simulation mode {status}',
                    'simulation_mode': SIMULATION_MODE
                })
            
            elif action == 'change_camera':
                new_camera_id = request.json.get('camera_id', 0)
                CAMERA_ID = new_camera_id
                CAMERA_AVAILABLE = check_camera_availability()
                return jsonify({
                    'success': True,
                    'message': f'Camera changed to ID {CAMERA_ID}',
                    'camera_available': CAMERA_AVAILABLE,
                    'simulation_mode': SIMULATION_MODE
                })
            
            elif action == 'test_camera':
                CAMERA_AVAILABLE = check_camera_availability()
                return jsonify({
                    'success': True,
                    'camera_available': CAMERA_AVAILABLE,
                    'simulation_mode': SIMULATION_MODE,
                    'message': 'Camera test completed'
                })
            
            else:
                return jsonify({'error': 'Invalid action'}), 400
                
        except Exception as e:
            return jsonify({'error': f'Error controlling camera: {str(e)}'}), 500
    
    # GET request - return current camera status
    return jsonify({
        'simulation_mode': SIMULATION_MODE,
        'camera_available': CAMERA_AVAILABLE,
        'camera_id': CAMERA_ID,
        'tesseract_available': not SIMULATION_MODE or CAMERA_AVAILABLE
    })

@app.route('/api/camera_test')
@admin_required
def api_camera_test():
    """API endpoint to test different camera IDs"""
    try:
        available_cameras = []
        
        # Test camera IDs 0-3
        for camera_id in range(4):
            test_camera = cv2.VideoCapture(camera_id)
            if test_camera.isOpened():
                available_cameras.append({
                    'id': camera_id,
                    'name': f'Camera {camera_id}',
                    'available': True
                })
                test_camera.release()
            else:
                available_cameras.append({
                    'id': camera_id,
                    'name': f'Camera {camera_id}',
                    'available': False
                })
        
        return jsonify({
            'available_cameras': available_cameras,
            'current_camera': CAMERA_ID,
            'total_found': len([c for c in available_cameras if c['available']])
        })
        
    except Exception as e:
        return jsonify({'error': f'Error testing cameras: {str(e)}'}), 500

@app.route('/api/admin/detections_trend')
@admin_required
def api_admin_detections_trend():
    """API endpoint for detection trends over the last 7 days"""
    try:
        from datetime import date, timedelta
        
        # Get last 7 days
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        
        labels = []
        total_counts = []
        valid_counts = []
        
        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            # Total detections for this day
            total_count = Detection.query.filter(
                Detection.timestamp >= day_start,
                Detection.timestamp <= day_end
            ).count()
            
            # Valid detections for this day
            valid_count = Detection.query.filter(
                Detection.timestamp >= day_start,
                Detection.timestamp <= day_end,
                Detection.is_valid == True
            ).count()
            
            labels.append(current_date.strftime('%m/%d'))
            total_counts.append(total_count)
            valid_counts.append(valid_count)
            
            current_date += timedelta(days=1)
        
        return jsonify({
            'labels': labels,
            'total': total_counts,
            'valid': valid_counts
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching trend data: {str(e)}'}), 500

@app.route('/api/admin/hourly_stats')
@admin_required
def api_admin_hourly_stats():
    """API endpoint for hourly detection statistics for today"""
    try:
        from datetime import date
        
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Get all detections for today
        today_detections = Detection.query.filter(
            Detection.timestamp >= today_start,
            Detection.timestamp <= today_end
        ).all()
        
        # Count by hour
        hourly_counts = [0] * 24
        for detection in today_detections:
            hour = detection.timestamp.hour
            hourly_counts[hour] += 1
        
        return jsonify({
            'hourly_counts': hourly_counts,
            'total_today': len(today_detections)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error fetching hourly stats: {str(e)}'}), 500

@app.route('/api/real_time_stats')
def real_time_stats():
    """Enhanced real-time statistics for dynamic dashboard"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        # Enhanced statistics with performance metrics
        total_detections = Detection.query.filter_by(user_id=user.id).count()
        valid_detections = Detection.query.filter_by(user_id=user.id, is_valid=True).count()
        invalid_detections = total_detections - valid_detections
        
        # Performance metrics
        avg_detection_time = 1.2  # Mock value for now
        accuracy_rate = (valid_detections / total_detections * 100) if total_detections > 0 else 0
        
        # Regional coverage - get unique postal codes and calculate their regions
        valid_postal_codes = db.session.query(Detection.postal_code).filter_by(
            user_id=user.id, is_valid=True
        ).distinct().all()
        
        unique_regions = set()
        for pc_tuple in valid_postal_codes:
            postal_code = pc_tuple[0]
            if postal_code in TUNISIA_POSTAL_CODES:
                region = TUNISIA_POSTAL_CODES[postal_code]['region']
                unique_regions.add(region)
        
        regions_detected = len(unique_regions)
        total_regions = 24  # Tunisia has 24 regions
        coverage_percent = (regions_detected / total_regions * 100)
        
        return jsonify({
            'total_detections': total_detections,
            'valid_detections': valid_detections,
            'invalid_detections': invalid_detections,
            'accuracy_rate': round(accuracy_rate, 1),
            'avg_detection_time': avg_detection_time,
            'coverage_percent': round(coverage_percent, 1),
            'regions_covered': regions_detected,
            'performance_score': round((accuracy_rate + coverage_percent) / 2, 1)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live_notifications')
def live_notifications():
    """Get live notifications for the dynamic platform"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        # Get recent system events (mock data for now)
        notifications = [
            {
                'id': 1,
                'type': 'detection',
                'message': 'Nouvelle détection en cours...',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'priority': 'info'
            },
            {
                'id': 2,
                'type': 'system',
                'message': 'IA optimisée - Performance améliorée',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'priority': 'success'
            }
        ]
        
        return jsonify({
            'notifications': notifications,
            'unread_count': len(notifications)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dynamic_chart_data')
def dynamic_chart_data():
    """Enhanced chart data with multiple datasets"""
    try:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        # Get detection data for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        detections = Detection.query.filter(
            Detection.user_id == user.id,
            Detection.timestamp >= start_date,
            Detection.timestamp <= end_date
        ).all()
        
        # Group by day
        daily_data = {}
        for i in range(7):
            date = start_date + timedelta(days=i)
            day_name = date.strftime('%a')
            daily_data[day_name] = {'total': 0, 'valid': 0, 'invalid': 0}
        
        for detection in detections:
            day_name = detection.timestamp.strftime('%a')
            if day_name in daily_data:
                daily_data[day_name]['total'] += 1
                if detection.is_valid:
                    daily_data[day_name]['valid'] += 1
                else:
                    daily_data[day_name]['invalid'] += 1
        
        return jsonify({
            'labels': list(daily_data.keys()),
            'datasets': [
                {
                    'label': 'Total',
                    'data': [daily_data[day]['total'] for day in daily_data.keys()],
                    'borderColor': '#667eea',
                    'backgroundColor': 'rgba(102, 126, 234, 0.1)'
                },
                {
                    'label': 'Valides',
                    'data': [daily_data[day]['valid'] for day in daily_data.keys()],
                    'borderColor': '#4caf50',
                    'backgroundColor': 'rgba(76, 175, 80, 0.1)'
                },
                {
                    'label': 'Invalides',
                    'data': [daily_data[day]['invalid'] for day in daily_data.keys()],
                    'borderColor': '#f44336',
                    'backgroundColor': 'rgba(244, 67, 54, 0.1)'
                }
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system_health')
def system_health():
    """System health monitoring for dynamic platform"""
    try:
        # Mock system health data
        health_data = {
            'cpu_usage': 45,
            'memory_usage': 62,
            'disk_usage': 78,
            'camera_fps': 30,
            'detection_rate': 95,
            'database_status': 'connected',
            'ai_engine_status': 'active',
            'last_backup': '2024-01-15 02:30:00',
            'uptime': '15d 4h 32m'
        }
        
        return jsonify(health_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle_feature', methods=['POST'])
def toggle_feature():
    """Toggle platform features dynamically"""
    try:
        data = request.get_json()
        feature = data.get('feature')
        enabled = data.get('enabled', True)
        
        # Mock feature toggling
        features = {
            'auto_detection': enabled,
            'notifications': enabled,
            'real_time_updates': enabled,
            'ai_enhancement': enabled
        }
        
        return jsonify({
            'success': True,
            'feature': feature,
            'enabled': enabled,
            'message': f'Fonctionnalité {feature} {"activée" if enabled else "désactivée"}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        print("🔍 VALIDATION DU SYSTÈME")
        print("=" * 45)
        print(f"🎥 Mode: REAL CAMERA ONLY (Simulation DISABLED)")
        print(f"📷 Caméra ID: {CAMERA_ID}")
        print(f"⏱️  Intervalle de scan: {SCAN_INTERVAL}s")
        print(f"🎯 Seuil de confiance: {MIN_CONFIDENCE}%")
        print(f"🔍 OCR: {'Disponible' if tesseract_path else 'Non installé'}")
        print("=" * 45)
    
    # Register CRUD routes
    try:
        register_crud_routes(app)
        print("✅ CRUD routes registered successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not register CRUD routes: {e}")
    
    # Start processing thread
    processing_active = True
    processing_thread = threading.Thread(target=process_frames)
    processing_thread.daemon = True
    processing_thread.start()
    
    print(f"\n🚀 Démarrage du serveur Flask...")
    print(f"🌐 Accès: http://127.0.0.1:5000")
    print(f"👤 Admin: username=admin, password=admin123")
    print(f"👤 User: username=user, password=user123")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        processing_active = False
        if processing_thread.is_alive():
            processing_thread.join(timeout=1.0) 