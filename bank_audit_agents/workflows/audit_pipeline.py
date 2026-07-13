"""
审计工作流编排系统
定义和执行各种标准化的审计工作流程
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

logger = get_logger(__name__)


class WorkflowStatus(str):
    """工作流状态"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    step_name: str
    description: str
    task_type: str
    target_agent_type: str
    depends_on: List[str] = field(default_factory=list)
    input_mapping: Dict[str, str] = field(default_factory=dict)  # 上一步输出 -> 这一步输入
    required: bool = True
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowResult:
    """工作流执行结果"""
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
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class WorkflowTemplate(ABC):
    """
    工作流模板基类
    所有具体审计工作流模板继承此类
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    def build(self) -> "WorkflowTemplate":
        """构建工作流步骤"""
        pass

    def add_step(self, step: WorkflowStep) -> "WorkflowTemplate":
        """添加工作流步骤"""
        self.steps.append(step)
        return self

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """获取指定步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }


class CreditAuditWorkflow(WorkflowTemplate):
    """
    信贷审计工作流模板
    标准的信贷业务审计流程
    """

    def __init__(self):
        super().__init__(
            name="信贷审计工作流",
            description="标准化的信贷业务审计流程，包括文档解析、风险识别、合规检查、报告生成",
        )

    def build(self) -> WorkflowTemplate:
        # Step 1: 信贷文档解析
        self.add_step(WorkflowStep(
            step_id="document_parsing",
            step_name="文档解析",
            description="解析贷款合同、财务报表、审批文件等信贷资料",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 2: 风险点识别
        self.add_step(WorkflowStep(
            step_id="risk_identification",
            step_name="风险识别",
            description="识别信贷业务中的各类风险点",
            task_type="risk_identification",
            target_agent_type="risk_identifier",
            depends_on=["document_parsing"],
            input_mapping={"document_content": "document_parsing.parsed_content"},
        ))

        # Step 3: 合规检查
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

        # Step 5: 质量审核
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
    专门用于监管合规专项审计
    """

    def __init__(self):
        super().__init__(
            name="合规审计工作流",
            description="监管合规专项审计流程，重点检查监管政策执行情况",
        )

    def build(self) -> WorkflowTemplate:
        # Step 1: 监管政策文档解析
        self.add_step(WorkflowStep(
            step_id="regulation_parsing",
            step_name="监管政策解析",
            description="解析最新的监管政策文件，提取关键合规要求",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 2: 业务资料解析
        self.add_step(WorkflowStep(
            step_id="business_parsing",
            step_name="业务资料解析",
            description="解析被审计业务的相关资料",
            task_type="document_processing",
            target_agent_type="document_parser",
            depends_on=[],
        ))

        # Step 3: 反洗钱专项检查
        self.add_step(WorkflowStep(
            step_id="aml_check",
            step_name="反洗钱检查",
            description="KYC、大额可疑交易、制裁筛查等反洗钱合规检查",
            task_type="aml_check",
            target_agent_type="compliance_checker",
            depends_on=["business_parsing"],
        ))

        # Step 4: 一般合规检查
        self.add_step(WorkflowStep(
            step_id="general_compliance",
            step_name="一般合规检查",
            description="对照监管政策进行全面合规检查",
            task_type="compliance_check",
            target_agent_type="compliance_checker",
            depends_on=["regulation_parsing", "business_parsing"],
        ))

        # Step 5: 合规报告生成
        self.add_step(WorkflowStep(
            step_id="compliance_report",
            step_name="合规报告生成",
            description="生成合规专项审计报告",
            task_type="report_generation",
            target_agent_type="report_writer",
            depends_on=["aml_check", "general_compliance"],
        ))

        # Step 6: 质量审核
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
    用于财务报表和财务数据审计
    """

    def __init__(self):
        super().__init__(
            name="财务审计工作流",
            description="财务数据专项审计，包括财务报表分析、异常交易识别等",
        )

    def build(self) -> WorkflowTemplate:
        self.add_step(WorkflowStep(
            step_id="financial_data_parsing",
            step_name="财务数据解析",
            description="解析财务报表、账户流水等财务数据",
            task_type="document_processing",
            target_agent_type="document_parser",
        ))

        self.add_step(WorkflowStep(
            step_id="anomaly_detection",
            step_name="异常检测",
            description="识别财务异常交易和异常指标",
            task_type="risk_identification",
            target_agent_type="risk_identifier",
            depends_on=["financial_data_parsing"],
        ))

        self.add_step(WorkflowStep(
            step_id="financial_compliance",
            step_name="财务合规检查",
            description="检查财务制度执行和会计准则合规",
            task_type="compliance_check",
            target_agent_type="compliance_checker",
            depends_on=["financial_data_parsing"],
        ))

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
    负责执行具体的工作流实例
    """

    def __init__(self, orchestrator: AgentOrchestrator):
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

        Args:
            workflow_template: 工作流模板
            input_data: 初始输入数据
            workflow_id: 可选的工作流ID

        Returns:
            工作流执行结果
        """
        workflow_id = workflow_id or f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 初始化结果
        result = WorkflowResult(
            workflow_id=workflow_id,
            workflow_name=workflow_template.name,
            success=False,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(),
            metadata={"input_data_keys": list(input_data.keys())},
        )

        self.running_workflows[workflow_id] = result

        logger.info(f"开始执行工作流: {workflow_id} - {workflow_template.name}")

        try:
            # 执行所有步骤
            step_outputs: Dict[str, Any] = {}
            step_outputs["__initial__"] = input_data

            for step in workflow_template.steps:
                step_result = await self._execute_step(
                    workflow_id, step, step_outputs, input_data
                )
                step_outputs[step.step_id] = step_result

                if not step_result.get("success", False) and step.required:
                    raise Exception(
                        f"工作流步骤失败: {step.step_id}, "
                        f"错误: {step_result.get('error', 'unknown')}"
                    )

            # 聚合结果
            result.step_results = step_outputs
            result.aggregated_findings = self._aggregate_findings(step_outputs)
            result.final_report = self._extract_final_report(step_outputs)
            result.status = WorkflowStatus.COMPLETED
            result.success = True

        except Exception as e:
            logger.error(f"工作流执行失败: {workflow_id}, 错误: {str(e)}")
            result.status = WorkflowStatus.FAILED
            result.error_message = str(e)
            result.success = False

        finally:
            result.end_time = datetime.now()

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
        """执行单个工作流步骤"""
        logger.info(f"执行工作流步骤: {workflow_id} - {step.step_id}")

        # 准备输入数据
        step_input = self._prepare_step_input(step, step_outputs, initial_input)

        # 创建任务
        task = Task(
            task_id=f"{workflow_id}_{step.step_id}",
            task_type=step.task_type,
            description=step.description,
            input_data=step_input,
        )

        # 提交到协调器
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

        if not task_result:
            return {"success": False, "error": "任务结果未找到"}

        # 判断是否成功
        is_success = task.task_id in all_results["completed"]

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
        """准备步骤的输入数据"""
        step_input = initial_input.copy()

        # 根据输入映射从之前步骤的输出中获取数据
        for input_key, mapping in step.input_mapping.items():
            parts = mapping.split(".")
            if len(parts) >= 2:
                source_step = parts[0]
                source_key = ".".join(parts[1:])

                if source_step in step_outputs:
                    source_data = step_outputs[source_step]
                    # 简单的键值获取（实际可以支持更复杂的路径解析）
                    step_input[input_key] = source_data.get("output", {}).get(
                        source_key, source_data.get(source_key)
                    )

        return step_input

    def _aggregate_findings(self, step_outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """聚合所有步骤的发现"""
        all_findings = []

        for step_id, output in step_outputs.items():
            if isinstance(output, dict):
                findings = output.get("output", {}).get("findings", [])
                if findings:
                    for finding in findings:
                        finding["source_step"] = step_id
                        all_findings.append(finding)

        return all_findings

    def _extract_final_report(self, step_outputs: Dict[str, Any]) -> Optional[str]:
        """从步骤输出中提取最终报告"""
        # 查找报告生成步骤
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
    提供高层API，方便执行各种审计任务
    """

    def __init__(self, orchestrator: Optional[AgentOrchestrator] = None):
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.executor = WorkflowExecutor(self.orchestrator)
        self.workflow_templates: Dict[str, WorkflowTemplate] = {}

        # 注册默认工作流模板
        self._register_default_templates()

    def _register_default_templates(self):
        """注册默认工作流模板"""
        self.register_workflow(CreditAuditWorkflow().build())
        self.register_workflow(ComplianceAuditWorkflow().build())
        self.register_workflow(FinancialAuditWorkflow().build())

    def register_workflow(self, workflow: WorkflowTemplate):
        """注册工作流模板"""
        self.workflow_templates[workflow.name] = workflow
        logger.info(f"已注册工作流模板: {workflow.name}")

    def get_available_workflows(self) -> List[Dict[str, Any]]:
        """获取可用的工作流列表"""
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
        运行审计

        Args:
            workflow_name: 工作流名称
            document_paths: 要审计的文档路径列表
            audit_context: 审计上下文信息

        Returns:
            工作流执行结果
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
        """运行信贷审计"""
        context = {
            "audited_unit": audited_unit,
            "audit_period": audit_period,
            "audit_type": "信贷审计",
        }
        return await self.run_audit("信贷审计工作流", loan_documents, context)

    async def run_compliance_audit(
        self,
        business_documents: List[str],
        regulation_documents: Optional[List[str]] = None,
    ) -> WorkflowResult:
        """运行合规审计"""
        context = {
            "regulation_documents": regulation_documents or [],
            "audit_type": "合规审计",
        }
        return await self.run_audit("合规审计工作流", business_documents, context)

    async def shutdown(self):
        """关闭审计流水线"""
        await self.orchestrator.stop()
        logger.info("审计流水线已关闭")

    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线状态"""
        return {
            "orchestrator": self.orchestrator.get_status(),
            "registered_workflows": self.get_available_workflows(),
            "running_workflows": len(self.executor.running_workflows),
        }
