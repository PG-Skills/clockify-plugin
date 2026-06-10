# Instalar o Clockify Plugin no Cowork

> Manual rápido — leva ~2 minutos e você só faz isso **uma vez**.
> **Pré-requisito:** Claude desktop app ("Cowork") instalado.

## Passo a passo

1. **Adicionar o marketplace**
   No Cowork, vá em **Customize → + → Criar plugin → Adicionar marketplace** e cole a URL:
   ```
   https://github.com/PG-Skills/clockify-plugin
   ```

2. **Instalar e ligar a sincronização**
   Clique em **Instalar** no `clockify-plugin`. Depois, nos **3 pontinhos (···)** do plugin,
   habilite **"Sincronizar automaticamente"** — assim você sempre recebe a última versão.

3. **Criar uma pasta local**
   Crie uma pasta em algum lugar da sua máquina (pode ser qualquer uma; sugestão: **"Clockify Plugin"**).
   As skills **rodam sempre nessa pasta**, porque guardam sua configuração num arquivo local ali.
   Sempre abra essa **mesma pasta** no Cowork.

4. **Conectar (setup inicial)**
   Abra uma sessão **nessa pasta** e rode:
   ```
   /clockify
   ```
   Ele pede sua **API key do Clockify** e conecta sua **agenda do Outlook** (link `.ics`). Pronto.

## Depois de instalado

| Comando | O que faz |
|---|---|
| `/clockify-tracking` | Lança suas horas no Clockify — um **dia** ou um **período**. |
| `/clockify-report` | **Relatório** das suas horas — **diário** ou **mensal**. |

> **Importante:** sempre abra a **mesma pasta** do passo 3. Se abrir outra, os comandos avisam
> para rodar `/clockify` ali primeiro.

## Permissão de rede (se algo falhar)

O plugin acessa a internet de dentro do Cowork: ele fala com `api.clockify.me` e lê o link do
seu calendário do Outlook. Se o Cowork pedir **permissão de rede**, **permita**. Se aparecer um
aviso de que a conexão foi **bloqueada**, verifique as permissões de rede nas configurações do
Cowork **deste computador** — em contas gerenciadas pela empresa, pode ser necessário pedir ao
administrador para liberar esses endereços.
