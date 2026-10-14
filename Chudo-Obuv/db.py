from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

import config

engine = create_engine(config.DB_URL, pool_pre_ping=True)

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "img" / "products"
DISCOUNT_PERCENT = 25

PRODUCT_SQL = """
    SELECT p.id, p.name, p.description, p.composition, p.price, p.image,
           c.name AS category, m.name AS manufacturer,
           COALESCE(SUM(s.quantity), 0) AS total
    FROM products p
    JOIN categories c ON c.id = p.category_id
    JOIN manufacturers m ON m.id = p.manufacturer_id
    LEFT JOIN stock_items s ON s.product_id = p.id
"""


def query(sql, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).mappings().all()


def query_one(sql, **params):
    rows = query(sql, **params)
    return rows[0] if rows else None


def products_sold_last_month():
    # Прошлый календарный месяц: с 1-го числа прошлого месяца до 1-го числа текущего
    first_day = date.today().replace(day=1)
    previous_first_day = (first_day - timedelta(days=1)).replace(day=1)
    rows = query(
        """SELECT DISTINCT s.product_id FROM order_items oi
           JOIN orders o ON o.id = oi.order_id
           JOIN stock_items s ON s.id = oi.stock_item_id
           WHERE o.order_date >= :start AND o.order_date < :end""",
        start=previous_first_day, end=first_day,
    )
    return {row["product_id"] for row in rows}


def add_prices(rows):
    # Скидка 25% на товары, которые не заказывали в прошлом календарном месяце
    sold = products_sold_last_month()
    products = []
    for row in rows:
        product = dict(row)
        product["has_discount"] = product["id"] not in sold
        if product["has_discount"]:
            product["final_price"] = round(product["price"] * (100 - DISCOUNT_PERCENT) / 100, 2)
        else:
            product["final_price"] = product["price"]
        image = product["image"]
        if image and (PRODUCTS_DIR / image).exists():
            product["image_url"] = "img/products/" + image
        else:
            product["image_url"] = "img/picture.png"
        products.append(product)
    return products


def get_products():
    rows = query(PRODUCT_SQL + " GROUP BY p.id, c.name, m.name ORDER BY p.id")
    return add_prices(rows)


def get_product(product_id):
    rows = query(PRODUCT_SQL + " WHERE p.id = :id GROUP BY p.id, c.name, m.name", id=product_id)
    products = add_prices(rows)
    return products[0] if products else None


def get_categories():
    return query("SELECT id, name FROM categories ORDER BY name")


def get_stock(product_id):
    return query(
        """SELECT s.id, s.quantity, z.value AS size FROM stock_items s
           JOIN sizes z ON z.id = s.size_id
           WHERE s.product_id = :id
           ORDER BY CAST(z.value AS DECIMAL(4, 1))""",
        id=product_id,
    )


def get_stock_item(stock_id):
    return query_one(
        """SELECT s.id, s.product_id, s.quantity, z.value AS size FROM stock_items s
           JOIN sizes z ON z.id = s.size_id WHERE s.id = :id""",
        id=stock_id,
    )


def get_users():
    return query("SELECT id, last_name, first_name, middle_name FROM users ORDER BY last_name")


ORDER_SQL = """
    SELECT o.id, o.order_date, o.user_id,
           CONCAT(u.last_name, ' ', u.first_name, ' ', u.middle_name) AS client,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total
    FROM orders o
    JOIN users u ON u.id = o.user_id
    LEFT JOIN order_items oi ON oi.order_id = o.id
"""
ORDER_GROUP = " GROUP BY o.id, o.order_date, u.last_name, u.first_name, u.middle_name"


def get_orders():
    return query(ORDER_SQL + ORDER_GROUP + " ORDER BY o.order_date DESC, o.id DESC")


def get_order(order_id):
    return query_one(ORDER_SQL + " WHERE o.id = :id" + ORDER_GROUP, id=order_id)


def get_available_stock():
    return query(
        """SELECT s.id, s.quantity, z.value AS size, p.name, m.name AS manufacturer
           FROM stock_items s
           JOIN products p ON p.id = s.product_id
           JOIN manufacturers m ON m.id = p.manufacturer_id
           JOIN sizes z ON z.id = s.size_id
           WHERE s.quantity > 0
           ORDER BY p.name, CAST(z.value AS DECIMAL(4, 1))"""
    )


def get_order_lines(order_id):
    return query(
        """SELECT oi.id, p.name, m.name AS manufacturer, z.value AS size,
                  oi.quantity, oi.unit_price, oi.quantity * oi.unit_price AS sum
           FROM order_items oi
           JOIN stock_items s ON s.id = oi.stock_item_id
           JOIN products p ON p.id = s.product_id
           JOIN manufacturers m ON m.id = p.manufacturer_id
           JOIN sizes z ON z.id = s.size_id
           WHERE oi.order_id = :id ORDER BY oi.id""",
        id=order_id,
    )


def delete_order_items(conn, order_id, item_id=None):
    # Удаляет одну или все позиции заказа и возвращает их пары на склад
    condition = "oi.order_id = :order_id"
    if item_id is not None:
        condition += " AND oi.id = :item_id"
    params = {"order_id": order_id, "item_id": item_id}
    conn.execute(
        text("UPDATE stock_items s JOIN order_items oi ON oi.stock_item_id = s.id "
             "SET s.quantity = s.quantity + oi.quantity WHERE " + condition),
        params,
    )
    conn.execute(text("DELETE oi FROM order_items oi WHERE " + condition), params)
