# Dashboard - Ecossistema de Inovação de Minas Gerais

Dashboard interativo desenvolvido com Streamlit para análise do ecossistema de inovação de Minas Gerais, utilizando dados da Base de Startups MG do SEBRAE.

## 🚀 Funcionalidades

- **Visão Geral**: Métricas principais do ecossistema
- **Análise por Setores**: Distribuição e ranking de setores
- **Análise Geográfica**: Distribuição por cidades e estados
- **Análise Temporal**: Crescimento ao longo dos anos
- **Análise de Equipe**: Distribuição de tamanhos de equipe
- **Análise ESG**: Práticas de sustentabilidade
- **Filtros Avançados**: Filtros interativos por múltiplas dimensões
- **Dados Detalhados**: Tabela completa com todas as informações

## 📊 Dados

- **Fonte**: Base de Startups MG - SEBRAE Minas Gerais
- **Total**: Mais de 1.000 startups registradas
- **Atualização**: Tempo real via Google Sheets

## 🛠️ Instalação e Execução

1. **Instalar dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Executar o aplicativo**:
   ```bash
   streamlit run app.py
   ```

3. **Acessar no navegador**:
   ```
   http://localhost:8501
   ```

## 📈 Como Usar

1. **Navegação**: Use a sidebar para aplicar filtros
2. **Interação**: Clique nos gráficos para análises detalhadas
3. **Filtros**: Combine múltiplos filtros para análises específicas
4. **Dados**: Visualize tabelas completas ou resumidas

## 🔧 Tecnologias

- **Streamlit**: Framework web
- **Plotly**: Visualizações interativas
- **Pandas**: Manipulação de dados
- **Google Sheets**: Fonte de dados

## 📝 Estrutura do Projeto

```
├── app.py              # Aplicativo principal
├── requirements.txt    # Dependências
└── README.md          # Documentação
```