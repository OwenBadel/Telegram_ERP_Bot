"""
Gestor de Base de Datos SQLite Transaccional para el ERP.
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "erp_inventory.db"


class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
        self._mem_conn = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        if self._mem_conn:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            # 1. Tabla de Categorías
            conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            );
            """)

            # 2. Tabla de Productos
            conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category_name TEXT NOT NULL DEFAULT 'General',
                stock_current INTEGER NOT NULL DEFAULT 0,
                stock_min INTEGER NOT NULL DEFAULT 5,
                cost_price REAL NOT NULL DEFAULT 0.0,
                sale_price REAL NOT NULL DEFAULT 0.0,
                location TEXT NOT NULL DEFAULT 'Bodega Central',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. Tabla de Movimientos Kardex
            conn.execute("""
            CREATE TABLE IF NOT EXISTS kardex_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_sku TEXT NOT NULL,
                product_name TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                previous_stock INTEGER NOT NULL,
                new_stock INTEGER NOT NULL,
                unit_cost REAL DEFAULT 0.0,
                reference_doc TEXT DEFAULT 'N/A',
                notes TEXT,
                user_name TEXT DEFAULT 'Sistema',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_sku) REFERENCES products(sku) ON UPDATE CASCADE
            );
            """)

            # 4. Tabla de Usuarios Autorizados (RBAC Telegram)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                username TEXT,
                role TEXT NOT NULL DEFAULT 'OPERADOR',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Verificar si se debe sembrar datos iniciales
            cursor = conn.execute("SELECT COUNT(*) as count FROM products;")
            if cursor.fetchone()["count"] == 0:
                self._seed_initial_data(conn)

    def _seed_initial_data(self, conn: sqlite3.Connection):
        """Siembra datos iniciales de prueba para catálogo e inventario."""
        initial_categories = [
            ("Hardware & Cómputo", "Servidores, portátiles y estaciones de trabajo"),
            ("Periféricos & Monitores", "Pantallas, teclados, ratones y accesorios"),
            ("Redes & Telecomunicaciones", "Switches, routers, cableado UTP y fibra"),
            ("Almacenamiento & Memorias", "Discos SSD NVMe, memorias RAM y discos mecánicos")
        ]
        for name, desc in initial_categories:
            conn.execute("INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?);", (name, desc))

        initial_products = [
            ("LAP-001", "Laptop Lenovo ThinkPad T14 Gen 4", "Hardware & Cómputo", 15, 5, 850.00, 1150.00, "Estante A-1"),
            ("LAP-002", "MacBook Pro M3 14 pulg 16GB", "Hardware & Cómputo", 4, 3, 1600.00, 2050.00, "Caja Fuerte B-2"),
            ("MON-001", "Monitor Dell UltraSharp 27 pulg 4K", "Periféricos & Monitores", 8, 4, 320.00, 480.00, "Estante B-1"),
            ("MON-002", "Monitor LG UltraWide 34 pulg", "Periféricos & Monitores", 3, 5, 410.00, 590.00, "Estante B-2"), # Stock Bajo
            ("NET-001", "Switch Cisco Catalyst 24 Puertos PoE", "Redes & Telecomunicaciones", 6, 2, 650.00, 920.00, "Rack R-1"),
            ("NET-002", "Bobina Cable UTP Cat6 305m", "Redes & Telecomunicaciones", 2, 5, 95.00, 140.00, "Tarima R-4"), # Stock Bajo
            ("MEM-001", "SSD Kingston NV2 1TB NVMe PCIe 4.0", "Almacenamiento & Memorias", 28, 10, 55.00, 85.00, "Gaveta C-1"),
            ("MEM-002", "Memoria RAM Corsair Vengeance 32GB DDR5", "Almacenamiento & Memorias", 12, 6, 90.00, 130.00, "Gaveta C-2"),
            ("ACC-001", "Teclado Mecánico Keychron K2 Wireless", "Periféricos & Monitores", 1, 5, 75.00, 110.00, "Gaveta A-3") # Stock Crítico
        ]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for sku, name, cat, stock, smin, cost, sale, loc in initial_products:
            conn.execute("""
            INSERT INTO products (sku, name, category_name, stock_current, stock_min, cost_price, sale_price, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (sku, name, cat, stock, smin, cost, sale, loc, now_str))

            # Movimiento inicial en Kardex
            conn.execute("""
            INSERT INTO kardex_movements (product_sku, product_name, movement_type, quantity, previous_stock, new_stock, unit_cost, reference_doc, notes, user_name, created_at)
            VALUES (?, ?, 'ENTRADA_COMPRA', ?, 0, ?, ?, 'INV-INICIAL', 'Inventario inicial de arranque del sistema', 'Owen Badel Hooker', ?);
            """, (sku, name, stock, stock, cost, now_str))
