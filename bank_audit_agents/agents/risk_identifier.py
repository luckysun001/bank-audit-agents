"""
风险识别智能体
深度分析文档内容，识别各类审计风险点
"""
import json
from typing import Any, Dict, List, Optional

from bank_audit_agents.core.base_agent import (
    AgentResult,
    AgentType,
    BaseAgent,
    Task,
)
from bank_audit_agents.utils.logger import get_logger
from bank_audit_agents.utils.llm_client import get_llm_client

logger = get_logger(__name__)


class RiskLevel(str):
    """风险等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskIdentifierAgent(BaseAgent):
    """
    风险识别智能体

    核心能力:
    1. 信贷风险识别（信用风险、集中度风险、担保风险等）
    2. 合规风险识别（监管政策违规、内部制度违规等）
    3. 财务风险识别（财务造假、异常交易、偿债能力等）
    4. 操作风险识别（流程缺陷、内部控制漏洞等）
    5. 风险评级和优先级排序
    """

    # 风险模式库（实际项目中会扩展为完整的风险规则库）
    RISK_PATTERNS = {
        "credit_risk": [
            {"pattern": "逾期", "level": RiskLevel.HIGH, "category": "信贷风险"},
            {"pattern": "欠息", "level": RiskLevel.HIGH, "category": "信贷风险"},
            {"pattern": "不良", "level": RiskLevel.MEDIUM, "category": "信贷风险"},
            {"pattern": "重组贷款", "level": RiskLevel.HIGH, "category": "信贷风险"},
            {"pattern": "借新还旧", "level": RiskLevel.HIGH, "category": "信贷风险"},
        ],
        "compliance_risk": [
            {"pattern": "违反.*规定", "level": RiskLevel.MEDIUM, "category": "合规风险"},
            {"pattern": "未按.*执行", "level": RiskLevel.MEDIUM, "category": "合规风险"},
            {"pattern": "越权审批", "level": RiskLevel.HIGH, "category": "合规风险"},
            {"pattern": "流程不符", "level": RiskLevel.LOW, "category": "合规风险"},
        ],
        "financial_risk": [
            {"pattern": "亏损", "level": RiskLevel.HIGH, "category": "财务风险"},
            {"pattern": "资不抵债", "level": RiskLevel.CRITICAL, "category": "财务风险"},
            {"pattern": "现金流紧张", "level": RiskLevel.HIGH, "category": "财务风险"},
            {"pattern": "负债率过高", "level": RiskLevel.MEDIUM, "category": "财务风险"},
        ],
        "guarantee_risk": [
            {"pattern": "担保不足", "level": RiskLevel.HIGH, "category": "担保风险"},
            {"pattern": "抵押物不足值", "level": RiskLevel.HIGH, "category": "担保风险"},
            {"pattern": "互保圈", "level": RiskLevel.CRITICAL, "category": "担保风险"},
        ],
    }

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.RISK_IDENTIFIER, agent_id, **kwargs)
        self.risk_database: Dict[str, Any] = {}  # 风险知识库
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
        return """你是一位资深银行风险识别专家，具有20年银行风险管理经验。

你的核心职责:
1. 从审计文档中精准识别各类风险点，包括但不限于：
   - 信贷风险：信用风险、集中度风险、担保风险、期限错配风险
   - 合规风险：监管政策违规、内部制度违反、反洗钱风险
   - 财务风险：财务造假、偿债能力恶化、异常交易
   - 操作风险：流程缺陷、内部控制漏洞、系统风险
   - 集中度风险：行业集中、客户集中、区域集中

2. 风险评级标准:
   - 严重(CRITICAL): 可能造成重大损失，需立即整改
   - 高(HIGH): 可能造成较大损失，需重点关注
   - 中(MEDIUM): 存在风险隐患，需限期整改
   - 低(LOW): 轻微问题，建议改进

3. 输出要求:
   - 每个风险点需明确：风险描述、风险等级、风险类别、影响程度
   - 标注风险在文档中的具体位置
   - 提供风险发生可能性评估
   - 给出初步的风险缓释建议
"""

    def get_tools(self) -> List[Any]:
        return [
            "risk_pattern_matcher",
            "anomaly_detector",
            "trend_analyzer",
            "risk_classifier",
            "impact_assessor",
            "knowledge_base_retriever",
        ]

    async def execute(self, task: Task) -> AgentResult:
        logger.info(f"风险识别智能体开始处理任务: {task.task_id}")

        document_content = task.input_data.get("document_content", "")
        document_type = task.input_data.get("document_type", "general")
        risk_focus = task.input_data.get("risk_focus", [])  # 指定关注的风险类型

        if not document_content:
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少文档内容",
                error="document_content is required",
                confidence_score=0.0,
            )

        # 执行风险识别（LLM 驱动，mock 模式下回退到示例数据）
        identified_risks = await self._identify_risks(
            document_content, document_type, risk_focus
        )

        # 风险评级
        rated_risks = self._rate_risks(identified_risks)

        # 统计分析
        risk_summary = self._generate_risk_summary(rated_risks)

        # 生成建议
        recommendations = self._generate_recommendations(rated_risks)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=risk_summary,
            findings=rated_risks,
            recommendations=recommendations,
            confidence_score=self._calculate_confidence(rated_risks),
            metadata={
                "total_risks": len(rated_risks),
                "critical_count": sum(1 for r in rated_risks if r["level"] == RiskLevel.CRITICAL),
                "high_count": sum(1 for r in rated_risks if r["level"] == RiskLevel.HIGH),
                "medium_count": sum(1 for r in rated_risks if r["level"] == RiskLevel.MEDIUM),
                "low_count": sum(1 for r in rated_risks if r["level"] == RiskLevel.LOW),
                "document_type": document_type,
            },
        )

    async def _identify_risks(
        self, content: str, document_type: str, risk_focus: List[str]
    ) -> List[Dict[str, Any]]:
        """
        识别风险点
        - LLM 模式：将文档内容发送给 LLM 进行风险分析
        - Mock 模式：返回示例风险数据
        """
        user_prompt = json.dumps({
            "document_content": content[:4000],
            "document_type": document_type,
            "risk_focus": risk_focus,
        }, ensure_ascii=False)

        def _mock_fallback():
            return self._get_mock_risks(risk_focus)

        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含一个 'risks' 数组，每个元素包含字段：risk_id, description, category, level(critical/high/medium/low), location, evidence, likelihood(0-1)。",
            user_prompt=user_prompt,
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        if isinstance(result, dict) and "risks" in result:
            risks = result["risks"]
        elif isinstance(result, list):
            risks = result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            risks = self._get_mock_risks(risk_focus)

        # 确保每个风险都有 level 字段
        for risk in risks:
            if "level" not in risk:
                risk["level"] = RiskLevel.MEDIUM
            elif isinstance(risk["level"], str) and risk["level"].upper() not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
                risk["level"] = RiskLevel.MEDIUM

        return risks

    def _get_mock_risks(self, risk_focus: List[str]) -> List[Dict[str, Any]]:
        """返回示例风险数据（mock fallback）"""
        mock_risks = [
            {
                "risk_id": "RISK_001",
                "description": "发现借新还旧迹象，贷款可能存在隐性不良风险",
                "category": "信贷风险",
                "level": RiskLevel.HIGH,
                "location": "第5页贷款用途描述",
                "evidence": "贷款用途为'流动资金周转'，但原贷款即将到期",
                "likelihood": 0.85,
            },
            {
                "risk_id": "RISK_002",
                "description": "抵押物评估价值偏高，抵押率实际超过监管要求",
                "category": "担保风险",
                "level": RiskLevel.MEDIUM,
                "location": "第8页抵押物评估报告",
                "evidence": "评估价较市场均价高15%，实际抵押率约83%",
                "likelihood": 0.70,
            },
            {
                "risk_id": "RISK_003",
                "description": "借款人资产负债率超过70%，偿债压力较大",
                "category": "财务风险",
                "level": RiskLevel.MEDIUM,
                "location": "第3页财务报表摘要",
                "evidence": "资产负债率72.3%，较上年上升5.6个百分点",
                "likelihood": 0.95,
            },
            {
                "risk_id": "RISK_004",
                "description": "贷款审批流程缺少关键审批人签字",
                "category": "合规风险",
                "level": RiskLevel.HIGH,
                "location": "第10页审批表",
                "evidence": "分行风险总监审批位置空白，仅有电子印章",
                "likelihood": 0.90,
            },
        ]

        if risk_focus:
            return [r for r in mock_risks if r["category"] in risk_focus]
        return mock_risks

    def _rate_risks(self, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对识别的风险进行评级和排序"""
        for risk in risks:
            # 计算综合风险得分（实际会使用更复杂的评分模型）
            likelihood = risk.get("likelihood", 0.5)
            impact = self._get_impact_weight(risk["level"])
            risk["risk_score"] = likelihood * impact

            # 添加风险等级标签
            risk["level_label"] = {
                RiskLevel.CRITICAL: "🔴 严重风险",
                RiskLevel.HIGH: "🟠 高风险",
                RiskLevel.MEDIUM: "🟡 中风险",
                RiskLevel.LOW: "🟢 低风险",
                RiskLevel.INFO: "🔵 提示",
            }.get(risk["level"], "未知")

        # 按风险得分降序排序
        risks.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
        return risks

    def _get_impact_weight(self, level: str) -> float:
        """获取风险等级对应的影响权重"""
        weights = {
            RiskLevel.CRITICAL: 1.0,
            RiskLevel.HIGH: 0.8,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.LOW: 0.2,
            RiskLevel.INFO: 0.1,
        }
        return weights.get(level, 0.3)

    def _generate_risk_summary(self, risks: List[Dict[str, Any]]) -> str:
        """生成风险汇总摘要"""
        if not risks:
            return "未识别到明显风险点"

        level_counts = {}
        for risk in risks:
            level = risk["level"]
            level_counts[level] = level_counts.get(level, 0) + 1

        critical = level_counts.get(RiskLevel.CRITICAL, 0)
        high = level_counts.get(RiskLevel.HIGH, 0)
        medium = level_counts.get(RiskLevel.MEDIUM, 0)
        low = level_counts.get(RiskLevel.LOW, 0)

        summary_parts = [
            f"共识别风险点{len(risks)}个",
        ]

        if critical > 0:
            summary_parts.append(f"严重风险{critical}个")
        if high > 0:
            summary_parts.append(f"高风险{high}个")
        if medium > 0:
            summary_parts.append(f"中风险{medium}个")
        if low > 0:
            summary_parts.append(f"低风险{low}个")

        return "，".join(summary_parts)

    def _generate_recommendations(self, risks: List[Dict[str, Any]]) -> List[str]:
        """生成风险缓释建议"""
        recommendations = []

        # 高优先级风险建议
        high_risks = [r for r in risks if r["level"] in [RiskLevel.CRITICAL, RiskLevel.HIGH]]
        if high_risks:
            recommendations.append(
                f"⚠️ 立即关注{len(high_risks)}个高/严重风险点，制定专项整改方案"
            )

        # 分类建议
        categories = set(r["category"] for r in risks)
        for category in categories:
            category_risks = [r for r in risks if r["category"] == category]
            recommendations.append(
                f"📋 针对{category}领域的{len(category_risks)}个风险点，"
                f"建议开展专项检查，完善控制措施"
            )

        # 通用建议
        recommendations.append("🔄 建立风险台账，定期跟踪整改进度")
        recommendations.append("📊 完善风险识别规则库，提高自动化识别覆盖率")

        return recommendations

    def _calculate_confidence(self, risks: List[Dict[str, Any]]) -> float:
        """计算整体置信度"""
        if not risks:
            return 0.5

        avg_likelihood = sum(r.get("likelihood", 0.5) for r in risks) / len(risks)
        return min(avg_likelihood + 0.1, 1.0)  # 基础置信度加10%
