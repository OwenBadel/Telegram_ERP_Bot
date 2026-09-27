"""
Constructores de Teclados en Línea (Inline Keyboards) para Telegram.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📦 Ver Catálogo Completo", callback_data="menu_catalog"),
            InlineKeyboardButton("⚠️ Alertas de Stock Bajo", callback_data="menu_alerts")
        ],
        [
            InlineKeyboardButton("📥 Registrar Entrada", callback_data="menu_help_in"),
            InlineKeyboardButton("📤 Registrar Salida", callback_data="menu_help_out")
        ],
        [
            InlineKeyboardButton("📑 Últimos Movimientos (Kardex)", callback_data="menu_kardex"),
            InlineKeyboardButton("📄 Descargar Reporte PDF", callback_data="menu_pdf")
        ],
        [
            InlineKeyboardButton("ℹ️ Guía y Ayuda NLU", callback_data="menu_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_product_action_keyboard(sku: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(f"📥 + Entrada {sku}", callback_data=f"act_in_{sku}"),
            InlineKeyboardButton(f"📤 - Salida {sku}", callback_data=f"act_out_{sku}")
        ],
        [
            InlineKeyboardButton(f"📋 Kardex {sku}", callback_data=f"act_kardex_{sku}"),
            InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
