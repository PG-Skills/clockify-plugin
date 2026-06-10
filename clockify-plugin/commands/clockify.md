---
description: Confere a conexão com o Clockify e mostra o que está configurado
---

**Língua — NUNCA assuma português.** Fale SEMPRE a língua da pessoa. Este comando costuma ser
invocado sem texto nenhum: nesse caso, use a língua em que a conversa/interface do Claude dela
está, e ajuste assim que ela escrever. Todas as frases entre aspas abaixo são modelos em pt-BR —
**traduza** ao falar.

**Passo 1 — projeto (pasta local).** Antes de tudo, confirme que a pessoa está num projeto:
rode `pwd`; se for um lugar temporário (`/sessions/...` sem `/mnt/`) ou `CLAUDE_PROJECT_DIR`
estiver vazio, oriente a pessoa, em linguagem leiga, a clicar em **"Trabalhar em um projeto"**
e criar/escolher uma pasta (a config não persiste sem isso) — e **pare** até existir. (Mesma
verificação da skill `clockify-tracking`.)

**Como rodar o CLI:** se `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli ...` não rodar no
terminal (sandbox não enxerga o plugin), use a cópia local **condicionada à versão** como na
skill `clockify-tracking`, seção "Como rodar o CLI" (compara a `version` do plugin com o marcador
`.clockify/bin/.cli-version`; só recopia quando muda; roda com `python3 -B`).

**Passo 2 — Setup (só o `/clockify` faz isso).** O setup é **chave do Clockify + agenda do
Outlook (obrigatória)**. `/clockify-tracking` e `/clockify-report` só rodam depois disso. Comece
com `... setup-status` (local, sem rede):
- `configured: true` → já está pronto: confirme a conta (rode `... whoami`, use o `name`) e vá
  pro Passo 3. (Só refaça abaixo se a pessoa pediu pra trocar a chave ou reconectar a agenda.)
- Senão, faça **2a** e/ou **2b** conforme o que falta.

**2a — Chave do Clockify** (se `has_key: false`, ou a pessoa quer trocar a chave):
1. Peça, leigo: *"Cola aqui sua chave do Clockify — você pega em
   https://app.clockify.me/manage-api-keys (Perfil → Preferências → Avançado → 'Gerenciar
   chaves de API')."*
2. **Proteja a credencial ANTES de gravar:** olhe o `.gitignore` da raiz do projeto (ferramenta
   de arquivo); se existir e não tiver `.clockify/`, acrescente; se não existir, crie um com
   `.clockify/`.
3. **Grave** `.clockify/credentials.json` com
   `{"api_key":"<a chave>","ics_url":null,"workspace_id":null,"user_id":null}` (Write).
4. Rode `... whoami`. `{"error":"INVALID_KEY"}` → *"Essa chave não funcionou, confere e tenta de
   novo."* (repita). `{"error":"HTTP_ERROR",...}` → diga que o Clockify não respondeu agora e
   ofereça tentar de novo (não trate como chave inválida). `{"error":"NETWORK_BLOCKED",...}` →
   **a chave NÃO é o problema**: o Cowork deste computador está bloqueando meu acesso à
   internet. Diga leigo: permitir quando o Cowork pedir permissão de rede (ou nas
   configurações do Cowork); em computador de empresa, o administrador talvez precise liberar
   `api.clockify.me`. Não peça outra chave; **nunca** mande a pessoa pro terminal. Sucesso
   (`{"name":...}`) → cumprimente com o nome; `workspace_id`/`user_id` ficam em cache.

**2b — Agenda do Outlook (OBRIGATÓRIA)** (se `has_ics: false`): conecte agora — **não é
opcional, não ofereça pular**. Guie:
*"Agora vou conectar sua agenda do Outlook — é necessário pra eu trazer suas reuniões
automaticamente na hora de lançar. Abra
https://outlook.cloud.microsoft/mail/options/calendar/SharedCalendars e use **Publicar
calendário** (NÃO 'Compartilhar' — só o Publicar gera o link). Copie o link que termina em
**.ics** e cole aqui."*
Quando colar: **reescreva** `.clockify/credentials.json` mantendo todos os campos existentes
(`api_key`, `workspace_id`, `user_id`) e preenchendo `"ics_url"` (ferramenta de arquivo). Valide
com `... agenda --date <hoje>`: se vier `{"error":"ICS_ERROR",...}` ou `{"ics": false}`, explique
simples que o link não funcionou (confirme *Publicar* e o `.ics`) e **peça de novo** — repita até
validar. Se vier `{"error":"NETWORK_BLOCKED",...}`, **o link NÃO é o problema** — o Cowork deste
computador está bloqueando o acesso à internet: NÃO peça o link de novo; oriente como no Passo 2a
(permitir a rede no Cowork / falar com o administrador) e retome a validação depois. **Não vá pro Passo 3 sem ICS válido.** **Nunca mostre JSON/IDs nem despeje eventos.**
(Opcional: rode `... prefs get` e conte, leigo, se há atividade padrão e quantas aprendidas.)

**Passo 3 — Manual rápido (boas-vindas).** Sempre que o Passo 2 terminar com a conexão OK
(depois de tratar a agenda), **apresente um mini-manual** ensinando a pessoa leiga a usar o
plugin: leia `${CLAUDE_PLUGIN_ROOT}/skills/clockify-tracking/references/manual-rapido.md`
(ferramenta de arquivo) e apresente-o **adaptado à língua da pessoa**, seguindo as regras de
lá (cada exemplo começa com a skill/comando; o exemplo de "hoje" reflete que eu puxo da agenda
do Outlook primeiro; nada de JSON/IDs). Mantenha curto — é um onboarding de ~20 segundos.
