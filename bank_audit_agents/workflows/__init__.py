"""
银行审计多智能体平台 - 工作流编排模块

本模块负责定义和执行各种标准化的审计工作流程，实现审计任务的自动化编排。

核心组件:
    1. WorkflowTemplate: 工作流模板抽象基类（模板方法模式）
    2. WorkflowExecutor: 工作流执行器，管理步骤执行顺序和结果聚合
    3. AuditPipeline: 审计流水线，提供高层 API 接口
    4. WorkflowStep: 工作流步骤数据类
    5. WorkflowResult: 工作流执行结果数据类
    6. WorkflowStatus: 工作流状态枚举

预定义工作流模板:
    - CreditAuditWorkflow: 信贷审计工作流（文档解析→风险识别→合规检查→报告生成→质量审核）
    - ComplianceAuditWorkflow: 合规审计工作流（监管政策解析→业务资料解析→反洗钱检查→合规检查→报告生成）
    - FinancialAuditWorkflow: 财务审计工作流（财务数据解析→异常检测→财务合规检查→报告生成）

设计模式:
    - 模板方法模式: WorkflowTemplate 定义步骤框架，子类实现具体步骤
    - 执行者模式: WorkflowExecutor 将工作流定义与执行逻辑分离

核心功能:
    - 工作流模板注册和管理
    - 步骤依赖关系定义和解析
    - 输入输出映射（步骤间数据传递）
    - 步骤结果聚合和最终报告提取
    - 必需步骤失败的工作流终止机制
"""
