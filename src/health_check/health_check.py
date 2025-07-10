import json
import datetime
import os


def lambda_handler(event, context):
    """ヘルスチェック用のエンドポイント"""

    # 基本的なヘルスチェック情報
    health_info = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "environment": os.environ.get('ENVIRONMENT', 'unknown'),
        "version": "1.0.0",
        "service": "lambda-cicd-sample"
    }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET'
        },
        'body': json.dumps(health_info)
    }