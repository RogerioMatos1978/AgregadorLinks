# NOVO: script para rodar o app em modo "produção/rede" usando Waitress em vez
# do servidor de desenvolvimento do Flask (o que aparece no aviso ao rodar
# "python app.py": "This is a development server. Do not use it in a
# production deployment."). O Waitress aguenta várias conexões simultâneas
# com estabilidade — importante aqui porque cada TV/dispositivo conectado
# recarrega a página sozinho a cada 30 segundos.
#
# Uso:
#   python serve.py
#
# Por padrão escuta em 0.0.0.0 (toda a rede local, qualquer dispositivo
# consegue acessar) na porta definida em PORT no seu .env (ou 5001 se não
# definir). Para restringir e voltar a aceitar só este computador, defina
# HOST=127.0.0.1 no .env.
#
# Ver PLANO-REDE.md e NOVIDADES.md para o passo a passo completo de como
# deixar isso rodando sempre ligado na rede (IP fixo, firewall, serviço do
# Windows).

import os

from waitress import serve

from app import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5001))
    print(f"Servindo em http://{host}:{port} (Ctrl+C para parar)")
    serve(app, host=host, port=port)
