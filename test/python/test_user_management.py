import unittest
import json
import os
import uuid
from unittest.mock import patch, MagicMock, Mock
import boto3

# Handle different moto versions for backward compatibility
try:
    from moto import mock_aws
    USE_MOCK_AWS = True
except ImportError:
    USE_MOCK_AWS = False
    try:
        from moto import mock_dynamodb2 as mock_dynamodb
    except ImportError:
        from moto import mock_dynamodb

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['USER_TABLE_NAME'] = 'test-users'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add source path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/user_management'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/layers/common/python'))

# Import the module to test
import user_management


if USE_MOCK_AWS:
    decorator = mock_aws
else:
    decorator = mock_dynamodb

@decorator
class TestUserManagement(unittest.TestCase):
    """Test cases for User Management Lambda function"""
    
    def setUp(self):
        """Test setup"""
        # Create DynamoDB table
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = self.dynamodb.create_table(
            TableName='test-users',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create test context
        self.context = Mock()
        self.context.request_id = 'test-request-id'
        self.context.function_name = 'test-user-management'
        self.context.get_remaining_time_in_millis = lambda: 300000

    def test_create_user_success(self):
        """Test successful user creation"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'Test User',
                'email': 'test@example.com',
                'phone': '123-456-7890',
                'department': 'Engineering'
            })
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'User created successfully')
        self.assertIn('user', body)
        self.assertEqual(body['user']['name'], 'Test User')
        self.assertEqual(body['user']['email'], 'test@example.com')
        self.assertEqual(body['user']['phone'], '123-456-7890')
        self.assertEqual(body['user']['department'], 'Engineering')
        self.assertEqual(body['user']['status'], 'active')
        self.assertIn('id', body['user'])
        self.assertIn('created_at', body['user'])
        self.assertIn('updated_at', body['user'])

    def test_create_user_invalid_data(self):
        """Test user creation with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'Test User',
                'email': 'invalid-email'
            })
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Invalid email format', body['error'])

    def test_create_user_missing_body(self):
        """Test user creation without body"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users'
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)

    def test_get_user_success(self):
        """Test successful user retrieval"""
        # First create a user
        user_id = str(uuid.uuid4())
        self.table.put_item(Item={
            'id': user_id,
            'name': 'Test User',
            'email': 'test@example.com',
            'status': 'active',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        })

        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': user_id}
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['user']['id'], user_id)
        self.assertEqual(body['user']['name'], 'Test User')
        self.assertEqual(body['user']['email'], 'test@example.com')

    def test_get_user_not_found(self):
        """Test user retrieval with non-existent ID"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': 'non-existent-id'}
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 404)

    def test_get_user_missing_id(self):
        """Test user retrieval without ID"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {}
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)

    def test_list_users_success(self):
        """Test successful user listing"""
        # Create test users
        users = [
            {
                'id': str(uuid.uuid4()),
                'name': f'Test User {i}',
                'email': f'test{i}@example.com',
                'status': 'active',
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
            for i in range(3)
        ]

        for user in users:
            self.table.put_item(Item=user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users'
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertIn('users', body)
        self.assertEqual(len(body['users']), 3)

    def test_list_users_with_limit(self):
        """Test user listing with limit parameter"""
        # Create test users
        users = [
            {
                'id': str(uuid.uuid4()),
                'name': f'Test User {i}',
                'email': f'test{i}@example.com',
                'status': 'active',
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
            for i in range(5)
        ]

        for user in users:
            self.table.put_item(Item=user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': {'limit': '2'}
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertIn('users', body)
        self.assertEqual(len(body['users']), 2)

    def test_invalid_resource(self):
        """Test invalid resource"""
        event = {
            'httpMethod': 'GET',
            'resource': '/invalid'
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 404)

    def test_cors_headers(self):
        """Test CORS headers are present"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users'
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertIn('headers', response)
        self.assertIn('Access-Control-Allow-Origin', response['headers'])

    def test_exception_handling(self):
        """Test exception handling"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': 'invalid json'
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)

    @patch('user_management.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp):
        """Test timestamp generation in user creation"""
        mock_timestamp.return_value = '2023-01-01T12:00:00Z'

        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'Test User',
                'email': 'test@example.com'
            })
        }

        response = user_management.lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['user']['created_at'], '2023-01-01T12:00:00Z')
        self.assertEqual(body['user']['updated_at'], '2023-01-01T12:00:00Z')


if __name__ == '__main__':
    unittest.main()