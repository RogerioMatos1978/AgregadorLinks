# Plano: rodar o Agregador de Links na rede local

Com base no que você definiu: acesso por **IP + porta**, modo TV **continua público**
(sem login), e o servidor roda num **PC dedicado, sempre ligado, como serviço do
Windows**. Este documento mapeia o que muda, em que ordem, e o que é viável sem
grandes riscos.

## Resumo da viabilidade

É totalmente viável e não exige reescrever nada do projeto. A mudança de código é
pequena — hoje o `app.run()` no fim do `app.py` não define o parâmetro `host`, então
o Flask escuta só em `127.0.0.1` (localhost), invisível para o resto da rede. O
trabalho maior não é código, é infraestrutura ao redor dele: IP fixo, firewall,
servidor de produção no lugar do servidor de desenvolvimento do Flask, e o serviço
do Windows para manter tudo rodando sozinho.

## 1. IP fixo para o PC servidor

Como o acesso será por IP + porta (ex: `http://192.168.1.50:5001`), esse IP não pode
mudar — senão todo mundo perde o endereço a cada reinício do roteador. A forma mais
confiável é reservar o IP no próprio roteador (DHCP reservation / IP reservado),
vinculando-o ao endereço MAC da placa de rede do PC. Isso é configurado no painel de
administração do roteador, não no Windows, e evita conflito de IP com outros
aparelhos. Configurar um IP estático diretamente no Windows também funciona, mas é
mais fácil de gerar conflito se dois dispositivos acabarem com o mesmo endereço.

## 2. Trocar o servidor de desenvolvimento por um servidor de produção

O aviso que aparece no terminal (`WARNING: This is a development server...`) existe
porque o servidor embutido do Flask não foi feito para atender vários clientes ao
mesmo tempo com estabilidade — e aqui teremos isso: cada TV/dispositivo conectado
recarrega a página sozinho a cada 30 segundos. Antes de expor na rede, vale trocar
para o **Waitress**, um servidor WSGI leve, mantido pela mesma equipe do Flask, que
roda bem no Windows sem precisar de configuração complexa (diferente do Gunicorn,
que não roda nativamente no Windows).

Isso já foi aplicado: `waitress` está no `requirements.txt`, e agora existe um
`serve.py` — rode `python serve.py` em vez de `python app.py` para subir com
Waitress. O `HOST=0.0.0.0` (definido no `.env`) é o que faz o servidor aceitar
conexões vindas de qualquer dispositivo da rede, não só da própria máquina — essa é
a mudança que resolve o problema original de só funcionar em localhost. Por
segurança, o padrão do `.env.example` continua `HOST=127.0.0.1` (só este
computador); é preciso trocar para `0.0.0.0` de propósito quando for expor na rede.

## 3. Liberar a porta no firewall do Windows

Por padrão, o Firewall do Windows bloqueia conexões de entrada não solicitadas.
É preciso criar uma regra de entrada liberando a porta escolhida (5001, ou 80 se
quiser evitar digitar a porta no navegador) para tráfego TCP. Sem isso, mesmo com o
servidor rodando em `0.0.0.0`, outros dispositivos da rede não conseguem alcançá-lo.

## 4. Rodar como serviço do Windows

Para o app sobreviver a reinícios do PC e não depender de alguém deixar um terminal
aberto, a rota mais confiável é o **NSSM** (Non-Sucking Service Manager), uma
ferramenta gratuita que registra qualquer comando como serviço do Windows — com
início automático no boot e reinício automático se o processo cair. O serviço seria
configurado para rodar o comando do Waitress (passo 2), com o diretório de trabalho
apontando para a pasta `linkaggreg`.

Uma alternativa mais simples, sem instalar nada extra, é o Agendador de Tarefas do
Windows com um gatilho "ao iniciar o sistema" — funciona, mas não reinicia sozinho
se o processo travar ou fechar por engano, então é uma opção menos robusta que o
NSSM para um serviço que precisa ficar sempre no ar.

## 5. Segurança ao sair do localhost

Expor o app na rede local aumenta a superfície de ataque, mesmo sendo uma rede
"de confiança". Vale garantir três coisas antes de ativar: a `SECRET_KEY` do `.env`
precisa ser uma chave real (gerada por você), não a de teste que estava no pacote de
testes; a senha do usuário `admin` também precisa ser trocada da senha de teste
(`admin12345`) para uma senha real; e a porta escolhida não deve ser redirecionada
no roteador para a internet (nenhum "port forwarding") — o objetivo é só a rede
local, não acesso público externo. O cookie de sessão continua sem `Secure` (porque
não há HTTPS na rede local), então login e senha trafegam sem criptografia dentro da
própria rede — aceitável para uma rede doméstica/interna confiável, mas é bom você
estar ciente disso.

## 6. Como fica o uso no dia a dia

O admin acessa `http://<IP-do-servidor>:5001/login`, entra com o usuário e senha de
administrador, e usa a tela normal para adicionar, editar e excluir links — nada
muda aqui. Qualquer TV ou dispositivo na mesma rede acessa
`http://<IP-do-servidor>:5001/tv` diretamente, sem precisar de login, e a página se
atualiza sozinha a cada 30 segundos mostrando os links mais recentes — esse
comportamento já existe no código hoje, não precisa de nenhuma alteração. Se uma
Smart TV tiver navegador embutido, basta deixar essa URL salva como favorito ou
página inicial; se não tiver, um Chromecast, Fire TV Stick ou mini PC conectado à
TV, configurado para abrir essa URL em tela cheia ao ligar, resolve.

## Ordem prática de execução

1. Reservar o IP fixo do PC servidor no roteador.
2. No `.env`, defina `HOST=0.0.0.0` e confira `PORT` (padrão 5001). Dentro de
   `linkaggreg`, com o ambiente virtual ativado, rode `pip install -r
   requirements.txt` (para instalar o Waitress) e teste com `python serve.py`.
3. Trocar a `SECRET_KEY` e a senha do `admin` no `.env` por valores reais.
4. Liberar a porta 5001 no Firewall do Windows (regra de entrada).
5. Testar o acesso de outro aparelho na mesma rede (celular, notebook) pelo IP.
6. Registrar como serviço do Windows via NSSM, apontando para
   `python serve.py` (ou o `iniciar-rede.bat` incluído no pacote), com início
   automático.
7. Configurar cada TV (ou o aparelho conectado a ela) para abrir
   `http://<IP>:5001/tv` automaticamente ao ligar.

## O que já foi aplicado no pacote de teste

`waitress` no `requirements.txt`, o script `serve.py` (roda o app com Waitress),
a variável `HOST` no `.env.example` (documentada, padrão seguro `127.0.0.1`), e um
atalho `iniciar-rede.bat` para abrir com duplo clique no Windows. Os passos 1
(IP fixo no roteador), 4 (firewall) e 6 (serviço do Windows/NSSM) continuam sendo
configuração fora do código — dependem do seu roteador e do seu Windows, não têm
como ser "aplicados" por mim automaticamente. Me avise se quiser o passo a passo
detalhado de algum desses três na hora de configurar.
