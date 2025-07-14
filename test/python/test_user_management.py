import json
import os
import pytest
import uuid
from unittest.mock import patch, MagicMock
import boto3

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
    context = MagicMock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-user-management'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-user-management'
    context.memory_limit_in_mb = 512
    context.get_remaining_time_in_millis.return_value = 30000
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
                'name': 'Test User',
                'email': 'test@example.com',
                'phone': '090-1234-5678',
                'department': 'Engineering'
            })
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['message'] == 'User created successfully'
        assert 'user' in body
        assert body['user']['name'] == 'Test User'
        assert body['user']['email'] == 'test@example.com'
        assert body['user']['phone'] == '090-1234-5678'
        assert body['user']['department'] == 'Engineering'
        assert body['user']['status'] == 'active'
        assert 'id' in body['user']
        assert 'created_at' in body['user']
        assert 'updated_at' in body['user']

    def test_create_user_invalid_data(self, dynamodb_table, lambda_context):
        """Test user creation with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': '',  # Invalid empty name
                'email': 'invalid-email'  # Invalid email format
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
        dynamodb_table.put_item(Item={
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

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'user' in body
        assert body['user']['id'] == user_id
        assert body['user']['name'] == 'Test User'
        assert body['user']['email'] == 'test@example.com'

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
        assert body['error'] == 'User ID is required'

    def test_list_users_success(self, dynamodb_table, lambda_context):
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
            dynamodb_table.put_item(Item=user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'users' in body
        assert 'count' in body
        assert body['count'] == 3
        assert len(body['users']) == 3

    def test_list_users_with_limit(self, dynamodb_table, lambda_context):
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
            dynamodb_table.put_item(Item=user)

        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': {'limit': '2'}
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'users' in body
        assert 'count' in body
        assert body['count'] == 2
        assert len(body['users']) == 2

    def test_invalid_resource(self, dynamodb_table, lambda_context):
        """Test invalid resource path"""
        event = {
            'httpMethod': 'GET',
            'resource': '/invalid-resource',
            'pathParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_cors_headers(self, dynamodb_table, lambda_context):
        """Test CORS headers in response"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': None
        }

        response = user_management.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers

    def test_exception_handling(self, lambda_context):
        """Test exception handling when DynamoDB is unavailable"""
        with patch('user_management.db_manager.put_item', side_effect=Exception('Database error')):
            event = {
                'httpMethod': 'POST',
                'resource': '/users',
                'body': json.dumps({
                    'name': 'Test User',
                    'email': 'test@example.com'
                })
            }

            response = user_management.lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['error'] == 'Failed to create user'

    @patch('user_management.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp, dynamodb_table, lambda_context):
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

        response = user_management.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['user']['created_at'] == '2023-01-01T12:00:00Z'
        assert body['user']['updated_at'] == '2023-01-01T12:00:00Z'
        assert mock_timestamp.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=user_management', '--cov-report=html'])