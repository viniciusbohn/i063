import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime
import numpy as np
from urllib.parse import quote
import unicodedata

# Configuração da página
st.set_page_config(
    page_title="Dashboard - Ecossistema de Inovação MG",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Constantes globais para mapas
MAP_CENTER = {"lat": -18.5, "lon": -44.5}
MAP_ZOOM = 5.2
MAP_HEIGHT = 680
MAP_CONFIG = {
    "displayModeBar": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": [],
}
MAP_STYLE = "carto-darkmatter"  # Estilo escuro que combina com o fundo do Streamlit
MAP_BASE_LAYER = None

# Paleta base para regiões (suficiente para 14 regiões)
REGION_COLOR_PALETTE = (
    px.colors.qualitative.Safe
    + px.colors.qualitative.Set3
    + px.colors.qualitative.Pastel
    + px.colors.qualitative.Dark2
)

# Cores para categorias de atores
CATEGORIA_COLORS = {
    "Startup": "#1f77b4",  # Azul
    "Empresa Âncora": "#ff7f0e",  # Laranja
    "Fundos e Investidores": "#2ca02c",  # Verde
    "Hubs, Incubadoras e Parques Tecnológicos": "#d62728",  # Vermelho
    "Universidades e ICTs": "#9467bd",  # Roxo
    "Órgãos Públicos e Apoio": "#8c564b",  # Marrom
}


def hex_to_rgb(hex_color: str):
    """Converte cor hex/rgb em tupla (r, g, b)."""
    if not isinstance(hex_color, str):
        raise ValueError("Cor inválida.")
    color = hex_color.strip()
    if color.startswith("rgb"):
        values = color[color.find("(") + 1 : color.find(")")].split(",")
        values = [v.strip() for v in values if v.strip()]
        if len(values) < 3:
            raise ValueError(f"Cor RGB inválida: {hex_color}")
        return tuple(int(float(v)) for v in values[:3])
    hex_clean = color.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    return tuple(int(hex_clean[i : i + 2], 16) for i in (0, 2, 4))


def build_colorscale(base_hex: str, min_alpha: float = 0.25):
    """Gera colorscale RGBA baseada na cor base."""
    r, g, b = hex_to_rgb(base_hex)
    return [
        (0.0, f"rgba({r},{g},{b},{min_alpha})"),  # Valor mínimo mais visível
        (0.25, f"rgba({r},{g},{b},{min_alpha + 0.2})"),
        (0.5, f"rgba({r},{g},{b},{min_alpha + 0.4})"),
        (0.75, f"rgba({r},{g},{b},{min_alpha + 0.65})"),
        (1.0, f"rgba({r},{g},{b},1.0)"),
    ]


def color_with_intensity(base_hex: str, intensity: float, min_alpha: float = 0.18):
    """Retorna cor RGBA variando transparência conforme intensidade (0-1)."""
    intensity = max(0.0, min(1.0, float(intensity)))
    r, g, b = hex_to_rgb(base_hex)
    alpha = min_alpha + (1 - min_alpha) * intensity
    return f"rgba({r},{g},{b},{alpha})"


def normalize_codigo_ibge(series: pd.Series) -> pd.Series:
    """Normaliza série com códigos IBGE para strings de sete dígitos."""
    def _normalize(value):
        if pd.isna(value):
            return np.nan
        try:
            return f"{int(float(value)):07d}"
        except (ValueError, TypeError):
            value_str = str(value).strip()
            if value_str == "":
                return np.nan
            value_str = value_str.split('.')[0]
            return value_str.zfill(7)
    return series.apply(_normalize)

# CSS personalizado
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        color: white;
        text-align: center;
        margin: 0.5rem 0;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: bold;
        margin: 0.3rem 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        line-height: 1.2;
    }
    
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
        text-transform: none;
        letter-spacing: 0.5px;
        line-height: 1.3;
        margin-bottom: 0.5rem;
        flex-shrink: 0;
        max-height: 3.9em;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
    }
    
    .site-icon {
        text-align: center;
        width: 40px;
        min-width: 40px;
        max-width: 40px;
    }
    .site-icon a {
        text-decoration: none;
        color: #4A9EFF;
        font-size: 1.2rem;
        display: inline-block;
    }
    .site-icon a:hover {
        color: #6BB6FF;
        transform: scale(1.2);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache por 5 minutos para permitir atualizações
def load_data_from_sheets(sheet_name, force_reload=False):
    """
    Carrega dados do Google Sheets SEBRAE MG de uma aba específica
    """
    try:
        sheet_id = "104LamJgsPmwAldSBUOSsAHfXo4m356by44VnGgk2avk"
        
        # Método 1: Tenta com a URL de export CSV direta usando o nome da aba
        try:
            encoded_sheet_name = quote(sheet_name, safe="")
            sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
            # Tenta diferentes encodings para resolver problemas com caracteres especiais
            try:
                df = pd.read_csv(sheet_url, encoding='utf-8')
            except:
                try:
                    df = pd.read_csv(sheet_url, encoding='latin-1')
                except:
                    df = pd.read_csv(sheet_url, encoding='iso-8859-1')
        except:
            # Método 2: Tenta com export direto (pode pegar a primeira aba)
            try:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                try:
                    df = pd.read_csv(sheet_url, encoding='utf-8')
                except:
                    df = pd.read_csv(sheet_url, encoding='latin-1')
            except:
                # Método 3: Tenta com gid=0 (primeira aba)
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
                try:
                    df = pd.read_csv(sheet_url, encoding='utf-8')
                except:
                    df = pd.read_csv(sheet_url, encoding='latin-1')
        
        # Remove linhas completamente vazias
        df = df.dropna(how='all')
        
        # Remove espaços dos nomes das colunas (importante!)
        df.columns = df.columns.str.strip()
        
        # Remove linhas onde a primeira coluna está vazia (NaN ou string vazia)
        if len(df) > 0 and len(df.columns) > 0:
            primeira_col = df.columns[0]
            if primeira_col in df.columns:
                # Remove linhas onde a primeira coluna é NaN OU string vazia (após remover espaços)
                mask = df[primeira_col].notna() & (df[primeira_col].astype(str).str.strip() != '')
                df = df[mask]
                # Remove linhas que são claramente cabeçalhos duplicados
                df = df[~df[primeira_col].astype(str).str.contains('^name$|^Name$|^NAME$', case=False, na=False, regex=True)]
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()


@st.cache_data(ttl=300)  # Cache por 5 minutos para permitir atualizações
def load_data_municipios_regioes(force_reload=False):
    """
    Carrega dados da aba "Municípios e Regiões" para o mapa
    """
    return load_data_from_sheets("Municípios e Regiões", force_reload)


@st.cache_data(ttl=300)  # Cache por 5 minutos para permitir atualizações
def load_data_base_atores(force_reload=False):
    """
    Carrega dados da aba "Base | Atores MG" para a tabela de startups
    """
    return load_data_from_sheets("Base | Atores MG", force_reload)


@st.cache_data
def load_geojson_mg():
    """
    Carrega GeoJSON dos municípios de Minas Gerais.
    """
    # Fonte principal (repositório geodata-br)
    try:
        url_geojson = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-31-mun.json"
        response = requests.get(url_geojson, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    # Fonte alternativa: IBGE
    try:
        url_geojson = (
            "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/31"
            "?formato=application/vnd.geo+json&qualidade=intermediaria"
        )
        response = requests.get(url_geojson, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    return None


@st.cache_data(ttl=3600)  # Cache por 1 hora (dados raramente mudam)
def load_municipios_com_coordenadas():
    """
    Carrega dados de municípios de MG com latitude e longitude de fonte pública.
    """
    try:
        # Fonte: repositório kelvins/municipios-brasileiros no GitHub
        url_municipios = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
        df_municipios = pd.read_csv(url_municipios)
        
        # Filtra apenas Minas Gerais (código UF = 31)
        df_mg = df_municipios[df_municipios['codigo_uf'] == 31].copy()
        
        # Renomeia colunas para compatibilidade
        if 'codigo_ibge' not in df_mg.columns:
            if 'codigo' in df_mg.columns:
                df_mg['codigo_ibge'] = df_mg['codigo']
        
        # Garante que código IBGE existe
        if 'codigo_ibge' not in df_mg.columns:
            if 'codigo' in df_mg.columns:
                df_mg['codigo_ibge'] = df_mg['codigo']
            else:
                raise ValueError("Coluna 'codigo_ibge' ou 'codigo' não encontrada")
        
        # Garante que nome existe
        if 'nome' not in df_mg.columns:
            if 'nome_municipio' in df_mg.columns:
                df_mg['nome'] = df_mg['nome_municipio']
            else:
                raise ValueError("Coluna 'nome' não encontrada")
        
        # Verifica e adiciona coordenadas se necessário
        if 'latitude' not in df_mg.columns or 'longitude' not in df_mg.columns:
            # Usa coordenadas padrão do centro de MG se não disponíveis
            if 'latitude' not in df_mg.columns:
                df_mg['latitude'] = -18.5122
            if 'longitude' not in df_mg.columns:
                df_mg['longitude'] = -44.5550
        
        # Seleciona apenas as colunas necessárias
        colunas_finais = ['codigo_ibge', 'nome', 'latitude', 'longitude']
        df_mg = df_mg[colunas_finais].copy()
        
        # Normaliza código IBGE
        if 'codigo_ibge' in df_mg.columns:
            df_mg['codigo_ibge'] = normalize_codigo_ibge(df_mg['codigo_ibge'])
        
        return df_mg
    
    except Exception as e:
        st.warning(f"⚠️ Não foi possível carregar coordenadas de municípios da fonte remota: {str(e)}")
        # Retorna DataFrame vazio se não conseguir carregar
        return pd.DataFrame(columns=['codigo_ibge', 'nome', 'latitude', 'longitude'])

def create_overview_metrics(df):
    """
    Cria métricas principais do dashboard em formato de cards
    """
    st.header("📊 Visão Geral do Ecossistema")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if 'qtd_startups' in df.columns:
            total_startups = pd.to_numeric(df['qtd_startups'], errors='coerce').sum()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total de Startups</div>
                <div class="metric-value">{int(total_startups):,}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total de Municípios</div>
                <div class="metric-value">{len(df):,}</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        if 'qtd_startups' in df.columns:
            municipios_com_startups = df[pd.to_numeric(df['qtd_startups'], errors='coerce') > 0].shape[0]
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Municípios com Startups</div>
                <div class="metric-value">{municipios_com_startups:,}</div>
            </div>
            """, unsafe_allow_html=True)
        elif 'foundationYear' in df.columns:
            startups_2020_plus = df[df['foundationYear'] >= 2020].shape[0]
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Startups Recentes (2020+)</div>
                <div class="metric-value">{startups_2020_plus:,}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Municípios com Startups</div>
                <div class="metric-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        if 'nome_mesorregiao' in df.columns:
            regioes_unicas = df['nome_mesorregiao'].nunique()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Regiões Mapeadas</div>
                <div class="metric-value">{regioes_unicas:,}</div>
            </div>
            """, unsafe_allow_html=True)
        elif 'sector' in df.columns:
            setores_unicos = df['sector'].nunique()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Setores Atendidos</div>
                <div class="metric-value">{setores_unicos:,}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Regiões</div>
                <div class="metric-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col4:
        if 'nome_municipio' in df.columns:
            municipios_unicos = df['nome_municipio'].nunique()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Municípios Mapeados</div>
                <div class="metric-value">{municipios_unicos:,}</div>
            </div>
            """, unsafe_allow_html=True)
        elif 'cidade_Max' in df.columns:
            cidades_unicas = df['cidade_Max'].nunique()
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Cidades Atendidas</div>
                <div class="metric-value">{cidades_unicas:,}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Municípios</div>
                <div class="metric-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Indicador Reservado</div>
            <div class="metric-value">-</div>
        </div>
        """, unsafe_allow_html=True)

def create_sector_analysis(df):
    """
    Cria análise por setores
    """
    st.header("🏢 Análise por Setores")
    
    if 'sector' in df.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            # Top setores (remove NaN)
            sector_counts = df['sector'].dropna().value_counts().head(10)
            
            fig = px.bar(
                x=sector_counts.values,
                y=sector_counts.index,
                orientation='h',
                title="Top 10 Setores",
                color=sector_counts.values,
                color_continuous_scale='Blues'
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Distribuição por setores (remove NaN)
            sector_counts_all = df['sector'].dropna().value_counts()
            
            fig = px.pie(
                values=sector_counts_all.values,
                names=sector_counts_all.index,
                title="Distribuição por Setores"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna 'sector' não encontrada nos dados")

def create_temporal_analysis(df):
    """
    Cria análise temporal
    """
    st.header("📈 Análise Temporal")
    
    if 'foundationYear' in df.columns:
        # Limpa dados de ano de fundação
        df_clean = df.copy()
        df_clean['foundationYear'] = pd.to_numeric(df_clean['foundationYear'], errors='coerce')
        df_clean = df_clean[df_clean['foundationYear'].notna()]
        df_clean = df_clean[df_clean['foundationYear'] >= 2000]  # Filtra anos razoáveis
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Startups por ano
            yearly_counts = df_clean['foundationYear'].value_counts().sort_index()
            
            fig = px.line(
                x=yearly_counts.index,
                y=yearly_counts.values,
                title="Startups Fundadas por Ano",
                markers=True
            )
            fig.update_layout(xaxis_title="Ano", yaxis_title="Número de Startups")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Acumulado por ano
            yearly_counts_sorted = yearly_counts.sort_index()
            cumulative = yearly_counts_sorted.cumsum()
            
            fig = px.line(
                x=cumulative.index,
                y=cumulative.values,
                title="Acumulado de Startups por Ano",
                markers=True
            )
            fig.update_layout(xaxis_title="Ano", yaxis_title="Total Acumulado")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna 'foundationYear' não encontrada nos dados")

def create_advanced_filters(df):
    """
    Cria filtros avançados na sidebar
    """
    # Título reduzido no topo da sidebar
    st.sidebar.markdown("### 🚀 Dashboard MG")
    st.sidebar.markdown("---")  # Espaçador
    
    st.sidebar.header("🔍 Filtros Avançados")
    
    # Filtro por região (mesorregião)
    if 'nome_mesorregiao' in df.columns:
        # Remove valores NaN e converte para string
        regioes_validas = df['nome_mesorregiao'].dropna().astype(str).unique()
        regioes = ['Todas'] + sorted(list(regioes_validas))
        regiao_selecionada = st.sidebar.selectbox("Região", regioes)
        
        if regiao_selecionada != 'Todas':
            df = df[df['nome_mesorregiao'].astype(str) == regiao_selecionada]
    
    # Filtro por município
    if 'nome_municipio' in df.columns:
        # Remove valores NaN e converte para string
        municipios_validos = df['nome_municipio'].dropna().astype(str).unique()
        municipios = ['Todos'] + sorted(list(municipios_validos))
        municipio_selecionado = st.sidebar.selectbox("Município", municipios)
        
        if municipio_selecionado != 'Todos':
            df = df[df['nome_municipio'].astype(str) == municipio_selecionado]
    
    # Filtro por quantidade de startups (mínimo)
    if 'qtd_startups' in df.columns:
        qtd_max = int(pd.to_numeric(df['qtd_startups'], errors='coerce').max() or 0)
        qtd_min = int(pd.to_numeric(df['qtd_startups'], errors='coerce').min() or 0)
        if qtd_max > qtd_min:
            qtd_range = st.sidebar.slider(
                "Quantidade Mínima de Startups",
                min_value=qtd_min,
                max_value=qtd_max,
                value=qtd_min
            )
            df = df[pd.to_numeric(df['qtd_startups'], errors='coerce') >= qtd_range]
    
    # Filtros alternativos (para compatibilidade com outras abas)
    if 'sector' in df.columns and 'nome_mesorregiao' not in df.columns:
        # Remove valores NaN e converte para string
        setores_validos = df['sector'].dropna().astype(str).unique()
        setores = ['Todos'] + sorted(list(setores_validos))
        setor_selecionado = st.sidebar.selectbox("Setor", setores)
        
        if setor_selecionado != 'Todos':
            df = df[df['sector'].astype(str) == setor_selecionado]
    
    if 'cidade_Max' in df.columns and 'nome_municipio' not in df.columns:
        # Remove valores NaN e converte para string
        cidades_validas = df['cidade_Max'].dropna().astype(str).unique()
        cidades = ['Todas'] + sorted(list(cidades_validas))
        cidade_selecionada = st.sidebar.selectbox("Cidade", cidades)
        
        if cidade_selecionada != 'Todas':
            df = df[df['cidade_Max'].astype(str) == cidade_selecionada]
    
    return df

def create_interactive_map(df):
    """
    Cria mapa interativo de Minas Gerais dividido por regiões
    """
    st.header("🗺️ Mapa Interativo por Região")
    
    # Usa as colunas específicas da aba "Municípios e Regiões"
    coluna_regiao = "nome_mesorregiao"
    coluna_municipio = "nome_municipio"
    coluna_qtd_startups = "qtd_startups"
    coluna_codigo_ibge = "codigo_ibge"
    
    if coluna_regiao not in df.columns:
        st.error(f"❌ A coluna de região '{coluna_regiao}' não foi encontrada na planilha.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return
    
    if coluna_municipio not in df.columns:
        st.error(f"❌ A coluna de município '{coluna_municipio}' não foi encontrada na planilha.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return
    
    if coluna_codigo_ibge not in df.columns:
        st.error(f"❌ A coluna de código IBGE '{coluna_codigo_ibge}' não foi encontrada na planilha.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return
    
    st.success(f"✅ Coluna de região utilizada: **{coluna_regiao}**")
    st.success(f"✅ Coluna de município utilizada: **{coluna_municipio}**")
    
    try:
        # Carrega dados de municípios com coordenadas
        df_municipios = load_municipios_com_coordenadas()
        
        if df_municipios.empty:
            st.error("❌ Não foi possível carregar os dados de municípios.")
            return
        
        # Prepara dados da planilha
        df_map = df[[coluna_codigo_ibge, coluna_municipio, coluna_regiao, coluna_qtd_startups]].copy()
        df_map = df_map.dropna(subset=[coluna_municipio, coluna_regiao])
        df_map[coluna_codigo_ibge] = normalize_codigo_ibge(df_map[coluna_codigo_ibge])
        df_map[coluna_qtd_startups] = pd.to_numeric(df_map[coluna_qtd_startups], errors='coerce').fillna(0).astype(int)
        
        # Seleciona apenas colunas disponíveis para o merge
        colunas_merge = ['codigo_ibge']
        if 'nome' in df_municipios.columns:
            colunas_merge.append('nome')
        if 'latitude' in df_municipios.columns:
            colunas_merge.append('latitude')
        if 'longitude' in df_municipios.columns:
            colunas_merge.append('longitude')
        
        # Faz merge usando código IBGE
        df_merged = df_map.merge(
            df_municipios[colunas_merge],
            on='codigo_ibge',
            how='inner'
        )
        
        if df_merged.empty:
            st.warning("⚠️ Não foi possível fazer o match entre os códigos IBGE da planilha e os dados de municípios.")
            st.info("💡 Dica: Verifique se os códigos IBGE na planilha correspondem aos códigos oficiais dos municípios.")
            return
        
        # Cria o mapa
        st.subheader("📍 Distribuição Geográfica por Região")

        # Conta quantos registros por região
        regioes_counts = df_merged[coluna_regiao].value_counts()

        # Cria paleta de cores
        cores = (
            px.colors.qualitative.Set3
            + px.colors.qualitative.Pastel
            + px.colors.qualitative.Dark2
            + px.colors.qualitative.Set2
        )
        cores_dict = {regiao: cores[i % len(cores)] for i, regiao in enumerate(regioes_counts.index)}

        # Dados para choropleth
        df_choropleth = df_merged.copy()
        df_choropleth['codigo_ibge'] = normalize_codigo_ibge(df_choropleth['codigo_ibge'])

        geojson_mg = load_geojson_mg()

        fig = px.choropleth_mapbox(
            df_choropleth,
            geojson=geojson_mg,
            locations='codigo_ibge',
            featureidkey="properties.codigo_ibge",
            color=coluna_regiao,
            color_discrete_map=cores_dict,
            hover_data=None,
            opacity=0.85,
            zoom=MAP_ZOOM,
            center=MAP_CENTER,
            height=700,
            title="Mapa de Minas Gerais por Região"
        )

        fig.update_layout(
            mapbox_style="carto-darkmatter",  # Estilo escuro que combina com o fundo do Streamlit
            mapbox=dict(
                center=MAP_CENTER,
                zoom=MAP_ZOOM,
                layers=[]
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
            paper_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=0,
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="rgba(0,0,0,0.2)",
                borderwidth=1
            )
        )

        fig.update_traces(
            hovertemplate=(
                "<b>Região:</b> %{customdata[0]}<br>"
                "<b>Município:</b> %{customdata[1]}<br>"
                "<b>Total de startups:</b> %{customdata[2]}<extra></extra>"
            ),
            customdata=df_choropleth[[coluna_regiao, coluna_municipio, coluna_qtd_startups]].values
        )
        
        st.plotly_chart(fig, use_container_width=True, config=MAP_CONFIG)
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total de Municípios", len(df_merged))
        
        with col2:
            st.metric("Regiões Únicas", df_merged[coluna_regiao].nunique())
        
        with col3:
            total_startups = df_merged[coluna_qtd_startups].sum()
            st.metric("Total de Startups", int(total_startups))
        
    except Exception as e:
        st.error(f"❌ Erro ao criar mapa: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

def render_region_legend(regioes, base_colors, title=""):
    """
    Renderiza legenda personalizada para as regiões utilizando Streamlit.
    """
    if not regioes:
        st.info("Legenda indisponível.")
        return
    
    if title:
        st.subheader(title)
        legend_items = []
    for regiao in regioes:
        color = base_colors.get(regiao, "#cccccc")
        legend_items.append(
            f"""
            <div style="display:flex; align-items:center; margin-bottom:6px;">
                <span style="
                    width:18px;
                    height:18px;
                    border-radius:4px;
                    background-color:{color};
                    display:inline-block;
                    margin-right:10px;
                    box-shadow:0 0 4px rgba(0,0,0,0.15);
                "></span>
                <span style="color:#e2e8f0; font-size:0.95rem;">{regiao}</span>
            </div>
            """
        )
    st.markdown("".join(legend_items), unsafe_allow_html=True)


def create_choropleth_map(df, df_atores=None):
    """
    Cria o mapa choropleth principal colorindo todos os municípios pelas regiões.
    
    Args:
        df: DataFrame com dados da aba "Municípios e Regiões"
        df_atores: DataFrame opcional com dados da aba "Base | Atores MG" para filtro por categoria
    """
    
    # Usa as colunas específicas da aba "Municípios e Regiões"
    coluna_regiao = "nome_mesorregiao"
    coluna_municipio = "nome_municipio"
    coluna_qtd_startups = "qtd_startups"
    coluna_qtd_empresas_ancora = "qtd_empresas_ancora"
    coluna_qtd_fundos_e_investidores = "qtd_fundos_e_investidores"
    coluna_qtd_universidades_icts = "qtd_universidades_icts"
    coluna_qtd_orgaos = "qtd_orgaos"
    coluna_codigo_ibge = "codigo_ibge"

    if coluna_regiao not in df.columns:
        st.warning(f"⚠️ Coluna '{coluna_regiao}' não encontrada na planilha. Este mapa requer a coluna de região.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return

    if coluna_municipio not in df.columns:
        st.warning(f"⚠️ Coluna '{coluna_municipio}' não encontrada na planilha.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return

    if coluna_qtd_startups not in df.columns:
        st.warning(f"⚠️ Coluna '{coluna_qtd_startups}' não encontrada na planilha.")
        st.info(f"💡 Colunas disponíveis: {', '.join(df.columns.astype(str).tolist())}")
        return

    try:
        with st.spinner("Carregando dados geográficos de Minas Gerais..."):
            geojson_mg = load_geojson_mg()
    except Exception as e:
        st.error(f"❌ Falha ao carregar GeoJSON: {e}")
        geojson_mg = None

    # Dados da planilha normalizados
    colunas_necessarias = [coluna_codigo_ibge, coluna_municipio, coluna_regiao, coluna_qtd_startups]
    if coluna_qtd_empresas_ancora in df.columns:
        colunas_necessarias.append(coluna_qtd_empresas_ancora)
    if coluna_qtd_fundos_e_investidores in df.columns:
        colunas_necessarias.append(coluna_qtd_fundos_e_investidores)
    if coluna_qtd_universidades_icts in df.columns:
        colunas_necessarias.append(coluna_qtd_universidades_icts)
    if coluna_qtd_orgaos in df.columns:
        colunas_necessarias.append(coluna_qtd_orgaos)
    
    df_map = df[colunas_necessarias].copy()
    df_map = df_map.dropna(subset=[coluna_municipio, coluna_regiao])
    df_map[coluna_codigo_ibge] = normalize_codigo_ibge(df_map[coluna_codigo_ibge])
    # Remove linhas com código IBGE inválido
    df_map = df_map[df_map[coluna_codigo_ibge].notna()]
    df_map[coluna_codigo_ibge] = df_map[coluna_codigo_ibge].astype(str)  # Garante que seja string
    df_map[coluna_qtd_startups] = pd.to_numeric(df_map[coluna_qtd_startups], errors='coerce').fillna(0).astype(int)
    if coluna_qtd_empresas_ancora in df_map.columns:
        df_map[coluna_qtd_empresas_ancora] = pd.to_numeric(df_map[coluna_qtd_empresas_ancora], errors='coerce').fillna(0).astype(int)
    if coluna_qtd_fundos_e_investidores in df_map.columns:
        df_map[coluna_qtd_fundos_e_investidores] = pd.to_numeric(df_map[coluna_qtd_fundos_e_investidores], errors='coerce').fillna(0).astype(int)
    if coluna_qtd_universidades_icts in df_map.columns:
        df_map[coluna_qtd_universidades_icts] = pd.to_numeric(df_map[coluna_qtd_universidades_icts], errors='coerce').fillna(0).astype(int)
    if coluna_qtd_orgaos in df_map.columns:
        df_map[coluna_qtd_orgaos] = pd.to_numeric(df_map[coluna_qtd_orgaos], errors='coerce').fillna(0).astype(int)

    # Base de municípios com latitude/longitude (para coordenadas se necessário)
    df_municipios = load_municipios_com_coordenadas()
    
    if df_municipios.empty:
        st.warning("⚠️ Não foi possível carregar dados de coordenadas dos municípios. O mapa pode não funcionar corretamente.")
        return

    # Seleciona apenas colunas disponíveis para o merge
    colunas_merge = ['codigo_ibge']
    if 'nome' in df_municipios.columns:
        colunas_merge.append('nome')
    if 'latitude' in df_municipios.columns:
        colunas_merge.append('latitude')
    if 'longitude' in df_municipios.columns:
        colunas_merge.append('longitude')

    # Combina dados da planilha com dados de municípios usando código IBGE
    df_regions = df_map.merge(
        df_municipios[colunas_merge],
        on='codigo_ibge',
        how='left'
    )
    
    # Se o merge não trouxe o nome, usa o nome da planilha
    df_regions['nome'] = df_regions['nome'].fillna(df_regions[coluna_municipio])
    
    # Renomeia para manter consistência
    df_regions['regiao_final'] = df_regions[coluna_regiao]
    df_regions['count'] = df_regions[coluna_qtd_startups]
    
    # Mantém somente municípios que têm região definida na planilha
    df_regions = df_regions[df_regions['regiao_final'].notna()]
    
    # Define cores para TODAS as regiões ANTES de aplicar filtros
    # Isso garante que cada região mantenha sua cor original
    regioes_todas = sorted(df_regions['regiao_final'].unique())
    base_colors = {regiao: REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)] for i, regiao in enumerate(regioes_todas)}

    # Inicializa variáveis de filtro
    categorias_selecionadas = []
    categorias_disponiveis = []
    
    # Cria layout com filtros à esquerda e mapa à direita
    col_filters, col_map = st.columns([0.35, 0.65])
    
    with col_filters:
        # Prepara dados para determinar categorias disponíveis (antes dos filtros)
        categorias_disponiveis = []
        if df_atores is not None and not df_atores.empty:
            # Procura por coluna de categoria (pode ter vários nomes)
            coluna_categoria = None
            possiveis_nomes = ['categoria', 'tipo', 'tipo_ator', 'categoria_ator', 'actor_type', 'type']
            for nome in possiveis_nomes:
                if nome in df_atores.columns:
                    coluna_categoria = nome
                    break
            
            if coluna_categoria:
                categorias_disponiveis = sorted(df_atores[coluna_categoria].dropna().unique().tolist())
        
        # Se não encontrou categoria nos atores, usa valores padrão baseado nas colunas disponíveis
        if not categorias_disponiveis:
            # Constrói lista de categorias baseada nas colunas disponíveis
            categorias_base = []
            if coluna_qtd_startups in df.columns:
                categorias_base.append("Startup")
            if coluna_qtd_empresas_ancora in df.columns:
                categorias_base.append("Empresa Âncora")
            if coluna_qtd_fundos_e_investidores in df.columns:
                categorias_base.append("Fundos e Investidores")
            if coluna_qtd_universidades_icts in df.columns:
                categorias_base.append("Universidades e ICTs")
            if coluna_qtd_orgaos in df.columns:
                categorias_base.append("Órgãos Públicos e Apoio")
            categorias_disponiveis = categorias_base
        
        # Cabeçalho com título e botão de reset
        col_title, col_reset = st.columns([3, 1])
        with col_title:
            st.subheader("🔍 Filtros")
        with col_reset:
            st.write("")  # Espaçamento
            if st.button("🔄 Resetar", key="btn_reset_filtros", use_container_width=True):
                # Define explicitamente os valores padrão no session_state
                st.session_state.filtro_regiao = "Todas"
                st.session_state.filtro_municipio = "Todos"
                st.session_state.filtro_categoria = categorias_disponiveis.copy() if categorias_disponiveis else []
                st.rerun()
        
        # Filtro de Região
        regioes_disponiveis = sorted(df_regions['regiao_final'].unique())
        opcoes_regiao = ["Todas"] + regioes_disponiveis
        
        # Inicializa com "Todas" se não estiver definido
        if "filtro_regiao" not in st.session_state:
            st.session_state.filtro_regiao = "Todas"
        
        # Garante que o valor no session_state seja válido
        if st.session_state.filtro_regiao not in opcoes_regiao:
            st.session_state.filtro_regiao = "Todas"
        
        # Usa o selectbox sem index, deixando o Streamlit usar o valor do session_state via key
        regiao_selecionada = st.selectbox(
            "Região",
            options=opcoes_regiao,
            key="filtro_regiao"
        )
        
        # Filtro de Município (depende da região selecionada)
        if regiao_selecionada != "Todas":
            municipios_disponiveis = sorted(
                df_regions[df_regions['regiao_final'] == regiao_selecionada][coluna_municipio].unique()
            )
        else:
            municipios_disponiveis = sorted(df_regions[coluna_municipio].unique())
        
        municipio_selecionado = st.selectbox(
            "Município",
            options=["Todos"] + municipios_disponiveis,
            index=0,
            key="filtro_municipio"
        )
        
        # Filtro de Categoria do Ator (seleção múltipla)
        # Define default como todas as categorias disponíveis apenas se ainda não estiver definido
        if "filtro_categoria" not in st.session_state:
            st.session_state.filtro_categoria = categorias_disponiveis.copy() if categorias_disponiveis else []
        
        categorias_selecionadas = st.multiselect(
            "Categoria do Ator",
            options=categorias_disponiveis,
            key="filtro_categoria"
        )
        
        # Aplica filtros aos dados
        df_regions_filtrado = df_regions.copy()
        
        if regiao_selecionada != "Todas":
            df_regions_filtrado = df_regions_filtrado[
                df_regions_filtrado['regiao_final'] == regiao_selecionada
            ]
        
        if municipio_selecionado != "Todos":
            df_regions_filtrado = df_regions_filtrado[
                df_regions_filtrado[coluna_municipio] == municipio_selecionado
            ]
        
        # Aplica filtro de categoria - ajusta os valores de count baseado nas categorias selecionadas
        if categorias_selecionadas:
            df_regions_filtrado = df_regions_filtrado.copy()
            # Recalcula o count baseado nas categorias selecionadas
            count_filtrado = pd.Series(0, index=df_regions_filtrado.index)
            
            if "Startup" in categorias_selecionadas and coluna_qtd_startups in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_startups], errors='coerce').fillna(0)
            
            if "Empresa Âncora" in categorias_selecionadas and coluna_qtd_empresas_ancora in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_empresas_ancora], errors='coerce').fillna(0)
            
            if "Fundos e Investidores" in categorias_selecionadas and coluna_qtd_fundos_e_investidores in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_fundos_e_investidores], errors='coerce').fillna(0)
            
            if "Universidades e ICTs" in categorias_selecionadas and coluna_qtd_universidades_icts in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_universidades_icts], errors='coerce').fillna(0)
            
            if "Órgãos Públicos e Apoio" in categorias_selecionadas and coluna_qtd_orgaos in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_orgaos], errors='coerce').fillna(0)
            
            df_regions_filtrado['count'] = count_filtrado.astype(int)
        elif categorias_disponiveis:
            # Se nenhuma categoria selecionada mas há categorias disponíveis, não mostra nada
            df_regions_filtrado = df_regions_filtrado.copy()
            df_regions_filtrado['count'] = 0
        else:
            # Se não há categorias disponíveis, usa o comportamento padrão (todas as categorias)
            categorias_selecionadas = categorias_disponiveis if categorias_disponiveis else []
        
        # Mostra cards com totais por categoria
        st.markdown("---")
        
        # Calcula totais baseado nos dados filtrados do mapa (que já têm filtros de região e município aplicados)
        contadores = {}
        
        # Startups - usa dados agregados do mapa (soma a coluna qtd_startups dos municípios filtrados)
        if coluna_qtd_startups in df_regions_filtrado.columns:
            total_startups = pd.to_numeric(df_regions_filtrado[coluna_qtd_startups], errors='coerce').fillna(0).sum()
            contadores["Startups"] = int(total_startups)
        else:
            contadores["Startups"] = 0
        
        # Empresas Âncoras - usa dados agregados do mapa (soma a coluna qtd_empresas_ancora dos municípios filtrados)
        if coluna_qtd_empresas_ancora in df_regions_filtrado.columns:
            total_empresas_ancora = pd.to_numeric(df_regions_filtrado[coluna_qtd_empresas_ancora], errors='coerce').fillna(0).sum()
            contadores["Grandes Empresas Âncoras"] = int(total_empresas_ancora)
        else:
            contadores["Grandes Empresas Âncoras"] = 0
        
        # Fundos e Investidores - usa dados agregados do mapa
        if coluna_qtd_fundos_e_investidores in df_regions_filtrado.columns:
            total_fundos = pd.to_numeric(df_regions_filtrado[coluna_qtd_fundos_e_investidores], errors='coerce').fillna(0).sum()
            contadores["Fundos e Investidores"] = int(total_fundos)
        else:
            contadores["Fundos e Investidores"] = 0
        
        # Universidades e ICTs - usa dados agregados do mapa
        if coluna_qtd_universidades_icts in df_regions_filtrado.columns:
            total_universidades = pd.to_numeric(df_regions_filtrado[coluna_qtd_universidades_icts], errors='coerce').fillna(0).sum()
            contadores["Universidades e ICTs"] = int(total_universidades)
        else:
            contadores["Universidades e ICTs"] = 0
        
        # Órgãos Públicos e Apoio - usa dados agregados do mapa
        if coluna_qtd_orgaos in df_regions_filtrado.columns:
            total_orgaos = pd.to_numeric(df_regions_filtrado[coluna_qtd_orgaos], errors='coerce').fillna(0).sum()
            contadores["Órgãos Públicos e Apoio"] = int(total_orgaos)
        else:
            contadores["Órgãos Públicos e Apoio"] = 0
        
        # Outras categorias - por enquanto ficam zeradas (serão implementadas depois)
        contadores["Hubs, Incubadoras e Parques Tecnológicos"] = 0
        
        # Cria cards em grid 3x2
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Startups</div>
                <div class="metric-value">{contadores.get("Startups", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Hubs, Incubadoras e Parques Tecnológicos</div>
                <div class="metric-value">{contadores.get("Hubs, Incubadoras e Parques Tecnológicos", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Universidades e ICTs</div>
                <div class="metric-value">{contadores.get("Universidades e ICTs", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Grandes Empresas Âncoras</div>
                <div class="metric-value">{contadores.get("Grandes Empresas Âncoras", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Fundos e Investidores</div>
                <div class="metric-value">{contadores.get("Fundos e Investidores", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Órgãos Públicos e Apoio</div>
                <div class="metric-value">{contadores.get("Órgãos Públicos e Apoio", 0):,}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Atualiza df_regions com os dados filtrados
    df_regions = df_regions_filtrado
    
    # Calcula centro e zoom baseado na região selecionada
    map_center = MAP_CENTER
    map_zoom = MAP_ZOOM
    
    if regiao_selecionada != "Todas" and not df_regions.empty:
        # Filtra dados da região selecionada para calcular bounding box
        df_regiao_zoom = df_regions[df_regions['regiao_final'] == regiao_selecionada].copy()
        df_regiao_zoom = df_regiao_zoom.dropna(subset=['latitude', 'longitude'])
        
        if not df_regiao_zoom.empty:
            # Calcula bounding box
            min_lat = df_regiao_zoom['latitude'].min()
            max_lat = df_regiao_zoom['latitude'].max()
            min_lon = df_regiao_zoom['longitude'].min()
            max_lon = df_regiao_zoom['longitude'].max()
            
            # Calcula centro
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
            # Calcula extensão geográfica
            lat_range = max_lat - min_lat
            lon_range = max_lon - min_lon
            max_range = max(lat_range, lon_range)
            
            # Ajusta zoom baseado na extensão
            if max_range > 5:
                zoom = 5.5
            elif max_range > 2:
                zoom = 6.5
            elif max_range > 1:
                zoom = 7.5
            elif max_range > 0.5:
                zoom = 8.5
            else:
                zoom = 9.5
            
            # Regiões específicas que precisam de menos zoom (mais afastado)
            if regiao_selecionada in ["Norte", "Noroalto"]:
                zoom = max(zoom - 1.0, 4.5)  # Reduz o zoom em 1.0, mas não menos que 4.5
            else:
                # Adiciona padding (aumenta um pouco o zoom para dar espaço)
                zoom = min(zoom + 0.3, 10.0)
            
            map_center = {"lat": center_lat, "lon": center_lon}
            map_zoom = zoom

    # Se não temos GeoJSON, usa fallback com scatter
    if not geojson_mg:
        st.warning("⚠️ GeoJSON não disponível. Usando visualização alternativa.")
        create_alternative_choropleth(df_regions)
        return

    # Garante que todos os features tenham código IBGE (texto) normalizado
    for feature in geojson_mg.get('features', []):
        props = feature.get('properties', {})
        codigo = props.get('codigo_ibge') or props.get('id') or feature.get('id') or props.get('CD_MUN') or props.get('codigo')
        if codigo is not None:
            try:
                codigo_normalizado = normalize_codigo_ibge(pd.Series([codigo])).iloc[0]
                if pd.notna(codigo_normalizado):
                    props['codigo_ibge'] = codigo_normalizado
            except:
                pass
        feature['properties'] = props

    # Usa as regiões filtradas, mas mantém as cores originais já definidas
    regioes = sorted(df_regions['regiao_final'].unique())

    fig = go.Figure()

    # Cria dicionário de features por código IBGE (apenas códigos válidos)
    features_by_code = {}
    for feature in geojson_mg.get('features', []):
        codigo = feature['properties'].get('codigo_ibge')
        if codigo and pd.notna(codigo):
            features_by_code[str(codigo)] = feature

    # Debug: identifica municípios sem match no GeoJSON
    municipios_sem_match = []
    
    for regiao in regioes:
        # Inclui todos os municípios da região (incluindo 0 startups)
        df_regiao = df_regions[df_regions['regiao_final'] == regiao].copy()
        if df_regiao.empty:
            continue

        df_regiao['codigo_ibge'] = normalize_codigo_ibge(df_regiao['codigo_ibge'])
        df_regiao = df_regiao.dropna(subset=['codigo_ibge'])
        if df_regiao.empty:
            continue

        # Calcula intensidade com diferença clara entre 0 e 1+ startups
        max_count = df_regiao['count'].max()
        if not max_count or max_count <= 0:
            # Se todos têm 0 startups, define intensidade mínima visível
            df_regiao['intensidade'] = 0.05  # Intensidade muito baixa mas visível
        else:
            # Municípios com 0 startups: intensidade baixa (0.05)
            # Municípios com 1+ startups: intensidade normalizada entre 0.25 e 1.0
            # Isso cria uma diferença clara visualmente
            df_regiao['intensidade'] = df_regiao['count'].apply(
                lambda x: 0.05 if x == 0 else 0.25 + (x / max_count) * 0.75
            )

        # Identifica municípios com match no GeoJSON (garante que código seja string)
        df_regiao['codigo_ibge_str'] = df_regiao['codigo_ibge'].astype(str)
        df_regiao['tem_match'] = df_regiao['codigo_ibge_str'].apply(lambda x: x in features_by_code)
        
        # Coleta municípios sem match para debug
        sem_match = df_regiao[~df_regiao['tem_match']]
        if not sem_match.empty:
            municipios_sem_match.extend(sem_match[[coluna_municipio, 'codigo_ibge']].values.tolist())
        
        # Filtra apenas municípios com match no GeoJSON
        df_regiao_com_match = df_regiao[df_regiao['tem_match']].copy()
        if df_regiao_com_match.empty:
            continue

        features_region = [features_by_code.get(str(code)) for code in df_regiao_com_match['codigo_ibge']]
        features_region = [feat for feat in features_region if feat is not None]
        if not features_region:
            continue

        geojson_regiao = {"type": "FeatureCollection", "features": features_region}

        # Prepara valores individuais para cada categoria (antes de criar o trace)
        qtd_startups_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_startups], errors='coerce').fillna(0).astype(int).values if coluna_qtd_startups in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))
        qtd_empresas_ancora_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_empresas_ancora], errors='coerce').fillna(0).astype(int).values if coluna_qtd_empresas_ancora in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))
        qtd_fundos_e_investidores_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_fundos_e_investidores], errors='coerce').fillna(0).astype(int).values if coluna_qtd_fundos_e_investidores in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))
        qtd_universidades_icts_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_universidades_icts], errors='coerce').fillna(0).astype(int).values if coluna_qtd_universidades_icts in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))
        qtd_orgaos_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_orgaos], errors='coerce').fillna(0).astype(int).values if coluna_qtd_orgaos in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))

        # Constrói hovertemplate dinamicamente baseado nas categorias selecionadas
        hovertemplate_parts = [
            "<b>Região:</b> %{customdata[0]}<br>",
            "<b>Município:</b> %{customdata[1]}<br>"
        ]
        
        # Se nenhuma categoria selecionada, mostra todas as disponíveis
        categorias_para_mostrar = categorias_selecionadas if categorias_selecionadas else categorias_disponiveis
        
        # Adiciona todas as categorias no customdata na ordem fixa: startups, empresas âncora, fundos, universidades, órgãos
        # Índices: 0=região, 1=município, 2=startups, 3=empresas âncora, 4=fundos e investidores, 5=universidades e ICTs, 6=órgãos
        
        # Adiciona apenas as categorias que devem ser mostradas no hovertemplate
        if "Startup" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Startups:</b> %{customdata[2]}<br>")
        
        if "Empresa Âncora" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Empresas Âncora:</b> %{customdata[3]}<br>")
        
        if "Fundos e Investidores" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Fundos e Investidores:</b> %{customdata[4]}<br>")
        
        if "Universidades e ICTs" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Universidades e ICTs:</b> %{customdata[5]}<br>")
        
        if "Órgãos Públicos e Apoio" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Órgãos Públicos e Apoio:</b> %{customdata[6]}<br>")
        
        hovertemplate_parts.append("<extra></extra>")
        hovertemplate_str = "".join(hovertemplate_parts)

        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson_regiao,
                locations=df_regiao_com_match['codigo_ibge_str'],
                z=df_regiao_com_match['intensidade'],
                zmin=0,
                zmax=1,
                featureidkey="properties.codigo_ibge",
                colorscale=build_colorscale(base_colors[regiao]),
                marker_opacity=0.98,
                marker_line_width=0.3,
                marker_line_color="rgba(60,60,60,0.25)",
                customdata=np.stack(
                    (
                        np.full(len(df_regiao_com_match), regiao),
                        df_regiao_com_match[coluna_municipio].values,
                        qtd_startups_vals,
                        qtd_empresas_ancora_vals,
                        qtd_fundos_e_investidores_vals,
                        qtd_universidades_icts_vals,
                        qtd_orgaos_vals,
                    ),
                    axis=-1,
                ),
                hovertemplate=hovertemplate_str,
                name=regiao,
                showscale=False,
                showlegend=True,
            )
        )
    
    map_layers = [MAP_BASE_LAYER] if MAP_BASE_LAYER else []

    fig.update_layout(
        mapbox=dict(
            style=MAP_STYLE,
            center=map_center,
            zoom=map_zoom,
            layers=map_layers,
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        title_text="Mapa Político de Minas Gerais - Divisão por Região",
        showlegend=True,
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 30, 0.95)",
            bordercolor="rgba(255, 255, 255, 0.2)",
            font=dict(size=15, color="rgba(255, 255, 255, 0.95)", family="Arial, sans-serif"),
            namelength=-1,
        ),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(0,0,0,0.75)",
            bordercolor="rgba(255,255,255,0.3)",
            borderwidth=1,
            font=dict(color="#e2e8f0", size=13),
            itemclick="toggleothers",
            itemdoubleclick="toggle",
            tracegroupgap=8,
            itemsizing="constant",
            itemwidth=30,
        ),
        height=MAP_HEIGHT,
        plot_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
        paper_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
    )

    # Mostra o mapa no lado direito (legenda está dentro do mapa)
    with col_map:
        st.plotly_chart(fig, use_container_width=True, config=MAP_CONFIG)


def create_alternative_choropleth(df_regions):
    """
    Cria mapa alternativo (scatter) caso o GeoJSON não esteja disponível.
    """
    if df_regions.empty:
        st.warning("⚠️ Sem dados para gerar visualização alternativa.")
        return

    regioes = sorted(df_regions['regiao_final'].unique())
    base_colors = {regiao: REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)] for i, regiao in enumerate(regioes)}

    fig = go.Figure()

    for regiao in regioes:
        df_regiao = df_regions[df_regions['regiao_final'] == regiao].copy()
        if df_regiao.empty:
            continue

        max_count = df_regiao['count'].max()
        if not max_count or max_count <= 0:
            df_regiao['intensidade'] = 0.0
        else:
            df_regiao['intensidade'] = (df_regiao['count'] / max_count).clip(0, 1)

        marker_colors = [color_with_intensity(base_colors[regiao], val) for val in df_regiao['intensidade']]
        fill_color = color_with_intensity(base_colors[regiao], df_regiao['intensidade'].max())

        fig.add_trace(
            go.Scattermapbox(
                lat=df_regiao['latitude'],
                lon=df_regiao['longitude'],
                mode='markers',
                name=regiao,
                marker=dict(size=12, color=marker_colors, opacity=0.95),
                text=[f"{nome} ({cnt} startups)" for nome, cnt in zip(df_regiao['nome'], df_regiao['count'])],
                hovertemplate='<b>%{text}</b><extra></extra>',
                showlegend=True,
            )
        )

    map_layers = [MAP_BASE_LAYER] if MAP_BASE_LAYER else []

    fig.update_layout(
        mapbox=dict(
            style=MAP_STYLE,
            center=MAP_CENTER,
            zoom=MAP_ZOOM,
            layers=map_layers,
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        title_text="Mapa de Minas Gerais - Visualização por Região",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="right",
            x=0.98,
            bgcolor="rgba(0,0,0,0.7)",
            bordercolor="rgba(255,255,255,0.2)",
            borderwidth=1,
            font=dict(color="#e2e8f0", size=11),
            itemclick="toggleothers",
            itemdoubleclick="toggle",
        ),
        height=MAP_HEIGHT,
        plot_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
        paper_bgcolor="rgba(0,0,0,0)",  # Fundo transparente para combinar com a página
    )

    # Mostra o mapa ocupando toda a largura (legenda está dentro do mapa)
    st.plotly_chart(fig, use_container_width=True, config=MAP_CONFIG)

def _build_custom_html_table(df_display, styled_df, is_multiindex, categoria_col_for_style, 
                             regiao_col_for_style, regioes_cores, coluna_site, format_dict):
    """
    Constrói tabela HTML manualmente com tooltips para links de site.
    """
    # Identifica índices das colunas
    site_col_idx = None
    categoria_col_idx = None
    regiao_col_idx = None
    
    if is_multiindex:
        columns_list = list(df_display.columns)
        for idx, col_tuple in enumerate(columns_list):
            if len(col_tuple) == 2:
                col_name = col_tuple[1]
                if col_name == coluna_site:
                    site_col_idx = idx
                if categoria_col_for_style and len(categoria_col_for_style) == 2 and categoria_col_for_style[1] == col_name:
                    categoria_col_idx = idx
                if regiao_col_for_style and len(regiao_col_for_style) == 2 and regiao_col_for_style[1] == col_name:
                    regiao_col_idx = idx
    else:
        columns_list = list(df_display.columns)
        for idx, col in enumerate(columns_list):
            if col == coluna_site:
                site_col_idx = idx
            if col == categoria_col_for_style:
                categoria_col_idx = idx
            if col == regiao_col_for_style:
                regiao_col_idx = idx
    
    # Inicia construção do HTML
    html_parts = ['<table id="data-table" style="width:100%;border-collapse:collapse;">']
    
    # Cabeçalhos
    if is_multiindex:
        # Primeira linha: cabeçalhos agrupados
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        
        # Agrupa colunas por grupo para calcular colspan
        groups = {}
        for idx, col_tuple in enumerate(df_display.columns):
            if len(col_tuple) == 2:
                group_name = col_tuple[0]
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(idx)
            else:
                if '' not in groups:
                    groups[''] = []
                groups[''].append(idx)
        
        # Renderiza cabeçalhos agrupados
        for group_name, indices in groups.items():
            if group_name:  # Só renderiza se tiver nome
                colspan = len(indices)
                if group_name == "Dados Gerais":
                    bg_color = "rgba(31, 119, 180, 0.25)"
                elif group_name == "Dados (Startups)":
                    bg_color = "rgba(44, 160, 44, 0.25)"
                else:
                    bg_color = "transparent"
                html_parts.append(f'<th colspan="{colspan}" style="background-color:{bg_color};color:white;font-weight:600;padding:8px;text-align:left;border:1px solid rgba(255,255,255,0.1);">{group_name}</th>')
        
        html_parts.append('</tr>')
        
        # Segunda linha: nomes das colunas
        html_parts.append('<tr>')
        for col_tuple in df_display.columns:
            if len(col_tuple) == 2:
                col_name = col_tuple[1]
            else:
                col_name = col_tuple
            style = 'padding:8px;text-align:left;border:1px solid rgba(255,255,255,0.1);'
            html_parts.append(f'<th style="{style}">{col_name}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')
    else:
        html_parts.append('<thead><tr>')
        for col in df_display.columns:
            style = 'padding:8px;text-align:left;border:1px solid rgba(255,255,255,0.1);'
            html_parts.append(f'<th style="{style}">{col}</th>')
        html_parts.append('</tr></thead>')
    
    # Corpo da tabela
    html_parts.append('<tbody>')
    for idx, row in df_display.iterrows():
        # Obtém o link do site para o tooltip
        site_url = ''
        if site_col_idx is not None:
            site_value = row[df_display.columns[site_col_idx]]
            if pd.notna(site_value) and str(site_value).strip():
                site_url = str(site_value).strip()
                if not site_url.startswith(('http://', 'https://')):
                    site_url = 'https://' + site_url
        
        # Adiciona linha da tabela
        html_parts.append('<tr>')
        for col_idx, col in enumerate(df_display.columns):
            if is_multiindex and len(col) == 2:
                col_name = col[1]
            else:
                col_name = col
            
            value = row[col]
            cell_style = 'padding:8px;border:1px solid rgba(255,255,255,0.1);'
            
            # Aplica estilos específicos
            if col_idx == categoria_col_idx and categoria_col_for_style:
                valor_str = str(value).strip() if pd.notna(value) else ''
                cor = None
                for cat_key, cat_cor in CATEGORIA_COLORS.items():
                    if cat_key.lower() in valor_str.lower() or valor_str.lower() in cat_key.lower():
                        cor = cat_cor
                        break
                if not cor:
                    cor = "#6c757d"
                if cor.startswith('#'):
                    r, g, b = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)
                    cor_transparente = f"rgba({r}, {g}, {b}, 0.3)"
                else:
                    cor_transparente = cor
                cell_style += f'background-color:{cor_transparente};border-left:3px solid {cor};'
            
            if col_idx == regiao_col_idx and regiao_col_for_style and regioes_cores:
                valor_str = str(value).strip() if pd.notna(value) else ''
                cor_hex = regioes_cores.get(valor_str, "#6c757d")
                cor_rgba = color_with_intensity(cor_hex, 0.0, min_alpha=0.18)
                cell_style += f'background-color:{cor_rgba};'
            
            # Formata valor
            if pd.isna(value):
                cell_value = ''
            else:
                # Para coluna de site, adiciona ícone clicável
                if col_idx == site_col_idx and site_url:
                    # Escapa apenas o texto para exibição, mas mantém a URL original no href
                    import html as html_module
                    # Escapa o valor para exibição
                    value_escaped = html_module.escape(str(value)) if value else ''
                    # URL no href não precisa ser escapada (mas escapa para o title)
                    site_url_title = html_module.escape(site_url)
                    cell_value = f'<a href="{site_url}" target="_blank" rel="noopener noreferrer" style="color:#4A9EFF;text-decoration:none;font-size:1.2rem;margin-right:8px;display:inline-block;" title="{site_url_title}">🔗</a><span style="color:#cccccc;">{value_escaped}</span>'
                else:
                    # Formata outros valores
                    cell_value = str(value)
                    # Aplica formatação de ano se necessário
                    if format_dict and col in format_dict:
                        try:
                            num_val = float(value)
                            cell_value = f"{int(num_val)}"
                        except:
                            pass
            
            html_parts.append(f'<td style="{cell_style}">{cell_value}</td>')
        html_parts.append('</tr>')
    html_parts.append('</tbody>')
    html_parts.append('</table>')
    
    # Adiciona CSS para estilização da tabela
    css_js = """
    <style>
        #data-table, #data-table-2 {
            width: 100%;
            border-collapse: collapse;
            background-color: transparent;
        }
        #data-table th, #data-table td, #data-table-2 th, #data-table-2 td {
            color: white;
        }
        #data-table td a, #data-table-2 td a {
            text-decoration: none;
        }
        #data-table td a:hover, #data-table-2 td a:hover {
            opacity: 0.8;
            transform: scale(1.1);
            transition: all 0.2s ease;
        }
    </style>
    """
    
    return css_js + ''.join(html_parts)

def create_data_table(df, df_regions_map=None):
    """
    Cria tabela de dados detalhados das startups (aba "Base | Atores MG")
    
    Args:
        df: DataFrame com os dados das startups
        df_regions_map: DataFrame opcional com dados das regiões para obter cores consistentes
    """
    # Identifica a coluna de categoria (busca case-insensitive e por substring)
    coluna_categoria = None
    possiveis_colunas_categoria = ['categoria', 'category', 'tipo', 'type', 'tipo_ator', 'actor_type', 'categoria_ator']
    
    # Primeiro tenta match exato (case-insensitive)
    for col in df.columns:
        col_lower = col.lower().strip()
        for possivel in possiveis_colunas_categoria:
            if col_lower == possivel.lower():
                coluna_categoria = col
                break
        if coluna_categoria:
            break
    
    # Se não encontrou, tenta busca por substring
    if not coluna_categoria:
        for col in df.columns:
            col_lower = col.lower().strip()
            for possivel in possiveis_colunas_categoria:
                if possivel.lower() in col_lower or col_lower in possivel.lower():
                    coluna_categoria = col
                    break
            if coluna_categoria:
                break
    
    # Debug temporário - mostra colunas disponíveis (comentar depois)
    # st.info(f"🔍 Colunas disponíveis: {', '.join(list(df.columns))}")
    # if coluna_categoria:
    #     st.success(f"✅ Coluna de categoria encontrada: {coluna_categoria}")
    # else:
    #     st.warning(f"⚠️ Coluna de categoria NÃO encontrada. Procurando por: {possiveis_colunas_categoria}")
    
    # Seleciona colunas principais para exibição (da aba "Base | Atores MG")
    # Ordem de prioridade: name, categoria, cidade, região sebrae, setor, foundationYear, description
    colunas_disponiveis = []
    colunas_adicionadas = set()
    
    # Função auxiliar para adicionar coluna se existir
    def adicionar_coluna(col_nome):
        if col_nome in df.columns and col_nome not in colunas_adicionadas:
            colunas_disponiveis.append(col_nome)
            colunas_adicionadas.add(col_nome)
    
    # Função auxiliar para buscar coluna por nome (case-insensitive)
    def buscar_coluna(nomes_possiveis):
        for nome in nomes_possiveis:
            for col in df.columns:
                if col.lower().strip() == nome.lower().strip():
                    adicionar_coluna(col)
                    return
    
    # 1. Nome do ator
    buscar_coluna(['name', 'nome', 'nome do ator'])
    if 'name' in df.columns and 'name' not in colunas_adicionadas:
        adicionar_coluna('name')
    
    # 2. Site (segunda coluna em Dados Gerais)
    coluna_site = None
    possiveis_colunas_site = ['site', 'website', 'url', 'link', 'web', 'homepage']
    for col in df.columns:
        col_lower = col.lower().strip()
        if any(nome in col_lower for nome in possiveis_colunas_site):
            coluna_site = col
            adicionar_coluna(col)
            break
    
    # 3. Categoria (já identificada acima) - terceira coluna
    # Se encontrou a coluna de categoria, adiciona
    if coluna_categoria and coluna_categoria not in colunas_adicionadas:
        adicionar_coluna(coluna_categoria)
    # Se não encontrou mas existe alguma coluna que pode ser categoria, tenta adicionar todas as possíveis
    elif not coluna_categoria:
        # Tenta encontrar qualquer coluna que possa ser categoria
        for col in df.columns:
            col_lower = col.lower().strip()
            if any(palavra in col_lower for palavra in ['categoria', 'category', 'tipo', 'type', 'ator', 'actor']):
                coluna_categoria = col
                adicionar_coluna(col)
                break
    
    # 3. Cidade
    buscar_coluna(['cidade_max', 'cidade', 'municipio', 'município', 'city'])
    
    # 4. Região Sebrae (procura por qualquer coluna que contenha essas palavras)
    for col in df.columns:
        col_lower = col.lower().strip()
        if ('sebrae' in col_lower or 'regiao' in col_lower or 'região' in col_lower) and col not in colunas_adicionadas:
            adicionar_coluna(col)
            break
    
    # 6. Setor
    buscar_coluna(['sector', 'setor', 'setores'])
    
    # 7. Ano de fundação
    buscar_coluna(['foundationyear', 'foundation_year', 'ano de fundação', 'ano'])
    
    # 8. Descrição
    buscar_coluna(['description', 'descrição', 'descricao'])
    
    # Se não encontrou nenhuma coluna específica, usa todas as colunas disponíveis
    if not colunas_disponiveis:
        colunas_disponiveis = list(df.columns[:10]) if len(df.columns) > 0 else []
    
    if colunas_disponiveis:
        # Garante ordem correta: name, site, categoria, ...
        # Remove colunas da posição atual e reorganiza
        colunas_ordenadas = []
        
        # 1. Nome do ator (primeira coluna)
        for col in colunas_disponiveis:
            col_lower = str(col).lower().strip()
            if any(palavra in col_lower for palavra in ['name', 'nome']) and not any(palavra in col_lower for palavra in ['empresa', 'company']):
                colunas_ordenadas.append(col)
                break
        
        # 2. Site (segunda coluna)
        if coluna_site and coluna_site in colunas_disponiveis:
            colunas_ordenadas.append(coluna_site)
        
        # 3. Categoria (terceira coluna)
        if coluna_categoria and coluna_categoria in colunas_disponiveis:
            colunas_ordenadas.append(coluna_categoria)
        
        # Adiciona as outras colunas na ordem que aparecem
        for col in colunas_disponiveis:
            if col not in colunas_ordenadas:
                colunas_ordenadas.append(col)
        
        colunas_disponiveis = colunas_ordenadas
        
        # Cria uma cópia para estilização
        df_display = df[colunas_disponiveis].copy()
        
        # Processa a coluna de site - formata como texto simples
        if coluna_site and coluna_site in df_display.columns:
            def formatar_site_completo(url):
                """
                Formata o campo de site para exibir a URL por extenso (texto simples).
                """
                if pd.isna(url) or str(url).strip() == '':
                    return ''
                url_str = str(url).strip()
                # Garante que a URL tenha protocolo
                if not url_str.startswith(('http://', 'https://')):
                    url_str = 'https://' + url_str
                return url_str
            
            # Aplica a função para formatar o site como texto simples
            df_display[coluna_site] = df_display[coluna_site].apply(formatar_site_completo)
        
        # Formata a coluna "Ano de Fundação" para remover casas decimais
        for col in df_display.columns:
            col_lower = str(col).lower().strip()
            if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                # Converte para numérico e depois para inteiro, removendo decimais
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                # Converte para inteiro, tratando NaNs
                df_display[col] = df_display[col].apply(lambda x: int(float(x)) if pd.notna(x) else pd.NA)
        
        # Identifica quais colunas pertencem a cada grupo
        # Usa as colunas reais do df_display (que pode incluir "Link" adicionada depois)
        colunas_dados_gerais = []
        colunas_dados_startups = []
        outras_colunas = []
        
        # Identifica as colunas de cada grupo de forma mais precisa
        # Itera sobre as colunas reais do DataFrame, não apenas colunas_disponiveis
        for col in df_display.columns:
            col_lower = str(col).lower().strip()
            
            # Dados Gerais: name/nome, site, categoria, cidade, região sebrae
            if (any(palavra in col_lower for palavra in ['name', 'nome']) and not any(palavra in col_lower for palavra in ['empresa', 'company'])) or \
               any(palavra in col_lower for palavra in ['site', 'website', 'url', 'link']) or \
               any(palavra in col_lower for palavra in ['categoria', 'category']) or \
               any(palavra in col_lower for palavra in ['cidade', 'municipio', 'city']) or \
               any(palavra in col_lower for palavra in ['regiao', 'região', 'sebrae']):
                colunas_dados_gerais.append(col)
            # Dados (Startups): setor, ano de fundação
            elif any(palavra in col_lower for palavra in ['sector', 'setor']) or \
                 any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                colunas_dados_startups.append(col)
            else:
                outras_colunas.append(col)
        
        # Cria MultiIndex para cabeçalhos agrupados
        if colunas_dados_gerais or colunas_dados_startups:
            tuples = []
            # Adiciona colunas de Dados Gerais
            for col in colunas_dados_gerais:
                tuples.append(('Dados Gerais', col))
            # Adiciona colunas de Dados (Startups)
            for col in colunas_dados_startups:
                tuples.append(('Dados (Startups)', col))
            # Adiciona outras colunas sem cabeçalho agrupado
            for col in outras_colunas:
                tuples.append(('', col))
            
            # Cria MultiIndex
            df_display.columns = pd.MultiIndex.from_tuples(tuples)
        
        # Verifica se está usando MultiIndex
        is_multiindex = isinstance(df_display.columns, pd.MultiIndex)
        
        # Formata novamente após criar MultiIndex (caso necessário)
        # Formata a coluna "Ano de Fundação" para remover casas decimais
        if is_multiindex:
            for col_tuple in df_display.columns:
                if len(col_tuple) == 2:
                    col = col_tuple[1]
                else:
                    col = col_tuple
                col_lower = str(col).lower().strip()
                if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                    # Converte para numérico e depois para inteiro
                    df_display[col_tuple] = pd.to_numeric(df_display[col_tuple], errors='coerce')
                    df_display[col_tuple] = df_display[col_tuple].apply(lambda x: int(float(x)) if pd.notna(x) and not pd.isna(x) else pd.NA)
        else:
            for col in df_display.columns:
                col_lower = str(col).lower().strip()
                if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                    df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                    df_display[col] = df_display[col].apply(lambda x: int(float(x)) if pd.notna(x) and not pd.isna(x) else pd.NA)
        
        # Encontra a coluna de categoria para estilização (pode estar em MultiIndex ou não)
        categoria_col_for_style = None
        if coluna_categoria:
            if is_multiindex:
                # Procura a coluna de categoria no MultiIndex (segundo nível)
                for col_tuple in df_display.columns:
                    if len(col_tuple) == 2 and col_tuple[1] == coluna_categoria:
                        categoria_col_for_style = col_tuple
                        break
            else:
                if coluna_categoria in df_display.columns:
                    categoria_col_for_style = coluna_categoria
        
        # Encontra a coluna de região Sebrae para estilização
        coluna_regiao_sebrae = None
        for col in df.columns:
            col_lower = col.lower().strip()
            if ('sebrae' in col_lower or 'regiao' in col_lower or 'região' in col_lower) and col in colunas_disponiveis:
                coluna_regiao_sebrae = col
                break
        
        # Obtém cores das regiões (mesma lógica do mapa)
        regioes_cores = {}
        if coluna_regiao_sebrae and coluna_regiao_sebrae in df.columns:
            # Obtém todas as regiões únicas do DataFrame
            regioes_unicas = sorted(df[coluna_regiao_sebrae].dropna().unique())
            # Atribui cores usando a mesma paleta do mapa
            regioes_cores = {regiao: REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)] for i, regiao in enumerate(regioes_unicas)}
        
        # Encontra a coluna de região no DataFrame display (pode estar em MultiIndex)
        regiao_col_for_style = None
        if coluna_regiao_sebrae:
            if is_multiindex:
                # Procura a coluna de região no MultiIndex (segundo nível)
                for col_tuple in df_display.columns:
                    if len(col_tuple) == 2 and col_tuple[1] == coluna_regiao_sebrae:
                        regiao_col_for_style = col_tuple
                        break
            else:
                if coluna_regiao_sebrae in df_display.columns:
                    regiao_col_for_style = coluna_regiao_sebrae
        
        # Aplica estilo se tiver coluna de categoria
        if categoria_col_for_style:
            # Função para aplicar cores semi-transparentes
            def style_categoria(val):
                if pd.isna(val):
                    return ''
                valor_str = str(val).strip()
                # Busca a cor correspondente (case-insensitive e permite variações)
                cor = None
                for categoria_key, categoria_cor in CATEGORIA_COLORS.items():
                    if categoria_key.lower() in valor_str.lower() or valor_str.lower() in categoria_key.lower():
                        cor = categoria_cor
                        break
                
                if not cor:
                    cor = "#6c757d"  # Cinza como padrão
                
                # Converte para rgba com transparência
                if cor.startswith('#'):
                    r = int(cor[1:3], 16)
                    g = int(cor[3:5], 16)
                    b = int(cor[5:7], 16)
                    cor_transparente = f"rgba({r}, {g}, {b}, 0.3)"
                else:
                    cor_transparente = cor
                
                return f'background-color: {cor_transparente}; border-left: 3px solid {cor}; padding: 4px 8px;'
            
            # Usa map em vez de applymap (applymap está deprecated)
            styled_df = df_display.style.map(
                style_categoria,
                subset=[categoria_col_for_style]
            )
            
            # Aplica cores nas células da coluna de região (se existir)
            if regiao_col_for_style and regioes_cores:
                def style_regiao(val):
                    if pd.isna(val):
                        return ''
                    valor_str = str(val).strip()
                    # Busca a cor correspondente à região
                    cor_hex = regioes_cores.get(valor_str, "#6c757d")  # Cinza como padrão
                    # Usa color_with_intensity com intensity=0 (min_alpha padrão é 0.18)
                    cor_rgba = color_with_intensity(cor_hex, 0.0, min_alpha=0.18)
                    return f'background-color: {cor_rgba}; padding: 4px 8px;'
                
                styled_df = styled_df.map(
                    style_regiao,
                    subset=[regiao_col_for_style]
                )
            
            # Formata coluna de ano de fundação para exibir sem decimais
            format_dict = {}
            if is_multiindex:
                for col_tuple in df_display.columns:
                    if len(col_tuple) == 2:
                        col = col_tuple[1]
                    else:
                        col = col_tuple
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col_tuple] = '{:.0f}'
            else:
                for col in df_display.columns:
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col] = '{:.0f}'
            
            if format_dict:
                styled_df = styled_df.format(format_dict, na_rep='')
            
            # Adiciona estilos aos cabeçalhos do MultiIndex
            if is_multiindex:
                # Cor semi-transparente para "Dados Gerais" (azul suave)
                cor_dados_gerais = "rgba(31, 119, 180, 0.25)"  # Azul semi-transparente
                # Cor semi-transparente para "Dados (Startups)" (verde suave)
                cor_dados_startups = "rgba(44, 160, 44, 0.25)"  # Verde semi-transparente
                
                # Estilos para os cabeçalhos do MultiIndex
                # Agrupa colunas por cabeçalho para aplicar estilos
                header_styles = []
                
                # Encontra índices das colunas de cada grupo
                indices_dados_gerais = []
                indices_dados_startups = []
                
                for idx, col_tuple in enumerate(df_display.columns):
                    if len(col_tuple) == 2:
                        header_name = col_tuple[0]
                        if header_name == "Dados Gerais":
                            indices_dados_gerais.append(idx)
                        elif header_name == "Dados (Startups)":
                            indices_dados_startups.append(idx)
                
                # Aplica estilos para "Dados Gerais"
                if indices_dados_gerais:
                    for idx in indices_dados_gerais:
                        header_styles.append({
                            'selector': f'th.col{idx}.level0',
                            'props': [('background-color', cor_dados_gerais), ('color', 'white'), ('font-weight', '600')]
                        })
                
                # Aplica estilos para "Dados (Startups)"
                if indices_dados_startups:
                    for idx in indices_dados_startups:
                        header_styles.append({
                            'selector': f'th.col{idx}.level0',
                            'props': [('background-color', cor_dados_startups), ('color', 'white'), ('font-weight', '600')]
                        })
                
                if header_styles:
                    styled_df = styled_df.set_table_styles(header_styles, overwrite=False)
            
            # Formata coluna de ano de fundação para exibir sem decimais
            format_dict = {}
            if is_multiindex:
                for col_tuple in df_display.columns:
                    if len(col_tuple) == 2:
                        col = col_tuple[1]
                    else:
                        col = col_tuple
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col_tuple] = '{:.0f}'
            else:
                for col in df_display.columns:
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col] = '{:.0f}'
            
            if format_dict:
                styled_df = styled_df.format(format_dict, na_rep='')
            
            # Constrói tabela HTML manualmente com tooltips para links
            if coluna_site and coluna_site in df_display.columns:
                html_table = _build_custom_html_table(
                    df_display, styled_df, is_multiindex, 
                    categoria_col_for_style, regiao_col_for_style, 
                    regioes_cores, coluna_site, format_dict
                )
                
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            # Aplica cores nas células da coluna de região (se existir) mesmo sem coluna de categoria
            styled_df = None
            if regiao_col_for_style and regioes_cores:
                # Cria styled_df primeiro
                styled_df = df_display.style
                def style_regiao(val):
                    if pd.isna(val):
                        return ''
                    valor_str = str(val).strip()
                    # Busca a cor correspondente à região
                    cor_hex = regioes_cores.get(valor_str, "#6c757d")  # Cinza como padrão
                    # Usa color_with_intensity com intensity=0 (min_alpha padrão é 0.18)
                    cor_rgba = color_with_intensity(cor_hex, 0.0, min_alpha=0.18)
                    return f'background-color: {cor_rgba}; padding: 4px 8px;'
                
                styled_df = df_display.style.map(
                    style_regiao,
                    subset=[regiao_col_for_style]
                )
            
            # Aplica estilos aos cabeçalhos do MultiIndex mesmo sem coluna de categoria
            if is_multiindex:
                # Cor semi-transparente para "Dados Gerais" (azul suave)
                cor_dados_gerais = "rgba(31, 119, 180, 0.25)"  # Azul semi-transparente
                # Cor semi-transparente para "Dados (Startups)" (verde suave)
                cor_dados_startups = "rgba(44, 160, 44, 0.25)"  # Verde semi-transparente
                
                # Estilos para os cabeçalhos do MultiIndex
                header_styles = []
                
                # Encontra índices das colunas de cada grupo
                indices_dados_gerais = []
                indices_dados_startups = []
                
                for idx, col_tuple in enumerate(df_display.columns):
                    if len(col_tuple) == 2:
                        header_name = col_tuple[0]
                        if header_name == "Dados Gerais":
                            indices_dados_gerais.append(idx)
                        elif header_name == "Dados (Startups)":
                            indices_dados_startups.append(idx)
                
                # Aplica estilos para "Dados Gerais"
                if indices_dados_gerais:
                    for idx in indices_dados_gerais:
                        header_styles.append({
                            'selector': f'th.col{idx}.level0',
                            'props': [('background-color', cor_dados_gerais), ('color', 'white'), ('font-weight', '600')]
                        })
                
                # Aplica estilos para "Dados (Startups)"
                if indices_dados_startups:
                    for idx in indices_dados_startups:
                        header_styles.append({
                            'selector': f'th.col{idx}.level0',
                            'props': [('background-color', cor_dados_startups), ('color', 'white'), ('font-weight', '600')]
                        })
                
                if header_styles:
                    if styled_df is None:
                        styled_df = df_display.style
                    styled_df = styled_df.set_table_styles(header_styles)
            
            # Formata coluna de ano de fundação para exibir sem decimais
            if styled_df is None:
                styled_df = df_display.style
            
            format_dict = {}
            if is_multiindex:
                for col_tuple in df_display.columns:
                    if len(col_tuple) == 2:
                        col = col_tuple[1]
                    else:
                        col = col_tuple
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col_tuple] = '{:.0f}'
            else:
                for col in df_display.columns:
                    col_lower = str(col).lower().strip()
                    if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                        format_dict[col] = '{:.0f}'
            
            if format_dict:
                styled_df = styled_df.format(format_dict, na_rep='')
            
            # Para renderizar HTML na coluna de link (ícone) ou site, precisamos usar tabela customizada
            coluna_com_html = coluna_site
            if coluna_com_html and coluna_com_html in df_display.columns:
                # Constrói tabela HTML manualmente para garantir que links funcionem
                html_table = _build_custom_html_table(
                    df_display, styled_df, is_multiindex, 
                    categoria_col_for_style, regiao_col_for_style, 
                    regioes_cores, coluna_site, format_dict
                )
                
                # Substitui o ID da tabela para o segundo caso
                html_table = html_table.replace('id="data-table"', 'id="data-table-2"')
                
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhuma coluna encontrada nos dados.")

def main():
    """
    Função principal do dashboard
    """
    
    # Adiciona botões de controle no topo da página
    col1, col2, col3 = st.columns([1, 1, 10])
    with col1:
        if st.button("🔄 Limpar Cache", help="Força o reload dos dados da planilha", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache limpo! Recarregando...")
            st.rerun()
    
    with col2:
        if st.button("📊 Debug", help="Mostra informações sobre os dados carregados", use_container_width=True):
            st.session_state.show_debug = not st.session_state.get('show_debug', False)
            st.rerun()
    
    # Carrega dados do mapa (aba "Municípios e Regiões")
    with st.spinner("Carregando dados do mapa..."):
        df_mapa = load_data_municipios_regioes(force_reload=False)
    
    # Carrega dados da tabela (aba "Base | Atores MG")
    with st.spinner("Carregando dados das startups..."):
        df_startups = load_data_base_atores(force_reload=False)
    
    # Mostra informações de debug se solicitado
    if st.session_state.get('show_debug', False):
        st.info("🔍 **Informações de Debug:**")
        col_debug1, col_debug2 = st.columns(2)
        with col_debug1:
            st.write(f"**Dados do Mapa:** {len(df_mapa)} linhas")
            if not df_mapa.empty:
                st.write(f"Colunas: {', '.join(df_mapa.columns[:5].tolist())}...")
        with col_debug2:
            st.write(f"**Dados da Tabela:** {len(df_startups)} linhas")
            if not df_startups.empty:
                st.write(f"Colunas: {', '.join(df_startups.columns[:5].tolist())}...")
                # Mostra primeiras linhas da primeira coluna
                primeira_col = df_startups.columns[0]
                st.write(f"Primeira coluna: **{primeira_col}**")
                valores_unicos = df_startups[primeira_col].dropna().unique()[:5]
                st.write(f"Primeiros valores: {list(valores_unicos)}")
        st.markdown("---")
    
    if df_mapa.empty:
        st.error("Não foi possível carregar os dados do mapa.")
        return
    
    if df_startups.empty:
        st.warning("Não foi possível carregar os dados das startups. A tabela não será exibida.")
    
    # Usa os dados sem filtros do sidebar (sidebar removido)
    df_mapa_filtered = df_mapa
    
    # Usa os dados sem filtros do sidebar (sidebar removido)
    df_startups_filtered = df_startups if not df_startups.empty else df_startups
    
    # Cria visualizações
    # Análise por setores (apenas se a coluna existir)
    if not df_startups_filtered.empty and 'sector' in df_startups_filtered.columns:
        create_sector_analysis(df_startups_filtered)
    
    # Mapa político choropleth (usa dados de "Municípios e Regiões")
    create_choropleth_map(df_mapa_filtered, df_startups if not df_startups.empty else None)
    
    # Análise temporal (apenas se a coluna existir)
    if not df_startups_filtered.empty and 'foundationYear' in df_startups_filtered.columns:
        create_temporal_analysis(df_startups_filtered)
    
    # Linha separadora antes da tabela
    st.markdown("---")
    
    # Campo de pesquisa acima da tabela
    if not df_startups_filtered.empty:
        # Opção para ignorar filtros do mapa
        st.subheader("📋 Tabela de Dados")
        
        # Contador de dados antes dos filtros
        total_antes_filtros = len(df_startups_filtered)
        
        # Checkbox para ignorar filtros do mapa
        ignorar_filtros = st.checkbox(
            "🔓 Mostrar TODOS os dados (ignorar filtros do mapa)",
            value=False,
            help="Marque esta opção para ver todos os dados, independente dos filtros aplicados no mapa"
        )
        
        # Aplica os mesmos filtros do mapa aos dados das startups (se não estiver ignorando)
        if ignorar_filtros:
            df_startups_para_tabela = df_startups_filtered.copy()
            # Mostra aviso
            st.info(f"📊 Mostrando **TODOS** os {len(df_startups_para_tabela)} registros (filtros do mapa ignorados)")
        else:
            df_startups_para_tabela = df_startups_filtered.copy()
            
            # Obtém os valores dos filtros do session_state (definidos no mapa)
            regiao_filtro_tabela = st.session_state.get("filtro_regiao", "Todas")
            municipio_filtro_tabela = st.session_state.get("filtro_municipio", "Todos")
            categorias_filtro_tabela = st.session_state.get("filtro_categoria", [])
            
            # Conta quantos filtros estão ativos
            filtros_ativos = []
            if regiao_filtro_tabela != "Todas":
                filtros_ativos.append(f"Região: {regiao_filtro_tabela}")
            if municipio_filtro_tabela != "Todos":
                filtros_ativos.append(f"Município: {municipio_filtro_tabela}")
            if categorias_filtro_tabela:
                filtros_ativos.append(f"Categorias: {', '.join(categorias_filtro_tabela)}")
            
            if filtros_ativos:
                st.warning(f"⚠️ **Filtros ativos do mapa:** {', '.join(filtros_ativos)}. Use a opção acima para ver todos os dados.")
        
            # Aplica filtro de região (apenas se não estiver ignorando filtros)
            if not ignorar_filtros and regiao_filtro_tabela != "Todas":
                # Procura coluna de região nas startups (com várias variações)
                coluna_regiao_startups = None
                possiveis_nomes_regiao = ['região sebrae', 'regiao sebrae', 'região_sebrae', 'regiao_sebrae', 
                                         'nome_mesorregiao', 'mesorregiao', 'regiao', 'região']
                for col in df_startups_para_tabela.columns:
                    col_lower = col.lower().strip()
                    if any(nome in col_lower for nome in possiveis_nomes_regiao):
                        coluna_regiao_startups = col
                        break
                
                if coluna_regiao_startups:
                    antes = len(df_startups_para_tabela)
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_regiao_startups].astype(str).str.strip() == regiao_filtro_tabela
                    ]
                    depois = len(df_startups_para_tabela)
                    if st.session_state.get('show_debug', False):
                        st.write(f"🔍 Filtro região: {antes} → {depois} linhas")
            
            # Aplica filtro de município (apenas se não estiver ignorando filtros)
            if not ignorar_filtros and municipio_filtro_tabela != "Todos":
                # Procura coluna de município/cidade nas startups
                coluna_municipio_startups = None
                possiveis_nomes_municipio = ['cidade', 'municipio', 'cidade_max', 'município']
                for col in df_startups_para_tabela.columns:
                    col_lower = col.lower().strip()
                    if any(nome in col_lower for nome in possiveis_nomes_municipio):
                        coluna_municipio_startups = col
                        break
                
                if coluna_municipio_startups:
                    antes = len(df_startups_para_tabela)
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_municipio_startups].astype(str).str.strip() == municipio_filtro_tabela
                    ]
                    depois = len(df_startups_para_tabela)
                    if st.session_state.get('show_debug', False):
                        st.write(f"🔍 Filtro município: {antes} → {depois} linhas")
            
            # Aplica filtro de categoria (apenas se não estiver ignorando filtros)
            if not ignorar_filtros and categorias_filtro_tabela:
                # Procura coluna de categoria nas startups
                coluna_categoria_startups = None
                possiveis_nomes_categoria = ['categoria', 'category', 'tipo', 'type', 'tipo_ator', 'actor_type']
                for col in df_startups_para_tabela.columns:
                    col_lower = col.lower().strip()
                    if any(nome == col_lower or nome in col_lower for nome in possiveis_nomes_categoria):
                        coluna_categoria_startups = col
                        break
                
                if coluna_categoria_startups:
                    # Mapeia categorias do filtro do mapa para categorias reais na tabela
                    categorias_mapeadas = []
                    for cat_filtro in categorias_filtro_tabela:
                        cat_filtro_str = str(cat_filtro).strip()
                        if cat_filtro_str == "Universidades e ICTs":
                            # Mapeia para as categorias reais na tabela
                            categorias_mapeadas.extend(["Universidade", "ICT", "Universidade/ICT"])
                        elif cat_filtro_str == "Órgãos Públicos e Apoio":
                            # Mapeia para as categorias reais na tabela
                            categorias_mapeadas.extend(["Órgão Público", "Órgão de Apoio"])
                        else:
                            # Mantém a categoria original para outras categorias
                            categorias_mapeadas.append(cat_filtro_str)
                    
                    # Remove duplicatas mantendo a ordem
                    categorias_mapeadas = list(dict.fromkeys(categorias_mapeadas))
                    
                    antes = len(df_startups_para_tabela)
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().isin(
                            [str(cat).strip() for cat in categorias_mapeadas]
                        )
                    ]
                    depois = len(df_startups_para_tabela)
                    if st.session_state.get('show_debug', False):
                        st.write(f"🔍 Filtro categoria: {antes} → {depois} linhas")
                        st.write(f"🔍 Categorias mapeadas: {categorias_mapeadas}")
            
            # Mostra contador de dados após filtros
            total_apos_filtros = len(df_startups_para_tabela)
            if total_antes_filtros != total_apos_filtros:
                st.caption(f"📊 Mostrando {total_apos_filtros} de {total_antes_filtros} registros (filtros aplicados)")
            else:
                st.caption(f"📊 Mostrando todos os {total_apos_filtros} registros")
        
        # Campo de pesquisa (fora do bloco if/else para funcionar em ambos os casos)
        texto_pesquisa = st.text_input(
            "🔍 Pesquisar por nome",
            value="",
            placeholder="Digite o nome do ator...",
            key="campo_pesquisa_tabela"
        )
        
        # Filtra os dados baseado na pesquisa
        df_tabela_filtrado = df_startups_para_tabela.copy()
        if texto_pesquisa and texto_pesquisa.strip():
            texto_busca = texto_pesquisa.strip()
            
            # Procura na coluna de nome (pode ter diferentes nomes)
            coluna_nome = None
            possiveis_colunas_nome = ['name', 'nome', 'nome_ator', 'nome_atore', 'actor_name', 'nome_empresa', 'nome do ator']
            
            # Primeiro tenta busca exata (case-insensitive)
            for col in possiveis_colunas_nome:
                if col in df_tabela_filtrado.columns:
                    coluna_nome = col
                    break
            
            # Se não encontrou, tenta busca case-insensitive nos nomes das colunas
            if not coluna_nome:
                for col in df_tabela_filtrado.columns:
                    col_lower = str(col).lower().strip()
                    for possivel in possiveis_colunas_nome:
                        if possivel.lower() in col_lower or col_lower in possivel.lower():
                            coluna_nome = col
                            break
                    if coluna_nome:
                        break
            
            if coluna_nome:
                # Busca case-insensitive e parcial (contém)
                mask = df_tabela_filtrado[coluna_nome].astype(str).str.contains(
                    texto_busca,
                    case=False,
                    na=False,
                    regex=False
                )
                df_tabela_filtrado = df_tabela_filtrado[mask]
            else:
                # Se não encontrou coluna de nome, tenta buscar em todas as colunas de texto
                mask = pd.Series([False] * len(df_tabela_filtrado))
                for col in df_tabela_filtrado.columns:
                    if df_tabela_filtrado[col].dtype == 'object':  # Colunas de texto
                        mask |= df_tabela_filtrado[col].astype(str).str.contains(
                            texto_busca,
                            case=False,
                            na=False,
                            regex=False
                        )
                df_tabela_filtrado = df_tabela_filtrado[mask]
        
        # Tabela de dados (usa dados filtrados)
        create_data_table(df_tabela_filtrado)
    
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🚀 Dashboard Interativo do Ecossistema de Inovação de Minas Gerais</p>
        <p>Desenvolvido com Streamlit</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
