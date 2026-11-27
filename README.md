# Painel de e-mails

Lê sua caixa do Gmail, separa cada e-mail em um tipo e mostra tudo num painel web:

| Tipo | Exemplos |
|---|---|
| **Venda de produto** | "Nova venda", "Pedido confirmado", "Pagamento aprovado", "Pix recebido" |
| **Pergunta de cliente** | "Dúvida", "Quanto custa?", "Qual o prazo?", "Vocês entregam…?" |
| **Mensagem de cliente** | Agradecimentos, reclamações, "não recebi meu pedido", trocas e o resto |
| **Outros** | Newsletters, códigos de verificação e avisos automáticos (para não poluir os três tipos acima) |

O painel mostra:
- quantos e-mails de cada tipo chegaram (7, 30, 90 dias ou tudo); clique num cartão para filtrar;
- um gráfico de e-mails por dia, separado por tipo;
- a lista de e-mails, com busca, e o link **Gmail ↗** que abre o e-mail original no Gmail;
- a página de cada e-mail, com o texto, o motivo da classificação, o botão **Responder** e a opção de **corrigir o tipo** à mão (a correção é mantida).

Usa só Python 3.10 ou mais recente, sem instalar nenhum pacote. Os e-mails ficam num arquivo local (`emails.db`) no seu computador.

## 1. Ver uma demonstração (sem Gmail)

```bash
python -m painel_emails demo
```
Abra http://localhost:8000.

## 2. Conectar ao seu Gmail

1. Ative a **verificação em duas etapas** na sua Conta Google.
2. Crie uma **senha de app** em https://myaccount.google.com/apppasswords (nome: "Painel de e-mails"). O Google mostra 16 letras.
3. No Gmail, em Configurações → Ver todas as configurações → Encaminhamento e POP/IMAP, confirme que o **IMAP está ativado**.
4. Copie `.env.example` para `.env` e preencha `EMAIL_USUARIO` e `EMAIL_SENHA_APP`.

O acesso é somente leitura: o painel não apaga, não move e não marca e-mails como lidos.

## 3. Usar

```bash
python -m painel_emails painel --sincronizar   # busca e-mails novos e abre o painel
```
No painel, o botão **Buscar novos e-mails** traz o que chegou depois. Outros comandos:

```bash
python -m painel_emails sincronizar     # só busca (bom para agendar no cron/Agendador de Tarefas)
python -m painel_emails reclassificar   # reaplica as regras depois de editá-las
python -m painel_emails painel --host 0.0.0.0   # acessar pelo celular na mesma rede Wi-Fi
```

Para buscar sozinho a cada 15 minutos (Linux/macOS, `crontab -e`):
```
*/15 * * * * cd /caminho/do/projeto && python3 -m painel_emails sincronizar
```

## Ajustar a classificação

As palavras-chave ficam em `painel_emails/regras.json`. Acentos e maiúsculas não importam. Palavras no assunto valem 2 pontos, no texto 1 ponto; a categoria com mais pontos vence. Um `?` na mensagem conta como pergunta (cumprimentos como "tudo bem?" são ignorados). Sem nenhuma palavra encontrada, o e-mail vira "Mensagem de cliente".

Depois de editar, rode `python -m painel_emails reclassificar`. As correções feitas à mão no painel são preservadas.

Dica: inclua nas regras de **venda** o assunto exato que a sua plataforma (Shopify, Hotmart, Mercado Livre, Nuvemshop…) usa nos avisos de venda.

## Testes

```bash
python -m unittest discover -s tests
```

## Versão online (claude.ai)

`online/painel-emails.html` é a versão publicada como página privada no claude.ai. Ela lê o Gmail pelo
conector do Gmail da conta Claude de quem abre a página (somente leitura), classifica com as mesmas regras
e guarda as correções de tipo só para quem as fez. Não precisa de servidor nem de computador ligado.

---

# Etiquetas IMEI (Zebra 40×25 mm, 2 colunas)

Programa para **fotografar a etiqueta da caixa do celular**, ler o **IMEI 1 e o IMEI 2** e imprimir etiquetas
com código de barras numa **impressora Zebra**, no rolo de **40×25 mm com 2 colunas**.

- Lê os **códigos de barras** da foto; se faltar algum, lê os **números impressos (OCR)**.
- Confere cada IMEI pelo dígito verificador (Luhn) antes de imprimir.
- Também aceita digitar ou usar **leitor de código de barras USB** (ao completar o IMEI 1, pula para o IMEI 2).
- **Imprimir agora** (uma caixa) ou montar uma **fila** e imprimir tudo de uma vez, com cópias.
- Prévia da etiqueta na tela; botão para **baixar o ZPL**.
- Usa só Python 3.10+ (sem instalar pacotes). As bibliotecas de leitura já vêm na pasta `etiquetas_imei/static/vendor`, então funciona sem internet.

## Como abrir

No computador onde a Zebra está ligada (ou qualquer computador na mesma rede de uma Zebra de rede):

```bash
python -m etiquetas_imei
```
No Windows, basta dar dois cliques em **`Etiquetas IMEI.bat`**.

A janela mostra dois endereços:
- `http://localhost:8100` — para usar no próprio computador;
- `http://192.168.x.x:8100` — para abrir **no celular** (mesmo Wi-Fi). No celular, o botão **📷 Tirar foto da caixa** abre a câmera.

## Configurar a impressora (⚙️ no fim da página)

| Ligação | O que preencher |
|---|---|
| **Rede** (Ethernet/Wi-Fi) | IP da Zebra e porta `9100` |
| **USB no Windows** | Nome da impressora como aparece no Windows (ex.: `ZDesigner GC420t`). O envio é em modo RAW pelo spooler, sem instalar nada. |
| **USB no Linux/macOS** | Nome da fila no CUPS (crie a fila como *Raw*) |

Depois clique em **Imprimir etiqueta de teste**.

Etiqueta (padrão): 203 dpi, 40×25 mm, 2 colunas, 2 mm entre colunas. Se a impressão sair deslocada, ajuste
**Espaço entre colunas**, **Margem esquerda** e **Ajuste vertical**. Para Zebra de 300 dpi, troque a resolução.

**Layout**
- *IMEI 1 na esquerda, IMEI 2 na direita* (padrão): cada caixa usa uma fileira — um IMEI por etiqueta.
- *IMEI 1 e IMEI 2 na mesma etiqueta*: cada etiqueta leva os dois códigos; com 2 colunas, cabem dois celulares por fileira.

## Dicas para a foto
Enquadre a etiqueta com os códigos, reta, bem iluminada e sem reflexo. Se só um IMEI for lido, tire outra foto
mais de perto ou digite o segundo. Se a foto trouxer mais de dois números, toque no certo para usar.

## Testes
```bash
python -m unittest discover -s tests
```
