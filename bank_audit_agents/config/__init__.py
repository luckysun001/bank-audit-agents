"""
银行审计多智能体平台 - 配置管理模块

本模块使用 Pydantic Settings 实现全局配置管理，支持从环境变量和 .env 文件加载配置。

核心组件:
    1. Settings: 全局配置类，包含所有系统配置项
    2. AgentType: 智能体类型枚举（文档解析、风险识别、合规检查等）
    3. WorkflowType: 工作流类型枚举（信贷审计、合规审计、财务审计等）
    4. AgentConfig: 单个智能体的配置类
    5. get_settings(): 获取全局配置实例的便捷函数

配置加载顺序:
    1. 默认值（代码中定义）
    2. .env 文件中的环境变量
    3. 操作系统环境变量（覆盖 .env 文件）

配置分类:
    - 基础配置: 环境、项目名、日志级别
    - LLM 配置: API Key、模型、温度、超时等
    - 智能体配置: 迭代次数、并行执行、内存等
    - 向量数据库配置: 存储类型、路径、集合名
    - Redis 配置: URL、启用状态、缓存 TTL
    - 审计追踪配置: 启用状态、路径、保留天数
    - 报告生成配置: 输出路径、格式、模板路径
    - UI 配置: 启用状态、端口、主题
    - API 配置: 主机、端口、工作进程数、CORS、安全等

使用示例:
    from bank_audit_agents.config.settings import get_settings
    settings = get_settings()
    print(settings.openai_api_key)
"""
