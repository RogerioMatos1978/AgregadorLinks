from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import qrcode
import os

# ==== Configuração da aplicação ====
app = Flask(__name__)
app.secret_key = "minha_chave_super_secreta"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "links.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# ==== Modelos ====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    qrcode_image = db.Column(db.String(200), nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone(timedelta(hours=-3)))  # Horário Brasília
    )


# ==== Funções auxiliares ====
def generate_qrcode(link_id, url):
    """Gerar QRCode e salvar em static/qrcodes"""
    folder = os.path.join(BASE_DIR, "static", "qrcodes")
    os.makedirs(folder, exist_ok=True)

    img = qrcode.make(url)
    filename = f"qrcode_{link_id}.png"
    filepath = os.path.join(folder, filename)
    img.save(filepath)
    return "qrcodes/" + filename


# ==== Rotas ====
@app.route("/")
def index():
    user = session.get("user")
    admin = session.get("admin")
    links = Link.query.order_by(Link.created_at.desc()).limit(8).all()

    return render_template("index.html", links=links, logged_in=bool(user), user=user, admin=admin)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user"] = user.email
            session["admin"] = user.is_admin
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado!", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        user = User(email=email, password=hashed_pw, is_admin=False)
        db.session.add(user)
        db.session.commit()

        flash("Cadastro realizado! Faça login.", "success")
        return redirect(url_for("login"))
    #Rota para registrar usuario desativada
    #return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("index"))


@app.route("/add", methods=["GET", "POST"])
def add_link():
    if not session.get("admin"):
        flash("Apenas administradores podem adicionar links.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        if Link.query.count() >= 8:
            flash("Limite de 8 links atingido. Exclua um para adicionar outro.", "warning")
            return redirect(url_for("index"))

        title = request.form["title"]
        url = request.form["url"]
        description = request.form["description"]

        new_link = Link(title=title, url=url, description=description)
        db.session.add(new_link)
        db.session.commit()

        # Gerar QRCode
        qrcode_path = generate_qrcode(new_link.id, url)
        new_link.qrcode_image = qrcode_path
        db.session.commit()

        flash("Link adicionado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("add_link.html")


@app.route("/delete/<int:link_id>")
def delete_link(link_id):
    if not session.get("admin"):
        flash("Apenas administradores podem excluir links.", "danger")
        return redirect(url_for("index"))

    link = Link.query.get_or_404(link_id)

    if link.qrcode_image:
        try:
            os.remove(os.path.join(BASE_DIR, "static", link.qrcode_image))
        except:
            pass

    db.session.delete(link)
    db.session.commit()
    flash("Link removido com sucesso!", "info")
    return redirect(url_for("index"))


# ==== Inicialização do banco e admin padrão ====
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@fieg.com.br").first():
        admin_user = User(
            email="admin@fieg.com.br",
            password=generate_password_hash("@#$admin123"),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Usuário admin criado: admin@fieg.com.br / senha: @#$admin123")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
