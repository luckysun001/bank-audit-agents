"""
银行审计多智能体系统配置模块

本模块使用 Pydantic Settings 实现配置管理，支持从环境变量和 .env 文件加载配置。

核心组件:
    1. AgentType: 智能体类型枚举
    2. WorkflowType: 工作流类型枚举
    3. AgentConfig: 单个智能体的配置类
    4. Settings: 全局配置类
    5. get_settings(): 获取全局配置实例的便捷函数

配置加载顺序:
    1. 默认值
    2. .env 文件中的环境变量
    3. 操作系统环境变量（覆盖 .env 文件）

使用示例:
    from bank_audit_agents.config.settings import get_settings
    settings = get_settings()
    print(settings.openai_api_key)
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AgentType(str, Enum):
    """
    智能体类型枚举

    定义系统中所有可用的智能体类型，用于智能体注册、任务分配和工作流配置。

    类型说明:
        DOCUMENT_PARSER:      文档解析智能体 - 负责解析各类审计文档
        RISK_IDENTIFIER:     风险识别智能体 - 识别各类审计风险点
        COMPLIANCE_CHECKER:  合规检查智能体 - 对照监管政策进行合规核查
        REPORT_WRITER:       报告撰写智能体 - 生成标准化审计报告
        QUALITY_AUDITOR:     质量审核智能体 - 审核其他智能体输出质量
        TASK_COORDINATOR:    任务协调智能体 - 统筹审计流程，分配任务
    """
    DOCUMENT_PARSER = "document_parser"
    RISK_IDENTIFIER = "risk_identifier"
    COMPLIANCE_CHECKER = "compliance_checker"
    REPORT_WRITER = "report_writer"
    QUALITY_AUDITOR = "quality_auditor"
    TASK_COORDINATOR = "task_coordinator"


class WorkflowType(str, Enum):
    """
    工作流类型枚举

    定义系统中支持的审计工作流类型。

    类型说明:
        CREDIT_AUDIT:       信贷审计工作流 - 用于信贷业务审计
        COMPLIANCE_AUDIT:   合规审计工作流 - 用于监管合规专项审计
        FINANCIAL_AUDIT:    财务审计工作流 - 用于财务数据审计
        INTERNAL_CONTROL:   内部控制审计工作流
        AML_AUDIT:          反洗钱审计工作流
        CUSTOM:             自定义工作流
    """
    CREDIT_AUDIT = "credit_audit"
    COMPLIANCE_AUDIT = "compliance_audit"
    FINANCIAL_AUDIT = "financial_audit"
    INTERNAL_CONTROL = "internal_control"
    AML_AUDIT = "aml_audit"
    CUSTOM = "custom"


class AgentConfig(BaseSettings):
    """
    单个智能体的配置类

    用于配置特定类型智能体的行为参数。

    属性说明:
        agent_type:         智能体类型
        name:               智能体名称（中文）
        description:        智能体描述
        max_iterations:     最大迭代次数，默认 10
        temperature:        LLM 温度参数（0-1，越低越确定性）
        enable_memory:      是否启用记忆功能
        enable_thinking:    是否启用思考过程
        timeout_seconds:    超时时间（秒），默认 300
        system_prompt:      系统提示词模板（可选，使用默认则为 None）
        enabled_tools:      启用的工具列表
    """
    model_config = {"extra": "allow"}

    agent_type: AgentType
    name: str
    description: str
    max_iterations: int = 10
    temperature: float = 0.1
    enable_memory: bool = True
    enable_thinking: bool = True
    timeout_seconds: int = 300

    # 系统提示词模板（可选）
    system_prompt: Optional[str] = None

    # 工具配置
    enabled_tools: List[str] = Field(default_factory=list)


class Settings(BaseSettings):
    """
    全局配置类

    使用 Pydantic Settings 实现，支持从环境变量和 .env 文件加载配置。

    配置分类:
        1. 基础配置：环境、项目名、日志级别
        2. LLM 配置：API Key、模型、温度、超时等
        3. 智能体配置：迭代次数、并行执行、内存等
        4. 向量数据库配置：存储类型、路径、集合名
        5. Redis 配置：URL、启用状态、缓存 TTL
        6. 审计追踪配置：启用状态、路径、保留天数
        7. 报告生成配置：输出路径、格式、模板路径
        8. UI 配置：启用状态、端口、主题
        9. API 配置：主机、端口、工作进程数、CORS、安全等
    """
    model_config = {
        "env_file": ".env",           # 环境变量文件路径
        "env_file_encoding": "utf-8", # 文件编码
        "case_sensitive": False,      # 环境变量不区分大小写
    }

    # =========================================================================
    # 基础配置
    # =========================================================================
    environment: str = "development"      # 运行环境：development/production/test
    project_name: str = "Bank Audit Agents"  # 项目名称
    log_level: str = "INFO"             # 日志级别：DEBUG/INFO/WARNING/ERROR/CRITICAL
    debug: bool = True                  # 是否启用调试模式

    # =========================================================================
    # LLM (大语言模型) 配置
    # =========================================================================
    openai_api_key: Optional[str] = None     # OpenAI API Key
    openai_base_url: Optional[str] = None    # OpenAI 基础 URL（用于自定义 API 服务）
    default_llm_model: str = "gpt-4o"       # 默认 LLM 模型
    default_embedding_model: str = "text-embedding-3-large"  # 默认嵌入模型
    llm_temperature: float = 0.1             # LLM 温度参数（0-1）
    llm_max_tokens: int = 4096              # 最大生成 token 数
    llm_timeout: int = 120                  # LLM 调用超时时间（秒）
    llm_max_retries: int = 3                # LLM 调用最大重试次数

    # =========================================================================
    # 智能体配置
    # =========================================================================
    agent_max_iterations: int = 10       # 智能体最大迭代次数
    agent_parallel_execution: bool = True  # 是否启用并行执行
    agent_enable_memory: bool = True      # 是否启用智能体记忆
    agent_enable_thinking: bool = True    # 是否启用思考过程

    # 超时配置
    agent_timeout_seconds: int = 300           # 单个智能体任务超时时间（秒）
    workflow_timeout_seconds: int = 1800      # 工作流整体超时时间（秒），30分钟

    # =========================================================================
    # 向量数据库配置（用于知识库检索）
    # =========================================================================
    vector_store_type: str = "chroma"              # 向量存储类型
    vector_store_path: str = "./data/vector_store" # 向量存储路径
    vector_store_collection: str = "audit_knowledge_base"  # 向量集合名称

    # =========================================================================
    # Redis 配置（用于记忆、队列、缓存）
    # =========================================================================
    redis_url: str = "redis://localhost:6379/0"  # Redis 连接 URL
    redis_enable: bool = True                   # 是否启用 Redis
    redis_cache_ttl: int = 3600                 # 缓存 TTL（秒），1小时

    # =========================================================================
    # 审计追踪配置（操作日志记录）
    # =========================================================================
    audit_trail_enabled: bool = True               # 是否启用审计追踪
    audit_trail_path: str = "./data/audit_trails"  # 审计追踪文件路径
    audit_trail_retention_days: int = 90           # 审计日志保留天数
    save_intermediate_results: bool = True         # 是否保存中间结果

    # =========================================================================
    # 报告生成配置
    # =========================================================================
    report_output_path: str = "./data/reports"     # 报告输出路径
    report_formats: List[str] = Field(default_factory=lambda: ["md", "docx", "pdf"])  # 报告格式
    report_template_path: str = "./config/templates"  # 报告模板路径

    # =========================================================================
    # UI 配置（Streamlit Dashboard）
    # =========================================================================
    ui_enable: bool = True      # 是否启用 Web UI
    ui_port: int = 8501         # UI 服务端口
    ui_theme: str = "light"     # UI 主题：light/dark

    # =========================================================================
    # API 配置（FastAPI）
    # =========================================================================
    api_host: str = "0.0.0.0"  # API 服务主机地址
    api_port: int = 8080       # API 服务端口
    api_workers: int = 4       # API 工作进程数

    # CORS 配置（跨域资源共享）
    api_cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    # 安全配置
    api_key_enabled: bool = True  # 是否启用 API Key 认证
    api_keys: List[str] = Field(default_factory=list)  # 允许的 API Key 列表

    # 敏感字段列表（用于数据脱敏）
    sensitive_fields: List[str] = Field(default_factory=lambda: [
        "password", "api_key", "secret", "token", "credential",
        "account_number", "id_card", "phone", "email",
    ])

    # =========================================================================
    # 配置方法
    # =========================================================================

    def get_agent_config(self, agent_type: AgentType) -> AgentConfig:
        """
        获取指定类型智能体的配置

        根据智能体类型返回预定义的配置参数，包括名称、描述、温度参数和启用的工具。

        Args:
            agent_type: 智能体类型

        Returns:
            AgentConfig: 智能体配置对象
        """
        base_configs = {
            AgentType.DOCUMENT_PARSER: AgentConfig(
                agent_type=AgentType.DOCUMENT_PARSER,
                name="文档解析智能体",
                description="负责解析和理解各类审计文档，提取关键信息",
                temperature=0.0,  # 文档解析需要高确定性
                enabled_tools=["pdf_parser", "docx_parser", "excel_parser", "text_extractor"],
            ),
            AgentType.RISK_IDENTIFIER: AgentConfig(
                agent_type=AgentType.RISK_IDENTIFIER,
                name="风险识别智能体",
                description="深度分析文档内容，识别各类审计风险点",
                temperature=0.3,  # 风险识别需要一定的创造性
                enabled_tools=["risk_pattern_matcher", "anomaly_detector", "trend_analyzer"],
            ),
            AgentType.COMPLIANCE_CHECKER: AgentConfig(
                agent_type=AgentType.COMPLIANCE_CHECKER,
                name="合规检查智能体",
                description="对照监管政策和行内制度，进行合规性核查",
                temperature=0.1,  # 合规检查需要高确定性
                enabled_tools=["regulation_retriever", "compliance_checker", "violation_classifier"],
            ),
            AgentType.REPORT_WRITER: AgentConfig(
                agent_type=AgentType.REPORT_WRITER,
                name="报告撰写智能体",
                description="生成标准化审计报告，包括问题描述、风险评估、整改建议",
                temperature=0.4,  # 报告撰写需要一定的创造性
                enabled_tools=["report_template_engine", "recommendation_generator"],
            ),
            AgentType.QUALITY_AUDITOR: AgentConfig(
                agent_type=AgentType.QUALITY_AUDITOR,
                name="质量审核智能体",
                description="审核其他智能体的输出，确保审计质量和一致性",
                temperature=0.2,  # 质量审核需要较高的确定性
                enabled_tools=["quality_checker", "consistency_verifier", "completeness_checker"],
            ),
            AgentType.TASK_COORDINATOR: AgentConfig(
                agent_type=AgentType.TASK_COORDINATOR,
                name="任务协调智能体",
                description="统筹整个审计流程，分配任务，协调各智能体协作",
                temperature=0.1,  # 任务协调需要高确定性
                enabled_tools=["task_planner", "workflow_orchestrator", "progress_tracker"],
            ),
        }
        return base_configs.get(agent_type, base_configs[AgentType.DOCUMENT_PARSER])

    @property
    def is_production(self) -> bool:
        """
        判断是否为生产环境

        Returns:
            bool: 如果环境为 production 则返回 True
        """
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """
        判断是否为开发环境

        Returns:
            bool: 如果环境为 development 则返回 True
        """
        return self.environment == "development"


# 全局配置实例（模块级单例）
settings = Settings()


def get_settings() -> Settings:
    """
    获取全局配置实例

    返回模块级的配置单例，避免重复创建配置对象。

    Returns:
        Settings: 全局配置实例
    """
    return settings