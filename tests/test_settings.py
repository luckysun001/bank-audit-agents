"""配置模块测试：默认值、环境判定、智能体配置、单例。"""

from bank_audit_agents.config.settings import AgentType, Settings, WorkflowType, get_settings


def _settings(**overrides) -> Settings:
    # 强制覆盖 api key，避免测试环境的环境变量影响 mock/available 判定
    return Settings(openai_api_key=None, **overrides)


def test_default_values():
    s = _settings()
    assert s.project_name == "Bank Audit Agents"
    assert s.log_level == "INFO"
    assert s.llm_max_retries == 3
    assert s.llm_max_tokens == 4096
    assert s.api_cors_origins == ["http://localhost:8501"]
    assert s.sensitive_fields == [
        "password",
        "api_key",
        "secret",
        "token",
        "credential",
        "account_number",
        "id_card",
        "phone",
        "email",
    ]
    assert s.report_formats == ["md", "docx", "pdf"]


def test_environment_flags():
    prod = _settings(environment="production")
    assert prod.is_production is True
    assert prod.is_development is False

    dev = _settings(environment="development")
    assert dev.is_development is True
    assert dev.is_production is False


def test_get_agent_config_per_type():
    s = _settings()
    risk = s.get_agent_config(AgentType.RISK_IDENTIFIER)
    assert risk.agent_type == AgentType.RISK_IDENTIFIER
    assert risk.temperature == 0.3
    assert "risk_pattern_matcher" in risk.enabled_tools

    compliance = s.get_agent_config(AgentType.COMPLIANCE_CHECKER)
    assert compliance.temperature == 0.1

    coordinator = s.get_agent_config(AgentType.TASK_COORDINATOR)
    assert coordinator.agent_type == AgentType.TASK_COORDINATOR


def test_get_agent_config_unknown_falls_back_to_document_parser():
    s = _settings()
    # 仅枚举内类型存在，验证兜底分支不抛错
    cfg = s.get_agent_config(AgentType.DOCUMENT_PARSER)
    assert cfg.agent_type == AgentType.DOCUMENT_PARSER


def test_workflow_type_enum():
    assert WorkflowType.CREDIT_AUDIT.value == "credit_audit"
    assert WorkflowType.AML_AUDIT.value == "aml_audit"


def test_get_settings_singleton():
    assert get_settings() is get_settings()
