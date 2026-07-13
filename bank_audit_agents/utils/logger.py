"""
日志工具模块
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加异常信息
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # 添加额外的字段
        if hasattr(record, "agent_id"):
            log_record["agent_id"] = record.agent_id
        if hasattr(record, "task_id"):
            log_record["task_id"] = record.task_id

        return json.dumps(log_record, ensure_ascii=False)


def get_logger(
    name: str,
    level: str = "INFO",
    log_format: str = "text",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    获取配置好的日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式 (text, json)
        log_file: 日志文件路径（可选）

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 创建格式器
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# 默认日志实例
default_logger = get_logger("bank_audit_agents")


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    **kwargs,
):
    """
    记录带上下文信息的日志

    Args:
        logger: 日志记录器
        level: 日志级别
        message: 日志消息
        agent_id: 智能体 ID（可选）
        task_id: 任务 ID（可选）
        **kwargs: 其他上下文信息
    """
    extra = {}
    if agent_id:
        extra["agent_id"] = agent_id
    if task_id:
        extra["task_id"] = task_id
    extra.update(kwargs)

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra)
