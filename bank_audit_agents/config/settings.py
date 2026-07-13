"""
银行审计多智能体系统配置
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AgentType(str, Enum):
    """智能体类型枚举"""
    DOCUMENT_PARSER = "document_parser"
    RISK_IDENTIFIER = "risk_identifier"
    COMPLIANCE_CHECKER = "compliance_checker"
    REPORT_WRITER = "report_writer"
    QUALITY_AUDITOR = "quality_auditor"
    TASK_COORDINATOR = "task_coordinator"


class WorkflowType(str, Enum):
    """工作流类型枚举"""
    CREDIT_AUDIT = "credit_audit"
    COMPLIANCE_AUDIT = "compliance_audit"
    FINANCIAL_AUDIT = "financial_audit"
    INTERNAL_CONTROL = "internal_control"
    AML_AUDIT = "aml_audit"
    CUSTOM = "custom"


class AgentConfig(BaseSettings):
    """智能体配置"""
    model_config = {"extra": "allow"}

    agent_type: AgentType
    name: str
    description: str
    max_iterations: int = 10
    temperature: float = 0.1
    enable_memory: bool = True
    enable_thinking: bool = True
    timeout_seconds: int = 300

    # 系统提示词模板
    system_prompt: Optional[str] = None

    # 工具配置
    enabled_tools: List[str] = Field(default_factory=list)


class Settings(BaseSettings):
    """全局配置"""
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    # =========================================================================
    # 基础配置
    # =========================================================================
    environment: str = "development"
    project_name: str = "Bank Audit Agents"
    log_level: str = "INFO"
    debug: bool = True

    # =========================================================================
    # LLM 配置
    # =========================================================================
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    default_llm_model: str = "gpt-4o"
    default_embedding_model: str = "text-embedding-3-large"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_timeout: int = 120
    llm_max_retries: int = 3

    # =========================================================================
    # 智能体配置
    # =========================================================================
    agent_max_iterations: int = 10
    agent_parallel_execution: bool = True
    agent_enable_memory: bool = True
    agent_enable_thinking: bool = True

    # 超时配置
    agent_timeout_seconds: int = 300
    workflow_timeout_seconds: int = 1800  # 30分钟

    # =========================================================================
    # 向量数据库配置
    # =========================================================================
    vector_store_type: str = "chroma"
    vector_store_path: str = "./data/vector_store"
    vector_store_collection: str = "audit_knowledge_base"

    # =========================================================================
    # Redis 配置（用于记忆、队列、缓存）
    # =========================================================================
    redis_url: str = "redis://localhost:6379/0"
    redis_enable: bool = True
    redis_cache_ttl: int = 3600

    # =========================================================================
    # 审计追踪配置
    # =========================================================================
    audit_trail_enabled: bool = True
    audit_trail_path: str = "./data/audit_trails"
    audit_trail_retention_days: int = 90
    save_intermediate_results: bool = True

    # =========================================================================
    # 报告生成配置
    # =========================================================================
    report_output_path: str = "./data/reports"
    report_formats: List[str] = Field(default_factory=lambda: ["md", "docx", "pdf"])
    report_template_path: str = "./config/templates"

    # =========================================================================
    # UI 配置
    # =========================================================================
    ui_enable: bool = True
    ui_port: int = 8501
    ui_theme: str = "light"

    # =========================================================================
    # API 配置
    # =========================================================================
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_workers: int = 4
    api_cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    # 安全配置
    api_key_enabled: bool = True
    api_keys: List[str] = Field(default_factory=list)
    sensitive_fields: List[str] = Field(default_factory=lambda: [
        "password", "api_key", "secret", "token", "credential",
        "account_number", "id_card", "phone", "email",
    ])

    # =========================================================================
    # 方法
    # =========================================================================
    def get_agent_config(self, agent_type: AgentType) -> AgentConfig:
        """获取指定类型智能体的配置"""
        base_configs = {
            AgentType.DOCUMENT_PARSER: AgentConfig(
                agent_type=AgentType.DOCUMENT_PARSER,
                name="文档解析智能体",
                description="负责解析和理解各类审计文档，提取关键信息",
                temperature=0.0,
                enabled_tools=["pdf_parser", "docx_parser", "excel_parser", "text_extractor"],
            ),
            AgentType.RISK_IDENTIFIER: AgentConfig(
                agent_type=AgentType.RISK_IDENTIFIER,
                name="风险识别智能体",
                description="深度分析文档内容，识别各类审计风险点",
                temperature=0.3,
                enabled_tools=["risk_pattern_matcher", "anomaly_detector", "trend_analyzer"],
            ),
            AgentType.COMPLIANCE_CHECKER: AgentConfig(
                agent_type=AgentType.COMPLIANCE_CHECKER,
                name="合规检查智能体",
                description="对照监管政策和行内制度，进行合规性核查",
                temperature=0.1,
                enabled_tools=["regulation_retriever", "compliance_checker", "violation_classifier"],
            ),
            AgentType.REPORT_WRITER: AgentConfig(
                agent_type=AgentType.REPORT_WRITER,
                name="报告撰写智能体",
                description="生成标准化审计报告，包括问题描述、风险评估、整改建议",
                temperature=0.4,
                enabled_tools=["report_template_engine", "recommendation_generator"],
            ),
            AgentType.QUALITY_AUDITOR: AgentConfig(
                agent_type=AgentType.QUALITY_AUDITOR,
                name="质量审核智能体",
                description="审核其他智能体的输出，确保审计质量和一致性",
                temperature=0.2,
                enabled_tools=["quality_checker", "consistency_verifier", "completeness_checker"],
            ),
            AgentType.TASK_COORDINATOR: AgentConfig(
                agent_type=AgentType.TASK_COORDINATOR,
                name="任务协调智能体",
                description="统筹整个审计流程，分配任务，协调各智能体协作",
                temperature=0.1,
                enabled_tools=["task_planner", "workflow_orchestrator", "progress_tracker"],
            ),
        }
        return base_configs.get(agent_type, base_configs[AgentType.DOCUMENT_PARSER])

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取全局配置"""
    return settings
