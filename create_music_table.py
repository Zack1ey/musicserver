"""
Script 2 & 3: Create the music DynamoDB table and load songs from 2026a2_songs.json.
Run this on your EC2 instance with: python3 create_music_table.py

KEY SCHEMA DESIGN RATIONALE:
- Partition Key: artist (String)
- Sort Key:      title  (String)

Why this design?
- The dataset contains duplicate song titles across different artists
  e.g. "Bad Blood" exists for both Taylor Swift AND Kendrick Lamar.
  Using title alone as PK would cause one record to overwrite the other.
- The dataset also contains duplicate titles by the SAME artist in different albums
  e.g. "Delicate" by Taylor Swift appears in two albums (different years).
  To handle this, we append the album to the sort key: "title#album"
  This ensures every record is unique with no data loss.

Final Key Design:
- PK: artist
- SK: title#album  (e.g. "Delicate#Reputation" vs "Delicate#Reputation (Deluxe)")

GSI - title-artist-index:
- PK: title   (allows querying by song title across all artists)
- SK: artist

LSI - artist-year-index:
- PK: artist  (same as table PK - required for LSI)
- SK: year    (allows querying all songs by an artist filtered by year)
"""

import boto3
import json
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')

TABLE_NAME = 'music'
JSON_FILE  = '2026a2_songs.json'


def create_music_table():
    """
    Create the music table with:
    - Partition Key: artist
    - Sort Key:      title_album (title#album composite)
    - GSI on title for querying by song title
    - LSI on year for querying by artist + year
    """
    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'artist',      'KeyType': 'HASH'},   # Partition key
                {'AttributeName': 'title_album', 'KeyType': 'RANGE'},  # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'artist',      'AttributeType': 'S'},
                {'AttributeName': 'title_album', 'AttributeType': 'S'},
                {'AttributeName': 'title',       'AttributeType': 'S'},
                {'AttributeName': 'year',        'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[
                {
                    # GSI: query songs by title (e.g. find all artists who made "Bad Blood")
                    'IndexName': 'title-artist-index',
                    'KeySchema': [
                        {'AttributeName': 'title',  'KeyType': 'HASH'},
                        {'AttributeName': 'artist', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                }
            ],
            LocalSecondaryIndexes=[
                {
                    # LSI: query by artist + year (e.g. "Jimmy Buffett songs from 1974")
                    'IndexName': 'artist-year-index',
                    'KeySchema': [
                        {'AttributeName': 'artist', 'KeyType': 'HASH'},
                        {'AttributeName': 'year',   'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Creating table '{TABLE_NAME}'... please wait.")
        table.wait_until_exists()
        print(f"Table '{TABLE_NAME}' created successfully.")
        return table
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table '{TABLE_NAME}' already exists. Using existing table.")
            return dynamodb.Table(TABLE_NAME)
        else:
            raise


def load_songs(table):
    """Load all songs from 2026a2_songs.json into the music table."""
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)

    songs = data['songs']
    print(f"Loading {len(songs)} songs into '{TABLE_NAME}' table...")

    loaded = 0
    for song in songs:
        # Composite sort key: "title#album" ensures uniqueness
        # e.g. "Delicate#Reputation" vs "Delicate#Reputation (Deluxe)"
        title_album = f"{song['title']}#{song['album']}"

        item = {
            'artist':      song['artist'],
            'title_album': title_album,       # Sort key (composite)
            'title':       song['title'],     # Stored separately for GSI + display
            'album':       song['album'],
            'year':        song['year'],
            'img_url':     song['img_url'],
        }

        table.put_item(Item=item)
        loaded += 1
        print(f"  [{loaded}/{len(songs)}] {song['artist']} - {song['title']} ({song['album']})")

    print(f"\nDone! {loaded} songs loaded successfully.")


if __name__ == '__main__':
    table = create_music_table()
    load_songs(table)
