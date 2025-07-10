import json
import os
import pytest
import uuid
from unittest.mock import patch, MagicMock
import boto3

# Handle different moto versions
try:
    from moto import mock_aws
    mock_dynamodb = mock_aws
    mock_s3 = mock_aws
except ImportError:
    try:
        from moto import mock_dynamodb2 as mock_dynamodb, mock_s3
    except ImportError:
        from moto import mock_dynamodb, mock_s3

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['PROCESSED_DATA_TABLE_NAME'] = 'test-processed-data'
os.environ['DATA_BUCKET_NAME'] = 'test-data-bucket'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add source path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/data_processor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/layers/common/python'))

# Import the module to test
import data_processor


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = MagicMock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-data-processor'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-data-processor'
    context.memory_limit_in_mb = 512
    context.get_remaining_time_in_millis.return_value = 30000
    return context


@pytest.fixture
@mock_dynamodb
def dynamodb_table():
    """Create a mock DynamoDB table"""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    table = dynamodb.create_table(
        TableName='test-processed-data',
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
@mock_s3
def s3_bucket():
    """Create a mock S3 bucket"""
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='test-data-bucket')
    yield s3


class TestDataProcessor:
    """Test cases for Data Processor Lambda function"""

    def test_process_data_api_success(self, dynamodb_table, lambda_context):
        """Test successful data processing via API"""
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps({
                'data': 'test data content',
                'type': 'text',
                'metadata': {'source': 'api'}
            })
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Data processed successfully'
        assert 'processed_data' in body
        assert body['processed_data']['type'] == 'text'
        assert body['processed_data']['status'] == 'processed'
        assert 'id' in body['processed_data']

    def test_process_data_api_invalid_data(self, dynamodb_table, lambda_context):
        """Test data processing with invalid data"""
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps({
                'data': '',  # Empty data
                'type': 'unknown'  # Invalid type
            })
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_s3_event_processing(self, dynamodb_table, s3_bucket, lambda_context):
        """Test S3 event processing"""
        # Create S3 event
        s3_event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {
                            'name': 'test-data-bucket'
                        },
                        'object': {
                            'key': 'uploads/test-file.txt',
                            'size': 1024
                        }
                    }
                }
            ]
        }

        # Put test object in S3
        s3_bucket.put_object(
            Bucket='test-data-bucket',
            Key='uploads/test-file.txt',
            Body=b'Test file content'
        )

        response = data_processor.lambda_handler(s3_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'S3 event processed successfully'
        assert 'processed_records' in body
        assert body['processed_records'] == 1

    def test_s3_event_processing_error(self, dynamodb_table, lambda_context):
        """Test S3 event processing with non-existent object"""
        s3_event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {
                            'name': 'non-existent-bucket'
                        },
                        'object': {
                            'key': 'uploads/non-existent-file.txt',
                            'size': 1024
                        }
                    }
                }
            ]
        }

        response = data_processor.lambda_handler(s3_event, lambda_context)
        
        # Should handle error gracefully
        assert response['statusCode'] in [200, 500]

    def test_invalid_request_method(self, dynamodb_table, lambda_context):
        """Test invalid HTTP method"""
        event = {
            'httpMethod': 'DELETE',
            'resource': '/process',
            'body': json.dumps({'data': 'test'})
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_missing_body(self, dynamodb_table, lambda_context):
        """Test API request with missing body"""
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': None
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_data_validation(self, dynamodb_table, lambda_context):
        """Test data validation logic"""
        # Test with valid data
        valid_data = {
            'data': 'valid content',
            'type': 'text',
            'metadata': {'source': 'test'}
        }
        
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps(valid_data)
        }

        response = data_processor.lambda_handler(event, lambda_context)
        assert response['statusCode'] == 200

        # Test with invalid data type
        invalid_data = {
            'data': 'content',
            'type': 'invalid_type'
        }
        
        event['body'] = json.dumps(invalid_data)
        response = data_processor.lambda_handler(event, lambda_context)
        assert response['statusCode'] == 400

    def test_cors_headers(self, dynamodb_table, lambda_context):
        """Test CORS headers in response"""
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps({
                'data': 'test data',
                'type': 'text'
            })
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'

    def test_exception_handling(self, lambda_context):
        """Test exception handling when DynamoDB is unavailable"""
        with patch('data_processor.db_manager.put_item', side_effect=Exception('Database error')):
            event = {
                'httpMethod': 'POST',
                'resource': '/process',
                'body': json.dumps({
                    'data': 'test data',
                    'type': 'text'
                })
            }

            response = data_processor.lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert body['error'] == 'Failed to process data'

    @patch('data_processor.get_current_timestamp')
    def test_timestamp_generation(self, mock_timestamp, dynamodb_table, lambda_context):
        """Test timestamp generation in data processing"""
        mock_timestamp.return_value = '2023-01-01T12:00:00Z'
        
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps({
                'data': 'test data',
                'type': 'text'
            })
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_data']['processed_at'] == '2023-01-01T12:00:00Z'
        assert mock_timestamp.call_count >= 1

    def test_large_data_processing(self, dynamodb_table, lambda_context):
        """Test processing of large data"""
        large_data = 'x' * 10000  # 10KB of data
        
        event = {
            'httpMethod': 'POST',
            'resource': '/process',
            'body': json.dumps({
                'data': large_data,
                'type': 'text',
                'metadata': {'size': 'large'}
            })
        }

        response = data_processor.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Data processed successfully'
        assert body['processed_data']['size'] == len(large_data)

    def test_multiple_s3_records(self, dynamodb_table, s3_bucket, lambda_context):
        """Test processing multiple S3 records in one event"""
        s3_event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {'name': 'test-data-bucket'},
                        'object': {'key': 'uploads/file1.txt', 'size': 1024}
                    }
                },
                {
                    'eventSource': 'aws:s3',
                    'eventName': 'ObjectCreated:Put',
                    's3': {
                        'bucket': {'name': 'test-data-bucket'},
                        'object': {'key': 'uploads/file2.txt', 'size': 2048}
                    }
                }
            ]
        }

        # Put test objects in S3
        s3_bucket.put_object(Bucket='test-data-bucket', Key='uploads/file1.txt', Body=b'File 1')
        s3_bucket.put_object(Bucket='test-data-bucket', Key='uploads/file2.txt', Body=b'File 2')

        response = data_processor.lambda_handler(s3_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_records'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=data_processor', '--cov-report=html'])