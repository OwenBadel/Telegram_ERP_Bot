"""
Capa de Servicio de Negocio ERP e Inventario.
Implementa las operaciones transaccionales y de consulta sobre el almacén.
"""

from typing import List, Optional, Tuple
from datetime import datetime
from .database import DatabaseManager
from .models import Product, KardexMovement, InventorySummary, MovementType, ERPUser, UserRole


class ERPService:
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()

    def get_summary(self) -> InventorySummary:
        """Calcula los indicadores clave de rendimiento (KPIs) del inventario."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_skus,
                COALESCE(SUM(stock_current), 0) as total_units,
                COALESCE(SUM(stock_current * cost_price), 0.0) as val_cost,
                COALESCE(SUM(stock_current * sale_price), 0.0) as val_sale
            FROM products;
            """)
            row = cursor.fetchone()

            # Productos en alerta de stock bajo
            low_cursor = conn.execute("""
            SELECT * FROM products WHERE stock_current <= stock_min ORDER BY stock_current ASC;
            """)
            low_items = [self._row_to_product(r) for r in low_cursor.fetchall()]

            return InventorySummary(
                total_skus=row["total_skus"],
                total_units=row["total_units"],
                total_valuation_cost=round(row["val_cost"], 2),
                total_valuation_sale=round(row["val_sale"], 2),
                low_stock_count=len(low_items),
                low_stock_items=low_items
            )

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """Obtiene un producto por su SKU exacto (o case-insensitive)."""
        clean_sku = sku.strip().upper()
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE UPPER(sku) = ?;", (clean_sku,))
            row = cursor.fetchone()
            if row:
                return self._row_to_product(row)
        return None

    def search_products(self, query: str = "") -> List[Product]:
        """Busca productos por coincidencia parcial en SKU, nombre o categoría."""
        clean_query = f"%{query.strip().lower()}%"
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
            SELECT * FROM products 
            WHERE LOWER(sku) LIKE ? OR LOWER(name) LIKE ? OR LOWER(category_name) LIKE ?
            ORDER BY category_name, name;
            """, (clean_query, clean_query, clean_query))
            return [self._row_to_product(r) for r in cursor.fetchall()]

    def get_low_stock_products(self) -> List[Product]:
        """Devuelve todos los productos cuyo stock actual sea menor o igual al stock mínimo."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
            SELECT * FROM products 
            WHERE stock_current <= stock_min 
            ORDER BY stock_current ASC, name ASC;
            """)
            return [self._row_to_product(r) for r in cursor.fetchall()]

    def register_movement(
        self,
        sku: str,
        movement_type: MovementType,
        quantity: int,
        user_name: str = "Operador",
        reference_doc: str = "N/A",
        notes: str = ""
    ) -> Tuple[bool, str, Optional[KardexMovement]]:
        """
        Ejecuta un movimiento atómico de Kardex (Entrada, Salida o Ajuste)
        actualizando el stock del producto con control de integridad.
        """
        if quantity <= 0:
            return False, "La cantidad del movimiento debe ser un número entero mayor a cero.", None

        clean_sku = sku.strip().upper()

        with self.db.get_connection() as conn:
            # 1. Obtener producto con bloqueo en transacción
            cursor = conn.execute("SELECT * FROM products WHERE UPPER(sku) = ?;", (clean_sku,))
            prod_row = cursor.fetchone()
            if not prod_row:
                return False, f"El producto con SKU '{clean_sku}' no existe en el catálogo del ERP.", None

            prev_stock = prod_row["stock_current"]
            cost_price = prod_row["cost_price"]
            prod_name = prod_row["name"]

            # 2. Calcular nuevo stock según tipo de movimiento
            if movement_type in [MovementType.ENTRADA_COMPRA, MovementType.TRANSFERENCIA]:
                new_stock = prev_stock + quantity
            elif movement_type in [MovementType.SALIDA_VENTA, MovementType.AJUSTE_MERMA]:
                if prev_stock < quantity:
                    return (
                        False,
                        f"Stock insuficiente para {clean_sku}. Stock disponible: {prev_stock}, solicitado: {quantity}.",
                        None
                    )
                new_stock = prev_stock - quantity
            else:
                return False, f"Tipo de movimiento no reconocido: {movement_type}", None

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 3. Actualizar stock en la tabla de productos
            conn.execute("""
            UPDATE products 
            SET stock_current = ?, updated_at = ? 
            WHERE UPPER(sku) = ?;
            """, (new_stock, now_str, clean_sku))

            # 4. Registrar movimiento en la tabla Kardex
            kardex_cursor = conn.execute("""
            INSERT INTO kardex_movements (
                product_sku, product_name, movement_type, quantity, 
                previous_stock, new_stock, unit_cost, reference_doc, notes, user_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (clean_sku, prod_name, movement_type.value, quantity, prev_stock, new_stock, cost_price, reference_doc, notes, user_name, now_str))

            movement_id = kardex_cursor.lastrowid

            movement = KardexMovement(
                id=movement_id,
                product_sku=clean_sku,
                product_name=prod_name,
                movement_type=movement_type,
                quantity=quantity,
                previous_stock=prev_stock,
                new_stock=new_stock,
                unit_cost=cost_price,
                reference_doc=reference_doc,
                notes=notes,
                user_name=user_name,
                created_at=datetime.now()
            )

            msg = f"Movimiento exitoso: {movement_type.value} de {quantity} un. en {clean_sku}. Nuevo stock: {new_stock} un."
            if new_stock <= prod_row["stock_min"]:
                msg += f"\n⚠️ *Alerta:* El stock actual ({new_stock}) ha alcanzado o caído por debajo del mínimo ({prod_row['stock_min']})."

            return True, msg, movement

    def get_kardex(self, limit: int = 15, sku: Optional[str] = None) -> List[KardexMovement]:
        """Consulta los últimos movimientos registrados en el Kardex."""
        with self.db.get_connection() as conn:
            if sku:
                cursor = conn.execute("""
                SELECT * FROM kardex_movements 
                WHERE UPPER(product_sku) = ? 
                ORDER BY id DESC LIMIT ?;
                """, (sku.strip().upper(), limit))
            else:
                cursor = conn.execute("""
                SELECT * FROM kardex_movements 
                ORDER BY id DESC LIMIT ?;
                """, (limit,))

            rows = cursor.fetchall()
            return [
                KardexMovement(
                    id=r["id"],
                    product_sku=r["product_sku"],
                    product_name=r["product_name"],
                    movement_type=MovementType(r["movement_type"]),
                    quantity=r["quantity"],
                    previous_stock=r["previous_stock"],
                    new_stock=r["new_stock"],
                    unit_cost=r["unit_cost"],
                    reference_doc=r["reference_doc"],
                    notes=r["notes"] or "",
                    user_name=r["user_name"],
                    created_at=datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S") if r["created_at"] else None
                )
                for r in rows
            ]

    def add_product(
        self,
        sku: str,
        name: str,
        category: str,
        initial_stock: int,
        stock_min: int,
        cost_price: float,
        sale_price: float,
        location: str,
        user_name: str = "Admin"
    ) -> Tuple[bool, str, Optional[Product]]:
        """Crea un nuevo producto en el catálogo e inicializa su Kardex."""
        clean_sku = sku.strip().upper()
        with self.db.get_connection() as conn:
            # Validar existencia
            existing = conn.execute("SELECT id FROM products WHERE UPPER(sku) = ?;", (clean_sku,)).fetchone()
            if existing:
                return False, f"El SKU '{clean_sku}' ya se encuentra registrado.", None

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
            INSERT INTO products (sku, name, category_name, stock_current, stock_min, cost_price, sale_price, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (clean_sku, name.strip(), category.strip(), initial_stock, stock_min, cost_price, sale_price, location.strip(), now_str))

            if initial_stock > 0:
                conn.execute("""
                INSERT INTO kardex_movements (product_sku, product_name, movement_type, quantity, previous_stock, new_stock, unit_cost, reference_doc, notes, user_name, created_at)
                VALUES (?, ?, 'ENTRADA_COMPRA', ?, 0, ?, ?, 'CREACION_PRODUCTO', 'Inventario inicial al crear ficha de producto', ?, ?);
                """, (clean_sku, name.strip(), initial_stock, initial_stock, cost_price, user_name, now_str))

        prod = self.get_product_by_sku(clean_sku)
        return True, f"Producto '{name}' ({clean_sku}) creado exitosamente con {initial_stock} unidades.", prod

    def _row_to_product(self, row) -> Product:
        return Product(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            category=row["category_name"],
            stock_current=row["stock_current"],
            stock_min=row["stock_min"],
            cost_price=row["cost_price"],
            sale_price=row["sale_price"],
            location=row["location"],
            updated_at=datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S") if row["updated_at"] else None
        )
