import boto3
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()

# DynamoDBクライアント
dynamodb = boto3.resource('dynamodb')


class DynamoDBManager:
    """シンプルなDynamoDB操作を提供するクラス"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.table = dynamodb.Table(table_name)

    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """アイテムをテーブルに追加"""
        try:
            response = self.table.put_item(Item=item)
            logger.info(f"Put item success: {item.get('id', 'unknown')}")
            return response
        except ClientError as e:
            logger.error(f"Error putting item: {e}")
            raise

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """キーでアイテムを取得"""
        try:
            response = self.table.get_item(Key=key)
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting item: {e}")
            raise

    def scan_table(self, limit: int = 100) -> List[Dict[str, Any]]:
        """テーブルをスキャン"""
        try:
            response = self.table.scan(Limit=limit)
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"Error scanning table: {e}")
            raise

    def update_item(self, key: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """アイテムを更新"""
        try:
            update_expression_parts = []
            expression_attribute_values = {}

            for field, value in updates.items():
                update_expression_parts.append(f"{field} = :{field}")
                expression_attribute_values[f":{field}"] = value

            response = self.table.update_item(
                Key=key,
                UpdateExpression="SET " + ", ".join(update_expression_parts),
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get('Attributes', {})
        except ClientError as e:
            logger.error(f"Error updating item: {e}")
            raise

    def delete_item(self, key: Dict[str, Any]) -> bool:
        """アイテムを削除"""
        try:
            self.table.delete_item(Key=key)
            logger.info(f"Delete item success: {key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting item: {e}")
            raise
