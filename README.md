# pg-clockify

> Lança suas horas no Clockify conversando com o Claude — direto no **Cowork** (Claude desktop app),
> sobre a sua pasta de projeto local. Cada pessoa usa suas próprias credenciais;
> **nada seu fica no repositório.**

Ferramenta interna da **PG**, desenvolvida pelo time **AI Product Innovation**.

## O que ele faz

- Converte entradas de agenda (ICS) ou descrições livres em lançamentos no **Clockify**.
- Mostra um resumo em **simulação** primeiro — só grava depois da sua confirmação.
- **Aprende** suas atividades recorrentes (ex.: "daily do projeto X" → projeto/tarefa certos).
- Lança **um dia** ou **um período** de uma vez (ótimo para fechar o mês retroativo).
- Mostra **relatórios** das suas horas — **diário** (dia a dia de um mês) ou **mensal** (vários meses).

## Pré-requisito

O **Claude desktop app** ("Cowork") com acesso à pasta do seu projeto.
Nenhuma outra dependência: a CLI Python usa apenas stdlib.

## Instalar (3 passos no Cowork)

```
/plugin marketplace add https://github.com/PG-Skills/clockify-plugin.git
/plugin install clockify-cowork@pg-clockify
```

Na primeira sessão, use `/clockify` para conectar:

```
/clockify
```

O plugin pergunta sua API key do Clockify, valida e salva em `.clockify/credentials.json`
(pasta do projeto, nunca versionado). Pronto — um passo único.

## Usar no dia a dia

| Comando | O que faz |
|---|---|
| `/clockify` | Verifica a conexão / reconfigura credenciais (e oferece conectar a agenda do Outlook). |
| `/clockify-tracking` | Lança no Clockify — você escolhe na conversa **hoje**, um **dia** ou um **período**. |
| `/clockify-report` | **Relatório** das horas — **diário** (um mês, dia a dia) ou **mensal** (intervalo de meses, máx 12). |

Em qualquer fluxo, o Claude mostra um resumo do que vai lançar e espera sua confirmação
antes de gravar. Lançamento duplicado é evitado automaticamente.

## Onde ficam os seus dados

Tudo é **por-projeto e fica fora do repositório** (em `.clockify/` na pasta aberta no Cowork):

- `credentials.json` (modo 0600) — API key, workspace_id/user_id em cache, ICS URL opcional.
- `prefs.json` — atividade padrão + learned (palavra-chave → projeto/tarefa/tag).

`.clockify/` deve estar no `.gitignore` do seu projeto — o plugin avisa se não estiver.
**Nenhum** dado de cliente nem credencial vai para este repositório.

## Problemas comuns

- **"Sem credenciais"** → rode `/clockify` para configurar (ou defina `CLOCKIFY_DIR` + `credentials.json` manualmente).
- **Lançou no projeto/tarefa errado** → ensine a atividade certa: o plugin pergunta e passa a reconhecer sozinho.
- **O mesmo nome de tarefa existe em mais de um projeto** → qualifique pelo projeto quando o plugin perguntar.

---

## Para mantenedores / desenvolvedores

O "cérebro" é a skill conversacional (`clockify-cowork/skills/clockify-tracking/SKILL.md`);
o "IO confiável" é uma CLI Python zero-dependência (`clockify-cowork/scripts/clockify_cli/`).

```bash
cd clockify-cowork/scripts
python3 -m pytest -q        # 90 testes, stdlib only, sem uv
```

Política de versão e processo de release: ver **`MAINTAINER.md`**.

---

<sub>Desenvolvido pelo time **AI Product Innovation** da PG.</sub>
