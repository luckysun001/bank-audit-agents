"""
日志工具模块

提供统一的日志记录功能，支持文本和 JSON 两种格式。

核心功能:
    1. 可配置的日志记录器
    2. JSON 格式日志输出（便于日志分析系统处理）
    3. 文本格式日志输出（便于开发调试）
    4. 支持自定义上下文信息（agent_id, task_id）
    5. 支持控制台和文件双输出

设计思想:
    - 支持多种日志格式，适应不同场景
    - 避免重复添加处理器
    - 支持自定义上下文，方便追踪问题

使用示例:
    # 获取日志记录器
    logger = get_logger(__name__)

    # 记录不同级别的日志
    logger.debug("调试信息")
    logger.info("普通信息")
    logger.warning("警告信息")
    logger.error("错误信息")

    # 记录带上下文的日志
    log_with_context(logger, "info", "任务完成", agent_id="agent_001", task_id="task_001")
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    JSON 格式日志格式化器

    将日志记录转换为 JSON 格式，便于日志分析系统处理。

    输出字段:
        - timestamp: 时间戳（UTC）
        - level: 日志级别
        - logger: 日志记录器名称
        - message: 日志消息
        - exception: 异常信息（可选）
        - agent_id: 智能体 ID（可选）
        - task_id: 任务 ID（可选）
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        Args:
            record: 日志记录对象

        Returns:
            str: JSON 格式的日志字符串
        """
        # 基础日志记录字段
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加异常信息（如果有）
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # 添加自定义上下文信息
        if hasattr(record, "agent_id"):
            log_record["agent_id"] = record.agent_id
        if hasattr(record, "task_id"):
            log_record["task_id"] = record.task_id

        # 返回 JSON 字符串（确保中文不转义）
        return json.dumps(log_record, ensure_ascii=False)


def get_logger(
    name: str,
    level: str = "INFO",
    log_format: str = "text",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    获取配置好的日志记录器

    核心流程:
        1. 获取或创建日志记录器
        2. 设置日志级别
        3. 避免重复添加处理器
        4. 创建格式器（文本或 JSON）
        5. 添加控制台处理器
        6. 添加文件处理器（如果指定）

    Args:
        name: 日志记录器名称（通常使用 __name__）
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_format: 日志格式（text 或 json）
        log_file: 日志文件路径（可选，不指定则只输出到控制台）

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 获取或创建日志记录器
    logger = logging.getLogger(name)

    # 设置日志级别
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加处理器（如果已配置，直接返回）
    if logger.handlers:
        return logger

    # 创建格式器
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        # 文本格式（默认）
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 创建文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# 默认日志实例（模块级别）
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

    将智能体 ID、任务 ID 等上下文信息添加到日志中，
    便于追踪问题和审计。

    Args:
        logger: 日志记录器
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        message: 日志消息
        agent_id: 智能体 ID（可选）
        task_id: 任务 ID（可选）
        **kwargs: 其他上下文信息（会添加到 extra 中）
    """
    # 构建 extra 字典（用于传递上下文信息）
    extra = {}
    if agent_id:
        extra["agent_id"] = agent_id
    if task_id:
        extra["task_id"] = task_id
    # 添加其他自定义上下文信息
    extra.update(kwargs)

    # 获取对应的日志方法
    log_method = getattr(logger, level.lower(), logger.info)

    # 记录日志（传递 extra 参数）
    log_method(message, extra=extra)