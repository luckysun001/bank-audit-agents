# 银行审计多智能体平台

多智能体协同的银行审计框架，通过角色分工协作完成审计流程。

[![CI](https://github.com/luckysun001/bank-audit-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/luckysun001/bank-audit-agents/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **状态：Beta (v1.0.0)** — Agent 架构、编排器与三种审计流水线已实现；
> 5 个 Agent 的执行逻辑均为 **LLM 驱动 + mock 回退**双模式：配置 `openai_api_key` 走真实模型，未配置自动降级为示例数据。

---

## 已实现

### 核心层

- **BaseAgent 抽象基类**（`core/base_agent.py`）：状态机（`AgentStatus`/`TaskStatus`）、
  任务重试与超时、消息队列（请求/响应、未读与最近消息）、会话历史与知识注入、回调机制、健康检查
- **AgentOrchestrator 编排器**（`core/orchestrator.py`）：Agent 注册与按类型/空闲择优选派、
  优先级任务队列、任务依赖图（依赖未满足则挂起）、批量提交、超时监控、优雅关闭、
  指标采集（平均耗时 / **P95** / 运行时长）、结果汇总与查询
- **四组后台 worker**：任务执行、消息路由、监控、超时巡检

### Agent 与流水线

- **5 个 Agent 实现**，全部接入 `LLMClient`（真实 LLM 优先，mock 兜底）：
  - `DocumentParser` — 资料收集与要素抽取
  - `ComplianceChecker` — 合规检查
  - `RiskIdentifier` — 风险识别
  - `ReportWriter` — 报告编写（LLM 增强建议生成）
  - `QualityCoordinator` — 质量复核 + 任务协调
- **三种审计流水线**（`workflows/audit_pipeline.py`）：信贷审计 / 合规审计 / 财务审计，
  由 `WorkflowExecutor` 按步骤执行、聚合 findings 并抽取最终报告，`AuditPipeline` 统一管理模板

### 支撑能力

- **LLM 客户端**（`utils/llm_client.py`）：基于 `AsyncOpenAI` 的 `chat` / `chat_json`（JSON 模式），
  请求级缓存，`call_with_fallback` 在调用失败时无缝切回 mock；`is_mock_mode` 可查询当前模式
- **工具层**（`tools/`）：此前各 Agent 的 `get_tools()` 只返回工具名字符串，现补上真正可执行的骨架
  - `tools/base.py` — `ToolSpec` / `ToolResult` / `ToolRegistry` 与 `@tool` 装饰器；
    `BaseAgent` 新增 `resolve_tools()`（把工具名解析为可执行对象）、`call_tool()`（统一返回 `ToolResult`，
    工具不存在也不抛异常）、`describe_tools()`（供拼装 Prompt）
  - `tools/rules.py` — **审计规则引擎**：规则为声明式描述（指标 + 运算符 + 阈值），
    内置 28 条常用监管指标（大额风险暴露集中度、不良率、拨备覆盖率、资本充足率、LCR/NSFR、
    反洗钱报送时限与资料保存、整改率等），支持按分类/严重级别过滤、`override_threshold()` 覆盖阈值、
    导出为 YAML/JSON。**阈值为参考值，落地请以最新监管文件与机构内部政策为准**
  - `tools/document_tools.py` — 文档结构化抽取：金额（元/万元/亿元自动换算到元）、百分比、
    日期归一化、当事主体（甲方/借款人/保证人…）、条款分段、综合摘要
  - `tools/document_loader.py` — **文档加载与 OCR**：PDF / Word / Excel / 图片 / 文本 -> 纯文本。
    PDF 优先取文本层，**判定为扫描件（平均每页字符数过少）时才转 OCR**；
    OCR 后端支持 tesseract 与 PaddleOCR，缺失时抛 `MissingDependencyError` 并给出安装命令
    （不静默返回空文本 —— 静默失败在审计场景里等于漏审）。
    `DocumentParserAgent` 已真正接入该层，提取方式与告警会写入 `metadata["extraction"]`
- **安全工具**（`utils/security.py`）：输入校验（查询/文档引用/报告标题的注入模式检测）、
  数据脱敏（账号 / 身份证 / 手机号）、API Key 常量时间比较校验、审计日志落盘、审计中间件工厂
- **Streamlit Dashboard**（`ui/dashboard.py`）：审计流程与结果的可视化界面
- **配置管理**（`config/settings.py`）：Pydantic Settings，支持 `.env`
- **结构化日志**（`utils/logger.py`）+ `verify.py` 一键自检脚本

## 未实现（TODO）

- **工具层仍不完整**：规则引擎、文档结构化抽取、文档加载与 OCR 已实现，
  但 **OCR 依赖需自行安装**（`pip install pytesseract` + 系统 tesseract 二进制，或 `pip install paddleocr`），
  扫描版 PDF 转图片还需 `pymupdf` 或 `pdf2image` + poppler；外部检索工具未接入
- **无 Prompt 模板文件**：各 Agent 的 Prompt 内联在代码中，未抽取为 YAML 模板
- **规则库规模有限**：内置 28 条常用监管指标，未覆盖此前声称的 200+ 条；规则可声明式扩展
- **记忆系统空缺**：`memory/` 仅有 `__init__.py`，长期记忆 / 向量记忆未落地
- **可观测性未接线**：Redis 缓存、Prometheus 指标导出、OpenTelemetry 链路追踪仅声明依赖
- **测试覆盖**：已有 `base_agent`、`orchestrator`、工具层（`test_tools.py`）、规则引擎（`test_rules.py`）、
  文档加载（`test_document_loader.py`）、5 类业务 Agent（`test_agents.py`，用 FakeLLM 注入）与
  工作流端到端（`test_workflows.py`）共 **135 个用例**；Dashboard / 记忆系统等仍无测试

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
│   ├── core/
│   │   ├── base_agent.py       # BaseAgent 抽象基类
│   │   └── orchestrator.py     # 多智能体编排器
│   ├── agents/
│   │   ├── document_parser.py        # 资料收集（LLM 驱动，mock fallback）
│   │   ├── compliance_checker.py     # 合规检查（LLM 驱动，mock fallback）
│   │   ├── risk_identifier.py        # 风险识别（LLM 驱动，mock fallback）
│   │   ├── report_writer.py          # 报告编写（LLM 驱动，mock fallback）
│   │   └── quality_and_coordinator.py# 质量复核 + 任务协调
│   ├── workflows/
│   │   └── audit_pipeline.py   # 审计流水线（信贷/合规/财务）
│   ├── config/
│   │   └── settings.py         # Pydantic Settings
│   ├── memory/                 # 记忆系统（TODO）
│   ├── tools/                  # 工具层
│   │   ├── base.py             # 工具抽象与注册表
│   │   ├── rules.py            # 审计规则引擎（内置 28 条监管指标）
│   │   ├── document_tools.py   # 文档结构化抽取（金额/比率/日期/主体/条款）
│   │   └── document_loader.py  # 文档加载与 OCR（PDF/Word/Excel/图片 -> 文本）
│   ├── ui/
│   │   └── dashboard.py        # Streamlit Dashboard
│   └── utils/
│       ├── logger.py           # 结构化日志
│       ├── security.py         # 输入校验 / 数据脱敏 / 鉴权 / 审计日志
│       └── llm_client.py       # LLM 客户端（真实 API + mock fallback）
│
├── docker/                     # Docker 配置
├── examples/
│   ├── 01_single_agent.py
│   ├── 02_orchestrator.py
│   └── 03_credit_audit_workflow.py
└── tests/
    ├── conftest.py             # FakeLLM 注入（不发真实请求）
    ├── test_base_agent.py
    ├── test_orchestrator.py
    ├── test_tools.py
    ├── test_rules.py
    ├── test_document_loader.py
    ├── test_agents.py          # 5 类业务 Agent
    └── test_workflows.py       # 工作流端到端
```

---

## 快速开始

```bash
cd 03-banking-audit-suite/bank-audit-agents
poetry install          # 或 pip install -e .
cp .env.example .env    # 可选：填入 OPENAI_API_KEY 切换到真实 LLM
python examples/01_single_agent.py
python verify.py        # 自检：不配 Key 也能跑通（mock 模式）
```

不配置 API Key 时所有 Agent 自动以 mock 模式运行，便于先验证编排与流水线是否通畅。

---

## 🔗 相关项目

本仓库解决「**多个 Agent 怎么分工协作跑完一整套审计流程**」。

如果你关心「审计知识怎么被准确检索和引用」，推荐作者的另一个开源项目：

> ### 🔍 [银行审计 RAG 系统（audit-rag）](https://github.com/luckysun001/audit-rag)
> 向量库 + Embedding + RAG 引擎，把法规与合同原文检索出来再交给模型作答。

| | 本仓库（bank-audit-agents） | audit-rag |
|---|---|---|
| **核心问题** | 审计任务的多角色协同 | 审计知识检索与引用 |
| **关键组件** | BaseAgent、Orchestrator、流水线 | 向量库、Embedding、RAG 引擎 |
| **典型用法** | 拆解审计项目 → 分派 Agent → 汇总报告 | 提问 → 检索法规/合同 → 生成结论 |

想系统学习背后的原理，另见 [AI-Learning-Playground](https://github.com/luckysun001/AI-Learning-Playground)。

---

## 技术栈

- Python 3.11+（3.10 已 EOL，且 chromadb 依赖的 onnxruntime 自 1.24.4 起不再发布 cp310 轮子）
- asyncio（编排与并发，自研实现，未依赖第三方编排框架）
- OpenAI Python SDK（AsyncOpenAI，LLM 调用）
- Pydantic v2 / pydantic-settings（配置与数据模型）
- Streamlit（Dashboard）
- structlog（日志）

> 说明：`pyproject.toml` 中声明的 LangChain / LangGraph / ChromaDB 属于规划中的可选依赖，
> 当前代码并未直接引用，编排层为自研 asyncio 实现。

---

## 许可证

MIT
