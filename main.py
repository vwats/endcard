
from app import app
import routes  # Import routes to register them with the app
import signal
import sys

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# When using Gunicorn, we don't need to run the app directly
app = app  # This makes the app importable by Gunicorn
