"""
Modelos de Dominio y Esquemas de Validación para el ERP.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class MovementType(str, Enum):
    ENTRADA_COMPRA = "ENTRADA_COMPRA"
    SALIDA_VENTA = "SALIDA_VENTA"
    AJUSTE_MERMA = "AJUSTE_MERMA"
    TRANSFERENCIA = "TRANSFERENCIA"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERADOR = "OPERADOR"
    CONSULTOR = "CONSULTOR"


class Product(BaseModel):
    id: Optional[int] = None
    sku: str = Field(..., description="Código único de producto / SKU")
    name: str = Field(..., description="Nombre comercial del producto")
    category: str = Field("General", description="Categoría del catálogo")
    stock_current: int = Field(0, ge=0, description="Stock disponible físico")
    stock_min: int = Field(5, ge=0, description="Nivel mínimo de alerta")
    cost_price: float = Field(0.0, ge=0, description="Costo unitario de adquisición")
    sale_price: float = Field(0.0, ge=0, description="Precio unitario de venta")
    location: str = Field("Bodega Central", description="Pasillo / Ubicación física")
    updated_at: Optional[datetime] = None

    @property
    def is_low_stock(self) -> bool:
        return self.stock_current <= self.stock_min

    @property
    def total_cost_value(self) -> float:
        return round(self.stock_current * self.cost_price, 2)


class KardexMovement(BaseModel):
    id: Optional[int] = None
    product_sku: str
    product_name: str
    movement_type: MovementType
    quantity: int
    previous_stock: int
    new_stock: int
    unit_cost: float = 0.0
    reference_doc: str = "N/A"
    notes: Optional[str] = ""
    user_name: str = "Sistema"
    created_at: Optional[datetime] = None


class InventorySummary(BaseModel):
    total_skus: int
    total_units: int
    total_valuation_cost: float
    total_valuation_sale: float
    low_stock_count: int
    low_stock_items: List[Product] = []


class ERPUser(BaseModel):
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    role: UserRole = UserRole.OPERADOR
    is_active: bool = True
