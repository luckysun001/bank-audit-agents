"""
质量审核智能体和任务协调智能体 - 优化版

优化内容:
1. 分离质量审核智能体，专注质量控制
2. 完善质量检查标准
3. 优化任务协调智能体
4. 增强类型安全
5. LLM 驱动质量检查（mock 模式回退到规则评分）
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from bank_audit_agents.core.base_agent import (
    AgentResult,
    AgentType,
    BaseAgent,
    Task,
)
from bank_audit_agents.utils.logger import get_logger
from bank_audit_agents.utils.llm_client import get_llm_client

logger = get_logger(__name__)


class QualityIssueLevel(str):
    """质量问题等级"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


@dataclass
class QualityIssue:
    """质量问题"""
    issue_id: str
    level: str
    category: str
    description: str
    suggestion: str = ""
    location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "level": self.level,
            "category": self.category,
            "description": self.description,
            "suggestion": self.suggestion,
            "location": self.location,
        }


class QualityStandard:
    """质量检查标准"""

    STANDARDS = {
        "completeness": {
            "name": "完整性检查",
            "weight": 0.25,
            "description": "检查信息是否完整，必填项是否填写",
        },
        "accuracy": {
            "name": "准确性检查",
            "weight": 0.25,
            "description": "检查数据、引用、金额是否准确",
        },
        "consistency": {
            "name": "一致性检查",
            "weight": 0.20,
            "description": "检查前后表述是否一致",
        },
        "clarity": {
            "name": "清晰度检查",
            "weight": 0.15,
            "description": "检查表述是否清晰易懂",
        },
        "compliance": {
            "name": "合规性检查",
            "weight": 0.15,
            "description": "检查是否符合审计规范",
        },
    }

    @classmethod
    def get_total_weight(cls) -> float:
        return sum(s["weight"] for s in cls.STANDARDS.values())


class QualityAuditorAgent(BaseAgent):
    """
    质量审核智能体

    核心能力:
    1. 审核其他智能体的输出质量
    2. 检查信息完整性和准确性
    3. 验证风险评估合理性
    4. 确保报告格式规范统一
    5. 交叉验证关键数据
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.QUALITY_AUDITOR, agent_id, **kwargs)
        self.audit_history: List[Dict[str, Any]] = []
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
        return """你是一位银行审计质量控制专家，具有10年以上审计质量检查经验。

你的核心职责:
1. 完整性检查：确保所有必填项都已填写，信息完整无遗漏
2. 准确性检查：验证所有数据、引用、金额的准确性，交叉核对来源
3. 一致性检查：确保风险评估前后一致，问题描述与证据匹配
4. 规范性检查：确保报告格式规范，术语使用正确，符合审计标准
5. 合理性检查：验证风险评级是否合理，整改建议是否可落地

质量评级标准:
- A级(优秀): 90分以上，完全符合质量要求，无需修改
- B级(良好): 80-89分，基本符合要求，少量改进建议
- C级(合格): 70-79分，存在一定问题，需要修改后通过
- D级(不合格): 70分以下，存在严重问题，需重新审核

你的审核必须严谨、公正，确保最终输出的审计质量。
"""

    def get_tools(self) -> List[Any]:
        return [
            "quality_checker",
            "consistency_verifier",
            "completeness_checker",
            "data_validator",
            "cross_reference_checker",
        ]

    async def execute(self, task: Task) -> AgentResult:
        """执行质量审核任务"""
        logger.info(f"🔍 质量审核智能体开始审核任务: {task.task_id}")

        content_to_audit = task.input_data.get("content", {})
        source_agent = task.input_data.get("source_agent", "unknown")
        audit_type = task.input_data.get("audit_type", "general")

        # 执行各项质量检查（LLM 驱动，mock 模式下回退到规则评分）
        quality_scores, issues = await self._perform_quality_checks(content_to_audit, audit_type)

        # 计算总体质量得分
        overall_score = self._calculate_overall_score(quality_scores)

        # 确定质量等级
        quality_grade = self._determine_grade(overall_score)

        # 生成审核结论
        audit_conclusion = self._generate_conclusion(overall_score, quality_grade, issues)

        # 记录审核历史
        audit_record = {
            "audit_id": task.task_id,
            "source_agent": source_agent,
            "audit_type": audit_type,
            "quality_grade": quality_grade,
            "overall_score": overall_score,
            "audit_time": task.started_at.isoformat() if task.started_at else None,
        }
        self.audit_history.append(audit_record)

        # 生成建议
        recommendations = []
        for issue in issues:
            suggestion = issue.suggestion if hasattr(issue, "suggestion") else issue.get("suggestion", "")
            if suggestion:
                recommendations.append(suggestion)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=audit_conclusion,
            findings=[issue.to_dict() if hasattr(issue, "to_dict") else issue for issue in issues],
            recommendations=recommendations,
            confidence_score=0.98,
            output_data={
                "quality_grade": quality_grade,
                "overall_score": overall_score,
                "detailed_scores": quality_scores,
                "issue_count": len(issues),
                "pass_threshold": overall_score >= 70,
            },
        )

    async def _perform_quality_checks(
        self, content: Any, audit_type: str
    ) -> Tuple[Dict[str, float], List[QualityIssue]]:
        """
        执行各项质量检查
        - LLM 模式：发送内容给 LLM 进行质量评估
        - Mock 模式：使用基于内容长度的规则评分
        """
        content_str = str(content)[:3000]

        standard_names = {k: v["name"] for k, v in QualityStandard.STANDARDS.items()}

        def _rule_based_fallback():
            scores = {}
            issues = []
            content_length = len(content_str)

            for standard_key, config in QualityStandard.STANDARDS.items():
                base_score = min(95, 70 + content_length / 100)
                import random
                random.seed(hash(str(content)) + hash(standard_key))
                score = base_score + random.uniform(-5, 5)
                score = max(60, min(100, score))

                has_issue = score < 85
                scores[standard_key] = round(score, 1)

                if has_issue:
                    issue = QualityIssue(
                        issue_id=f"QI-{standard_key}-{len(issues)}",
                        level=self._score_to_level(score),
                        category=config["name"],
                        description=f"{config['name']}得分较低: {score:.1f}分",
                        suggestion=self._get_suggestion(standard_key, score),
                    )
                    issues.append(issue)

            return {"scores": scores, "issues": [i.to_dict() for i in issues]}

        user_prompt = json.dumps({
            "content": content_str,
            "audit_type": audit_type,
            "standards": standard_names,
        }, ensure_ascii=False)

        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含 'scores' 对象（key为标准key，value为分数0-100）和 'issues' 数组（每个元素含 issue_id, level, category, description, suggestion）。",
            user_prompt=user_prompt,
            fallback_fn=_rule_based_fallback,
            response_format_json=True,
        )

        if isinstance(result, dict) and "scores" in result:
            scores = result["scores"]
            raw_issues = result.get("issues", [])
            issues = []
            for raw in raw_issues:
                issues.append(QualityIssue(
                    issue_id=raw.get("issue_id", f"QI-{len(issues)}"),
                    level=raw.get("level", QualityIssueLevel.MINOR),
                    category=raw.get("category", "其他"),
                    description=raw.get("description", ""),
                    suggestion=raw.get("suggestion", ""),
                ))
            return scores, issues
        else:
            return _rule_based_fallback()["scores"], []

    def _score_to_level(self, score: float) -> str:
        """将分数转换为问题等级"""
        if score < 60:
            return QualityIssueLevel.CRITICAL
        elif score < 75:
            return QualityIssueLevel.MAJOR
        elif score < 85:
            return QualityIssueLevel.MINOR
        else:
            return QualityIssueLevel.SUGGESTION

    def _get_suggestion(self, standard_key: str, score: float) -> str:
        """获取改进建议"""
        suggestions = {
            "completeness": "建议补充相关信息，确保所有必要字段都已填写",
            "accuracy": "建议核对相关数据的准确性，确保数值和引用无误",
            "consistency": "建议检查表述的一致性，确保前后逻辑统一",
            "clarity": "建议优化表述方式，使用更清晰准确的语言",
            "compliance": "建议检查是否符合审计规范和监管要求",
        }
        return suggestions.get(standard_key, "建议进一步审核")

    def _calculate_overall_score(self, quality_scores: Dict[str, float]) -> float:
        """计算总体质量得分"""
        total_score = 0.0
        total_weight = 0.0
        for standard_key, score in quality_scores.items():
            weight = QualityStandard.STANDARDS[standard_key]["weight"]
            total_score += score * weight
            total_weight += weight

        # 归一化到 0-100
        if total_weight > 0:
            total_score = total_score / total_weight
        return round(total_score, 1)

    def _determine_grade(self, score: float) -> str:
        """确定质量等级"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        else:
            return "D"

    def _generate_conclusion(self, score: float, grade: str, issues: List[Any]) -> str:
        """生成审核结论"""
        issue_count = len(issues)

        grade_descriptions = {
            "A": "质量优秀，完全符合审计标准，可以直接使用",
            "B": "质量良好，基本符合要求，建议根据意见稍作修改后使用",
            "C": "质量合格，但需要根据审核意见进行必要修改",
            "D": "质量不合格，存在较严重问题，需要重新审核",
        }

        conclusion = (
            f"质量审核完成，综合得分 {score:.1f} 分，等级 {grade}。"
            f"{grade_descriptions.get(grade, '')}"
        )

        if issue_count > 0:
            conclusion += f" 发现 {issue_count} 项待改进问题。"

        return conclusion

    def get_audit_statistics(self) -> Dict[str, Any]:
        """获取审核统计信息"""
        if not self.audit_history:
            return {"total_audits": 0}

        grade_counts: Dict[str, int] = defaultdict(int)
        total_score = 0.0

        for record in self.audit_history:
            grade = record["quality_grade"]
            grade_counts[grade] += 1
            total_score += record["overall_score"]

        avg_score = total_score / len(self.audit_history)

        return {
            "total_audits": len(self.audit_history),
            "grade_distribution": dict(grade_counts),
            "average_score": round(avg_score, 1),
            "pass_rate": round(
                sum(1 for r in self.audit_history if r["quality_grade"] in ["A", "B", "C"])
                / len(self.audit_history) * 100,
                1,
            ),
        }


class TaskCoordinatorAgent(BaseAgent):
    """
    任务协调智能体

    核心能力:
    1. 任务分解和分配
    2. 工作流编排和调度
    3. 智能体间协作协调
    4. 任务依赖管理
    5. 进度监控和异常处理
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.TASK_COORDINATOR, agent_id, **kwargs)
        self.task_queue: List[Task] = []

    def get_system_prompt(self) -> str:
        return """你是银行审计项目总协调人，负责整个审计工作流的规划和调度。

你的核心职责:
1. 任务分解：将复杂的审计项目分解为可执行的子任务
2. 智能体分配：根据各智能体的专长和当前负载分配任务
3. 依赖管理：管理任务间的依赖关系，确保正确的执行顺序
4. 进度监控：实时监控任务执行进度，发现异常及时处理
5. 结果汇总：汇总各智能体的输出，形成完整的审计结果
6. 资源调度：优化智能体资源分配，提高整体效率

协调原则:
- 高效：最大化并行执行，缩短总体时间
- 有序：严格按照依赖关系调度
- 容错：单个任务失败不影响整体流程，有重试机制
- 透明：所有任务状态清晰可查
- 公平：确保高优先级任务优先执行
"""

    def get_tools(self) -> List[Any]:
        return [
            "task_planner",
            "workflow_orchestrator",
            "progress_tracker",
            "dependency_manager",
            "resource_scheduler",
        ]

    async def execute(self, task: Task) -> AgentResult:
        """执行项目协调任务"""
        logger.info(f"🎯 任务协调智能体开始处理项目: {task.task_id}")

        project_requirements = task.input_data.get("project_requirements", {})
        workflow_type = project_requirements.get("workflow_type", "credit_audit")
        priority = project_requirements.get("priority", "normal")

        # 1. 任务分解
        subtasks = self._decompose_project(workflow_type, project_requirements)

        # 2. 建立任务依赖
        dependency_graph = self._setup_dependencies(subtasks, workflow_type)

        # 3. 分配任务到智能体
        assignments = self._assign_tasks_to_agents(subtasks)

        # 4. 生成执行计划
        execution_plan = self._generate_execution_plan(subtasks, assignments)

        # 5. 估算执行时间
        estimated_duration = self._estimate_duration(subtasks)

        result_summary = (
            f"审计项目已拆解为 {len(subtasks)} 个子任务，"
            f"分配给 {len(set(assignments.values()))} 种类型的智能体执行。"
            f"预计执行时间约 {estimated_duration} 分钟。"
        )

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=result_summary,
            findings=execution_plan,
            recommendations=[
                "建议实时监控任务执行状态",
                "对高风险任务设置超时预警",
                "准备好备选执行方案应对异常",
            ],
            confidence_score=0.95,
            output_data={
                "workflow_type": workflow_type,
                "priority": priority,
                "total_tasks": len(subtasks),
                "assignments": assignments,
                "dependency_graph": dependency_graph,
                "estimated_duration_minutes": estimated_duration,
                "execution_plan": execution_plan,
            },
        )

    def _decompose_project(
        self, workflow_type: str, requirements: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """将审计项目分解为子任务"""
        task_definitions = self._get_workflow_tasks(workflow_type)

        subtasks = []
        for i, (task_type, name, desc) in enumerate(task_definitions):
            subtask = {
                "task_id": f"TASK-{i:03d}",
                "task_type": task_type,
                "name": name,
                "description": desc,
                "priority": self._get_task_priority(task_type),
            }
            subtasks.append(subtask)

        return subtasks

    def _get_workflow_tasks(self, workflow_type: str) -> List[Tuple[str, str, str]]:
        """获取工作流的任务定义"""
        workflows = {
            "credit_audit": [
                ("document_parsing", "文档解析", "解析贷款合同、财务报表等信贷资料"),
                ("risk_identification", "风险识别", "识别信贷业务中的各类风险点"),
                ("compliance_check", "合规检查", "对照监管政策进行合规性核查"),
                ("report_generation", "报告生成", "整合结果，生成审计报告"),
                ("quality_audit", "质量审核", "对审计报告进行质量审核"),
            ],
            "compliance_audit": [
                ("document_parsing", "监管政策解析", "解析最新的监管政策文件"),
                ("business_parsing", "业务资料解析", "解析被审计业务的相关资料"),
                ("aml_check", "反洗钱检查", "检查反洗钱合规情况"),
                ("general_compliance", "一般合规检查", "全面合规性检查"),
                ("report_generation", "合规报告生成", "生成合规专项审计报告"),
            ],
            "financial_audit": [
                ("data_parsing", "财务数据解析", "解析财务报表和账户流水"),
                ("anomaly_detection", "异常检测", "识别财务异常交易和指标"),
                ("compliance_check", "财务合规检查", "检查财务制度执行情况"),
                ("report_generation", "财务审计报告", "生成财务审计报告"),
            ],
        }

        return workflows.get(workflow_type, workflows["credit_audit"])

    def _get_task_priority(self, task_type: str) -> int:
        """获取任务的优先级"""
        priorities = {
            "document_parsing": 10,
            "data_parsing": 10,
            "business_parsing": 10,
            "risk_identification": 8,
            "anomaly_detection": 8,
            "compliance_check": 7,
            "aml_check": 9,
            "general_compliance": 7,
            "report_generation": 5,
            "quality_audit": 6,
        }
        return priorities.get(task_type, 5)

    def _setup_dependencies(
        self, subtasks: List[Dict[str, Any]], workflow_type: str
    ) -> Dict[str, List[str]]:
        """设置任务依赖关系"""
        dependency_graph = {}

        # 默认按顺序依赖
        for i in range(1, len(subtasks)):
            current_task_id = subtasks[i]["task_id"]
            prev_task_id = subtasks[i - 1]["task_id"]
            dependency_graph[current_task_id] = [prev_task_id]

        return dependency_graph

    def _assign_tasks_to_agents(self, subtasks: List[Dict[str, Any]]) -> Dict[str, str]:
        """将任务分配给合适的智能体类型"""
        task_agent_mapping = {
            "document_parsing": AgentType.DOCUMENT_PARSER.value,
            "data_parsing": AgentType.DOCUMENT_PARSER.value,
            "business_parsing": AgentType.DOCUMENT_PARSER.value,
            "risk_identification": AgentType.RISK_IDENTIFIER.value,
            "anomaly_detection": AgentType.RISK_IDENTIFIER.value,
            "compliance_check": AgentType.COMPLIANCE_CHECKER.value,
            "aml_check": AgentType.COMPLIANCE_CHECKER.value,
            "general_compliance": AgentType.COMPLIANCE_CHECKER.value,
            "report_generation": AgentType.REPORT_WRITER.value,
            "quality_audit": AgentType.QUALITY_AUDITOR.value,
        }

        assignments = {}
        for subtask in subtasks:
            task_type = subtask["task_type"]
            agent_type = task_agent_mapping.get(task_type, AgentType.RISK_IDENTIFIER.value)
            assignments[subtask["task_id"]] = agent_type

        return assignments

    def _generate_execution_plan(
        self, subtasks: List[Dict[str, Any]], assignments: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """生成执行计划"""
        execution_plan = []

        for i, subtask in enumerate(subtasks, 1):
            execution_plan.append({
                "sequence": i,
                "task_id": subtask["task_id"],
                "task_type": subtask["task_type"],
                "name": subtask["name"],
                "description": subtask["description"],
                "assigned_agent_type": assignments.get(subtask["task_id"], "unknown"),
                "priority": subtask["priority"],
            })

        return execution_plan

    def _estimate_duration(self, subtasks: List[Dict[str, Any]]) -> int:
        """估算执行时间（分钟）"""
        # 假设每个任务平均 0.5 分钟，加上并行执行的优化
        base_time = len(subtasks) * 0.5
        # 考虑并行因素，乘以 0.7
        return max(1, int(base_time * 0.7))
