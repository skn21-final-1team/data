from __future__ import annotations

import re


class MarkdownPreprocessor:
    @staticmethod
    def strip_whitespace(text: str) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    @staticmethod
    def normalize_blank_lines(text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    @staticmethod
    def normalize_headings(text: str) -> str:
        return re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", text, flags=re.MULTILINE)

    @staticmethod
    def remove_html_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def remove_reference_markers(text: str) -> str:
        return re.sub(r"\[(\d+|edit)\]", "", text)

    @staticmethod
    def normalize_list_markers(text: str) -> str:
        return re.sub(r"^(\s*)[*+]\s", r"\1- ", text, flags=re.MULTILINE)

    @staticmethod
    def repair_code_fences(text: str) -> str:
        if len(re.findall(r"^```", text, flags=re.MULTILINE)) % 2 != 0:
            text += "\n```"
        return text

    @staticmethod
    def normalize_table_separators(text: str) -> str:
        return re.sub(
            r"^\|[\s\-:]+\|$",
            lambda m: re.sub(r"[^\-|:]", "-", m.group()),
            text,
            flags=re.MULTILINE,
        )

    @classmethod
    def run(cls, text: str) -> str:
        text = cls.strip_whitespace(text)
        text = cls.remove_html_tags(text)
        text = cls.remove_reference_markers(text)
        text = cls.normalize_headings(text)
        text = cls.normalize_list_markers(text)
        text = cls.repair_code_fences(text)
        text = cls.normalize_table_separators(text)
        text = cls.normalize_blank_lines(text)
        return text
