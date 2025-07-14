import json
import os
import pytest
import uuid
from unittest.mock import Mock
import boto3
from moto import mock_aws

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['USER_TABLE_NAME'] = 'test-users'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add source path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/user_management'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/layers/common/python'))

# Import the module to test
import user_management


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = Mock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-user-management'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-user-management'
    context.memory_limit_in_mb = 512
    context.get_remaining_time_in_millis = Mock(return_value=30000)
    return context


@pytest.fixture
def dynamodb_table(dynamodb_resource):
    """Create a mock DynamoDB table"""
    table = dynamodb_resource.create_table(
        TableName='test-users',
        KeySchema=[
            {
                'AttributeName': 'id',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'id',
                'AttributeType': 'S'
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Wait for table to be created
    table.wait_until_exists()
    
    return table
class TestUserManagement:
    """Test cases for User Management Lambda function"""

    def test_create_user_success(self, dynamodb_table, lambda_context):
        """Test successful user creation"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'username': 'testuser',
                'email': 'test@example.com',
                'phone': '+81-90-1234-5678'
            })
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['message'] == 'User created successfully'
        assert 'user' in body
        assert body['user']['username'] == 'testuser'
        assert body['user']['email'] == 'test@example.com'
        assert 'id' in body['user']

    def test_create_user_invalid_data(self, dynamodb_table, lambda_context):
        """Test user creation with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'username': '',  # Empty username
                'email': 'invalid-email',  # Invalid email
                'phone': 'invalid-phone'  # Invalid phone
            })
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_create_user_missing_body(self, dynamodb_table, lambda_context):
        """Test user creation with missing body"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_get_user_success(self, dynamodb_table, lambda_context):
        """Test successful user retrieval"""
        # First create a user
        user_id = str(uuid.uuid4())
        test_user = {
            'id': user_id,
            'username': 'testuser',
            'email': 'test@example.com',
            'phone': '+81-90-1234-5678',
            'created_at': '2023-01-01T12:00:00Z'
        }
        dynamodb_table.put_item(Item=test_user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': user_id}
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['user']['id'] == user_id
        assert body['user']['username'] == 'testuser'

    def test_get_user_not_found(self, dynamodb_table, lambda_context):
        """Test user retrieval with non-existent ID"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': 'non-existent-id'}
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'User not found'

    def test_get_user_missing_id(self, dynamodb_table, lambda_context):
        """Test user retrieval with missing ID"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_list_users_success(self, dynamodb_table, lambda_context):
        """Test successful user listing"""
        # Create test users
        for i in range(3):
            test_user = {
                'id': str(uuid.uuid4()),
                'username': f'testuser{i}',
                'email': f'test{i}@example.com',
                'phone': '+81-90-1234-567' + str(i),
                'created_at': '2023-01-01T12:00:00Z'
            }
            dynamodb_table.put_item(Item=test_user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'users' in body
        assert len(body['users']) >= 3

    def test_list_users_with_limit(self, dynamodb_table, lambda_context):
        """Test user listing with limit parameter"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': {'limit': '2'}
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'users' in body

    def test_invalid_resource(self, dynamodb_table, lambda_context):
        """Test invalid resource path"""
        event = {
            'httpMethod': 'GET',
            'resource': '/invalid',
            'pathParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_cors_headers(self, dynamodb_table, lambda_context):
        """Test CORS headers in response"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'username': 'testuser',
                'email': 'test@example.com',
                'phone': '+81-90-1234-5678'
            })
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])