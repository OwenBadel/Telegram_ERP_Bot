"""
Generador de Reportes Ejecutivos en PDF para el ERP.
Basado en ReportLab Platypus con diseño corporativo y NumberedCanvas.
"""

import os
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.pdfgen import canvas
from .models import InventorySummary, Product


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular y estampar 'Página X de Y' con membrete corporativo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Línea y pie de página
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 36, letter[1] - 36 if self._pagesize == landscape(letter) else letter[0] - 36, 36)

        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(
            letter[1] - 36 if self._pagesize == landscape(letter) else letter[0] - 36,
            24,
            page_str
        )
        self.drawString(36, 24, "ERP Mobile Telegram Agent • Sistema de Control de Inventario y Activos")
        self.drawString(280, 24, "Titular: Ing. Owen Badel Hooker")
        self.restoreState()


class ERPPDFExporter:
    def __init__(self, reports_dir: str = None):
        self.reports_dir = Path(reports_dir or (Path(__file__).resolve().parent.parent / "reports"))
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_inventory_report(
        self,
        summary: InventorySummary,
        products: list[Product],
        company_name: str = "Empresa Asociada S.A.S.",
        generated_by: str = "Telegram ERP Agent"
    ) -> str:
        """Genera un informe ejecutivo apaisado (Landscape) con tabla de existencias y KPIs."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_inventario_{timestamp}.pdf"
        output_path = self.reports_dir / filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=landscape(letter),
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a")
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#475569")
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0f172a")
        )
        cell_text = ParagraphStyle(
            "CellText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155")
        )
        badge_alert = ParagraphStyle(
            "BadgeAlert",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#dc2626")
        )
        badge_ok = ParagraphStyle(
            "BadgeOk",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#16a34a")
        )

        story = []

        # 1. Cabecera Ejecutiva
        now_date_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        header_table_data = [
            [
                Paragraph(f"<b>{company_name}</b><br/><font size=12 color='#2563eb'>Informe Ejecutivo de Existencias y Valoración de Inventario</font>", title_style),
                Paragraph(f"<b>Fecha:</b> {now_date_str}<br/><b>Generado por:</b> {generated_by}<br/><b>Estado:</b> Auditado / En Línea", subtitle_style)
            ]
        ]
        header_table = Table(header_table_data, colWidths=[520, 200])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        # 2. Resumen de KPIs en Tarjetas
        kpi_data = [
            [
                Paragraph("<b>Total SKUs</b>", cell_bold),
                Paragraph("<b>Unidades Totales</b>", cell_bold),
                Paragraph("<b>Valor a Costo</b>", cell_bold),
                Paragraph("<b>Valor a Venta</b>", cell_bold),
                Paragraph("<b>Alertas Stock Bajo</b>", cell_bold)
            ],
            [
                Paragraph(f"<font size=13 color='#0284c7'><b>{summary.total_skus}</b></font>", cell_text),
                Paragraph(f"<font size=13 color='#0f172a'><b>{summary.total_units}</b></font>", cell_text),
                Paragraph(f"<font size=13 color='#16a34a'><b>${summary.total_valuation_cost:,.2f}</b></font>", cell_text),
                Paragraph(f"<font size=13 color='#2563eb'><b>${summary.total_valuation_sale:,.2f}</b></font>", cell_text),
                Paragraph(f"<font size=13 color='#dc2626'><b>{summary.low_stock_count} SKUs</b></font>", cell_text)
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[144, 144, 144, 144, 144])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 15))

        # 3. Tabla Detallada de Inventario
        table_headers = [
            Paragraph("<b>SKU</b>", cell_bold),
            Paragraph("<b>Descripción del Producto</b>", cell_bold),
            Paragraph("<b>Categoría</b>", cell_bold),
            Paragraph("<b>Ubicación</b>", cell_bold),
            Paragraph("<b>Mín</b>", cell_bold),
            Paragraph("<b>Stock</b>", cell_bold),
            Paragraph("<b>Costo Unit.</b>", cell_bold),
            Paragraph("<b>Precio Venta</b>", cell_bold),
            Paragraph("<b>Valor Total</b>", cell_bold),
            Paragraph("<b>Estado</b>", cell_bold)
        ]

        table_data = [table_headers]

        for p in products:
            status_para = Paragraph("⚠️ REORDEN", badge_alert) if p.is_low_stock else Paragraph("✅ ÓPTIMO", badge_ok)
            row = [
                Paragraph(f"<b>{p.sku}</b>", cell_bold),
                Paragraph(p.name, cell_text),
                Paragraph(p.category, cell_text),
                Paragraph(p.location, cell_text),
                Paragraph(str(p.stock_min), cell_text),
                Paragraph(f"<b>{p.stock_current}</b>", cell_bold),
                Paragraph(f"${p.cost_price:,.2f}", cell_text),
                Paragraph(f"${p.sale_price:,.2f}", cell_text),
                Paragraph(f"<b>${p.total_cost_value:,.2f}</b>", cell_bold),
                status_para
            ]
            table_data.append(row)

        col_widths = [60, 180, 110, 80, 32, 40, 55, 55, 60, 48]
        items_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        ts = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (4, 0), (8, -1), "RIGHT"),
            ("ALIGN", (9, 0), (9, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ])

        # Alternar colores de filas
        for i in range(1, len(table_data)):
            bg = colors.HexColor("#f8fafc") if i % 2 == 1 else colors.white
            ts.add("BACKGROUND", (0, i), (-1, i), bg)

        items_table.setStyle(ts)
        story.append(items_table)

        doc.build(story, canvasmaker=NumberedCanvas)
        return str(output_path)
