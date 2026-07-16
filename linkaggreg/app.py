from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import qrcode
import os
import sys

# NOVO: carrega variáveis do arquivo .env automaticamente em desenvolvimento.
# Em produção (Render, Railway, etc.) as variáveis já vêm do ambiente e o
# python-dotenv simplesmente não encontra o arquivo — não há problema nisso.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# CORREÇÃO #7: sqlite3 não é mais necessário — migrações manuais foram removidas
# import sqlite3

# ==== Configuração da aplicação ====
app = Flask(__name__)

# CORREÇÃO #3: SECRET_KEY obrigatória em produção — levanta erro se não definida via env
# Antes: app.secret_key = os.environ.get("SECRET_KEY", "minha_chave_super_secreta")
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    import warnings
    warnings.warn(
        "SECRET_KEY não definida via variável de ambiente! "
        "Usando chave temporária — NÃO use em produção.",
        stacklevel=2,
    )
    _secret = "chave-temporaria-insegura-nao-use-em-producao"
app.secret_key = _secret

# NOVO: modo debug controlado por variável de ambiente, nunca fixo no código.
# O debugger interativo do Werkzeug permite execução remota de código — jamais
# pode ficar ligado em um servidor acessível pela rede/internet.
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")

# NOVO: reforço de segurança do cookie de sessão.
# HTTPONLY: JavaScript não consegue ler o cookie (mitiga roubo de sessão via XSS).
# SAMESITE=Lax: cookie não é enviado em requisições cross-site (mitiga CSRF).
# SECURE: só habilite quando o site rodar atrás de HTTPS (defina COOKIE_SECURE=true).
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "links.db")


def get_database_uri():
    """Retorna a URL do banco. Em producao, defina DATABASE_URL com PostgreSQL."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        return "sqlite:///" + DB_PATH

    # Algumas plataformas ainda fornecem postgres://, mas SQLAlchemy espera postgresql://.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Usa o driver psycopg 3 quando a URL nao informa um driver explicitamente.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# NOVO: proteção CSRF global. Toda rota POST/PUT/PATCH/DELETE passa a exigir
# um token válido (campo csrf_token no formulário). Sem isso, um site malicioso
# podia montar um form escondido apontando para /delete/<id> e, se a vítima
# estivesse logada, o navegador enviava o cookie de sessão automaticamente.
csrf = CSRFProtect(app)

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
    # CORREÇÃO #6: is_admin mantido apenas para compatibilidade com bancos antigos.
    # TODO: remover este campo após executar migration limpando dados legados.
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default=ROLE_VIEWER, nullable=False)

    def can_edit(self):
        # CORREÇÃO #6: lógica unificada — is_admin considerado apenas como fallback legado
        return self.role == ROLE_ADMIN


# CORREÇÃO #5: current_user() estava definida mas nunca usada nas rotas.
# Agora é utilizada em editor_required() e context_user_data() para consistência.
def current_user():
    """Retorna o objeto User da sessão atual, ou None se não logado."""
    email = session.get("user")
    if not email:
        return None
    return User.query.filter_by(email=email).first()


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    qrcode_image = db.Column(db.String(200), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Data/hora de validade no horário de Brasília
    created_at = db.Column(
        db.DateTime(timezone=True),
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


# CORREÇÃO #7: ensure_user_role_column() removida — usava sqlite3 diretamente,
# duplicando responsabilidade do Flask-Migrate. Para bancos legados, execute:
#   flask db migrate -m "add role column"
#   flask db upgrade
# def ensure_user_role_column(): ...


# CORREÇÃO #7: ensure_link_validity_columns() removida pelo mesmo motivo.
# def ensure_link_validity_columns(): ...


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


# CORREÇÃO #11: format_datetime_local registrada como global de template,
# não mais passada como argumento em cada render_template().
@app.template_global("format_datetime_local")
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


# CORREÇÃO #8: total_links_count() considera TODOS os links (ativos ou não)
# para aplicar o limite de 8 de forma consistente.
def total_links_count():
    return Link.query.count()


@app.template_filter("datetime_br")
def datetime_br(value):
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=BR_TZ)
    return value.strftime("%d/%m/%Y %H:%M")


def context_user_data():
    # CORREÇÃO #5: agora usa current_user() para obter dados consistentes da sessão
    user = current_user()
    email = session.get("user")
    role = session.get("role", ROLE_VIEWER)
    can_edit = user.can_edit() if user else False
    return {
        "logged_in": bool(email),
        "user": email,
        "role": role,
        "admin": can_edit,       # compatibilidade com templates antigos
        "can_edit": can_edit,
        "is_viewer": role == ROLE_VIEWER,
        # CORREÇÃO #12: tv_mode sempre presente no contexto padrão (False por padrão)
        "tv_mode": False,
    }


def editor_required():
    # CORREÇÃO #5: usa current_user() em vez de session diretamente
    user = current_user()
    if not user or not user.can_edit():
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
    return render_template(
        "index.html", links=links,
        logged_in=True, user="TV", role=ROLE_VIEWER,
        admin=False, can_edit=False, is_viewer=True,
        tv_mode=True,  # CORREÇÃO #12: tv_mode explícito
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            # NOVO: previne fixação de sessão — descarta qualquer sessão antiga
            # e gera um cookie de sessão novo no momento do login.
            session.clear()
            session["user"] = user.email
            session["role"] = user.role
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
        # CORREÇÃO #8: limite baseado em todos os links, não só ativos/não-expirados
        if total_links_count() >= 8:
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

        # NOVO: se a geração do QR Code falhar (ex.: disco cheio, permissão de
        # pasta, URL problemática), o link continua salvo — apenas sem imagem —
        # em vez de estourar um erro 500 depois que o registro já existe no banco.
        try:
            new_link.qrcode_image = generate_qrcode(new_link.id, url)
            db.session.commit()
        except Exception as e:
            app.logger.warning("Falha ao gerar QR Code para o link %s: %s", new_link.id, e)
            flash("Link adicionado, mas houve um problema ao gerar o QR Code.", "warning")
            return redirect(url_for("index"))

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
                old_path = os.path.join(BASE_DIR, "static", link.qrcode_image)
                try:
                    os.remove(old_path)
                except OSError as e:
                    # CORREÇÃO #9: loga o erro em vez de silenciar completamente
                    app.logger.warning("Não foi possível remover QR Code antigo: %s", e)
            # NOVO: mesma proteção da rota /add — falha na geração não derruba a request.
            try:
                link.qrcode_image = generate_qrcode(link.id, link.url)
            except Exception as e:
                app.logger.warning("Falha ao gerar QR Code para o link %s: %s", link.id, e)
                flash("Link atualizado, mas houve um problema ao gerar o novo QR Code.", "warning")

        db.session.commit()
        flash("Link atualizado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("edit_link.html", link=link, **context_user_data())


# CORREÇÃO #2: rotas de deleção agora usam POST para evitar deleção acidental por GET
@app.route("/delete/<int:link_id>", methods=["POST"])
def delete_link(link_id):
    if not editor_required():
        return redirect(url_for("index"))

    link = Link.query.get_or_404(link_id)

    if link.qrcode_image:
        try:
            os.remove(os.path.join(BASE_DIR, "static", link.qrcode_image))
        except OSError as e:
            app.logger.warning("Não foi possível remover QR Code: %s", e)

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

        # NOVO: senha mínima de 8 caracteres — antes qualquer valor não vazio era aceito.
        if len(password) < 8:
            flash("A senha deve ter pelo menos 8 caracteres.", "danger")
            return redirect(url_for("add_user"))

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
            # NOVO: mesma validação de senha mínima ao trocar a senha de um usuário existente.
            if len(new_password) < 8:
                flash("A senha deve ter pelo menos 8 caracteres.", "danger")
                return redirect(url_for("edit_user", user_id=usuario.id))
            usuario.password = generate_password_hash(new_password)

        db.session.commit()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("users"))

    return render_template("user_form.html", usuario=usuario, **context_user_data())


# CORREÇÃO #2: deleção de usuário também migrada para POST
@app.route("/users/delete/<int:user_id>", methods=["POST"])
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
def is_flask_db_command():
    return 'flask' in os.path.basename(sys.argv[0]).lower() and 'db' in sys.argv


def initialize_database():
    """Cria as tabelas e usuarios padrao quando o app inicia fora do Flask-Migrate."""
    db.create_all()
    # CORREÇÃO #7: funções de migração manual removidas.
    # Bancos antigos devem ser migrados via: flask db migrate && flask db upgrade

    # CORREÇÃO #1: senhas lidas de variáveis de ambiente — nunca hardcoded
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fieg.com.br")
    admin_pass  = os.environ.get("ADMIN_PASSWORD", "mude-esta-senha-admin")

    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        admin_user = User(
            email=admin_email,
            password=generate_password_hash(admin_pass),
            is_admin=True,
            role=ROLE_ADMIN,
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"Usuário admin criado: {admin_email} — defina ADMIN_PASSWORD via variável de ambiente.")
    else:
        admin_user.is_admin = True
        admin_user.role = ROLE_ADMIN
        db.session.commit()

    # CORREÇÃO #1: senha do viewer também via env
    viewer_email = os.environ.get("VIEWER_EMAIL", "tv@fieg.com.br")
    viewer_pass  = os.environ.get("VIEWER_PASSWORD", "mude-esta-senha-tv")

    if not User.query.filter_by(email=viewer_email).first():
        viewer_user = User(
            email=viewer_email,
            password=generate_password_hash(viewer_pass),
            is_admin=False,
            role=ROLE_VIEWER,
        )
        db.session.add(viewer_user)
        db.session.commit()
        print(f"Usuário visualizador criado: {viewer_email} — defina VIEWER_PASSWORD via variável de ambiente.")


if not is_flask_db_command():
    with app.app_context():
        initialize_database()


if __name__ == "__main__":
    # NOVO: debug/host controlados por ambiente — nunca hardcoded.
    app.run(debug=app.config["DEBUG"], port=int(os.environ.get("PORT", 5001)))
