import contextvars
from typing import Optional

# ContextVar to store the current language for the request lifecycle
current_language = contextvars.ContextVar("current_language", default="vi")

def get_language() -> str:
    return current_language.get()

def set_language(lang: str):
    current_language.set(lang)

def get_dir() -> str:
    """Return 'rtl' if current language is right-to-left, else 'ltr'."""
    lang = get_language().split("-")[0]
    return "rtl" if lang in ["ar", "he", "fa", "ur"] else "ltr"

def get_report_labels() -> dict:
    """Return localized labels for PDF reports based on current language."""
    lang = get_language().split("-")[0]
    labels = {
        "vi": {"page": "Trang", "report": "Báo cáo", "generated_at": "Tạo lúc"},
        "en": {"page": "Page", "report": "Report", "generated_at": "Generated at"},
        "ko": {"page": "페이지", "report": "보고서", "generated_at": "생성 일시"},
        "ar": {"page": "صفحة", "report": "تقرير", "generated_at": "تم إنشاؤه في"},
    }
    return labels.get(lang, labels["en"])
