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
from validators import validate_email, validate_required_fields


# 環境変数
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
NOTIFICATIONS_TABLE_NAME = f"{ENVIRONMENT}-notifications"

# AWS クライアント
sns_client = boto3.client('sns')
ses_client = boto3.client('ses')
db_manager = DynamoDBManager(NOTIFICATIONS_TABLE_NAME)


def lambda_handler(event, context):
    """通知サービスのメインハンドラー"""
    log_event(event, context)

    try:
        # イベントソースを判定
        if 'Records' in event and event['Records']:
            # SNSイベント
            return handle_sns_event(event, context)
        elif 'httpMethod' in event:
            # API Gatewayイベント
            return handle_api_request(event, context)
        else:
            print("Unknown event type")
            return {'statusCode': 400, 'body': 'Unknown event type'}

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def handle_sns_event(event, context):
    """SNSイベントを処理"""
    try:
        for record in event['Records']:
            sns = record['Sns']
            message = sns['Message']
            subject = sns.get('Subject', 'No Subject')
            topic_arn = sns['TopicArn']

            print(f"Processing SNS message from topic: {topic_arn}")

            # 通知を記録
            notification = {
                'id': record['Sns']['MessageId'],
                'type': 'sns_notification',
                'source': 'sns',
                'topic_arn': topic_arn,
                'subject': subject,
                'message': message,
                'status': 'received',
                'created_at': get_current_timestamp()
            }

            db_manager.put_item(notification)

            # メッセージを処理（例：特定のキーワードに基づいてアクション）
            if 'URGENT' in message.upper():
                handle_urgent_notification(notification)

            # 処理完了を記録
            db_manager.update_item(
                {'id': notification['id']},
                {'status': 'processed', 'processed_at': get_current_timestamp()}
            )

        return {'statusCode': 200, 'body': 'SNS events processed successfully'}

    except Exception as e:
        print(f"Error processing SNS event: {str(e)}")
        raise


def handle_api_request(event, context):
    """APIリクエストを処理して通知を送信"""
    try:
        # リクエストボディをパース
        body = parse_json_body(event)

        # バリデーション
        is_valid, missing = validate_required_fields(
            body,
            ['recipient', 'subject', 'message', 'channel']
        )

        if not is_valid:
            return create_response(400, {'error': f'Missing required fields: {", ".join(missing)}'})

        recipient = body['recipient']
        subject = body['subject']
        message = body['message']
        channel = body['channel']  # 'email' or 'sms'

        # チャンネルごとの処理
        if channel == 'email':
            if not validate_email(recipient):
                return create_response(400, {'error': 'Invalid email address'})
            result = send_email_notification(recipient, subject, message)
        elif channel == 'sms':
            result = send_sms_notification(recipient, message)
        else:
            return create_response(400, {'error': 'Invalid channel. Use "email" or "sms"'})

        # 通知を記録
        notification = {
            'id': context.request_id,
            'type': f'{channel}_notification',
            'source': 'api',
            'recipient': recipient,
            'subject': subject,
            'message': message,
            'channel': channel,
            'status': 'sent' if result['success'] else 'failed',
            'created_at': get_current_timestamp()
        }

        if not result['success']:
            notification['error'] = result.get('error', 'Unknown error')

        db_manager.put_item(notification)

        return create_response(
            200 if result['success'] else 500,
            {
                'message': 'Notification sent successfully' if result['success'] else 'Failed to send notification',
                'notification_id': context.request_id,
                'details': result
            }
        )

    except Exception as e:
        print(f"Error handling API request: {str(e)}")
        return create_response(500, {'error': 'Failed to send notification'})


def send_email_notification(recipient, subject, message):
    """メール通知を送信"""
    try:
        # SESを使用してメールを送信
        # 注：SESで送信元アドレスが検証されている必要があります
        response = ses_client.send_email(
            Source=f'noreply@{ENVIRONMENT}.example.com',
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': message}}
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


def send_sms_notification(phone_number, message):
    """SMS通知を送信"""
    try:
        # SNSを使用してSMSを送信
        response = sns_client.publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
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


def handle_urgent_notification(notification):
    """緊急通知を処理"""
    print(f"URGENT notification detected: {notification['id']}")
    # ここに緊急通知の特別な処理を実装
    # 例：管理者への即時通知、特別なログ記録など
