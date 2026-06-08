---
description: Confere a conexão com o Clockify e mostra o que está configurado
---

**Passo 1 — projeto (pasta local).** Antes de tudo, confirme que a pessoa está num projeto:
rode `pwd`; se for um lugar temporário (`/sessions/...` sem `/mnt/`) ou `CLAUDE_PROJECT_DIR`
estiver vazio, oriente a pessoa, em linguagem leiga, a clicar em **"Trabalhar em um projeto"**
e criar/escolher uma pasta (a config não persiste sem isso) — e **pare** até existir. (Mesma
verificação da skill `clockify-tracking`.)

**Como rodar o CLI:** se `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli ...` não rodar no
terminal (sandbox não enxerga o plugin), use a cópia local **atualizada** como na skill
`clockify-tracking`, seção "Como rodar o CLI" (sempre `rm -rf .clockify/bin/clockify_cli` +
recopiar do plugin + `python3 -B`) — nunca reuse cópia velha.

**Passo 2 — conexão.** Com projeto confirmado, rode
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli whoami`.
- `{"error":"NO_KEY"}` → use a skill **clockify-tracking** para conectar (peça a chave —
  disponível em https://app.clockify.me/manage-api-keys, Perfil → Preferências → Avançado →
  "Gerenciar chaves de API" — e grave `.clockify/credentials.json`).
- `{"error":"INVALID_KEY"}` → avise, em linguagem leiga, que a chave não funcionou.
- `{"error":"HTTP_ERROR",...}` → diga que o Clockify não respondeu agora; ofereça tentar de novo.
- Sucesso → confirme a conta conectada (use o `name`). Em seguida rode
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli prefs get` e conte, em linguagem
  natural, se há atividade padrão e quantas atividades aprendidas existem. Depois rode
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli agenda --date <hoje>`: se `ics` for
  `true`, diga "agenda do Outlook conectada". Se `false`, **não apenas mencione — ofereça
  conectar**: *"Sua agenda do Outlook não está conectada. Quer conectar pra eu já trazer suas
  reuniões do dia automaticamente? É opcional."* Se a pessoa topar, conduza pelo passo de
  Agenda da skill **clockify-tracking** (link do Outlook em **Publicar calendário**, NÃO
  Compartilhar). **Nunca mostre JSON/IDs nem despeje os eventos.**

**Passo 3 — Manual rápido (boas-vindas).** Sempre que o Passo 2 terminar com a conexão OK
(depois de tratar a agenda), **apresente um mini-manual** ensinando a pessoa leiga a usar o
plugin: leia `${CLAUDE_PLUGIN_ROOT}/skills/clockify-tracking/references/manual-rapido.md`
(ferramenta de arquivo) e apresente-o **adaptado à língua da pessoa**, seguindo as regras de
lá (cada exemplo começa com a skill/comando; o exemplo de "hoje" reflete que eu puxo da agenda
do Outlook primeiro; nada de JSON/IDs). Mantenha curto — é um onboarding de ~20 segundos.
