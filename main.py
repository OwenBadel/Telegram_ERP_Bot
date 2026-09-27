"""
Punto de Entrada Principal — Telegram ERP Agent.
Soporta Modo Telegram Live (Polling) y Modo Simulador Interactivo CLI.

Titular y Autor: Ingeniero Owen Badel Hooker
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno locales y de la raíz
PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

# Asegurar UTF-8 en consola de Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.erp_service import ERPService
from core.pdf_exporter import ERPPDFExporter
from core.nlu_engine import NLUEngine
from core.models import MovementType


def run_telegram_live():
    """Inicia el bot real de Telegram utilizando python-telegram-bot en modo Polling."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or "tu_token" in token.lower() or len(token) < 20:
        print("\n❌ [ERROR] No se ha configurado un TELEGRAM_BOT_TOKEN válido en el archivo .env")
        print("💡 Para obtener un token:")
        print("   1. Abre Telegram y busca @BotFather")
        print("   2. Escribe /newbot y sigue las instrucciones")
        print("   3. Pega el token generado en projects/PROJ_011_Telegram_ERP_Bot/.env")
        print("\n🔄 Iniciando automáticamente el Modo Simulador CLI para pruebas locales...")
        run_interactive_simulator()
        return

    try:
        from telegram.ext import (
            ApplicationBuilder,
            CommandHandler,
            CallbackQueryHandler,
            MessageHandler,
            filters
        )
        from bot.handlers import BotController

        controller = BotController()
        app = ApplicationBuilder().token(token).build()

        # Registro de Handlers de Comandos
        app.add_handler(CommandHandler("start", controller.start))
        app.add_handler(CommandHandler("help", controller.help_command))
        app.add_handler(CommandHandler("stock", controller.stock_command))
        app.add_handler(CommandHandler("entrada", controller.entrada_command))
        app.add_handler(CommandHandler("salida", controller.salida_command))
        app.add_handler(CommandHandler("alertas", controller.alertas_command))
        app.add_handler(CommandHandler("kardex", controller.kardex_command))
        app.add_handler(CommandHandler("reporte", controller.reporte_command))

        # Registro de Callback Queries (Botones Inline)
        app.add_handler(CallbackQueryHandler(controller.handle_callback_query))

        # Registro de Mensajes de Texto Libre (NLU)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), controller.handle_message))

        company = os.getenv("COMPANY_NAME", "Industrias Badel & Asociados S.A.S.")
        print("=" * 70)
        print("🤖 AGENTE ERP TELEGRAM — EN LÍNEA")
        print(f"🏢 Empresa: {company}")
        print("👨‍💻 Autor y Titular: Ingeniero Owen Badel Hooker")
        print("📡 Modo: Polling Activo en Telegram")
        print("=" * 70)
        print("Presiona Ctrl+C para detener el servicio.\n")

        app.run_polling()

    except Exception as e:
        print(f"\n❌ Error al conectar con Telegram: {e}")
        print("Iniciando Modo Simulador para validar la funcionalidad...")
        run_interactive_simulator()


def run_interactive_simulator():
    """Modo Simulador Interactivo por Consola para validar todas las capacidades del ERP sin token."""
    erp = ERPService()
    nlu = NLUEngine()
    pdf_gen = ERPPDFExporter()
    company = os.getenv("COMPANY_NAME", "Industrias Badel & Asociados S.A.S.")

    print("\n" + "=" * 75)
    print("🎮 SIMULADOR DE AGENTE TELEGRAM ERP (MODO PRUEBAS Y VALIDACIÓN)")
    print(f"🏢 Empresa: {company}")
    print("👨‍💻 Autor y Titular: Ingeniero Owen Badel Hooker")
    print("=" * 75)
    print("Simula los mensajes y comandos que un operador o gerente enviaría desde Telegram.")
    print("Comandos disponibles:")
    print("  /start            - Ver panel principal y KPIs")
    print("  /stock <sku>      - Consultar producto")
    print("  /entrada <sku> <cant> [doc] - Ingresar stock")
    print("  /salida <sku> <cant> [doc]  - Despachar stock")
    print("  /alertas          - Ver productos con bajo stock")
    print("  /kardex [sku]     - Ver historial de movimientos")
    print("  /reporte          - Generar informe ejecutivo en PDF")
    print("  /salir            - Salir del simulador")
    print("O simplemente escribe en lenguaje natural: 'stock de laptops' o 'entrada 10 MEM-001'")
    print("-" * 75)

    summary = erp.get_summary()
    print(f"📦 Inventario Inicial: {summary.total_skus} SKUs | {summary.total_units} Unidades | Valor Costo: ${summary.total_valuation_cost:,.2f} | {summary.low_stock_count} Alertas\n")

    while True:
        try:
            line = input("👤 Usuario en Telegram > ").strip()
            if not line:
                continue

            if line.lower() in ["/salir", "exit", "quit"]:
                print("👋 Cerrando simulador ERP. ¡Hasta pronto!")
                break

            # 1. Comandos directos
            if line.startswith("/start"):
                s = erp.get_summary()
                print("\n🤖 [Telegram Bot]:")
                print(f"👋 Bienvenido al Agente ERP de {company}!")
                print(f"• SKUs en Catálogo: {s.total_skus}")
                print(f"• Existencias Totales: {s.total_units} unidades")
                print(f"• Valoración Total Costo: ${s.total_valuation_cost:,.2f}")
                print(f"• Valoración Total Venta: ${s.total_valuation_sale:,.2f}")
                print(f"• Alertas de Stock: {s.low_stock_count} productos en umbral")
                print("\n[Botones Inline Simulados]: [📦 Catálogo] [⚠️ Alertas] [📥 Entrada] [📤 Salida] [📄 Reporte PDF]\n")

            elif line.startswith("/alertas"):
                low = erp.get_low_stock_products()
                print("\n🤖 [Telegram Bot]:")
                if not low:
                    print("✅ Todos los productos tienen existencias óptimas.")
                else:
                    print(f"⚠️ Alerta: {len(low)} productos en stock crítico:")
                    for p in low:
                        print(f"  • {p.sku} | {p.name}: {p.stock_current} un. (Mínimo: {p.stock_min}) - Ubicación: {p.location}")
                print()

            elif line.startswith("/stock"):
                parts = line.split(maxsplit=1)
                q = parts[1].strip() if len(parts) > 1 else ""
                if not q:
                    print("🤖 [Telegram Bot]: Indique SKU o término a buscar.")
                    continue
                p = erp.get_product_by_sku(q)
                print("\n🤖 [Telegram Bot]:")
                if p:
                    st = "⚠️ STOCK BAJO" if p.is_low_stock else "✅ ÓPTIMO"
                    print(f"📦 {p.sku} — {p.name}")
                    print(f"  • Stock: {p.stock_current} un. (Mín: {p.stock_min}) [{st}]")
                    print(f"  • Costo: ${p.cost_price:,.2f} | Venta: ${p.sale_price:,.2f} | Ubicación: {p.location}")
                else:
                    res = erp.search_products(q)
                    if not res:
                        print(f"🔍 No se encontraron productos coincidentes con '{q}'.")
                    else:
                        print(f"🔍 Encontrados {len(res)} productos:")
                        for item in res:
                            print(f"  • {item.sku}: {item.name} ({item.stock_current} un.)")
                print()

            elif line.startswith("/entrada"):
                parts = line.split()
                if len(parts) < 3:
                    print("🤖 [Telegram Bot]: Uso: /entrada <SKU> <CANTIDAD> [REFERENCIA]")
                    continue
                sku, qty_str = parts[1].upper(), parts[2]
                ref = " ".join(parts[3:]) if len(parts) > 3 else "Entrada Manual"
                try:
                    qty = int(qty_str)
                    ok, msg, m = erp.register_movement(sku, MovementType.ENTRADA_COMPRA, qty, "Usuario Simulador", ref)
                    print(f"\n🤖 [Telegram Bot]: {'✅' if ok else '❌'} {msg}\n")
                except ValueError:
                    print("❌ Cantidad inválida.")

            elif line.startswith("/salida"):
                parts = line.split()
                if len(parts) < 3:
                    print("🤖 [Telegram Bot]: Uso: /salida <SKU> <CANTIDAD> [REFERENCIA]")
                    continue
                sku, qty_str = parts[1].upper(), parts[2]
                ref = " ".join(parts[3:]) if len(parts) > 3 else "Despacho Manual"
                try:
                    qty = int(qty_str)
                    ok, msg, m = erp.register_movement(sku, MovementType.SALIDA_VENTA, qty, "Usuario Simulador", ref)
                    print(f"\n🤖 [Telegram Bot]: {'✅' if ok else '❌'} {msg}\n")
                except ValueError:
                    print("❌ Cantidad inválida.")

            elif line.startswith("/kardex"):
                parts = line.split()
                sku = parts[1].upper() if len(parts) > 1 else None
                movements = erp.get_kardex(limit=6, sku=sku)
                print("\n🤖 [Telegram Bot]:")
                print(f"📑 Últimos Movimientos Kardex{' de ' + sku if sku else ''}:")
                for m in movements:
                    sign = "+" if "ENTRADA" in m.movement_type.value else "-"
                    print(f"  • [{m.created_at.strftime('%H:%M:%S') if m.created_at else ''}] {m.product_sku}: {sign}{m.quantity} un. ({m.previous_stock}➔{m.new_stock}) Ref: {m.reference_doc}")
                print()

            elif line.startswith("/reporte"):
                print("\n🤖 [Telegram Bot]: ⏳ Generando informe ejecutivo en PDF con ReportLab...")
                s = erp.get_summary()
                prods = erp.search_products("")
                pdf_path = pdf_gen.generate_inventory_report(s, prods, company, "Usuario Simulador")
                print(f"✅ Documento PDF emitido con éxito:")
                print(f"📎 Archivo: {pdf_path}")
                print(f"📊 Incluye {len(prods)} SKUs y valoración total de ${s.total_valuation_cost:,.2f}\n")

            else:
                # 2. Procesamiento NLU para lenguaje natural
                parsed = nlu.parse_intent(line)
                intent = parsed.get("intent")
                if intent == "REPORTE_PDF":
                    s = erp.get_summary()
                    prods = erp.search_products("")
                    pdf_path = pdf_gen.generate_inventory_report(s, prods, company, "NLU Agent")
                    print(f"\n🤖 [Telegram Bot NLU]: 📄 He generado el informe PDF solicitado: {Path(pdf_path).name}\n")
                elif intent == "ALERTAS_STOCK":
                    low = erp.get_low_stock_products()
                    print(f"\n🤖 [Telegram Bot NLU]: ⚠️ Hay {len(low)} productos en alerta de stock.")
                    for p in low:
                        print(f"  • {p.sku}: {p.stock_current} un. (Mín: {p.stock_min})")
                    print()
                elif intent == "REGISTRO_MOVIMIENTO":
                    sku = parsed["sku"]
                    qty = parsed["quantity"]
                    m_type = parsed["movement_type"]
                    ref = parsed.get("reference", "NLU Auto")
                    ok, msg, m = erp.register_movement(sku, m_type, qty, "NLU Conversacional", ref)
                    print(f"\n🤖 [Telegram Bot NLU]: {'✅' if ok else '❌'} {msg}\n")
                elif intent == "CONSULTA_STOCK":
                    q = parsed.get("query", "")
                    p = erp.get_product_by_sku(q)
                    print("\n🤖 [Telegram Bot NLU]:")
                    if p:
                        print(f"📦 Encontrado {p.sku}: {p.name} con {p.stock_current} unidades disponibles.")
                    else:
                        res = erp.search_products(q)
                        if res:
                            print(f"🔍 Coincidencias encontradas ({len(res)}):")
                            for item in res[:5]:
                                print(f"  • {item.sku}: {item.name} ({item.stock_current} un.)")
                        else:
                            print(f"🔍 No encontré productos relacionados con '{q}'.")
                    print()
                else:
                    print("🤖 [Telegram Bot]: No reconocí la intención. Escribe /help para ver las opciones.")

        except KeyboardInterrupt:
            print("\n👋 Simulador detenido.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Telegram ERP Agent Runner")
    parser.add_argument("--sim", action="store_true", help="Forzar ejecución en Modo Simulador CLI")
    args = parser.parse_args()

    if args.sim:
        run_interactive_simulator()
    else:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token or "tu_token" in token.lower() or len(token) < 20:
            run_interactive_simulator()
        else:
            run_telegram_live()


if __name__ == "__main__":
    main()
