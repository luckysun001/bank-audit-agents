"""
质量审核和任务协调智能体模块

负责协调多智能体任务执行流程，确保审计质量和任务协作。

核心能力:
    1. 任务调度和分配
    2. 多智能体协作协调
    3. 审计质量检查和评估
    4. 任务依赖管理和工作流编排
    5. 进度监控和状态追踪

质量检查维度:
    - 结果准确性（数据正确性、逻辑一致性）
    - 完整性（是否覆盖所有要求）
    - 规范性（是否符合格式要求）
    - 时效性（是否在规定时间内完成）

工作模式:
    - LLM 模式：使用 LLM 进行智能质量评估和任务协调
    - Mock 模式：未配置 API Key 时，返回示例协调结果
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


# 质量评估标准（模拟）
QUALITY_STANDARDS = {
    # 结果准确性标准
    "accuracy": {
        "name": "准确性",
        "weight": 0.35,
        "criteria": [
            "数据提取是否准确",
            "风险评估是否合理",
            "合规判断是否正确",
            "结论是否有依据",
        ],
    },
    # 完整性标准
    "completeness": {
        "name": "完整性",
        "weight": 0.25,
        "criteria": [
            "是否覆盖所有检查点",
            "是否遗漏重要信息",
            "建议是否全面",
            "文档是否齐全",
        ],
    },
    # 规范性标准
    "standardization": {
        "name": "规范性",
        "weight": 0.20,
        "criteria": [
            "格式是否符合要求",
            "语言是否专业",
            "结构是否清晰",
            "是否遵循审计标准",
        ],
    },
    # 时效性标准
    "timeliness": {
        "name": "时效性",
        "weight": 0.20,
        "criteria": [
            "是否在规定时间内完成",
            "是否按时提交结果",
        ],
    },
}


class QualityAndCoordinatorAgent(BaseAgent):
    """
    质量审核和任务协调智能体

    继承自 BaseAgent，实现质量审核和任务协调的核心业务逻辑。

    核心职责:
        1. 协调多智能体的任务执行顺序
        2. 检查各智能体输出结果的质量
        3. 评估审计工作的整体质量
        4. 处理任务依赖关系
        5. 监控任务执行进度

    输入数据要求:
        - task_type: 任务类型（quality_check/coordination/progress_monitor）
        - agent_results: 各智能体的执行结果
        - task_context: 任务上下文（包含任务依赖、优先级等）
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """
        初始化质量审核和任务协调智能体

        Args:
            agent_id: 智能体 ID（可选，不提供则自动生成）
            **kwargs: 其他传递给父类的参数
        """
        super().__init__(AgentType.QUALITY_AND_COORDINATOR, agent_id, **kwargs)
        # 获取 LLM 客户端（支持 mock fallback）
        self._llm = get_llm_client()
        # 加载质量评估标准
        self._quality_standards = QUALITY_STANDARDS

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        定义智能体的角色为银行审计质量控制专家，明确职责和输出要求。

        Returns:
            str: 系统提示词文本
        """
        return """你是一位资深银行审计质量控制专家，具有10年以上审计质量管理经验。

你的核心职责:
1. 审核各智能体输出结果的质量
2. 评估审计工作的整体质量水平
3. 协调多智能体之间的任务执行流程
4. 识别质量问题并提出改进建议

质量评估标准:
- 准确性：数据正确性、逻辑一致性、结论合理性
- 完整性：覆盖范围、信息全面性、建议完整性
- 规范性：格式规范、语言专业、结构清晰
- 时效性：完成时间、提交及时性

输出要求:
- 以结构化 JSON 格式输出，包含 quality_report 对象
- quality_report 包含：overall_score, dimension_scores, quality_issues, improvement_suggestions
"""

    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        列出质量审核和任务协调相关的工具，实际项目中会接入真实的工具。

        Returns:
            List[Any]: 工具名称列表
        """
        return [
            "quality_assessment_tool",  # 质量评估工具
            "task_scheduler",           # 任务调度工具
            "progress_tracker",         # 进度追踪工具
            "dependency_manager",       # 依赖管理工具
            "escalation_handler",       # 升级处理工具
        ]

    async def execute(self, task: Task) -> AgentResult:
        """
        执行质量审核或任务协调任务

        核心执行流程:
            1. 验证输入参数（任务类型、智能体结果）
            2. 根据任务类型执行相应操作
            3. 调用 _perform_quality_check 进行质量检查
            4. 调用 _coordinate_tasks 进行任务协调
            5. 返回包含审核/协调结果的 AgentResult

        Args:
            task: 任务对象，包含输入数据

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"质量审核和任务协调智能体开始处理任务: {task.task_id}")

        # 从任务输入数据中提取参数
        task_type = task.input_data.get("task_type", "quality_check")
        agent_results = task.input_data.get("agent_results", {})
        task_context = task.input_data.get("task_context", {})

        # 验证必填参数
        if not agent_results and task_type == "quality_check":
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少智能体结果参数",
                error="agent_results is required for quality_check",
                confidence_score=0.0,
            )

        # 根据任务类型执行相应操作
        if task_type == "quality_check":
            # 执行质量检查
            quality_report = await self._perform_quality_check(agent_results, task_context)
            summary = self._generate_quality_summary(quality_report)
            findings = quality_report
        elif task_type == "coordination":
            # 执行任务协调
            coordination_result = await self._coordinate_tasks(agent_results, task_context)
            summary = self._generate_coordination_summary(coordination_result)
            findings = coordination_result
        elif task_type == "progress_monitor":
            # 执行进度监控
            progress_result = await self._monitor_progress(agent_results, task_context)
            summary = self._generate_progress_summary(progress_result)
            findings = progress_result
        else:
            # 默认执行质量检查
            quality_report = await self._perform_quality_check(agent_results, task_context)
            summary = self._generate_quality_summary(quality_report)
            findings = quality_report

        # 返回执行结果
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=summary,
            findings=findings,
            recommendations=self._generate_recommendations(findings),
            confidence_score=self._calculate_confidence(findings),
            metadata={
                "task_type": task_type,
                "agent_count": len(agent_results),
                "overall_score": findings.get("overall_score", 0),
            },
        )

    async def _perform_quality_check(
        self, agent_results: Dict[str, Any], task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行质量检查

        工作机制:
            1. 构造质量检查提示词
            2. 调用 LLM 进行智能质量评估
            3. 如果 LLM 不可用，使用 mock fallback 返回示例质量检查结果

        Args:
            agent_results: 各智能体的执行结果
            task_context: 任务上下文

        Returns:
            Dict[str, Any]: 质量检查报告
        """
        # 构造用户提示词
        user_prompt = {
            "agent_results": agent_results,
            "task_context": task_context,
            "quality_standards": self._quality_standards,
            "check_requirements": "请根据质量标准，评估各智能体输出结果的质量。",
        }

        # 定义 mock fallback 函数，返回示例质量检查结果
        def _mock_fallback():
            return self._get_mock_quality_report(agent_results)

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict) and "quality_report" in result:
            return result["quality_report"]
        elif isinstance(result, dict):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_quality_report(agent_results)

    def _get_mock_quality_report(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        返回示例质量检查报告（mock fallback）

        根据智能体结果数量返回示例质量评估数据，
        用于开发测试和演示目的。

        Args:
            agent_results: 各智能体的执行结果

        Returns:
            Dict[str, Any]: 示例质量检查报告
        """
        agent_count = len(agent_results)

        return {
            "overall_score": 85.5,
            "dimension_scores": {
                "accuracy": {
                    "score": 88,
                    "weight": 0.35,
                    "assessment": "数据提取准确，结论有依据",
                },
                "completeness": {
                    "score": 82,
                    "weight": 0.25,
                    "assessment": "覆盖主要检查点，但部分细节可补充",
                },
                "standardization": {
                    "score": 87,
                    "weight": 0.20,
                    "assessment": "格式规范，语言专业",
                },
                "timeliness": {
                    "score": 85,
                    "weight": 0.20,
                    "assessment": "基本按时完成",
                },
            },
            "quality_issues": [
                {
                    "issue": "部分风险评估置信度偏低",
                    "severity": "low",
                    "agent": "risk_identifier",
                    "suggestion": "建议增加数据验证环节",
                },
                {
                    "issue": "文档解析缺少部分字段",
                    "severity": "middle",
                    "agent": "document_parser",
                    "suggestion": "建议完善字段提取规则",
                },
            ],
            "improvement_suggestions": [
                "建议建立数据交叉验证机制",
                "建议优化字段提取规则",
                "建议加强结果审核环节",
            ],
            "agent_count": agent_count,
            "pass_rate": 100 if agent_count > 0 else 0,
        }

    async def _coordinate_tasks(
        self, agent_results: Dict[str, Any], task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行任务协调

        工作机制:
            1. 分析任务依赖关系
            2. 确定任务执行顺序
            3. 调用 LLM 进行智能任务协调
            4. 如果 LLM 不可用，使用 mock fallback 返回示例协调结果

        Args:
            agent_results: 各智能体的执行结果
            task_context: 任务上下文

        Returns:
            Dict[str, Any]: 任务协调结果
        """
        # 构造用户提示词
        user_prompt = {
            "agent_results": agent_results,
            "task_context": task_context,
            "coordination_requirements": "请分析任务依赖关系，确定最优执行顺序。",
        }

        # 定义 mock fallback 函数，返回示例协调结果
        def _mock_fallback():
            return self._get_mock_coordination_result()

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_coordination_result()

    def _get_mock_coordination_result(self) -> Dict[str, Any]:
        """
        返回示例任务协调结果（mock fallback）

        返回示例任务协调数据，用于开发测试和演示目的。

        Returns:
            Dict[str, Any]: 示例任务协调结果
        """
        return {
            "task_sequence": [
                {"agent": "document_parser", "step": 1, "status": "completed"},
                {"agent": "compliance_checker", "step": 2, "status": "completed"},
                {"agent": "risk_identifier", "step": 3, "status": "completed"},
                {"agent": "quality_and_coordinator", "step": 4, "status": "completed"},
                {"agent": "report_writer", "step": 5, "status": "pending"},
            ],
            "dependencies": {
                "compliance_checker": ["document_parser"],
                "risk_identifier": ["document_parser"],
                "quality_and_coordinator": ["compliance_checker", "risk_identifier"],
                "report_writer": ["quality_and_coordinator"],
            },
            "next_step": "report_writer",
            "estimated_completion_time": "10分钟",
            "overall_progress": 80,
        }

    async def _monitor_progress(
        self, agent_results: Dict[str, Any], task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        监控任务进度

        工作机制:
            1. 收集各智能体的执行状态
            2. 计算整体进度
            3. 识别瓶颈和延迟
            4. 调用 LLM 进行智能进度分析

        Args:
            agent_results: 各智能体的执行结果
            task_context: 任务上下文

        Returns:
            Dict[str, Any]: 进度监控结果
        """
        # 构造用户提示词
        user_prompt = {
            "agent_results": agent_results,
            "task_context": task_context,
            "monitor_requirements": "请监控任务执行进度，识别瓶颈和延迟。",
        }

        # 定义 mock fallback 函数，返回示例进度监控结果
        def _mock_fallback():
            return self._get_mock_progress_result(agent_results)

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt(),
            user_prompt=str(user_prompt),
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_progress_result(agent_results)

    def _get_mock_progress_result(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        返回示例进度监控结果（mock fallback）

        根据智能体结果数量返回示例进度数据，用于开发测试和演示目的。

        Args:
            agent_results: 各智能体的执行结果

        Returns:
            Dict[str, Any]: 示例进度监控结果
        """
        agent_count = len(agent_results)

        return {
            "overall_progress": 80,
            "agent_status": {
                "document_parser": {"status": "completed", "progress": 100},
                "compliance_checker": {"status": "completed", "progress": 100},
                "risk_identifier": {"status": "completed", "progress": 100},
                "quality_and_coordinator": {"status": "completed", "progress": 100},
                "report_writer": {"status": "pending", "progress": 0},
            },
            "completed_tasks": agent_count,
            "total_tasks": 5,
            "estimated_remaining_time": "10分钟",
            "bottlenecks": [],
            "delays": [],
        }

    def _generate_quality_summary(self, quality_report: Dict[str, Any]) -> str:
        """
        生成质量检查摘要

        根据质量检查报告生成简洁的摘要文本。

        Args:
            quality_report: 质量检查报告

        Returns:
            str: 质量检查摘要
        """
        overall_score = quality_report.get("overall_score", 0)
        issue_count = len(quality_report.get("quality_issues", []))

        if issue_count == 0:
            return f"质量检查通过，整体评分：{overall_score}分"

        return f"质量检查完成，整体评分：{overall_score}分，发现{issue_count}项质量问题"

    def _generate_coordination_summary(self, coordination_result: Dict[str, Any]) -> str:
        """
        生成任务协调摘要

        根据任务协调结果生成简洁的摘要文本。

        Args:
            coordination_result: 任务协调结果

        Returns:
            str: 任务协调摘要
        """
        next_step = coordination_result.get("next_step", "未知")
        progress = coordination_result.get("overall_progress", 0)

        return f"任务协调完成，当前进度：{progress}%，下一步：{next_step}"

    def _generate_progress_summary(self, progress_result: Dict[str, Any]) -> str:
        """
        生成进度监控摘要

        根据进度监控结果生成简洁的摘要文本。

        Args:
            progress_result: 进度监控结果

        Returns:
            str: 进度监控摘要
        """
        overall_progress = progress_result.get("overall_progress", 0)
        completed = progress_result.get("completed_tasks", 0)
        total = progress_result.get("total_tasks", 0)

        return f"进度监控完成，已完成{completed}/{total}个任务，整体进度：{overall_progress}%"

    def _generate_recommendations(self, findings: Dict[str, Any]) -> List[str]:
        """
        生成改进建议

        从质量检查或协调结果中提取建议。

        Args:
            findings: 检查或协调结果

        Returns:
            List[str]: 改进建议列表
        """
        recommendations = []

        # 提取质量检查报告中的改进建议
        if "improvement_suggestions" in findings:
            recommendations.extend(findings["improvement_suggestions"])

        # 提取质量问题中的建议
        if "quality_issues" in findings:
            for issue in findings["quality_issues"]:
                suggestion = issue.get("suggestion")
                if suggestion and suggestion not in recommendations:
                    recommendations.append(suggestion)

        # 添加通用建议
        if not recommendations:
            recommendations.append("建议定期进行质量检查")
            recommendations.append("建议优化任务协调流程")

        return recommendations

    def _calculate_confidence(self, findings: Dict[str, Any]) -> float:
        """
        计算置信度分数

        根据质量评分计算置信度。

        Args:
            findings: 检查或协调结果

        Returns:
            float: 置信度分数（0-1）
        """
        overall_score = findings.get("overall_score", 85)

        return min(0.95, max(0.70, overall_score / 100))