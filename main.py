from app import app
from scheduler import init_scheduler
import atexit

# Initialize the scheduler
scheduler = init_scheduler()

# Register a function to shut down the scheduler when exiting
atexit.register(lambda: scheduler.shutdown(wait=False))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
