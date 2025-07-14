import os
import sys
import uuid
import boto3
import re

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
NOTIFICATION_TABLE_NAME = os.environ.get('NOTIFICATION_TABLE_NAME', f"{ENVIRONMENT}-notifications")
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', f"arn:aws:sns:us-east-1:123456789012:{ENVIRONMENT}-notifications")

# 有効な通知タイプ
VALID_NOTIFICATION_TYPES = ['email', 'sms']


def lambda_handler(event, context):
    """通知サービスのメインハンドラー"""
    log_event(event, context)

    try:
        # AWS クライアントとDBマネージャーの初期化
        sns_client = boto3.client('sns')
        ses_client = boto3.client('ses')
        db_manager = DynamoDBManager(NOTIFICATION_TABLE_NAME)
        
        # イベントソースを判定
        if 'Records' in event and event['Records']:
            # SNSイベント
            return handle_sns_event(event, context, db_manager)
        elif 'httpMethod' in event:
            # API Gatewayイベント - ルーティングチェック
            http_method = event.get('httpMethod', '')
            resource = event.get('resource', '')
            
            if resource == '/notify' and http_method == 'POST':
                return handle_api_request(event, context, sns_client, db_manager)
            else:
                return create_response(404, {'error': 'Resource not found'})
        else:
            print("Unknown event type")
            return create_response(400, {'error': 'Unknown event type'})

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def handle_sns_event(event, context, db_manager):
    """SNSイベントを処理"""
    try:
        processed_records = 0
        
        for record in event['Records']:
            try:
                sns = record['Sns']
                message_content = sns['Message']
                subject = sns.get('Subject', 'No Subject')
                topic_arn = sns['TopicArn']
                message_id = sns['MessageId']

                print(f"Processing SNS message from topic: {topic_arn}")

                # メッセージ内容をパース（JSON形式の場合）
                try:
                    import json
                    parsed_message = json.loads(message_content)
                    recipient = parsed_message.get('recipient', 'unknown')
                    notification_type = parsed_message.get('type', 'sns')
                except:
                    recipient = 'unknown'
                    notification_type = 'sns'

                # 通知を記録
                notification_id = str(uuid.uuid4())
                notification = {
                    'id': notification_id,
                    'type': notification_type,
                    'source': 'sns',
                    'topic_arn': topic_arn,
                    'recipient': recipient,
                    'subject': subject,
                    'message': message_content,
                    'status': 'received',
                    'created_at': get_current_timestamp(),
                    'sns_message_id': message_id
                }

                db_manager.put_item(notification)

                # 処理完了を記録
                db_manager.update_item(
                    {'id': notification_id},
                    {'status': 'processed', 'processed_at': get_current_timestamp()}
                )
                
                processed_records += 1
                
            except Exception as record_error:
                print(f"Error processing SNS record: {str(record_error)}")
                # 個別レコードのエラーは記録するが、他のレコード処理は継続

        return create_response(200, {
            'message': 'SNS event processed successfully',
            'processed_records': processed_records
        })

    except Exception as e:
        print(f"Error processing SNS event: {str(e)}")
        return create_response(500, {'error': 'Failed to process SNS event'})


def handle_api_request(event, context, sns_client, db_manager):
    """APIリクエストを処理して通知を送信"""
    try:
        # リクエストボディをパース
        body = parse_json_body(event)

        # バリデーション
        if not body:
            return create_response(400, {'error': 'Request body is required'})
            
        recipient = body.get('recipient', '').strip()
        message = body.get('message', '').strip()
        notification_type = body.get('type', '').strip()
        subject = body.get('subject', '').strip()

        # 必須フィールドのチェック
        if not recipient:
            return create_response(400, {'error': 'Recipient is required'})
        if not message:
            return create_response(400, {'error': 'Message is required'})
        if not notification_type:
            return create_response(400, {'error': 'Type is required'})
            
        # 通知タイプの検証
        if notification_type not in VALID_NOTIFICATION_TYPES:
            return create_response(400, {'error': f'Invalid type. Must be one of: {", ".join(VALID_NOTIFICATION_TYPES)}'})

        # 受信者の形式検証
        if notification_type == 'email':
            if not is_valid_email(recipient):
                return create_response(400, {'error': 'Invalid email format'})
        elif notification_type == 'sms':
            if not is_valid_phone(recipient):
                return create_response(400, {'error': 'Invalid phone number format'})

        # 通知ID生成
        notification_id = str(uuid.uuid4())
        current_timestamp = get_current_timestamp()

        # 通知送信
        try:
            if notification_type == 'email':
                send_result = send_email_notification(recipient, subject, message)
            elif notification_type == 'sms':
                send_result = send_sms_notification(recipient, message)
            
            status = 'sent' if send_result.get('success', False) else 'failed'
        except Exception as send_error:
            print(f"Error sending notification: {str(send_error)}")
            status = 'failed'
            send_result = {'success': False, 'error': str(send_error)}

        # 通知を記録
        notification_record = {
            'id': notification_id,
            'type': f'{notification_type}_notification',
            'source': 'api',
            'recipient': recipient,
            'message': message,
            'notification_type': notification_type,
            'status': status,
            'created_at': current_timestamp
        }
        
        if subject:
            notification_record['subject'] = subject
            
        if not send_result.get('success', False):
            notification_record['error'] = send_result.get('error', 'Unknown error')

        db_manager.put_item(notification_record)

        # テストが期待するレスポンス形式
        notification_response = {
            'id': notification_id,
            'recipient': recipient,
            'type': notification_type,
            'status': status
        }
        
        if subject:
            notification_response['subject'] = subject

        return create_response(200, {
            'message': 'Notification sent successfully',
            'notification': notification_response
        })

    except Exception as e:
        print(f"Error handling API request: {str(e)}")
        return create_response(500, {'error': 'Failed to send notification'})


def send_email_notification(recipient, subject, message, sns_client):
    """メール通知を送信"""
    try:
        # SNSを使用してメール通知を送信（SESの代わり）
        # テスト環境ではモックされるため、実際の送信は行われない
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject or 'Notification',
            Message=message,
            MessageAttributes={
                'notification_type': {
                    'DataType': 'String',
                    'StringValue': 'email'
                },
                'recipient': {
                    'DataType': 'String',
                    'StringValue': recipient
                }
            }
        )

        return {
            'success': True,
            'message_id': response['MessageId']
        }

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def send_sms_notification(phone_number, message, sns_client):
    """SMS通知を送信"""
    try:
        # SNSを使用してSMS通知を送信
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            MessageAttributes={
                'notification_type': {
                    'DataType': 'String',
                    'StringValue': 'sms'
                },
                'recipient': {
                    'DataType': 'String',
                    'StringValue': phone_number
                }
            }
        )

        return {
            'success': True,
            'message_id': response['MessageId']
        }

    except Exception as e:
        print(f"Error sending SMS: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def is_valid_email(email):
    """メールアドレス形式の検証"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_phone(phone):
    """電話番号形式の検証（国際形式）"""
    pattern = r'^\+?[1-9]\d{1,14}$'
    return re.match(pattern, phone) is not None