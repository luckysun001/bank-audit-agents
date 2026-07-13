"""
智能体基类和核心抽象 - 优化版

优化内容:
1. 完善 AgentResult 的字段，添加 output_data
2. 增强类型提示的准确性
3. 添加更多的错误处理
4. 优化回调机制的类型安全
5. 添加验证方法
"""

import uuid
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict

from bank_audit_agents.config.settings import Settings, AgentType, get_settings
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    """智能体状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# 回调函数类型别名
TaskCallback = Callable[["Task"], None]
TaskResultCallback = Callable[["Task", "AgentResult"], None]
TaskErrorCallback = Callable[["Task", Exception], None]
MessageCallback = Callable[["AgentMessage"], None]


@dataclass
class AgentMessage:
    """智能体间通信消息"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    message_type: str = "information"  # information, request, response, command, error
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    references: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "references": self.references,
            "metadata": self.metadata,
        }

    @classmethod
    def create_request(
        cls,
        sender_id: str,
        receiver_id: str,
        request_type: str,
        payload: Dict[str, Any],
    ) -> "AgentMessage":
        """创建请求消息"""
        return cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="request",
            content={
                "request_type": request_type,
                "payload": payload,
            },
        )

    @classmethod
    def create_response(
        cls,
        sender_id: str,
        receiver_id: str,
        request_id: str,
        payload: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
    ) -> "AgentMessage":
        """创建响应消息"""
        return cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="response",
            content={
                "request_id": request_id,
                "success": success,
                "payload": payload,
                "error": error,
            },
            references=[request_id],
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """验证消息完整性"""
        errors = []
        if not self.sender_id:
            errors.append("sender_id 不能为空")
        if not self.receiver_id:
            errors.append("receiver_id 不能为空")
        if self.message_type not in ["information", "request", "response", "command", "error"]:
            errors.append(f"无效的 message_type: {self.message_type}")
        return len(errors) == 0, errors


@dataclass
class Task:
    """任务对象"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    description: str = ""
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10, 10最高
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_count: int = 0

    def start(self) -> None:
        """标记任务开始"""
        if self.status not in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
            logger.warning(f"任务 {self.task_id} 状态为 {self.status}，无法开始")
            return
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, output_data: Optional[Dict[str, Any]] = None) -> None:
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if output_data is not None:
            self.output_data = output_data

    def fail(self, error_message: str) -> None:
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message

    def cancel(self, reason: str = "cancelled by user") -> None:
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.error_message = reason

    def can_retry(self) -> bool:
        """判断任务是否可以重试"""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED

    def mark_for_retry(self) -> None:
        """标记任务为重试"""
        if self.can_retry():
            self.retry_count += 1
            self.status = TaskStatus.PENDING
            self.error_message = None
            logger.info(f"任务 {self.task_id} 准备第 {self.retry_count} 次重试")

    @property
    def duration_seconds(self) -> float:
        """获取任务执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def is_finished(self) -> bool:
        """任务是否已结束（完成、失败、取消、超时）"""
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        ]

    @property
    def is_runnable(self) -> bool:
        """任务是否可执行"""
        return self.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }

    def validate(self) -> Tuple[bool, List[str]]:
        """验证任务完整性"""
        errors = []
        if not self.task_type:
            errors.append("task_type 不能为空")
        if not self.description:
            errors.append("description 不能为空")
        if self.priority < 1 or self.priority > 10:
            errors.append(f"priority 必须在 1-10 之间，当前值: {self.priority}")
        return len(errors) == 0, errors

    def __lt__(self, other: "Task") -> bool:
        """支持 PriorityQueue 中的任务比较"""
        return self.task_id < other.task_id


@dataclass
class AgentResult:
    """智能体执行结果"""
    agent_id: str
    agent_type: str
    success: bool
    summary: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    output_data: Dict[str, Any] = field(default_factory=dict)  # 新增：结构化输出
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)  # 新增：警告信息

    def add_finding(self, finding: Dict[str, Any]) -> None:
        """添加发现项"""
        self.findings.append(finding)

    def add_recommendation(self, recommendation: str) -> None:
        """添加建议"""
        self.recommendations.append(recommendation)

    def add_warning(self, warning: str) -> None:
        """添加警告"""
        self.warnings.append(warning)

    def merge(self, other: "AgentResult") -> None:
        """合并另一个结果"""
        self.findings.extend(other.findings)
        self.recommendations.extend(other.recommendations)
        self.warnings.extend(other.warnings)
        self.output_data.update(other.output_data)
        self.metadata.update(other.metadata)
        self.confidence_score = min(self.confidence_score, other.confidence_score)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "success": self.success,
            "summary": self.summary,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "recommendations_count": len(self.recommendations),
            "recommendations": self.recommendations,
            "output_data": self.output_data,
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
            "confidence_score": self.confidence_score,
            "warnings": self.warnings,
            "has_warnings": len(self.warnings) > 0,
        }


class BaseAgent(ABC):
    """
    审计智能体基类
    所有具体审计智能体都继承自此基类
    """

    def __init__(
        self,
        agent_type: AgentType,
        agent_id: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        self.agent_type = agent_type
        self.agent_id = agent_id or f"{agent_type.value}_{uuid.uuid4().hex[:8]}"
        self.settings = settings or get_settings()

        # 智能体状态
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None

        # 消息队列
        self.inbox: List[AgentMessage] = []
        self.outbox: List[AgentMessage] = []

        # 执行统计
        self.total_tasks_executed = 0
        self.total_execution_time = 0.0
        self.total_tasks_failed = 0

        # 内存和上下文
        self.conversation_history: List[Any] = []
        self.knowledge_context: Dict[str, Any] = {}

        # 回调函数
        self.on_task_start: Optional[TaskCallback] = None
        self.on_task_complete: Optional[TaskResultCallback] = None
        self.on_task_fail: Optional[TaskErrorCallback] = None
        self.on_message_sent: Optional[MessageCallback] = None
        self.on_message_received: Optional[MessageCallback] = None

        logger.info(f"✅ 智能体初始化完成: {self.agent_id} ({agent_type.value})")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取智能体的系统提示词"""
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """获取智能体可用的工具列表"""
        pass

    @abstractmethod
    async def execute(self, task: Task) -> AgentResult:
        """
        执行任务的核心方法
        所有子类必须实现此方法

        Args:
            task: 要执行的任务对象

        Returns:
            AgentResult: 执行结果
        """
        pass

    async def run(self, task: Task) -> AgentResult:
        """
        运行任务（带状态管理和错误处理的包装方法）

        Args:
            task: 要执行的任务

        Returns:
            AgentResult: 执行结果
        """
        start_time = time.time()
        self.current_task = task
        self.status = AgentStatus.RUNNING

        logger.info(f"🚀 智能体开始执行任务: {self.agent_id}, 任务: {task.task_id}")

        # 验证任务
        is_valid, errors = task.validate()
        if not is_valid:
            error_msg = f"任务验证失败: {', '.join(errors)}"
            logger.error(f"❌ {error_msg}")
            task.fail(error_msg)
            self.status = AgentStatus.FAILED
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary=error_msg,
                error=error_msg,
                execution_time_seconds=time.time() - start_time,
            )

        # 触发开始回调
        if self.on_task_start:
            try:
                self.on_task_start(task)
            except Exception as e:
                logger.warning(f"on_task_start 回调执行失败: {e}")

        try:
            task.start()

            # 执行具体任务逻辑
            result = await self.execute(task)

            # 记录执行时间
            execution_time = time.time() - start_time
            result.execution_time_seconds = execution_time
            self.total_execution_time += execution_time
            self.total_tasks_executed += 1

            task.complete(result.output_data)

            logger.info(
                f"✅ 任务完成: {self.agent_id}, 任务: {task.task_id}, "
                f"耗时: {execution_time:.2f}秒, 置信度: {result.confidence_score:.2f}"
            )

            # 触发完成回调
            if self.on_task_complete:
                try:
                    self.on_task_complete(task, result)
                except Exception as e:
                    logger.warning(f"on_task_complete 回调执行失败: {e}")

            self.status = AgentStatus.COMPLETED
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            self.total_tasks_failed += 1
            error_msg = str(e)

            logger.error(
                f"❌ 任务执行失败: {self.agent_id}, 任务: {task.task_id}, "
                f"错误: {error_msg}, 耗时: {execution_time:.2f}秒"
            )

            task.fail(error_msg)

            error_result = AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary=f"任务执行失败: {error_msg}",
                error=error_msg,
                execution_time_seconds=execution_time,
            )

            # 触发失败回调
            if self.on_task_fail:
                try:
                    self.on_task_fail(task, e)
                except Exception as callback_error:
                    logger.warning(f"on_task_fail 回调执行失败: {callback_error}")

            self.status = AgentStatus.FAILED
            return error_result

    def send_message(
        self,
        receiver_id: str,
        content: Dict[str, Any],
        message_type: str = "information",
    ) -> str:
        """
        向其他智能体发送消息

        Args:
            receiver_id: 接收者智能体ID
            content: 消息内容
            message_type: 消息类型

        Returns:
            消息ID
        """
        message = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
        )

        # 验证消息
        is_valid, errors = message.validate()
        if not is_valid:
            logger.warning(f"消息验证失败: {errors}")

        self.outbox.append(message)

        logger.debug(f"📤 智能体发送消息: {self.agent_id} -> {receiver_id}, 类型: {message_type}")

        if self.on_message_sent:
            try:
                self.on_message_sent(message)
            except Exception as e:
                logger.warning(f"on_message_sent 回调执行失败: {e}")

        return message.message_id

    def receive_message(self, message: AgentMessage) -> None:
        """
        接收消息

        Args:
            message: 收到的消息
        """
        self.inbox.append(message)

        logger.debug(f"📥 智能体收到消息: {self.agent_id} <- {message.sender_id}, 类型: {message.message_type}")

        if self.on_message_received:
            try:
                self.on_message_received(message)
            except Exception as e:
                logger.warning(f"on_message_received 回调执行失败: {e}")

    def get_unread_messages(self) -> List[AgentMessage]:
        """获取所有未读消息（并清空收件箱）"""
        messages = self.inbox.copy()
        self.inbox.clear()
        return messages

    def get_latest_message(self) -> Optional[AgentMessage]:
        """获取最新的一条消息（不移除）"""
        return self.inbox[-1] if self.inbox else None

    def add_to_conversation(self, message: Any) -> None:
        """添加对话历史记录"""
        self.conversation_history.append(message)
        # 保留最近 100 条消息
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]

    def clear_conversation(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info(f"🧹 智能体 {self.agent_id} 对话历史已清空")

    def add_knowledge(self, key: str, value: Any) -> None:
        """添加知识库内容"""
        self.knowledge_context[key] = value

    def add_knowledge_batch(self, knowledge: Dict[str, Any]) -> None:
        """批量添加知识"""
        self.knowledge_context.update(knowledge)

    def get_knowledge(self, key: str, default: Any = None) -> Any:
        """获取知识库内容"""
        return self.knowledge_context.get(key, default)

    def remove_knowledge(self, key: str) -> None:
        """移除知识库内容"""
        self.knowledge_context.pop(key, None)

    def clear_knowledge(self) -> None:
        """清空知识库"""
        self.knowledge_context.clear()
        logger.info(f"🧹 智能体 {self.agent_id} 知识库已清空")

    def get_status_info(self) -> Dict[str, Any]:
        """获取智能体状态信息"""
        avg_time = (
            self.total_execution_time / self.total_tasks_executed
            if self.total_tasks_executed > 0
            else 0
        )
        success_rate = (
            self.total_tasks_executed / (self.total_tasks_executed + self.total_tasks_failed)
            if (self.total_tasks_executed + self.total_tasks_failed) > 0
            else 1.0
        )

        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "total_tasks_executed": self.total_tasks_executed,
            "inbox_count": len(self.inbox),
            "current_task_id": self.current_task.task_id if self.current_task else None,
            "statistics": {
                "total_tasks_executed": self.total_tasks_executed,
                "total_tasks_failed": self.total_tasks_failed,
                "total_execution_time": round(self.total_execution_time, 2),
                "average_execution_time": round(avg_time, 2),
                "success_rate": round(success_rate, 2),
            },
            "message_queues": {
                "inbox_count": len(self.inbox),
                "outbox_count": len(self.outbox),
            },
            "memory": {
                "conversation_history_length": len(self.conversation_history),
                "knowledge_entries": len(self.knowledge_context),
            },
        }

    def reset(self) -> None:
        """重置智能体状态"""
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.inbox.clear()
        self.outbox.clear()
        self.conversation_history.clear()
        # 注意：不清除 knowledge_context，保留积累的知识
        logger.info(f"🔄 智能体已重置: {self.agent_id}")

    def health_check(self) -> Tuple[bool, Dict[str, Any]]:
        """健康检查"""
        is_healthy = True
        details = {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "is_idle": self.status == AgentStatus.IDLE,
            "has_pending_messages": len(self.inbox) > 0,
        }

        # 检查是否长时间运行
        if self.status == AgentStatus.RUNNING and self.current_task:
            running_time = (datetime.now() - self.current_task.started_at).total_seconds()
            details["running_time_seconds"] = running_time
            if running_time > 600:  # 超过10分钟
                is_healthy = False
                details["warning"] = "任务执行时间过长"

        return is_healthy, details

    def __str__(self) -> str:
        return f"<BaseAgent id={self.agent_id} type={self.agent_type.value} status={self.status.value}>"

    def __repr__(self) -> str:
        return self.__str__()
