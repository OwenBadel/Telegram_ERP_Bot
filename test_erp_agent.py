"""
Suite de Pruebas Automatizadas (TDD) para el Telegram ERP Agent.
Verifica la integridad de la base de datos, el servicio ERP, el Kardex, el motor NLU y la generación de reportes PDF.
"""

import sys
import unittest
from pathlib import Path

# Configurar path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

from core.database import DatabaseManager
from core.erp_service import ERPService
from core.models import MovementType
from core.nlu_engine import NLUEngine
from core.pdf_exporter import ERPPDFExporter


class TestTelegramERPAgent(unittest.TestCase):
    def setUp(self):
        """Inicializa una base de datos en memoria para pruebas aisladas y reproducibles."""
        self.db = DatabaseManager(db_path=":memory:")
        self.erp = ERPService(db_manager=self.db)
        self.nlu = NLUEngine()
        self.pdf_exporter = ERPPDFExporter(reports_dir=str(project_dir / "reports"))

    def test_database_seed_and_summary(self):
        """Verifica que la base de datos se inicialice con el catálogo sembrado y KPIs correctos."""
        summary = self.erp.get_summary()
        self.assertGreaterEqual(summary.total_skus, 9, "Debe haber al menos 9 SKUs sembrados")
        self.assertGreater(summary.total_units, 50, "Debe haber existencias físicas iniciales")
        self.assertGreater(summary.total_valuation_cost, 1000.0, "La valoración a costo debe ser positiva")
        self.assertGreater(summary.low_stock_count, 0, "Debe haber al menos 1 producto con alerta de stock")

    def test_product_search_and_sku_lookup(self):
        """Verifica la consulta exacta de SKU y la búsqueda parcial por texto."""
        # Consulta exacta
        p = self.erp.get_product_by_sku("LAP-001")
        self.assertIsNotNone(p)
        self.assertEqual(p.sku, "LAP-001")
        self.assertIn("ThinkPad", p.name)

        # Búsqueda parcial insensible a mayúsculas
        results = self.erp.search_products("dell")
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(any("Dell" in r.name for r in results))

    def test_kardex_in_movement(self):
        """Verifica que una entrada aumente el stock y genere el registro en Kardex."""
        sku = "LAP-001"
        p_initial = self.erp.get_product_by_sku(sku)
        initial_stock = p_initial.stock_current

        ok, msg, movement = self.erp.register_movement(
            sku=sku,
            movement_type=MovementType.ENTRADA_COMPRA,
            quantity=10,
            user_name="Ing. Owen Badel Hooker",
            reference_doc="FACT-001",
            notes="Recepción de compra lote 1"
        )
        self.assertTrue(ok)
        self.assertIn("Movimiento exitoso", msg)

        # Verificar nuevo stock
        p_updated = self.erp.get_product_by_sku(sku)
        self.assertEqual(p_updated.stock_current, initial_stock + 10)

        # Verificar registro Kardex
        kardex = self.erp.get_kardex(limit=1, sku=sku)
        self.assertEqual(len(kardex), 1)
        self.assertEqual(kardex[0].quantity, 10)
        self.assertEqual(kardex[0].previous_stock, initial_stock)
        self.assertEqual(kardex[0].new_stock, initial_stock + 10)
        self.assertEqual(kardex[0].reference_doc, "FACT-001")

    def test_kardex_out_movement_and_insufficient_stock(self):
        """Verifica que una salida disminuya el stock y que rechace salidas superiores al disponible."""
        sku = "MON-001"
        p = self.erp.get_product_by_sku(sku)
        avail = p.stock_current

        # 1. Salida válida
        ok, msg, _ = self.erp.register_movement(
            sku=sku,
            movement_type=MovementType.SALIDA_VENTA,
            quantity=2,
            user_name="Operador Bodega",
            reference_doc="ORD-101"
        )
        self.assertTrue(ok)
        self.assertEqual(self.erp.get_product_by_sku(sku).stock_current, avail - 2)

        # 2. Salida que excede el stock disponible
        ok_fail, msg_fail, _ = self.erp.register_movement(
            sku=sku,
            movement_type=MovementType.SALIDA_VENTA,
            quantity=avail + 100,
            user_name="Operador Bodega"
        )
        self.assertFalse(ok_fail)
        self.assertIn("insuficiente", msg_fail.lower())

    def test_low_stock_detection(self):
        """Verifica que los productos con stock_current <= stock_min se identifiquen en alertas."""
        low_items = self.erp.get_low_stock_products()
        self.assertGreater(len(low_items), 0)
        for item in low_items:
            self.assertLessEqual(item.stock_current, item.stock_min)

    def test_nlu_engine_intents(self):
        """Verifica que el motor NLU clasifique correctamente los mensajes conversacionales."""
        # Intención de entrada
        parsed_in = self.nlu.parse_intent("entrada 12 unidades de LAP-001 por factura FAC-90")
        self.assertEqual(parsed_in["intent"], "REGISTRO_MOVIMIENTO")
        self.assertEqual(parsed_in["movement_type"], MovementType.ENTRADA_COMPRA)
        self.assertEqual(parsed_in["quantity"], 12)
        self.assertEqual(parsed_in["sku"], "LAP-001")
        self.assertEqual(parsed_in["reference"], "FAC-90")

        # Intención de salida
        parsed_out = self.nlu.parse_intent("salida 3 de MON-002 orden ORD-40")
        self.assertEqual(parsed_out["intent"], "REGISTRO_MOVIMIENTO")
        self.assertEqual(parsed_out["movement_type"], MovementType.SALIDA_VENTA)
        self.assertEqual(parsed_out["quantity"], 3)
        self.assertEqual(parsed_out["sku"], "MON-002")

        # Intención de alertas
        parsed_alert = self.nlu.parse_intent("cuales productos tienen bajo stock")
        self.assertEqual(parsed_alert["intent"], "ALERTAS_STOCK")

        # Intención de reporte PDF
        parsed_pdf = self.nlu.parse_intent("descargar reporte en pdf")
        self.assertEqual(parsed_pdf["intent"], "REPORTE_PDF")

        # Consulta directa
        parsed_stock = self.nlu.parse_intent("stock de thinkpad")
        self.assertEqual(parsed_stock["intent"], "CONSULTA_STOCK")

    def test_pdf_report_generation(self):
        """Verifica que ReportLab genere un PDF válido y accesible en disco."""
        summary = self.erp.get_summary()
        products = self.erp.search_products("")
        pdf_path = self.pdf_exporter.generate_inventory_report(
            summary=summary,
            products=products,
            company_name="Empresa Prueba S.A.S.",
            generated_by="Ing. Owen Badel Hooker"
        )
        self.assertTrue(Path(pdf_path).exists(), "El archivo PDF debe crearse físicamente")
        self.assertGreater(Path(pdf_path).stat().st_size, 1000, "El archivo PDF debe tener contenido binario")


if __name__ == "__main__":
    unittest.main()
