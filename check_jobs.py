from app import app, db
from models import Job

with app.app_context():
    print('Available jobs:')
    for job in Job.query.all():
        print(f'ID: {job.id}, Code: {job.job_code}, Location: {job.location}')