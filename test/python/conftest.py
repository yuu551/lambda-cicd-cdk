import pytest
import boto3
from moto import mock_aws


@pytest.fixture(scope='function')
@mock_aws
def dynamodb_resource():
    """Create a mock DynamoDB resource"""
    return boto3.resource('dynamodb', region_name='us-east-1')


@pytest.fixture(scope='function')
@mock_aws  
def s3_client():
    """Create a mock S3 client"""
    return boto3.client('s3', region_name='us-east-1')


@pytest.fixture(scope='function')
@mock_aws
def sns_client():
    """Create a mock SNS client"""
    return boto3.client('sns', region_name='us-east-1')