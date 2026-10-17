"""
文档加载层：把各种格式的审计文档变成纯文本，供后续 LLM / 规则引擎处理。

设计要点
--------
1. **先文本层，后 OCR**。PDF 大多内嵌文本层，直接提取又快又准；
   只有确认是扫描件（文本层过少）时才走 OCR —— OCR 慢且易错，不该无差别使用。
2. **重型/可选依赖一律函数内按需导入**。缺失时抛 :class:`MissingDependencyError`
   并附带安装命令，绝不静默返回空文本（静默失败在审计场景里等于漏审）。
3. **有状态的过程信息不丢**：页数、提取方式、告警都会记录在
   :class:`ExtractedDocument` 里，便于 Agent 在报告中标注"该结论来自 OCR，
   置信度较低"这类重要提示。

已声明的主依赖：``pypdf``（PDF）、``python-docx``（Word）。
可选依赖（需自行安装）：``pytesseract`` + tesseract 二进制、``paddleocr``、
``openpyxl``（Excel）、``Pillow``（图片预处理）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from bank_audit_agents.tools.base import tool
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)

#: 平均每页少于该字符数即判定为扫描件（纯扫描页通常只有 0~几十个字符）
SCANNED_PAGE_THRESHOLD = 50

#: 支持的扩展名 -> 处理方式
SUPPORTED_EXTENSIONS = {
    ".txt": "纯文本",
    ".md": "纯文本",
    ".json": "纯文本",
    ".csv": "纯文本",
    ".pdf": "PDF（文本层优先，扫描件走 OCR）",
    ".docx": "Word",
    ".xlsx": "Excel（openpyxl）",
    ".xlsm": "Excel（openpyxl）",
    ".png": "图片（OCR）",
    ".jpg": "图片（OCR）",
    ".jpeg": "图片（OCR）",
    ".tif": "图片（OCR）",
    ".tiff": "图片（OCR）",
}


class MissingDependencyError(RuntimeError):
    """可选依赖缺失。

    区别于 ImportError：附带**可直接执行的安装命令**，
    并且明确说明是系统级依赖还是 Python 包。
    """

    def __init__(self, package: str, install_cmd: str, note: str = ""):
        self.package = package
        self.install_cmd = install_cmd
        self.note = note
        message = f"缺少依赖 {package}，请安装: {install_cmd}"
        if note:
            message += f"（{note}）"
        super().__init__(message)


@dataclass
class ExtractedDocument:
    """文档提取结果"""

    text: str
    source: str
    #: 提取方式：text_layer / ocr / docx / xlsx / plain_text
    method: str
    pages: int = 0
    #: 提取过程中的告警（如"疑似扫描件"、"部分页 OCR 失败"）
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "method": self.method,
            "pages": self.pages,
            "char_count": self.char_count,
            "is_empty": self.is_empty,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def _require(module: str, package: str, install_cmd: str, note: str = ""):
    """按需导入可选依赖，缺失时抛出带安装命令的错误。"""
    try:
        return __import__(module)
    except ImportError as exc:
        raise MissingDependencyError(package, install_cmd, note) from exc


# ---------------------------------------------------------------------------
# 各格式提取
# ---------------------------------------------------------------------------


def _extract_plain_text(path: Path, encoding: str = "utf-8") -> ExtractedDocument:
    for enc in (encoding, "utf-8", "gbk", "gb18030"):
        try:
            text = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:  # pragma: no cover - 理论上 gb18030 能覆盖中文场景
        text = path.read_text(encoding="utf-8", errors="replace")
    return ExtractedDocument(
        text=text, source=str(path), method="plain_text", pages=1
    )


def _extract_pdf(
    path: Path,
    ocr_enabled: bool,
    ocr_lang: str,
    scanned_threshold: int,
    max_pages: Optional[int],
) -> ExtractedDocument:
    """PDF 提取：先取文本层，判定为扫描件时再 OCR。"""
    pypdf = _require(
        "pypdf",
        "pypdf",
        "pip install pypdf",
    )

    reader = pypdf.PdfReader(str(path))
    total_pages = len(reader.pages)
    limit = min(total_pages, max_pages) if max_pages else total_pages

    chunks: List[str] = []
    empty_pages: List[int] = []
    warnings: List[str] = []

    for idx in range(limit):
        try:
            page_text = reader.pages[idx].extract_text() or ""
        except Exception as exc:  # 单页损坏不应中断整份文档
            page_text = ""
            warnings.append(f"第 {idx + 1} 页文本提取失败: {exc}")
        chunks.append(page_text)
        if len(page_text.strip()) < scanned_threshold:
            empty_pages.append(idx + 1)

    text = "\n".join(chunks)
    chars_per_page = len(text.strip()) / max(limit, 1)

    doc = ExtractedDocument(
        text=text,
        source=str(path),
        method="text_layer",
        pages=limit,
        warnings=warnings,
        metadata={"total_pages": total_pages, "empty_text_pages": empty_pages},
    )

    # 文本层过少 -> 判定为扫描件
    if chars_per_page < scanned_threshold:
        if not ocr_enabled:
            doc.warnings.append(
                f"平均每页仅 {chars_per_page:.0f} 字符，疑似扫描件；"
                "已禁用 OCR（ocr_enabled=False），提取结果可能不完整"
            )
            return doc

        doc.warnings.append(
            f"平均每页仅 {chars_per_page:.0f} 字符，判定为扫描件，转 OCR"
        )
        try:
            ocr_text = ocr_pdf(path, lang=ocr_lang, max_pages=max_pages)
            if ocr_text.strip():
                doc.text = ocr_text
                doc.method = "ocr"
                doc.metadata["ocr_lang"] = ocr_lang
            else:
                doc.warnings.append("OCR 未识别出任何文本")
        except MissingDependencyError as exc:
            doc.warnings.append(str(exc))
        except Exception as exc:  # OCR 失败不应让整个解析崩掉
            doc.warnings.append(f"OCR 失败: {exc}")

    return doc


def _extract_docx(path: Path) -> ExtractedDocument:
    docx = _require("docx", "python-docx", "pip install python-docx")

    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    # 表格内容在审计文档里常常是关键数据，不能丢
    tables: List[str] = []
    for table in document.tables:
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        if rows:
            tables.append("\n".join(rows))

    text = "\n".join(paragraphs)
    if tables:
        text += "\n\n[表格]\n" + "\n\n".join(tables)

    return ExtractedDocument(
        text=text,
        source=str(path),
        method="docx",
        pages=1,
        metadata={"paragraphs": len(paragraphs), "tables": len(tables)},
    )


def _extract_xlsx(path: Path) -> ExtractedDocument:
    openpyxl = _require("openpyxl", "openpyxl", "pip install openpyxl")

    workbook = openpyxl.load_workbook(str(path), data_only=True)
    sheets: List[str] = []
    for name in workbook.sheetnames:
        sheet = workbook[name]
        rows = [
            " | ".join("" if cell is None else str(cell) for cell in row)
            for row in sheet.iter_rows(values_only=True)
        ]
        rows = [r for r in rows if r.strip(" |")]
        if rows:
            sheets.append(f"[{name}]\n" + "\n".join(rows))

    return ExtractedDocument(
        text="\n\n".join(sheets),
        source=str(path),
        method="xlsx",
        pages=len(workbook.sheetnames),
        metadata={"sheets": workbook.sheetnames},
    )


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


def _ocr_with_tesseract(image_path: Path, lang: str) -> str:
    """用 pytesseract 识别单张图片。

    注意：``pytesseract`` 只是 tesseract 的 Python 封装，
    **还需要系统安装 tesseract 二进制**（apt install tesseract-ocr /
    brew install tesseract / Windows 安装包），否则会报
    ``TesseractNotFoundError`` —— 这里单独给出提示。
    """
    pytesseract = _require(
        "pytesseract",
        "pytesseract",
        "pip install pytesseract && (apt-get install -y tesseract-ocr || brew install tesseract)",
        "pytesseract 仅为封装，还需系统级 tesseract 二进制",
    )
    try:
        return pytesseract.image_to_string(str(image_path), lang=lang)
    except Exception as exc:  # 通常是 TesseractNotFoundError
        raise MissingDependencyError(
            "tesseract 二进制",
            "apt-get install -y tesseract-ocr  # 或 brew install tesseract",
            f"pytesseract 已安装但调用失败: {exc}",
        ) from exc


def _ocr_with_paddle(image_path: Path, lang: str) -> str:
    """用 PaddleOCR 识别单张图片（中文场景效果通常优于 tesseract）。"""
    paddleocr = _require("paddleocr", "paddleocr", "pip install paddleocr")

    engine = paddleocr.PaddleOCR(lang="ch" if lang.startswith("chi") else "en")
    result = engine.ocr(str(image_path), cls=True)
    lines: List[str] = []
    for page in result or []:
        for line in page or []:
            if line and len(line) >= 2 and line[1]:
                lines.append(str(line[1][0]))
    return "\n".join(lines)


def ocr_image(image_path: str, lang: str = "chi_sim+eng", backend: str = "auto") -> str:
    """识别图片中的文字。

    Args:
        image_path: 图片路径
        lang: tesseract 语言参数（PaddleOCR 只区分中英文）
        backend: ``tesseract`` / ``paddle`` / ``auto``（依次尝试）
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图片不存在: {path}")

    order = ["tesseract", "paddle"] if backend == "auto" else [backend]
    errors: List[str] = []

    for name in order:
        try:
            if name == "tesseract":
                return _ocr_with_tesseract(path, lang)
            if name == "paddle":
                return _ocr_with_paddle(path, lang)
            raise ValueError(f"未知 OCR 后端: {name}")
        except MissingDependencyError as exc:
            errors.append(str(exc))
            logger.warning(f"OCR 后端 {name} 不可用: {exc}")

    raise MissingDependencyError(
        "OCR 后端", "pip install pytesseract  # 或 pip install paddleocr", "; ".join(errors)
    )


def ocr_pdf(
    pdf_path: str, lang: str = "chi_sim+eng", max_pages: Optional[int] = None, dpi: int = 200
) -> str:
    """对扫描版 PDF 做 OCR。

    需要先把 PDF 页渲染成图片，因此依赖 ``pdf2image`` + ``poppler``
    （系统级），或 PyMuPDF（``fitz``，纯 wheel 安装更省事）。
    """
    path = Path(pdf_path)

    # 优先 PyMuPDF：无需系统级 poppler，安装体验更好
    try:
        fitz = _require("fitz", "PyMuPDF", "pip install pymupdf")
    except MissingDependencyError:
        fitz = None

    if fitz is not None:
        document = fitz.open(str(path))
        limit = min(len(document), max_pages) if max_pages else len(document)
        texts: List[str] = []
        for idx in range(limit):
            pixmap = document[idx].get_pixmap(dpi=dpi)
            tmp_path = Path(os.path.join(os.path.dirname(str(path)), f"._ocr_page_{idx}.png"))
            try:
                pixmap.save(str(tmp_path))
                texts.append(ocr_image(str(tmp_path), lang=lang))
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        document.close()
        return "\n".join(texts)

    # 退路：pdf2image + poppler
    pdf2image = _require(
        "pdf2image",
        "pdf2image",
        "pip install pdf2image && (apt-get install -y poppler-utils || brew install poppler)",
        "也可改用 pip install pymupdf，无需系统级依赖",
    )
    try:
        images = pdf2image.convert_from_path(str(path), dpi=dpi)
    except Exception as exc:
        raise MissingDependencyError(
            "poppler",
            "apt-get install -y poppler-utils  # 或 brew install poppler",
            f"pdf2image 已安装但调用失败: {exc}",
        ) from exc

    limit = min(len(images), max_pages) if max_pages else len(images)
    texts = []
    for idx, image in enumerate(images[:limit]):
        tmp_path = Path(os.path.join(os.path.dirname(str(path)), f"._ocr_page_{idx}.png"))
        try:
            image.save(str(tmp_path), "PNG")
            texts.append(ocr_image(str(tmp_path), lang=lang))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    return "\n".join(texts)


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


def extract_document_text(
    path: str,
    ocr_enabled: bool = True,
    ocr_lang: str = "chi_sim+eng",
    scanned_threshold: int = SCANNED_PAGE_THRESHOLD,
    max_pages: Optional[int] = None,
    encoding: str = "utf-8",
) -> ExtractedDocument:
    """把任意受支持格式的文档提取为纯文本。

    Args:
        path: 文档路径
        ocr_enabled: 判定为扫描件时是否启用 OCR
        ocr_lang: OCR 语言参数
        scanned_threshold: 平均每页字符数低于该值即判定为扫描件
        max_pages: 最多处理多少页（长文档截断用）
        encoding: 纯文本文件的首选编码

    Raises:
        FileNotFoundError: 路径不存在
        ValueError: 扩展名不受支持
        MissingDependencyError: 缺少可选依赖（附安装命令）
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文档不存在: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的文档格式: {suffix or '(无扩展名)'}，"
            f"支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if suffix in (".txt", ".md", ".json", ".csv"):
        return _extract_plain_text(file_path, encoding=encoding)
    if suffix == ".pdf":
        return _extract_pdf(file_path, ocr_enabled, ocr_lang, scanned_threshold, max_pages)
    if suffix == ".docx":
        return _extract_docx(file_path)
    if suffix in (".xlsx", ".xlsm"):
        return _extract_xlsx(file_path)

    # 图片
    text = ocr_image(str(file_path), lang=ocr_lang) if ocr_enabled else ""
    doc = ExtractedDocument(text=text, source=str(file_path), method="ocr", pages=1)
    if not ocr_enabled:
        doc.warnings.append("已禁用 OCR（ocr_enabled=False），图片未提取文本")
    return doc


def supported_formats() -> Dict[str, str]:
    """返回支持的扩展名与处理方式（供 UI / 文档生成使用）"""
    return dict(SUPPORTED_EXTENSIONS)


# ---------------------------------------------------------------------------
# 注册为工具（供 Agent 通过 get_tools() / call_tool() 使用）
# ---------------------------------------------------------------------------


@tool(
    name="extract_document_text",
    description=(
        "把 PDF / Word / Excel / 图片 / 文本文件提取为纯文本。"
        "PDF 优先取文本层，判定为扫描件时自动转 OCR"
    ),
    category="document",
    parameters={
        "path": "文档路径",
        "ocr_enabled": "是否启用 OCR（默认 True）",
        "max_pages": "最多处理的页数（默认全部）",
    },
)
def load_document_text(
    path: str, ocr_enabled: bool = True, max_pages: Optional[int] = None
) -> Dict[str, Any]:
    """工具化封装：返回结构化结果（含告警与提取方式）"""
    doc = extract_document_text(path, ocr_enabled=ocr_enabled, max_pages=max_pages)
    result = doc.to_dict()
    result["text"] = doc.text
    return result
