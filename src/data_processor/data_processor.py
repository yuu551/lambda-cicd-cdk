import os
import sys
import uuid
import boto3

# Lambda Layerのパスを追加
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/lib/python3.9/site-packages')

from utils import (
    create_response,
    log_event,
    parse_json_body,
    get_current_timestamp
)
from db import DynamoDBManager


# 環境変数
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
PROCESSED_DATA_TABLE_NAME = os.environ.get('PROCESSED_DATA_TABLE_NAME', f"{ENVIRONMENT}-processed-data")
DATA_BUCKET_NAME = os.environ.get('DATA_BUCKET_NAME', f"{ENVIRONMENT}-data-bucket")

# 有効なデータタイプ
VALID_DATA_TYPES = ['text', 'json', 'csv', 'xml', 'binary']


def lambda_handler(event, context):
    """データ処理のメインハンドラー"""
    log_event(event, context)

    try:
        # AWS クライアントとDBマネージャーの初期化
        s3_client = boto3.client('s3')
        db_manager = DynamoDBManager(PROCESSED_DATA_TABLE_NAME)
        
        # イベントソースを判定
        if 'Records' in event and event['Records']:
            # S3イベント
            return handle_s3_event(event, context, s3_client, db_manager)
        elif 'httpMethod' in event:
            # API Gatewayイベント - ルーティングチェック
            http_method = event.get('httpMethod', '')
            resource = event.get('resource', '')
            
            if resource == '/process' and http_method == 'POST':
                return handle_api_request(event, context, db_manager)
            else:
                return create_response(404, {'error': 'Resource not found'})
        else:
            print("Unknown event type")
            return create_response(400, {'error': 'Unknown event type'})

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def handle_s3_event(event, context, s3_client, db_manager):
    """S3イベントを処理"""
    try:
        processed_records = 0
        
        for record in event['Records']:
            # S3イベント情報を取得
            s3_info = record['s3']
            bucket_name = s3_info['bucket']['name']
            object_key = s3_info['object']['key']
            event_name = record['eventName']

            print(f"Processing S3 event: {event_name} for {bucket_name}/{object_key}")

            try:
                # 処理ジョブを記録
                job_id = str(uuid.uuid4())
                job = {
                    'id': job_id,
                    'type': 's3_processing',
                    'bucket': bucket_name,
                    'key': object_key,
                    'status': 'processing',
                    'created_at': get_current_timestamp(),
                    'event_name': event_name
                }

                db_manager.put_item(job)

                # ファイルサイズを取得
                response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
                file_size = response['ContentLength']
                content_type = response.get('ContentType', 'unknown')

                # 処理完了を記録
                updates = {
                    'status': 'completed',
                    'completed_at': get_current_timestamp(),
                    'file_size': file_size,
                    'content_type': content_type
                }

                db_manager.update_item({'id': job_id}, updates)
                processed_records += 1
                
            except Exception as record_error:
                print(f"Error processing record {object_key}: {str(record_error)}")
                # 個別レコードのエラーは記録するが、他のレコード処理は継続
                if 'job_id' in locals():
                    db_manager.update_item(
                        {'id': job_id},
                        {'status': 'failed', 'error': str(record_error), 'failed_at': get_current_timestamp()}
                    )

        return create_response(200, {
            'message': 'S3 event processed successfully',
            'processed_records': processed_records
        })

    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        return create_response(500, {'error': 'Failed to process S3 event'})


def handle_api_request(event, context, db_manager):
    """APIリクエストを処理"""
    try:
        # リクエストボディをパース
        body = parse_json_body(event)

        # バリデーション
        if not body or 'data' not in body:
            return create_response(400, {'error': 'Request body must contain "data" field'})
            
        data = body['data']
        data_type = body.get('type', 'text')
        
        # データが空の場合のチェック
        if not data or (isinstance(data, str) and data.strip() == ''):
            return create_response(400, {'error': 'Data cannot be empty'})
            
        # データタイプのバリデーション
        if data_type not in VALID_DATA_TYPES:
            return create_response(400, {'error': f'Invalid data type. Must be one of: {", ".join(VALID_DATA_TYPES)}'})

        # 処理データIDを生成
        processed_id = str(uuid.uuid4())
        current_timestamp = get_current_timestamp()
        
        # データサイズを計算
        data_size = len(str(data))

        # 処理ジョブを作成（データベース記録用）
        job = {
            'id': processed_id,
            'type': 'api_processing',
            'status': 'queued',
            'created_at': current_timestamp,
            'data': data,
            'data_type': data_type,
            'metadata': body.get('metadata', {})
        }

        db_manager.put_item(job)

        # 実際のデータ処理を実行
        processed_result = process_data(data, data_type)

        # 処理結果を更新
        updates = {
            'status': 'completed',
            'completed_at': current_timestamp,
            'result': processed_result
        }

        db_manager.update_item({'id': processed_id}, updates)

        # テストが期待するレスポンス形式
        processed_data = {
            'id': processed_id,
            'type': data_type,
            'status': 'processed',
            'processed_at': current_timestamp,
            'size': data_size
        }

        return create_response(200, {
            'message': 'Data processed successfully',
            'processed_data': processed_data
        })

    except Exception as e:
        print(f"Error processing API request: {str(e)}")
        return create_response(500, {'error': 'Failed to process data'})


def process_data(data, data_type='text'):
    """データを処理する（サンプル実装）"""
    # 実際の処理ロジックをここに実装
    # このサンプルでは、データの文字数や単語数をカウント
    if isinstance(data, str):
        result = {
            'original_length': len(data),
            'word_count': len(data.split()),
            'processed': True,
            'timestamp': get_current_timestamp(),
            'type': data_type
        }
    elif isinstance(data, dict):
        result = {
            'key_count': len(data.keys()),
            'processed': True,
            'timestamp': get_current_timestamp(),
            'type': data_type
        }
    elif isinstance(data, list):
        result = {
            'item_count': len(data),
            'processed': True,
            'timestamp': get_current_timestamp(),
            'type': data_type
        }
    else:
        result = {
            'data_type': type(data).__name__,
            'processed': True,
            'timestamp': get_current_timestamp(),
            'type': data_type
        }
    
    return result
