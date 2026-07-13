"""
合规检查智能体
对照监管政策和行内制度，进行合规性核查
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


class ComplianceLevel(str):
    """合规等级"""
    FULLY_COMPLIANT = "fully_compliant"
    MOSTLY_COMPLIANT = "mostly_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"


class ComplianceCheckerAgent(BaseAgent):
    """
    合规检查智能体

    核心能力:
    1. 监管政策合规检查（银保监会、人民银行等）
    2. 行内制度合规检查
    3. 反洗钱合规检查
    4. 消费者权益保护检查
    5. 违规项分类和严重程度评级
    """

    # 监管政策分类（简化版）
    REGULATORY_FRAMEWORKS = {
        "credit": [
            {"name": "《固定资产贷款管理暂行办法》", "code": "银监会2009年第2号令"},
            {"name": "《流动资金贷款管理暂行办法》", "code": "银监会2010年第1号令"},
            {"name": "《个人贷款管理暂行办法》", "code": "银监会2010年第2号令"},
            {"name": "《商业银行授信工作尽职指引》", "code": "银监发〔2004〕51号"},
        ],
        "aml": [
            {"name": "《中华人民共和国反洗钱法》", "code": "主席令第56号"},
            {"name": "《金融机构反洗钱规定》", "code": "中国人民银行令〔2006〕第1号"},
            {"name": "《金融机构大额交易和可疑交易报告管理办法》", "code": "中国人民银行令〔2016〕第3号"},
        ],
        "internal_control": [
            {"name": "《商业银行内部控制指引》", "code": "银监发〔2014〕40号"},
            {"name": "《商业银行合规风险管理指引》", "code": "银监发〔2006〕76号"},
        ],
        "consumer_protection": [
            {"name": "《银行业消费者权益保护工作指引》", "code": "银监发〔2013〕38号"},
            {"name": "《商业银行服务价格管理办法》", "code": "银监会发改委令2014年第1号"},
        ],
    }

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.COMPLIANCE_CHECKER, agent_id, **kwargs)
        self.compliance_rules_db: Dict[str, Any] = {}
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
        return """你是一位资深银行合规审计专家，熟悉所有银行监管政策和内部管理制度。

你的核心职责:
1. 对照监管政策进行合规性核查
   - 银保监会监管规定
   - 人民银行监管要求
   - 银行内部管理制度
   - 行业自律规定

2. 核查范围:
   - 信贷业务合规（三查、授信、担保、审批等）
   - 反洗钱合规（客户身份识别、大额可疑交易报告、制裁筛查等）
   - 消费者权益保护（收费透明、信息披露、营销规范等）
   - 数据合规（客户信息保护、数据安全等）

3. 输出要求:
   - 明确列出适用的法规条款
   - 对每项合规检查给出：合规状态、违规描述、违反条款、整改建议
   - 评估违规严重程度：严重/较重/一般/轻微
   - 给出整改优先级和建议时限
"""

    def get_tools(self) -> List[Any]:
        return [
            "regulation_retriever",
            "compliance_checker",
            "violation_classifier",
            "aml_rule_engine",
            "sanction_screening",
            "fee_compliance_checker",
        ]

    async def execute(self, task: Task) -> AgentResult:
        logger.info(f"合规检查智能体开始处理任务: {task.task_id}")

        audit_content = task.input_data.get("audit_content", "")
        business_type = task.input_data.get("business_type", "credit")
        check_frameworks = task.input_data.get("check_frameworks", ["credit", "aml"])

        if not audit_content:
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少审计内容",
                error="audit_content is required",
                confidence_score=0.0,
            )

        # 执行合规检查（LLM 驱动，mock 模式下回退到示例数据）
        compliance_results = await self._check_compliance(
            audit_content, business_type, check_frameworks
        )

        # 生成合规报告
        compliance_report = self._generate_compliance_report(compliance_results)

        # 计算合规得分
        compliance_score = self._calculate_compliance_score(compliance_results)

        # 整改建议
        rectification_suggestions = self._generate_rectification_suggestions(compliance_results)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=compliance_report["summary"],
            findings=compliance_results,
            recommendations=rectification_suggestions,
            confidence_score=compliance_score,
            metadata={
                "business_type": business_type,
                "check_frameworks": check_frameworks,
                "total_checks": compliance_report["total_checks"],
                "violation_count": compliance_report["violation_count"],
                "compliance_level": compliance_report["compliance_level"],
            },
        )

    async def _check_compliance(
        self, content: str, business_type: str, frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """
        执行合规检查
        - LLM 模式：将审计内容发送给 LLM 进行合规分析
        - Mock 模式：返回示例违规数据
        """
        framework_names = []
        for fw_key in frameworks:
            for name, items in self.REGULATORY_FRAMEWORKS.items():
                if name == fw_key:
                    framework_names.extend([item["name"] for item in items])

        user_prompt = json.dumps({
            "audit_content": content[:4000],
            "business_type": business_type,
            "applicable_frameworks": framework_names,
        }, ensure_ascii=False)

        def _mock_fallback():
            return self._get_mock_violations(frameworks)

        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含一个 'violations' 数组，每个元素包含字段：violation_id, category, framework, article, description, severity(严重/较重/一般/轻微), evidence, impact。",
            user_prompt=user_prompt,
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        if isinstance(result, dict) and "violations" in result:
            return result["violations"]
        elif isinstance(result, list):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_violations(frameworks)

    def _get_mock_violations(self, frameworks: List[str]) -> List[Dict[str, Any]]:
        """返回示例违规数据（mock fallback）"""
        mock_violations = [
            {
                "violation_id": "VIOL_001",
                "category": "信贷合规",
                "framework": "《流动资金贷款管理暂行办法》",
                "article": "第十六条",
                "description": "贷款资金支付审核不严格，未提供完整的用途证明材料",
                "severity": "较重",
                "evidence": "第12页支付凭证，缺少对应交易合同",
                "impact": "可能导致贷款资金挪用风险",
            },
            {
                "violation_id": "VIOL_002",
                "category": "反洗钱",
                "framework": "《金融机构客户身份识别和客户身份资料及交易记录保存管理办法》",
                "article": "第七条",
                "description": "客户KYC信息不完整，缺少实际控制人信息",
                "severity": "严重",
                "evidence": "客户档案第3页，受益人身份证明文件缺失",
                "impact": "违反反洗钱监管要求，可能面临监管处罚",
            },
            {
                "violation_id": "VIOL_003",
                "category": "信贷合规",
                "framework": "《商业银行授信工作尽职指引》",
                "article": "第三十五条",
                "description": "贷后检查频率不足，超过规定时限15天",
                "severity": "一般",
                "evidence": "贷后检查表日期与贷款发放日期间隔超过90天",
                "impact": "风险预警不及时，可能错过风险化解时机",
            },
            {
                "violation_id": "VIOL_004",
                "category": "消费者权益保护",
                "framework": "《银行业消费者权益保护工作指引》",
                "article": "第二十条",
                "description": "贷款合同关键条款未进行显著提示",
                "severity": "轻微",
                "evidence": "合同第6页关于违约条款未使用加粗提示",
                "impact": "可能引发消费者投诉和法律纠纷",
            },
        ]

        framework_mapping = {
            "credit": "信贷合规",
            "aml": "反洗钱",
            "consumer": "消费者权益保护",
            "control": "内部控制",
        }

        violations = []
        for violation in mock_violations:
            category_eng = next(
                (k for k, v in framework_mapping.items() if v == violation["category"]),
                None
            )
            if category_eng in frameworks:
                violations.append(violation)

        return violations

    def _generate_compliance_report(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成合规检查报告"""
        severity_counts = {
            "严重": 0,
            "较重": 0,
            "一般": 0,
            "轻微": 0,
        }

        for v in violations:
            severity = v.get("severity", "一般")
            if severity in severity_counts:
                severity_counts[severity] += 1

        # 计算合规等级
        if not violations:
            compliance_level = ComplianceLevel.FULLY_COMPLIANT
            summary = "✅ 完全合规，未发现违规事项"
        elif severity_counts["严重"] > 0 or severity_counts["较重"] >= 2:
            compliance_level = ComplianceLevel.NON_COMPLIANT
            summary = f"❌ 存在严重合规风险：严重{severity_counts['严重']}项，较重{severity_counts['较重']}项"
        elif severity_counts["较重"] > 0 or severity_counts["一般"] >= 3:
            compliance_level = ComplianceLevel.PARTIALLY_COMPLIANT
            summary = f"⚠️ 部分合规：一般{severity_counts['一般']}项，轻微{severity_counts['轻微']}项，需整改"
        else:
            compliance_level = ComplianceLevel.MOSTLY_COMPLIANT
            summary = f"✅ 基本合规：轻微{severity_counts['轻微']}项改进建议"

        return {
            "summary": summary,
            "compliance_level": compliance_level,
            "violation_count": len(violations),
            "severity_counts": severity_counts,
            "total_checks": 15,  # 模拟检查项总数
        }

    def _calculate_compliance_score(self, violations: List[Dict[str, Any]]) -> float:
        """计算合规得分（0-100分）"""
        if not violations:
            return 100.0

        # 严重程度权重
        severity_weights = {
            "严重": 20,
            "较重": 10,
            "一般": 5,
            "轻微": 2,
        }

        total_deduction = sum(
            severity_weights.get(v.get("severity", "一般"), 5) for v in violations
        )

        return max(100 - total_deduction, 0) / 100

    def _generate_rectification_suggestions(self, violations: List[Dict[str, Any]]) -> List[str]:
        """生成整改建议"""
        suggestions = []

        # 按严重程度分组
        severe_violations = [v for v in violations if v["severity"] in ["严重", "较重"]]
        other_violations = [v for v in violations if v["severity"] in ["一般", "轻微"]]

        if severe_violations:
            suggestions.append(
                f"🚨 立即整改{len(severe_violations)}项严重/较严重违规，成立专项整改小组"
            )
            for v in severe_violations[:2]:
                suggestions.append(f"   - {v['description']}")

        if other_violations:
            suggestions.append(
                f"📋 限期整改{len(other_violations)}项一般/轻微违规，1个月内完成"
            )

        # 通用建议
        suggestions.append("📚 组织相关业务人员进行监管政策再培训")
        suggestions.append("🔍 优化合规检查流程，加强事前和事中控制")
        suggestions.append("📝 建立合规问题台账，定期开展整改回头看")

        return suggestions
