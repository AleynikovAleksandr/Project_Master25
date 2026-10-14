from datetime import date

from flask import Blueprint, flash, redirect, request, session, url_for
from sqlalchemy import text

import db
from core import render
from apl.access import can, need

bp = Blueprint("orders", __name__)


@bp.route("/orders")
@need("orders")
def orders():
    return render.page("orders.html", orders=db.get_orders())


@bp.route("/orders/<int:order_id>")
@need("orders")
def order(order_id):
    item = db.get_order(order_id)
    if item is None:
        flash(f"Заказ № {order_id} не найден. Возможно, его уже удалили.", "error")
        return redirect(url_for("orders.orders"))
    lines = db.get_order_lines(order_id)
    users = []
    stock = []
    if can("edit_orders"):
        users = db.get_users()
        stock = db.get_available_stock()
    return render.page("order.html", order=item, lines=lines, users=users, stock=stock,
                           today=date.today().isoformat())


@bp.route("/orders/new")
@need("orders")
def new_order():
    session["cart"] = []
    flash("Выберите товары в каталоге (можно искать по наименованию), затем откройте «Заказ», "
          "укажите клиента и подтвердите заказ.", "info")
    return redirect(url_for("catalog.catalog"))


@bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@need("orders")
def delete_order(order_id):
    with db.engine.begin() as conn:
        db.delete_order_items(conn, order_id)
        conn.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order_id})
    flash(f"Заказ № {order_id} удалён.", "info")
    return redirect(url_for("orders.orders"))


def read_quantity(value):
    value = value.strip()
    if not value.isdigit() or int(value) < 1:
        return None
    return int(value)


@bp.route("/orders/<int:order_id>/edit", methods=["POST"])
@need("edit_orders")
def update_order(order_id):
    back = url_for("orders.order", order_id=order_id)
    try:
        new_date = date.fromisoformat(request.form.get("order_date", ""))
    except ValueError:
        flash("Дата заказа указана неверно. Выберите дату в календаре.", "error")
        return redirect(back)
    if new_date > date.today():
        flash("Дата заказа не может быть позже сегодняшнего дня.", "error")
        return redirect(back)

    user_id = request.form.get("user_id", "")
    if not user_id.isdigit() or db.query_one("SELECT id FROM users WHERE id = :id", id=int(user_id)) is None:
        flash("Выберите клиента из списка.", "error")
        return redirect(back)

    with db.engine.begin() as conn:
        conn.execute(text("UPDATE orders SET order_date = :d, user_id = :u WHERE id = :id"),
                     {"d": new_date, "u": int(user_id), "id": order_id})
    flash("Изменения заказа сохранены.", "info")
    return redirect(back)


@bp.route("/orders/<int:order_id>/items/<int:item_id>/quantity", methods=["POST"])
@need("edit_orders")
def change_quantity(order_id, item_id):
    back = url_for("orders.order", order_id=order_id)
    qty = read_quantity(request.form.get("qty", ""))
    if qty is None:
        flash("Количество пар должно быть целым числом больше нуля. Чтобы убрать позицию, нажмите «Удалить».", "error")
        return redirect(back)

    line = db.query_one(
        """SELECT oi.quantity, oi.stock_item_id, s.quantity AS free FROM order_items oi
           JOIN stock_items s ON s.id = oi.stock_item_id
           WHERE oi.id = :item_id AND oi.order_id = :order_id""",
        item_id=item_id, order_id=order_id,
    )
    if line is None:
        flash("Позиция не найдена. Возможно, её уже удалили.", "error")
        return redirect(back)

    # Склад меняется на разницу: больше пар — списываем, меньше — возвращаем
    difference = qty - line["quantity"]
    if difference > line["free"]:
        flash(f"Такого количества нет в наличии. Можно добавить не больше {line['free']} пар.", "error")
        return redirect(back)

    with db.engine.begin() as conn:
        conn.execute(text("UPDATE stock_items SET quantity = quantity - :d WHERE id = :id"),
                     {"d": difference, "id": line["stock_item_id"]})
        conn.execute(text("UPDATE order_items SET quantity = :q WHERE id = :id"), {"q": qty, "id": item_id})
    flash("Количество в позиции изменено.", "info")
    return redirect(back)


@bp.route("/orders/<int:order_id>/items/add", methods=["POST"])
@need("edit_orders")
def add_item(order_id):
    back = url_for("orders.order", order_id=order_id)
    stock_id = request.form.get("stock_id", "")
    qty = read_quantity(request.form.get("qty", ""))
    if not stock_id.isdigit():
        flash("Выберите товар и размер из списка.", "error")
        return redirect(back)
    if qty is None:
        flash("Количество пар должно быть целым числом больше нуля.", "error")
        return redirect(back)

    stock = db.get_stock_item(int(stock_id))
    if stock is None or qty > stock["quantity"]:
        flash(f"Такого количества нет в наличии. Доступно пар: {stock['quantity'] if stock else 0}.", "error")
        return redirect(back)

    price = db.get_product(stock["product_id"])["final_price"]
    existing = db.query_one("SELECT id FROM order_items WHERE order_id = :o AND stock_item_id = :s",
                            o=order_id, s=stock["id"])
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE stock_items SET quantity = quantity - :q WHERE id = :id"),
                     {"q": qty, "id": stock["id"]})
        if existing:
            conn.execute(text("UPDATE order_items SET quantity = quantity + :q WHERE id = :id"),
                         {"q": qty, "id": existing["id"]})
        else:
            conn.execute(text("INSERT INTO order_items (order_id, stock_item_id, quantity, unit_price) "
                              "VALUES (:o, :s, :q, :p)"),
                         {"o": order_id, "s": stock["id"], "q": qty, "p": price})
    flash("Позиция добавлена в заказ.", "info")
    return redirect(back)


@bp.route("/orders/<int:order_id>/items/<int:item_id>/delete", methods=["POST"])
@need("edit_orders")
def delete_item(order_id, item_id):
    with db.engine.begin() as conn:
        db.delete_order_items(conn, order_id, item_id)
        left = conn.execute(
            text("SELECT COUNT(*) FROM order_items WHERE order_id = :id"), {"id": order_id}
        ).scalar()
        if left == 0:
            conn.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order_id})

    if left == 0:
        flash(f"Из заказа № {order_id} удалена последняя позиция, поэтому заказ удалён.", "warning")
        return redirect(url_for("orders.orders"))
    flash("Товарная позиция удалена из заказа.", "info")
    return redirect(url_for("orders.order", order_id=order_id))
