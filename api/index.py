import sys
import os

# Add parent directory to path so app can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Expose app for Vercel serverless
# Vercel's Python runtime will invoke the WSGI app directly
