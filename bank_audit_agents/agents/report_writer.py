"""
报告撰写智能体 - 独立优化版

核心能力:
1. 标准化审计报告生成
2. 问题分级归类和描述
3. 风险评估汇总和趋势分析
4. 整改建议智能生成
5. 多格式导出（Markdown、Word、PDF、HTML）
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from bank_audit_agents.core.base_agent import (
    AgentResult,
    AgentType,
    BaseAgent,
    Task,
)
from bank_audit_agents.utils.logger import get_logger
from bank_audit_agents.utils.llm_client import get_llm_client

logger = get_logger(__name__)


class ReportFormat(str):
    """报告格式"""
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN_TEXT = "plain_text"


class ReportStyle(str):
    """报告风格"""
    STANDARD = "standard"
    CONCISE = "concise"
    DETAILED = "detailed"
    REGULATORY = "regulatory"


@dataclass
class ReportSection:
    """报告章节"""
    title: str
    content: str
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        return f"## {self.title}\n\n{self.content}\n\n"


@dataclass
class AuditFinding:
    """审计发现项"""
    finding_id: str
    category: str
    risk_level: str  # critical, high, medium, low
    title: str
    description: str
    basis: str = ""  # 审计依据
    evidence: str = ""
    recommendation: str = ""
    severity_score: float = 0.0

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        level_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }.get(self.risk_level, "⚪")

        return (
            f"{level_emoji} **{self.title}**\n\n"
            f"**分类**: {self.category} | **风险等级**: {self.risk_level.upper()}\n\n"
            f"**问题描述**: {self.description}\n\n"
            + (f"**审计依据**: {self.basis}\n\n" if self.basis else "")
            + (f"**审计证据**: {self.evidence}\n\n" if self.evidence else "")
            + (f"**整改建议**: {self.recommendation}\n\n" if self.recommendation else "")
        )


class ReportTemplate:
    """报告模板"""

    @staticmethod
    def get_header(
        project_name: str,
        audited_unit: str,
        audit_period: str,
    ) -> str:
        """获取报告头部"""
        return f"""# {project_name} 审计报告

| 项目 | 内容 |
|------|------|
| **被审计单位** | {audited_unit} |
| **审计期间** | {audit_period} |
| **报告日期** | {datetime.now().strftime('%Y年%m月%d日')} |

---
"""

    @staticmethod
    def get_summary_section(
        total_findings: int,
        risk_distribution: Dict[str, int],
        compliance_score: float,
    ) -> ReportSection:
        """获取摘要章节"""
        critical = risk_distribution.get("critical", 0)
        high = risk_distribution.get("high", 0)
        medium = risk_distribution.get("medium", 0)
        low = risk_distribution.get("low", 0)

        overall_assessment = ""
        if critical > 0 or high >= 3:
            overall_assessment = "整体风险较高，存在重大问题，需立即整改"
        elif high > 0 or medium >= 5:
            overall_assessment = "存在一定风险，需制定整改计划"
        else:
            overall_assessment = "整体风险可控，运营较为规范"

        content = f"""本次审计共发现问题 **{total_findings}** 项，风险分布如下：

- 🔴 **严重风险**: {critical} 项
- 🟠 **高风险**: {high} 项
- 🟡 **中风险**: {medium} 项
- 🟢 **低风险**: {low} 项

**综合合规评分**: {compliance_score:.1f}/100

**整体评估**: {overall_assessment}
"""
        return ReportSection(title="一、审计摘要", content=content, order=1)

    @staticmethod
    def get_findings_section(findings: List[AuditFinding]) -> ReportSection:
        """获取审计发现章节"""
        content_parts = ["### 主要问题\n\n"]

        # 按风险等级排序
        sorted_findings = sorted(
            findings,
            key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                f.risk_level, 99
            ),
        )

        for finding in sorted_findings:
            content_parts.append(finding.to_markdown())

        return ReportSection(
            title="二、审计发现的主要问题",
            content="\n".join(content_parts),
            order=2,
        )

    @staticmethod
    def get_recommendations_section(recommendations: List[str]) -> ReportSection:
        """获取整改建议章节"""
        content = "### 主要整改建议\n\n"
        for i, rec in enumerate(recommendations, 1):
            content += f"{i}. {rec}\n\n"

        return ReportSection(title="三、整改建议", content=content, order=3)

    @staticmethod
    def get_conclusion_section(conclusion_text: str) -> ReportSection:
        """获取结论章节"""
        return ReportSection(title="四、审计结论", content=conclusion_text, order=4)

    @staticmethod
    def get_footer() -> str:
        """获取报告页脚"""
        return f"""---

*本报告由智能审计系统自动生成，如有疑问请联系审计部门。*
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.sections: List[ReportSection] = []

    def add_section(self, section: ReportSection) -> None:
        """添加章节"""
        self.sections.append(section)
        self.sections.sort(key=lambda s: s.order)

    def generate_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        parts = []
        for section in self.sections:
            parts.append(section.to_markdown())
        parts.append(ReportTemplate.get_footer())
        return "\n".join(parts)

    def generate_plain_text(self) -> str:
        """生成纯文本格式报告"""
        markdown = self.generate_markdown()
        # 简单的 Markdown 到纯文本转换
        text = markdown.replace("## ", "").replace("### ", "")
        text = text.replace("**", "").replace("`", "")
        return text

    def generate_html(self) -> str:
        """生成 HTML 格式报告"""
        md_content = self.generate_markdown()

        # 简单的 Markdown 到 HTML 转换（实际可使用 markdown 库）
        html_content = md_content.replace("## ", "<h2>").replace("\n\n", "</h2>\n\n")
        html_content = html_content.replace("### ", "<h3>").replace("\n\n", "</h3>\n\n")
        html_content = html_content.replace("**", "<strong>").replace("**", "</strong>")

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>审计报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 10px; }}
        h2 {{ color: #2d3748; margin-top: 30px; }}
        h3 {{ color: #4a5568; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 12px; text-align: left; }}
        th {{ background-color: #f7fafc; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""


class ReportWriterAgent(BaseAgent):
    """
    报告撰写智能体

    负责整合各智能体的输出，生成标准化的审计报告。
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.REPORT_WRITER, agent_id, **kwargs)
        self.report_generator = ReportGenerator()
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
        return """你是一位资深银行审计报告撰写专家，具有15年以上审计报告撰写经验。

你的核心职责:
1. 生成专业、规范、准确的审计报告
2. 对审计发现进行结构化整理和分级归类
3. 撰写专业的风险评估和影响分析
4. 提出有针对性、可落地的整改建议
5. 确保报告符合银行审计规范和监管要求

报告撰写原则:
- 客观中立：基于事实描述，避免主观臆断
- 条理清晰：使用规范的审计报告结构
- 专业严谨：使用审计专业术语，表述准确无误
- 重点突出：高风险问题优先，突出重点
- 可操作性：整改建议具体明确，可落地执行

输出要求:
- 结构完整：摘要、审计发现、风险评估、整改建议、结论
- 分类清晰：按风险等级和业务领域分类展示问题
- 表述专业：使用标准审计术语
- 建议可行：整改建议具体、可衡量、可实现
"""

    def get_tools(self) -> List[Any]:
        """获取可用工具列表"""
        return [
            "report_template_engine",
            "recommendation_generator",
            "risk_aggregator",
            "format_converter",
            "audit_lexicon",
        ]

    async def execute(self, task: Task) -> AgentResult:
        """执行报告撰写任务"""
        logger.info(f"📝 报告撰写智能体开始处理任务: {task.task_id}")

        findings_data = task.input_data.get("findings", [])
        audit_context = task.input_data.get("audit_context", {})
        report_style = task.input_data.get("report_style", ReportStyle.STANDARD)
        output_format = task.input_data.get("output_format", ReportFormat.MARKDOWN)

        try:
            # 1. 处理审计发现
            processed_findings = self._process_findings(findings_data)

            # 2. 分析风险分布
            risk_distribution = self._analyze_risk_distribution(processed_findings)

            # 3. 计算合规得分
            compliance_score = self._calculate_compliance_score(processed_findings)

            # 4. 生成整改建议
            recommendations = self._generate_recommendations(processed_findings)

            # 5. 生成报告
            report_content = self._generate_report(
                findings=processed_findings,
                risk_distribution=risk_distribution,
                compliance_score=compliance_score,
                recommendations=recommendations,
                context=audit_context,
                style=report_style,
                output_format=output_format,
            )

            # 6. 生成统计摘要
            summary = self._generate_summary(processed_findings, compliance_score)

            result = AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=True,
                summary=summary,
                findings=[{"type": "report_generated", "content": f"报告包含 {len(processed_findings)} 个发现项"}],
                recommendations=recommendations,
                confidence_score=0.95,
                output_data={
                    "report_content": report_content,
                    "report_format": output_format,
                    "findings_count": len(processed_findings),
                    "risk_distribution": risk_distribution,
                    "compliance_score": compliance_score,
                },
            )

            logger.info(f"✅ 报告生成完成: {len(processed_findings)} 个发现项")
            return result

        except Exception as e:
            logger.error(f"❌ 报告生成失败: {str(e)}")
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary=f"报告生成失败: {str(e)}",
                error=str(e),
                confidence_score=0.0,
            )

    def _process_findings(self, findings_data: List[Dict[str, Any]]) -> List[AuditFinding]:
        """处理审计发现数据"""
        findings = []

        for i, data in enumerate(findings_data):
            finding = AuditFinding(
                finding_id=data.get("finding_id", f"FIND-{i:03d}"),
                category=data.get("category", "其他"),
                risk_level=data.get("risk_level", "medium"),
                title=data.get("title", f"问题 {i+1}"),
                description=data.get("description", ""),
                basis=data.get("basis", ""),
                evidence=data.get("evidence", ""),
                recommendation=data.get("recommendation", ""),
                severity_score=data.get("severity_score", 0.5),
            )
            findings.append(finding)

        return findings

    def _analyze_risk_distribution(self, findings: List[AuditFinding]) -> Dict[str, int]:
        """分析风险分布"""
        distribution: Dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for finding in findings:
            level = finding.risk_level.lower()
            if level in distribution:
                distribution[level] += 1

        return distribution

    def _calculate_compliance_score(self, findings: List[AuditFinding]) -> float:
        """计算合规得分 (0-100)"""
        if not findings:
            return 100.0

        # 风险权重
        weights = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 2,
        }

        total_deduction = sum(
            weights.get(f.risk_level.lower(), 5) for f in findings
        )

        return max(100.0 - total_deduction, 0.0)

    def _generate_recommendations(self, findings: List[AuditFinding]) -> List[str]:
        """生成整改建议"""
        recommendations = []

        # 按严重程度统计
        critical_count = sum(1 for f in findings if f.risk_level == "critical")
        high_count = sum(1 for f in findings if f.risk_level == "high")

        if critical_count + high_count > 0:
            recommendations.append(
                f"针对发现的 {critical_count} 项严重风险和 {high_count} 项高风险问题，"
                f"建议立即成立专项整改小组，制定详细整改计划。"
            )

        # 按分类生成建议
        categories = set(f.category for f in findings)
        for category in categories:
            category_findings = [f for f in findings if f.category == category]
            recommendations.append(
                f"针对{category}领域发现的 {len(category_findings)} 项问题，"
                f"建议开展专项检查，完善相关制度流程。"
            )

        # 通用建议
        recommendations.append(
            "建立问题台账，明确整改责任人、整改期限和验收标准，"
            "定期跟踪整改进度，确保整改工作落到实处。"
        )

        recommendations.append(
            "加强员工培训，提升合规意识和风险防范能力，"
            "建立健全内部控制长效机制。"
        )

        return recommendations

    def _generate_report(
        self,
        findings: List[AuditFinding],
        risk_distribution: Dict[str, int],
        compliance_score: float,
        recommendations: List[str],
        context: Dict[str, Any],
        style: str,
        output_format: str,
    ) -> str:
        """生成报告内容"""
        generator = ReportGenerator()

        # 添加报告头部
        project_name = context.get("project_name", "审计项目")
        audited_unit = context.get("audited_unit", "被审计单位")
        audit_period = context.get("audit_period", "审计期间")
        header = ReportTemplate.get_header(project_name, audited_unit, audit_period)

        # 添加摘要章节
        summary_section = ReportTemplate.get_summary_section(
            total_findings=len(findings),
            risk_distribution=risk_distribution,
            compliance_score=compliance_score,
        )
        generator.add_section(summary_section)

        # 添加审计发现章节
        if findings:
            findings_section = ReportTemplate.get_findings_section(findings)
            generator.add_section(findings_section)

        # 添加整改建议章节
        rec_section = ReportTemplate.get_recommendations_section(recommendations)
        generator.add_section(rec_section)

        # 添加结论章节
        conclusion_text = self._generate_conclusion(compliance_score, len(findings))
        conclusion_section = ReportTemplate.get_conclusion_section(conclusion_text)
        generator.add_section(conclusion_section)

        # 根据格式输出
        if output_format == ReportFormat.HTML:
            return header + generator.generate_html()
        elif output_format == ReportFormat.PLAIN_TEXT:
            return header + generator.generate_plain_text()
        else:  # Markdown
            return header + generator.generate_markdown()

    async def _generate_recommendations_llm(self, findings: List[AuditFinding]) -> List[str]:
        """使用 LLM 生成整改建议（mock 模式下回退到模板生成）"""
        findings_summary = json.dumps([
            {"category": f.category, "risk_level": f.risk_level, "title": f.title, "description": f.description}
            for f in findings
        ], ensure_ascii=False)

        def _template_fallback():
            return self._generate_recommendations(findings)

        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含一个 'recommendations' 数组，每个元素是一个字符串。",
            user_prompt=f"根据以下审计发现，生成有针对性的整改建议：\n{findings_summary}",
            fallback_fn=_template_fallback,
            response_format_json=True,
        )

        if isinstance(result, dict) and "recommendations" in result:
            return result["recommendations"]
        elif isinstance(result, list):
            return result
        else:
            return self._generate_recommendations(findings)

    def _generate_conclusion(self, compliance_score: float, finding_count: int) -> str:
        """生成审计结论"""
        if compliance_score >= 90:
            assessment = "整体运营情况良好，内部控制有效，风险可控。"
        elif compliance_score >= 75:
            assessment = "整体运营较为规范，存在一定风险隐患，需持续改进。"
        elif compliance_score >= 60:
            assessment = "存在较多风险隐患，内部控制有待加强，需认真整改。"
        else:
            assessment = "存在严重风险隐患，内部控制存在重大缺陷，需立即整改。"

        return f"""本次审计共发现问题 {finding_count} 项，综合合规评分 {compliance_score:.1f} 分。

{assessment}

希望被审计单位高度重视本次审计发现的问题，认真落实各项整改措施，举一反三，持续完善内部控制体系，提升风险管理水平。

审计组将持续跟踪整改进展，适时开展整改回头看，确保审计成果得到有效应用。
"""

    def _generate_summary(self, findings: List[AuditFinding], compliance_score: float) -> str:
        """生成执行摘要"""
        level_counts = {
            "critical": sum(1 for f in findings if f.risk_level == "critical"),
            "high": sum(1 for f in findings if f.risk_level == "high"),
            "medium": sum(1 for f in findings if f.risk_level == "medium"),
        }

        return (
            f"审计报告已生成，共发现问题 {len(findings)} 项，"
            f"其中严重风险 {level_counts['critical']} 项，"
            f"高风险 {level_counts['high']} 项，"
            f"中风险 {level_counts['medium']} 项，"
            f"综合合规评分 {compliance_score:.1f} 分。"
        )
