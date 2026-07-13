"""
文档解析智能体
负责解析和理解各类审计文档，提取关键信息
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


class DocumentParserAgent(BaseAgent):
    """
    文档解析智能体

    核心能力:
    1. 解析多种格式文档（PDF, Word, Excel, 扫描件等）
    2. 提取结构化信息（金额、日期、主体、关键词等）
    3. 文档分类和打标签
    4. 关键段落识别和摘要生成
    """

    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id, **kwargs)
        self._llm = get_llm_client()

    def get_system_prompt(self) -> str:
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
        return [
            # 实际项目中会接入真实的文档解析工具
            "pdf_parser",
            "docx_parser",
            "excel_parser",
            "text_extractor",
            "table_extractor",
            "entity_recognizer",
        ]

    async def execute(self, task: Task) -> AgentResult:
        logger.info(f"文档解析智能体开始处理任务: {task.task_id}")

        document_path = task.input_data.get("document_path")
        document_type = task.input_data.get("document_type", "auto")
        extraction_requirements = task.input_data.get("extraction_requirements", [])

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

        # 提取关键信息
        key_info = self._extract_key_information(findings)

        # 生成文档摘要
        summary = self._generate_document_summary(key_info)

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
        - LLM 模式：将文档内容发送给 LLM 进行结构化信息提取
        - Mock 模式：返回示例解析结果
        """
        # 尝试读取文档内容（如果路径是文本文件）
        document_text = ""
        try:
            with open(document_path, "r", encoding="utf-8") as f:
                document_text = f.read()[:4000]
        except Exception:
            document_text = f"[文档路径: {document_path}]"

        user_prompt = json.dumps({
            "document_path": document_path,
            "document_type": document_type,
            "extraction_requirements": requirements,
            "document_text": document_text,
        }, ensure_ascii=False)

        def _mock_fallback():
            return self._get_mock_findings()

        result = await self._llm.call_with_fallback(
            system_prompt=self.get_system_prompt() + "\n\n请以 JSON 格式返回结果，包含一个 'findings' 数组，每个元素包含字段：field, value, value_type(currency/period/rate/entity/text), confidence(0-1), location。",
            user_prompt=user_prompt,
            fallback_fn=_mock_fallback,
            response_format_json=True,
        )

        if isinstance(result, dict) and "findings" in result:
            return result["findings"]
        elif isinstance(result, list):
            return result
        else:
            logger.warning("LLM 返回格式异常，使用 mock 数据")
            return self._get_mock_findings()

    def _get_mock_findings(self) -> List[Dict[str, Any]]:
        """返回示例解析结果（mock fallback）"""
        return [
            {
                "field": "loan_amount",
                "value": "5000000",
                "value_type": "currency",
                "confidence": 0.95,
                "location": "第2页第3段",
            },
            {
                "field": "loan_term",
                "value": "12个月",
                "value_type": "period",
                "confidence": 0.98,
                "location": "第2页第5段",
            },
            {
                "field": "interest_rate",
                "value": "4.35%",
                "value_type": "rate",
                "confidence": 0.92,
                "location": "第3页第1段",
            },
            {
                "field": "borrower",
                "value": "某某科技有限公司",
                "value_type": "entity",
                "confidence": 0.99,
                "location": "第1页标题",
            },
            {
                "field": "guarantor",
                "value": "某某担保集团",
                "value_type": "entity",
                "confidence": 0.90,
                "location": "第4页第2段",
            },
        ]

    def _extract_key_information(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从解析结果中提取关键信息"""
        key_info = {}
        for finding in findings:
            field = finding["field"]
            key_info[field] = finding["value"]

        # 推断文档类型
        if "loan_amount" in key_info and "borrower" in key_info:
            key_info["document_type"] = "loan_contract"
        elif "balance_sheet_date" in key_info:
            key_info["document_type"] = "financial_statement"
        else:
            key_info["document_type"] = "general_audit_document"

        return key_info

    def _generate_document_summary(self, key_info: Dict[str, Any]) -> str:
        """生成文档摘要"""
        doc_type = key_info.get("document_type", "unknown")

        if doc_type == "loan_contract":
            borrower = key_info.get("borrower", "未知")
            amount = key_info.get("loan_amount", "未知")
            term = key_info.get("loan_term", "未知")
            return f"信贷合同：借款人{borrower}，贷款金额{amount}，期限{term}"

        return f"文档解析完成，共提取{len(key_info)}项关键信息"
