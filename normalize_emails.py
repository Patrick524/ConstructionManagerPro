#!/usr/bin/env python3
"""
Script to normalize all existing email addresses to lowercase in the database.
This ensures consistency after implementing case-insensitive email login.
"""

from app import app, db
from models import User

def normalize_existing_emails():
    """Update all existing user emails to lowercase"""
    with app.app_context():
        try:
            # Get all users
            users = User.query.all()
            updated_count = 0
            
            print(f"Found {len(users)} users in database")
            
            for user in users:
                original_email = user.email
                normalized_email = original_email.lower()
                
                if original_email != normalized_email:
                    print(f"Updating email: {original_email} -> {normalized_email}")
                    user.email = normalized_email
                    updated_count += 1
                else:
                    print(f"Email already normalized: {original_email}")
            
            if updated_count > 0:
                db.session.commit()
                print(f"\nSuccessfully normalized {updated_count} email addresses")
            else:
                print("\nNo email addresses needed normalization")
                
        except Exception as e:
            print(f"Error normalizing emails: {e}")
            db.session.rollback()

if __name__ == "__main__":
    print("Starting email normalization...")
    normalize_existing_emails()
    print("Email normalization complete!")