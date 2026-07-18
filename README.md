# Agregador de Links - Py 3.13

Aplicação Flask para cadastrar, exibir e gerenciar até 8 links (com QR Code) em um painel — pensada para telas de TV/mural digital.

## Instalação

```bash
# 1. Criar o ambiente virtual
python -m venv venv

# 2. Ativar o ambiente virtual
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instalar as dependências
cd linkaggreg
pip install -r requirements.txt
```

## Configuração

Copie `.env.example` para `.env` na raiz do projeto e ajuste os valores:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Defina principalmente `SECRET_KEY`, `ADMIN_PASSWORD` e `VIEWER_PASSWORD` com valores próprios — os padrões do `.env.example` são apenas para desenvolvimento local e não devem ser usados em produção.

## Executar

```bash
python app.py
```

O app inicia em `http://localhost:5001`. Por padrão cria dois usuários (se ainda não existirem): um admin (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) e um visualizador (`VIEWER_USERNAME`/`VIEWER_PASSWORD`).

## Rodar na rede local (para TVs e outros dispositivos)

Para outros aparelhos da mesma rede acessarem o painel (ex.: uma Smart TV abrindo
o modo `/tv`), use o Waitress em vez do servidor de desenvolvimento:

```bash
python serve.py
```

Isso escuta em `0.0.0.0` (toda a rede) na porta definida em `PORT`. Ainda é preciso
fixar o IP do computador no roteador e liberar a porta no firewall do Windows — o
passo a passo completo está em `PLANO-REDE.md`.

## Estrutura

- `app.py` — aplicação Flask (rotas, modelos, autenticação)
- `serve.py` — sobe o app com Waitress, para uso na rede local (ver acima)
- `templates/` — páginas HTML (Jinja2)
- `static/` — CSS e QR Codes gerados
- `migrations/` — migrações de banco (Flask-Migrate/Alembic)
- `tests/` — testes automatizados (pytest)

## Notas de segurança

Este projeto usa proteção CSRF (Flask-WTF) em todos os formulários, cookies de sessão com `HttpOnly`/`SameSite=Lax`, e nenhuma senha fica fixa no código-fonte — tudo vem de variáveis de ambiente. Veja `CORRECOES.md` para o histórico completo de correções aplicadas.
