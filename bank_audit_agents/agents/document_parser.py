"""
文档解析智能体模块

负责解析和理解各类审计文档，提取关键信息。

核心能力:
    1. 解析多种格式文档（PDF, Word, Excel, 扫描件等）
    2. 提取结构化信息（金额、日期、主体、关键词等）
    3. 文档分类和打标签
    4. 关键段落识别和摘要生成

工作模式:
    - LLM 模式：当配置了 OpenAI API Key 时，使用 LLM 进行智能文档解析
    - Mock 模式：未配置 API Key 时，返回示例数据作为回退

使用示例:
    agent = DocumentParserAgent()
    task = Task(
        task_type="document_parsing",
        description="解析信贷合同",
        input_data={
            "document_path": "data/loan_contract.pdf",
            "document_type": "loan_contract",
            "extraction_requirements": ["借款人", "贷款金额", "期限"],
        },
    )
    result = await agent.run(task)
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

# 获取模块级日志记录器
logger = get_logger(__name__)


class DocumentParserAgent(BaseAgent):
    """
    文档解析智能体

    继承自 BaseAgent，实现文档解析的核心业务逻辑。

    核心职责:
        1. 读取文档内容（支持本地文件路径）
        2. 使用 LLM 提取结构化信息
        3. 识别文档类型并分类
        4. 生成文档摘要

    输入数据要求:
        - document_path: 文档路径（必填）
        - document_type: 文档类型（可选，auto 表示自动识别）
        - extraction_requirements: 需要提取的字段列表（可选）
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """
        初始化文档解析智能体

        Args:
            agent_id: 智能体 ID（可选，不提供则自动生成）
            **kwargs: 其他传递给父类的参数
        """
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id, **kwargs)
        # 获取 LLM 客户端（支持 mock fallback）
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        定义智能体的角色为银行审计文档专家，明确职责和输出要求。

        Returns:
            str: 系统提示词文本
        """
        return """你是一位资深银行审计文档专家，具有15年以上银行审计文档处理经验。

你的核心职责:
1. 精确解析各类审计文档，包括信贷合同、财务报表、监管文件、会议纪要等
2. 提取关键审计信息：金额、日期、交易主体、审批流程、风险条款等
3. 识别文档类型，并进行标准化分类和打标签
4. 生成准确的文档摘要和要点摘录

输出要求:
- 以结构化 JSON 格式输出提取结果
- 确保数值和日期的准确性
- 标注信息来源和文档位置
- 对不确定的信息标注置信度
"""

    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        列出文档解析相关的工具，实际项目中会接入真实的文档解析工具。

        Returns:
            List[Any]: 工具名称列表
        """
        return [
            # 实际项目中会接入真实的文档解析工具
            "pdf_parser",           # PDF 文档解析工具
            "docx_parser",          # Word 文档解析工具
            "excel_parser",         # Excel 表格解析工具
            "text_extractor",       # 文本提取工具
            "table_extractor",      # 表格提取工具
            "entity_recognizer",    # 实体识别工具
        ]

    async def execute(self, task: Task) -> AgentResult:
        """
        执行文档解析任务

        核心执行流程:
            1. 验证输入参数（检查文档路径是否存在）
            2. 调用 _parse_document 解析文档内容
            3. 调用 _extract_key_information 提取关键信息
            4. 调用 _generate_document_summary 生成摘要
            5. 返回包含解析结果的 AgentResult

        Args:
            task: 任务对象，包含输入数据

        Returns:
            AgentResult: 执行结果
        """
        logger.info(f"文档解析智能体开始处理任务: {task.task_id}")

        # 从任务输入数据中提取参数
        document_path = task.input_data.get("document_path")
        document_type = task.input_data.get("document_type", "auto")
        extraction_requirements = task.input_data.get("extraction_requirements", [])

        # 验证必填参数
        if not document_path:
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary="缺少文档路径参数",
                error="document_path is required",
                confidence_score=0.0,
            )

        # 解析文档内容（LLM 驱动，mock 模式下回退到示例数据）
        findings = await self._parse_document(
            document_path, document_type, extraction_requirements
        )

        # 从解析结果中提取关键信息
        key_info = self._extract_key_information(findings)

        # 生成文档摘要
        summary = self._generate_document_summary(key_info)

        # 返回执行结果
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=summary,
            findings=findings,
            recommendations=[
                "建议对提取的关键金额进行交叉验证",
                "建议对重要合同条款进行人工复核",
            ],
            confidence_score=0.85,
            metadata={
                "document_path": document_path,
                "document_type": key_info.get("document_type", "unknown"),
                "extracted_fields": len(key_info),
                "total_findings": len(findings),
            },
        )

    async def _parse_document(
        self, document_path: str, document_type: str, requirements: List[str]
    ) -> List[Dict[str, Any]]:
        """
        解析文档内容

        工作机制:
            1. 尝试读取文档内容（如果路径是文本文件）
            2. 构造 LLM 调用参数
            3. 调用 LLM 进行结构化信息提取
            4. 如果 LLM 不可用，使用 mock fallback 返回示例数据

        Args:
            document_path:    文档路径
            document_type:    文档类型
            requirements:     需要提取的字段列表

        Returns:
            List[Dict[str, Any]]: 提取的结构化信息列表
        """
        # 尝试读取文档内容（如果路径是文本文件）
        document_text = ""
        try:
            with open(document_path, "r", encoding="utf-8") as f:
                # 最多读取前 4000 字符，避免超出 LLM token 限制
                document_text = f.read()[:4000]
        except Exception:
            # 如果无法读取文件，使用文档路径作为占位符
            document_text = f"[文档路径: {document_path}]"

        # 构造用户提示词（JSON 格式，便于 LLM 解析）
        user_prompt = json.dumps({
            "document_path": document_path,
            "document_type": document_type,
            "extraction_requirements": requirements,
            "document_text": document_text,
        }, ensure_ascii=False)

        # 定义 mock fallback 函数，返回示例解析结果
        def _mock_fallback():
            return self._get_mock_findings()

        # 调用 LLM（带 fallback）
        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含一个 'findings' 数组，每个元素包含字段：field, value, value_type(currency/period/rate/entity/text), confidence(0-1), location。",
            user_prompt=user_prompt,
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        # 处理 LLM 返回结果
        if isinstance(result, dict) and "findings" in result:
            return result["findings"]
        elif isinstance(result, list):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_findings()

    def _get_mock_findings(self) -> List[Dict[str, Any]]:
        """
        返回示例解析结果（mock fallback）

        当 LLM 不可用时使用此方法返回模拟数据，
        用于开发测试和演示目的。

        Returns:
            List[Dict[str, Any]]: 示例解析结果列表
        """
        return [
            {
                "field": "loan_amount",      # 字段名：贷款金额
                "value": "5000000",          # 值：500万元
                "value_type": "currency",     # 值类型：货币
                "confidence": 0.95,           # 置信度：95%
                "location": "第2页第3段",     # 在文档中的位置
            },
            {
                "field": "loan_term",         # 字段名：贷款期限
                "value": "12个月",           # 值：12个月
                "value_type": "period",       # 值类型：期限
                "confidence": 0.98,           # 置信度：98%
                "location": "第2页第5段",
            },
            {
                "field": "interest_rate",     # 字段名：利率
                "value": "4.35%",            # 值：4.35%
                "value_type": "rate",         # 值类型：比率
                "confidence": 0.92,           # 置信度：92%
                "location": "第3页第1段",
            },
            {
                "field": "borrower",          # 字段名：借款人
                "value": "某某科技有限公司",   # 值：公司名称
                "value_type": "entity",       # 值类型：实体
                "confidence": 0.99,           # 置信度：99%
                "location": "第1页标题",
            },
            {
                "field": "guarantor",         # 字段名：担保人
                "value": "某某担保集团",       # 值：担保公司名称
                "value_type": "entity",       # 值类型：实体
                "confidence": 0.90,           # 置信度：90%
                "location": "第4页第2段",
            },
        ]

    def _extract_key_information(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从解析结果中提取关键信息

        将 findings 列表转换为字典形式，并推断文档类型。

        Args:
            findings: 解析结果列表

        Returns:
            Dict[str, Any]: 关键信息字典
        """
        key_info = {}
        for finding in findings:
            field = finding["field"]
            key_info[field] = finding["value"]

        # 根据提取的字段推断文档类型
        if "loan_amount" in key_info and "borrower" in key_info:
            key_info["document_type"] = "loan_contract"           # 信贷合同
        elif "balance_sheet_date" in key_info:
            key_info["document_type"] = "financial_statement"     # 财务报表
        else:
            key_info["document_type"] = "general_audit_document"  # 一般审计文档

        return key_info

    def _generate_document_summary(self, key_info: Dict[str, Any]) -> str:
        """
        生成文档摘要

        根据文档类型和关键信息生成简洁的摘要文本。

        Args:
            key_info: 关键信息字典

        Returns:
            str: 文档摘要
        """
        doc_type = key_info.get("document_type", "unknown")

        # 根据文档类型生成不同格式的摘要
        if doc_type == "loan_contract":
            borrower = key_info.get("borrower", "未知")
            amount = key_info.get("loan_amount", "未知")
            term = key_info.get("loan_term", "未知")
            return f"信贷合同：借款人{borrower}，贷款金额{amount}，期限{term}"

        # 默认摘要格式
        return f"文档解析完成，共提取{len(key_info)}项关键信息"