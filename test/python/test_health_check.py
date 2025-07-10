import json
import os
import pytest
from unittest.mock import MagicMock
from datetime import datetime

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
    context = MagicMock()
    context.request_id = 'test-request-id'
    context.function_name = 'test-health-check'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-health-check'
    context.memory_limit_in_mb = 256
    context.get_remaining_time_in_millis.return_value = 30000
    return context


class TestHealthCheck:
    """Test cases for Health Check Lambda function"""

    def test_health_check_success(self, lambda_context):
        """Test successful health check"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['service'] == 'health-check'
        assert body['environment'] == 'test'
        assert 'timestamp' in body
        assert 'version' in body
        assert 'uptime' in body

    def test_health_check_with_details(self, lambda_context):
        """Test health check with detailed information"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert 'details' in body
        assert 'memory' in body['details']
        assert 'runtime' in body['details']
        assert 'region' in body['details']

    def test_health_check_cors_headers(self, lambda_context):
        """Test CORS headers in health check response"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert 'headers' in response
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
        assert 'Content-Type' in headers
        assert headers['Content-Type'] == 'application/json'

    def test_health_check_invalid_method(self, lambda_context):
        """Test health check with invalid HTTP method"""
        event = {
            'httpMethod': 'POST',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_health_check_invalid_resource(self, lambda_context):
        """Test health check with invalid resource path"""
        event = {
            'httpMethod': 'GET',
            'resource': '/invalid',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == 'Resource not found'

    def test_health_check_response_structure(self, lambda_context):
        """Test health check response structure"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Required fields
        required_fields = ['status', 'service', 'environment', 'timestamp', 'version']
        for field in required_fields:
            assert field in body, f"Missing required field: {field}"
        
        # Validate timestamp format
        timestamp = body['timestamp']
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp}")

    def test_health_check_environment_variables(self, lambda_context):
        """Test health check with different environment variables"""
        # Test with production environment
        os.environ['ENVIRONMENT'] = 'production'
        
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['environment'] == 'production'
        
        # Reset environment
        os.environ['ENVIRONMENT'] = 'test'

    def test_health_check_memory_info(self, lambda_context):
        """Test health check memory information"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'details' in body
        assert 'memory' in body['details']
        memory_info = body['details']['memory']
        assert 'limit_mb' in memory_info
        assert memory_info['limit_mb'] == lambda_context.memory_limit_in_mb

    def test_health_check_runtime_info(self, lambda_context):
        """Test health check runtime information"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'details' in body
        assert 'runtime' in body['details']
        runtime_info = body['details']['runtime']
        assert 'python_version' in runtime_info
        assert 'function_name' in runtime_info
        assert runtime_info['function_name'] == lambda_context.function_name

    def test_health_check_multiple_requests(self, lambda_context):
        """Test multiple health check requests"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        # Make multiple requests
        responses = []
        for i in range(3):
            response = health_check.lambda_handler(event, lambda_context)
            responses.append(response)
            assert response['statusCode'] == 200

        # All responses should be successful
        for response in responses:
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'

    def test_health_check_response_time(self, lambda_context):
        """Test health check response time"""
        import time
        
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        start_time = time.time()
        response = health_check.lambda_handler(event, lambda_context)
        end_time = time.time()
        
        # Health check should be fast (under 1 second)
        response_time = end_time - start_time
        assert response_time < 1.0, f"Health check took too long: {response_time} seconds"
        assert response['statusCode'] == 200

    def test_health_check_exception_handling(self, lambda_context):
        """Test health check exception handling"""
        # Simulate an error condition
        with pytest.raises(Exception):
            # This should not happen in normal operation, but test error handling
            event = None  # Invalid event
            health_check.lambda_handler(event, lambda_context)

    def test_health_check_json_serialization(self, lambda_context):
        """Test JSON serialization of health check response"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': {'details': 'true'}
        }

        response = health_check.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        # Ensure response body is valid JSON
        try:
            body = json.loads(response['body'])
            # Re-serialize to ensure it's completely valid
            json.dumps(body)
        except (json.JSONDecodeError, TypeError) as e:
            pytest.fail(f"Response body is not valid JSON: {e}")

    def test_health_check_consistent_format(self, lambda_context):
        """Test health check response format consistency"""
        event = {
            'httpMethod': 'GET',
            'resource': '/health',
            'pathParameters': None,
            'queryStringParameters': None
        }

        # Make multiple requests and ensure consistent format
        for i in range(5):
            response = health_check.lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            body = json.loads(response['body'])
            assert isinstance(body, dict)
            assert 'status' in body
            assert 'timestamp' in body


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=health_check', '--cov-report=html'])