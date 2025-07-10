import re
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger()


class ValidationError(Exception):
    """バリデーションエラー用のカスタム例外"""
    pass


def validate_email(email: str) -> bool:
    """メールアドレスの形式を検証"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
    """必須フィールドの存在を検証"""
    missing_fields = []

    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields


def validate_string_length(value: str, min_length: int = 0, max_length: Optional[int] = None) -> bool:
    """文字列の長さを検証"""
    if len(value) < min_length:
        return False

    if max_length and len(value) > max_length:
        return False

    return True


def validate_phone_number(phone: str) -> bool:
    """電話番号の形式を検証（国際的な形式に対応）"""
    # ハイフンありなし両方に対応、より柔軟な検証
    patterns = [
        r'^0\d{9,10}$',  # 日本形式 ハイフンなし
        r'^0\d{1,4}-\d{1,4}-\d{4}$',  # 日本形式 ハイフンあり
        r'^\+81\d{9,10}$',  # 国際形式
        r'^\d{3}-\d{3}-\d{4}$',  # 米国形式
        r'^\+\d{1,3}\d{7,14}$',  # 一般的な国際形式
        r'^\d{10,15}$'  # 数字のみ10-15桁
    ]

    return any(re.match(pattern, phone) for pattern in patterns)


def validate_user_data(user_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """ユーザーデータの総合的な検証"""
    try:
        # 必須フィールドチェック
        is_valid, missing = validate_required_fields(
            user_data,
            ['name', 'email']
        )
        if not is_valid:
            return False, f"Missing required fields: {', '.join(missing)}"

        # メールアドレス検証
        if not validate_email(user_data['email']):
            return False, "Invalid email format"

        # 名前の長さ検証
        if not validate_string_length(user_data['name'], min_length=1, max_length=100):
            return False, "Name must be between 1 and 100 characters"

        # オプション：電話番号が存在する場合の検証
        if 'phone' in user_data and user_data['phone']:
            if not validate_phone_number(user_data['phone']):
                return False, "Invalid phone number format"

        return True, None

    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, "Validation failed due to unexpected error"
