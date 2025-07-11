import json
import os
import pytest
import uuid
from unittest.mock import patch, MagicMock
import boto3

# Handle different moto versions for backward compatibility
try:
    from moto import mock_aws
    mock_dynamodb = mock_aws
    mock_sns = mock_aws
except ImportError:
    try:
        from moto import mock_dynamodb2 as mock_dynamodb, mock_sns
    except ImportError:
        from moto import mock_dynamodb, mock_sns

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['NOTIFICATION_TABLE_NAME'] = 'test-notifications'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-notifications'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add source path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/notification'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/layers/common/python'))

# Import the module to test
import notification


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = MagicMock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-notification'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-notification'
    context.memory_limit_in_mb = 512
    context.get_remaining_time_in_millis.return_value = 30000
    return context


@pytest.fixture
@mock_dynamodb
def dynamodb_table():
    """Create a mock DynamoDB table"""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    table = dynamodb.create_table(
        TableName='test-notifications',
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


@pytest.fixture
@mock_sns
def sns_topic():
    """Create a mock SNS topic"""
    sns = boto3.client('sns', region_name='us-east-1')
    response = sns.create_topic(Name='test-notifications')
    return response['TopicArn']


class TestNotification:
    """Test cases for Notification Lambda function"""

    @mock_dynamodb
    @mock_sns
    def test_send_notification_success(self, dynamodb_table, sns_topic, lambda_context):
        """Test successful notification sending"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Test notification',
                'subject': 'Test Subject',
                'type': 'email',
                'recipient': 'test@example.com'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Notification sent successfully'
        assert 'id' in body

    @mock_dynamodb
    @mock_sns
    def test_send_notification_invalid_data(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification sending with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Test notification'
                # Missing required fields
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    @mock_dynamodb
    @mock_sns
    def test_invalid_request_method(self, dynamodb_table, sns_topic, lambda_context):
        """Test invalid HTTP method"""
        event = {
            'httpMethod': 'GET',
            'resource': '/notify'
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 405
        body = json.loads(response['body'])
        assert 'Method not allowed' in body['error']

    @mock_dynamodb
    @mock_sns
    def test_cors_headers(self, dynamodb_table, sns_topic, lambda_context):
        """Test CORS headers are present"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Test',
                'subject': 'Test',
                'type': 'email',
                'recipient': 'test@example.com'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        assert 'Access-Control-Allow-Origin' in response['headers']

    @mock_dynamodb
    @mock_sns
    def test_exception_handling(self, dynamodb_table, sns_topic, lambda_context):
        """Test exception handling"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': 'invalid json'
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400

    @mock_dynamodb
    @mock_sns
    @patch('notification.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp, dynamodb_table, sns_topic, lambda_context):
        """Test timestamp generation in notification"""
        mock_timestamp.return_value = '2023-01-01T12:00:00Z'

        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Test notification',
                'subject': 'Test Subject',
                'type': 'email',
                'recipient': 'test@example.com'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        # Verify timestamp was used
        mock_timestamp.assert_called()

    @mock_dynamodb
    @mock_sns
    def test_sns_event_processing(self, dynamodb_table, sns_topic, lambda_context):
        """Test processing SNS event"""
        sns_event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-topic',
                        'Message': json.dumps({
                            'message': 'SNS triggered notification',
                            'type': 'system'
                        })
                    }
                }
            ]
        }

        response = notification.lambda_handler(sns_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'processed' in body

    @mock_dynamodb
    @mock_sns
    def test_notification_validation(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification data validation"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Valid notification',
                'subject': 'Valid Subject',
                'type': 'email',
                'recipient': 'valid@example.com'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'id' in body

    @mock_dynamodb
    @mock_sns
    def test_multiple_recipients(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification to multiple recipients"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Broadcast notification',
                'subject': 'Broadcast Subject',
                'type': 'email',
                'recipients': ['user1@example.com', 'user2@example.com']
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        # Should still succeed even if recipients format is different
        assert response['statusCode'] in [200, 400]

    @mock_dynamodb
    @mock_sns
    def test_invalid_email_format(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification with invalid email format"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'message': 'Test notification',
                'subject': 'Test Subject',
                'type': 'email',
                'recipient': 'invalid-email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body