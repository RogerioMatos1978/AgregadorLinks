from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import qrcode
import os
import sqlite3

# ==== Configuração da aplicação ====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "minha_chave_super_secreta")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "links.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Níveis:
# admin  = editor do sistema: adiciona, edita e exclui links
# viewer = visualizador: indicado para TV, apenas exibe os cards
ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
BR_TZ = timezone(timedelta(hours=-3))

# ==== Modelos ====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # mantido por compatibilidade
    role = db.Column(db.String(20), default=ROLE_VIEWER, nullable=False)

    def can_edit(self):
        return self.role == ROLE_ADMIN or self.is_admin


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    qrcode_image = db.Column(db.String(200), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Data/hora de validade no horário de Brasília
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(BR_TZ)  # Horário Brasília
    )

    def is_expired(self):
        if not self.expires_at:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=BR_TZ)
        return datetime.now(BR_TZ) > expires

    def is_available(self):
        return bool(self.active) and not self.is_expired()


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


def ensure_user_role_column():
    """Atualiza banco antigo automaticamente, adicionando a coluna role se não existir."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(user)").fetchall()]
        if "role" not in cols:
            conn.execute("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'viewer'")
            conn.execute("UPDATE user SET role = 'admin' WHERE is_admin = 1")
            conn.execute("UPDATE user SET role = 'viewer' WHERE is_admin = 0 OR is_admin IS NULL")
            conn.commit()
    finally:
        conn.close()


def ensure_link_validity_columns():
    """Atualiza banco antigo automaticamente, adicionando validade e status ativo."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(link)").fetchall()]
        if "active" not in cols:
            conn.execute("ALTER TABLE link ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1")
        if "expires_at" not in cols:
            conn.execute("ALTER TABLE link ADD COLUMN expires_at DATETIME")
        conn.commit()
    finally:
        conn.close()


def parse_datetime_local(value):
    """Converte o campo HTML datetime-local para datetime no horário de Brasília."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M")
        return dt.replace(tzinfo=BR_TZ)
    except ValueError:
        return None


def format_datetime_local(value):
    """Formata datetime para preencher input type=datetime-local."""
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=BR_TZ)
    return value.strftime("%Y-%m-%dT%H:%M")


def valid_links_query():
    """Links ativos e não expirados."""
    now = datetime.now(BR_TZ)
    return Link.query.filter(
        Link.active == True,
        db.or_(Link.expires_at == None, Link.expires_at >= now)
    )


@app.template_filter("datetime_br")
def datetime_br(value):
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=BR_TZ)
    return value.strftime("%d/%m/%Y %H:%M")


def current_user():
    email = session.get("user")
    if not email:
        return None
    return User.query.filter_by(email=email).first()


def context_user_data():
    user = session.get("user")
    role = session.get("role", ROLE_VIEWER)
    can_edit = bool(session.get("can_edit"))
    return {
        "logged_in": bool(user),
        "user": user,
        "role": role,
        "admin": can_edit,       # compatibilidade com templates antigos
        "can_edit": can_edit,
        "is_viewer": role == ROLE_VIEWER,
    }


def editor_required():
    if not session.get("can_edit"):
        flash("Apenas usuários Admin/Editor podem realizar esta ação.", "danger")
        return False
    return True


# ==== Rotas ====
@app.route("/")
def index():
    links = valid_links_query().order_by(Link.created_at.desc()).limit(8).all()
    return render_template("index.html", links=links, **context_user_data())


@app.route("/tv")
def tv():
    """Tela limpa para TV: sem botões de edição, ideal para monitor/TV."""
    links = valid_links_query().order_by(Link.created_at.desc()).limit(8).all()
    return render_template("index.html", links=links, logged_in=True, user="TV", role=ROLE_VIEWER, admin=False, can_edit=False, is_viewer=True, tv_mode=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user"] = user.email
            session["role"] = user.role or (ROLE_ADMIN if user.is_admin else ROLE_VIEWER)
            session["can_edit"] = user.can_edit()
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html", **context_user_data())


@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("index"))


@app.route("/add", methods=["GET", "POST"])
def add_link():
    if not editor_required():
        return redirect(url_for("index"))

    if request.method == "POST":
        if valid_links_query().count() >= 8:
            flash("Limite de 8 links atingido. Exclua um para adicionar outro.", "warning")
            return redirect(url_for("index"))

        title = request.form["title"].strip()
        url = request.form["url"].strip()
        description = request.form.get("description", "").strip()
        expires_at_raw = request.form.get("expires_at", "")
        expires_at = parse_datetime_local(expires_at_raw)
        active = bool(request.form.get("active"))

        if expires_at_raw and not expires_at:
            flash("Data de validade inválida.", "danger")
            return redirect(url_for("add_link"))

        new_link = Link(title=title, url=url, description=description, expires_at=expires_at, active=active)
        db.session.add(new_link)
        db.session.commit()

        qrcode_path = generate_qrcode(new_link.id, url)
        new_link.qrcode_image = qrcode_path
        db.session.commit()

        flash("Link adicionado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("add_link.html", **context_user_data())


@app.route("/edit/<int:link_id>", methods=["GET", "POST"])
def edit_link(link_id):
    if not editor_required():
        return redirect(url_for("index"))

    link = Link.query.get_or_404(link_id)

    if request.method == "POST":
        old_url = link.url
        link.title = request.form["title"].strip()
        link.url = request.form["url"].strip()
        link.description = request.form.get("description", "").strip()
        expires_at_raw = request.form.get("expires_at", "")
        expires_at = parse_datetime_local(expires_at_raw)
        link.active = bool(request.form.get("active"))

        if expires_at_raw and not expires_at:
            flash("Data de validade inválida.", "danger")
            return redirect(url_for("edit_link", link_id=link.id))
        link.expires_at = expires_at

        if old_url != link.url:
            if link.qrcode_image:
                try:
                    os.remove(os.path.join(BASE_DIR, "static", link.qrcode_image))
                except OSError:
                    pass
            link.qrcode_image = generate_qrcode(link.id, link.url)

        db.session.commit()
        flash("Link atualizado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("edit_link.html", link=link, format_datetime_local=format_datetime_local, **context_user_data())


@app.route("/delete/<int:link_id>")
def delete_link(link_id):
    if not editor_required():
        return redirect(url_for("index"))

    link = Link.query.get_or_404(link_id)

    if link.qrcode_image:
        try:
            os.remove(os.path.join(BASE_DIR, "static", link.qrcode_image))
        except OSError:
            pass

    db.session.delete(link)
    db.session.commit()
    flash("Link removido com sucesso!", "info")
    return redirect(url_for("index"))


@app.route("/users")
def users():
    if not editor_required():
        return redirect(url_for("index"))
    users_list = User.query.order_by(User.email.asc()).all()
    return render_template("users.html", users=users_list, **context_user_data())


@app.route("/users/add", methods=["GET", "POST"])
def add_user():
    if not editor_required():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form.get("role", ROLE_VIEWER)
        if role not in (ROLE_ADMIN, ROLE_VIEWER):
            role = ROLE_VIEWER

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.", "warning")
            return redirect(url_for("add_user"))

        user = User(
            email=email,
            password=generate_password_hash(password),
            role=role,
            is_admin=(role == ROLE_ADMIN),
        )
        db.session.add(user)
        db.session.commit()
        flash("Usuário criado com sucesso!", "success")
        return redirect(url_for("users"))

    return render_template("user_form.html", usuario=None, **context_user_data())


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if not editor_required():
        return redirect(url_for("index"))

    usuario = User.query.get_or_404(user_id)

    if request.method == "POST":
        usuario.email = request.form["email"].strip().lower()
        role = request.form.get("role", ROLE_VIEWER)
        if role not in (ROLE_ADMIN, ROLE_VIEWER):
            role = ROLE_VIEWER
        usuario.role = role
        usuario.is_admin = (role == ROLE_ADMIN)

        new_password = request.form.get("password", "").strip()
        if new_password:
            usuario.password = generate_password_hash(new_password)

        db.session.commit()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("users"))

    return render_template("user_form.html", usuario=usuario, **context_user_data())


@app.route("/users/delete/<int:user_id>")
def delete_user(user_id):
    if not editor_required():
        return redirect(url_for("index"))

    usuario = User.query.get_or_404(user_id)
    if usuario.email == session.get("user"):
        flash("Você não pode excluir o usuário que está logado.", "warning")
        return redirect(url_for("users"))

    db.session.delete(usuario)
    db.session.commit()
    flash("Usuário removido com sucesso!", "info")
    return redirect(url_for("users"))


# ==== Inicialização do banco e usuários padrão ====
with app.app_context():
    db.create_all()
    ensure_user_role_column()
    ensure_link_validity_columns()

    admin_email = "admin@fieg.com.br"
    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        admin_user = User(
            email=admin_email,
            password=generate_password_hash("@#$admin123"),
            is_admin=True,
            role=ROLE_ADMIN,
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Usuário admin criado: admin@fieg.com.br / senha: @#$admin123")
    else:
        admin_user.is_admin = True
        admin_user.role = ROLE_ADMIN
        db.session.commit()

    viewer_email = "tv@fieg.com.br"
    if not User.query.filter_by(email=viewer_email).first():
        viewer_user = User(
            email=viewer_email,
            password=generate_password_hash("tv123"),
            is_admin=False,
            role=ROLE_VIEWER,
        )
        db.session.add(viewer_user)
        db.session.commit()
        print("Usuário visualizador criado: tv@fieg.com.br / senha: tv123")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
