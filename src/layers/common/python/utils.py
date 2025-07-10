import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# ロガーの設定
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def create_response(status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """APIレスポンスを作成する共通関数"""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }

    if headers:
        default_headers.update(headers)

    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, default=str)
    }


def log_event(event: Dict[str, Any], context: Any) -> None:
    """Lambda関数のイベントとコンテキストをログに記録"""
    logger.info(f"Event: {json.dumps(event)}")
    logger.info(f"Context: {context}")
    logger.info(f"Request ID: {context.request_id if hasattr(context, 'request_id') else 'N/A'}")


def get_current_timestamp() -> str:
    """現在のタイムスタンプを取得"""
    return datetime.utcnow().isoformat() + 'Z'


def parse_json_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """APIイベントからJSONボディをパース"""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            return json.loads(body)
        return body
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON body: {body}")
        return {}


def get_path_parameter(event: Dict[str, Any], parameter_name: str) -> Optional[str]:
    """パスパラメータを取得"""
    path_parameters = event.get('pathParameters', {})
    return path_parameters.get(parameter_name) if path_parameters else None


def get_query_parameter(event: Dict[str, Any], parameter_name: str) -> Optional[str]:
    """クエリパラメータを取得"""
    query_parameters = event.get('queryStringParameters', {})
    return query_parameters.get(parameter_name) if query_parameters else None
