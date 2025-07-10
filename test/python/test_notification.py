import json
import os
import pytest
import uuid
from unittest.mock import patch, MagicMock
from moto import mock_dynamodb, mock_sns
import boto3

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['NOTIFICATION_TABLE_NAME'] = 'test-notifications'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-notifications'
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
    
    yield table


@pytest.fixture
@mock_sns
def sns_topic():
    """Create a mock SNS topic"""
    sns = boto3.client('sns', region_name='us-east-1')
    response = sns.create_topic(Name='test-notifications')
    topic_arn = response['TopicArn']
    yield sns, topic_arn


class TestNotification:
    """Test cases for Notification Lambda function"""

    def test_send_notification_api_success(self, dynamodb_table, sns_topic, lambda_context):
        """Test successful notification sending via API"""
        sns_client, topic_arn = sns_topic
        
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'test@example.com',
                'message': 'Test notification message',
                'type': 'email',
                'subject': 'Test Subject'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Notification sent successfully'
        assert 'notification' in body
        assert body['notification']['recipient'] == 'test@example.com'
        assert body['notification']['type'] == 'email'
        assert body['notification']['status'] == 'sent'
        assert 'id' in body['notification']

    def test_send_notification_api_invalid_data(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification sending with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': '',  # Empty recipient
                'message': '',    # Empty message
                'type': 'invalid' # Invalid type
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_sns_event_processing(self, dynamodb_table, lambda_context):
        """Test SNS event processing"""
        sns_event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-notifications',
                        'Message': json.dumps({
                            'recipient': 'test@example.com',
                            'message': 'SNS triggered notification',
                            'type': 'email'
                        }),
                        'Subject': 'Test SNS Notification',
                        'MessageId': 'test-message-id'
                    }
                }
            ]
        }

        response = notification.lambda_handler(sns_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'SNS event processed successfully'
        assert 'processed_records' in body
        assert body['processed_records'] == 1

    def test_email_notification(self, dynamodb_table, sns_topic, lambda_context):
        """Test email notification processing"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'user@example.com',
                'message': 'This is an email notification',
                'type': 'email',
                'subject': 'Important Email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['notification']['type'] == 'email'
        assert body['notification']['recipient'] == 'user@example.com'
        assert body['notification']['subject'] == 'Important Email'

    def test_sms_notification(self, dynamodb_table, sns_topic, lambda_context):
        """Test SMS notification processing"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': '+1234567890',
                'message': 'This is an SMS notification',
                'type': 'sms'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['notification']['type'] == 'sms'
        assert body['notification']['recipient'] == '+1234567890'

    def test_invalid_recipient_email(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification with invalid email format"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'invalid-email-format',
                'message': 'Test message',
                'type': 'email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_invalid_recipient_phone(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification with invalid phone format"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'invalid-phone',
                'message': 'Test message',
                'type': 'sms'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_missing_body(self, dynamodb_table, lambda_context):
        """Test API request with missing body"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': None
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_invalid_request_method(self, dynamodb_table, lambda_context):
        """Test invalid HTTP method"""
        event = {
            'httpMethod': 'GET',
            'resource': '/notify',
            'body': json.dumps({'recipient': 'test@example.com', 'message': 'test'})
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_cors_headers(self, dynamodb_table, sns_topic, lambda_context):
        """Test CORS headers in response"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'test@example.com',
                'message': 'Test message',
                'type': 'email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'

    def test_exception_handling(self, lambda_context):
        """Test exception handling when services are unavailable"""
        with patch('notification.db_manager.put_item', side_effect=Exception('Database error')):
            event = {
                'httpMethod': 'POST',
                'resource': '/notify',
                'body': json.dumps({
                    'recipient': 'test@example.com',
                    'message': 'Test message',
                    'type': 'email'
                })
            }

            response = notification.lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['error'] == 'Failed to send notification'

    @patch('notification.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp, dynamodb_table, sns_topic, lambda_context):
        """Test timestamp generation in notification"""
        mock_timestamp.return_value = '2023-01-01T12:00:00Z'
        
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'test@example.com',
                'message': 'Test message',
                'type': 'email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['notification']['sent_at'] == '2023-01-01T12:00:00Z'
        assert mock_timestamp.call_count >= 1

    def test_multiple_sns_records(self, dynamodb_table, lambda_context):
        """Test processing multiple SNS records in one event"""
        sns_event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-notifications',
                        'Message': json.dumps({
                            'recipient': 'user1@example.com',
                            'message': 'Message 1',
                            'type': 'email'
                        }),
                        'MessageId': 'message-1'
                    }
                },
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-notifications',
                        'Message': json.dumps({
                            'recipient': 'user2@example.com',
                            'message': 'Message 2',
                            'type': 'email'
                        }),
                        'MessageId': 'message-2'
                    }
                }
            ]
        }

        response = notification.lambda_handler(sns_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_records'] == 2

    def test_notification_priority(self, dynamodb_table, sns_topic, lambda_context):
        """Test notification with priority setting"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'urgent@example.com',
                'message': 'Urgent notification',
                'type': 'email',
                'priority': 'high',
                'subject': 'URGENT: Action Required'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['notification']['priority'] == 'high'

    @patch('notification.sns_client.publish')
    def test_sns_publish_error(self, mock_publish, dynamodb_table, lambda_context):
        """Test SNS publish error handling"""
        mock_publish.side_effect = Exception('SNS publish failed')
        
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'test@example.com',
                'message': 'Test message',
                'type': 'email'
            })
        }

        response = notification.lambda_handler(event, lambda_context)
        
        # Should handle error gracefully
        assert response['statusCode'] in [200, 500]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=notification', '--cov-report=html'])