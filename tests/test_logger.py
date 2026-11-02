"""日志工具测试：JSONFormatter、get_logger、log_with_context。"""

import json
import logging
import sys

from bank_audit_agents.utils.logger import (
    JSONFormatter,
    get_logger,
    log_with_context,
)


def test_json_formatter_basic_fields():
    fmt = JSONFormatter()
    rec = logging.LogRecord("test", logging.INFO, "path", 1, "hello world", None, None)
    out = json.loads(fmt.format(rec))
    assert out["message"] == "hello world"
    assert out["level"] == "INFO"
    assert out["logger"] == "test"


def test_json_formatter_includes_extra_fields():
    fmt = JSONFormatter()
    rec = logging.LogRecord("test", logging.INFO, "path", 1, "msg", None, None)
    rec.agent_id = "agent-1"
    rec.task_id = "task-9"
    out = json.loads(fmt.format(rec))
    assert out["agent_id"] == "agent-1"
    assert out["task_id"] == "task-9"


def test_json_formatter_includes_exception():
    fmt = JSONFormatter()
    try:
        1 / 0
    except ZeroDivisionError:
        rec = logging.LogRecord("test", logging.ERROR, "path", 1, "boom", None, sys.exc_info())
    out = json.loads(fmt.format(rec))
    # 异常字段记录的是 traceback，而非业务 message
    assert "ZeroDivisionError" in out["exception"]
    # 业务 message 单独记录
    assert out["message"] == "boom"


def test_get_logger_respects_level():
    logger = get_logger("test_logger_level", level="DEBUG")
    assert logger.level == logging.DEBUG
    logger2 = get_logger("test_logger_level_warn", level="WARNING")
    assert logger2.level == logging.WARNING


def test_get_logger_does_not_duplicate_handlers():
    logger = get_logger("test_logger_dedup", level="INFO")
    n_before = len(logger.handlers)
    # 再次以相同 name 获取不应重复添加处理器
    logger_again = get_logger("test_logger_dedup", level="INFO")
    assert logger_again is logger
    assert len(logger.handlers) == n_before


def test_log_with_context_attaches_extra():
    logger = get_logger("test_logger_ctx", level="INFO", log_format="json")
    captured = []
    handler = logging.Handler()
    handler.emit = lambda r: captured.append(r)
    logger.addHandler(handler)

    log_with_context(logger, "info", "事件", agent_id="a1", task_id="t1", custom="x")

    assert len(captured) == 1
    rec = captured[0]
    assert rec.getMessage() == "事件"
    assert rec.agent_id == "a1"
    assert rec.task_id == "t1"
    # 任意 kwargs 也作为 extra 透传
    assert rec.custom == "x"


def test_log_with_context_missing_optional_extra():
    logger = get_logger("test_logger_ctx2", level="INFO")
    captured = []
    handler = logging.Handler()
    handler.emit = lambda r: captured.append(r)
    logger.addHandler(handler)

    # agent_id / task_id 不传时不应出现在 record 上
    log_with_context(logger, "warning", "no ctx")
    rec = captured[0]
    assert not hasattr(rec, "agent_id")
    assert not hasattr(rec, "task_id")
