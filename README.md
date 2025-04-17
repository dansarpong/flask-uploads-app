# Flask File Storage Application with MySQL Database and AWS S3 Bucket

A Flask web application for uploading, storing, and managing files using AWS S3 bucket and MySQL database.

## Features

- Upload files to S3 bucket
- Store file metadata in MySQL database
- View/Download files via pre-signed URLs
- Delete files from S3 bucket and database
- Supports multiple file types (txt, pdf, png, jpg, jpeg, doc, docx)

## Prerequisites

- Python 3.10+
- MySQL database
- AWS S3 bucket with CORS configured
- AWS credentials

## Setup

1. Clone the repository:

```bash
git clone https://github.com/dansarpong/flask-uploads-app.git
cd flask-uploads-app
```

1. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Create `.env` file with the following variables:

```env
FLASK_SECRET_KEY=your_secret_key
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=your_aws_region
S3_BUCKET=your_bucket_name
MYSQL_HOST=localhost
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_database_name
MYSQL_PORT=3306
MAX_CONTENT_LENGTH=16777216  # 16MB max file size
```

1. Run the application:

```bash
flask run
```

## Usage

- Access the application at `http://localhost:5000`
- Upload files using the upload form
- View/Download files using the provided links
- Delete files using the delete button

## Security Features

- Secure filename handling
- File type validation
- Pre-signed URLs for secure file access
- Maximum file size limit
