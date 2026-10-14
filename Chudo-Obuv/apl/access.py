from functools import wraps

from flask import flash, redirect, session, url_for

# Единая точка прав: какое действие каким ролям доступно
RIGHTS = {
    "catalog": ("guest", "client", "manager", "admin"),
    "order": ("client", "manager", "admin"),
    "orders": ("manager", "admin"),
    "edit_orders": ("admin",),
}

DENIED = {
    "catalog": "Войдите в систему по логину или нажмите «Просмотр каталога без авторизации».",
    "order": "Оформлять заказы могут только авторизованные пользователи. Войдите в систему по своему логину.",
    "orders": "Работать со списком заказов могут только менеджер и администратор.",
    "edit_orders": "Редактировать заказы может только администратор.",
}


def can(right):
    return session.get("role") in RIGHTS[right]


def need(right):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if can(right):
                return view(*args, **kwargs)
            flash(DENIED[right], "warning")
            if "role" not in session:
                return redirect(url_for("login"))
            return redirect(url_for("catalog.catalog"))
        return wrapper
    return decorator
