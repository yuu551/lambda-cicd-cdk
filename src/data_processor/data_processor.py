import os
import sys
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
PROCESSING_TABLE_NAME = f"{ENVIRONMENT}-processing-jobs"

# AWS クライアント
s3_client = boto3.client('s3')
db_manager = DynamoDBManager(PROCESSING_TABLE_NAME)


def lambda_handler(event, context):
    """データ処理のメインハンドラー"""
    log_event(event, context)

    try:
        # イベントソースを判定
        if 'Records' in event and event['Records']:
            # S3イベント
            return handle_s3_event(event, context)
        elif 'httpMethod' in event:
            # API Gatewayイベント
            return handle_api_request(event, context)
        else:
            print("Unknown event type")
            return {'statusCode': 400, 'body': 'Unknown event type'}

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def handle_s3_event(event, context):
    """S3イベントを処理"""
    try:
        for record in event['Records']:
            # S3イベント情報を取得
            s3_info = record['s3']
            bucket_name = s3_info['bucket']['name']
            object_key = s3_info['object']['key']
            event_name = record['eventName']

            print(f"Processing S3 event: {event_name} for {bucket_name}/{object_key}")

            # 処理ジョブを記録
            job = {
                'id': context.request_id,
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

            db_manager.update_item({'id': context.request_id}, updates)

        return {'statusCode': 200, 'body': 'S3 event processed successfully'}

    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        # エラーを記録
        if 'job' in locals():
            db_manager.update_item(
                {'id': context.request_id},
                {'status': 'failed', 'error': str(e), 'failed_at': get_current_timestamp()}
            )
        raise


def handle_api_request(event, context):
    """APIリクエストを処理"""
    try:
        # リクエストボディをパース
        body = parse_json_body(event)

        if not body or 'data' not in body:
            return create_response(400, {'error': 'Request body must contain "data" field'})

        # 処理ジョブを作成
        job = {
            'id': context.request_id,
            'type': 'api_processing',
            'status': 'queued',
            'created_at': get_current_timestamp(),
            'data': body['data'],
            'metadata': body.get('metadata', {})
        }

        db_manager.put_item(job)

        # ここで実際のデータ処理を実行
        # （サンプルなので、簡単な処理のみ）
        processed_data = process_data(body['data'])

        # 処理結果を更新
        updates = {
            'status': 'completed',
            'completed_at': get_current_timestamp(),
            'result': processed_data
        }

        db_manager.update_item({'id': context.request_id}, updates)

        return create_response(200, {
            'message': 'Data processed successfully',
            'job_id': context.request_id,
            'result': processed_data
        })

    except Exception as e:
        print(f"Error processing API request: {str(e)}")
        return create_response(500, {'error': 'Failed to process data'})


def process_data(data):
    """データを処理する（サンプル実装）"""
    # 実際の処理ロジックをここに実装
    # このサンプルでは、データの文字数や単語数をカウント
    if isinstance(data, str):
        return {
            'original_length': len(data),
            'word_count': len(data.split()),
            'processed': True,
            'timestamp': get_current_timestamp()
        }
    elif isinstance(data, dict):
        return {
            'key_count': len(data.keys()),
            'processed': True,
            'timestamp': get_current_timestamp()
        }
    elif isinstance(data, list):
        return {
            'item_count': len(data),
            'processed': True,
            'timestamp': get_current_timestamp()
        }
    else:
        return {
            'type': type(data).__name__,
            'processed': True,
            'timestamp': get_current_timestamp()
        }
