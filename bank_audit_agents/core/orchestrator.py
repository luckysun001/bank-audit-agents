"""
智能体协调器 - 优化版

优化内容:
1. 增强任务调度的公平性
2. 添加任务超时处理
3. 完善监控指标
4. 优雅关闭机制
5. 增强错误恢复能力
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque

from bank_audit_agents.core.base_agent import (
    AgentMessage,
    AgentResult,
    AgentStatus,
    BaseAgent,
    Task,
    TaskStatus,
)
# 注意：智能体类在 register_default_agents 方法中动态导入
# 以避免循环导入问题
from bank_audit_agents.config.settings import AgentType, Settings, get_settings
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)


class OrchestratorStatus(str):
    """协调器状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class OrchestratorMetrics:
    """协调器指标收集器"""

    def __init__(self):
        self.task_queue_size_history = deque(maxlen=1000)
        self.execution_times = deque(maxlen=1000)
        self.start_time: Optional[datetime] = None

    def record_task_execution_time(self, duration: float) -> None:
        """记录任务执行时间"""
        self.execution_times.append(duration)

    def get_avg_execution_time(self) -> float:
        """获取平均执行时间"""
        if not self.execution_times:
            return 0.0
        return sum(self.execution_times) / len(self.execution_times)

    def get_p95_execution_time(self) -> float:
        """获取 P95 执行时间"""
        if not self.execution_times:
            return 0.0
        sorted_times = sorted(self.execution_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]

    def get_uptime_seconds(self) -> float:
        """获取运行时间（秒）"""
        if not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()


class AgentOrchestrator:
    """
    智能体协调器

    核心功能:
    1. 智能体生命周期管理（注册、启动、停止）
    2. 任务调度和分配（优先级队列、负载均衡）
    3. 智能体间消息路由
    4. 执行状态监控
    5. 错误处理和恢复（超时、重试）
    6. 结果汇总和整合
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

        # 智能体池
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_type_pool: Dict[str, List[str]] = {}  # 按类型分组的智能体ID

        # 任务管理
        self.task_queue: asyncio.PriorityQueue[Tuple[int, Task]] = asyncio.PriorityQueue()
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        self.task_to_agent: Dict[str, str] = {}  # 任务ID -> 智能体ID

        # 任务依赖管理
        self.task_dependencies: Dict[str, Set[str]] = {}  # task_id -> 依赖的 task_ids
        self.task_dependents: Dict[str, Set[str]] = {}    # task_id -> 依赖它的 task_ids

        # 消息总线
        self.message_bus: asyncio.Queue[AgentMessage] = asyncio.Queue()

        # 执行状态
        self.status = OrchestratorStatus.IDLE
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        self._worker_tasks: List[asyncio.Task] = []

        # 指标收集
        self.metrics = OrchestratorMetrics()

        # 统计信息
        self.stats = {
            "total_tasks_submitted": 0,
            "total_tasks_completed": 0,
            "total_tasks_failed": 0,
            "total_tasks_timeout": 0,
            "total_messages_exchanged": 0,
            "start_time": None,
        }

        # 回调函数
        self.on_task_completed: Optional[Any] = None
        self.on_task_failed: Optional[Any] = None
        self.on_message_sent: Optional[Any] = None

        logger.info("✅ 智能体协调器初始化完成")

    # =========================================================================
    # 智能体管理
    # =========================================================================

    def register_agent(self, agent: BaseAgent) -> str:
        """
        注册智能体到协调器

        Args:
            agent: 智能体实例

        Returns:
            智能体ID
        """
        agent_id = agent.agent_id
        agent_type = agent.agent_type.value

        if agent_id in self.agents:
            logger.warning(f"⚠️  智能体已注册: {agent_id}")
            return agent_id

        self.agents[agent_id] = agent

        # 按类型分组
        if agent_type not in self.agent_type_pool:
            self.agent_type_pool[agent_type] = []
        self.agent_type_pool[agent_type].append(agent_id)

        logger.info(f"✅ 智能体已注册: {agent_id} ({agent_type})")
        return agent_id

    def register_default_agents(self) -> None:
        """注册默认的审计智能体集合"""
        # 动态导入以避免循环依赖
        from bank_audit_agents.agents.document_parser import DocumentParserAgent
        from bank_audit_agents.agents.risk_identifier import RiskIdentifierAgent
        from bank_audit_agents.agents.compliance_checker import ComplianceCheckerAgent
        from bank_audit_agents.agents.quality_and_coordinator import (
            QualityAuditorAgent,
            TaskCoordinatorAgent,
        )

        default_agents = [
            DocumentParserAgent(),
            RiskIdentifierAgent(),
            ComplianceCheckerAgent(),
            QualityAuditorAgent(),
            TaskCoordinatorAgent(),
        ]

        for agent in default_agents:
            self.register_agent(agent)

        logger.info(f"✅ 已注册 {len(default_agents)} 个默认智能体")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """获取智能体实例"""
        return self.agents.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> List[BaseAgent]:
        """根据类型获取智能体列表"""
        agent_ids = self.agent_type_pool.get(agent_type, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]

    def get_idle_agent_by_type(self, agent_type: str) -> Optional[BaseAgent]:
        """获取空闲的指定类型智能体（负载均衡）"""
        agents = self.get_agents_by_type(agent_type)
        if not agents:
            return None

        # 优先选择空闲的智能体
        idle_agents = [a for a in agents if a.status == AgentStatus.IDLE]
        if idle_agents:
            # 选择任务执行最少的，实现负载均衡
            idle_agents.sort(key=lambda a: a.total_tasks_executed)
            return idle_agents[0]

        # 如果没有空闲的，返回负载最轻的
        agents.sort(key=lambda a: a.total_tasks_executed)
        return agents[0]

    def unregister_agent(self, agent_id: str) -> None:
        """注销智能体"""
        if agent_id not in self.agents:
            logger.warning(f"⚠️  智能体不存在: {agent_id}")
            return

        agent = self.agents[agent_id]
        agent_type = agent.agent_type.value

        # 从类型池中移除
        if agent_type in self.agent_type_pool:
            if agent_id in self.agent_type_pool[agent_type]:
                self.agent_type_pool[agent_type].remove(agent_id)

        del self.agents[agent_id]
        logger.info(f"🗑️  智能体已注销: {agent_id}")

    # =========================================================================
    # 任务管理
    # =========================================================================

    async def submit_task(
        self,
        task: Task,
        target_agent_type: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """
        提交任务到协调器

        Args:
            task: 任务对象
            target_agent_type: 目标智能体类型（可选）
            dependencies: 依赖的任务ID列表

        Returns:
            任务ID
        """
        task_id = task.task_id

        # 保存目标智能体类型
        if target_agent_type:
            task.metadata["target_agent_type"] = target_agent_type

        # 保存依赖关系
        if dependencies:
            self.task_dependencies[task_id] = set(dependencies)
            for dep_id in dependencies:
                if dep_id not in self.task_dependents:
                    self.task_dependents[dep_id] = set()
                self.task_dependents[dep_id].add(task_id)

        # 检查依赖是否满足
        if self._check_dependencies_satisfied(task_id):
            task.status = TaskStatus.ASSIGNED
            priority = 11 - task.priority  # 反转优先级，数字越小优先级越高
            await self.task_queue.put((priority, task))
            logger.info(f"📥 任务已加入队列: {task_id}, 优先级: {task.priority}")
        else:
            self.active_tasks[task_id] = task
            waiting_on = len(self.task_dependencies.get(task_id, set()))
            logger.info(f"⏳ 任务等待依赖: {task_id}, 等待 {waiting_on} 个任务")

        self.stats["total_tasks_submitted"] += 1
        return task_id

    async def submit_tasks_batch(
        self,
        tasks: List[Task],
        dependency_graph: Optional[Dict[str, List[str]]] = None,
    ) -> List[str]:
        """批量提交任务"""
        task_ids = []

        # 首先注册所有任务
        for task in tasks:
            self.active_tasks[task.task_id] = task

        # 设置依赖关系
        if dependency_graph:
            for task_id, deps in dependency_graph.items():
                self.task_dependencies[task_id] = set(deps)
                for dep_id in deps:
                    if dep_id not in self.task_dependents:
                        self.task_dependents[dep_id] = set()
                    self.task_dependents[dep_id].add(task_id)

        # 提交没有依赖的任务
        for task in tasks:
            if self._check_dependencies_satisfied(task.task_id):
                task.status = TaskStatus.ASSIGNED
                priority = 11 - task.priority
                await self.task_queue.put((priority, task))
                self.stats["total_tasks_submitted"] += 1
            task_ids.append(task.task_id)

        logger.info(f"📥 批量提交任务: {len(task_ids)} 个")
        return task_ids

    def _check_dependencies_satisfied(self, task_id: str) -> bool:
        """检查任务的所有依赖是否都已完成"""
        dependencies = self.task_dependencies.get(task_id, set())

        if not dependencies:
            return True  # 没有依赖，可以执行

        # 检查所有依赖是否都在已完成任务列表中
        return all(dep_id in self.completed_tasks for dep_id in dependencies)

    async def _on_task_completed(self, task: Task, result: AgentResult) -> None:
        """任务完成后的处理"""
        task_id = task.task_id

        # 移动到已完成
        self.completed_tasks[task_id] = task
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        if task_id in self.task_to_agent:
            del self.task_to_agent[task_id]

        self.stats["total_tasks_completed"] += 1
        self.metrics.record_task_execution_time(task.duration_seconds)

        logger.info(
            f"✅ 任务完成: {task_id}, 耗时: {task.duration_seconds:.2f}秒, "
            f"发现: {len(result.findings)} 项"
        )

        # 检查并唤醒依赖此任务的任务
        if task_id in self.task_dependents:
            awakened_count = 0
            for dependent_id in self.task_dependents[task_id]:
                if self._check_dependencies_satisfied(dependent_id):
                    if dependent_id in self.active_tasks:
                        dependent_task = self.active_tasks[dependent_id]
                        dependent_task.status = TaskStatus.ASSIGNED
                        priority = 11 - dependent_task.priority
                        await self.task_queue.put((priority, dependent_task))
                        awakened_count += 1

            if awakened_count > 0:
                logger.info(f"🔄 唤醒 {awakened_count} 个依赖任务")

    async def _on_task_failed(self, task: Task, error: Exception) -> None:
        """任务失败后的处理"""
        task_id = task.task_id

        # 检查是否可以重试
        if task.can_retry():
            task.mark_for_retry()
            priority = 11 - task.priority
            await self.task_queue.put((priority, task))
            logger.info(f"🔄 任务重试: {task_id}, 第 {task.retry_count} 次")
            return

        # 不能重试，标记为失败
        self.failed_tasks[task_id] = task
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        if task_id in self.task_to_agent:
            del self.task_to_agent[task_id]

        self.stats["total_tasks_failed"] += 1

        logger.error(f"❌ 任务失败: {task_id}, 错误: {str(error)}")

        # 取消所有依赖此任务的任务
        if task_id in self.task_dependents:
            for dependent_id in self.task_dependents[task_id]:
                if dependent_id in self.active_tasks:
                    dependent_task = self.active_tasks[dependent_id]
                    dependent_task.cancel(f"依赖任务 {task_id} 失败")
                    self.failed_tasks[dependent_id] = dependent_task
                    del self.active_tasks[dependent_id]
                    logger.warning(f"⛔ 依赖任务已取消: {dependent_id}")

    # =========================================================================
    # 消息总线
    # =========================================================================

    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: Dict[str, Any],
        message_type: str = "information",
    ) -> str:
        """
        发送消息到消息总线

        Args:
            sender_id: 发送者智能体ID
            receiver_id: 接收者智能体ID ('*' 表示广播)
            content: 消息内容
            message_type: 消息类型

        Returns:
            消息ID
        """
        message = AgentMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
        )

        await self.message_bus.put(message)
        self.stats["total_messages_exchanged"] += 1

        # 触发消息发送回调
        if self.on_message_sent:
            try:
                self.on_message_sent(message)
            except Exception as e:
                logger.warning(f"on_message_sent 回调执行失败: {e}")

        logger.debug(f"📤 消息已发送: {sender_id} -> {receiver_id}")
        return message.message_id

    async def _route_message(self, message: AgentMessage) -> None:
        """路由消息到目标智能体"""
        receiver_id = message.receiver_id

        # 广播消息
        if receiver_id == "*":
            for agent_id, agent in self.agents.items():
                if agent_id != message.sender_id:
                    agent.receive_message(message)
        # 点对点消息
        elif receiver_id in self.agents:
            self.agents[receiver_id].receive_message(message)
        else:
            logger.warning(f"⚠️  消息目标不存在: {receiver_id}")

    # =========================================================================
    # 工作协程
    # =========================================================================

    async def start(self) -> None:
        """启动协调器"""
        if self.is_running:
            logger.warning("⚠️  协调器已经在运行中")
            return

        self.is_running = True
        self.status = OrchestratorStatus.RUNNING
        self.metrics.start_time = datetime.now()
        self.stats["start_time"] = datetime.now()

        # 启动工作协程
        self._worker_tasks = [
            asyncio.create_task(self._task_execution_worker(), name="task-executor"),
            asyncio.create_task(self._message_routing_worker(), name="message-router"),
            asyncio.create_task(self._monitoring_worker(), name="monitor"),
            asyncio.create_task(self._timeout_worker(), name="timeout-checker"),
        ]

        logger.info("🚀 智能体协调器已启动")

    async def stop(self, wait_for_completion: bool = True) -> None:
        """停止协调器"""
        if not self.is_running:
            return

        logger.info("⏹️  正在停止协调器...")
        self.status = OrchestratorStatus.SHUTTING_DOWN

        # 等待任务完成
        if wait_for_completion:
            await self.wait_for_completion(timeout=30)

        # 设置关闭事件
        self._shutdown_event.set()

        # 取消所有工作协程
        for worker_task in self._worker_tasks:
            worker_task.cancel()

        # 等待协程结束
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        self.is_running = False
        self.status = OrchestratorStatus.STOPPED

        logger.info("✅ 协调器已停止")

    async def _task_execution_worker(self) -> None:
        """任务执行工作协程"""
        logger.debug("🔧 任务执行工作协程启动")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                # 获取任务（带超时以便检查停止信号）
                _, task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)

                # 分配智能体
                target_agent_type = task.metadata.get("target_agent_type")
                agent = self._assign_task_to_agent(task, target_agent_type)

                if agent:
                    # 执行任务
                    self.active_tasks[task.task_id] = task
                    self.task_to_agent[task.task_id] = agent.agent_id

                    logger.info(f"⚡ 开始执行任务: {task.task_id} -> {agent.agent_id}")

                    try:
                        result = await agent.run(task)

                        if result.success:
                            await self._on_task_completed(task, result)
                        else:
                            await self._on_task_failed(
                                task, Exception(result.error or "Task failed")
                            )

                    except Exception as e:
                        await self._on_task_failed(task, e)
                else:
                    logger.warning(
                        f"⚠️  没有可用的智能体处理任务: {task.task_id}, "
                        f"类型: {target_agent_type or task.task_type}"
                    )
                    # 重新入队，增加一点延迟避免忙等
                    await asyncio.sleep(0.5)
                    task.status = TaskStatus.PENDING
                    priority = 11 - task.priority
                    await self.task_queue.put((priority, task))

                self.task_queue.task_done()

            except asyncio.TimeoutError:
                # 正常超时，继续循环
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 任务执行工作协程错误: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # 避免错误风暴

        logger.debug("🔧 任务执行工作协程停止")

    async def _message_routing_worker(self) -> None:
        """消息路由工作协程"""
        logger.debug("📨 消息路由工作协程启动")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                # 获取消息
                message = await asyncio.wait_for(self.message_bus.get(), timeout=1.0)
                await self._route_message(message)
                self.message_bus.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 消息路由工作协程错误: {str(e)}", exc_info=True)
                await asyncio.sleep(1)

        logger.debug("📨 消息路由工作协程停止")

    async def _monitoring_worker(self) -> None:
        """监控工作协程"""
        logger.debug("📊 监控工作协程启动")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # 每60秒输出一次统计

                uptime = self.metrics.get_uptime_seconds()
                logger.info(
                    f"📊 协调器运行统计: 运行{int(uptime)}秒, "
                    f"提交{self.stats['total_tasks_submitted']}, "
                    f"完成{self.stats['total_tasks_completed']}, "
                    f"失败{self.stats['total_tasks_failed']}, "
                    f"队列{self.task_queue.qsize()}, "
                    f"活跃{len(self.active_tasks)}"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 监控工作协程错误: {str(e)}", exc_info=True)

        logger.debug("📊 监控工作协程停止")

    async def _timeout_worker(self) -> None:
        """超时检查工作协程"""
        logger.debug("⏱️  超时检查工作协程启动")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(10)  # 每10秒检查一次

                now = datetime.now()
                timeout_tasks = []

                for task_id, task in list(self.active_tasks.items()):
                    if task.status == TaskStatus.IN_PROGRESS and task.started_at:
                        elapsed = (now - task.started_at).total_seconds()
                        if elapsed > task.timeout_seconds:
                            timeout_tasks.append(task_id)

                for task_id in timeout_tasks:
                    task = self.active_tasks[task_id]
                    logger.warning(
                        f"⏰ 任务执行超时: {task_id}, 已运行 {task.duration_seconds:.1f}秒"
                    )
                    self.stats["total_tasks_timeout"] += 1

                    # 取消任务
                    agent_id = self.task_to_agent.get(task_id)
                    if agent_id and agent_id in self.agents:
                        agent = self.agents[agent_id]
                        agent.status = AgentStatus.IDLE

                    task.cancel("执行超时")
                    self.failed_tasks[task_id] = task
                    del self.active_tasks[task_id]
                    if task_id in self.task_to_agent:
                        del self.task_to_agent[task_id]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 超时检查工作协程错误: {str(e)}", exc_info=True)

        logger.debug("⏱️  超时检查工作协程停止")

    def _assign_task_to_agent(
        self,
        task: Task,
        target_agent_type: Optional[str] = None,
    ) -> Optional[BaseAgent]:
        """将任务分配给合适的智能体"""
        # 如果指定了智能体类型，优先使用该类型
        if target_agent_type:
            agent = self.get_idle_agent_by_type(target_agent_type)
            if agent:
                return agent

        # 根据任务类型自动匹配
        task_type_mapping = {
            "document": AgentType.DOCUMENT_PARSER.value,
            "parse": AgentType.DOCUMENT_PARSER.value,
            "risk": AgentType.RISK_IDENTIFIER.value,
            "compliance": AgentType.COMPLIANCE_CHECKER.value,
            "aml": AgentType.COMPLIANCE_CHECKER.value,
            "report": "report_writer",  # 报告智能体类型
            "quality": "quality_auditor",
        }

        task_type_lower = task.task_type.lower()
        for keyword, agent_type in task_type_mapping.items():
            if keyword in task_type_lower:
                agent = self.get_idle_agent_by_type(agent_type)
                if agent:
                    return agent

        # 默认使用风险识别智能体
        return self.get_idle_agent_by_type(AgentType.RISK_IDENTIFIER.value)

    # =========================================================================
    # 状态查询
    # =========================================================================

    async def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """等待所有任务完成"""
        start_time = asyncio.get_event_loop().time()

        while self.is_running and (
            self.task_queue.qsize() > 0 or len(self.active_tasks) > 0
        ):
            await asyncio.sleep(0.1)

            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    logger.warning("⏰ 等待任务完成超时")
                    break

    def get_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        uptime = self.metrics.get_uptime_seconds()

        # 智能体状态统计
        agent_status_stats: Dict[str, int] = {}
        for agent in self.agents.values():
            status = agent.status.value
            agent_status_stats[status] = agent_status_stats.get(status, 0) + 1

        return {
            "status": self.status,
            "is_running": self.is_running,
            "agents_count": len(self.agents),
            "queue_size": self.task_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "uptime_seconds": round(uptime, 2),
            "agents": {
                "total_count": len(self.agents),
                "by_status": agent_status_stats,
                "by_type": {k: len(v) for k, v in self.agent_type_pool.items()},
                "details": {
                    agent_id: agent.get_status_info()
                    for agent_id, agent in self.agents.items()
                },
            },
            "tasks": {
                "queue_size": self.task_queue.qsize(),
                "active_count": len(self.active_tasks),
                "completed_count": len(self.completed_tasks),
                "failed_count": len(self.failed_tasks),
            },
            "performance": {
                "avg_execution_time": round(self.metrics.get_avg_execution_time(), 2),
                "p95_execution_time": round(self.metrics.get_p95_execution_time(), 2),
            },
            "statistics": self.stats.copy(),
        }

    def get_results(self) -> Dict[str, Any]:
        """获取所有任务的执行结果摘要"""
        return {
            "completed": {
                task_id: task.to_dict()
                for task_id, task in list(self.completed_tasks.items())[-100:]
            },
            "failed": {
                task_id: task.to_dict()
                for task_id, task in list(self.failed_tasks.items())[-100:]
            },
            "pending": {
                task_id: task.to_dict()
                for task_id, task in self.active_tasks.items()
            },
            "queue_size": self.task_queue.qsize(),
        }

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务的结果"""
        if task_id in self.completed_tasks:
            return {"status": "completed", "task": self.completed_tasks[task_id].to_dict()}
        elif task_id in self.failed_tasks:
            return {"status": "failed", "task": self.failed_tasks[task_id].to_dict()}
        elif task_id in self.active_tasks:
            return {"status": "active", "task": self.active_tasks[task_id].to_dict()}
        return None
