import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from database import db, FileMetadata
from datetime import datetime, timezone
import MySQLdb
import requests



def get_ssm_parameter(param_name):
    response = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
    return response['Parameter']['Value']

def get_aws_region():
    """
    Fetches the current EC2 instance's AWS region using IMDSv2
    Returns region string or None if not running on EC2
    """
    token_url = "http://169.254.169.254/latest/api/token"
    metadata_url = "http://169.254.169.254/latest/meta-data/placement/availability-zone"
    
    try:
        # Get IMDSv2 token
        token_response = requests.put(
            token_url,
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2
        )
        token_response.raise_for_status()
        
        # Get availability zone with token
        headers = {"X-aws-ec2-metadata-token": token_response.text}
        az_response = requests.get(metadata_url, headers=headers, timeout=2)
        az_response.raise_for_status()
        
        # Remove last character to get region
        return az_response.text[:-1]
        
    except requests.exceptions.RequestException as e:
        # Fallback to IMDSv1 if IMDSv2 fails
        try:
            az_response = requests.get(metadata_url, timeout=2)
            az_response.raise_for_status()
            return az_response.text[:-1]
        except requests.exceptions.RequestException:
            return None

AWS_REGION = get_aws_region()
if not AWS_REGION:
    raise ValueError("AWS_REGION is not found")

ssm_client = boto3.client('ssm', region_name=AWS_REGION)
rds_client = boto3.client('rds', region_name=AWS_REGION)
if AWS_REGION == 'eu-west-1':
    S3_BUCKET = get_ssm_parameter('primary_bucket_name')
    MYSQL_NAME = get_ssm_parameter('primary_rds_name')

else:
    S3_BUCKET = get_ssm_parameter('dr_bucket_name')
    MYSQL_NAME = get_ssm_parameter('dr_rds_name')

MYSQL_USER = get_ssm_parameter('db_username')
MYSQL_PASSWORD = get_ssm_parameter('db_password')
MYSQL_DATABASE = get_ssm_parameter('db_name')

MYSQL_DETAILS = rds_client.describe_db_instances(DBInstanceIdentifier=MYSQL_NAME)
MYSQL_HOST = MYSQL_DETAILS['DBInstances'][0]['Endpoint']['Address']
MYSQL_PORT = MYSQL_DETAILS['DBInstances'][0]['Endpoint']['Port']

MAX_CONTENT_LENGTH=16777216  # 16MB in bytes



def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    try:
        # Connect to MySQL without specifying a database
        connection = MySQLdb.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            passwd=MYSQL_PASSWORD,
            port=MYSQL_PORT
        )
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        database_name = MYSQL_DATABASE
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
        
        connection.close()
        print(f"Database '{database_name}' created or already exists")
    except Exception as e:
        print(f"Error creating database: {e}")
        raise

def create_app():
    # Create database first
    create_database_if_not_exists()
    
    app = Flask(__name__)

    # Configuration from environment variables
    app.config['SECRET_KEY'] = 'dev-secret-key'  # Replace with SSM parameter in production
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Database configuration
    db_uri = (
        f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@"
        f"{MYSQL_HOST}:{MYSQL_PORT}/"
        f"{MYSQL_DATABASE}"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        db.create_all()  # Create database tables

    return app

app = create_app()


# Initialize AWS S3 client
s3_client = boto3.client(
    's3',
    region_name=AWS_REGION
)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_presigned_url(key):
    """
    Generate a pre-signed URL for an existing S3 object
    """
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        return url
    except ClientError as e:
        print(f"Error generating pre-signed URL: {e}")
        return None

def upload_file_to_s3(file, filename):
    """
    Upload a file to S3 bucket and generate a pre-signed URL
    """
    try:
        s3_client.upload_fileobj(
            file,
            S3_BUCKET,
            filename,
            ExtraArgs={
                "ContentType": file.content_type
            }
        )
        return generate_presigned_url(filename)
    except ClientError as e:
        print(f"Error uploading file to S3: {e}")
        return None

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):  # Add file_id parameter here
    try:
        # Get file from database
        file = FileMetadata.query.get_or_404(file_id)
        
        # Delete from S3
        try:
            s3_client.delete_object(
                Bucket=S3_BUCKET,
                Key=file.filename
            )
        except ClientError as e:
            print(f"Error deleting file from S3: {e}")
            flash('Error deleting file from S3')
            return redirect(url_for('index'))
        
        # Delete from database
        db.session.delete(file)
        db.session.commit()
        
        flash('File successfully deleted')
    except Exception as e:
        print(f"Error deleting file: {e}")
        flash('Error deleting file')
        
    return redirect(url_for('index'))

@app.route('/')
def index():
    # Get files sorted by upload_date in descending order (most recent first)
    files = FileMetadata.query.order_by(FileMetadata.upload_date.desc()).all()
    # Generate fresh pre-signed URLs for all files
    for file in files:
        file.s3_url = generate_presigned_url(file.filename)
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer to beginning
        
        # Upload to S3
        s3_url = upload_file_to_s3(file, filename)
        if not s3_url:
            flash('Error uploading file to S3')
            return redirect(url_for('index'))
        
        # Save metadata to RDS
        file_metadata = FileMetadata(
            filename=filename,
            original_filename=file.filename,
            mime_type=file.content_type,
            size=file_size,  # Use the calculated file size
            upload_date=datetime.now(timezone.utc),
            s3_url=s3_url
        )
        db.session.add(file_metadata)
        db.session.commit()
        
        flash('File successfully uploaded')
        return redirect(url_for('index'))
    
    flash('Invalid file type')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
