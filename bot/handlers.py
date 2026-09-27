"""
Manejadores de Comandos, Mensajes y Callbacks para el Bot de Telegram.
"""

import os
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from core.erp_service import ERPService
from core.nlu_engine import NLUEngine
from core.pdf_exporter import ERPPDFExporter
from core.models import MovementType
from .keyboards import get_main_menu_keyboard, get_product_action_keyboard, get_back_to_menu_keyboard


COMPANY_NAME = os.getenv("COMPANY_NAME", "Industrias Badel & Asociados S.A.S.")


def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


class BotController:
    def __init__(self, erp_service: ERPService = None):
        self.erp = erp_service or ERPService()
        self.nlu = NLUEngine()
        self.pdf_exporter = ERPPDFExporter()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el panel de bienvenida con KPIs y menú interactivo."""
        user = update.effective_user
        summary = self.erp.get_summary()

        text = (
            f"👋 *Bienvenido, {user.first_name}*\n"
            f"🏢 *{COMPANY_NAME}*\n"
            f"🤖 *Agente ERP & Control de Inventarios*\n\n"
            f"📊 *Estado Actual del Almacén:*\n"
            f"• *Catálogo Total:* `{summary.total_skus}` SKUs registrados\n"
            f"• *Existencias Físicas:* `{summary.total_units}` unidades\n"
            f"• *Valoración a Costo:* `{format_currency(summary.total_valuation_cost)}`\n"
            f"• *Valoración a Venta:* `{format_currency(summary.total_valuation_sale)}`\n"
            f"• *Alertas de Stock Bajo:* `{summary.low_stock_count}` productos en umbral\n\n"
            f"Seleccione una acción rápida o escriba su solicitud en lenguaje natural:"
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra la guía completa de comandos y sintaxis conversacional."""
        help_text = (
            "📖 *Guía de Operación del Agente ERP Telegram*\n\n"
            "🔹 *Comandos Directos:*\n"
            "• `/stock <sku o nombre>` : Consulta existencias y precios\n"
            "• `/entrada <sku> <cant> [doc]` : Registra ingreso de mercancía\n"
            "• `/salida <sku> <cant> [doc]` : Registra despacho o venta\n"
            "• `/alertas` : Lista productos con stock crítico o bajo\n"
            "• `/kardex [sku]` : Consulta los últimos movimientos contables\n"
            "• `/reporte` : Genera y envía el reporte PDF ejecutivo\n\n"
            "🔹 *Lenguaje Natural Inteligente:*\n"
            "Puedes escribir directamente mensajes como:\n"
            "• _¿Cuánto stock queda de laptops?_\n"
            "• _Entrada 15 unidades de LAP-001 por factura F-990_\n"
            "• _Salida 2 de MEM-001 orden V-401_\n"
            "• _Generar balance en pdf_\n"
            "• _Qué productos tienen bajo stock_"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def stock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Consulta existencias de un producto específico o busca en catálogo."""
        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text(
                "ℹ️ Indique el SKU o término a buscar. Ejemplo: `/stock LAP-001` o `/stock dell`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await self._execute_stock_search(update, query)

    async def entrada_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Registra una entrada de inventario por comando /entrada."""
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ *Uso incorrecto.* Formato: `/entrada <SKU> <CANTIDAD> [REFERENCIA]`\n"
                "Ejemplo: `/entrada LAP-001 10 Factura-8041`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        sku = context.args[0].upper()
        try:
            qty = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ La cantidad debe ser un número entero.")
            return

        ref = " ".join(context.args[2:]) if len(context.args) > 2 else "Recepción Manual"
        user_name = update.effective_user.full_name

        success, msg, movement = self.erp.register_movement(
            sku=sku,
            movement_type=MovementType.ENTRADA_COMPRA,
            quantity=qty,
            user_name=user_name,
            reference_doc=ref,
            notes="Registrado vía comando Telegram"
        )
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {msg}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_product_action_keyboard(sku) if success else None
        )

    async def salida_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Registra una salida de inventario por comando /salida."""
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ *Uso incorrecto.* Formato: `/salida <SKU> <CANTIDAD> [REFERENCIA]`\n"
                "Ejemplo: `/salida MON-001 2 Despacho-550`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        sku = context.args[0].upper()
        try:
            qty = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ La cantidad debe ser un número entero.")
            return

        ref = " ".join(context.args[2:]) if len(context.args) > 2 else "Despacho Manual"
        user_name = update.effective_user.full_name

        success, msg, movement = self.erp.register_movement(
            sku=sku,
            movement_type=MovementType.SALIDA_VENTA,
            quantity=qty,
            user_name=user_name,
            reference_doc=ref,
            notes="Registrado vía comando Telegram"
        )
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {msg}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_product_action_keyboard(sku) if success else None
        )

    async def alertas_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra los productos en estado de alerta o stock crítico."""
        low_items = self.erp.get_low_stock_products()
        if not low_items:
            await update.message.reply_text("✅ *Excelente noticia:* Todos los productos tienen existencias por encima del stock mínimo.", parse_mode=ParseMode.MARKDOWN)
            return

        lines = [f"⚠️ *Alerta: {len(low_items)} Productos en Stock Bajo o Crítico*\n"]
        for p in low_items:
            diff = p.stock_min - p.stock_current
            reorder_text = f"Faltan {diff} un. para el mínimo" if diff > 0 else "En nivel exacto de alerta"
            lines.append(
                f"• *{p.sku}* — {p.name}\n"
                f"  Stock: `{p.stock_current}` un. | Mínimo: `{p.stock_min}` un. ({reorder_text})\n"
                f"  Ubicación: `{p.location}` | Costo Reposición: `{format_currency(p.cost_price)}`\n"
            )

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def kardex_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra los últimos movimientos en el libro Kardex."""
        sku = context.args[0].upper() if context.args else None
        movements = self.erp.get_kardex(limit=10, sku=sku)

        if not movements:
            await update.message.reply_text(f"ℹ️ No hay movimientos registrados{' para ' + sku if sku else ''}.")
            return

        title = f"📑 *Libro Kardex: Últimos Movimientos{' de ' + sku if sku else ' Globales'}*\n"
        lines = [title]
        for m in movements:
            icon = "🟢" if "ENTRADA" in m.movement_type.value else "🔴"
            sign = "+" if "ENTRADA" in m.movement_type.value else "-"
            date_str = m.created_at.strftime("%d/%m %H:%M") if m.created_at else "N/A"
            lines.append(
                f"{icon} `{date_str}` | *{m.product_sku}*\n"
                f"  {sign}{m.quantity} un. ({m.previous_stock} ➔ {m.new_stock}) | {m.movement_type.value}\n"
                f"  Doc: `{m.reference_doc}` • Por: `{m.user_name}`\n"
            )

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def reporte_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Genera el reporte ejecutivo en PDF y lo despacha al chat."""
        msg = await update.message.reply_text("⏳ *Generando informe ejecutivo de inventario en PDF...*", parse_mode=ParseMode.MARKDOWN)

        summary = self.erp.get_summary()
        products = self.erp.search_products("")
        user_name = update.effective_user.full_name

        pdf_path = self.pdf_exporter.generate_inventory_report(
            summary=summary,
            products=products,
            company_name=COMPANY_NAME,
            generated_by=f"{user_name} (Telegram ERP)"
        )

        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=Path(pdf_path).name,
                caption=(
                    f"📄 *Informe Ejecutivo de Inventario*\n"
                    f"🏢 {COMPANY_NAME}\n"
                    f"• {summary.total_skus} SKUs | {summary.total_units} Unidades\n"
                    f"• Valoración: {format_currency(summary.total_valuation_cost)}"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        await msg.delete()

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa las interacciones con los botones en línea del menú."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "menu_main":
            summary = self.erp.get_summary()
            text = (
                f"🏢 *{COMPANY_NAME}* • Panel de Control\n\n"
                f"• *SKUs Activos:* `{summary.total_skus}` | *Unidades:* `{summary.total_units}`\n"
                f"• *Valor Costo:* `{format_currency(summary.total_valuation_cost)}`\n"
                f"• *Alertas:* `{summary.low_stock_count}` productos en stock bajo"
            )
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu_keyboard())

        elif data == "menu_catalog":
            products = self.erp.search_products("")[:12]
            lines = ["📦 *Catálogo de Existencias (Resumen):*\n"]
            for p in products:
                status_icon = "⚠️" if p.is_low_stock else "✅"
                lines.append(f"{status_icon} *{p.sku}* | `{p.stock_current} un.` — {p.name} ({format_currency(p.sale_price)})")
            lines.append("\n_Para ver detalle, escribe /stock seguido del código SKU._")
            await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_menu_keyboard())

        elif data == "menu_alerts":
            low_items = self.erp.get_low_stock_products()
            if not low_items:
                await query.edit_message_text("✅ *Todo en orden:* No hay productos por debajo del stock mínimo.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_menu_keyboard())
            else:
                lines = [f"⚠️ *{len(low_items)} Productos en Alerta de Stock:*\n"]
                for p in low_items:
                    lines.append(f"• *{p.sku}* — {p.name}\n  Stock: `{p.stock_current}` / Mín: `{p.stock_min}` (Ubicación: {p.location})")
                await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_menu_keyboard())

        elif data == "menu_kardex":
            movements = self.erp.get_kardex(limit=8)
            lines = ["📑 *Últimos 8 Movimientos en Kardex:*\n"]
            for m in movements:
                sign = "+" if "ENTRADA" in m.movement_type.value else "-"
                lines.append(f"• `{m.product_sku}`: {sign}{m.quantity} un. ({m.previous_stock}➔{m.new_stock}) [{m.movement_type.value[:7]}]")
            await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_menu_keyboard())

        elif data == "menu_pdf":
            await query.message.reply_text("⏳ *Generando informe ejecutivo en PDF...*", parse_mode=ParseMode.MARKDOWN)
            summary = self.erp.get_summary()
            products = self.erp.search_products("")
            pdf_path = self.pdf_exporter.generate_inventory_report(
                summary=summary,
                products=products,
                company_name=COMPANY_NAME,
                generated_by="Telegram Agent (Botón)"
            )
            with open(pdf_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=Path(pdf_path).name,
                    caption=f"📄 *Reporte de Inventario Emitido Exitosamente*",
                    parse_mode=ParseMode.MARKDOWN
                )

        elif data == "menu_help":
            help_text = (
                "💡 *¿Cómo interactuar con el Agente?*\n\n"
                "1. *Botones Rápidos:* Presiona los botones del menú para consultas al instante.\n"
                "2. *Comandos:* Usa `/stock`, `/entrada`, `/salida`, `/alertas`, `/reporte`.\n"
                "3. *Lenguaje Natural:* Escribe consultas como _'stock de thinkpad'_ o _'entrada 5 de LAP-001'_."
            )
            await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_menu_keyboard())

        elif data.startswith("act_in_"):
            sku = data.replace("act_in_", "")
            await query.message.reply_text(f"ℹ️ Para ingresar mercancía a *{sku}*, usa: `/entrada {sku} <cantidad> [factura]`", parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("act_out_"):
            sku = data.replace("act_out_", "")
            await query.message.reply_text(f"ℹ️ Para despachar mercancía de *{sku}*, usa: `/salida {sku} <cantidad> [orden]`", parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("act_kardex_"):
            sku = data.replace("act_kardex_", "")
            movements = self.erp.get_kardex(limit=5, sku=sku)
            if not movements:
                await query.message.reply_text(f"ℹ️ Sin movimientos registrados para {sku}.")
            else:
                lines = [f"📑 *Kardex Reciente de {sku}:*\n"]
                for m in movements:
                    sign = "+" if "ENTRADA" in m.movement_type.value else "-"
                    lines.append(f"• `{m.created_at.strftime('%d/%m') if m.created_at else ''}`: {sign}{m.quantity} un. ({m.movement_type.value}) Doc: {m.reference_doc}")
                await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesa mensajes de texto arbitrarios mediante el motor NLU."""
        text = update.message.text
        if not text:
            return

        parsed = self.nlu.parse_intent(text)
        intent = parsed.get("intent")

        if intent == "REPORTE_PDF":
            await self.reporte_command(update, context)

        elif intent == "ALERTAS_STOCK":
            await self.alertas_command(update, context)

        elif intent == "AYUDA":
            await self.help_command(update, context)

        elif intent == "CONSULTA_STOCK":
            query = parsed.get("query", "")
            await self._execute_stock_search(update, query)

        elif intent == "REGISTRO_MOVIMIENTO":
            sku = parsed["sku"]
            qty = parsed["quantity"]
            m_type = parsed["movement_type"]
            ref = parsed.get("reference", "NLU Auto")
            user_name = update.effective_user.full_name

            success, msg, m = self.erp.register_movement(
                sku=sku,
                movement_type=m_type,
                quantity=qty,
                user_name=user_name,
                reference_doc=ref,
                notes="Interpretado por NLU Telegram"
            )
            await update.message.reply_text(
                f"{'✅' if success else '❌'} {msg}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_product_action_keyboard(sku) if success else None
            )

        else:
            await update.message.reply_text(
                "🤔 No entendí con certeza tu mensaje. Intenta usar un comando como `/stock` o presiona un botón del menú:",
                reply_markup=get_main_menu_keyboard()
            )

    async def _execute_stock_search(self, update: Update, query: str):
        # 1. Buscar coincidencia exacta por SKU
        exact = self.erp.get_product_by_sku(query)
        if exact:
            status_icon = "⚠️ *STOCK BAJO / REORDEN*" if exact.is_low_stock else "✅ *EXISTENCIAS ÓPTIMAS*"
            text = (
                f"📦 *Ficha de Producto: {exact.sku}*\n"
                f"• *Descripción:* {exact.name}\n"
                f"• *Categoría:* {exact.category}\n"
                f"• *Ubicación Física:* `{exact.location}`\n"
                f"• *Stock Disponible:* `{exact.stock_current}` unidades\n"
                f"• *Stock Mínimo:* `{exact.stock_min}` unidades\n"
                f"• *Precio Costo:* `{format_currency(exact.cost_price)}`\n"
                f"• *Precio Venta:* `{format_currency(exact.sale_price)}`\n"
                f"• *Valoración Stock:* `{format_currency(exact.total_cost_value)}`\n\n"
                f"Estado: {status_icon}"
            )
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_product_action_keyboard(exact.sku)
            )
            return

        # 2. Búsqueda por coincidencia
        results = self.erp.search_products(query)
        if not results:
            await update.message.reply_text(
                f"🔍 No se encontraron productos coincidentes con *'{query}'* en el catálogo.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        lines = [f"🔍 *Resultados de Búsqueda para '{query}' ({len(results)} encontrados):*\n"]
        for p in results[:8]:
            alert = "⚠️" if p.is_low_stock else "✅"
            lines.append(f"{alert} *{p.sku}* | `{p.stock_current} un.` — {p.name} ({format_currency(p.sale_price)})")

        lines.append("\n_Para consultar uno en detalle, escribe: /stock <SKU>_")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
