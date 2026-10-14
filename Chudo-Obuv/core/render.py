from flask import render_template

from apl.access import can


def money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def setup(app):
    app.jinja_env.filters["money"] = money
    app.jinja_env.globals["can"] = can


def page(name, **data):
    # Все страницы приложения собираются из шаблонов через эту функцию
    return render_template(name, **data)
