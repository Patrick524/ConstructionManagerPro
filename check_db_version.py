
#!/usr/bin/env python3

from app import app, db
import sqlalchemy

def check_database_version():
    """Check the database version and SQLAlchemy version"""
    
    with app.app_context():
        try:
            # Get SQLAlchemy version
            print(f"SQLAlchemy version: {sqlalchemy.__version__}")
            
            # Get database engine info
            engine = db.engine
            print(f"Database URL: {engine.url}")
            print(f"Database dialect: {engine.dialect.name}")
            
            # Execute a version query based on the database type
            with engine.connect() as connection:
                if engine.dialect.name == 'sqlite':
                    result = connection.execute(db.text("SELECT sqlite_version()"))
                    version = result.fetchone()[0]
                    print(f"SQLite version: {version}")
                    
                elif engine.dialect.name == 'postgresql':
                    result = connection.execute(db.text("SELECT version()"))
                    version = result.fetchone()[0]
                    print(f"PostgreSQL version: {version}")
                    
                elif engine.dialect.name == 'mysql':
                    result = connection.execute(db.text("SELECT VERSION()"))
                    version = result.fetchone()[0]
                    print(f"MySQL version: {version}")
                    
                else:
                    print(f"Unknown database type: {engine.dialect.name}")
                    
        except Exception as e:
            print(f"Error checking database version: {e}")

if __name__ == "__main__":
    check_database_version()
