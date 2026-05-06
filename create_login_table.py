"""
Script 1: Create and populate the login DynamoDB table with 10 users.
Run this on your EC2 instance with: python3 create_login_table.py
"""

import boto3
from botocore.exceptions import ClientError

# Connect to DynamoDB - uses the EC2 instance's IAM role (LabRole) automatically
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
client = boto3.client('dynamodb', region_name='ap-southeast-2')

TABLE_NAME = 'login'

def create_login_table():
    """Create the login table with email as partition key."""
    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'email', 'KeyType': 'HASH'},  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'email', 'AttributeType': 'S'},
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

def populate_login_table(table):
    """Insert 10 user records into the login table."""
    users = [
        {'email': 's3910000@student.rmit.edu.au', 'user_name': 'Olivia', 'password': 'Olivia001'},
        {'email': 's3920000@student.rmit.edu.au', 'user_name': 'Noah',   'password': 'Noah002'},
        {'email': 's3930000@student.rmit.edu.au', 'user_name': 'Emma',   'password': 'Emma003'},
        {'email': 's3940000@student.rmit.edu.au', 'user_name': 'Liam',   'password': 'Liam004'},
        {'email': 's3950000@student.rmit.edu.au', 'user_name': 'Ava',    'password': 'Ava005'},
        {'email': 's3960000@student.rmit.edu.au', 'user_name': 'William','password': 'William006'},
        {'email': 's3970000@student.rmit.edu.au', 'user_name': 'Sophia', 'password': 'Sophia007'},
        {'email': 's3980000@student.rmit.edu.au', 'user_name': 'James',  'password': 'James008'},
        {'email': 's3990000@student.rmit.edu.au', 'user_name': 'Isabella','password': 'Isabella009'},
        {'email': 's4000000@student.rmit.edu.au', 'user_name': 'Oliver', 'password': 'Oliver010'},
    ]

    print("Inserting 10 users into login table...")
    for user in users:
        table.put_item(Item=user)
        print(f"  Inserted: {user['email']} / {user['user_name']}")

    print("All 10 users inserted successfully.")

if __name__ == '__main__':
    table = create_login_table()
    populate_login_table(table)
