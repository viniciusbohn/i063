# Como Configurar a API do Google Sheets

Para carregar todas as linhas da planilha (sem limitação de ~2000 linhas), o app agora usa a API do Google Sheets. Siga os passos abaixo:

## Passo 1: Criar um Projeto no Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Crie um novo projeto ou selecione um existente
3. Anote o ID do projeto

## Passo 2: Habilitar a Google Sheets API

1. No Google Cloud Console, vá em **APIs & Services** > **Library**
2. Procure por "Google Sheets API"
3. Clique em **Enable**

## Passo 3: Criar uma Service Account

1. Vá em **APIs & Services** > **Credentials**
2. Clique em **Create Credentials** > **Service Account**
3. Dê um nome (ex: "streamlit-sheets-reader")
4. Clique em **Create and Continue**
5. Pule a etapa de "Grant this service account access to project" (opcional)
6. Clique em **Done**

## Passo 4: Criar e Baixar a Chave JSON

1. Na lista de Service Accounts, clique na que você criou
2. Vá na aba **Keys**
3. Clique em **Add Key** > **Create new key**
4. Selecione **JSON**
5. Clique em **Create**
6. O arquivo JSON será baixado automaticamente

## Passo 5: Compartilhar a Planilha com a Service Account

1. Abra o arquivo JSON baixado
2. Copie o email que está no campo `client_email` (algo como: `seu-service-account@projeto.iam.gserviceaccount.com`)
3. Abra a planilha do Google Sheets: https://docs.google.com/spreadsheets/d/104LamJgsPmwAldSBUOSsAHfXo4m356by44VnGgk2avk
4. Clique em **Share** (Compartilhar)
5. Cole o email da service account
6. Dê permissão de **Viewer** (Visualizador)
7. Clique em **Send**

## Passo 6: Configurar no Streamlit

### Opção A: Via Variável de Ambiente (Recomendado para produção)

1. No Streamlit Cloud, vá em **Settings** > **Secrets**
2. Adicione uma nova variável:
   - Key: `GOOGLE_APPLICATION_CREDENTIALS`
   - Value: Cole o conteúdo completo do arquivo JSON (tudo em uma linha)

### Opção B: Via Arquivo Local (Para desenvolvimento)

1. Renomeie o arquivo JSON baixado para `credentials.json`
2. Coloque o arquivo na raiz do projeto (mesma pasta do `app.py`)
3. Adicione `credentials.json` ao `.gitignore` para não commitar as credenciais

## Verificação

Após configurar, o app irá:
- ✅ Usar a API do Google Sheets automaticamente (carrega TODAS as linhas)
- ⚠️ Se não encontrar credenciais, usa export CSV como fallback (pode ter limitação)

## Troubleshooting

- **Erro "Permission denied"**: Verifique se compartilhou a planilha com o email da service account
- **Erro "API not enabled"**: Verifique se habilitou a Google Sheets API no Google Cloud Console
- **Erro "File not found"**: Verifique se o arquivo `credentials.json` está no local correto ou se a variável de ambiente está configurada

