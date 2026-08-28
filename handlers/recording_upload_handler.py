import os
import boto3
from botocore.client import Config
from services.logger_service import logger
from config.settings import settings

# Initialize S3/MinIO Client
s3_client = boto3.client(
    's3',
    endpoint_url=settings.MINIO_ENDPOINT_URL,
    aws_access_key_id=settings.MINIO_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

def upload_to_minio_and_cleanup(local_path: str, bucket_name: str, object_name: str):
    """Background task to upload audio recording to MinIO and delete local copy."""
    try:
        if os.path.exists(local_path):
            s3_client.upload_file(local_path, bucket_name, object_name)
            logger.info(f"Successfully uploaded {local_path} to MinIO ({bucket_name}/{object_name})")
            os.remove(local_path)
        else:
            logger.warning(f"File not found for MinIO upload: {local_path}")
    except Exception:
        logger.exception(f"Failed to upload {local_path} to MinIO")