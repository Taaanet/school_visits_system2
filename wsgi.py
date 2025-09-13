import sys
import os

# Add your project directory to the Python path
path = '/home/yourusername/school_visits_system'
if path not in sys.path:
    sys.path.insert(0, path)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'your-production-secret-key'

# Import and run the Flask app
from app import app as application