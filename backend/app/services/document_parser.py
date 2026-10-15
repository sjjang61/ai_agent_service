"""
파일 타입별 텍스트 추출
"""

from typing import BinaryIO
import PyPDF2


class DocumentParser:
    """파일 타입별 텍스트 추출"""

    @staticmethod
    def parse(file: BinaryIO, file_type: str) -> str:
        """파일 → 텍스트 변환"""
        if file_type in ("txt", "md"):
            return DocumentParser._parse_text(file)

        elif file_type == "pdf":
            return DocumentParser._parse_pdf(file)

        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    @staticmethod
    def _parse_text(file: BinaryIO) -> str:
        """텍스트 파일 파싱"""
        return file.read().decode("utf-8")

    @staticmethod
    def _parse_pdf(file: BinaryIO) -> str:
        """PDF 파일 파싱"""
        reader = PyPDF2.PdfReader(file)
        pages = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                pages.append(f"[Page {page_num + 1}]\n{text}")

        return "\n\n".join(pages)
