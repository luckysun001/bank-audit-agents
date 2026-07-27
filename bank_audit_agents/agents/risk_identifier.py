"""
风险识别智能体模块

负责识别和评估银行审计过程中的各类风险。

核心能力:
    1. 信用风险识别（借款人信用状况评估）
    2. 市场风险识别（利率、汇率波动风险）
    3. 操作风险识别（流程缺陷、内部控制不足）
    4. 流动性风险识别（资金流动性管理）
    5. 风险等级评估和风险敞口计算

风险评估维度:
    - 风险发生概率（高/中/低）
    - 风险影响程度（严重/中等/轻微）
    - 风险敞口金额
    - 风险缓释措施评估

工作模式:
    - LLM 模式：使用 LLM 进行智能风险分析
    - Mock 模式：未配置 API Key 时，返回示例风险识别结果
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


# 风险类型定义（模拟）
RISK_TYPES = {
    # 信用风险
    "credit_risk": {
        "name": "信用风险",
        "description": "借款人无法按时偿还本息的风险",
        "key_indicators": ["还款能力", "信用记录", "资产负债率", "现金流状况"],
    },
    # 市场风险
    "market_risk": {
        "name": "市场风险",
        "description": "因市场价格波动导致资产损失的风险",
        "key_indicators": ["利率敏感性", "汇率波动", "资产价格变动"],
    },
    # 操作风险
    "operational_risk": {
        "name": "操作风险",
        "description": "因内部控制缺陷或人为失误导致的风险",
        "key_indicators": ["流程完整性", "权限管理", "审计追踪"],
    },
    # 流动性风险
    "liquidity_risk": {
        "name": "流动性风险",
        "description": "银行无法及时满足资金需求的风险",
        "key_indicators": ["资金缺口", "存款稳定性", "融资渠道"],
    },
    # 合规风险
    "compliance_risk": {
        "name": "合规风险",
        "description": "违反监管规定导致处罚的风险",
        "key_indicators": ["法规遵循度", "政策执行情况", "违规历史"],
    },
}


class RiskIdentifierAgent(BaseAgent):
    """
    风险识别智能体

    继承自 BaseAgent，实现风险识别的核心业务逻辑。

    核心职责:
        1. 根据业务数据识别潜在风险
        2. 评估风险等级和影响程度
        3. 计算风险敞口金额
        4. 提出风险缓释建议

    输入数据要求:
        - business_type: 业务类型（如 loan, investment, deposit）
        - business_data: 业务数据（包含具体业务信息）
        - risk_scope: 风险评估范围（可选，默认 all）
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """
        初始化风险识别智能体

        Args:
            agent_id: 智能体 ID（可选，不提供则自动生成）
            **kwargs: 其他传递给父类的参数
        """
        super().__init__(AgentType.RISK_IDENTIFIER, agent_id, **kwargs)
        # 获取 LLM 客户端（支持 mock fallback）
        self._llm = get_llm_client()
        # 加载风险类型定义
        self._risk_types = RISK_TYPES

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        定义智能体的角色为银行风险专家，明确职责和输出要求。

        Returns:
            str: 系统提示词文本
        """
        return """你是一位资深银行风险专家，具有12年以上银行风险管理经验。

你的核心职责:
1. 识别业务中存在的各类风险（信用风险、市场风险、操作风险、流动性风险等）
2. 评估风险发生概率（高/中/低）和影响程度（严重/中等/轻微）
3. 计算风险敞口金额
4. 提出具体的风险缓释措施和管理建议

风险评估标准:
- 信用风险：评估借款人信用状况、还款能力、担保措施
- 市场风险：评估利率、汇率、资产价格变动影响
- 操作风险：评估流程缺陷、内部控制、人为因素
- 流动性风险：评估资金流动性、融资能力

输出要求:
- 以结构化 JSON 格式输出，包含 risks 数组
- 每个风险项包含：risk_type, risk_name, risk_description, probability(high/middle/low), impact(severe/medium/mild), exposure_amount, recommendation
"""

    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        列出风险识别相关的工具，实际项目中会接入真实的风险评估工具。

        Returns:
            List[Any]: 工具名称列表
        """
        return [
            "credit_scoring",         # 信用评分工具
            "market_risk_model",      # 市场风险模型
            "operational_risk_model", # 操作风险模型
            "liquidity_analysis",     # 流动性分析工具
            "risk_database",          # 风险数据库查询
        ]

    async def execute(self, task: Task) -> AgentResult:
        """
        执行风险识别任务

        核心执行流程:
            1. 验证输入参数（业务类型、业务数据）
            2. 根据业务类型确定风险评估维度
            3. 调用 _identify_risks 识别风险
            4. 调用 _calculate_overall_risk 计算整体风险评分
            5. 调用 _generate_recommendations 生成风险缓释建议
            6. 返回包含风险识别结果的 AgentResult

        Args:
            task: 任务对象，包含输入数据

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"风险识别智能体开始处理任务: {task.task_id}")

        # 从任务输入数据中提取参数
        business_type = task.input_data.get("business_type")
        business_data = task.input_data.get("business_data", {})
        risk_scope = task.input_data.get("risk_scope", "all")

        # 验证必填参数
        if not business_type:
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少业务类型参数",
                error="business_type is required",
                confidence_score=0.0,
            )

        # 根据业务类型确定风险评估维度
        risk_dimensions = self._determine_risk_dimensions(business_type, risk_scope)

        # 执行风险识别（LLM 驱动，mock 模式下回退到示例数据）
        risks = await self._identify_risks(
            business_type, business_data, risk_dimensions
        )

        # 计算整体风险评分
        overall_risk_score = self._calculate_overall_risk(risks)

        # 评估整体风险等级
        overall_risk_level = self._assess_overall_risk_level(overall_risk_score)

        # 生成风险缓释建议
        recommendations = self._generate_recommendations(risks)

        # 生成摘要
        summary = self._generate_summary(business_type, risks, overall_risk_level)

        # 返回执行结果
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=summary,
            findings=risks,
            recommendations=recommendations,
            confidence_score=self._calculate_confidence(risks),
            metadata={
                "business_type": business_type,
                "risk_scope": risk_scope,
                "risk_count": len(risks),
                "overall_risk_score": overall_risk_score,
                "overall_risk_level": overall_risk_level,
                "total_exposure": sum(r.get("exposure_amount", 0) for r in risks),
            },
        )

    def _determine_risk_dimensions(self, business_type: str, scope: str) -> List[str]:
        """
        根据业务类型确定风险评估维度

        根据业务类型和风险评估范围，确定需要评估的风险类型。

        Args:
            business_type: 业务类型
            scope: 风险评估范围（all/credit/market/operational/liquidity）

        Returns:
            List[str]: 风险评估维度列表
        """
        if scope != "all":
            return [scope]

        # 根据业务类型自动确定风险维度
        dimension_map = {
            "loan": ["credit_risk", "operational_risk"],
            "investment": ["market_risk", "credit_risk"],
            "deposit": ["liquidity_risk", "operational_risk"],
            "foreign_exchange": ["market_risk", "liquidity_risk"],
        }

        return dimension_map.get(business_type, list(self._risk_types.keys()))

    async def _identify_risks(
        self, business_type: str, business_data: Dict[str, Any], dimensions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        识别风险

        工作机制:
            1. 构造风险识别提示词
            2. 调用 LLM 进行智能风险分析
            3. 如果 LLM 不可用，使用 mock fallback 返回示例风险识别结果

        Args:
            business_type: 业务类型
            business_data: 业务数据
            dimensions: 风险评估维度

        Returns:
            List[Dict[str, Any]]: 风险识别结果列表
        """
        # 获取风险类型详细信息
        risk_info = {dim: self._risk_types[dim] for dim in dimensions if dim in self._risk_types}

        # 构造用户提示词
        user_prompt = {
            "business_type": business_type,
            "business_data": business_data,
            "risk_dimensions": dimensions,
            "risk_type_info": risk_info,
            "analysis_requirements": "请根据业务数据，识别各风险维度下的具体风险，并评估风险等级。",
        }

        # 定义 mock fallback 函数，返回示例风险识别结果
        def _mock_fallback():
            return self._get_mock_risks(business_type, dimensions)

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict) and "risks" in result:
            return result["risks"]
        elif isinstance(result, list):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_risks(business_type, dimensions)

    def _get_mock_risks(self, business_type: str, dimensions: List[str]) -> List[Dict[str, Any]]:
        """
        返回示例风险识别结果（mock fallback）

        根据业务类型和风险维度返回不同的示例风险数据，
        用于开发测试和演示目的。

        Args:
            business_type: 业务类型
            dimensions: 风险评估维度

        Returns:
            List[Dict[str, Any]]: 示例风险识别结果列表
        """
        mock_risks = []

        # 根据风险维度生成示例风险
        for dim in dimensions:
            risk_type_info = self._risk_types.get(dim, {})

            if dim == "credit_risk":
                mock_risks.append({
                    "risk_type": "credit_risk",
                    "risk_name": risk_type_info.get("name", "信用风险"),
                    "risk_description": "借款人资产负债率较高，现金流紧张，存在违约风险",
                    "probability": "middle",
                    "impact": "severe",
                    "exposure_amount": 3000000,
                    "recommendation": "加强贷后管理，密切监控借款人财务状况",
                })

            elif dim == "market_risk":
                mock_risks.append({
                    "risk_type": "market_risk",
                    "risk_name": risk_type_info.get("name", "市场风险"),
                    "risk_description": "贷款组合利率敏感性较高，利率上升可能导致利差收窄",
                    "probability": "middle",
                    "impact": "medium",
                    "exposure_amount": 2000000,
                    "recommendation": "优化利率风险管理，考虑使用利率互换工具",
                })

            elif dim == "operational_risk":
                mock_risks.append({
                    "risk_type": "operational_risk",
                    "risk_name": risk_type_info.get("name", "操作风险"),
                    "risk_description": "贷款审批流程存在权限管理漏洞，可能导致违规操作",
                    "probability": "low",
                    "impact": "medium",
                    "exposure_amount": 500000,
                    "recommendation": "完善权限管理体系，加强流程监控",
                })

            elif dim == "liquidity_risk":
                mock_risks.append({
                    "risk_type": "liquidity_risk",
                    "risk_name": risk_type_info.get("name", "流动性风险"),
                    "risk_description": "中长期贷款占比较高，可能导致资金期限错配",
                    "probability": "low",
                    "impact": "medium",
                    "exposure_amount": 1500000,
                    "recommendation": "优化资产负债结构，拓宽融资渠道",
                })

            elif dim == "compliance_risk":
                mock_risks.append({
                    "risk_type": "compliance_risk",
                    "risk_name": risk_type_info.get("name", "合规风险"),
                    "risk_description": "部分贷款合同条款不符合最新监管要求",
                    "probability": "middle",
                    "impact": "medium",
                    "exposure_amount": 800000,
                    "recommendation": "审查并修订合同条款，确保合规性",
                })

        return mock_risks

    def _calculate_overall_risk(self, risks: List[Dict[str, Any]]) -> float:
        """
        计算整体风险评分

        根据各风险项的概率和影响程度计算综合风险评分。

        评分规则:
            - 概率权重：high=3, middle=2, low=1
            - 影响权重：severe=3, medium=2, mild=1
            - 综合评分 = Σ(概率权重 × 影响权重) / 风险项数

        Args:
            risks: 风险识别结果列表

        Returns:
            float: 整体风险评分（1-9）
        """
        if not risks:
            return 1.0

        # 定义概率和影响的权重映射
        prob_weights = {"high": 3, "middle": 2, "low": 1}
        impact_weights = {"severe": 3, "medium": 2, "mild": 1}

        total_score = 0
        for risk in risks:
            prob = prob_weights.get(risk.get("probability", "low"), 1)
            impact = impact_weights.get(risk.get("impact", "mild"), 1)
            total_score += prob * impact

        return round(total_score / len(risks), 2)

    def _assess_overall_risk_level(self, score: float) -> str:
        """
        评估整体风险等级

        根据整体风险评分确定风险等级。

        等级划分:
            - 高风险：7-9分
            - 中风险：4-6分
            - 低风险：1-3分

        Args:
            score: 整体风险评分

        Returns:
            str: 整体风险等级（high/middle/low）
        """
        if score >= 7:
            return "high"
        elif score >= 4:
            return "middle"
        else:
            return "low"

    def _generate_recommendations(self, risks: List[Dict[str, Any]]) -> List[str]:
        """
        生成风险缓释建议

        从风险识别结果中提取建议，并添加通用风险防控建议。

        Args:
            risks: 风险识别结果列表

        Returns:
            List[str]: 风险缓释建议列表
        """
        recommendations = []

        # 提取每个风险项的建议
        for risk in risks:
            rec = risk.get("recommendation")
            if rec and rec not in recommendations:
                recommendations.append(rec)

        # 添加通用风险防控建议
        if risks:
            recommendations.append("建议建立风险预警机制，及时发现潜在风险")
            recommendations.append("建议定期开展风险评估，动态调整风险管理策略")

        return recommendations

    def _generate_summary(
        self, business_type: str, risks: List[Dict[str, Any]], risk_level: str
    ) -> str:
        """
        生成风险识别摘要

        根据业务类型、风险数量和整体风险等级生成简洁的摘要文本。

        Args:
            business_type: 业务类型
            risks: 风险识别结果列表
            risk_level: 整体风险等级

        Returns:
            str: 风险识别摘要
        """
        risk_map = {"high": "高", "middle": "中", "low": "低"}

        if not risks:
            return f"{business_type}业务风险评估完成，未发现显著风险"

        total_exposure = sum(r.get("exposure_amount", 0) for r in risks)

        return (
            f"{business_type}业务风险识别完成，共识别{len(risks)}项风险，"
            f"总风险敞口{total_exposure}元，整体风险等级：{risk_map.get(risk_level, '未知')}"
        )

    def _calculate_confidence(self, risks: List[Dict[str, Any]]) -> float:
        """
        计算置信度分数

        根据风险项的数量和严重程度计算置信度。

        Args:
            risks: 风险识别结果列表

        Returns:
            float: 置信度分数（0-1）
        """
        if not risks:
            return 0.90

        # 严重风险降低置信度
        severe_count = sum(1 for r in risks if r.get("impact") == "severe")
        confidence = 0.85 - (severe_count * 0.05)

        return max(0.60, confidence)