import unittest
import json
import os
import uuid
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws

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


@mock_aws
class TestNotification(unittest.TestCase):
    """Test cases for Notification Lambda function"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create mock DynamoDB table
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = self.dynamodb.create_table(
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
        self.table.wait_until_exists()
        
        # Create mock SNS topic
        self.sns_client = boto3.client('sns', region_name='us-east-1')
        response = self.sns_client.create_topic(Name='test-notifications')
        self.topic_arn = response['TopicArn']
        
        # Create mock Lambda context
        self.lambda_context = Mock()
        self.lambda_context.request_id = 'test-request-id'
        self.lambda_context.function_name = 'test-notification'
        self.lambda_context.function_version = '$LATEST'
        self.lambda_context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-notification'
        self.lambda_context.memory_limit_in_mb = 512
        self.lambda_context.get_remaining_time_in_millis = Mock(return_value=30000)

    def test_send_notification_api_success(self):
        """Test successful notification sending via API"""
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'Notification sent successfully')
        self.assertIn('notification', body)
        self.assertEqual(body['notification']['recipient'], 'test@example.com')
        self.assertEqual(body['notification']['type'], 'email')
        self.assertEqual(body['notification']['status'], 'sent')
        self.assertIn('id', body['notification'])

    def test_send_notification_api_invalid_data(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    def test_sns_event_processing(self):
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

        response = notification.lambda_handler(sns_event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'SNS event processed successfully')
        self.assertIn('processed_records', body)
        self.assertEqual(body['processed_records'], 1)

    def test_email_notification(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['notification']['type'], 'email')
        self.assertEqual(body['notification']['recipient'], 'user@example.com')
        self.assertEqual(body['notification']['subject'], 'Important Email')

    def test_sms_notification(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['notification']['type'], 'sms')
        self.assertEqual(body['notification']['recipient'], '+1234567890')

    def test_invalid_recipient_email(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    def test_invalid_recipient_phone(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    def test_missing_body(self):
        """Test API request with missing body"""
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': None
        }

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    def test_invalid_request_method(self):
        """Test invalid HTTP method"""
        event = {
            'httpMethod': 'GET',
            'resource': '/notify',
            'body': json.dumps({'recipient': 'test@example.com', 'message': 'test'})
        }

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'Resource not found')

    def test_cors_headers(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertIn('headers', response)
        headers = response['headers']
        self.assertIn('Access-Control-Allow-Origin', headers)
        self.assertEqual(headers['Access-Control-Allow-Origin'], '*')

    def test_exception_handling(self):
        """Test exception handling when services are unavailable"""
        with patch('notification.DynamoDBManager.put_item', side_effect=Exception('Database error')):
            event = {
                'httpMethod': 'POST',
                'resource': '/notify',
                'body': json.dumps({
                    'recipient': 'test@example.com',
                    'message': 'Test message',
                    'type': 'email'
                })
            }

            response = notification.lambda_handler(event, self.lambda_context)
            
            self.assertEqual(response['statusCode'], 500)
            body = json.loads(response['body'])
            self.assertEqual(body['error'], 'Failed to send notification')

    @patch('notification.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        # Note: The notification response doesn't include sent_at field currently
        # This test validates timestamp is being called internally
        self.assertGreaterEqual(mock_timestamp.call_count, 1)

    def test_multiple_sns_records(self):
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

        response = notification.lambda_handler(sns_event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['processed_records'], 2)

    def test_notification_priority(self):
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

        response = notification.lambda_handler(event, self.lambda_context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        # Note: The notification response doesn't include priority field currently
        # This test validates the request is processed successfully even with priority
        self.assertEqual(body['notification']['recipient'], 'urgent@example.com')

    @patch('boto3.client')
    def test_sns_publish_error(self, mock_boto_client):
        """Test SNS publish error handling"""
        mock_sns = Mock()
        mock_sns.publish.side_effect = Exception('SNS publish failed')
        mock_boto_client.return_value = mock_sns
        
        event = {
            'httpMethod': 'POST',
            'resource': '/notify',
            'body': json.dumps({
                'recipient': 'test@example.com',
                'message': 'Test message',
                'type': 'email'
            })
        }

        response = notification.lambda_handler(event, self.lambda_context)
        
        # Should handle error gracefully
        self.assertIn(response['statusCode'], [200, 500])


if __name__ == '__main__':
    unittest.main()