from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class FileMetadata(db.Model):
    __tablename__ = 'file_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(datetime.timezone.utc))
    s3_url = db.Column(db.String(1000), nullable=False)
    
    def __repr__(self):
        return f'<FileMetadata {self.filename}>'
