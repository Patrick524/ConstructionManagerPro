"""
Script to manually test the auto_clock_out_job function.
This is a one-time use test script to verify the function works properly.
"""
from app import app
from scheduler import auto_clock_out_job
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Print active sessions before running the job
with app.app_context():
    print("Running auto_clock_out_job test...")
    auto_clock_out_job()
    print("Test completed!")

print("Check the database to see if sessions older than 8 hours were closed.")