"""
报告撰写智能体模块

负责生成银行审计报告，整合各智能体的分析结果。

核心能力:
    1. 整合多智能体分析结果
    2. 生成结构化审计报告
    3. 报告格式标准化（Word/PDF/HTML）
    4. 关键发现和建议汇总

报告类型:
    - 信贷审计报告
    - 合规审计报告
    - 风险评估报告
    - 综合审计报告

工作模式:
    - LLM 模式：使用 LLM 进行智能报告生成
    - Mock 模式：未配置 API Key 时，返回示例报告内容
"""

from typing import Any, Dict, List, Optional

from bank_audit_agents.core.base_agent import (
    AgentResult,
    AgentType,
    BaseAgent,
    Task,
)
from bank_audit_agents.utils.logger import get_logger
from bank_audit_agents.utils.llm_client import get_llm_client

# 获取模块级日志记录器
logger = get_logger(__name__)


# 报告模板定义（模拟）
REPORT_TEMPLATES = {
    # 信贷审计报告模板
    "loan_audit": {
        "title": "信贷业务审计报告",
        "sections": [
            {"name": "审计概况", "order": 1},
            {"name": "文档解析结果", "order": 2},
            {"name": "合规检查结果", "order": 3},
            {"name": "风险识别结果", "order": 4},
            {"name": "关键发现", "order": 5},
            {"name": "整改建议", "order": 6},
            {"name": "审计结论", "order": 7},
        ],
    },
    # 合规审计报告模板
    "compliance_audit": {
        "title": "合规审计报告",
        "sections": [
            {"name": "审计概况", "order": 1},
            {"name": "合规检查结果", "order": 2},
            {"name": "违规事项汇总", "order": 3},
            {"name": "风险评估", "order": 4},
            {"name": "整改建议", "order": 5},
            {"name": "审计结论", "order": 6},
        ],
    },
    # 风险评估报告模板
    "risk_assessment": {
        "title": "风险评估报告",
        "sections": [
            {"name": "评估概况", "order": 1},
            {"name": "风险识别结果", "order": 2},
            {"name": "风险敞口分析", "order": 3},
            {"name": "风险等级评估", "order": 4},
            {"name": "风险缓释建议", "order": 5},
            {"name": "评估结论", "order": 6},
        ],
    },
    # 综合审计报告模板
    "comprehensive": {
        "title": "综合审计报告",
        "sections": [
            {"name": "审计概况", "order": 1},
            {"name": "文档解析结果", "order": 2},
            {"name": "合规检查结果", "order": 3},
            {"name": "风险识别结果", "order": 4},
            {"name": "关键发现", "order": 5},
            {"name": "风险评估", "order": 6},
            {"name": "整改建议", "order": 7},
            {"name": "审计结论", "order": 8},
        ],
    },
}


class ReportWriterAgent(BaseAgent):
    """
    报告撰写智能体

    继承自 BaseAgent，实现审计报告生成的核心业务逻辑。

    核心职责:
        1. 整合各智能体的分析结果
        2. 根据报告类型选择合适的模板
        3. 生成结构化的审计报告
        4. 汇总关键发现和整改建议

    输入数据要求:
        - report_type: 报告类型（loan_audit/compliance_audit/risk_assessment/comprehensive）
        - audit_data: 审计数据（包含各智能体的分析结果）
        - report_format: 报告格式（可选，默认 markdown）
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """
        初始化报告撰写智能体

        Args:
            agent_id: 智能体 ID（可选，不提供则自动生成）
            **kwargs: 其他传递给父类的参数
        """
        super().__init__(AgentType.REPORT_WRITER, agent_id, **kwargs)
        # 获取 LLM 客户端（支持 mock fallback）
        self._llm = get_llm_client()
        # 加载报告模板
        self._report_templates = REPORT_TEMPLATES

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        定义智能体的角色为银行审计报告专家，明确职责和输出要求。

        Returns:
            str: 系统提示词文本
        """
        return """你是一位资深银行审计报告专家，具有15年以上审计报告撰写经验。

你的核心职责:
1. 整合各智能体的分析结果，生成结构化审计报告
2. 清晰呈现审计发现、风险评估和整改建议
3. 确保报告内容准确、客观、专业
4. 符合银行审计报告的格式规范和语言要求

报告撰写标准:
- 结构清晰，逻辑严谨
- 数据准确，来源明确
- 语言专业，表达简洁
- 建议具体，可操作性强

输出要求:
- 以结构化 JSON 格式输出，包含 report_content 对象
- report_content 包含：title, sections 数组
- 每个 section 包含：name, content
"""

    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        列出报告撰写相关的工具，实际项目中会接入真实的报告生成工具。

        Returns:
            List[Any]: 工具名称列表
        """
        return [
            "report_template_loader",    # 报告模板加载器
            "data_aggregator",           # 数据聚合工具
            "format_converter",          # 格式转换工具（MD→PDF/Word）
            "report_validator",          # 报告验证工具
            "report_storer",             # 报告存储工具
        ]

    async def execute(self, task: Task) -> AgentResult:
        """
        执行报告撰写任务

        核心执行流程:
            1. 验证输入参数（报告类型、审计数据）
            2. 根据报告类型选择模板
            3. 整合各智能体的分析结果
            4. 调用 _generate_report_content 生成报告内容
            5. 调用 _format_report 格式化报告
            6. 返回包含报告内容的 AgentResult

        Args:
            task: 任务对象，包含输入数据

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"报告撰写智能体开始处理任务: {task.task_id}")

        # 从任务输入数据中提取参数
        report_type = task.input_data.get("report_type", "comprehensive")
        audit_data = task.input_data.get("audit_data", {})
        report_format = task.input_data.get("report_format", "markdown")

        # 验证必填参数
        if not audit_data:
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少审计数据参数",
                error="audit_data is required",
                confidence_score=0.0,
            )

        # 获取报告模板
        template = self._get_report_template(report_type)

        # 整合各智能体的分析结果
        aggregated_data = self._aggregate_audit_data(audit_data)

        # 生成报告内容（LLM 驱动，mock 模式下回退到示例数据）
        report_content = await self._generate_report_content(
            report_type, template, aggregated_data
        )

        # 格式化报告
        formatted_report = self._format_report(report_content, report_format)

        # 生成摘要
        summary = self._generate_summary(report_type, report_content)

        # 返回执行结果
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=summary,
            findings=report_content,
            recommendations=[
                "建议对报告内容进行人工审核",
                "建议按照整改建议制定整改计划",
            ],
            confidence_score=0.88,
            metadata={
                "report_type": report_type,
                "report_format": report_format,
                "sections_count": len(report_content.get("sections", [])),
                "source_data_sources": len(audit_data),
            },
        )

    def _get_report_template(self, report_type: str) -> Dict[str, Any]:
        """
        获取报告模板

        根据报告类型选择合适的模板，如果未找到则使用默认模板。

        Args:
            report_type: 报告类型

        Returns:
            Dict[str, Any]: 报告模板
        """
        return self._report_templates.get(report_type, self._report_templates["comprehensive"])

    def _aggregate_audit_data(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        整合审计数据

        将各智能体的分析结果整合成统一的数据结构，便于报告生成。

        Args:
            audit_data: 原始审计数据（各智能体的分析结果）

        Returns:
            Dict[str, Any]: 整合后的审计数据
        """
        aggregated = {
            "document_parser": audit_data.get("document_parser", {}),
            "compliance_checker": audit_data.get("compliance_checker", {}),
            "risk_identifier": audit_data.get("risk_identifier", {}),
            "quality_coordinator": audit_data.get("quality_coordinator", {}),
        }

        # 汇总所有发现和建议
        all_findings = []
        all_recommendations = []

        for agent_name, agent_data in aggregated.items():
            if isinstance(agent_data, dict):
                findings = agent_data.get("findings", [])
                recommendations = agent_data.get("recommendations", [])
                if isinstance(findings, list):
                    all_findings.extend(findings)
                if isinstance(recommendations, list):
                    all_recommendations.extend(recommendations)

        aggregated["all_findings"] = all_findings
        aggregated["all_recommendations"] = all_recommendations

        return aggregated

    async def _generate_report_content(
        self, report_type: str, template: Dict[str, Any], aggregated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成报告内容

        工作机制:
            1. 构造报告生成提示词
            2. 调用 LLM 进行智能报告撰写
            3. 如果 LLM 不可用，使用 mock fallback 返回示例报告内容

        Args:
            report_type: 报告类型
            template: 报告模板
            aggregated_data: 整合后的审计数据

        Returns:
            Dict[str, Any]: 报告内容
        """
        # 构造用户提示词
        user_prompt = {
            "report_type": report_type,
            "template": template,
            "audit_data": aggregated_data,
            "writing_requirements": "请根据审计数据和模板，撰写一份专业的银行审计报告。",
        }

        # 定义 mock fallback 函数，返回示例报告内容
        def _mock_fallback():
            return self._get_mock_report_content(report_type, template)

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict) and "report_content" in result:
            return result["report_content"]
        elif isinstance(result, dict):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_report_content(report_type, template)

    def _get_mock_report_content(self, report_type: str, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        返回示例报告内容（mock fallback）

        根据报告类型和模板返回不同的示例报告数据，
        用于开发测试和演示目的。

        Args:
            report_type: 报告类型
            template: 报告模板

        Returns:
            Dict[str, Any]: 示例报告内容
        """
        # 获取模板定义的章节
        sections = []
        for section_def in template.get("sections", []):
            section_name = section_def["name"]

            if section_name == "审计概况":
                sections.append({
                    "name": "审计概况",
                    "content": """## 审计概况

### 审计对象
本次审计对象为某某科技有限公司的信贷业务。

### 审计范围
- 信贷合同合规性审查
- 风险评估与管理
- 内部控制有效性评价

### 审计方法
- 文档资料审查
- 合规性检查
- 风险识别与评估

### 审计期间
2024年1月1日至2024年12月31日""",
                })

            elif section_name == "文档解析结果":
                sections.append({
                    "name": "文档解析结果",
                    "content": """## 文档解析结果

### 提取的关键信息
| 字段 | 值 | 置信度 |
|------|-----|--------|
| 借款人 | 某某科技有限公司 | 99% |
| 贷款金额 | 500万元 | 95% |
| 贷款期限 | 12个月 | 98% |
| 利率 | 4.35% | 92% |
| 担保人 | 某某担保集团 | 90% |

### 文档分类
- 文档类型：信贷合同
- 文档状态：有效""",
                })

            elif section_name == "合规检查结果":
                sections.append({
                    "name": "合规检查结果",
                    "content": """## 合规检查结果

### 违规事项汇总
1. **贷款审批流程不合规**
   - 法规依据：商业银行互联网贷款管理暂行办法（CBIRC-2020-5）
   - 违规描述：缺少风控部门独立审批环节
   - 风险等级：中
   - 整改建议：补充风控部门独立审批环节

2. **利率定价超授权**
   - 法规依据：信贷业务审批管理办法（INT-LOAN-001）
   - 违规描述：利率超出授权范围0.5个百分点
   - 风险等级：高
   - 整改建议：调整利率至授权范围""",
                })

            elif section_name == "风险识别结果":
                sections.append({
                    "name": "风险识别结果",
                    "content": """## 风险识别结果

### 识别的风险项
1. **信用风险**
   - 描述：借款人资产负债率较高，存在违约风险
   - 概率：中
   - 影响：严重
   - 敞口金额：300万元

2. **市场风险**
   - 描述：利率敏感性较高，利率上升可能导致利差收窄
   - 概率：中
   - 影响：中等
   - 敞口金额：200万元

3. **操作风险**
   - 描述：审批流程存在权限管理漏洞
   - 概率：低
   - 影响：中等
   - 敞口金额：50万元

### 整体风险评估
- 综合风险评分：5.5分
- 整体风险等级：中""",
                })

            elif section_name == "关键发现":
                sections.append({
                    "name": "关键发现",
                    "content": """## 关键发现

### 主要问题
1. **合规风险突出**：存在2项违规事项，其中1项为高风险
2. **信用风险值得关注**：借款人财务状况一般，需加强贷后管理
3. **内部控制存在缺陷**：审批流程权限管理不够完善

### 问题根源分析
- 制度执行不到位
- 风险管理意识有待加强
- 流程监控机制不完善""",
                })

            elif section_name == "整改建议":
                sections.append({
                    "name": "整改建议",
                    "content": """## 整改建议

### 短期措施（1-3个月）
1. 立即调整贷款利率至授权范围内
2. 补充风控部门独立审批环节
3. 完善权限管理体系

### 中期措施（3-6个月）
1. 建立定期合规检查机制
2. 加强员工合规培训
3. 优化贷后管理流程

### 长期措施（6个月以上）
1. 建立风险预警机制
2. 完善内部控制体系
3. 加强风险管理文化建设""",
                })

            elif section_name == "审计结论":
                sections.append({
                    "name": "审计结论",
                    "content": """## 审计结论

### 总体评价
本次信贷业务审计发现存在一定的合规风险和信用风险，整体风险等级为中等。

### 审计意见
1. **保留意见**：建议对发现的问题进行整改
2. **整改期限**：建议在3个月内完成整改
3. **后续跟踪**：建议对整改情况进行后续跟踪检查

### 报告日期
2024年12月31日""",
                })

            else:
                sections.append({
                    "name": section_name,
                    "content": f"## {section_name}\n\n本章节内容待补充。",
                })

        return {
            "title": template.get("title", "审计报告"),
            "sections": sections,
        }

    def _format_report(self, report_content: Dict[str, Any], report_format: str) -> str:
        """
        格式化报告

        将结构化报告内容转换为指定格式的文本。

        Args:
            report_content: 结构化报告内容
            report_format: 报告格式（markdown/html/pdf/word）

        Returns:
            str: 格式化后的报告文本
        """
        if report_format == "markdown":
            return self._format_to_markdown(report_content)
        elif report_format == "html":
            return self._format_to_html(report_content)
        else:
            return self._format_to_markdown(report_content)

    def _format_to_markdown(self, report_content: Dict[str, Any]) -> str:
        """
        转换为 Markdown 格式

        Args:
            report_content: 结构化报告内容

        Returns:
            str: Markdown 格式报告
        """
        lines = []
        lines.append(f"# {report_content.get('title', '审计报告')}")
        lines.append("")

        for section in report_content.get("sections", []):
            lines.append(section.get("content", ""))
            lines.append("")

        return "\n".join(lines)

    def _format_to_html(self, report_content: Dict[str, Any]) -> str:
        """
        转换为 HTML 格式

        Args:
            report_content: 结构化报告内容

        Returns:
            str: HTML 格式报告
        """
        lines = []
        lines.append("<!DOCTYPE html>")
        lines.append("<html lang='zh-CN'>")
        lines.append("<head>")
        lines.append(f"<title>{report_content.get('title', '审计报告')}</title>")
        lines.append("<meta charset='UTF-8'>")
        lines.append("<style>body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }</style>")
        lines.append("</head>")
        lines.append("<body>")

        for section in report_content.get("sections", []):
            content = section.get("content", "")
            content = content.replace("# ", "<h1>").replace("#", "</h1>")
            content = content.replace("## ", "<h2>").replace("##", "</h2>")
            content = content.replace("### ", "<h3>").replace("###", "</h3>")
            content = content.replace("**", "<strong>").replace("**", "</strong>")
            content = content.replace("\n", "<br>")
            lines.append(content)

        lines.append("</body>")
        lines.append("</html>")

        return "\n".join(lines)

    def _generate_summary(self, report_type: str, report_content: Dict[str, Any]) -> str:
        """
        生成报告摘要

        根据报告类型和内容生成简洁的摘要文本。

        Args:
            report_type: 报告类型
            report_content: 报告内容

        Returns:
            str: 报告摘要
        """
        section_count = len(report_content.get("sections", []))
        title = report_content.get("title", "审计报告")

        return f"{title}已生成，共包含{section_count}个章节"