"""
🏦 银行审计多智能体协作平台

一个基于多智能体系统的智能审计解决方案，提供完整的信贷审计、合规审计、风险管理等工作流程。

核心特性:
- 🤖 6个专业审计智能体
- 🔄 3种内置审计工作流
- 🖥️ 完整的Web监控仪表板
- 📊 实时任务状态监控
- 📝 标准化审计报告生成
- ✅ 自动化质量审核

使用示例:
    >>> from bank_audit_agents import AgentOrchestrator, DocumentParserAgent
    >>> orchestrator = AgentOrchestrator()
    >>> orchestrator.register_agent(DocumentParserAgent())
    >>> await orchestrator.start()
"""

__version__ = "1.0.0"
__author__ = "Bank AI Lab"
__description__ = "基于多智能体系统的银行审计智能化解决方案"

# 导出核心基类
from bank_audit_agents.core.base_agent import (
    BaseAgent,
    Task,
    AgentResult,
    AgentMessage,
    AgentStatus,
    TaskStatus,
)

# 导出协调器
from bank_audit_agents.core.orchestrator import (
    AgentOrchestrator,
    OrchestratorStatus,
)

# 导出所有智能体
from bank_audit_agents.agents import (
    DocumentParserAgent,
    RiskIdentifierAgent,
    ComplianceCheckerAgent,
    ReportWriterAgent,
    QualityAuditorAgent,
    TaskCoordinatorAgent,
)

# 导出工作流
from bank_audit_agents.workflows.audit_pipeline import (
    AuditPipeline,
    WorkflowExecutor,
    WorkflowTemplate,
    WorkflowStep,
    WorkflowResult,
    CreditAuditWorkflow,
    ComplianceAuditWorkflow,
    FinancialAuditWorkflow,
)

# 导出配置
from bank_audit_agents.config.settings import (
    Settings,
    AgentType,
    WorkflowType,
    get_settings,
)

__all__ = [
    # 核心基类
    "BaseAgent",
    "Task",
    "AgentResult",
    "AgentMessage",
    "AgentStatus",
    "TaskStatus",
    # 协调器
    "AgentOrchestrator",
    "OrchestratorStatus",
    # 智能体
    "DocumentParserAgent",
    "RiskIdentifierAgent",
    "ComplianceCheckerAgent",
    "ReportWriterAgent",
    "QualityAuditorAgent",
    "TaskCoordinatorAgent",
    # 工作流
    "AuditPipeline",
    "WorkflowExecutor",
    "WorkflowTemplate",
    "WorkflowStep",
    "WorkflowResult",
    "CreditAuditWorkflow",
    "ComplianceAuditWorkflow",
    "FinancialAuditWorkflow",
    # 配置
    "Settings",
    "AgentType",
    "WorkflowType",
    "get_settings",
]
