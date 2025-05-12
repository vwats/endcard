
from app import app
import routes  # Import routes to register them with the app
import signal
import sys

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    ports = [5000, 5001, 5002, 5003]
    for port in ports:
        try:
            app.run(host="0.0.0.0", port=port, debug=True)
            break
        except OSError as e:
            if port == ports[-1]:
                print(f"All ports {ports} are in use. Please free up one of these ports.")
                sys.exit(1)
            print(f"Port {port} is in use, trying next port...")
            continue
        except Exception as e:
            print(f"Error starting server: {e}")
            sys.exit(1)
