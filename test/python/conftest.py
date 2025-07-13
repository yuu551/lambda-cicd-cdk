import os
import pytest
import boto3
from moto import mock_aws


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def mocked_aws(aws_credentials):
    """Mock all AWS services for tests"""
    with mock_aws():
        yield


@pytest.fixture(scope="function")
def dynamodb_client(mocked_aws):
    """Mocked DynamoDB client"""
    return boto3.client("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def dynamodb_resource(mocked_aws):
    """Mocked DynamoDB resource"""
    return boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def s3_client(mocked_aws):
    """Mocked S3 client"""
    return boto3.client("s3", region_name="us-east-1")


@pytest.fixture(scope="function")
def sns_client(mocked_aws):
    """Mocked SNS client"""
    return boto3.client("sns", region_name="us-east-1")