#!/usr/bin/env python3
"""
DVR to DigitalOcean Spaces Uploader
Monitors the recordings directory and uploads completed DVR files to DigitalOcean Spaces
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
import requests
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables - Spaces
SPACES_REGION = os.getenv('SPACES_REGION', 'sgp1')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_ACCESS_KEY = os.getenv('SPACES_ACCESS_KEY')
SPACES_SECRET_KEY = os.getenv('SPACES_SECRET_KEY')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT', f'https://{SPACES_REGION}.digitaloceanspaces.com')
DELETE_AFTER_UPLOAD = os.getenv('DELETE_AFTER_UPLOAD', 'false').lower() == 'true'

# Environment variables - CDN
SPACES_CDN_ENABLED = os.getenv('SPACES_CDN_ENABLED', 'false').lower() == 'true'
SPACES_CDN_URL = os.getenv('SPACES_CDN_URL', '')

# Environment variables - Webhook
WEBHOOK_ENABLED = os.getenv('WEBHOOK_ENABLED', 'false').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')

RECORDINGS_DIR = Path('/recordings')
UPLOADED_DIR = Path('/uploaded')
UPLOAD_DELAY = 30  # Wait 30 seconds after file is modified before uploading

# Track files being monitored
file_timestamps = {}


class WebhookNotifier:
    """Send webhook notifications to Laravel API after upload"""
    
    def __init__(self):
        self.enabled = WEBHOOK_ENABLED
        self.url = WEBHOOK_URL
        self.secret = WEBHOOK_SECRET
        
        if not self.enabled:
            logger.info("Webhook notifications disabled")
        elif not self.url:
            logger.warning("Webhook enabled but URL not configured")
            self.enabled = False
        else:
            logger.info(f"Webhook notifications enabled: {self.url}")
    
    def notify(self, file_info: dict) -> bool:
        """Send webhook notification"""
        if not self.enabled:
            return False
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'DVR-Uploader/1.0'
            }
            
            # Add secret header if configured
            if self.secret:
                headers['X-Webhook-Secret'] = self.secret
            
            # Send POST request
            response = requests.post(
                self.url,
                json=file_info,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Webhook sent successfully: {file_info['filename']}")
                return True
            else:
                logger.warning(f"✗ Webhook failed (HTTP {response.status_code}): {file_info['filename']}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Webhook request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error sending webhook: {e}")
            return False


class S3Uploader:
    """Handle uploads to DigitalOcean Spaces using S3 API"""
    
    def __init__(self):
        if not all([SPACES_BUCKET, SPACES_ACCESS_KEY, SPACES_SECRET_KEY]):
            raise ValueError("Missing required environment variables: SPACES_BUCKET, SPACES_ACCESS_KEY, SPACES_SECRET_KEY")
        
        self.session = boto3.session.Session()
        self.client = self.session.client(
            's3',
            region_name=SPACES_REGION,
            endpoint_url=SPACES_ENDPOINT,
            aws_access_key_id=SPACES_ACCESS_KEY,
            aws_secret_access_key=SPACES_SECRET_KEY
        )
        self.bucket = SPACES_BUCKET
        logger.info(f"Initialized S3 client for bucket: {self.bucket} at {SPACES_ENDPOINT}")
    
    def upload_file(self, local_path: Path, s3_key: str) -> bool:
        """Upload a file to Spaces"""
        try:
            file_size = local_path.stat().st_size
            logger.info(f"Uploading {local_path.name} ({file_size / 1024 / 1024:.2f} MB) to s3://{self.bucket}/{s3_key}")
            
            self.client.upload_file(
                str(local_path),
                self.bucket,
                s3_key,
                ExtraArgs={'ACL': 'private'}
            )
            
            logger.info(f"✓ Successfully uploaded: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"✗ Failed to upload {local_path.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error uploading {local_path.name}: {e}")
            return False


class DVRFileHandler(FileSystemEventHandler):
    """Monitor DVR recordings and upload completed files"""
    
    def __init__(self, uploader: S3Uploader, webhook: WebhookNotifier):
        self.uploader = uploader
        self.webhook = webhook
        UPLOADED_DIR.mkdir(exist_ok=True)
    
    def on_created(self, event):
        """Track new files"""
        if event.is_directory or not event.src_path.endswith('.flv'):
            return
        
        file_path = Path(event.src_path)
        logger.info(f"New recording detected: {file_path.name}")
        file_timestamps[str(file_path)] = time.time()
    
    def on_modified(self, event):
        """Update timestamp when file is modified"""
        if event.is_directory or not event.src_path.endswith('.flv'):
            return
        
        file_path = Path(event.src_path)
        file_timestamps[str(file_path)] = time.time()
    
    def process_pending_uploads(self):
        """Check for files ready to upload"""
        current_time = time.time()
        files_to_upload = []
        
        for file_path_str, last_modified in list(file_timestamps.items()):
            if current_time - last_modified >= UPLOAD_DELAY:
                files_to_upload.append(file_path_str)
        
        for file_path_str in files_to_upload:
            self.upload_file(Path(file_path_str))
            del file_timestamps[file_path_str]
    
    def upload_file(self, file_path: Path):
        """Upload a completed DVR file"""
        if not file_path.exists():
            logger.warning(f"File no longer exists: {file_path}")
            return
        
        try:
            # Generate S3 key preserving directory structure
            relative_path = file_path.relative_to(RECORDINGS_DIR)
            s3_key = f"dvr/{relative_path.as_posix()}"
            
            # Get file info
            file_size = file_path.stat().st_size
            
            # Upload to Spaces
            success = self.uploader.upload_file(file_path, s3_key)
            
            if success:
                # Generate file URL
                if SPACES_CDN_ENABLED and SPACES_CDN_URL:
                    file_url = f"{SPACES_CDN_URL}/{s3_key}"
                else:
                    file_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{s3_key}"
                
                # Extract stream information from path
                # Path format: live/stream_name/timestamp.flv
                parts = relative_path.parts
                stream_app = parts[0] if len(parts) > 0 else 'unknown'
                stream_name = parts[1] if len(parts) > 1 else 'unknown'
                filename_timestamp = file_path.stem  # filename without extension
                
                # Prepare file info for webhook
                file_info = {
                    'filename': file_path.name,
                    'file_url': file_url,
                    'file_size': file_size,
                    'upload_time': datetime.now().isoformat(),
                    'stream_app': stream_app,
                    'stream_name': stream_name,
                    'timestamp': filename_timestamp,
                    'bucket': SPACES_BUCKET,
                    'region': SPACES_REGION
                }
                
                # Send webhook notification
                self.webhook.notify(file_info)
                
                # Create marker file in uploaded directory
                uploaded_marker = UPLOADED_DIR / relative_path.parent / f"{file_path.name}.uploaded"
                uploaded_marker.parent.mkdir(parents=True, exist_ok=True)
                marker_content = f"Uploaded at {datetime.now().isoformat()}\n"
                marker_content += f"URL: {file_url}\n"
                marker_content += f"Size: {file_size} bytes\n"
                uploaded_marker.write_text(marker_content)
                
                # Optionally delete local file after successful upload
                if DELETE_AFTER_UPLOAD:
                    logger.info(f"Deleting local file: {file_path.name}")
                    file_path.unlink()
                else:
                    logger.info(f"Keeping local file: {file_path.name}")
        
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")


def scan_existing_files(handler: DVRFileHandler):
    """Scan for existing DVR files that haven't been uploaded"""
    logger.info("Scanning for existing DVR files...")
    
    if not RECORDINGS_DIR.exists():
        logger.warning(f"Recordings directory does not exist: {RECORDINGS_DIR}")
        return
    
    uploaded_files = set()
    if UPLOADED_DIR.exists():
        for marker in UPLOADED_DIR.rglob('*.uploaded'):
            uploaded_files.add(marker.stem)
    
    # Scan all .flv files
    unuploaded_count = 0
    for flv_file in RECORDINGS_DIR.rglob('*.flv'):
        if flv_file.name not in uploaded_files:
            logger.info(f"Found unuploaded file: {flv_file.name} ({flv_file.stat().st_size / 1024 / 1024:.2f} MB)")
            handler.upload_file(flv_file)
            unuploaded_count += 1
    
    if unuploaded_count == 0:
        logger.info("No unuploaded files found")
    else:
        logger.info(f"Processed {unuploaded_count} unuploaded files")
    
    logger.info("Initial scan complete")


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("DVR to DigitalOcean Spaces Uploader")
    logger.info("=" * 60)
    logger.info(f"Monitoring: {RECORDINGS_DIR}")
    logger.info(f"Bucket: {SPACES_BUCKET}")
    logger.info(f"Region: {SPACES_REGION}")
    logger.info(f"Delete after upload: {DELETE_AFTER_UPLOAD}")
    logger.info(f"Webhook: {'Enabled' if WEBHOOK_ENABLED else 'Disabled'}")
    logger.info(f"CDN: {'Enabled' if SPACES_CDN_ENABLED else 'Disabled'}")
    logger.info("=" * 60)
    
    try:
        # Initialize uploader
        uploader = S3Uploader()
        
        # Initialize webhook notifier
        webhook = WebhookNotifier()
        
        # Create file system handler
        handler = DVRFileHandler(uploader, webhook)
        
        # Scan for existing files
        scan_existing_files(handler)
        
        # Start monitoring
        observer = Observer()
        observer.schedule(handler, str(RECORDINGS_DIR), recursive=True)
        observer.start()
        logger.info("Started monitoring for new recordings...")
        
        try:
            while True:
                time.sleep(5)
                handler.process_pending_uploads()
                
                # Every 5 minutes, rescan for missed files
                if hasattr(main, '_last_scan_time'):
                    if time.time() - main._last_scan_time > 300:  # 5 minutes
                        logger.info("Performing periodic rescan for missed files...")
                        scan_existing_files(handler)
                        main._last_scan_time = time.time()
                else:
                    main._last_scan_time = time.time()
                    
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            observer.stop()
        
        observer.join()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
