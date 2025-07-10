import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from moto import mock_aws
import boto3

# テスト用の環境変数設定
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# テスト対象モジュールをインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'user_management'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'common', 'python'))

from user_management import lambda_handler, create_user, get_user, list_users


@mock_aws
class TestUserManagement(unittest.TestCase):
    """ユーザー管理機能のテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        # DynamoDBテーブルを作成
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = self.dynamodb.create_table(
            TableName='test-users',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # テストコンテキストを作成
        self.context = Mock()
        self.context.request_id = 'test-request-id'
        self.context.function_name = 'test-user-management'
        self.context.get_remaining_time_in_millis = lambda: 300000
    
    def test_create_user_success(self):
        """ユーザー作成成功のテスト"""
        # テストイベントを作成
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'John Doe',
                'email': 'john@example.com',
                'phone': '090-1234-5678'
            })
        }
        
        # 実行
        response = lambda_handler(event, self.context)
        
        # 検証
        self.assertEqual(response['statusCode'], 201)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'User created successfully')
        self.assertEqual(body['user']['name'], 'John Doe')
        self.assertEqual(body['user']['email'], 'john@example.com')
        self.assertIn('id', body['user'])
        self.assertIn('created_at', body['user'])
    
    def test_create_user_invalid_email(self):
        """無効なメールアドレスでのユーザー作成テスト"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'John Doe',
                'email': 'invalid-email'
            })
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Invalid email format', body['error'])
    
    def test_create_user_missing_fields(self):
        """必須フィールドが欠けているユーザー作成テスト"""
        event = {
            'httpMethod': 'POST',
            'resource': '/users',
            'body': json.dumps({
                'name': 'John Doe'
                # emailが欠けている
            })
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Missing required fields', body['error'])
    
    def test_get_user_success(self):
        """ユーザー取得成功のテスト"""
        # テストユーザーを作成
        test_user = {
            'id': 'test-user-id',
            'name': 'Test User',
            'email': 'test@example.com',
            'created_at': '2023-01-01T00:00:00Z'
        }
        
        # DynamoDBに直接挿入
        self.table.put_item(Item=test_user)
        
        # テストイベントを作成
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': 'test-user-id'}
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['user']['id'], 'test-user-id')
        self.assertEqual(body['user']['name'], 'Test User')
    
    def test_get_user_not_found(self):
        """存在しないユーザー取得のテスト"""
        event = {
            'httpMethod': 'GET',
            'resource': '/users/{id}',
            'pathParameters': {'id': 'non-existent-user'}
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertIn('User not found', body['error'])
    
    def test_list_users_success(self):
        """ユーザー一覧取得成功のテスト"""
        # テストユーザーを複数作成
        test_users = [
            {
                'id': 'user-1',
                'name': 'User 1',
                'email': 'user1@example.com',
                'created_at': '2023-01-01T00:00:00Z'
            },
            {
                'id': 'user-2',
                'name': 'User 2',
                'email': 'user2@example.com',
                'created_at': '2023-01-02T00:00:00Z'
            }
        ]
        
        # DynamoDBに直接挿入
        for user in test_users:
            self.table.put_item(Item=user)
        
        # テストイベントを作成
        event = {
            'httpMethod': 'GET',
            'resource': '/users',
            'queryStringParameters': {'limit': '10'}
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(len(body['users']), 2)
        self.assertEqual(body['count'], 2)
    
    def test_unknown_resource(self):
        """不明なリソースのテスト"""
        event = {
            'httpMethod': 'GET',
            'resource': '/unknown'
        }
        
        response = lambda_handler(event, self.context)
        
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertIn('Resource not found', body['error'])


if __name__ == '__main__':
    unittest.main()