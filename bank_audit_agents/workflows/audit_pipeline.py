"""
审计工作流编排系统

负责定义和执行各种标准化的审计工作流程。

核心组件:
    1. WorkflowStatus - 工作流状态枚举
    2. WorkflowStep - 工作流步骤数据类
    3. WorkflowResult - 工作流执行结果数据类
    4. WorkflowTemplate - 工作流模板抽象基类
    5. WorkflowExecutor - 工作流执行器
    6. AuditPipeline - 审计流水线（高层API）

预定义工作流模板:
    - CreditAuditWorkflow: 信贷审计工作流
    - ComplianceAuditWorkflow: 合规审计工作流
    - FinancialAuditWorkflow: 财务审计工作流

工作流执行流程:
    1. 注册工作流模板
    2. 创建工作流实例
    3. 执行工作流步骤（按依赖顺序）
    4. 聚合步骤结果
    5. 生成最终报告

使用示例:
    pipeline = AuditPipeline()
    result = await pipeline.run_credit_audit(
        loan_documents=["loan_contract.pdf"],
        audited_unit="某某科技有限公司",
    )
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict

from bank_audit_agents.core.base_agent import Task, TaskStatus
from bank_audit_agents.core.orchestrator import AgentOrchestrator
from bank_audit_agents.config.settings import WorkflowType
from bank_audit_agents.utils.logger import get_logger

# 获取模块级日志记录器
logger = get_logger(__name__)


class WorkflowStatus(str):
    """
    工作流状态枚举

    定义工作流在生命周期中的各种状态。

    状态转换流程:
        CREATED → RUNNING → COMPLETED
                         → FAILED
                         → CANCELLED
    """
    CREATED = "created"      # 已创建，尚未开始执行
    RUNNING = "running"      # 正在执行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class WorkflowStep:
    """
    工作流步骤数据类

    表示工作流中的一个执行步骤，包含步骤的基本信息和执行配置。

    字段说明:
        step_id: 步骤唯一标识
        step_name: 步骤名称
        description: 步骤描述
        task_type: 任务类型
        target_agent_type: 目标智能体类型（由哪个智能体执行）
        depends_on: 依赖的步骤ID列表（步骤执行顺序控制）
        input_mapping: 输入映射（上一步输出 -> 这一步输入）
        required: 是否为必需步骤（必需步骤失败会导致工作流失败）
        retry_count: 当前重试次数
        max_retries: 最大重试次数
    """
    step_id: str
    step_name: str
    description: str
    task_type: str
    target_agent_type: str
    depends_on: List[str] = field(default_factory=list)
    input_mapping: Dict[str, str] = field(default_factory=dict)
    required: bool = True
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """
        将步骤转换为字典格式

        Returns:
            Dict[str, Any]: 步骤字典表示
        """
        return asdict(self)


@dataclass
class WorkflowResult:
    """
    工作流执行结果数据类

    存储工作流执行的完整结果信息。

    字段说明:
        workflow_id: 工作流唯一标识
        workflow_name: 工作流名称
        success: 是否执行成功
        status: 工作流状态
        start_time: 开始时间
        end_time: 结束时间
        step_results: 各步骤执行结果
        aggregated_findings: 聚合后的发现列表
        final_report: 最终报告
        error_message: 错误信息（如果失败）
        metadata: 元数据
    """
    workflow_id: str
    workflow_name: str
    success: bool
    status: WorkflowStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    step_results: Dict[str, Any] = field(default_factory=dict)
    aggregated_findings: List[Dict[str, Any]] = field(default_factory=list)
    final_report: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """
        计算工作流执行时长（秒）

        Returns:
            float: 执行时长（秒）
        """
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class WorkflowTemplate(ABC):
    """
    工作流模板抽象基类

    所有具体审计工作流模板继承此类，定义工作流的结构和步骤。

    设计模式: 模板方法模式（Template Method Pattern）
        - build() 方法为抽象方法，由子类实现具体步骤
        - add_step() 方法用于添加步骤
        - get_step() 方法用于获取指定步骤

    使用方式:
        class MyWorkflow(WorkflowTemplate):
            def build(self) -> WorkflowTemplate:
                self.add_step(WorkflowStep(...))
                return self
    """

    def __init__(self, name: str, description: str = ""):
        """
        初始化工作流模板

        Args:
            name: 工作流名称
            description: 工作流描述
        """
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    def build(self) -> "WorkflowTemplate":
        """
        构建工作流步骤

        由子类实现，定义工作流的具体步骤和依赖关系。

        Returns:
            WorkflowTemplate: 返回自身，支持链式调用
        """
        pass

    def add_step(self, step: WorkflowStep) -> "WorkflowTemplate":
        """
        添加工作流步骤

        Args:
            step: 工作流步骤

        Returns:
            WorkflowTemplate: 返回自身，支持链式调用
        """
        self.steps.append(step)
        return self

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """
        获取指定步骤

        Args:
            step_id: 步骤ID

        Returns:
            Optional[WorkflowStep]: 步骤对象（如果找到），否则返回 None
        """
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        将工作流模板转换为字典格式

        Returns:
            Dict[str, Any]: 工作流模板字典表示
        """
        return {
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }


class CreditAuditWorkflow(WorkflowTemplate):
    """
    信贷审计工作流模板

    标准的信贷业务审计流程，包含以下步骤:
        1. 文档解析（解析贷款合同、财务报表等）
        2. 风险识别（识别信贷业务中的各类风险点）
        3. 合规检查（对照监管政策进行合规性核查）
        4. 报告生成（整合结果，生成审计报告）
        5. 质量审核（对审计报告进行质量审核）

    步骤依赖关系:
        document_parsing ──→ risk_identification ──┐
                        │                          ├──→ report_generation ──→ quality_audit
                        └──→ compliance_check ─────┘
    """

    def __init__(self):
        """
        初始化信贷审计工作流模板

        设置工作流名称和描述。
        """
        super().__init__(
            name="信贷审计工作流",
            description="标准化的信贷业务审计流程，包括文档解析、风险识别、合规检查、报告生成",
        )

    def build(self) -> WorkflowTemplate:
        """
        构建信贷审计工作流步骤

        按顺序添加5个步骤，定义步骤之间的依赖关系。

        Returns:
            WorkflowTemplate: 返回自身
        """
        # Step 1: 信贷文档解析（无依赖）
        self.add_step(WorkflowStep(
            step_id="document_parsing",
            step_name="文档解析",
            description="解析贷款合同、财务报表、审批文件等信贷资料",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 2: 风险点识别（依赖文档解析）
        self.add_step(WorkflowStep(
            step_id="risk_identification",
            step_name="风险识别",
            description="识别信贷业务中的各类风险点",
            task_type="risk_identification",
            target_agent_type="risk_identifier",
            depends_on=["document_parsing"],
            input_mapping={"document_content": "document_parsing.parsed_content"},
        ))

        # Step 3: 合规检查（依赖文档解析）
        self.add_step(WorkflowStep(
            step_id="compliance_check",
            step_name="合规检查",
            description="对照监管政策进行合规性核查",
            task_type="compliance_check",
            target_agent_type="compliance_checker",
            depends_on=["document_parsing"],
            input_mapping={"audit_content": "document_parsing.parsed_content"},
        ))

        # Step 4: 报告生成（依赖风险识别和合规检查）
        self.add_step(WorkflowStep(
            step_id="report_generation",
            step_name="报告生成",
            description="整合风险识别和合规检查结果，生成审计报告",
            task_type="report_generation",
            target_agent_type="report_writer",
            depends_on=["risk_identification", "compliance_check"],
            input_mapping={
                "findings": "risk_identification.findings",
                "compliance_results": "compliance_check.findings",
            },
        ))

        # Step 5: 质量审核（依赖报告生成）
        self.add_step(WorkflowStep(
            step_id="quality_audit",
            step_name="质量审核",
            description="对审计报告进行质量审核",
            task_type="quality_audit",
            target_agent_type="quality_auditor",
            depends_on=["report_generation"],
            input_mapping={"content": "report_generation.report_content"},
        ))

        return self


class ComplianceAuditWorkflow(WorkflowTemplate):
    """
    合规审计工作流模板

    专门用于监管合规专项审计，包含以下步骤:
        1. 监管政策解析
        2. 业务资料解析
        3. 反洗钱专项检查
        4. 一般合规检查
        5. 合规报告生成
        6. 质量审核

    步骤依赖关系:
        regulation_parsing ──┐
                             ├──→ general_compliance ──┐
        business_parsing ────┘                          ├──→ compliance_report ──→ quality_audit
                           │──→ aml_check ─────────────┘
    """

    def __init__(self):
        """
        初始化合规审计工作流模板

        设置工作流名称和描述。
        """
        super().__init__(
            name="合规审计工作流",
            description="监管合规专项审计流程，重点检查监管政策执行情况",
        )

    def build(self) -> WorkflowTemplate:
        """
        构建合规审计工作流步骤

        按顺序添加6个步骤，定义步骤之间的依赖关系。

        Returns:
            WorkflowTemplate: 返回自身
        """
        # Step 1: 监管政策文档解析（无依赖）
        self.add_step(WorkflowStep(
            step_id="regulation_parsing",
            step_name="监管政策解析",
            description="解析最新的监管政策文件，提取关键合规要求",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 2: 业务资料解析（无依赖）
        self.add_step(WorkflowStep(
            step_id="business_parsing",
            step_name="业务资料解析",
            description="解析被审计业务的相关资料",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 3: 反洗钱专项检查（依赖业务资料解析）
        self.add_step(WorkflowStep(
            step_id="aml_check",
            step_name="反洗钱检查",
            description="KYC、大额可疑交易、制裁筛查等反洗钱合规检查",
            task_type="aml_check",
            target_agent_type="compliance_checker",
            depends_on=["business_parsing"],
        ))

        # Step 4: 一般合规检查（依赖监管政策解析和业务资料解析）
        self.add_step(WorkflowStep(
            step_id="general_compliance",
            step_name="一般合规检查",
            description="对照监管政策进行全面合规检查",
            task_type="compliance_check",
            target_agent_type="compliance_checker",
            depends_on=["regulation_parsing", "business_parsing"],
        ))

        # Step 5: 合规报告生成（依赖反洗钱检查和一般合规检查）
        self.add_step(WorkflowStep(
            step_id="compliance_report",
            step_name="合规报告生成",
            description="生成合规专项审计报告",
            task_type="report_generation",
            target_agent_type="report_writer",
            depends_on=["aml_check", "general_compliance"],
        ))

        # Step 6: 质量审核（依赖合规报告生成）
        self.add_step(WorkflowStep(
            step_id="quality_audit",
            step_name="质量审核",
            description="对合规审计报告进行质量审核",
            task_type="quality_audit",
            target_agent_type="quality_auditor",
            depends_on=["compliance_report"],
        ))

        return self


class FinancialAuditWorkflow(WorkflowTemplate):
    """
    财务审计工作流模板

    用于财务报表和财务数据审计，包含以下步骤:
        1. 财务数据解析
        2. 异常检测
        3. 财务合规检查
        4. 财务审计报告

    步骤依赖关系:
        financial_data_parsing ──→ anomaly_detection ──┐
                           │                          ├──→ financial_report
                           └──→ financial_compliance ──┘
    """

    def __init__(self):
        """
        初始化财务审计工作流模板

        设置工作流名称和描述。
        """
        super().__init__(
            name="财务审计工作流",
            description="财务数据专项审计，包括财务报表分析、异常交易识别等",
        )

    def build(self) -> WorkflowTemplate:
        """
        构建财务审计工作流步骤

        按顺序添加4个步骤，定义步骤之间的依赖关系。

        Returns:
            WorkflowTemplate: 返回自身
        """
        # Step 1: 财务数据解析（无依赖）
        self.add_step(WorkflowStep(
            step_id="financial_data_parsing",
            step_name="财务数据解析",
            description="解析财务报表、账户流水等财务数据",
            task_type="document_processing",
            target_agent_type="document_parser",
        ))

        # Step 2: 异常检测（依赖财务数据解析）
        self.add_step(WorkflowStep(
            step_id="anomaly_detection",
            step_name="异常检测",
            description="识别财务异常交易和异常指标",
            task_type="risk_identification",
            target_agent_type="risk_identifier",
            depends_on=["financial_data_parsing"],
        ))

        # Step 3: 财务合规检查（依赖财务数据解析）
        self.add_step(WorkflowStep(
            step_id="financial_compliance",
            step_name="财务合规检查",
            description="检查财务制度执行和会计准则合规",
            task_type="compliance_check",
            target_agent_type="compliance_checker",
            depends_on=["financial_data_parsing"],
        ))

        # Step 4: 财务审计报告（依赖异常检测和财务合规检查）
        self.add_step(WorkflowStep(
            step_id="financial_report",
            step_name="财务审计报告",
            description="生成财务审计报告",
            task_type="report_generation",
            target_agent_type="report_writer",
            depends_on=["anomaly_detection", "financial_compliance"],
        ))

        return self


class WorkflowExecutor:
    """
    工作流执行器

    负责执行具体的工作流实例，管理步骤执行顺序和结果聚合。

    核心职责:
        1. 创建工作流执行上下文
        2. 按依赖顺序执行步骤
        3. 管理步骤输入输出映射
        4. 聚合步骤结果
        5. 提取最终报告

    设计模式: 执行者模式（Executor Pattern）
        将工作流定义与执行逻辑分离，提高可维护性和扩展性。
    """

    def __init__(self, orchestrator: AgentOrchestrator):
        """
        初始化工作流执行器

        Args:
            orchestrator: 智能体协调器，用于提交和管理任务
        """
        self.orchestrator = orchestrator
        self.running_workflows: Dict[str, WorkflowResult] = {}

    async def execute(
        self,
        workflow_template: WorkflowTemplate,
        input_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
    ) -> WorkflowResult:
        """
        执行工作流

        核心执行流程:
            1. 初始化工作流结果
            2. 按顺序执行每个步骤
            3. 检查必需步骤是否成功
            4. 聚合步骤结果
            5. 提取最终报告

        Args:
            workflow_template: 工作流模板
            input_data: 初始输入数据
            workflow_id: 可选的工作流ID（不提供则自动生成）

        Returns:
            WorkflowResult: 工作流执行结果
        """
        # 生成工作流ID（如果未提供）
        workflow_id = workflow_id or f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 初始化工作流结果
        result = WorkflowResult(
            workflow_id=workflow_id,
            workflow_name=workflow_template.name,
            success=False,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(),
            metadata={"input_data_keys": list(input_data.keys())},
        )

        # 保存到运行中的工作流列表
        self.running_workflows[workflow_id] = result

        logger.info(f"开始执行工作流: {workflow_id} - {workflow_template.name}")

        try:
            # 存储所有步骤的输出
            step_outputs: Dict[str, Any] = {}
            step_outputs["__initial__"] = input_data

            # 按顺序执行每个步骤
            for step in workflow_template.steps:
                step_result = await self._execute_step(
                    workflow_id, step, step_outputs, input_data
                )
                step_outputs[step.step_id] = step_result

                # 如果是必需步骤且执行失败，抛出异常终止工作流
                if not step_result.get("success", False) and step.required:
                    raise Exception(
                        f"工作流步骤失败: {step.step_id}, "
                        f"错误: {step_result.get('error', 'unknown')}"
                    )

            # 聚合所有步骤的发现
            result.step_results = step_outputs
            result.aggregated_findings = self._aggregate_findings(step_outputs)
            result.final_report = self._extract_final_report(step_outputs)
            result.status = WorkflowStatus.COMPLETED
            result.success = True

        except Exception as e:
            # 处理执行异常
            logger.error(f"工作流执行失败: {workflow_id}, 错误: {str(e)}")
            result.status = WorkflowStatus.FAILED
            result.error_message = str(e)
            result.success = False

        finally:
            # 记录结束时间
            result.end_time = datetime.now()

        # 记录执行完成日志
        logger.info(
            f"工作流执行完成: {workflow_id}, 状态: {result.status}, "
            f"耗时: {result.duration_seconds:.2f}秒"
        )

        return result

    async def _execute_step(
        self,
        workflow_id: str,
        step: WorkflowStep,
        step_outputs: Dict[str, Any],
        initial_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行单个工作流步骤

        步骤执行流程:
            1. 准备输入数据（根据 input_mapping 从之前步骤获取）
            2. 创建 Task 对象
            3. 提交任务到协调器
            4. 等待任务完成
            5. 获取任务结果
            6. 封装步骤结果

        Args:
            workflow_id: 工作流ID
            step: 工作流步骤
            step_outputs: 所有步骤的输出（用于输入映射）
            initial_input: 初始输入数据

        Returns:
            Dict[str, Any]: 步骤执行结果
        """
        logger.info(f"执行工作流步骤: {workflow_id} - {step.step_id}")

        # 准备步骤输入数据（根据输入映射从之前步骤获取）
        step_input = self._prepare_step_input(step, step_outputs, initial_input)

        # 创建任务对象
        task = Task(
            task_id=f"{workflow_id}_{step.step_id}",
            task_type=step.task_type,
            description=step.description,
            input_data=step_input,
        )

        # 提交任务到协调器
        await self.orchestrator.submit_task(
            task,
            target_agent_type=step.target_agent_type,
        )

        # 等待任务完成
        await self.orchestrator.wait_for_completion()

        # 获取任务结果
        all_results = self.orchestrator.get_results()
        task_result = all_results["completed"].get(
            task.task_id, all_results["failed"].get(task.task_id)
        )

        # 如果未找到任务结果，返回失败
        if not task_result:
            return {"success": False, "error": "任务结果未找到"}

        # 判断任务是否成功
        is_success = task.task_id in all_results["completed"]

        # 返回步骤执行结果
        return {
            "success": is_success,
            "step_id": step.step_id,
            "task_id": task.task_id,
            "output": task_result.get("output", {}),
            "error": task_result.get("error"),
        }

    def _prepare_step_input(
        self,
        step: WorkflowStep,
        step_outputs: Dict[str, Any],
        initial_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        准备步骤的输入数据

        根据 step.input_mapping 从之前步骤的输出中获取数据，
        构建当前步骤的输入。

        输入映射格式:
            {"input_key": "source_step.output_key"}
            例如: {"findings": "risk_identification.findings"}

        Args:
            step: 工作流步骤
            step_outputs: 所有步骤的输出
            initial_input: 初始输入数据

        Returns:
            Dict[str, Any]: 步骤输入数据
        """
        # 从初始输入开始
        step_input = initial_input.copy()

        # 根据输入映射从之前步骤的输出中获取数据
        for input_key, mapping in step.input_mapping.items():
            parts = mapping.split(".")
            if len(parts) >= 2:
                source_step = parts[0]
                source_key = ".".join(parts[1:])

                # 如果源步骤存在，获取对应的数据
                if source_step in step_outputs:
                    source_data = step_outputs[source_step]
                    # 支持从 output 字段或直接从步骤结果中获取数据
                    step_input[input_key] = source_data.get("output", {}).get(
                        source_key, source_data.get(source_key)
                    )

        return step_input

    def _aggregate_findings(self, step_outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        聚合所有步骤的发现

        从每个步骤的输出中提取 findings 字段，添加来源步骤标识。

        Args:
            step_outputs: 所有步骤的输出

        Returns:
            List[Dict[str, Any]]: 聚合后的发现列表
        """
        all_findings = []

        for step_id, output in step_outputs.items():
            if isinstance(output, dict):
                findings = output.get("output", {}).get("findings", [])
                if findings:
                    for finding in findings:
                        # 添加来源步骤标识
                        finding["source_step"] = step_id
                        all_findings.append(finding)

        return all_findings

    def _extract_final_report(self, step_outputs: Dict[str, Any]) -> Optional[str]:
        """
        从步骤输出中提取最终报告

        按优先级查找报告生成步骤的输出。

        Args:
            step_outputs: 所有步骤的输出

        Returns:
            Optional[str]: 最终报告内容（如果找到），否则返回 None
        """
        # 报告步骤优先级顺序
        report_steps = ["report_generation", "compliance_report", "financial_report"]

        for step_id in report_steps:
            if step_id in step_outputs:
                output = step_outputs[step_id]
                report = output.get("output", {}).get("report_content")
                if report:
                    return report

        return None


class AuditPipeline:
    """
    审计流水线

    提供高层API，方便执行各种审计任务。

    核心职责:
        1. 管理工作流模板注册
        2. 提供便捷的审计执行方法
        3. 管理协调器生命周期
        4. 提供状态查询接口

    使用示例:
        pipeline = AuditPipeline()
        result = await pipeline.run_credit_audit(
            loan_documents=["contract.pdf"],
            audited_unit="某某公司",
        )
    """

    def __init__(self, orchestrator: Optional[AgentOrchestrator] = None):
        """
        初始化审计流水线

        Args:
            orchestrator: 可选的智能体协调器（不提供则自动创建）
        """
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.executor = WorkflowExecutor(self.orchestrator)
        self.workflow_templates: Dict[str, WorkflowTemplate] = {}

        # 注册默认工作流模板
        self._register_default_templates()

    def _register_default_templates(self):
        """
        注册默认工作流模板

        自动注册3个预定义的工作流模板:
            1. 信贷审计工作流
            2. 合规审计工作流
            3. 财务审计工作流
        """
        self.register_workflow(CreditAuditWorkflow().build())
        self.register_workflow(ComplianceAuditWorkflow().build())
        self.register_workflow(FinancialAuditWorkflow().build())

    def register_workflow(self, workflow: WorkflowTemplate):
        """
        注册工作流模板

        Args:
            workflow: 工作流模板
        """
        self.workflow_templates[workflow.name] = workflow
        logger.info(f"已注册工作流模板: {workflow.name}")

    def get_available_workflows(self) -> List[Dict[str, Any]]:
        """
        获取可用的工作流列表

        Returns:
            List[Dict[str, Any]]: 工作流列表（包含名称、描述、步骤数量）
        """
        return [
            {
                "name": wf.name,
                "description": wf.description,
                "steps_count": len(wf.steps),
            }
            for wf in self.workflow_templates.values()
        ]

    async def run_audit(
        self,
        workflow_name: str,
        document_paths: List[str],
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """
        运行审计（通用方法）

        核心流程:
            1. 确保协调器已启动
            2. 获取工作流模板
            3. 准备输入数据
            4. 执行工作流

        Args:
            workflow_name: 工作流名称
            document_paths: 要审计的文档路径列表
            audit_context: 审计上下文信息（可选）

        Returns:
            WorkflowResult: 工作流执行结果

        Raises:
            ValueError: 如果工作流模板不存在
        """
        # 确保协调器已启动
        if not self.orchestrator.is_running:
            self.orchestrator.register_default_agents()
            await self.orchestrator.start()

        # 获取工作流模板
        workflow = self.workflow_templates.get(workflow_name)
        if not workflow:
            raise ValueError(f"未找到工作流模板: {workflow_name}")

        # 准备输入数据
        input_data = {
            "document_paths": document_paths,
            "audit_context": audit_context or {},
            "workflow_name": workflow_name,
            "start_time": datetime.now().isoformat(),
        }

        # 执行工作流
        result = await self.executor.execute(workflow, input_data)

        return result

    async def run_credit_audit(
        self,
        loan_documents: List[str],
        audited_unit: str = "",
        audit_period: str = "",
    ) -> WorkflowResult:
        """
        运行信贷审计（便捷方法）

        Args:
            loan_documents: 信贷文档路径列表
            audited_unit: 被审计单位（可选）
            audit_period: 审计期间（可选）

        Returns:
            WorkflowResult: 工作流执行结果
        """
        # 构建审计上下文
        context = {
            "audited_unit": audited_unit,
            "audit_period": audit_period,
            "audit_type": "信贷审计",
        }

        # 调用通用审计方法
        return await self.run_audit("信贷审计工作流", loan_documents, context)

    async def run_compliance_audit(
        self,
        business_documents: List[str],
        regulation_documents: Optional[List[str]] = None,
    ) -> WorkflowResult:
        """
        运行合规审计（便捷方法）

        Args:
            business_documents: 业务文档路径列表
            regulation_documents: 监管文档路径列表（可选）

        Returns:
            WorkflowResult: 工作流执行结果
        """
        # 构建审计上下文
        context = {
            "regulation_documents": regulation_documents or [],
            "audit_type": "合规审计",
        }

        # 调用通用审计方法
        return await self.run_audit("合规审计工作流", business_documents, context)

    async def shutdown(self):
        """
        关闭审计流水线

        停止协调器，释放资源。
        """
        await self.orchestrator.stop()
        logger.info("审计流水线已关闭")

    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        获取流水线状态

        Returns:
            Dict[str, Any]: 流水线状态信息
        """
        return {
            "orchestrator": self.orchestrator.get_status(),
            "registered_workflows": self.get_available_workflows(),
            "running_workflows": len(self.executor.running_workflows),
        }