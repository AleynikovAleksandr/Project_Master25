from datetime import date

from flask import Blueprint, flash, redirect, request, session, url_for
from sqlalchemy import text

import db
from core import render
from apl.access import can, need

bp = Blueprint("cart", __name__)


def read_quantity(value):
    value = value.strip()
    if not value.isdigit() or int(value) < 1:
        return None
    return int(value)


def in_cart(stock_id):
    for item in session.get("cart", []):
        if item["stock_id"] == stock_id:
            return item["qty"]
    return 0


def cart_lines():
    lines = []
    for item in session.get("cart", []):
        stock = db.get_stock_item(item["stock_id"])
        if stock is None:
            continue
        product = db.get_product(stock["product_id"])
        lines.append({
            "stock_id": stock["id"],
            "product": product,
            "size": stock["size"],
            "available": stock["quantity"],
            "qty": item["qty"],
            "sum": product["final_price"] * item["qty"],
        })
    return lines


@bp.route("/cart")
@need("order")
def cart():
    lines = cart_lines()
    users = db.get_users() if can("orders") else []
    return render.page("cart.html", lines=lines, total=sum(line["sum"] for line in lines), users=users)


@bp.route("/cart/add", methods=["POST"])
@need("order")
def add():
    stock_id = request.form.get("stock_id", "")
    qty = read_quantity(request.form.get("qty", ""))
    back = url_for("catalog.product", product_id=request.form.get("product_id", 0))

    if not stock_id.isdigit():
        flash("Выберите размер из списка доступных размеров.", "error")
        return redirect(back)
    if qty is None:
        flash("Количество пар должно быть целым числом больше нуля.", "error")
        return redirect(back)

    stock = db.get_stock_item(int(stock_id))
    free = stock["quantity"] - in_cart(int(stock_id)) if stock else 0
    if qty > free:
        flash(f"Такого количества нет в наличии. Для этого размера можно заказать не больше {free} пар.", "error")
        return redirect(back)

    cart = session.get("cart", [])
    for item in cart:
        if item["stock_id"] == int(stock_id):
            item["qty"] += qty
            break
    else:
        cart.append({"stock_id": int(stock_id), "qty": qty})
    session["cart"] = cart
    flash("Товар добавлен в заказ. Откройте «Заказ», чтобы проверить и подтвердить его.", "info")
    return redirect(url_for("catalog.catalog"))


@bp.route("/cart/change", methods=["POST"])
@need("order")
def change():
    stock_id = int(request.form["stock_id"])
    qty = read_quantity(request.form.get("qty", ""))
    stock = db.get_stock_item(stock_id)
    available = stock["quantity"] if stock else 0
    if qty is None:
        flash("Количество пар должно быть целым числом больше нуля. Чтобы убрать товар, нажмите «Удалить».", "error")
    elif qty > available:
        flash(f"Такого количества нет в наличии. Доступно пар: {available}.", "error")
    else:
        cart = session.get("cart", [])
        for item in cart:
            if item["stock_id"] == stock_id:
                item["qty"] = qty
        session["cart"] = cart
    return redirect(url_for("cart.cart"))


@bp.route("/cart/remove", methods=["POST"])
@need("order")
def remove():
    stock_id = int(request.form["stock_id"])
    session["cart"] = [item for item in session.get("cart", []) if item["stock_id"] != stock_id]
    return redirect(url_for("cart.cart"))


@bp.route("/cart/cancel", methods=["POST"])
@need("order")
def cancel():
    session["cart"] = []
    flash("Заказ отменён.", "info")
    return redirect(url_for("catalog.catalog"))


@bp.route("/cart/confirm", methods=["POST"])
@need("order")
def confirm():
    lines = cart_lines()
    if not lines:
        flash("В заказе нет товаров. Добавьте товары из каталога.", "warning")
        return redirect(url_for("catalog.catalog"))

    user_id = session["user_id"]
    if can("orders"):
        # Менеджер и администратор оформляют заказ на выбранного клиента
        user_id = int(request.form.get("user_id") or user_id)

    try:
        with db.engine.begin() as conn:
            order_id = conn.execute(
                text("INSERT INTO orders (order_date, user_id) VALUES (:order_date, :user_id)"),
                {"order_date": date.today(), "user_id": user_id},
            ).lastrowid
            for line in lines:
                # Пары списываются, только если их хватает, иначе заказ откатывается целиком
                changed = conn.execute(
                    text("UPDATE stock_items SET quantity = quantity - :qty "
                         "WHERE id = :id AND quantity >= :qty"),
                    {"qty": line["qty"], "id": line["stock_id"]},
                ).rowcount
                if changed == 0:
                    raise ValueError(f"«{line['product']['name']}», размер {line['size']}: "
                                     f"осталось только {line['available']} пар.")
                conn.execute(
                    text("INSERT INTO order_items (order_id, stock_item_id, quantity, unit_price) "
                         "VALUES (:order_id, :stock_id, :qty, :price)"),
                    {"order_id": order_id, "stock_id": line["stock_id"],
                     "qty": line["qty"], "price": line["product"]["final_price"]},
                )
    except ValueError as error:
        flash(f"Заказ не оформлен: {error} Измените количество и подтвердите заказ ещё раз.", "error")
        return redirect(url_for("cart.cart"))

    session["cart"] = []
    flash(f"Заказ № {order_id} оформлен {date.today():%d.%m.%Y}.", "info")
    if can("orders"):
        return redirect(url_for("orders.orders"))
    return redirect(url_for("catalog.catalog"))
