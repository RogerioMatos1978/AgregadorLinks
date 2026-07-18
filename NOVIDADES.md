# Novidades desta rodada — pacote de teste

Este é um pacote separado, gerado para você testar antes de decidir aplicar (ou
não) as mudanças no seu repositório. Nada aqui substituiu os arquivos originais.

## Atualização mais recente: preparado para rodar na rede local

Adicionado suporte para acessar o painel e o modo TV de outros dispositivos da
mesma rede (não só do computador onde o app está rodando), com base no
`PLANO-REDE.md` incluído neste pacote:

- **`serve.py`** (novo): sobe o app com **Waitress** em vez do servidor de
  desenvolvimento do Flask — mais estável para atender várias TVs/dispositivos
  ao mesmo tempo. Uso: `python serve.py` (precisa de `pip install -r
  requirements.txt` primeiro, para instalar o Waitress).
- **`HOST`** (novo, no `.env.example`): controla se o servidor aceita conexões
  só deste computador (`127.0.0.1`, padrão — comportamento de sempre) ou de
  qualquer dispositivo da rede (`0.0.0.0`). É preciso trocar esse valor de
  propósito para expor na rede; o padrão continua seguro.
- **`iniciar-rede.bat`** (novo, na raiz do pacote): atalho de duplo clique no
  Windows para subir o app em modo rede sem precisar digitar comandos.
- **`app.py`**: o bloco final (`python app.py`) agora também respeita `HOST`,
  mas continua com padrão `127.0.0.1` — é o `serve.py` que muda o padrão para
  `0.0.0.0`, porque é o script pensado para uso em rede.
- **`PLANO-REDE.md`** (novo): o mapeamento completo do que ainda precisa ser
  configurado fora do código (IP fixo no roteador, firewall do Windows, e
  rodar como serviço do Windows via NSSM) para deixar isso sempre no ar.

O modo TV (`/tv`) continua público, sem exigir login — isso não mudou.

## Rodada anterior: login trocado de e-mail para usuário

O campo de login deixou de ser e-mail e passou a ser um nome de usuário comum
(sem precisar de formato `algo@algo.com`). Isso mexeu em vários pontos:

- **Banco de dados:** a coluna `User.email` virou `User.username`
  (`String(80)`, antes era `String(120)`). Criei a migration
  `migrations/versions/0002_user_username.py` para quem já tinha um banco
  criado pela migration anterior — bancos novos (SQLite criado do zero) já
  nascem com a coluna certa e não precisam rodar nada.
- **Rotas:** `/login`, `/users/add` e `/users/edit` agora recebem `username`
  em vez de `email` no formulário. As mensagens de erro também foram
  ajustadas ("Usuário ou senha inválidos", "Usuário já cadastrado").
- **Variáveis de ambiente:** `ADMIN_EMAIL`/`VIEWER_EMAIL` viraram
  `ADMIN_USERNAME`/`VIEWER_USERNAME` no `.env.example`.
- **Credenciais de teste** (documentadas em comentário dentro de
  `initialize_database()`, em `app.py`, e também nos valores padrão do
  `.env.example`) — troque antes de usar fora do seu computador:

  ```
  usuário: admin   senha: admin12345    (admin/editor)
  usuário: tv      senha: tv12345678    (visualizador)
  ```

- **Templates:** `login.html`, `user_form.html`, `users.html` e o
  `register.html` (que já estava desativado) tiveram o campo/coluna de
  e-mail trocado por usuário.
- **Testes automatizados:** `conftest.py` e `test_app.py` foram atualizados
  para logar com `username`; os 7 testes continuam passando.

Se você já tinha testado a versão anterior deste pacote e criou um banco
SQLite local com login por e-mail, apague esse `links.db` de teste (ou rode
`flask db upgrade` dentro de `linkaggreg/` com o ambiente virtual ativado)
antes de testar esta versão — caso contrário o login vai falhar porque a
coluna no banco antigo ainda se chama `email`.

## O que mudou em `linkaggreg/app.py` (rodada anterior)

**Limite de tentativas de login.** Adicionado `Flask-Limiter`: no máximo 5
tentativas de login por minuto por IP. Depois disso o servidor responde
"429 Too Many Requests" em vez de deixar tentar senha indefinidamente
(proteção básica contra força bruta).

**Validação de URL.** `/add` e `/edit` agora recusam qualquer URL que não
comece com `http://` ou `https://` (antes só existia validação no navegador,
que pode ser contornada). Sem isso, seria possível salvar um link do tipo
`javascript:...` que rodaria código no navegador de quem clicasse.

**Limite de 8 links configurável.** Antes o número 8 estava fixo em dois
lugares do código. Agora vem de uma variável de ambiente `MAX_LINKS`
(continua 8 por padrão).

**SECRET_KEY obrigatória fora do modo de desenvolvimento.** Antes, se você
esquecesse de definir `SECRET_KEY`, o app subia mesmo assim com uma chave
insegura fixa e só um aviso no log. Agora, com `FLASK_DEBUG=false` (o padrão),
o app recusa iniciar e mostra um erro claro explicando o que fazer. Com
`FLASK_DEBUG=true` o comportamento antigo (aviso + chave temporária) continua,
só para não travar quem está testando pela primeira vez.

## O que mudou nos templates

`base.html`: o modo TV recarregava a página duas vezes ao mesmo tempo (por
`<meta refresh>` e por um `setInterval` em JavaScript, fazendo a mesma coisa).
Agora cada modo usa só um mecanismo.

## O que foi adicionado

**Testes automatizados** (`linkaggreg/tests/`) — o projeto não tinha nenhum
teste antes. Cobrem: página inicial carrega, `/add` exige login, login com
credenciais corretas funciona, URL `javascript:` é rejeitada, URL `https://`
válida é aceita, e o limite de tentativas de login bloqueia na 6ª tentativa.
Todos os 7 testes passaram na validação que fiz antes de te entregar isto.

**`requirements-dev.txt`** — dependências só para rodar os testes (`pytest`),
separadas do `requirements.txt` de produção.

## Como testar

```bash
cd linkaggreg
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
copy ..\.env.example ..\.env    # Windows — cp ../.env.example ../.env no Linux/Mac
python app.py
```

O app sobe em `http://localhost:5001` com um banco SQLite novo (não usa o seu
`links.db` de produção — este pacote não trouxe esse arquivo de propósito,
por conter hashes de senha reais). Faça login com `admin` / `admin12345`
(ou os valores que você definiu no `.env`).

Para rodar os testes automatizados:

```bash
pip install -r requirements-dev.txt
pytest
```

## O que NÃO mudou

Estrutura de pastas, CSS e o restante da lógica de links seguem exatamente
como estavam. A única migração de banco necessária é a troca de e-mail por
usuário, descrita acima — o resto do esquema não mudou.

## Se decidir aplicar no projeto real

Compare este `app.py` e `base.html` com os seus (as mudanças estão marcadas
com comentários `NOVO:`) e copie manualmente as partes que quiser manter — ou
me avise que eu aplico direto no seu projeto.
