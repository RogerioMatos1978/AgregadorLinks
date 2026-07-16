# Análise e correções — AgregadorLinks

Revisão do repositório `RogerioMatos1978/AgregadorLinks` (branch `master`). O código já trazia 12 correções anteriores documentadas em comentários `CORREÇÃO #N` dentro do próprio `app.py` — essa base estava sólida. As mudanças abaixo tratam do que ainda restava.

## O que foi corrigido nesta rodada

**CSRF em todos os formulários.** Nenhum formulário POST (login, adicionar/editar/excluir link, criar/editar/excluir usuário) tinha proteção contra CSRF. Um site malicioso podia montar um formulário oculto apontando para `/delete/<id>` e, se a vítima estivesse logada como admin, o navegador enviava o cookie de sessão automaticamente e o link era apagado sem o usuário perceber. Adicionei `Flask-WTF` (`CSRFProtect`) no `app.py` e um campo `csrf_token` oculto em cada `<form>`.

**Modo debug fixo no código.** `app.run(debug=True, ...)` estava hardcoded. Se esse código fosse parar em produção, o debugger interativo do Werkzeug fica acessível a qualquer visitante e permite executar código arbitrário no servidor a partir da página de erro. Agora `debug` vem da variável `FLASK_DEBUG` (padrão `false`).

**Cookie de sessão sem reforço.** Configurei `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE=Lax` e `SESSION_COOKIE_SECURE` (controlável via `COOKIE_SECURE`, ligue quando estiver atrás de HTTPS). Isso reduz o risco de roubo de sessão via XSS e de envio do cookie em requisições cross-site.

**Fixação de sessão no login.** Adicionei `session.clear()` antes de gravar a nova sessão em `/login`, para não reaproveitar um session ID que possa ter sido definido antes da autenticação.

**Falha na geração de QR Code derrubava a request.** Em `/add` e `/edit`, se `qrcode.make()`/`img.save()` falhasse (disco cheio, permissão, etc.), o link já tinha sido salvo no banco mas a request estourava um erro 500 — o usuário via uma tela de erro sem saber se o link foi salvo. Agora isso é tratado com `try/except`: o link fica salvo, o usuário recebe um aviso claro, e o erro vai para o log.

**Senha de usuário sem validação mínima.** `/users/add` e `/users/edit` aceitavam qualquer senha não vazia (até 1 caractere). Adicionei validação de 8 caracteres mínimos no servidor e `minlength="8"` no formulário.

**Banco de dados versionado no Git.** `linkaggreg/links.db` está commitado no repositório — isso inclui hashes de senha reais assim que o app roda em produção, além de inflar o histórico do Git a cada alteração. Não havia `.gitignore` no projeto. Criei um `.gitignore` cobrindo `*.db`, `.env`, `venv/`, `__pycache__/`, QR Codes gerados em runtime, `.idea/` e `.vscode/`.

**Dependências e configuração.** Adicionei `Flask-WTF` e `python-dotenv` ao `requirements.txt`, e `FLASK_DEBUG`/`COOKIE_SECURE`/`PORT` ao `.env.example`. `python-dotenv` carrega o `.env` automaticamente ao rodar localmente (opcional — se não estiver instalado, o app segue funcionando via variáveis de ambiente do sistema).

**Reforço leve em templates.** Adicionei `rel="noopener noreferrer"` ao link externo de cada card em `index.html` (o `target="_blank"` sem isso permite que a página aberta manipule a aba de origem via `window.opener`).

## Ação manual necessária: remover o banco de dados do histórico do Git

Eu não tenho acesso de escrita ao seu repositório (só consegui ler os arquivos), então as correções estão nos arquivos que estou te entregando — você precisa aplicá-las no seu repositório local. Para o `links.db` especificamente, tirar do `.gitignore` daqui pra frente não apaga o que já foi commitado antes. Rode isto na sua máquina, dentro da pasta do projeto:

```bash
git rm --cached linkaggreg/links.db
git add .gitignore
git commit -m "Remove banco de dados do versionamento e adiciona .gitignore"
git push
```

Isso remove o arquivo do commit mais recente, mas ele continua nos commits antigos do histórico. Se esse banco já teve senhas reais de produção, o ideal é **trocar a `SECRET_KEY` e as senhas de admin/viewer** — a exposição histórica não é desfeita só por isso. Reescrever o histórico do Git (`git filter-repo` ou BFG Repo-Cleaner) é possível, mas é uma operação destrutiva que reescreve hashes de commit; avise se quiser um passo a passo.

## O que ficou de fora (por decisão, não por esquecimento)

`register.html` existe mas nenhuma rota `/register` usa esse template — o autocadastro público foi desativado intencionalmente (ver nota em `menu.html`, já documentada no código anterior). O template ficou órfão; pode ser removido com segurança se não for reativado.

Não adicionei rate limiting no `/login` (proteção contra força bruta) nem 2FA — são melhorias legítimas, mas exigem uma dependência nova (`Flask-Limiter`) e uma decisão de produto sobre o comportamento esperado (bloqueio temporário? captcha?). Posso implementar se você quiser.

## Como aplicar

1. Baixe os arquivos entregues (pasta `AgregadorLinks`).
2. Copie sobre o seu clone local do repositório (ou compare arquivo a arquivo — os comentários `NOVO:` marcam o que mudou).
3. Rode `pip install -r linkaggreg/requirements.txt` para instalar `Flask-WTF` e `python-dotenv`.
4. Crie seu `.env` a partir do `.env.example`.
5. Execute `git rm --cached linkaggreg/links.db` conforme acima antes de commitar.
6. Teste localmente (`python app.py`) e depois `git add`, `git commit`, `git push`.
