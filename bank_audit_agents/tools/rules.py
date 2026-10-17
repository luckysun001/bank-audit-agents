"""
审计规则引擎

设计取舍：
- 规则采用**声明式**描述（指标 + 比较运算符 + 阈值），而不是硬编码 if-else，
  这样规则库可以整体导出为 YAML/JSON，也便于按机构差异覆盖阈值
- 内置规则覆盖信贷、资本、流动性、反洗钱合规、内控运营等常用监管指标
- **阈值是参考值**：监管口径会随文件版本调整（例如《反洗钱法》2025 年修订后
  资料保存年限由 5 年提高到 10 年），落地时请以最新监管文件和机构内部政策为准，
  通过 ``RuleEngine.override_threshold()`` 覆盖

上下文约定：
    evaluate 接收一个扁平 dict，键为规则中的 ``metric``，值为数值（百分比统一用
    数字表示，如 12.5 表示 12.5%）；缺失的指标会被记入 ``missing_metrics`` 而非误报。
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from bank_audit_agents.tools.base import ToolSpec, get_default_registry, tool
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "RuleCategory",
    "RuleSeverity",
    "AuditRule",
    "RuleFinding",
    "RuleEngine",
    "DEFAULT_RULES",
    "build_default_engine",
]

# 支持的比较语义：表示"该指标应当满足的约束"
_OPERATORS = ("lte", "lt", "gte", "gt", "eq", "ne")


class RuleCategory(str, Enum):
    """规则分类"""

    CREDIT = "credit"            # 信贷风险
    CAPITAL = "capital"          # 资本充足
    LIQUIDITY = "liquidity"      # 流动性
    COMPLIANCE = "compliance"    # 合规 / 反洗钱
    OPERATION = "operation"      # 内控与运营
    FINANCIAL = "financial"      # 财务表现


class RuleSeverity(str, Enum):
    """违规严重程度"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _is_violated(actual: float, operator: str, threshold: float) -> bool:
    """判断指标是否违反约束"""
    if operator == "lte":
        return actual > threshold
    if operator == "lt":
        return actual >= threshold
    if operator == "gte":
        return actual < threshold
    if operator == "gt":
        return actual <= threshold
    if operator == "eq":
        return actual != threshold
    if operator == "ne":
        return actual == threshold
    raise ValueError(f"不支持的运算符: {operator}，可选: {_OPERATORS}")


@dataclass
class AuditRule:
    """一条审计规则

    Args:
        rule_id: 唯一编号，如 ``CREDIT-001``
        name: 规则名称
        category: 分类
        severity: 违反时的严重程度
        metric: 从上下文取值用的指标键
        operator: 约束语义，``lte`` 表示"应当 ≤ 阈值"
        threshold: 阈值
        unit: 单位说明（``%`` / ``ratio`` / ``days`` / ``times`` / ``count``）
        description: 规则说明
        regulation_ref: 监管依据（文件 / 条款的通俗表述）
        recommendation: 违反后的整改建议
    """

    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    metric: str
    operator: str
    threshold: float
    unit: str = "%"
    description: str = ""
    regulation_ref: str = ""
    recommendation: str = ""

    def __post_init__(self):
        if self.operator not in _OPERATORS:
            raise ValueError(f"规则 {self.rule_id} 的运算符非法: {self.operator}")

    def evaluate(self, context: Dict[str, Any]) -> Optional["RuleFinding"]:
        """对给定上下文求值；指标缺失返回 None，违反则返回 finding"""
        if self.metric not in context:
            return None
        raw = context[self.metric]
        if raw is None:
            return None
        try:
            actual = float(raw)
        except (TypeError, ValueError):
            return None

        if not _is_violated(actual, self.operator, self.threshold):
            return None

        return RuleFinding(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category.value,
            severity=self.severity.value,
            metric=self.metric,
            actual=actual,
            threshold=self.threshold,
            unit=self.unit,
            message=(
                f"{self.name}：实际 {actual}{self.unit}，"
                f"约束为 {self.operator} {self.threshold}{self.unit}"
            ),
            recommendation=self.recommendation,
            regulation_ref=self.regulation_ref,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["severity"] = self.severity.value
        return payload


@dataclass
class RuleFinding:
    """规则命中结果（即一条审计发现）"""

    rule_id: str
    rule_name: str
    category: str
    severity: str
    metric: str
    actual: float
    threshold: float
    unit: str = "%"
    message: str = ""
    recommendation: str = ""
    regulation_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_agent_finding(self) -> Dict[str, Any]:
        """转换成 AgentResult.findings 期望的结构"""
        return {
            "rule_id": self.rule_id,
            "title": self.rule_name,
            "category": self.category,
            "severity": self.severity,
            "description": self.message,
            "evidence": {
                "metric": self.metric,
                "actual": self.actual,
                "threshold": self.threshold,
                "unit": self.unit,
            },
            "recommendation": self.recommendation,
            "regulation_ref": self.regulation_ref,
        }


class RuleEngine:
    """规则引擎"""

    def __init__(self, rules: Optional[Iterable[AuditRule]] = None):
        self.rules: List[AuditRule] = list(rules) if rules else []

    # ---------- 规则管理 ----------

    def add_rule(self, rule: AuditRule) -> AuditRule:
        self.rules.append(rule)
        return rule

    def add_rules(self, rules: Iterable[AuditRule]) -> None:
        self.rules.extend(rules)

    def get_rule(self, rule_id: str) -> Optional[AuditRule]:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def override_threshold(self, rule_id: str, threshold: float) -> bool:
        """覆盖某条规则的阈值（适配机构内部更严的政策），返回是否命中"""
        rule = self.get_rule(rule_id)
        if rule is None:
            logger.warning(f"未找到规则，无法覆盖阈值: {rule_id}")
            return False
        rule.threshold = threshold
        return True

    @classmethod
    def from_dicts(cls, payloads: Iterable[Dict[str, Any]]) -> "RuleEngine":
        """从字典列表构造（对应 YAML/JSON 形式的规则库）"""
        rules = []
        for item in payloads:
            rules.append(
                AuditRule(
                    rule_id=item["rule_id"],
                    name=item["name"],
                    category=RuleCategory(item.get("category", "credit")),
                    severity=RuleSeverity(item.get("severity", "medium")),
                    metric=item["metric"],
                    operator=item.get("operator", "lte"),
                    threshold=float(item["threshold"]),
                    unit=item.get("unit", "%"),
                    description=item.get("description", ""),
                    regulation_ref=item.get("regulation_ref", ""),
                    recommendation=item.get("recommendation", ""),
                )
            )
        return cls(rules)

    # ---------- 执行 ----------

    def evaluate(
        self,
        context: Dict[str, Any],
        categories: Optional[Iterable[RuleCategory]] = None,
        min_severity: Optional[RuleSeverity] = None,
    ) -> List[RuleFinding]:
        """对上下文执行全部规则，返回命中（违反）的发现"""
        wanted = {c.value for c in categories} if categories else None
        findings: List[RuleFinding] = []

        for rule in self.rules:
            if wanted and rule.category.value not in wanted:
                continue
            if min_severity is not None and not self._severity_at_least(rule, min_severity):
                continue
            finding = rule.evaluate(context)
            if finding is not None:
                findings.append(finding)

        severity_rank = {s.value: i for i, s in enumerate(RuleSeverity)}
        findings.sort(key=lambda f: severity_rank.get(f.severity, 0), reverse=True)
        return findings

    @staticmethod
    def _severity_at_least(rule: AuditRule, minimum: RuleSeverity) -> bool:
        order = [s.value for s in RuleSeverity]
        return order.index(rule.severity.value) >= order.index(minimum.value)

    def missing_metrics(self, context: Dict[str, Any]) -> List[str]:
        """返回上下文中缺失的指标键（用于提示数据不全，而非静默跳过）"""
        return [r.metric for r in self.rules if r.metric not in context or context[r.metric] is None]

    def evaluate_report(
        self,
        context: Dict[str, Any],
        categories: Optional[Iterable[RuleCategory]] = None,
    ) -> Dict[str, Any]:
        """执行并汇总成报告字典，可直接作为工具输出"""
        findings = self.evaluate(context, categories=categories)
        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for f in findings:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
            by_category[f.category] = by_category.get(f.category, 0) + 1

        return {
            "evaluated_rules": len(self.rules),
            "violations": len(findings),
            "by_severity": by_severity,
            "by_category": by_category,
            "missing_metrics": self.missing_metrics(context),
            "findings": [f.to_dict() for f in findings],
        }

    def to_dict(self) -> List[Dict[str, Any]]:
        """导出规则库（便于落 YAML 或交给 LLM 做规则检索）"""
        return [r.to_dict() for r in self.rules]

    def __len__(self) -> int:
        return len(self.rules)


# ---------------------------------------------------------------------------
# 内置规则库
#
# 说明：以下阈值为公开监管指标中的常见参考值，用于演示与快速落地。
# 监管口径会随文件版本调整，实施前请核对最新监管要求与机构内部政策。
# ---------------------------------------------------------------------------

DEFAULT_RULES: List[AuditRule] = [
    # ---------- 信贷风险 ----------
    AuditRule(
        rule_id="CREDIT-001",
        name="单一客户贷款集中度",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.CRITICAL,
        metric="single_customer_concentration",
        operator="lte",
        threshold=10.0,
        unit="%",
        description="对同一借款客户的贷款余额占资本净额的比例不应超过 10%",
        regulation_ref="《商业银行大额风险暴露管理办法》",
        recommendation="压降单一客户授信敞口，或增加银团贷款、担保等风险缓释措施",
    ),
    AuditRule(
        rule_id="CREDIT-002",
        name="单一集团客户授信集中度",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.CRITICAL,
        metric="group_customer_concentration",
        operator="lte",
        threshold=15.0,
        unit="%",
        description="对同一集团客户的授信余额占资本净额的比例不应超过 15%",
        regulation_ref="《商业银行大额风险暴露管理办法》",
        recommendation="统一集团授信管理，穿透识别关联方并合并计算敞口",
    ),
    AuditRule(
        rule_id="CREDIT-003",
        name="不良贷款率",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        metric="npl_ratio",
        operator="lte",
        threshold=5.0,
        unit="%",
        description="不良贷款占各项贷款余额的比例，通常不应超过 5%",
        regulation_ref="商业银行风险监管核心指标（参考）",
        recommendation="加大不良处置力度，强化贷后管理与早期预警",
    ),
    AuditRule(
        rule_id="CREDIT-004",
        name="拨备覆盖率",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        metric="provision_coverage",
        operator="gte",
        threshold=150.0,
        unit="%",
        description="贷款损失准备占不良贷款余额的比例，监管区间通常在 120%~150%，按机构要求取值",
        regulation_ref="《商业银行贷款损失准备管理办法》",
        recommendation="补提贷款损失准备，或加快不良核销与转让",
    ),
    AuditRule(
        rule_id="CREDIT-005",
        name="贷款拨备率（拨贷比）",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        metric="provision_to_loan",
        operator="gte",
        threshold=2.5,
        unit="%",
        description="贷款损失准备占各项贷款余额的比例，通常不应低于 2.5%",
        regulation_ref="《商业银行贷款损失准备管理办法》",
        recommendation="按季度测算拨备缺口并制定达标计划",
    ),
    AuditRule(
        rule_id="CREDIT-006",
        name="逾期 90 天以上贷款与不良贷款比例",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        metric="overdue90_to_npl",
        operator="lte",
        threshold=100.0,
        unit="%",
        description="逾期 90 天以上贷款应全部计入不良，比例不应超过 100%（消除『剪刀差』）",
        regulation_ref="监管关于不良贷款分类准确性的要求（参考）",
        recommendation="核查五级分类准确性，将符合条件的逾期贷款及时下调至不良",
    ),
    AuditRule(
        rule_id="CREDIT-007",
        name="最大十家客户贷款比例",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        metric="top10_customer_ratio",
        operator="lte",
        threshold=50.0,
        unit="%",
        description="最大十家客户贷款余额占资本净额的比例，通常作为集中度监测指标",
        regulation_ref="商业银行风险监管核心指标（监测参考）",
        recommendation="优化客户结构，控制大额客户授信总量",
    ),

    # ---------- 资本充足 ----------
    AuditRule(
        rule_id="CAPITAL-001",
        name="资本充足率",
        category=RuleCategory.CAPITAL,
        severity=RuleSeverity.CRITICAL,
        metric="capital_adequacy_ratio",
        operator="gte",
        threshold=10.5,
        unit="%",
        description="资本充足率不低于 10.5%（核心一级 7.5% + 储备资本 2.5%，系统重要性机构另加）",
        regulation_ref="《商业银行资本管理办法》",
        recommendation="补充资本或压降风险加权资产，制定资本充足率达标规划",
    ),
    AuditRule(
        rule_id="CAPITAL-002",
        name="一级资本充足率",
        category=RuleCategory.CAPITAL,
        severity=RuleSeverity.CRITICAL,
        metric="tier1_ratio",
        operator="gte",
        threshold=8.5,
        unit="%",
        description="一级资本充足率不低于 8.5%",
        regulation_ref="《商业银行资本管理办法》",
        recommendation="补充核心一级资本或发行其他一级资本工具",
    ),
    AuditRule(
        rule_id="CAPITAL-003",
        name="核心一级资本充足率",
        category=RuleCategory.CAPITAL,
        severity=RuleSeverity.CRITICAL,
        metric="cet1_ratio",
        operator="gte",
        threshold=7.5,
        unit="%",
        description="核心一级资本充足率不低于 7.5%",
        regulation_ref="《商业银行资本管理办法》",
        recommendation="留存利润、控制分红比例或引入战略投资者",
    ),
    AuditRule(
        rule_id="CAPITAL-004",
        name="杠杆率",
        category=RuleCategory.CAPITAL,
        severity=RuleSeverity.HIGH,
        metric="leverage_ratio",
        operator="gte",
        threshold=4.0,
        unit="%",
        description="一级资本净额与调整后表内外资产余额之比不低于 4%",
        regulation_ref="《商业银行杠杆率管理办法》",
        recommendation="控制表外业务扩张，压降低风险权重资产规模",
    ),

    # ---------- 流动性 ----------
    AuditRule(
        rule_id="LIQUIDITY-001",
        name="流动性覆盖率（LCR）",
        category=RuleCategory.LIQUIDITY,
        severity=RuleSeverity.CRITICAL,
        metric="lcr",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="优质流动性资产储备与未来 30 天净现金流出之比不低于 100%",
        regulation_ref="《商业银行流动性风险管理办法》",
        recommendation="提高优质流动性资产储备，稳定负债来源",
    ),
    AuditRule(
        rule_id="LIQUIDITY-002",
        name="净稳定资金比例（NSFR）",
        category=RuleCategory.LIQUIDITY,
        severity=RuleSeverity.HIGH,
        metric="nsfr",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="可用稳定资金与所需稳定资金之比不低于 100%",
        regulation_ref="《商业银行流动性风险管理办法》",
        recommendation="延长负债期限结构，降低对短期批发性融资的依赖",
    ),
    AuditRule(
        rule_id="LIQUIDITY-003",
        name="流动性比例",
        category=RuleCategory.LIQUIDITY,
        severity=RuleSeverity.MEDIUM,
        metric="liquidity_ratio",
        operator="gte",
        threshold=25.0,
        unit="%",
        description="流动性资产与流动性负债之比不低于 25%",
        regulation_ref="《商业银行流动性风险管理办法》",
        recommendation="调整资产负债期限错配，增加流动性资产配置",
    ),
    AuditRule(
        rule_id="LIQUIDITY-004",
        name="存贷比（监测）",
        category=RuleCategory.LIQUIDITY,
        severity=RuleSeverity.LOW,
        metric="loan_to_deposit",
        operator="lte",
        threshold=75.0,
        unit="%",
        description="各项贷款余额与各项存款余额之比，作为流动性监测指标参考值",
        regulation_ref="商业银行流动性风险监测指标（参考）",
        recommendation="关注存款增长与贷款投放节奏的匹配度",
    ),

    # ---------- 合规 / 反洗钱 ----------
    AuditRule(
        rule_id="COMPLIANCE-001",
        name="客户身份识别（KYC）完整率",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.CRITICAL,
        metric="kyc_completeness",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="应识别并核验客户身份，完整率应为 100%",
        regulation_ref="《中华人民共和国反洗钱法》《金融机构客户尽职调查和客户身份资料及交易记录保存管理办法》",
        recommendation="补齐缺失的客户身份要素，建立开户环节必填校验",
    ),
    AuditRule(
        rule_id="COMPLIANCE-002",
        name="大额交易报告及时率",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.HIGH,
        metric="large_transaction_report_days",
        operator="lte",
        threshold=5.0,
        unit="days",
        description="大额交易应在发生后 5 个工作日内报送",
        regulation_ref="《金融机构大额交易和可疑交易报告管理办法》",
        recommendation="完善交易监测系统的自动报送与超时告警",
    ),
    AuditRule(
        rule_id="COMPLIANCE-003",
        name="可疑交易报告及时率",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.HIGH,
        metric="suspicious_report_days",
        operator="lte",
        threshold=5.0,
        unit="days",
        description="应在发现可疑交易后 5 个工作日内报送",
        regulation_ref="《金融机构大额交易和可疑交易报告管理办法》",
        recommendation="优化可疑交易甄别流程，明确人工复核时限",
    ),
    AuditRule(
        rule_id="COMPLIANCE-004",
        name="客户身份资料保存年限",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.MEDIUM,
        metric="customer_data_retention_years",
        operator="gte",
        threshold=5.0,
        unit="years",
        description="客户身份资料自业务关系结束起至少保存 5 年；《反洗钱法》2025 年修订后要求为 10 年，按适用版本取值",
        regulation_ref="《中华人民共和国反洗钱法》",
        recommendation="核对现行适用法律版本，调整资料保存策略",
    ),
    AuditRule(
        rule_id="COMPLIANCE-005",
        name="交易记录保存年限",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.MEDIUM,
        metric="transaction_data_retention_years",
        operator="gte",
        threshold=5.0,
        unit="years",
        description="交易记录自交易记账起至少保存 5 年；《反洗钱法》2025 年修订后要求为 10 年，按适用版本取值",
        regulation_ref="《中华人民共和国反洗钱法》",
        recommendation="统一交易记录归档策略，确保可追溯",
    ),
    AuditRule(
        rule_id="COMPLIANCE-006",
        name="制裁名单筛查覆盖率",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.CRITICAL,
        metric="sanction_screening_coverage",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="存量与新增客户、交易对手应全部纳入制裁名单筛查",
        regulation_ref="反洗钱与制裁合规内控要求",
        recommendation="接入权威名单源，实现开户与交易环节的准实时筛查",
    ),
    AuditRule(
        rule_id="COMPLIANCE-007",
        name="高风险客户强化尽调（EDD）覆盖率",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.HIGH,
        metric="edd_coverage",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="被评定为高风险的客户应 100% 执行强化尽职调查",
        regulation_ref="《金融机构客户尽职调查和客户身份资料及交易记录保存管理办法》",
        recommendation="建立高风险客户清单并跟踪 EDD 执行情况",
    ),
    AuditRule(
        rule_id="COMPLIANCE-008",
        name="年度反洗钱培训次数",
        category=RuleCategory.COMPLIANCE,
        severity=RuleSeverity.LOW,
        metric="aml_training_per_year",
        operator="gte",
        threshold=1.0,
        unit="times",
        description="每年至少开展 1 次反洗钱专项培训",
        regulation_ref="反洗钱内控要求（参考）",
        recommendation="制定年度培训计划并留存签到与考核记录",
    ),

    # ---------- 内控与运营 ----------
    AuditRule(
        rule_id="OPERATION-001",
        name="审计发现问题整改率",
        category=RuleCategory.OPERATION,
        severity=RuleSeverity.HIGH,
        metric="rectification_rate",
        operator="gte",
        threshold=95.0,
        unit="%",
        description="已整改问题占应整改问题的比例，通常要求不低于 95%",
        regulation_ref="内部审计整改管理要求（参考）",
        recommendation="建立整改台账与闭环跟踪机制，对逾期项升级督办",
    ),
    AuditRule(
        rule_id="OPERATION-002",
        name="重大案件风险数量",
        category=RuleCategory.OPERATION,
        severity=RuleSeverity.CRITICAL,
        metric="major_case_count",
        operator="lte",
        threshold=0.0,
        unit="count",
        description="重大案件风险事件应为 0 起（含业内案件与内部人员作案）",
        regulation_ref="银行业案件风险防控要求（参考）",
        recommendation="立即启动案件查处与问责，开展全行排查",
    ),
    AuditRule(
        rule_id="OPERATION-003",
        name="重要凭证与印章双人管理覆盖率",
        category=RuleCategory.OPERATION,
        severity=RuleSeverity.HIGH,
        metric="dual_control_coverage",
        operator="gte",
        threshold=100.0,
        unit="%",
        description="重要空白凭证、印章、密押应 100% 落实双人管理与分岗制约",
        regulation_ref="商业银行内部控制指引（参考）",
        recommendation="梳理印章与凭证台账，补齐双人管理记录",
    ),
    AuditRule(
        rule_id="OPERATION-004",
        name="系统权限年度复核次数",
        category=RuleCategory.OPERATION,
        severity=RuleSeverity.MEDIUM,
        metric="access_review_per_year",
        operator="gte",
        threshold=1.0,
        unit="times",
        description="重要信息系统访问权限每年至少复核 1 次",
        regulation_ref="信息科技风险管理要求（参考）",
        recommendation="建立权限定期复核流程，及时清理冗余与离岗账户",
    ),

    # ---------- 财务表现（监测类） ----------
    AuditRule(
        rule_id="FINANCIAL-001",
        name="成本收入比",
        category=RuleCategory.FINANCIAL,
        severity=RuleSeverity.LOW,
        metric="cost_income_ratio",
        operator="lte",
        threshold=45.0,
        unit="%",
        description="营业费用与营业收入之比，作为效率类监测指标参考值",
        regulation_ref="商业银行风险监管核心指标（监测参考）",
        recommendation="优化费用结构，提升人均与网点产出效率",
    ),
    AuditRule(
        rule_id="FINANCIAL-002",
        name="资产利润率（ROA）",
        category=RuleCategory.FINANCIAL,
        severity=RuleSeverity.LOW,
        metric="roa",
        operator="gte",
        threshold=0.6,
        unit="%",
        description="净利润与平均资产总额之比，作为盈利性监测指标参考值",
        regulation_ref="商业银行风险监管核心指标（监测参考）",
        recommendation="改善资产端定价与负债成本，提升中间业务收入占比",
    ),
]


def build_default_engine() -> RuleEngine:
    """构造装载内置规则的引擎"""
    return RuleEngine(list(DEFAULT_RULES))


# ---------- 注册为 Agent 可调用的工具 ----------


@tool(
    name="audit_rule_check",
    description="按内置审计规则库检查一组指标，返回违反项与整改建议",
    category="rules",
    parameters={
        "context": "dict，指标名 -> 数值（百分比用数字表示，如 12.5 表示 12.5%）",
        "categories": "可选，限定规则分类，如 ['credit', 'capital']",
    },
)
def audit_rule_check(
    context: Dict[str, Any],
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """规则检查工具：把指标上下文交给规则引擎，返回结构化报告"""
    engine = build_default_engine()
    wanted = None
    if categories:
        wanted = [RuleCategory(c) for c in categories]
    return engine.evaluate_report(context, categories=wanted)


@tool(
    name="rule_library_lookup",
    description="查询内置审计规则库（可按分类过滤），用于报告写作时引用监管依据",
    category="rules",
    parameters={"category": "可选，规则分类，如 credit / capital / compliance"},
)
def rule_library_lookup(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """规则库检索工具"""
    engine = build_default_engine()
    if category:
        cat = RuleCategory(category)
        return [r.to_dict() for r in engine.rules if r.category == cat]
    return engine.to_dict()
