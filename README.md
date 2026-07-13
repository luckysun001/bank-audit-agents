# 银行审计多智能体平台

多智能体协同的银行审计框架，通过角色分工协作完成审计流程。

> **状态：Alpha (v1.0.0)** — Agent 架构和编排器已实现，Agent 执行逻辑当前为 mock 模拟，真实 LLM 集成为 TODO。

---

## 已实现

- **BaseAgent 抽象基类**：含状态机、消息队列、回调机制、健康检查
- **5 个 Agent 实现**：
  - DocumentParser（资料收集）
  - ComplianceChecker（合规检查）
  - RiskIdentifier（风险识别）
  - ReportWriter（报告编写）
  - QualityCoordinator（质量复核 + 任务协调）
- **Orchestrator 编排器**：优先级队列、任务依赖图、超时监控、优雅关闭、P95 指标
- **审计流水线**：信贷审计、合规审计、财务审计三种工作流模板
- **Streamlit Dashboard**：基础可视化界面
- **配置管理**：Pydantic Settings

## 当前限制

- **Agent execute 方法支持 LLM / Mock 双模式**：当配置 `openai_api_key` 时使用真实 LLM 调用驱动审计逻辑；未配置时自动回退到示例数据（mock fallback）
- **无工具层**：README 声称的文档解析器、OCR、规则引擎、搜索工具均未实现
- **无 Prompt 模板**：声称的 YAML Prompt 模板未实现
- **无审计规则库**：声称的 200+ 监管规则未实现
- **测试覆盖有限**：仅 base_agent 和 orchestrator 的单元测试

---

## 项目结构

```text
bank-audit-agents/
├── pyproject.toml              # Poetry 依赖配置
├── .env.example                # 环境变量示例
├── docker-compose.yml          # Docker Compose 编排
├── Makefile                    # 常用命令
├── start.sh                    # 启动脚本
├── pytest.ini                  # 测试配置
├── verify.py                   # 验证脚本
│
├── bank_audit_agents/          # 核心代码
│   ├── __init__.py
│   ├── core/                   # 核心层
│   │   ├── base_agent.py       # BaseAgent 抽象基类
│   │   └── orchestrator.py     # 多智能体编排器
│   ├── agents/                 # Agent 实现
│   │   ├── document_parser.py       # 资料收集 Agent（LLM 驱动，mock fallback）
│   │   ├── compliance_checker.py    # 合规检查 Agent（LLM 驱动，mock fallback）
│   │   ├── risk_identifier.py       # 风险识别 Agent（LLM 驱动，mock fallback）
│   │   ├── report_writer.py         # 报告编写 Agent（LLM 增强建议生成）
│   │   └── quality_and_coordinator.py # 质量复核 + 任务协调 Agent（LLM 驱动质量检查）
│   ├── workflows/              # 工作流
│   │   └── audit_pipeline.py   # 审计流水线（信贷/合规/财务）
│   ├── config/                 # 配置
│   │   └── settings.py         # Pydantic Settings
│   ├── memory/                 # 记忆系统（仅 __init__.py）
│   ├── ui/                     # 前端界面
│   │   └── dashboard.py        # Streamlit Dashboard
│   └── utils/                  # 工具函数
│       ├── logger.py           # 日志
│       ├── security.py         # 安全工具（CORS/认证/审计日志/数据脱敏）
│       └── llm_client.py       # LLM 客户端（OpenAI 驱动，mock fallback）
│
├── docker/                     # Docker 配置
│   └── Dockerfile
├── examples/                   # 示例代码
│   ├── 01_single_agent.py
│   ├── 02_orchestrator.py
│   └── 03_credit_audit_workflow.py
└── tests/                      # 测试
    ├── test_base_agent.py
    └── test_orchestrator.py
```

---

## 快速开始

```bash
cd 03-banking-audit-suite/bank-audit-agents
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY
```

---

## 技术栈

- Python 3.10+
- LangChain / LangGraph（Agent 编排，TODO 集成）
- FastAPI（API 框架）
- Streamlit（Dashboard）
- Pydantic v2（配置管理）
- structlog（日志）
- Redis（缓存，TODO）
- Prometheus / OpenTelemetry（监控，TODO）

---

## 许可证

MIT
