import os
import sys
import uuid

# Lambda Layerのパスを追加
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/lib/python3.9/site-packages')

from utils import (
    create_response,
    log_event,
    parse_json_body,
    get_path_parameter,
    get_query_parameter,
    get_current_timestamp
)
from db import DynamoDBManager
from validators import validate_user_data


# 環境変数から設定を取得
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
USER_TABLE_NAME = os.environ.get('USER_TABLE_NAME', f"{ENVIRONMENT}-users")

# DynamoDBマネージャーの初期化
db_manager = DynamoDBManager(USER_TABLE_NAME)


def lambda_handler(event, context):
    """ユーザー管理APIのメインハンドラー"""
    log_event(event, context)

    try:
        http_method = event.get('httpMethod', '')
        resource = event.get('resource', '')

        # ルーティング
        if resource == '/users' and http_method == 'POST':
            return create_user(event)
        elif resource == '/users/{id}' and http_method == 'GET':
            return get_user(event)
        elif resource == '/users' and http_method == 'GET':
            return list_users(event)
        else:
            return create_response(404, {'error': 'Resource not found'})

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def create_user(event):
    """新規ユーザーを作成"""
    try:
        # リクエストボディをパース
        body = parse_json_body(event)

        # バリデーション
        is_valid, error_message = validate_user_data(body)
        if not is_valid:
            return create_response(400, {'error': error_message})

        # ユーザーオブジェクトを作成
        user = {
            'id': str(uuid.uuid4()),
            'name': body['name'],
            'email': body['email'],
            'created_at': get_current_timestamp(),
            'updated_at': get_current_timestamp(),
            'status': 'active'
        }

        # オプショナルフィールド
        if 'phone' in body:
            user['phone'] = body['phone']
        if 'department' in body:
            user['department'] = body['department']

        # データベースに保存
        db_manager.put_item(user)

        return create_response(201, {
            'message': 'User created successfully',
            'user': user
        })

    except Exception as e:
        print(f"Error creating user: {str(e)}")
        return create_response(500, {'error': 'Failed to create user'})


def get_user(event):
    """IDでユーザーを取得"""
    try:
        user_id = get_path_parameter(event, 'id')
        if not user_id:
            return create_response(400, {'error': 'User ID is required'})

        # データベースから取得
        user = db_manager.get_item({'id': user_id})

        if not user:
            return create_response(404, {'error': 'User not found'})

        return create_response(200, {'user': user})

    except Exception as e:
        print(f"Error getting user: {str(e)}")
        return create_response(500, {'error': 'Failed to get user'})


def list_users(event):
    """ユーザー一覧を取得"""
    try:
        # クエリパラメータから取得数を取得
        limit_str = get_query_parameter(event, 'limit')
        limit = int(limit_str) if limit_str else 50
        limit = min(limit, 100)  # 最大100件に制限

        # データベースから一覧取得
        users = db_manager.scan_table(limit=limit)

        return create_response(200, {
            'users': users,
            'count': len(users)
        })

    except Exception as e:
        print(f"Error listing users: {str(e)}")
        return create_response(500, {'error': 'Failed to list users'})
