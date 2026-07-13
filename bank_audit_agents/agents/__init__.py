"""
银行审计多智能体平台 智能体模块索引
"""

# 导入智能体类型
from bank_audit_agents.agents.document_parser import DocumentParserAgent
from bank_audit_agents.agents.risk_identifier import RiskIdentifierAgent
from bank_audit_agents.agents.compliance_checker import ComplianceCheckerAgent
from bank_audit_agents.agents.report_writer import ReportWriterAgent
from bank_audit_agents.agents.quality_and_coordinator import (
    QualityAuditorAgent,
    TaskCoordinatorAgent,
)

__all__ = [
    "DocumentParserAgent",
    "RiskIdentifierAgent",
    "ComplianceCheckerAgent",
    "ReportWriterAgent",
    "QualityAuditorAgent",
    "TaskCoordinatorAgent",
]

# 可用智能体类型映射
AGENT_TYPES = {
    "document_parser": DocumentParserAgent,
    "risk_identifier": RiskIdentifierAgent,
    "compliance_checker": ComplianceCheckerAgent,
    "report_writer": ReportWriterAgent,
    "quality_auditor": QualityAuditorAgent,
    "task_coordinator": TaskCoordinatorAgent,
}


def get_agent_class(agent_type: str):
    """根据类型获取智能体类"""
    return AGENT_TYPES.get(agent_type)


def get_all_agent_classes():
    """获取所有智能体类"""
    return list(AGENT_TYPES.values())
