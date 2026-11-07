"""安全模块测试：输入校验、敏感数据脱敏、审计日志、API Key 认证。

这些函数都是纯逻辑、不依赖网络，直接用确定性输入断言行为。
"""

import json

import pytest

from bank_audit_agents.utils import security
from bank_audit_agents.utils.security import (
    AuditLogEntry,
    AuditLogger,
    DataMasker,
    InputValidator,
    SecurityEventType,
    _constant_time_compare,
    create_audit_middleware,
    verify_api_key,
)

# ---------------------------------------------------------------------------
# 输入校验 InputValidator
# ---------------------------------------------------------------------------


def test_validate_query_rejects_empty():
    ok, msg = InputValidator.validate_query("")
    assert ok is False
    assert "不能为空" in msg

    ok, msg = InputValidator.validate_query("   ")
    assert ok is False


def test_validate_query_rejects_too_long():
    ok, msg = InputValidator.validate_query("a" * (InputValidator.MAX_QUERY_LENGTH + 1))
    assert ok is False
    assert "长度" in msg


def test_validate_query_rejects_sql_injection():
    for payload in [
        "SELECT * FROM users WHERE 1=1",
        "DROP TABLE audit",
        "x' OR '1'='1'",
        "union select password from admin",
    ]:
        ok, msg = InputValidator.validate_query(payload)
        assert ok is False, payload
        assert "SQL" in msg


def test_validate_query_rejects_xss():
    for payload in [
        "<script>alert(1)</script>",
        "javascript:void(0)",
        '<img src=x onerror="alert(1)">',
        "<iframe src='evil'></iframe>",
    ]:
        ok, msg = InputValidator.validate_query(payload)
        assert ok is False, payload
        assert "XSS" in msg


def test_validate_query_accepts_normal_text():
    ok, msg = InputValidator.validate_query("请核查客户 张三 的授信额度")
    assert ok is True
    assert msg == ""


def test_validate_doc_reference_rejects_traversal():
    assert InputValidator.validate_doc_reference("../secret.txt")[0] is False
    assert InputValidator.validate_doc_reference("/etc/passwd")[0] is False
    assert InputValidator.validate_doc_reference("")[0] is False


def test_validate_doc_reference_accepts_relative():
    ok, msg = InputValidator.validate_doc_reference("reports/2024/loan.docx")
    assert ok is True


def test_validate_report_title():
    assert InputValidator.validate_report_title("")[0] is False
    assert InputValidator.validate_report_title("a" * 201)[0] is False
    assert InputValidator.validate_report_title("2024年度信贷审计报告")[0] is True


def test_validate_query_is_case_insensitive():
    # 大写关键字也应被识别（_check_patterns 内部 lower）
    ok, _ = InputValidator.validate_query("SELECT password FROM users")
    assert ok is False


# ---------------------------------------------------------------------------
# 敏感数据脱敏 DataMasker
# ---------------------------------------------------------------------------


def test_mask_account_number():
    assert DataMasker.mask_account("6222021234567890123") == "6222****0123"
    assert DataMasker.mask_account("123") == "****"


def test_mask_id_card():
    assert DataMasker.mask_id_card("110101199003071234") == "110********1234"
    assert DataMasker.mask_id_card("123") == "****"


def test_mask_phone():
    assert DataMasker.mask_phone("13800138000") == "138****8000"
    assert DataMasker.mask_phone("123") == "****"


def test_mask_email():
    # 邮箱脱敏通过通用 mask 走 MASK_RULES 中的 "email" 规则
    out = DataMasker.mask({"email": "alice@example.com"})
    assert out["email"] == "a***@example.com"
    assert DataMasker.mask({"email": "noatsign"})["email"] == "****"


def test_mask_dict_recurses_and_masks_sensitive_keys():
    data = {
        "username": "zhangsan",
        "password": "s3cret",
        "nested": {"token": "abcdefghij", "note": "普通文本"},
        "items": [{"api_key": "ABCDEFGHIJKL"}, {"x": 1}],
    }
    masked = DataMasker.mask(data)
    assert masked["password"] == "******"
    assert masked["username"] == "zhangsan"  # 非敏感，保持不变
    assert masked["nested"]["token"] == "abcd****ghij"
    assert masked["nested"]["note"] == "普通文本"
    assert masked["items"][0]["api_key"] == "ABCD****IJKL"
    assert masked["items"][1]["x"] == 1


def test_mask_uses_custom_fields():
    data = {"custom_secret": "abcdefgh"}
    out = DataMasker.mask(data, sensitive_fields=["custom_secret"])
    # 自定义敏感字段若没有专属脱敏规则，则整体掩码
    assert out["custom_secret"] == "******"


def test_mask_non_dict_passthrough():
    assert DataMasker.mask("plain") == "plain"
    assert DataMasker.mask(123) == 123


# ---------------------------------------------------------------------------
# 审计日志 AuditLogger
# ---------------------------------------------------------------------------


def test_audit_logger_records_entries():
    log = AuditLogger()
    log.log(AuditLogEntry(event_type="api_key_validated", status_code=200))
    entries = log.get_entries()
    assert len(entries) == 1
    assert entries[0].event_type == "api_key_validated"


def test_audit_logger_writes_file(tmp_path):
    f = tmp_path / "audit.log"
    log = AuditLogger(log_file=str(f))
    log.log(AuditLogEntry(event_type="input_validation_failed", detail="注入尝试"))
    content = f.read_text(encoding="utf-8").strip()
    parsed = json.loads(content)
    assert parsed["event_type"] == "input_validation_failed"
    assert parsed["detail"] == "注入尝试"


def test_audit_log_entry_to_dict():
    e = AuditLogEntry(event_type="x", method="POST", endpoint="/api")
    d = e.to_dict()
    assert d["event_type"] == "x"
    assert d["method"] == "POST"
    assert "timestamp" in d


# ---------------------------------------------------------------------------
# API Key 认证 verify_api_key
# ---------------------------------------------------------------------------


def test_verify_api_key_dev_mode_allows_when_unconfigured():
    # 未配置任何 key 时，无论传入什么都是 anonymous（开发模式）
    assert verify_api_key(api_key="anything", configured_keys=[]) == "anonymous"
    assert verify_api_key(api_key=None, configured_keys=[]) == "anonymous"


def test_verify_api_key_rejects_missing():
    with pytest.raises(Exception):  # HTTPException 401
        verify_api_key(configured_keys=["k-valid"])


def test_verify_api_key_accepts_valid():
    result = verify_api_key(api_key="k-valid-secret", configured_keys=["k-valid-secret"])
    assert result == "k-valid-****"
    # 审计日志应记录验证成功
    last = audit_logger_last()
    assert last.event_type == SecurityEventType.API_KEY_VALIDATED.value


def test_verify_api_key_rejects_invalid():
    with pytest.raises(Exception):
        verify_api_key(api_key="wrong", configured_keys=["k-valid-secret"])


def audit_logger_last():
    entries = security.audit_logger.get_entries(limit=1)
    return entries[-1] if entries else None


# ---------------------------------------------------------------------------
# 恒定时间比较
# ---------------------------------------------------------------------------


def test_constant_time_compare():
    assert _constant_time_compare("abc", "abc") is True
    assert _constant_time_compare("abc", "abd") is False
    assert _constant_time_compare("abc", "abcd") is False  # 长度不同
    assert _constant_time_compare("", "") is True


# ---------------------------------------------------------------------------
# 审计中间件
# ---------------------------------------------------------------------------


class _FakeClient:
    host = "127.0.0.1"


class _FakeRequest:
    def __init__(self, path="/x", method="GET", params=None):
        self.url = type("U", (), {"path": path})()
        self.method = method
        self.query_params = params or {}
        self.client = _FakeClient()


class _FakeResponse:
    def __init__(self, status=200):
        self.status_code = status


def test_audit_middleware_logs_request():
    log = AuditLogger()
    mw = create_audit_middleware(log)

    async def call_next(req):
        return _FakeResponse(201)

    import asyncio

    resp = asyncio.run(mw(_FakeRequest(path="/api/v1/query", method="POST"), call_next))
    assert resp.status_code == 201
    entries = log.get_entries()
    assert len(entries) == 1
    assert entries[0].endpoint == "/api/v1/query"
    assert entries[0].method == "POST"
    assert entries[0].status_code == 201
    assert entries[0].client_ip == "127.0.0.1"
