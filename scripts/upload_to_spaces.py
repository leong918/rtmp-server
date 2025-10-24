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
import shutil
import subprocess

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

# Environment variables - FFmpeg
CONVERT_TO_MP4 = os.getenv('CONVERT_TO_MP4', 'false').lower() == 'true'
FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')

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


class VideoConverter:
    """Convert FLV files to MP4 using FFmpeg"""
    
    def __init__(self):
        self.ffmpeg_path = FFMPEG_PATH
        self.enabled = CONVERT_TO_MP4
        
        if self.enabled:
            # Check if FFmpeg is available
            if not shutil.which(self.ffmpeg_path):
                logger.error(f"FFmpeg not found at: {self.ffmpeg_path}")
                logger.error("Please install FFmpeg or set FFMPEG_PATH environment variable")
                self.enabled = False
            else:
                logger.info(f"FFmpeg found: {self.ffmpeg_path}")
                logger.info("FLV to MP4 conversion enabled")
        else:
            logger.info("FLV to MP4 conversion disabled")
    
    def convert_to_mp4(self, flv_path: Path) -> Optional[Path]:
        """Convert FLV file to MP4"""
        if not self.enabled:
            return None
        
        if not flv_path.exists():
            logger.error(f"FLV file not found: {flv_path}")
            return None
        
        # Generate MP4 output path
        mp4_path = flv_path.with_suffix('.mp4')
        
        try:
            logger.info(f"Converting {flv_path.name} to MP4...")
            
            # FFmpeg command to convert FLV to MP4
            # -i: input file
            # -c:v copy: copy video codec (fast, no re-encoding)
            # -c:a aac: convert audio to AAC
            # -movflags +faststart: optimize for web streaming
            cmd = [
                self.ffmpeg_path,
                '-i', str(flv_path),
                '-c:v', 'copy',  # Copy video stream (fast)
                '-c:a', 'aac',    # Convert audio to AAC
                '-strict', 'experimental',
                '-movflags', '+faststart',  # Optimize for streaming
                '-y',  # Overwrite output file if exists
                str(mp4_path)
            ]
            
            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0 and mp4_path.exists():
                mp4_size = mp4_path.stat().st_size
                flv_size = flv_path.stat().st_size
                logger.info(f"✓ Converted successfully: {mp4_path.name}")
                logger.info(f"  FLV size: {flv_size / 1024 / 1024:.2f} MB")
                logger.info(f"  MP4 size: {mp4_size / 1024 / 1024:.2f} MB")
                return mp4_path
            else:
                logger.error(f"✗ Conversion failed for {flv_path.name}")
                logger.error(f"FFmpeg output: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"✗ Conversion timeout for {flv_path.name}")
            return None
        except Exception as e:
            logger.error(f"✗ Conversion error for {flv_path.name}: {e}")
            return None


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
                ExtraArgs={'ACL': 'public-read'}
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
    
    def __init__(self, uploader: S3Uploader, webhook: WebhookNotifier, converter: VideoConverter):
        self.uploader = uploader
        self.webhook = webhook
        self.converter = converter
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
            # Convert FLV to MP4 if enabled
            upload_file = file_path
            original_file = file_path
            
            if file_path.suffix == '.flv' and self.converter.enabled:
                logger.info(f"Converting {file_path.name} to MP4...")
                mp4_file = self.converter.convert_to_mp4(file_path)
                
                if mp4_file:
                    upload_file = mp4_file
                    logger.info(f"Will upload MP4 version: {mp4_file.name}")
                else:
                    logger.warning(f"Conversion failed, will upload original FLV: {file_path.name}")
            
            # Generate S3 key preserving directory structure
            relative_path = upload_file.relative_to(RECORDINGS_DIR)
            s3_key = f"dvr/{relative_path.as_posix()}"
            
            # Get file info
            file_size = upload_file.stat().st_size
            
            # Upload to Spaces
            success = self.uploader.upload_file(upload_file, s3_key)
            
            if success:
                # Generate file URL
                if SPACES_CDN_ENABLED and SPACES_CDN_URL:
                    file_url = f"{SPACES_CDN_URL}/{s3_key}"
                else:
                    file_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{s3_key}"
                
                # Extract stream information from path
                # Path format: live/stream_name/timestamp.flv or timestamp.mp4
                parts = relative_path.parts
                stream_app = parts[0] if len(parts) > 0 else 'unknown'
                stream_name = parts[1] if len(parts) > 1 else 'unknown'
                filename_timestamp = upload_file.stem  # filename without extension
                
                # Prepare file info for webhook
                file_info = {
                    'filename': upload_file.name,
                    'original_filename': original_file.name,
                    'file_url': file_url,
                    'file_size': file_size,
                    'upload_time': datetime.now().isoformat(),
                    'stream_app': stream_app,
                    'stream_name': stream_name,
                    'timestamp': filename_timestamp,
                    'bucket': SPACES_BUCKET,
                    'region': SPACES_REGION,
                    'format': upload_file.suffix[1:]  # mp4 or flv
                }
                
                # Send webhook notification
                self.webhook.notify(file_info)
                
                # Create marker file in uploaded directory
                uploaded_marker = UPLOADED_DIR / relative_path.parent / f"{original_file.name}.uploaded"
                uploaded_marker.parent.mkdir(parents=True, exist_ok=True)
                marker_content = f"Uploaded at {datetime.now().isoformat()}\n"
                marker_content += f"Original: {original_file.name}\n"
                marker_content += f"Uploaded: {upload_file.name}\n"
                marker_content += f"URL: {file_url}\n"
                marker_content += f"Size: {file_size} bytes\n"
                marker_content += f"Format: {upload_file.suffix[1:]}\n"
                uploaded_marker.write_text(marker_content)
                
                # Optionally delete local files after successful upload
                if DELETE_AFTER_UPLOAD:
                    logger.info(f"Deleting local files...")
                    original_file.unlink()
                    if upload_file != original_file and upload_file.exists():
                        upload_file.unlink()
                else:
                    logger.info(f"Keeping local files")
                    # Clean up MP4 if we're keeping the original FLV
                    if upload_file != original_file and upload_file.exists() and original_file.suffix == '.flv':
                        logger.info(f"Cleaning up temporary MP4: {upload_file.name}")
                        upload_file.unlink()
        
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
        # Initialize video converter
        converter = VideoConverter()
        
        # Initialize uploader
        uploader = S3Uploader()
        
        # Initialize webhook notifier
        webhook = WebhookNotifier()
        
        # Create file system handler
        handler = DVRFileHandler(uploader, webhook, converter)
        
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
