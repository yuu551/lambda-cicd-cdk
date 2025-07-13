import json
import datetime
import os
import sys
import platform

# Lambda Layerのパスを追加
sys.path.insert(0, '/opt/python')
sys.path.insert(0, '/opt/python/lib/python3.9/site-packages')

from utils import create_response, get_current_timestamp


def lambda_handler(event, context):
    """ヘルスチェック用のエンドポイント"""
    
    try:
        # ルーティングチェック
        http_method = event.get('httpMethod', '')
        resource = event.get('resource', '')
        
        if resource == '/health' and http_method == 'GET':
            return handle_health_check(event, context)
        else:
            return create_response(404, {'error': 'Resource not found'})
            
    except Exception as e:
        print(f"Error in health check: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def handle_health_check(event, context):
    """ヘルスチェック処理"""
    
    # 起動時間の計算（シンプルな実装）
    uptime_ms = context.get_remaining_time_in_millis() if hasattr(context, 'get_remaining_time_in_millis') else 30000
    uptime_seconds = (300000 - uptime_ms) / 1000  # 5分のタイムアウトから逆算
    
    # 基本的なヘルスチェック情報
    health_info = {
        "status": "healthy",
        "timestamp": get_current_timestamp(),
        "environment": os.environ.get('ENVIRONMENT', 'unknown'),
        "version": "1.0.0",
        "service": "health-check",
        "uptime": f"{uptime_seconds:.2f}s"
    }
    
    # 詳細情報の要求をチェック
    query_params = event.get('queryStringParameters', {})
    if query_params and query_params.get('details') == 'true':
        health_info['details'] = {
            'memory': {
                'limit_mb': context.memory_limit_in_mb if hasattr(context, 'memory_limit_in_mb') else 256,
                'unit': 'MB'
            },
            'runtime': {
                'python_version': platform.python_version(),
                'function_name': context.function_name if hasattr(context, 'function_name') else 'unknown',
                'function_version': context.function_version if hasattr(context, 'function_version') else 'unknown'
            },
            'region': os.environ.get('AWS_REGION', 'us-east-1')
        }
    
    # CORSヘッダーを含むレスポンスを作成
    headers = {
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }
    
    return create_response(200, health_info, headers)