"""
Music Subscription App - Flask Backend
Handles login, register, main page, subscriptions, and music queries.
Connects to DynamoDB and S3 on AWS.
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Session secret key

# AWS config
REGION        = 'ap-southeast-2'
BUCKET_NAME   = 'zackiey-music-app-zack-2026' 
LOGIN_TABLE   = 'login'
MUSIC_TABLE   = 'music'
SUBS_TABLE    = 'subscriptions'

dynamodb = boto3.resource('dynamodb', region_name="ap-southeast-2")
s3_client = boto3.client('s3', region_name="ap-southeast-2")

login_table = dynamodb.Table(LOGIN_TABLE)
music_table = dynamodb.Table(MUSIC_TABLE)


def get_s3_image_url(filename):
    """Generate a pre-signed URL for secure S3 image access."""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f'images/{filename}'},
            ExpiresIn=3600
        )
        return url
    except ClientError:
        return ''


def get_subs_table():
    """Get or create the subscriptions table."""
    try:
        table = dynamodb.create_table(
            TableName=SUBS_TABLE,
            KeySchema=[
                {'AttributeName': 'email',       'KeyType': 'HASH'},
                {'AttributeName': 'title_album',  'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'email',       'AttributeType': 'S'},
                {'AttributeName': 'title_album', 'AttributeType': 'S'},
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        return table
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            return dynamodb.Table(SUBS_TABLE)
        raise


# Ensure subscriptions table exists on startup
subs_table = get_subs_table()


# ─── LOGIN ────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        try:
            response = login_table.get_item(Key={'email': email})
            user = response.get('Item')

            if user and user.get('password') == password:
                session['email']     = email
                session['user_name'] = user.get('user_name', email)
                return redirect(url_for('main'))
            else:
                error = 'email or password is invalid'
        except ClientError:
            error = 'email or password is invalid'

    return render_template('login.html', error=error)


# ─── REGISTER ─────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email     = request.form.get('email', '').strip()
        user_name = request.form.get('user_name', '').strip()
        password  = request.form.get('password', '').strip()

        try:
            response = login_table.get_item(Key={'email': email})
            if response.get('Item'):
                error = 'The email already exists'
            else:
                login_table.put_item(Item={
                    'email':     email,
                    'user_name': user_name,
                    'password':  password
                })
                return redirect(url_for('login'))
        except ClientError as e:
            error = f'Registration failed: {str(e)}'

    return render_template('register.html', error=error)


# ─── MAIN PAGE ────────────────────────────────────────────────────────────────

@app.route('/main')
def main():
    if 'email' not in session:
        return redirect(url_for('login'))

    # Load user's subscriptions
    try:
        response = subs_table.query(
            KeyConditionExpression=Key('email').eq(session['email'])
        )
        subscriptions = response.get('Items', [])
        # Add presigned image URLs
        for sub in subscriptions:
            img_filename = sub.get('img_url', '').split('/')[-1]
            sub['presigned_url'] = get_s3_image_url(img_filename)
    except ClientError:
        subscriptions = []

    return render_template('main.html',
                           user_name=session.get('user_name'),
                           subscriptions=subscriptions)


# ─── QUERY ────────────────────────────────────────────────────────────────────

@app.route('/query', methods=['POST'])
def query():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    title  = request.form.get('title',  '').strip()
    year   = request.form.get('year',   '').strip()
    artist = request.form.get('artist', '').strip()
    album  = request.form.get('album',  '').strip()

    # At least one field required
    if not any([title, year, artist, album]):
        return jsonify({'error': 'Please fill in at least one field'})

    try:
        filter_parts = []
        expr_values  = {}
        expr_names   = {}

        if title:
            filter_parts.append('contains(#t, :title)')
            expr_values[':title'] = title
            expr_names['#t']      = 'title'
        if year:
            filter_parts.append('#y = :year')
            expr_values[':year'] = year
            expr_names['#y']     = 'year'
        if artist:
            filter_parts.append('contains(#a, :artist)')
            expr_values[':artist'] = artist
            expr_names['#a']       = 'artist'
        if album:
            filter_parts.append('contains(#al, :album)')
            expr_values[':album'] = album
            expr_names['#al']     = 'album'

        filter_expr = ' AND '.join(filter_parts)

        # Use Query on GSI if only title provided, otherwise Scan
        if artist and not title and not year and not album:
            # Query by artist (partition key)
            response = music_table.query(
                KeyConditionExpression=Key('artist').eq(artist)
            )
            results = response.get('Items', [])
        elif artist and year and not title and not album:
            # Query using LSI: artist-year-index
            response = music_table.query(
                IndexName='artist-year-index',
                KeyConditionExpression=Key('artist').eq(artist) & Key('year').eq(year)
            )
            results = response.get('Items', [])
        elif title and not artist and not year and not album:
            # Query using GSI: title-artist-index
            response = music_table.query(
                IndexName='title-artist-index',
                KeyConditionExpression=Key('title').eq(title)
            )
            results = response.get('Items', [])
        else:
            # Scan with filters for multi-condition queries
            scan_kwargs = {
                'FilterExpression': filter_expr,
                'ExpressionAttributeValues': expr_values,
            }
            if expr_names:
                scan_kwargs['ExpressionAttributeNames'] = expr_names

            response = music_table.scan(**scan_kwargs)
            results  = response.get('Items', [])

        # Get user's current subscriptions to mark already-subscribed songs
        subs_response = subs_table.query(
            KeyConditionExpression=Key('email').eq(session['email'])
        )
        subscribed_keys = {
            item['title_album'] for item in subs_response.get('Items', [])
        }

        # Add presigned image URLs and subscription status
        for item in results:
            img_filename = item.get('img_url', '').split('/')[-1]
            item['presigned_url']  = get_s3_image_url(img_filename)
            item['is_subscribed']  = item.get('title_album', '') in subscribed_keys

        return jsonify({'results': results})

    except ClientError as e:
        return jsonify({'error': str(e)})


# ─── SUBSCRIBE ────────────────────────────────────────────────────────────────

@app.route('/subscribe', methods=['POST'])
def subscribe():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    try:
        subs_table.put_item(Item={
            'email':       session['email'],
            'title_album': data['title_album'],
            'title':       data['title'],
            'artist':      data['artist'],
            'album':       data['album'],
            'year':        data['year'],
            'img_url':     data['img_url'],
        })
        return jsonify({'success': True})
    except ClientError as e:
        return jsonify({'error': str(e)})


# ─── REMOVE SUBSCRIPTION ──────────────────────────────────────────────────────

@app.route('/unsubscribe', methods=['DELETE'])
def unsubscribe():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    try:
        subs_table.delete_item(Key={
            'email':      session['email'],
            'title_album': data['title_album'],
        })
        return jsonify({'success': True})
    except ClientError as e:
        return jsonify({'error': str(e)})


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
