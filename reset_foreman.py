from app import app, db
from models import User
from werkzeug.security import generate_password_hash
from flask import Flask

with app.app_context():
    # Reset foreman password
    foreman = User.query.filter_by(email='foreman@example.com').first()
    if foreman:
        foreman.password_hash = generate_password_hash('password123')
        db.session.commit()
        print(f"Password reset for {foreman.name} ({foreman.email})")
    else:
        # Create foreman if not exists
        new_foreman = User(
            name="Mike Foreman",
            email="foreman@example.com",
            role="foreman"
        )
        new_foreman.password_hash = generate_password_hash('password123')
        db.session.add(new_foreman)
        db.session.commit()
        print(f"Created new foreman user: {new_foreman.email}")