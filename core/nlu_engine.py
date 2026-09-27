"""
Motor NLU Heurístico y de Intenciones en Lenguaje Natural.
Interpreta mensajes libres de los usuarios en Telegram y extrae entidades ERP.
"""

import re
from typing import Dict, Any, Optional
from .models import MovementType


class NLUEngine:
    def __init__(self):
        # Patrones para comandos de entrada / salida
        self.entrada_patterns = [
            re.compile(r"(?:entrada|ingresar?|recibir?|comprar?|aumentar|sumar)\s+(\d+)\s*(?:unidades?|un|piezas?|uds?)?\s*(?:de\s+)?([A-Z0-9_-]+)(?:\s+(?:por|con|doc|fac|ref)\s+(.+))?", re.IGNORECASE),
            re.compile(r"([A-Z0-9_-]+)\s*\+\s*(\d+)", re.IGNORECASE)
        ]
        self.salida_patterns = [
            re.compile(r"(?:salida|despachar?|vender?|restar|entregar?|baja)\s+(\d+)\s*(?:unidades?|un|piezas?|uds?)?\s*(?:de\s+)?([A-Z0-9_-]+)(?:\s+(?:por|con|doc|fac|ref|orden)\s+(.+))?", re.IGNORECASE),
            re.compile(r"([A-Z0-9_-]+)\s*-\s*(\d+)", re.IGNORECASE)
        ]
        self.stock_patterns = [
            re.compile(r"^(?:stock|cuanto\s+queda|existencias?|buscar?|consultar?|precio)\s+(.+)$", re.IGNORECASE),
            re.compile(r"^([A-Z]{3}-\d{3})$", re.IGNORECASE)
        ]

    def parse_intent(self, text: str) -> Dict[str, Any]:
        """Analiza un texto en lenguaje natural y extrae la intención y sus parámetros."""
        raw = text.strip()
        lower = raw.lower()

        # 1. Reporte PDF
        if any(kw in lower for kw in ["reporte", "informe", "pdf", "balance", "descargar", "exportar inventario"]):
            return {"intent": "REPORTE_PDF"}

        # 2. Alertas de Stock Bajo
        if any(kw in lower for kw in ["alerta", "bajo stock", "agotado", "reorden", "por terminar", "critico"]):
            return {"intent": "ALERTAS_STOCK"}

        # 3. Ayuda
        if lower in ["ayuda", "help", "hola", "que haces", "opciones", "menu"]:
            return {"intent": "AYUDA"}

        # 4. Entradas de inventario
        for p in self.entrada_patterns:
            m = p.search(raw)
            if m:
                groups = m.groups()
                if len(groups) == 2 and "+" in raw:
                    sku, qty = groups[0], int(groups[1])
                    ref = "Entrada Rápida"
                else:
                    qty = int(groups[0])
                    sku = groups[1]
                    ref_raw = groups[2].strip() if len(groups) > 2 and groups[2] else "N/A"
                    ref = re.sub(r"^(?:por|con|doc|fac|factura|ref|orden)\s+", "", ref_raw, flags=re.IGNORECASE).strip() if ref_raw != "N/A" else "N/A"
                return {
                    "intent": "REGISTRO_MOVIMIENTO",
                    "movement_type": MovementType.ENTRADA_COMPRA,
                    "sku": sku.strip().upper(),
                    "quantity": qty,
                    "reference": ref
                }

        # 5. Salidas de inventario
        for p in self.salida_patterns:
            m = p.search(raw)
            if m:
                groups = m.groups()
                if len(groups) == 2 and "-" in raw:
                    sku, qty = groups[0], int(groups[1])
                    ref = "Salida Rápida"
                else:
                    qty = int(groups[0])
                    sku = groups[1]
                    ref_raw = groups[2].strip() if len(groups) > 2 and groups[2] else "N/A"
                    ref = re.sub(r"^(?:por|con|doc|fac|factura|ref|orden)\s+", "", ref_raw, flags=re.IGNORECASE).strip() if ref_raw != "N/A" else "N/A"
                return {
                    "intent": "REGISTRO_MOVIMIENTO",
                    "movement_type": MovementType.SALIDA_VENTA,
                    "sku": sku.strip().upper(),
                    "quantity": qty,
                    "reference": ref
                }

        # 6. Consultas de Stock
        for p in self.stock_patterns:
            m = p.search(raw)
            if m:
                target = m.group(1).strip()
                return {
                    "intent": "CONSULTA_STOCK",
                    "query": target
                }

        # 7. Fallback: asumir búsqueda en catálogo si no es vacío
        if len(raw) >= 2:
            return {
                "intent": "CONSULTA_STOCK",
                "query": raw
            }

        return {"intent": "DESCONOCIDO", "raw_text": raw}
