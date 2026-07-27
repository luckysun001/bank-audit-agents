"""
安全模块

提供银行审计多智能体平台的安全加固功能。

核心功能:
    1. API Key 认证（FastAPI 依赖注入）
    2. 输入校验（SQL 注入、XSS 攻击防护）
    3. 敏感数据脱敏（银行账号、身份证、手机号等）
    4. 操作审计日志（记录所有 API 调用）
    5. 审计中间件（自动记录 HTTP 请求）

安全设计原则:
    - 纵深防御：多层安全防护机制
    - 最小权限：只授予必要的权限
    - 审计追踪：所有操作可追溯
    - 数据保护：敏感数据自动脱敏

使用示例:
    # API Key 认证（FastAPI）
    from fastapi import Depends
    @app.get("/protected", dependencies=[Depends(verify_api_key)])
    def protected():
        return {"message": "authorized"}

    # 输入校验
    is_valid, error = InputValidator.validate_query("select * from users")

    # 敏感数据脱敏
    masked_data = DataMasker.mask({"account_number": "1234567890123456"})

    # 审计日志中间件
    app.middleware("http")(create_audit_middleware())
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

# 获取模块级日志记录器
logger = logging.getLogger(__name__)

# API Key 请求头定义
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class SecurityEventType(str, Enum):
    """
    安全事件类型枚举

    定义系统中可能发生的安全事件类型，用于审计日志记录。
    """
    API_KEY_VALIDATED = "api_key_validated"        # API Key 验证成功
    API_KEY_REJECTED = "api_key_rejected"          # API Key 验证失败
    INPUT_VALIDATION_FAILED = "input_validation_failed"  # 输入校验失败
    SENSITIVE_DATA_DETECTED = "sensitive_data_detected"  # 检测到敏感数据
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"    # 超出速率限制


@dataclass
class AuditLogEntry:
    """
    审计日志条目数据类

    存储单条审计日志的详细信息，用于记录系统操作和安全事件。

    字段说明:
        timestamp: 事件发生时间
        event_type: 事件类型
        user_id: 用户 ID（默认为 anonymous）
        endpoint: 请求的 API 端点
        method: HTTP 方法（GET/POST/PUT/DELETE 等）
        status_code: HTTP 状态码
        detail: 事件详情描述
        client_ip: 客户端 IP 地址
        metadata: 附加元数据（查询参数、请求体摘要等）
    """
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
        """
        将审计日志条目转换为字典格式

        Returns:
            Dict[str, Any]: 字典格式的审计日志
        """
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
    """
    操作审计日志记录器

    负责记录所有系统操作和安全事件，支持内存存储和文件存储两种方式。

    核心职责:
        1. 记录审计日志条目
        2. 将日志写入文件（如果配置）
        3. 查询最近的审计日志

    使用方式:
        audit_logger = AuditLogger(log_file="audit.log")
        audit_logger.log(AuditLogEntry(event_type="api_request", ...))
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        初始化审计日志记录器

        Args:
            log_file: 审计日志文件路径（可选，不指定则只存储在内存中）
        """
        self.log_file = log_file
        # 内存中的审计日志列表
        self._entries: List[AuditLogEntry] = []

    def log(self, entry: AuditLogEntry):
        """
        记录审计日志

        流程:
            1. 将日志条目添加到内存列表
            2. 打印到标准日志（info 级别）
            3. 如果配置了日志文件，写入文件

        Args:
            entry: 审计日志条目
        """
        # 添加到内存列表
        self._entries.append(entry)

        # 打印到标准日志
        logger.info(
            f"[AUDIT] {entry.event_type} | {entry.method} {entry.endpoint} "
            f"| status={entry.status_code} | ip={entry.client_ip} "
            f"| detail={entry.detail}"
        )

        # 如果配置了日志文件，写入文件
        if self.log_file:
            self._write_to_file(entry)

    def _write_to_file(self, entry: AuditLogEntry):
        """
        将审计日志写入文件

        以追加模式写入，每条日志一行 JSON。

        Args:
            entry: 审计日志条目
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"写入审计日志失败: {e}")

    def get_entries(self, limit: int = 100) -> List[AuditLogEntry]:
        """
        获取最近的审计日志

        Args:
            limit: 返回日志条数（默认 100）

        Returns:
            List[AuditLogEntry]: 审计日志列表（倒序，最新的在前）
        """
        return self._entries[-limit:]


# 全局审计日志实例（默认不写入文件）
audit_logger = AuditLogger()


class InputValidator:
    """
    输入校验工具

    提供对用户输入的安全校验，防止 SQL 注入、XSS 攻击等安全威胁。

    支持的校验类型:
        1. 查询字符串校验（防止 SQL 注入、XSS）
        2. 文档引用校验（防止路径遍历）
        3. 报告标题校验（长度限制）
    """

    # SQL 注入检测模式（正则表达式）
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b.*\b(FROM|INTO|TABLE|WHERE)\b)",
        r"(--|/\*|\*/|;)",
        r"(\bOR\b\s+\b1\s*=\s*1\b)",
        r"(\bAND\b\s+\b1\s*=\s*1\b)",
    ]

    # XSS 攻击检测模式（正则表达式）
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
        """
        校验查询字符串

        检查项:
            1. 非空校验
            2. 长度限制（最大 2000 字符）
            3. SQL 注入检测
            4. XSS 攻击检测

        Args:
            query: 查询字符串

        Returns:
            tuple[bool, str]: (是否通过校验, 错误信息)
        """
        # 非空校验
        if not query or not query.strip():
            return False, "查询不能为空"

        # 长度限制
        if len(query) > cls.MAX_QUERY_LENGTH:
            return False, f"查询长度超过限制（最大 {cls.MAX_QUERY_LENGTH} 字符）"

        # SQL 注入检测
        if cls._check_patterns(query, cls.SQL_INJECTION_PATTERNS):
            return False, "查询包含潜在的 SQL 注入风险"

        # XSS 攻击检测
        if cls._check_patterns(query, cls.XSS_PATTERNS):
            return False, "查询包含潜在的 XSS 风险"

        # 校验通过
        return True, ""

    @classmethod
    def validate_doc_reference(cls, ref: str) -> tuple[bool, str]:
        """
        校验文档引用

        检查项:
            1. 非空校验
            2. 长度限制（最大 500 字符）
            3. 路径遍历检测（禁止 .. 和绝对路径）

        Args:
            ref: 文档引用字符串

        Returns:
            tuple[bool, str]: (是否通过校验, 错误信息)
        """
        # 非空校验
        if not ref:
            return False, "文档引用不能为空"

        # 长度限制
        if len(ref) > cls.MAX_DOC_REFERENCE_LENGTH:
            return False, f"文档引用长度超过限制（最大 {cls.MAX_DOC_REFERENCE_LENGTH} 字符）"

        # 路径遍历检测
        if ".." in ref or ref.startswith("/"):
            return False, "文档引用包含非法路径"

        # 校验通过
        return True, ""

    @classmethod
    def validate_report_title(cls, title: str) -> tuple[bool, str]:
        """
        校验报告标题

        检查项:
            1. 非空校验
            2. 长度限制（最大 200 字符）

        Args:
            title: 报告标题

        Returns:
            tuple[bool, str]: (是否通过校验, 错误信息)
        """
        # 非空校验
        if not title or not title.strip():
            return False, "报告标题不能为空"

        # 长度限制
        if len(title) > cls.MAX_REPORT_TITLE_LENGTH:
            return False, f"报告标题长度超过限制（最大 {cls.MAX_REPORT_TITLE_LENGTH} 字符）"

        # 校验通过
        return True, ""

    @classmethod
    def _check_patterns(cls, text: str, patterns: List[str]) -> bool:
        """
        检查文本是否匹配任何危险模式

        Args:
            text: 待检查文本
            patterns: 危险模式列表（正则表达式）

        Returns:
            bool: 是否匹配任何危险模式
        """
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False


class DataMasker:
    """
    敏感数据脱敏工具

    对银行审计过程中涉及的敏感数据进行自动脱敏处理，
    保护用户隐私和系统安全。

    支持的脱敏字段:
        - account_number: 银行账号（保留前4后4）
        - id_card: 身份证号（保留前3后4）
        - phone: 手机号（保留前3后4）
        - email: 邮箱（用户名只保留首字母）
        - password: 密码（全脱敏）
        - api_key: API Key（保留前4后4）
        - secret: 密钥（全脱敏）
        - token: Token（保留前4后4）
        - credential: 凭证（全脱敏）
    """

    # 默认敏感字段列表
    DEFAULT_SENSITIVE_FIELDS = [
        "password", "api_key", "secret", "token", "credential",
        "account_number", "id_card", "phone", "email",
    ]

    # 脱敏规则（字段名 -> 脱敏函数）
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
        """
        对数据中的敏感字段进行递归脱敏

        支持字典、列表和其他类型的数据结构。

        Args:
            data: 待脱敏的数据（支持嵌套结构）
            sensitive_fields: 敏感字段列表（可选，默认使用 DEFAULT_SENSITIVE_FIELDS）

        Returns:
            Any: 脱敏后的数据
        """
        fields = sensitive_fields or cls.DEFAULT_SENSITIVE_FIELDS

        # 递归处理字典
        if isinstance(data, dict):
            return {
                k: cls._mask_value(k, v, fields) if k.lower() in fields else cls.mask(v, fields)
                for k, v in data.items()
            }
        # 递归处理列表
        elif isinstance(data, list):
            return [cls.mask(item, fields) for item in data]
        # 其他类型直接返回
        else:
            return data

    @classmethod
    def _mask_value(cls, key: str, value: Any, fields: List[str]) -> Any:
        """
        对单个值进行脱敏

        根据字段名选择对应的脱敏规则。

        Args:
            key: 字段名
            value: 字段值
            fields: 敏感字段列表

        Returns:
            Any: 脱敏后的值
        """
        if value is None:
            return None

        key_lower = key.lower()
        # 如果有对应的脱敏规则，使用规则处理
        if key_lower in cls.MASK_RULES and isinstance(value, str):
            return cls.MASK_RULES[key_lower](value)
        # 否则使用默认脱敏（全星号）
        return "******"

    @classmethod
    def mask_account(cls, account: str) -> str:
        """
        脱敏银行账号

        保留前4位和后4位，中间用星号代替。

        Args:
            account: 银行账号

        Returns:
            str: 脱敏后的账号
        """
        if not account or len(account) <= 8:
            return "****"
        return account[:4] + "****" + account[-4:]

    @classmethod
    def mask_id_card(cls, id_card: str) -> str:
        """
        脱敏身份证号

        保留前3位和后4位，中间用星号代替。

        Args:
            id_card: 身份证号

        Returns:
            str: 脱敏后的身份证号
        """
        if not id_card or len(id_card) <= 7:
            return "****"
        return id_card[:3] + "********" + id_card[-4:]

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """
        脱敏手机号

        保留前3位和后4位，中间用星号代替。

        Args:
            phone: 手机号

        Returns:
            str: 脱敏后的手机号
        """
        if not phone or len(phone) <= 7:
            return "****"
        return phone[:3] + "****" + phone[-4:]


def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
    configured_keys: Optional[List[str]] = None,
) -> str:
    """
    API Key 认证依赖

    用于 FastAPI 的依赖注入，验证请求中的 API Key 是否有效。

    安全特性:
        - 使用恒定时间比较防止时序攻击
        - 自动记录认证成功/失败事件到审计日志

    使用方式:
        from fastapi import Depends
        @app.get("/protected", dependencies=[Depends(verify_api_key)])
        def protected():
            return {"message": "authorized"}

    Args:
        api_key: 请求头中的 API Key（由 FastAPI 自动注入）
        configured_keys: 配置的有效 API Key 列表（可选，不提供则允许所有请求）

    Returns:
        str: 脱敏后的 API Key（前8位）

    Raises:
        HTTPException: 401 错误（API Key 无效或缺失）
    """
    # 如果未配置 API Key，允许通过（开发模式）
    if not configured_keys:
        return "anonymous"

    # 如果请求中没有 API Key
    if not api_key:
        # 记录审计日志
        audit_logger.log(AuditLogEntry(
            event_type=SecurityEventType.API_KEY_REJECTED.value,
            detail="Missing API key",
            status_code=401,
        ))
        raise HTTPException(status_code=401, detail="API Key required")

    # 使用恒定时间比较验证 API Key（防止时序攻击）
    for configured in configured_keys:
        if _constant_time_compare(api_key, configured):
            # 记录审计日志
            audit_logger.log(AuditLogEntry(
                event_type=SecurityEventType.API_KEY_VALIDATED.value,
                status_code=200,
            ))
            # 返回脱敏后的 API Key（只显示前8位）
            return api_key[:8] + "****"

    # API Key 不匹配
    audit_logger.log(AuditLogEntry(
        event_type=SecurityEventType.API_KEY_REJECTED.value,
        detail="Invalid API key",
        status_code=401,
    ))
    raise HTTPException(status_code=401, detail="Invalid API Key")


def _constant_time_compare(a: str, b: str) -> bool:
    """
    恒定时间字符串比较

    防止时序攻击（Timing Attack），无论字符串是否匹配，
    比较时间都是相同的。

    Args:
        a: 待比较字符串1
        b: 待比较字符串2

    Returns:
        bool: 两个字符串是否相等
    """
    # 首先比较长度（长度不同直接返回 False）
    if len(a) != len(b):
        return False

    # 使用位运算进行逐字符比较
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)

    # 如果所有字符都相同，result 为 0
    return result == 0


def create_audit_middleware(audit_log: Optional[AuditLogger] = None):
    """
    创建审计日志中间件

    自动记录所有 HTTP 请求，包括请求方法、端点、状态码、客户端 IP 等信息。

    使用方式:
        from fastapi import FastAPI
        app = FastAPI()
        app.middleware("http")(create_audit_middleware())

    Args:
        audit_log: 审计日志记录器（可选，不提供则使用全局实例）

    Returns:
        Callable: 中间件函数
    """
    log = audit_log or audit_logger

    async def audit_middleware(request: Request, call_next):
        """
        审计中间件

        处理流程:
            1. 调用下一个中间件/路由处理函数
            2. 记录请求信息到审计日志
            3. 返回响应

        Args:
            request: FastAPI 请求对象
            call_next: 下一个处理函数

        Returns:
            Response: HTTP 响应
        """
        # 调用下一个处理函数
        response = await call_next(request)

        # 记录审计日志
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