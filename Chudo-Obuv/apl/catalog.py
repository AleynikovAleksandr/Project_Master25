from flask import Blueprint, flash, redirect, url_for

import db
from core import render
from apl.access import need
from apl.cart import in_cart

bp = Blueprint("catalog", __name__)


@bp.route("/catalog")
@need("catalog")
def catalog():
    return render.page("catalog.html", products=db.get_products(), categories=db.get_categories())


@bp.route("/product/<int:product_id>")
@need("order")
def product(product_id):
    item = db.get_product(product_id)
    if item is None:
        flash("Товар не найден. Возможно, его удалили из каталога.", "error")
        return redirect(url_for("catalog.catalog"))
    stock = db.get_stock(product_id)
    available = [row for row in stock if row["quantity"] - in_cart(row["id"]) > 0]
    return render.page("product.html", product=item, stock=stock, available=available)
