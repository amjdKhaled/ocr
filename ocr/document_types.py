"""
أنواع المستندات المدعومة وحقولها الافتراضية.

الأنواع الأساسية (تكليف/قرار/تعميم) هي محور الخدمة وبتشتغل على Templates
Laserfiche الحالية. الأنواع التجارية القديمة (فاتورة/إيصال/...) اتسابت
كخيار إضافي لمن يحتاجها، لكنها مفصولة بوضوح عن الأنواع الأساسية.
"""

from __future__ import annotations

from pydantic import BaseModel


class DocumentTypeConfig(BaseModel):
    label: str
    fields: list[str]


PRIMARY_DOCUMENT_TYPES: dict[str, DocumentTypeConfig] = {
    "takleef": DocumentTypeConfig(
        label="تكليف (Assignment)",
        fields=[
            "رقم التكليف",
            "تاريخ التكليف",
            "اسم المكلف",
            "تاريخ بداية التكليف",
            "تاريخ نهاية التكليف",
            "الموضوع",
            "صادر من",
        ],
    ),
    "qarar": DocumentTypeConfig(
        label="قرار (Decision)",
        fields=[
            "رقم القرار",
            "تاريخ القرار",
            "موضوع القرار",
            "الجهة المصدرة",
        ],
    ),
    "tamim": DocumentTypeConfig(
        label="تعميم (Circular)",
        fields=[
            "تاريخ صدور التعميم هجري",
            "موضوع التعميم",
            "جهة التعميم",
            "موجه الي",
            "نسخة الي",
        ],
    ),
}

# أنواع تجارية قديمة، اختيارية - مش الهدف الأساسي من الخدمة لكنها لسه مدعومة.
LEGACY_DOCUMENT_TYPES: dict[str, DocumentTypeConfig] = {
    "invoice": DocumentTypeConfig(
        label="فاتورة (Invoice)",
        fields=[
            "Invoice Number",
            "Invoice Date",
            "Customer Name",
            "Total Amount with VAT",
        ],
    ),
    "receipt": DocumentTypeConfig(
        label="إيصال (Receipt)",
        fields=[
            "Receipt Number",
            "Receipt Date",
            "Payer Name",
            "Amount Paid",
            "Payment Method",
        ],
    ),
    "purchase_order": DocumentTypeConfig(
        label="أمر شراء (Purchase Order)",
        fields=[
            "PO Number",
            "PO Date",
            "Supplier Name",
            "Total Amount",
            "Delivery Date",
        ],
    ),
    "delivery_note": DocumentTypeConfig(
        label="إذن تسليم (Delivery Note)",
        fields=[
            "Delivery Note Number",
            "Delivery Date",
            "Receiver Name",
            "Items Count",
        ],
    ),
    "quotation": DocumentTypeConfig(
        label="عرض أسعار (Price Quotation)",
        fields=[
            "Company Name",
            "Quotation Date",
            "Item List",
            "Total Amount",
        ],
    ),
}

DOCUMENT_TYPES: dict[str, DocumentTypeConfig] = {**PRIMARY_DOCUMENT_TYPES, **LEGACY_DOCUMENT_TYPES}

DEFAULT_DOC_TYPE = "takleef"


def get_fields_for_doc_type(doc_type: str) -> list[str]:
    """يرجّع حقول نوع المستند المطلوب، أو حقول النوع الافتراضي لو النوع مش معروف."""
    config = DOCUMENT_TYPES.get(doc_type, DOCUMENT_TYPES[DEFAULT_DOC_TYPE])
    return config.fields
