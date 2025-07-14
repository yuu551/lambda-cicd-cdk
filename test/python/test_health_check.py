import json
import os
import pytest
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws

# Set environment variables before importing the module
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Add source path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/health_check'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/layers/common/python'))

# Import the module to test
import health_check


@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = Mock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-health-check'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-health-check'
    context.memory_limit_in_mb = 512
    context.get_remaining_time_in_millis = Mock(return_value=30000)
    return context


class TestHealthCheck:
    """Test cases for Health Check Lambda function"""

    def test_health_check_success(self, lambda_context):
        """Test successful health check"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert 'timestamp' in body
        assert 'service' in body

    def test_health_check_with_details(self, lambda_context):
        """Test health check with details"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert 'details' in body
        assert 'memory' in body['details']
        assert 'runtime' in body['details']

    def test_health_check_invalid_method(self, lambda_context):
        """Test health check with invalid HTTP method"""
        event = {
            'httpMethod': 'POST',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_health_check_invalid_resource(self, lambda_context):
        """Test health check with invalid resource"""
        event = {
            'httpMethod': 'GET',
            'resource': '/invalid'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_health_check_response_structure(self, lambda_context):
        """Test health check response structure"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert 'statusCode' in response
        assert 'headers' in response
        assert 'body' in response
        
        body = json.loads(response['body'])
        assert 'status' in body
        assert 'timestamp' in body

    def test_health_check_cors_headers(self, lambda_context):
        """Test CORS headers in health check response"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'

    def test_health_check_json_serialization(self, lambda_context):
        """Test JSON serialization of health check response"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        # Should not raise an exception
        body = json.loads(response['body'])
        assert isinstance(body, dict)

    def test_health_check_environment_variables(self, lambda_context):
        """Test health check environment variable handling"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        body = json.loads(response['body'])
        assert 'details' in body
        assert 'environment' in body['details']

    def test_health_check_runtime_info(self, lambda_context):
        """Test health check runtime information"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        body = json.loads(response['body'])
        assert 'details' in body
        assert 'runtime' in body['details']
        assert 'version' in body['details']['runtime']

    def test_health_check_memory_info(self, lambda_context):
        """Test health check memory information with details"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        body = json.loads(response['body'])
        assert 'details' in body
        assert 'memory' in body['details']
        assert 'limit_mb' in body['details']['memory']
        assert body['details']['memory']['limit_mb'] == 512

    def test_health_check_response_time(self, lambda_context):
        """Test health check response time"""
        import time
        start_time = time.time()
        
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Should respond quickly (under 1 second)
        assert response_time < 1.0
        assert response['statusCode'] == 200

    def test_health_check_multiple_requests(self, lambda_context):
        """Test multiple health check requests"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        # Make multiple requests
        for _ in range(3):
            response = health_check.lambda_handler(event, lambda_context)
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'

    def test_health_check_consistent_format(self, lambda_context):
        """Test health check response format consistency"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health'
        }

        # Make multiple requests and verify consistent format
        for _ in range(2):
            response = health_check.lambda_handler(event, lambda_context)
            body = json.loads(response['body'])
            
            # Check required fields
            assert 'status' in body
            assert 'timestamp' in body
            assert 'service' in body
            
            # Check field types
            assert isinstance(body['status'], str)
            assert isinstance(body['timestamp'], str)
            assert isinstance(body['service'], str)

    def test_health_check_exception_handling(self, lambda_context):
        """Test health check exception handling"""
        # Mock an exception in the context
        lambda_context.get_remaining_time_in_millis = Mock(side_effect=Exception("Context error"))
        
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        # Should still return 200 even with context errors
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])