"""
合规检查智能体模块

负责检查银行审计相关业务的合规性，确保符合监管要求和内部政策。

核心能力:
    1. 监管法规匹配（银保监会、人民银行、外汇局等）
    2. 内部制度合规检查
    3. 合规风险等级评估
    4. 合规缺陷整改建议生成

合规检查维度:
    - 信贷业务合规（贷款审批、利率定价、期限管理）
    - 反洗钱合规（KYC、交易监控、可疑交易报告）
    - 资本充足率合规（资本计提、风险加权资产）
    - 信息披露合规（财务报告、监管报送）

工作模式:
    - LLM 模式：使用 LLM 进行智能合规分析
    - Mock 模式：未配置 API Key 时，返回示例合规检查结果
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


# 监管法规知识库（模拟）
REGULATORY_KNOWLEDGE = {
    # 银保监会相关法规
    "cbirc": {
        "name": "中国银保监会",
        "regulations": [
            {"code": "CBIRC-2020-5", "name": "商业银行互联网贷款管理暂行办法", "effective_date": "2020-07-01"},
            {"code": "CBIRC-2021-6", "name": "商业银行大额风险暴露管理办法", "effective_date": "2021-01-01"},
            {"code": "CBIRC-2022-1", "name": "商业银行资本管理办法", "effective_date": "2022-01-01"},
        ],
    },
    # 人民银行相关法规
    "pboc": {
        "name": "中国人民银行",
        "regulations": [
            {"code": "PBOC-2018-3", "name": "金融机构反洗钱规定", "effective_date": "2018-01-01"},
            {"code": "PBOC-2020-2", "name": "人民币银行结算账户管理办法", "effective_date": "2020-04-01"},
        ],
    },
    # 内部制度
    "internal": {
        "name": "银行内部制度",
        "regulations": [
            {"code": "INT-LOAN-001", "name": "信贷业务审批管理办法", "effective_date": "2021-06-01"},
            {"code": "INT-COMP-002", "name": "合规检查实施细则", "effective_date": "2022-01-01"},
            {"code": "INT-RISK-003", "name": "风险管理政策", "effective_date": "2022-03-01"},
        ],
    },
}


class ComplianceCheckerAgent(BaseAgent):
    """
    合规检查智能体

    继承自 BaseAgent，实现合规检查的核心业务逻辑。

    核心职责:
        1. 根据业务类型匹配相关法规
        2. 检查业务操作是否符合监管要求
        3. 识别合规缺陷并评估风险等级
        4. 生成合规整改建议

    输入数据要求:
        - business_type: 业务类型（如 loan, anti_money_laundering, capital_adequacy）
        - business_data: 业务数据（包含具体业务信息）
        - regulatory_scope: 监管范围（可选，默认 all）
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """
        初始化合规检查智能体

        Args:
            agent_id: 智能体 ID（可选，不提供则自动生成）
            **kwargs: 其他传递给父类的参数
        """
        super().__init__(AgentType.COMPLIANCE_CHECKER, agent_id, **kwargs)
        # 获取 LLM 客户端（支持 mock fallback）
        self._llm = get_llm_client()
        # 加载监管法规知识库
        self._regulatory_knowledge = REGULATORY_KNOWLEDGE

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        定义智能体的角色为银行合规专家，明确职责和输出要求。

        Returns:
            str: 系统提示词文本
        """
        return """你是一位资深银行合规专家，具有10年以上银行合规管理经验。

你的核心职责:
1. 根据业务类型匹配相关监管法规和内部制度
2. 检查业务操作是否符合合规要求
3. 识别合规缺陷并评估风险等级（高/中/低）
4. 为发现的合规问题提供具体的整改建议

合规检查标准:
- 信贷业务：审批流程、利率定价、期限管理、担保要求
- 反洗钱：客户身份识别、交易监控、可疑交易报告
- 资本充足：资本计提、风险加权资产计算、资本缓冲

输出要求:
- 以结构化 JSON 格式输出，包含 violations 数组
- 每个违规项包含：regulation_code, regulation_name, violation_description, risk_level, recommendation
- risk_level 取值：high/middle/low
"""

    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        列出合规检查相关的工具，实际项目中会接入真实的合规检查工具。

        Returns:
            List[Any]: 工具名称列表
        """
        return [
            "regulation_search",          # 法规检索工具
            "compliance_database",        # 合规数据库查询
            "internal_policy_check",      # 内部政策检查
            "risk_rating_tool",           # 风险评级工具
            "violation_history",          # 违规历史查询
        ]

    async def execute(self, task: Task) -> AgentResult:
        """
        执行合规检查任务

        核心执行流程:
            1. 验证输入参数（业务类型、业务数据）
            2. 根据业务类型匹配相关法规
            3. 调用 _check_compliance 执行合规检查
            4. 调用 _assess_risk_level 评估风险等级
            5. 调用 _generate_recommendations 生成整改建议
            6. 返回包含合规检查结果的 AgentResult

        Args:
            task: 任务对象，包含输入数据

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"合规检查智能体开始处理任务: {task.task_id}")

        # 从任务输入数据中提取参数
        business_type = task.input_data.get("business_type")
        business_data = task.input_data.get("business_data", {})
        regulatory_scope = task.input_data.get("regulatory_scope", "all")

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

        # 匹配相关法规
        applicable_regulations = self._match_regulations(business_type, regulatory_scope)

        # 执行合规检查（LLM 驱动，mock 模式下回退到示例数据）
        violations = await self._check_compliance(
            business_type, business_data, applicable_regulations
        )

        # 评估整体风险等级
        overall_risk_level = self._assess_risk_level(violations)

        # 生成整改建议
        recommendations = self._generate_recommendations(violations)

        # 生成摘要
        summary = self._generate_summary(business_type, violations, overall_risk_level)

        # 返回执行结果
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=summary,
            findings=violations,
            recommendations=recommendations,
            confidence_score=self._calculate_confidence(violations),
            metadata={
                "business_type": business_type,
                "regulatory_scope": regulatory_scope,
                "checked_regulations": len(applicable_regulations),
                "violation_count": len(violations),
                "overall_risk_level": overall_risk_level,
            },
        )

    def _match_regulations(self, business_type: str, scope: str) -> List[Dict[str, Any]]:
        """
        根据业务类型匹配相关法规

        根据业务类型和监管范围，从知识库中筛选适用的法规。

        Args:
            business_type: 业务类型
            scope: 监管范围（cbirc/pboc/internal/all）

        Returns:
            List[Dict[str, Any]]: 适用法规列表
        """
        all_regulations = []

        # 根据监管范围选择法规来源
        scopes = []
        if scope == "all":
            scopes = ["cbirc", "pboc", "internal"]
        else:
            scopes = [scope]

        # 收集所有适用法规
        for source in scopes:
            if source in self._regulatory_knowledge:
                all_regulations.extend(self._regulatory_knowledge[source]["regulations"])

        # 根据业务类型过滤法规
        filtered = []
        for reg in all_regulations:
            # 根据法规名称和业务类型进行匹配
            reg_name = reg["name"].lower()
            if (
                ("贷款" in reg["name"] and business_type in ["loan", "credit"]) or
                ("反洗钱" in reg["name"] and business_type == "anti_money_laundering") or
                ("资本" in reg["name"] and business_type == "capital_adequacy") or
                ("合规" in reg["name"]) or
                ("风险" in reg["name"])
            ):
                filtered.append(reg)

        return filtered

    async def _check_compliance(
        self, business_type: str, business_data: Dict[str, Any], regulations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        执行合规检查

        工作机制:
            1. 构造合规检查提示词
            2. 调用 LLM 进行智能合规分析
            3. 如果 LLM 不可用，使用 mock fallback 返回示例检查结果

        Args:
            business_type: 业务类型
            business_data: 业务数据
            regulations: 适用法规列表

        Returns:
            List[Dict[str, Any]]: 合规违规项列表
        """
        # 构造用户提示词
        user_prompt = {
            "business_type": business_type,
            "business_data": business_data,
            "applicable_regulations": regulations,
            "check_requirements": "请检查业务数据是否符合上述法规要求，列出所有违规项。",
        }

        # 定义 mock fallback 函数，返回示例合规检查结果
        def _mock_fallback():
            return self._get_mock_violations(business_type)

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict) and "violations" in result:
            return result["violations"]
        elif isinstance(result, list):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_violations(business_type)

    def _get_mock_violations(self, business_type: str) -> List[Dict[str, Any]]:
        """
        返回示例合规检查结果（mock fallback）

        根据业务类型返回不同的示例违规数据，
        用于开发测试和演示目的。

        Args:
            business_type: 业务类型

        Returns:
            List[Dict[str, Any]]: 示例违规项列表
        """
        if business_type == "loan":
            # 信贷业务示例违规
            return [
                {
                    "regulation_code": "CBIRC-2020-5",       # 法规编号
                    "regulation_name": "商业银行互联网贷款管理暂行办法",  # 法规名称
                    "violation_description": "贷款审批流程未完全符合规定，缺少风控部门独立审批环节",  # 违规描述
                    "risk_level": "middle",                   # 风险等级：中
                    "recommendation": "补充风控部门独立审批环节，完善审批流程",  # 整改建议
                },
                {
                    "regulation_code": "INT-LOAN-001",        # 内部制度编号
                    "regulation_name": "信贷业务审批管理办法",  # 内部制度名称
                    "violation_description": "贷款利率定价超出授权范围0.5个百分点",  # 违规描述
                    "risk_level": "high",                     # 风险等级：高
                    "recommendation": "调整利率至授权范围内，并对相关责任人进行问责",  # 整改建议
                },
            ]
        elif business_type == "anti_money_laundering":
            # 反洗钱业务示例违规
            return [
                {
                    "regulation_code": "PBOC-2018-3",         # 法规编号
                    "regulation_name": "金融机构反洗钱规定",   # 法规名称
                    "violation_description": "客户身份识别资料不完整，缺少受益所有人信息",  # 违规描述
                    "risk_level": "high",                     # 风险等级：高
                    "recommendation": "补充客户身份识别资料，完善受益所有人信息采集",  # 整改建议
                },
            ]
        elif business_type == "capital_adequacy":
            # 资本充足示例违规
            return [
                {
                    "regulation_code": "CBIRC-2022-1",       # 法规编号
                    "regulation_name": "商业银行资本管理办法",  # 法规名称
                    "violation_description": "风险加权资产计算存在偏差，部分资产分类不准确",  # 违规描述
                    "risk_level": "middle",                   # 风险等级：中
                    "recommendation": "重新评估资产分类，修正风险加权资产计算",  # 整改建议
                },
            ]
        else:
            # 默认示例违规
            return []

    def _assess_risk_level(self, violations: List[Dict[str, Any]]) -> str:
        """
        评估整体风险等级

        根据违规项的风险等级分布，确定整体合规风险等级。

        Args:
            violations: 违规项列表

        Returns:
            str: 整体风险等级（high/middle/low）
        """
        if not violations:
            return "low"

        # 统计各风险等级的数量
        high_count = sum(1 for v in violations if v.get("risk_level") == "high")
        middle_count = sum(1 for v in violations if v.get("risk_level") == "middle")

        # 根据规则确定整体风险等级
        if high_count > 0:
            return "high"
        elif middle_count > 0:
            return "middle"
        else:
            return "low"

    def _generate_recommendations(self, violations: List[Dict[str, Any]]) -> List[str]:
        """
        生成整改建议

        从违规项中提取整改建议，并添加通用建议。

        Args:
            violations: 违规项列表

        Returns:
            List[str]: 整改建议列表
        """
        recommendations = []

        # 提取每个违规项的整改建议
        for violation in violations:
            rec = violation.get("recommendation")
            if rec and rec not in recommendations:
                recommendations.append(rec)

        # 添加通用合规建议
        if violations:
            recommendations.append("建议建立定期合规检查机制，防范合规风险")
            recommendations.append("建议加强员工合规培训，提高合规意识")

        return recommendations

    def _generate_summary(
        self, business_type: str, violations: List[Dict[str, Any]], risk_level: str
    ) -> str:
        """
        生成合规检查摘要

        根据业务类型、违规数量和风险等级生成简洁的摘要文本。

        Args:
            business_type: 业务类型
            violations: 违规项列表
            risk_level: 整体风险等级

        Returns:
            str: 合规检查摘要
        """
        risk_map = {"high": "高", "middle": "中", "low": "低"}

        if not violations:
            return f"{business_type}业务合规检查通过，未发现违规项"

        return (
            f"{business_type}业务合规检查完成，共发现{len(violations)}项违规，"
            f"整体风险等级：{risk_map.get(risk_level, '未知')}"
        )

    def _calculate_confidence(self, violations: List[Dict[str, Any]]) -> float:
        """
        计算置信度分数

        根据违规项的数量和风险等级计算置信度。

        Args:
            violations: 违规项列表

        Returns:
            float: 置信度分数（0-1）
        """
        if not violations:
            return 0.90

        # 高风险违规降低置信度
        high_count = sum(1 for v in violations if v.get("risk_level") == "high")
        confidence = 0.85 - (high_count * 0.05)

        return max(0.60, confidence)