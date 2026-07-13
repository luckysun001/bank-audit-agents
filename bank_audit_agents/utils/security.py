"""
安全模块：API Key 认证、输入校验、敏感数据脱敏、操作审计日志

用于银行审计多智能体平台的安全加固。
"""
import re
import hashlib
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class SecurityEventType(str, Enum):
    """安全事件类型"""
    API_KEY_VALIDATED = "api_key_validated"
    API_KEY_REJECTED = "api_key_rejected"
    INPUT_VALIDATION_FAILED = "input_validation_failed"
    SENSITIVE_DATA_DETECTED = "sensitive_data_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""
    user_id: str = "anonymous"
    endpoint: str = ""
    method: str = ""
    status_code: int = 200
    detail: str = ""
    client_ip: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "detail": self.detail,
            "client_ip": self.client_ip,
            "metadata": self.metadata,
        }


class AuditLogger:
    """操作审计日志记录器"""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self._entries: List[AuditLogEntry] = []

    def log(self, entry: AuditLogEntry):
        """记录审计日志"""
        self._entries.append(entry)
        logger.info(
            f"[AUDIT] {entry.event_type} | {entry.method} {entry.endpoint} "
            f"| status={entry.status_code} | ip={entry.client_ip} "
            f"| detail={entry.detail}"
        )
        if self.log_file:
            self._write_to_file(entry)

    def _write_to_file(self, entry: AuditLogEntry):
        """写入审计日志文件"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_entries(self, limit: int = 100) -> List[AuditLogEntry]:
        """获取最近的审计日志"""
        return self._entries[-limit:]


# 全局审计日志实例
audit_logger = AuditLogger()


class InputValidator:
    """输入校验工具"""

    # 常见注入模式
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b.*\b(FROM|INTO|TABLE|WHERE)\b)",
        r"(--|/\*|\*/|;)",
        r"(\bOR\b\s+\b1\s*=\s*1\b)",
        r"(\bAND\b\s+\b1\s*=\s*1\b)",
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on(error|load|click|mouseover)\s*=",
        r"<iframe[^>]*>",
    ]

    # 银行审计相关字段长度限制
    MAX_QUERY_LENGTH = 2000
    MAX_DOC_REFERENCE_LENGTH = 500
    MAX_REPORT_TITLE_LENGTH = 200

    @classmethod
    def validate_query(cls, query: str) -> tuple[bool, str]:
        """校验查询字符串"""
        if not query or not query.strip():
            return False, "查询不能为空"

        if len(query) > cls.MAX_QUERY_LENGTH:
            return False, f"查询长度超过限制（最大 {cls.MAX_QUERY_LENGTH} 字符）"

        if cls._check_patterns(query, cls.SQL_INJECTION_PATTERNS):
            return False, "查询包含潜在的 SQL 注入风险"

        if cls._check_patterns(query, cls.XSS_PATTERNS):
            return False, "查询包含潜在的 XSS 风险"

        return True, ""

    @classmethod
    def validate_doc_reference(cls, ref: str) -> tuple[bool, str]:
        """校验文档引用"""
        if not ref:
            return False, "文档引用不能为空"

        if len(ref) > cls.MAX_DOC_REFERENCE_LENGTH:
            return False, f"文档引用长度超过限制（最大 {cls.MAX_DOC_REFERENCE_LENGTH} 字符）"

        # 不允许路径遍历
        if ".." in ref or ref.startswith("/"):
            return False, "文档引用包含非法路径"

        return True, ""

    @classmethod
    def validate_report_title(cls, title: str) -> tuple[bool, str]:
        """校验报告标题"""
        if not title or not title.strip():
            return False, "报告标题不能为空"

        if len(title) > cls.MAX_REPORT_TITLE_LENGTH:
            return False, f"报告标题长度超过限制（最大 {cls.MAX_REPORT_TITLE_LENGTH} 字符）"

        return True, ""

    @classmethod
    def _check_patterns(cls, text: str, patterns: List[str]) -> bool:
        """检查文本是否匹配任何危险模式"""
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False


class DataMasker:
    """敏感数据脱敏工具"""

    DEFAULT_SENSITIVE_FIELDS = [
        "password", "api_key", "secret", "token", "credential",
        "account_number", "id_card", "phone", "email",
    ]

    # 脱敏规则
    MASK_RULES = {
        "account_number": lambda v: v[:4] + "****" + v[-4:] if len(v) > 8 else "****",
        "id_card": lambda v: v[:3] + "********" + v[-4:] if len(v) > 11 else "****",
        "phone": lambda v: v[:3] + "****" + v[-4:] if len(v) > 7 else "****",
        "email": lambda v: v[0] + "***@" + v.split("@")[1] if "@" in v else "****",
        "password": lambda v: "******",
        "api_key": lambda v: v[:4] + "****" + v[-4:] if len(v) > 8 else "****",
        "secret": lambda v: "******",
        "token": lambda v: v[:4] + "****" + v[-4:] if len(v) > 8 else "****",
        "credential": lambda v: "******",
    }

    @classmethod
    def mask(cls, data: Any, sensitive_fields: Optional[List[str]] = None) -> Any:
        """对数据中的敏感字段进行脱敏"""
        fields = sensitive_fields or cls.DEFAULT_SENSITIVE_FIELDS

        if isinstance(data, dict):
            return {
                k: cls._mask_value(k, v, fields) if k.lower() in fields else cls.mask(v, fields)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [cls.mask(item, fields) for item in data]
        else:
            return data

    @classmethod
    def _mask_value(cls, key: str, value: Any, fields: List[str]) -> Any:
        """对单个值进行脱敏"""
        if value is None:
            return None

        key_lower = key.lower()
        if key_lower in cls.MASK_RULES and isinstance(value, str):
            return cls.MASK_RULES[key_lower](value)
        return "******"

    @classmethod
    def mask_account(cls, account: str) -> str:
        """脱敏银行账号"""
        if not account or len(account) <= 8:
            return "****"
        return account[:4] + "****" + account[-4:]

    @classmethod
    def mask_id_card(cls, id_card: str) -> str:
        """脱敏身份证号"""
        if not id_card or len(id_card) <= 7:
            return "****"
        return id_card[:3] + "********" + id_card[-4:]

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """脱敏手机号"""
        if not phone or len(phone) <= 7:
            return "****"
        return phone[:3] + "****" + phone[-4:]


def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
    configured_keys: Optional[List[str]] = None,
) -> str:
    """API Key 认证依赖

    用法:
        from fastapi import Depends
        @app.get("/protected", dependencies=[Depends(verify_api_key)])
        def protected(): ...
    """
    if not configured_keys:
        # 未配置 API Key 时，允许通过（开发模式）
        return "anonymous"

    if not api_key:
        audit_logger.log(AuditLogEntry(
            event_type=SecurityEventType.API_KEY_REJECTED.value,
            detail="Missing API key",
            status_code=401,
        ))
        raise HTTPException(status_code=401, detail="API Key required")

    # 使用恒定时间比较防止时序攻击
    for configured in configured_keys:
        if _constant_time_compare(api_key, configured):
            audit_logger.log(AuditLogEntry(
                event_type=SecurityEventType.API_KEY_VALIDATED.value,
                status_code=200,
            ))
            return api_key[:8] + "****"

    audit_logger.log(AuditLogEntry(
        event_type=SecurityEventType.API_KEY_REJECTED.value,
        detail="Invalid API key",
        status_code=401,
    ))
    raise HTTPException(status_code=401, detail="Invalid API Key")


def _constant_time_compare(a: str, b: str) -> bool:
    """恒定时间字符串比较，防止时序攻击"""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def create_audit_middleware(audit_log: Optional[AuditLogger] = None):
    """创建审计日志中间件

    用法:
        from fastapi import FastAPI
        app = FastAPI()
        app.middleware("http")(create_audit_middleware())
    """
    log = audit_log or audit_logger

    async def audit_middleware(request: Request, call_next):
        """审计中间件"""
        response = await call_next(request)

        # 记录所有 API 调用
        log.log(AuditLogEntry(
            event_type="api_request",
            endpoint=str(request.url.path),
            method=request.method,
            status_code=response.status_code,
            client_ip=request.client.host if request.client else "",
            metadata={"query_params": dict(request.query_params)},
        ))

        return response

    return audit_middleware
