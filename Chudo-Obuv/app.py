import os

import webview
from flask import Flask, flash, redirect, request, session, url_for
from werkzeug.exceptions import HTTPException

import db
from core import render, static_server
from apl import cart, catalog, orders
from database.import_data import prepare_database

app = Flask(__name__)
app.secret_key = os.urandom(16)

app.register_blueprint(catalog.bp)
app.register_blueprint(cart.bp)
app.register_blueprint(orders.bp)
render.setup(app)

ROLE_CODES = {
    "Администратор": "admin",
    "Менеджер": "manager",
    "Авторизованный пользователь": "client",
}


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render.page("login.html")

    login_text = request.form.get("login", "").strip()
    if not login_text:
        flash("Поле «Логин» пустое. Введите логин из списка пользователей системы.", "error")
        return render.page("login.html")

    user = db.query_one(
        """SELECT u.id, u.last_name, u.first_name, u.middle_name, r.name AS role
           FROM users u JOIN roles r ON r.id = u.role_id WHERE u.login = :login""",
        login=login_text,
    )
    if user is None:
        flash(f"Пользователь с логином «{login_text}» не найден. Проверьте написание логина.", "error")
        return render.page("login.html", login=login_text)

    session.clear()
    session["user_id"] = user["id"]
    session["fio"] = f"{user['last_name']} {user['first_name']} {user['middle_name']}"
    session["role"] = ROLE_CODES[user["role"]]
    session["role_name"] = user["role"]
    session["cart"] = []
    return redirect(url_for("catalog.catalog"))


@app.route("/guest")
def enter_as_guest():
    session.clear()
    session["role"] = "guest"
    session["role_name"] = "Неавторизованный пользователь"
    return redirect(url_for("catalog.catalog"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


@app.errorhandler(Exception)
def show_error(error):
    # Непредвиденная ошибка (например, нет связи с БД) показывается пользователю, приложение не падает
    if isinstance(error, HTTPException):
        return error
    return render.page("error.html", error=error), 500


if __name__ == "__main__":
    prepare_database()
    webview.create_window("Чудо Обувь", static_server.start(app), width=1280, height=860, min_size=(980, 640))
    webview.start(icon=os.path.join(app.static_folder, "img", "icon.ico"))
