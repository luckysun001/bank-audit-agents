"""文档加载层测试（PDF/Word/Excel/图片/文本 -> 纯文本 + OCR）。

只覆盖**不依赖可选库**的路径：纯文本、扩展名校验、缺失依赖报错。
真正调用 pypdf / python-docx / OCR 的路径留给安装了对应依赖的环境
（CI 未装这些可选依赖时也能全绿）。
"""

import pytest

from bank_audit_agents.tools.document_loader import (
    SUPPORTED_EXTENSIONS,
    ExtractedDocument,
    MissingDependencyError,
    extract_document_text,
    ocr_image,
    supported_formats,
)


def test_extract_plain_text(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("贷款金额 500 万元，期限 12 个月。", encoding="utf-8")

    doc = extract_document_text(str(path))

    assert isinstance(doc, ExtractedDocument)
    assert doc.method == "plain_text"
    assert "500" in doc.text
    assert doc.pages == 1
    assert not doc.warnings


def test_extract_markdown_and_json(tmp_path):
    (tmp_path / "a.md").write_text("# 标题\n内容", encoding="utf-8")
    (tmp_path / "b.json").write_text('{"k": 1}', encoding="utf-8")

    assert extract_document_text(str(tmp_path / "a.md")).text.startswith("#")
    assert '"k": 1' in extract_document_text(str(tmp_path / "b.json")).text


def test_gbk_text_is_decoded(tmp_path):
    """审计现场常遇到 GBK 编码的历史文件，不能因为编码问题读成乱码"""
    path = tmp_path / "gbk.txt"
    path.write_bytes("借款人：张三".encode("gbk"))

    doc = extract_document_text(str(path), encoding="utf-8")
    assert "张三" in doc.text


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        extract_document_text("./definitely-not-exists.pdf")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01")

    with pytest.raises(ValueError, match="不支持的文档格式"):
        extract_document_text(str(path))


def test_ocr_disabled_on_image_leaves_warning(tmp_path):
    """图片 + 关闭 OCR：不应静默返回空，而要留下告警"""
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")

    doc = extract_document_text(str(path), ocr_enabled=False)

    assert doc.is_empty
    assert any("OCR" in w for w in doc.warnings)


def test_ocr_image_reports_missing_dependency(tmp_path):
    """未安装 OCR 后端时，必须给出可执行的安装命令而非空字符串"""
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")

    try:
        import pytesseract  # noqa: F401
    except ImportError:
        with pytest.raises(MissingDependencyError) as exc_info:
            ocr_image(str(path))
        assert "pip install" in str(exc_info.value)
        assert "pip install" in exc_info.value.install_cmd


def test_supported_formats_is_a_copy():
    """返回副本，避免调用方改动污染模块级常量"""
    formats = supported_formats()
    formats[".evil"] = "x"
    assert ".evil" not in SUPPORTED_EXTENSIONS
    assert ".pdf" in formats


def test_extracted_document_to_dict_contains_provenance():
    doc = ExtractedDocument(
        text="正文", source="/tmp/a.pdf", method="ocr", pages=3, warnings=["低置信度"]
    )
    data = doc.to_dict()

    assert data["method"] == "ocr"
    assert data["pages"] == 3
    assert data["char_count"] == len("正文")
    assert data["warnings"] == ["低置信度"]
    assert "text" not in data  # 正文可能很长，不进摘要字典
