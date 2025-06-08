# Postal Code Detector

Real-time detection of 4-digit postal codes using OpenCV and Tesseract OCR running on a Raspberry Pi with Flask web interface.

## Features

- Real-time postal code detection using OCR
- Web-based interface for monitoring
- Role-based access control (Admin, User)
- Live video feed display
- Detection history with timestamps
- Regional statistics for Tunisia postal codes
- RESTful API for data access
- Modern responsive design with Bootstrap
- Comprehensive user management system
- Email-based password reset system

## Installation

### Prerequisites

- Python 3.7+ 
- Tesseract OCR
- OpenCV
- A camera (USB webcam or Raspberry Pi camera)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/postal-code-detector.git
   cd postal-code-detector
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install Tesseract OCR:
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Linux/Raspberry Pi: `sudo apt-get install tesseract-ocr`

4. Configure Tesseract path in `app.py` or `app_with_db.py` if necessary.

## Usage

### Running with In-Memory Storage

The default implementation (`app.py`) uses in-memory storage for simplicity:

```
python app.py
```

### Running with SQLite Database

For persistent storage, use the database implementation:

```
python app_with_db.py
```

This will create a SQLite database file `detector.db` in the application directory.

### Access the Application

Open a browser and navigate to:
- Local: http://127.0.0.1:5000
- Network (from other devices): http://[your-device-ip]:5000

### Default Credentials

- Admin: username `admin`, password `admin123`
- User: username `user`, password `user123`

## Application Structure

### Templates
- `base_dashboard.html` - Base template for all dashboards
- `admin_dashboard.html` - Admin interface with full controls
- `user_dashboard.html` - Standard user interface
- `login.html` - Authentication screen
- `register.html` - User registration screen
- `index.html` - Landing page

### Backend Implementation

#### In-Memory Version (`app.py`)
- Uses Python dictionaries and lists for storage
- Simple to set up, no dependencies beyond Flask
- Data is lost when the application restarts

#### Database Version (`app_with_db.py` + `models.py`)
- Uses SQLAlchemy ORM with SQLite database
- Persistent storage survives application restarts
- More scalable for production use
- Supports proper data relationships

### User Registration

New users can register directly through the registration form, or administrators can create accounts through the Admin dashboard.

## Configuring the Database

By default, the application uses SQLite. To use a different database:

1. Install the required driver:
   ```
   pip install psycopg2  # For PostgreSQL
   pip install pymysql   # For MySQL
   ```

2. Modify the database URI in `app_with_db.py`:
   ```python
   # PostgreSQL
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/detector'
   
   # MySQL
   app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/detector'
   ```

## Deployment

For production deployment:

1. Use a production WSGI server like Gunicorn:
   ```
   pip install gunicorn
   gunicorn app_with_db:app
   ```

2. Consider using a reverse proxy like Nginx for security and performance.

3. For HTTPS, set up SSL certificates with Let's Encrypt.

## License

MIT License

## Configuration

You can adjust the following parameters in the script:

- `CAMERA_ID`: Camera device ID (default is 0)
- `DISPLAY_WIDTH` and `DISPLAY_HEIGHT`: Display resolution
- `MIN_CONFIDENCE`: Minimum confidence threshold for OCR detection
- `SCAN_INTERVAL`: Time interval between OCR scans

## Troubleshooting

- If the camera doesn't work, try changing the `CAMERA_ID` value.
- For improved detection, ensure good lighting conditions.
- If text detection is poor, try adjusting the preprocessing parameters in the `preprocess_image` function.
- On Windows, if you get a "TesseractNotFoundError", make sure Tesseract is installed and the path is correctly set in the script.

## File Structure

```
postal_code_detector/
├── app.py                      # Main Flask application
├── app_with_db.py             # Flask app with database integration  
├── models.py                  # Database models
├── tunisia_postal_codes.py    # Tunisia postal codes data
├── static/
│   ├── style.css             # Custom CSS styles
│   └── script.js             # Frontend JavaScript
├── templates/
│   ├── base.html             # Base template
│   ├── index.html            # Landing page
│   ├── login.html            # Login page
│   ├── register.html         # Registration page
│   ├── admin_dashboard.html  # Admin interface
│   ├── user_dashboard.html   # User interface
│   └── profile.html          # User profile
└── requirements.txt          # Python dependencies
```
