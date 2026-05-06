"""
Script 4: Download artist images from img_url values in 2026a2_songs.json
and upload them to an S3 bucket.

Run with: python3 upload_images_s3.py

BEFORE RUNNING:
1. Create an S3 bucket in the AWS console first
2. Update BUCKET_NAME below with your bucket name
3. Make sure your EC2 has the LabRole attached (it should by default in AWS Academy)
"""

import boto3
import json
import os
import urllib.request
from botocore.exceptions import ClientError

# ---------------------------------------------------------------
# UPDATE THIS with your actual S3 bucket name
BUCKET_NAME = 'zackiey-music-app-zack-2026'
# ---------------------------------------------------------------

JSON_FILE  = '2026a2_songs.json'
IMG_FOLDER = 'artist_images'  # local temp folder

s3 = boto3.client('s3', region_name='ap-southeast-2')


def download_images(songs):
    """Download each unique artist image to a local folder."""
    os.makedirs(IMG_FOLDER, exist_ok=True)

    seen_urls = {}
    for song in songs:
        url = song['img_url']
        if url in seen_urls:
            continue  # already downloaded this artist image

        # Extract filename from URL e.g. "TaylorSwift.jpg"
        filename = url.split('/')[-1]
        local_path = os.path.join(IMG_FOLDER, filename)

        if os.path.exists(local_path):
            print(f"  Already exists locally: {filename}")
        else:
            print(f"  Downloading: {filename}")
            urllib.request.urlretrieve(url, local_path)

        seen_urls[url] = filename

    print(f"\nDownloaded {len(seen_urls)} unique artist images.\n")
    return seen_urls


def upload_to_s3(seen_urls):
    """Upload all downloaded images to S3."""
    print(f"Uploading images to S3 bucket: {BUCKET_NAME}")

    uploaded = 0
    for url, filename in seen_urls.items():
        local_path = os.path.join(IMG_FOLDER, filename)
        s3_key = f"images/{filename}"

        try:
            s3.upload_file(
                local_path,
                BUCKET_NAME,
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
            print(f"  Uploaded: s3://{BUCKET_NAME}/{s3_key}")
            uploaded += 1
        except ClientError as e:
            print(f"  ERROR uploading {filename}: {e}")

    print(f"\nDone! {uploaded} images uploaded to S3.")


def generate_s3_urls(seen_urls):
    """
    Print the S3 URL format for each image.
    Your app should use pre-signed URLs to access these securely.
    """
    print("\n--- S3 Image Keys (use these in your app) ---")
    for url, filename in seen_urls.items():
        s3_key = f"images/{filename}"
        print(f"  {filename}: {s3_key}")


if __name__ == '__main__':
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)

    songs = data['songs']
    seen_urls = download_images(songs)
    upload_to_s3(seen_urls)
    generate_s3_urls(seen_urls)
