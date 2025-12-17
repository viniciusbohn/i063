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
MAP_STYLE = "carto-positron"  # Estilo claro - fundo será customizado via plot_bgcolor
MAP_BASE_LAYER = None

# Cores oficiais do Sebrae
SEBRAE_AZUL = "#0052A5"  # Azul principal Sebrae
SEBRAE_AZUL_CLARO = "#0066CC"  # Azul claro Sebrae
SEBRAE_VERDE = "#00A859"  # Verde Sebrae
SEBRAE_LARANJA = "#FF6B35"  # Laranja Sebrae
SEBRAE_AMARELO = "#FFC107"  # Amarelo Sebrae
SEBRAE_CINZA_ESCURO = "#333333"  # Cinza escuro
SEBRAE_CINZA_CLARO = "#F5F5F5"  # Cinza claro
SEBRAE_BRANCO = "#FFFFFF"  # Branco

# Paleta de cores Sebrae para regiões (cores distintas para fácil identificação)
SEBRAE_COLOR_PALETTE = [
    SEBRAE_VERDE,          # Verde Sebrae - muito distinto
    SEBRAE_LARANJA,        # Laranja Sebrae - muito distinto
    SEBRAE_AMARELO,        # Amarelo Sebrae - muito distinto
    "#FF1493",             # Rosa/Magenta - muito distinto
    "#00CED1",             # Turquesa escuro - muito distinto
    "#FF6347",             # Tomate - distinto
    "#32CD32",             # Verde Lima - distinto
    "#FFD700",             # Dourado - distinto
    "#9370DB",             # Roxo médio - distinto
    "#20B2AA",             # Verde água - distinto
    "#FF4500",             # Laranja vermelho - distinto
    "#00FA9A",             # Verde médio - distinto
    "#FF69B4",             # Rosa quente - distinto
    "#1E90FF",             # Azul dodger - distinto
]

# Paleta base para regiões (usando cores Sebrae)
REGION_COLOR_PALETTE = SEBRAE_COLOR_PALETTE * 3  # Repete para ter cores suficientes

# Cores para categorias de atores (alinhadas com Sebrae)
CATEGORIA_COLORS = {
    "Startup": SEBRAE_AZUL,  # Azul Sebrae
    "Empresa Âncora": SEBRAE_LARANJA,  # Laranja Sebrae
    "Fundos e Investidores": SEBRAE_VERDE,  # Verde Sebrae
    "Hubs, Incubadoras e Parques Tecnológicos": SEBRAE_AMARELO,  # Amarelo Sebrae
    "Universidades e ICTs": SEBRAE_AZUL_CLARO,  # Azul claro Sebrae
    "Órgãos Públicos e Apoio": SEBRAE_CINZA_ESCURO,  # Cinza escuro
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

# CSS personalizado - Identidade Visual Sebrae
st.markdown(f"""
<style>
    /* Estiliza botões de cards - aplica a todos os botões secondary nas colunas dos cards */
    div[data-testid="column"] button[kind="secondary"] {{
        background: white !important;
        padding: 1.5rem !important;
        border-radius: 15px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
        text-align: center !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease, opacity 0.3s ease !important;
        height: 140px !important;
        min-height: 140px !important;
        max-height: 140px !important;
        width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        cursor: pointer !important;
        white-space: pre-line !important;
        font-size: inherit !important;
        box-sizing: border-box !important;
    }}
    
    div[data-testid="column"] button[kind="secondary"]:hover:not(:disabled) {{
        transform: translateY(-5px) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2) !important;
        background: #f8f9fa !important;
    }}
    
    div[data-testid="column"] button[kind="secondary"]:disabled {{
        opacity: 0.6 !important;
        background: #e9ecef !important;
        cursor: not-allowed !important;
        color: #6c757d !important;
    }}
    
    div[data-testid="column"] button[kind="secondary"]:disabled:hover {{
        opacity: 0.7 !important;
    }}
    
    /* Cards inativos - transparência mas ainda clicáveis */
    .card-inactive button[kind="secondary"],
    div.card-inactive button[kind="secondary"],
    div[data-category] button[kind="secondary"] {{
        opacity: 0.4 !important;
        background: rgba(255, 255, 255, 0.5) !important;
        color: rgba(51, 51, 51, 0.5) !important;
    }}
    
    .card-inactive button[kind="secondary"]:hover,
    div.card-inactive button[kind="secondary"]:hover,
    div[data-category] button[kind="secondary"]:hover {{
        opacity: 0.6 !important;
        background: rgba(248, 249, 250, 0.7) !important;
        transform: translateY(-5px) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2) !important;
    }}
    
    /* JavaScript para aplicar transparência baseado no estado */
    <script>
    function applyCardInactiveStyles() {{
        // Busca todos os containers com data-category
        const containers = document.querySelectorAll('div[data-category]');
        containers.forEach(container => {{
            const category = container.getAttribute('data-category');
            const isInactive = container.classList.contains('card-inactive');
            const button = container.querySelector('button[kind="secondary"]');
            
            if (button && isInactive) {{
                button.style.setProperty('opacity', '0.4', 'important');
                button.style.setProperty('background', 'rgba(255, 255, 255, 0.5)', 'important');
                button.style.setProperty('color', 'rgba(51, 51, 51, 0.5)', 'important');
            }}
        }});
    }}
    
    // Executa quando a página carrega
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', applyCardInactiveStyles);
    }} else {{
        applyCardInactiveStyles();
    }}
    
    // Executa após mudanças no DOM
    const observer = new MutationObserver(applyCardInactiveStyles);
    observer.observe(document.body, {{ childList: true, subtree: true }});
    
    // Executa periodicamente
    setInterval(applyCardInactiveStyles, 500);
    </script>
    
    .metric-card-label {{
        font-size: 0.9rem;
        color: {SEBRAE_CINZA_ESCURO};
        margin-bottom: 0.5rem;
    }}
    
    .metric-card-value {{
        font-size: 2.2rem;
        font-weight: bold;
        color: {SEBRAE_AZUL};
        line-height: 1.2;
    }}
    
    .metric-value {{
        font-size: 2.2rem;
        font-weight: bold;
        margin: 0.3rem 0;
        color: {SEBRAE_AZUL};
        line-height: 1.2;
    }}
    
    .metric-label {{
        font-size: 0.85rem;
        color: {SEBRAE_CINZA_ESCURO};
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
    }}
    
    .site-icon {{
        text-align: center;
        width: 40px;
        min-width: 40px;
        max-width: 40px;
    }}
    .site-icon a {{
        text-decoration: none;
        color: #4A9EFF;
        font-size: 1.2rem;
        display: inline-block;
    }}
    .site-icon a:hover {{
        color: #6BB6FF;
        transform: scale(1.2);
    }}
    
    /* Fundo da página - Azul Sebrae */
    .stApp {{
        background-color: {SEBRAE_AZUL_CLARO} !important;
        background: linear-gradient(135deg, {SEBRAE_AZUL} 0%, {SEBRAE_AZUL_CLARO} 100%) !important;
    }}
    
    /* Ajusta cores de texto para contraste no fundo azul */
    .stApp h1, .stApp h2, .stApp h3 {{
        color: white !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }}
    
    /* Ajusta métricas para contraste */
    [data-testid="stMetricValue"] {{
        color: white !important;
    }}
    
    [data-testid="stMetricLabel"] {{
        color: rgba(255, 255, 255, 0.9) !important;
    }}
    
    /* Ajusta textos gerais */
    .stMarkdown, .stMarkdown p {{
        color: rgba(255, 255, 255, 0.95) !important;
    }}
    
    /* Ajusta elementos de informação */
    .stInfo, .stSuccess, .stWarning, .stError {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Tabela - fundo branco */
    /* Estilos gerais de tabela - mas não para data-table */
    table:not(#data-table):not(#data-table-2) {{
        background-color: white !important;
    }}
    
    thead:not(#data-table thead):not(#data-table-2 thead) {{
        background-color: white !important;
    }}
    
    tbody:not(#data-table tbody):not(#data-table-2 tbody) {{
        background-color: white !important;
    }}
    
    tbody:not(#data-table tbody):not(#data-table-2 tbody) tr:nth-child(even) {{
        background-color: #f8f9fa !important;
    }}
    
    /* Tabela de dados - cabeçalho azul escuro com texto branco */
    #data-table thead th,
    #data-table-2 thead th,
    table[id*="data-table"] thead th {{
        background-color: #003366 !important;
        color: white !important;
        font-weight: 600 !important;
    }}
    
    /* Tabela de dados - corpo branco com texto escuro */
    #data-table tbody td,
    #data-table-2 tbody td,
    table[id*="data-table"] tbody td {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Remove zebrado da tabela de dados */
    #data-table tbody tr:nth-child(even) td,
    #data-table-2 tbody tr:nth-child(even) td {{
        background-color: white !important;
    }}
    
    /* Estilos para st.dataframe do Streamlit - seletores mais abrangentes */
    div[data-testid="stDataFrame"] table thead th,
    div[data-testid="stDataFrame"] table thead tr th,
    div[data-testid="stDataFrame"] thead th,
    div[data-testid="stDataFrame"] thead tr th,
    div[data-testid="stDataFrame"] table > thead > tr > th,
    div[data-testid="stDataFrame"] table thead th div,
    div[data-testid="stDataFrame"] table thead th span,
    div[data-testid="stDataFrame"] table thead th p,
    div[data-testid="stDataFrame"] thead th[role="columnheader"],
    div[data-testid="stDataFrame"] table thead th[role="columnheader"],
    div[data-testid="stDataFrame"] table thead tr:first-child th,
    div[data-testid="stDataFrame"] table thead tr:first-child td {{
        background-color: #003366 !important;
        background: #003366 !important;
        color: white !important;
        font-weight: 600 !important;
    }}
    
    /* Força o thead inteiro */
    div[data-testid="stDataFrame"] table thead,
    div[data-testid="stDataFrame"] table thead tr:first-child {{
        background-color: #003366 !important;
        background: #003366 !important;
    }}
    
    div[data-testid="stDataFrame"] table tbody td,
    div[data-testid="stDataFrame"] table tbody tr td,
    div[data-testid="stDataFrame"] tbody td,
    div[data-testid="stDataFrame"] tbody tr td,
    div[data-testid="stDataFrame"] table > tbody > tr > td {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    div[data-testid="stDataFrame"] table tbody tr:nth-child(even) td,
    div[data-testid="stDataFrame"] table tbody tr:nth-child(even) td div {{
        background-color: white !important;
    }}
    
    div[data-testid="stDataFrame"] table,
    div[data-testid="stDataFrame"] table > thead,
    div[data-testid="stDataFrame"] table > tbody,
    div[data-testid="stDataFrame"] > div {{
        background-color: white !important;
    }}
    
    /* Força estilos em todos os elementos dentro do dataframe */
    div[data-testid="stDataFrame"] {{
        background-color: white !important;
    }}
    
    tbody:not(#data-table tbody):not(#data-table-2 tbody) tr:hover {{
        background-color: #e9ecef !important;
    }}
    
    /* Hover na tabela de dados - mantém branco */
    #data-table tbody tr:hover td,
    #data-table-2 tbody tr:hover td {{
        background-color: #f8f9fa !important;
    }}
    
    th, td {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Dropdown boxes - fundo branco sem bordas brancas */
    div[data-baseweb="select"] {{
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    div[data-baseweb="select"] > div {{
        background-color: white !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        border-radius: 4px !important;
    }}
    
    div[data-baseweb="select"] input {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
        border: none !important;
    }}
    
    div[data-baseweb="select"] > div > div {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
        border: none !important;
    }}
    
    /* Multiselect - fundo branco sem bordas brancas */
    div[data-baseweb="select"][aria-multiselectable="true"] {{
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    div[data-baseweb="select"][aria-multiselectable="true"] > div {{
        background-color: white !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        border-radius: 4px !important;
    }}
    
    div[data-baseweb="select"][aria-multiselectable="true"] input {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
        border: none !important;
    }}
    
    /* Tags selecionadas no multiselect - Azul claro/transparente baseado em #003366 */
    div[data-baseweb="tag"] {{
        background-color: rgba(0, 51, 102, 0.2) !important; /* Azul #003366 com 20% de opacidade */
        color: {SEBRAE_CINZA_ESCURO} !important;
        border: 1px solid rgba(0, 51, 102, 0.4) !important;
    }}
    
    /* Texto dentro das tags - preto/cinza escuro para legibilidade */
    div[data-baseweb="select"] div[data-baseweb="tag"],
    div[data-baseweb="select"] div[data-baseweb="tag"] *,
    div[data-baseweb="select"] div[data-baseweb="tag"] span,
    div[data-baseweb="select"] div[data-baseweb="tag"] div,
    div[data-baseweb="select"] div[data-baseweb="tag"] p,
    div[data-baseweb="select"] div[data-baseweb="tag"] label {{
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Botão de remover - mantém visível */
    div[data-baseweb="tag"] button {{
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    div[data-baseweb="tag"] button svg,
    div[data-baseweb="tag"] button svg *,
    div[data-baseweb="tag"] svg path {{
        fill: {SEBRAE_CINZA_ESCURO} !important;
        stroke: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Tags no multiselect - garante que todas sejam azul claro/transparente */
    div[data-baseweb="select"] div[data-baseweb="tag"] {{
        background-color: rgba(0, 51, 102, 0.2) !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
        border: 1px solid rgba(0, 51, 102, 0.4) !important;
    }}
    
    /* Remove qualquer cor vermelha das tags e força azul claro */
    span[data-baseweb="tag"],
    div[data-baseweb="tag"] span,
    div[data-baseweb="select"] span[data-baseweb="tag"],
    div[role="listbox"] div[data-baseweb="tag"] {{
        background-color: rgba(0, 51, 102, 0.2) !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Override qualquer estilo inline vermelho ou outras cores - força azul claro */
    [style*="background-color: rgb(239, 68, 68)"],
    [style*="background-color:#ef4444"],
    [style*="background-color: #ef4444"],
    [style*="background-color:rgb(239, 68, 68)"],
    [style*="background-color: rgb(0, 82, 165)"],
    [style*="background-color:#0052A5"],
    [style*="background-color: #0052A5"],
    [style*="background-color: rgb(0, 51, 102)"],
    [style*="background-color:#003366"],
    [style*="background-color: #003366"] {{
        background-color: rgba(0, 51, 102, 0.2) !important;
    }}
    
    /* Tags dentro do multiselect - força azul claro */
    div[data-baseweb="select"][aria-multiselectable="true"] div[data-baseweb="tag"],
    div[data-baseweb="select"][aria-multiselectable="true"] span[data-baseweb="tag"] {{
        background-color: rgba(0, 51, 102, 0.2) !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Ícone X dentro das tags - preto para visibilidade */
    div[data-baseweb="tag"] svg,
    div[data-baseweb="tag"] svg *,
    div[data-baseweb="tag"] path,
    div[data-baseweb="tag"] button svg,
    div[data-baseweb="tag"] button svg * {{
        fill: {SEBRAE_CINZA_ESCURO} !important;
        stroke: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Botão de remover dentro das tags - preto */
    div[data-baseweb="tag"] button {{
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    div[data-baseweb="tag"] button * {{
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Placeholder e texto dos selects - mas não dentro das tags */
    div[data-baseweb="select"] span:not(div[data-baseweb="tag"] span) {{
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    /* Força branco em TODOS os elementos de texto dentro das tags - máxima especificidade */
    div[data-baseweb="select"] div[data-baseweb="tag"] span[data-baseweb="tag-text"],
    div[data-baseweb="select"] div[data-baseweb="tag"] > span:first-child,
    div[data-baseweb="select"] div[data-baseweb="tag"] > div:first-child,
    div[data-baseweb="select"] div[data-baseweb="tag"] > label,
    div[data-baseweb="select"] div[data-baseweb="tag"] > span,
    div[data-baseweb="select"] div[data-baseweb="tag"] > div {{
        color: white !important;
    }}
    
    /* Override absoluto - força branco em qualquer texto dentro de tag */
    div[data-baseweb="tag"] {{
        color: white !important;
    }}
    
    div[data-baseweb="tag"]::before,
    div[data-baseweb="tag"]::after {{
        color: white !important;
    }}
    
    /* Dropdown aberto */
    ul[role="listbox"] {{
        background-color: white !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
    }}
    
    li[role="option"] {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    li[role="option"]:hover {{
        background-color: #f8f9fa !important;
    }}
    
    /* Remove espaços e bordas extras ao redor dos selects */
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stMultiSelect"] > div {{
        background-color: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
    }}
    
    /* Remove bordas brancas dos containers */
    .stSelectbox > div,
    .stMultiSelect > div {{
        background-color: transparent !important;
        border: none !important;
    }}
    
    /* Campo de pesquisa - fundo branco */
    div[data-testid="stTextInput"] input {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    div[data-testid="stTextInput"] input::placeholder {{
        color: #999 !important;
    }}
    
    /* Tabela de dados - cabeçalho azul escuro e corpo branco */
    #data-table thead th,
    #data-table-2 thead th,
    table[id*="data-table"] thead th {{
        background-color: #003366 !important;
        color: white !important;
        font-weight: 600 !important;
    }}
    
    #data-table tbody td,
    #data-table-2 tbody td,
    table[id*="data-table"] tbody td {{
        background-color: white !important;
        color: {SEBRAE_CINZA_ESCURO} !important;
    }}
    
    #data-table,
    #data-table-2,
    table[id*="data-table"] {{
        background-color: white !important;
    }}
</style>
<script>
    // Aplica transparência aos cards inativos
    function applyCardInactiveStyles() {{
        // Busca todos os containers com data-category
        const containers = document.querySelectorAll('div[data-category]');
        containers.forEach(container => {{
            const isInactive = container.classList.contains('card-inactive');
            const category = container.getAttribute('data-category');
            
            // Busca o botão dentro do container ou no próximo elemento irmão
            let button = container.querySelector('button[kind="secondary"]');
            
            // Se não encontrou dentro, busca no próximo elemento irmão (Streamlit pode renderizar assim)
            if (!button) {{
                const nextSibling = container.nextElementSibling;
                if (nextSibling) {{
                    button = nextSibling.querySelector('button[kind="secondary"]');
                }}
            }}
            
            // Se ainda não encontrou, busca em todos os botões e verifica pela key
            if (!button) {{
                const allButtons = document.querySelectorAll('button[kind="secondary"]');
                allButtons.forEach(btn => {{
                    // Verifica se o botão está relacionado a esta categoria pela estrutura
                    const parent = btn.closest('div[data-testid="column"]');
                    if (parent && container.parentElement === parent.parentElement) {{
                        button = btn;
                    }}
                }});
            }}
            
            if (button && isInactive) {{
                button.style.setProperty('opacity', '0.4', 'important');
                button.style.setProperty('background', 'rgba(255, 255, 255, 0.5)', 'important');
                button.style.setProperty('color', 'rgba(51, 51, 51, 0.5)', 'important');
            }} else if (button && !isInactive) {{
                // Remove estilos de inativo se estiver ativo
                button.style.removeProperty('opacity');
                button.style.removeProperty('background');
                button.style.removeProperty('color');
            }}
        }});
        
        // Busca todos os botões e verifica pelo texto e pela lista de categorias inativas
        const inactiveCategories = new Set();
        containers.forEach(container => {{
            if (container.classList.contains('card-inactive')) {{
                const category = container.getAttribute('data-category');
                if (category) inactiveCategories.add(category);
            }}
        }});
        
        // Aplica estilos baseado no texto do botão e nas categorias inativas
        const allButtons = document.querySelectorAll('div[data-testid="column"] button[kind="secondary"]');
        allButtons.forEach(button => {{
            const buttonText = (button.textContent || button.innerText || '').trim();
            let shouldBeInactive = false;
            
            // Mapeia texto do botão para categoria
            if ((buttonText.includes('Startups') || buttonText.includes('Startup')) && inactiveCategories.has('Startup')) {{
                shouldBeInactive = true;
            }} else if ((buttonText.includes('Empresa Âncora') || buttonText.includes('Grandes Empresas')) && inactiveCategories.has('Empresa Âncora')) {{
                shouldBeInactive = true;
            }} else if ((buttonText.includes('Fundos e Investidores') || buttonText.includes('Fundos')) && inactiveCategories.has('Fundos e Investidores')) {{
                shouldBeInactive = true;
            }} else if ((buttonText.includes('Universidades') || buttonText.includes('ICTs')) && inactiveCategories.has('Universidades e ICTs')) {{
                shouldBeInactive = true;
            }} else if ((buttonText.includes('Órgãos Públicos') || buttonText.includes('Órgãos')) && inactiveCategories.has('Órgãos Públicos e Apoio')) {{
                shouldBeInactive = true;
            }} else if ((buttonText.includes('Hubs') || buttonText.includes('Incubadoras')) && inactiveCategories.has('Hubs, Incubadoras e Parques Tecnológicos')) {{
                shouldBeInactive = true;
            }}
            
            // Verifica também pelo atributo data-category-inactive
            const hasInactiveAttr = button.getAttribute('data-category-inactive') === 'true';
            if (hasInactiveAttr) shouldBeInactive = true;
            
            if (shouldBeInactive) {{
                button.style.setProperty('opacity', '0.4', 'important');
                button.style.setProperty('background', 'rgba(255, 255, 255, 0.5)', 'important');
                button.style.setProperty('color', 'rgba(51, 51, 51, 0.5)', 'important');
            }} else if (!hasInactiveAttr) {{
                // Remove estilos se não estiver inativo
                button.style.removeProperty('opacity');
                button.style.removeProperty('background');
                button.style.removeProperty('color');
            }}
        }});
    }}
    
    // Força fundo azul claro e texto preto nas tags do multiselect
    function styleTags() {{
        const tags = document.querySelectorAll('div[data-baseweb="tag"]');
        tags.forEach(tag => {{
            // Força fundo azul claro/transparente
            tag.style.setProperty('background-color', 'rgba(0, 51, 102, 0.2)', 'important');
            tag.style.backgroundColor = 'rgba(0, 51, 102, 0.2)';
            
            // Força texto preto/cinza escuro
            tag.style.setProperty('color', '#333333', 'important');
            tag.style.color = '#333333';
            
            // Força cor preta em todos os elementos filhos
            const allElements = tag.querySelectorAll('*');
            allElements.forEach(el => {{
                el.style.setProperty('color', '#333333', 'important');
                el.style.color = '#333333';
            }});
            
            // Força cor preta em spans e divs específicos
            const spans = tag.querySelectorAll('span');
            spans.forEach(span => {{
                span.style.setProperty('color', '#333333', 'important');
                span.style.color = '#333333';
            }});
            
            const divs = tag.querySelectorAll('div');
            divs.forEach(div => {{
                div.style.setProperty('color', '#333333', 'important');
                div.style.color = '#333333';
            }});
            
            // Ícones SVG em preto
            const svgs = tag.querySelectorAll('svg, svg *');
            svgs.forEach(svg => {{
                svg.style.setProperty('fill', '#333333', 'important');
                svg.style.setProperty('stroke', '#333333', 'important');
            }});
        }});
    }}
    
    // Executa imediatamente
    applyCardInactiveStyles();
    styleTags();
    
    // Executa quando a página carrega
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', function() {{
            applyCardInactiveStyles();
            styleTags();
        }});
    }} else {{
        applyCardInactiveStyles();
        styleTags();
    }}
    
    // Executa após mudanças no DOM
    const observer = new MutationObserver(function(mutations) {{
        mutations.forEach(function(mutation) {{
            if (mutation.addedNodes.length) {{
                applyCardInactiveStyles();
                styleTags();
            }}
        }});
        applyCardInactiveStyles();
        styleTags();
    }});
    observer.observe(document.body, {{ childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] }});
    
    // Executa periodicamente
    setInterval(function() {{
        applyCardInactiveStyles();
        styleTags();
    }}, 500);
    
    window.addEventListener('load', function() {{
        applyCardInactiveStyles();
        styleTags();
    }});
    document.addEventListener('DOMContentLoaded', function() {{
        applyCardInactiveStyles();
        styleTags();
        styleDataTable();
    }});
    
    // Função para estilizar tabelas de dados
    function styleDataTable() {{
        // Estiliza st.dataframe do Streamlit - busca todas as tabelas
        const allTables = document.querySelectorAll('table');
        allTables.forEach(table => {{
            // Verifica se é uma tabela de dados (não é a tabela de categorias)
            const isDataTable = table.closest('div[data-testid="stDataFrame"]') || 
                               table.id === 'data-table' || 
                               table.id === 'data-table-2' ||
                               (table.querySelector('thead') && table.querySelector('tbody') && 
                                !table.closest('.category-legend-item'));
            
            if (!isDataTable) return;
            
            // Remove todos os estilos inline que possam estar interferindo
            table.style.removeProperty('background-color');
            table.style.removeProperty('background');
            
            // Cabeçalho - azul escuro com texto branco
            // Busca todos os possíveis elementos de cabeçalho
            const headers = table.querySelectorAll('thead th, thead tr th, thead > tr > th, thead > tr > td, thead th[role="columnheader"]');
            headers.forEach(th => {{
                // Remove TODOS os estilos inline relacionados a background e color
                // Primeiro, limpa o atributo style completamente e reconstrói
                let currentStyle = th.getAttribute('style') || '';
                // Remove propriedades de background e color do style atual
                currentStyle = currentStyle
                    .replace(/background[^;]*;?/gi, '')
                    .replace(/background-color[^;]*;?/gi, '')
                    .replace(/background-image[^;]*;?/gi, '')
                    .replace(/color[^;]*;?/gi, '');
                
                // Reconstrói o style apenas com as propriedades que queremos manter (exceto background e color)
                const newStyle = currentStyle.trim() + '; background-color: #003366 !important; color: white !important; font-weight: 600 !important;';
                th.setAttribute('style', newStyle);
                
                // Também aplica via setProperty para garantir
                th.style.setProperty('background-color', '#003366', 'important');
                th.style.setProperty('color', 'white', 'important');
                th.style.setProperty('font-weight', '600', 'important');
                
                // Força também nos elementos filhos
                const children = th.querySelectorAll('*');
                children.forEach(child => {{
                    if (child.tagName !== 'SVG' && child.tagName !== 'PATH') {{
                        child.style.setProperty('color', 'white', 'important');
                        let childStyle = child.getAttribute('style') || '';
                        childStyle = childStyle.replace(/color[^;]*;?/gi, '');
                        child.setAttribute('style', childStyle.trim() + '; color: white !important;');
                    }}
                }});
                // Força também em divs e spans dentro do th
                const divs = th.querySelectorAll('div, span, p');
                divs.forEach(el => {{
                    el.style.setProperty('color', 'white', 'important');
                    let elStyle = el.getAttribute('style') || '';
                    elStyle = elStyle.replace(/color[^;]*;?/gi, '');
                    el.setAttribute('style', elStyle.trim() + '; color: white !important;');
                }});
            }});
            
            // Força fundo azul no thead e na primeira linha
            const thead = table.querySelector('thead');
            if (thead) {{
                let theadStyle = thead.getAttribute('style') || '';
                theadStyle = theadStyle.replace(/background[^;]*;?/gi, '').replace(/background-color[^;]*;?/gi, '');
                thead.setAttribute('style', theadStyle.trim() + '; background-color: #003366 !important;');
                thead.style.setProperty('background-color', '#003366', 'important');
            }}
            
            // Força fundo azul na primeira linha do thead
            const firstRow = table.querySelector('thead tr:first-child');
            if (firstRow) {{
                let rowStyle = firstRow.getAttribute('style') || '';
                rowStyle = rowStyle.replace(/background[^;]*;?/gi, '').replace(/background-color[^;]*;?/gi, '');
                firstRow.setAttribute('style', rowStyle.trim() + '; background-color: #003366 !important;');
                firstRow.style.setProperty('background-color', '#003366', 'important');
            }}
            
            // Corpo - fundo branco com texto escuro
            const cells = table.querySelectorAll('tbody td, tbody tr td, tbody > tr > td');
            cells.forEach(td => {{
                // Verifica se a célula tem cor especial (categoria/região) - se tiver, mantém
                const inlineStyle = td.getAttribute('style') || '';
                const computedStyle = window.getComputedStyle(td);
                const bgColor = computedStyle.backgroundColor;
                
                // Verifica se tem cor especial (não branco, não transparente)
                const hasSpecialBg = bgColor && 
                                    bgColor !== 'rgba(0, 0, 0, 0)' && 
                                    bgColor !== 'transparent' &&
                                    bgColor !== 'rgb(255, 255, 255)' &&
                                    bgColor !== 'rgba(255, 255, 255, 1)' &&
                                    !bgColor.includes('rgba(0, 0, 0, 0)') &&
                                    (inlineStyle.includes('background-color') && 
                                     !inlineStyle.includes('background-color: white') &&
                                     !inlineStyle.includes('background-color:white'));
                
                // Se não tem cor especial, remove estilos inline e aplica branco
                if (!hasSpecialBg) {{
                    td.style.removeProperty('background');
                    td.style.removeProperty('background-color');
                    td.style.setProperty('background-color', 'white', 'important');
                }}
                
                // Força texto escuro
                td.style.removeProperty('color');
                td.style.setProperty('color', '#333333', 'important');
                
                // Força texto escuro nos elementos filhos (exceto links)
                const children = td.querySelectorAll('span, div, p');
                children.forEach(child => {{
                    if (!child.closest('a')) {{
                        child.style.setProperty('color', '#333333', 'important');
                    }}
                }});
            }});
            
            // Remove zebrado - força branco nas linhas pares
            const evenRows = table.querySelectorAll('tbody tr:nth-child(even) td');
            evenRows.forEach(td => {{
                const inlineStyle = td.getAttribute('style') || '';
                const computedStyle = window.getComputedStyle(td);
                const bgColor = computedStyle.backgroundColor;
                
                const hasSpecialBg = bgColor && 
                                    bgColor !== 'rgba(0, 0, 0, 0)' && 
                                    bgColor !== 'transparent' &&
                                    bgColor !== 'rgb(255, 255, 255)' &&
                                    bgColor !== 'rgba(255, 255, 255, 1)' &&
                                    !bgColor.includes('rgba(0, 0, 0, 0)') &&
                                    (inlineStyle.includes('background-color') && 
                                     !inlineStyle.includes('background-color: white') &&
                                     !inlineStyle.includes('background-color:white'));
                
                if (!hasSpecialBg) {{
                    td.style.removeProperty('background');
                    td.style.removeProperty('background-color');
                    td.style.setProperty('background-color', 'white', 'important');
                }}
            }});
            
            // Força fundo branco na tabela e tbody
            table.style.setProperty('background-color', 'white', 'important');
            const tbody = table.querySelector('tbody');
            if (tbody) {{
                tbody.style.setProperty('background-color', 'white', 'important');
            }}
            
            // Força fundo branco no container do dataframe
            const dfContainer = table.closest('div[data-testid="stDataFrame"]');
            if (dfContainer) {{
                dfContainer.style.setProperty('background-color', 'white', 'important');
            }}
        }});
    }}
    
    // Executa periodicamente para garantir que os estilos sejam aplicados (mais frequente)
    setInterval(styleDataTable, 200);
    
    // Executa imediatamente várias vezes para garantir aplicação
    setTimeout(styleDataTable, 100);
    setTimeout(styleDataTable, 300);
    setTimeout(styleDataTable, 500);
    setTimeout(styleDataTable, 1000);
    
    // Observa mudanças no DOM com configuração mais agressiva
    const tableObserver = new MutationObserver(function(mutations) {{
        styleDataTable();
    }});
    tableObserver.observe(document.body, {{ 
        childList: true, 
        subtree: true, 
        attributes: true,
        attributeFilter: ['style', 'class']
    }});
</script>
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
        
        # CORREÇÃO: Verifica se os nomes das colunas estão concatenados com dados
        # Se a primeira coluna tem um nome muito longo (mais de 50 caracteres), provavelmente está concatenado
        primeira_col = df.columns[0] if len(df.columns) > 0 else None
        if primeira_col and len(str(primeira_col)) > 50:
            # Os nomes das colunas estão concatenados com dados
            # Para "Base | Atores MG", define os nomes das colunas manualmente
            if sheet_name == "Base | Atores MG":
                # Conta quantas colunas temos
                num_cols = len(df.columns)
                # Define nomes padrão baseado no número de colunas conhecidas
                expected_cols = ['Nome do Ator', 'Categoria', 'Cidade', 'Regiao Sebrae', 'Site', 
                               'Descrição Resumida', 'Setor', 'Tags', 'Ano de Fundação', 
                               'Tamanho da Equipe', 'Marco Legal', 'Relação com Beta-i']
                # Se temos mais colunas, adiciona "Coluna X" para as extras
                while len(expected_cols) < num_cols:
                    expected_cols.append(f'Coluna {len(expected_cols) + 1}')
                # Pega apenas as colunas necessárias
                expected_cols = expected_cols[:num_cols]
                # Renomeia as colunas
                df.columns = expected_cols
                # Remove as primeiras linhas que são dados concatenados
                # Procura pela primeira linha que tem dados válidos (primeira coluna com menos de 50 caracteres)
                if len(df) > 0:
                    mask = df.iloc[:, 0].astype(str).str.len() < 50
                    if mask.any():
                        # Encontra o primeiro índice True na máscara
                        try:
                            # Tenta usar idxmax (retorna o índice do primeiro True)
                            first_valid_idx = mask.idxmax()
                        except:
                            # Se idxmax não funcionar, usa argmax ou busca manual
                            try:
                                first_valid_idx = mask.argmax()
                            except:
                                # Busca manual pelo primeiro True
                                first_valid_idx = 0
                                for i, val in enumerate(mask):
                                    if val:
                                        first_valid_idx = i
                                        break
                        # Se encontrou uma linha válida, remove tudo antes dela
                        if first_valid_idx > 0:
                            df = df.iloc[first_valid_idx:].reset_index(drop=True)
        
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
                # Remove linhas onde a primeira coluna tem mais de 100 caracteres (provavelmente dados concatenados)
                df = df[df[primeira_col].astype(str).str.len() < 100]
        
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
            
            # Cores Sebrae para o gráfico
            colors_sebrae = [SEBRAE_AZUL, SEBRAE_AZUL_CLARO, SEBRAE_VERDE, SEBRAE_LARANJA, SEBRAE_AMARELO]
            fig = px.bar(
                x=sector_counts.values,
                y=sector_counts.index,
                orientation='h',
                title="Top 10 Setores",
                color=sector_counts.values,
                color_continuous_scale=[[0, SEBRAE_AZUL_CLARO], [1, SEBRAE_AZUL]]
            )
            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color=SEBRAE_CINZA_ESCURO)
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Distribuição por setores (remove NaN)
            sector_counts_all = df['sector'].dropna().value_counts()
            
            fig = px.pie(
                values=sector_counts_all.values,
                names=sector_counts_all.index,
                title="Distribuição por Setores",
                color_discrete_sequence=SEBRAE_COLOR_PALETTE
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color=SEBRAE_CINZA_ESCURO)
            )
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
                markers=True,
                color_discrete_sequence=[SEBRAE_AZUL]
            )
            fig.update_layout(
                xaxis_title="Ano", 
                yaxis_title="Número de Startups",
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color=SEBRAE_CINZA_ESCURO)
            )
            fig.update_traces(line=dict(width=3), marker=dict(size=8, color=SEBRAE_AZUL))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Acumulado por ano
            yearly_counts_sorted = yearly_counts.sort_index()
            cumulative = yearly_counts_sorted.cumsum()
            
            fig = px.line(
                x=cumulative.index,
                y=cumulative.values,
                title="Acumulado de Startups por Ano",
                markers=True,
                color_discrete_sequence=[SEBRAE_VERDE]
            )
            fig.update_layout(
                xaxis_title="Ano", 
                yaxis_title="Total Acumulado",
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color=SEBRAE_CINZA_ESCURO)
            )
            fig.update_traces(line=dict(width=3), marker=dict(size=8, color=SEBRAE_VERDE))
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
            mapbox_style="carto-positron",  # Estilo claro - fundo será customizado via plot_bgcolor
            mapbox=dict(
                center=MAP_CENTER,
                zoom=MAP_ZOOM,
                layers=[]
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
            paper_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
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
                <span style="color:{SEBRAE_CINZA_ESCURO}; font-size:0.95rem;">{regiao}</span>
            </div>
            """
        )
    st.markdown("".join(legend_items), unsafe_allow_html=True)


def render_category_legend(categorias_data, title=""):
    """
    Renderiza legenda personalizada para as categorias similar à legenda de regiões do mapa.
    categorias_data: dict com {category_name: {"color": cor, "total": valor, "display_name": nome_exibicao}}
    """
    if not categorias_data:
        return
    
    # Mapeamento de nomes de exibição para nomes de categoria
    card_to_category = {
        "Startups": "Startup",
        "Grandes Empresas Âncoras": "Empresa Âncora",
        "Fundos e Investidores": "Fundos e Investidores",
        "Universidades e ICTs": "Universidades e ICTs",
        "Hubs, Incubadoras e Parques Tecnológicos": "Hubs, Incubadoras e Parques Tecnológicos",
        "Órgãos Públicos e Apoio": "Órgãos Públicos e Apoio"
    }
    
    # Cria a tabela usando Streamlit columns para cada linha
    for display_name, category_name in card_to_category.items():
        if category_name not in categorias_data:
            continue
        
        data = categorias_data[category_name]
        total = data.get("total", 0)
        is_active = st.session_state.categorias_ativas.get(category_name, True)
        
        # Opacidade baseada no estado ativo/inativo
        opacity = 0.4 if not is_active else 1.0
        # Texto branco
        text_color = f"rgba(255, 255, 255, {opacity})"
        
        checkbox_key = f"legend_check_{category_name}"
        
        # Cria uma linha da tabela usando columns
        col_check, col_name, col_total = st.columns([0.08, 0.72, 0.2])
        
        with col_check:
            # Checkbox centralizado verticalmente
            checkbox_value = st.checkbox(
                "",
                value=is_active,
                key=checkbox_key,
                label_visibility="collapsed"
            )
            
            if checkbox_value != is_active:
                # Estado mudou, atualiza
                st.session_state.categorias_ativas[category_name] = checkbox_value
                categorias_disponiveis = list(card_to_category.values())
                categorias_ativas_list = [cat for cat, ativa in st.session_state.categorias_ativas.items() 
                                          if ativa and cat in categorias_disponiveis]
                st.session_state.filtro_categoria = categorias_ativas_list
                st.rerun()
        
        with col_name:
            # Nome da categoria
            st.markdown(
                f'<div style="color:{text_color}; font-size:0.95rem; opacity:{opacity}; line-height: 1.5;">{display_name}</div>',
                unsafe_allow_html=True
            )
        
        with col_total:
            # Total alinhado à direita
            st.markdown(
                f'<div style="color:{text_color}; font-size:0.95rem; font-weight:600; opacity:{opacity}; text-align: right; line-height: 1.5;">{total:,}</div>',
                unsafe_allow_html=True
            )
        
    
    # CSS para melhorar o alinhamento vertical e reduzir espaçamento
    st.markdown(
        """
        <style>
        /* Ajusta checkboxes para alinhar com o texto */
        div[data-testid*="stCheckbox"] {
            margin: 0 !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            height: auto !important;
        }
        
        /* Remove espaçamento extra das colunas */
        div[data-testid="column"] {
            padding: 0 4px !important;
        }
        
        /* Ajusta espaçamento vertical das linhas */
        div[data-testid="column"] > div {
            margin: 0 !important;
            padding: 4px 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


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
    coluna_qtd_hubs_incubadoras_parquestecnologicos = "qtd_hubs_incubadoras_parquestecnologicos"
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
    if coluna_qtd_hubs_incubadoras_parquestecnologicos in df.columns:
        colunas_necessarias.append(coluna_qtd_hubs_incubadoras_parquestecnologicos)
    
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
    if coluna_qtd_hubs_incubadoras_parquestecnologicos in df_map.columns:
        df_map[coluna_qtd_hubs_incubadoras_parquestecnologicos] = pd.to_numeric(df_map[coluna_qtd_hubs_incubadoras_parquestecnologicos], errors='coerce').fillna(0).astype(int)

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
    base_colors = {}
    
    # Cores especiais para regiões específicas
    TRIANGULO_COLOR = "#003366"  # Azul escuro para Triângulo e Alto Paranaíba
    RIO_DOCE_COLOR = "#8B0000"  # Vermelho escuro para Rio Doce e Vale do Aço
    
    for i, regiao in enumerate(regioes_todas):
        regiao_lower = str(regiao).lower().strip()
        
        # Verifica se é Triângulo e Alto Paranaíba
        if 'triângulo' in regiao_lower or 'triangulo' in regiao_lower or 'paranaíba' in regiao_lower or 'paranaiba' in regiao_lower:
            base_colors[regiao] = TRIANGULO_COLOR
        # Verifica se é Rio Doce e Vale do Aço
        elif 'rio doce' in regiao_lower or 'vale do aço' in regiao_lower or 'vale do aco' in regiao_lower:
            base_colors[regiao] = RIO_DOCE_COLOR
        else:
            base_colors[regiao] = REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)]

    # Inicializa variáveis de filtro
    categorias_selecionadas = []
    categorias_disponiveis = []
    
    # IMPORTANTE: Processa seleção do mapa ANTES de criar os widgets
    # Esta seleção foi armazenada na renderização anterior quando o usuário clicou
    # Verifica se há uma seleção pendente do mapa e se é diferente da última processada
    # Esta seleção foi armazenada na renderização anterior quando o usuário clicou no mapa
    if "mapa_selecao_pendente" in st.session_state and st.session_state.mapa_selecao_pendente:
        selecao = st.session_state.mapa_selecao_pendente
        
        # Cria um hash da seleção para comparar com a última processada
        selecao_hash = None
        if selecao and 'points' in selecao and len(selecao['points']) > 0:
            point = selecao['points'][0]
            if 'customdata' in point and len(point['customdata']) >= 2:
                selecao_hash = str(point['customdata'][0]) + "|" + str(point['customdata'][1])
        
        # Verifica se é uma seleção nova (diferente da última processada)
        ultima_selecao_hash = st.session_state.get("ultima_selecao_processada", None)
        
        if selecao_hash and selecao_hash != ultima_selecao_hash:
            if selecao and 'points' in selecao and len(selecao['points']) > 0:
                point = selecao['points'][0]
                if 'customdata' in point and len(point['customdata']) >= 2:
                    regiao_clicada = point['customdata'][0]
                    municipio_clicado = point['customdata'][1]
                    
                    # Ao clicar no mapa, sempre filtra diretamente pelo município
                    # Também atualiza a região para garantir que o dropdown de município mostre os municípios corretos
                    st.session_state.filtro_regiao = regiao_clicada
                    st.session_state.filtro_municipio = municipio_clicado
                    
                    # Marca esta seleção como processada
                    st.session_state.ultima_selecao_processada = selecao_hash
                    # Limpa a seleção pendente para evitar reprocessamento
                    st.session_state.mapa_selecao_pendente = None
                    # O on_select="rerun" já fez rerun na renderização anterior quando o usuário clicou
                    # Esta renderização já está aplicando os filtros atualizados, então não precisa fazer rerun novamente
    
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
            if coluna_qtd_hubs_incubadoras_parquestecnologicos in df.columns:
                categorias_base.append("Hubs, Incubadoras e Parques Tecnológicos")
            categorias_disponiveis = categorias_base
        
        # Inicializa estado das categorias ativas (todas ativas por padrão)
        if "categorias_ativas" not in st.session_state:
            st.session_state.categorias_ativas = {
                "Startup": True,
                "Empresa Âncora": True,
                "Fundos e Investidores": True,
                "Universidades e ICTs": True,
                "Órgãos Públicos e Apoio": True,
                "Hubs, Incubadoras e Parques Tecnológicos": True  # Agora tem dados
            }
        
        # Mapeia nomes dos cards para nomes das categorias no filtro
        card_to_category = {
            "Startups": "Startup",
            "Grandes Empresas Âncoras": "Empresa Âncora",
            "Fundos e Investidores": "Fundos e Investidores",
            "Universidades e ICTs": "Universidades e ICTs",
            "Órgãos Públicos e Apoio": "Órgãos Públicos e Apoio",
            "Hubs, Incubadoras e Parques Tecnológicos": "Hubs, Incubadoras e Parques Tecnológicos"
        }
        
        # Cabeçalho com logo Sebrae + Beta-i
        # Exibe logo Sebrae + Beta-i reduzido em 30% e próximo ao mapa
        st.markdown("""
        <style>
            .logo-container {
                margin-top: -80px !important;
                margin-bottom: -20px !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }
            .logo-container img {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }
            div[data-testid="stImage"] {
                margin-top: -80px !important;
                margin-bottom: -20px !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }
            /* Ajusta espaçamento mínimo entre filtros */
            div[data-testid="stSelectbox"],
            div[data-testid="stMultiSelect"] {
                margin-top: 0 !important;
                margin-bottom: 0 !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }
            /* Espaçamento mínimo entre filtros adjacentes */
            div[data-testid="stSelectbox"] + div[data-testid="stSelectbox"],
            div[data-testid="stSelectbox"] + div[data-testid="stMultiSelect"],
            div[data-testid="stMultiSelect"] + div[data-testid="stSelectbox"],
            div[data-testid="stMultiSelect"] + div[data-testid="stMultiSelect"] {
                margin-top: 0.2rem !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        col_img, col_empty = st.columns([0.7, 0.3])
        with col_img:
            st.markdown('<div class="logo-container">', unsafe_allow_html=True)
            st.image("Sebrae + Beta-i.png", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_empty:
            st.empty()
        
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
        
        # Inicializa com "Todos" se não estiver definido
        if "filtro_municipio" not in st.session_state:
            st.session_state.filtro_municipio = "Todos"
        
        # Garante que o valor no session_state seja válido
        opcoes_municipio = ["Todos"] + municipios_disponiveis
        if st.session_state.filtro_municipio not in opcoes_municipio:
            st.session_state.filtro_municipio = "Todos"
        
        municipio_selecionado = st.selectbox(
            "Município",
            options=opcoes_municipio,
            key="filtro_municipio"
        )
        
        # Filtro de Segmentos (Startups) - apenas se Startup estiver selecionada
        segmentos_selecionados = []
        if "Startup" in categorias_disponiveis:
            # Verifica se há dados de atores para obter segmentos
            df_atores_para_segmentos = None
            try:
                df_atores_para_segmentos = load_data_base_atores(force_reload=False)
            except:
                pass
            
            if df_atores_para_segmentos is not None and not df_atores_para_segmentos.empty:
                # Procura coluna de setor/segmento
                coluna_setor = None
                possiveis_nomes_setor = ['setor', 'sector', 'segmento', 'segment', 'segmentos', 'setores']
                for col in df_atores_para_segmentos.columns:
                    col_lower = str(col).lower().strip()
                    if any(nome in col_lower for nome in possiveis_nomes_setor):
                        coluna_setor = col
                        break
                
                if coluna_setor:
                    # Filtra apenas startups para obter segmentos únicos
                    coluna_categoria_atores = None
                    possiveis_nomes_categoria = ['categoria', 'category', 'tipo', 'type']
                    for col in df_atores_para_segmentos.columns:
                        col_lower = str(col).lower().strip()
                        if any(nome in col_lower for nome in possiveis_nomes_categoria):
                            coluna_categoria_atores = col
                            break
                    
                    # Filtra apenas startups
                    df_startups_para_segmentos = df_atores_para_segmentos.copy()
                    if coluna_categoria_atores:
                        df_startups_para_segmentos = df_startups_para_segmentos[
                            df_startups_para_segmentos[coluna_categoria_atores].astype(str).str.strip().str.lower() == 'startup'
                        ]
                    
                    # Obtém segmentos únicos (não vazios)
                    segmentos_disponiveis = df_startups_para_segmentos[coluna_setor].dropna()
                    segmentos_disponiveis = segmentos_disponiveis[segmentos_disponiveis.astype(str).str.strip() != '']
                    segmentos_disponiveis = sorted(segmentos_disponiveis.unique().tolist())
                    
                    if segmentos_disponiveis:
                        # Só mostra o filtro se Startup estiver nas categorias selecionadas
                        # Verifica tanto no estado dos cards quanto no filtro de categoria
                        categorias_ativas_list = [cat for cat, ativa in st.session_state.categorias_ativas.items() 
                                                  if ativa and cat in categorias_disponiveis]
                        filtro_categoria_atual = st.session_state.get("filtro_categoria", categorias_ativas_list)
                        
                        # Inicializa com lista vazia se não estiver definido
                        if "filtro_segmentos" not in st.session_state:
                            st.session_state.filtro_segmentos = []
                        
                        # Garante que os valores no session_state sejam válidos (ANTES de criar o widget)
                        segmentos_validos = [s for s in st.session_state.filtro_segmentos if s in segmentos_disponiveis]
                        if len(segmentos_validos) != len(st.session_state.filtro_segmentos):
                            st.session_state.filtro_segmentos = segmentos_validos
                        
                        # Se Startup não está selecionada, limpa o filtro de segmentos (ANTES de criar o widget)
                        if "Startup" not in categorias_ativas_list and "Startup" not in filtro_categoria_atual:
                            if st.session_state.filtro_segmentos:
                                st.session_state.filtro_segmentos = []
                        
                        # Mostra o filtro se Startup estiver selecionada
                        if "Startup" in categorias_ativas_list or "Startup" in filtro_categoria_atual:
                            segmentos_selecionados = st.multiselect(
                                "Segmentos (Startups)",
                                options=segmentos_disponiveis,
                                default=st.session_state.filtro_segmentos,
                                key="filtro_segmentos",
                                help="Filtra apenas startups por segmento. Não afeta outros atores."
                            )
                            # Não modificar st.session_state.filtro_segmentos aqui - o Streamlit já atualiza automaticamente via key
        
        # Processa cliques nos cards ANTES de criar o multiselect (para evitar erro de modificação do session_state)
        # Mapeia nomes dos cards para nomes das categorias no filtro
        card_to_category = {
            "Startups": "Startup",
            "Grandes Empresas Âncoras": "Empresa Âncora",
            "Fundos e Investidores": "Fundos e Investidores",
            "Universidades e ICTs": "Universidades e ICTs",
            "Órgãos Públicos e Apoio": "Órgãos Públicos e Apoio",
            "Hubs, Incubadoras e Parques Tecnológicos": "Hubs, Incubadoras e Parques Tecnológicos"
        }
        
        # Processa cliques nos cards (verifica flags de botões clicados)
        for card_name, category_name in card_to_category.items():
            click_flag_key = f"card_clicked_{category_name}"
            # Verifica se o card foi clicado (flag foi setada na renderização anterior)
            if click_flag_key in st.session_state and st.session_state[click_flag_key]:
                # Alterna o estado da categoria
                if category_name in st.session_state.categorias_ativas:
                    st.session_state.categorias_ativas[category_name] = not st.session_state.categorias_ativas[category_name]
                    # Limpa a flag
                    st.session_state[click_flag_key] = False
                    # Atualiza o filtro de categorias ANTES de criar o multiselect
                    categorias_ativas_list = [cat for cat, ativa in st.session_state.categorias_ativas.items() 
                                              if ativa and cat in categorias_disponiveis]
                    st.session_state.filtro_categoria = categorias_ativas_list
                    st.rerun()
        
        # Filtro de Categoria do Ator (seleção múltipla)
        # Sincroniza com o estado das categorias ativas dos cards
        categorias_ativas_list = [cat for cat, ativa in st.session_state.categorias_ativas.items() 
                                  if ativa and cat in categorias_disponiveis]
        
        # Atualiza o filtro baseado nas categorias ativas (usado internamente para filtrar dados)
        st.session_state.filtro_categoria = categorias_ativas_list.copy()
        
        # Filtro multiselect removido - agora usa apenas a legenda de categorias
        # Usa as categorias ativas como categorias selecionadas
        categorias_selecionadas = categorias_ativas_list
        
        # Aplica filtro de segmentos aos dados de atores ANTES de agregar
        segmentos_filtro = st.session_state.get("filtro_segmentos", [])
        df_atores_filtrado = df_atores.copy() if df_atores is not None and not df_atores.empty else None
        
        # Se há filtro de segmentos e há dados de atores, filtra apenas startups por segmento
        if segmentos_filtro and len(segmentos_filtro) > 0 and df_atores_filtrado is not None:
            # Procura coluna de setor/segmento
            coluna_setor_atores = None
            possiveis_nomes_setor = ['setor', 'sector', 'segmento', 'segment', 'segmentos', 'setores']
            for col in df_atores_filtrado.columns:
                col_lower = str(col).lower().strip()
                if any(nome in col_lower for nome in possiveis_nomes_setor):
                    coluna_setor_atores = col
                    break
            
            # Procura coluna de categoria
            coluna_categoria_atores = None
            possiveis_nomes_categoria = ['categoria', 'category', 'tipo', 'type', 'tipo_ator', 'actor_type']
            for col in df_atores_filtrado.columns:
                col_lower = str(col).lower().strip()
                if any(nome in col_lower for nome in possiveis_nomes_categoria):
                    coluna_categoria_atores = col
                    break
            
            if coluna_setor_atores and coluna_categoria_atores:
                # Separa startups e outros atores
                mask_startup = df_atores_filtrado[coluna_categoria_atores].astype(str).str.strip().str.lower() == 'startup'
                df_startups_filtrado = df_atores_filtrado[mask_startup].copy()
                df_outros_atores = df_atores_filtrado[~mask_startup].copy()
                
                # Aplica filtro de segmentos apenas nas startups
                df_startups_filtrado = df_startups_filtrado[
                    df_startups_filtrado[coluna_setor_atores].astype(str).str.strip().isin(
                        [str(seg).strip() for seg in segmentos_filtro]
                    )
                ]
                
                # Combina startups filtradas com outros atores
                df_atores_filtrado = pd.concat([df_startups_filtrado, df_outros_atores], ignore_index=True)
        
        # Reagrega dados se houver filtro de segmentos e dados de atores
        if segmentos_filtro and len(segmentos_filtro) > 0 and df_atores_filtrado is not None and not df_atores_filtrado.empty:
            # Procura colunas de localização para reagregar
            coluna_cidade_atores = None
            possiveis_nomes_cidade = ['cidade', 'municipio', 'cidade_max', 'município']
            for col in df_atores_filtrado.columns:
                col_lower = str(col).lower().strip()
                if any(nome in col_lower for nome in possiveis_nomes_cidade):
                    coluna_cidade_atores = col
                    break
            
            coluna_regiao_atores = None
            possiveis_nomes_regiao = ['região sebrae', 'regiao sebrae', 'região_sebrae', 'regiao_sebrae', 
                                     'nome_mesorregiao', 'mesorregiao', 'regiao', 'região']
            for col in df_atores_filtrado.columns:
                col_lower = str(col).lower().strip()
                if any(nome in col_lower for nome in possiveis_nomes_regiao):
                    coluna_regiao_atores = col
                    break
            
            if coluna_categoria_atores and coluna_cidade_atores:
                # Filtra apenas startups para contar
                df_startups_para_contar = df_atores_filtrado[
                    df_atores_filtrado[coluna_categoria_atores].astype(str).str.strip().str.lower() == 'startup'
                ].copy()
                
                # Reagrega contagens de startups por município/região
                if coluna_regiao_atores:
                    df_agregado = df_startups_para_contar.groupby([coluna_regiao_atores, coluna_cidade_atores]).size().reset_index(name='qtd_startups_filtrado')
                else:
                    df_agregado = df_startups_para_contar.groupby([coluna_cidade_atores]).size().reset_index(name='qtd_startups_filtrado')
                
                # Atualiza df_regions com as novas contagens (apenas para startups)
                for idx, row in df_regions.iterrows():
                    regiao_match = str(row['regiao_final']).strip() if pd.notna(row['regiao_final']) else ""
                    municipio_match = str(row[coluna_municipio]).strip() if pd.notna(row[coluna_municipio]) else ""
                    
                    # Busca contagem filtrada
                    if coluna_regiao_atores:
                        match = df_agregado[
                            (df_agregado[coluna_regiao_atores].astype(str).str.strip().str.lower() == regiao_match.lower()) &
                            (df_agregado[coluna_cidade_atores].astype(str).str.strip().str.lower() == municipio_match.lower())
                        ]
                    else:
                        match = df_agregado[
                            df_agregado[coluna_cidade_atores].astype(str).str.strip().str.lower() == municipio_match.lower()
                        ]
                    
                    if not match.empty and coluna_qtd_startups in df_regions.columns:
                        # Atualiza apenas a contagem de startups com o valor filtrado
                        nova_contagem = match.iloc[0]['qtd_startups_filtrado'] if 'qtd_startups_filtrado' in match.columns else 0
                        df_regions.loc[idx, coluna_qtd_startups] = int(nova_contagem) if pd.notna(nova_contagem) else 0
                    elif coluna_qtd_startups in df_regions.columns:
                        # Se não encontrou match, zera a contagem de startups (não há startups desse segmento neste município)
                        df_regions.loc[idx, coluna_qtd_startups] = 0
        
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
            
            if "Hubs, Incubadoras e Parques Tecnológicos" in categorias_selecionadas and coluna_qtd_hubs_incubadoras_parquestecnologicos in df_regions_filtrado.columns:
                count_filtrado += pd.to_numeric(df_regions_filtrado[coluna_qtd_hubs_incubadoras_parquestecnologicos], errors='coerce').fillna(0)
            
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
        
        # Hubs, Incubadoras e Parques Tecnológicos - usa dados agregados do mapa
        if coluna_qtd_hubs_incubadoras_parquestecnologicos in df_regions_filtrado.columns:
            total_hubs = pd.to_numeric(df_regions_filtrado[coluna_qtd_hubs_incubadoras_parquestecnologicos], errors='coerce').fillna(0).sum()
            contadores["Hubs, Incubadoras e Parques Tecnológicos"] = int(total_hubs)
        else:
            contadores["Hubs, Incubadoras e Parques Tecnológicos"] = 0
        
        # Prepara dados para a legenda de categorias
        categorias_legend_data = {}
        card_to_category = {
            "Startups": "Startup",
            "Grandes Empresas Âncoras": "Empresa Âncora",
            "Fundos e Investidores": "Fundos e Investidores",
            "Universidades e ICTs": "Universidades e ICTs",
            "Hubs, Incubadoras e Parques Tecnológicos": "Hubs, Incubadoras e Parques Tecnológicos",
            "Órgãos Públicos e Apoio": "Órgãos Públicos e Apoio"
        }
        
        for display_name, category_name in card_to_category.items():
            # Obtém a cor da categoria
            color = CATEGORIA_COLORS.get(category_name, "#cccccc")
            # Obtém o total (usa o nome de exibição para buscar no contadores)
            total = contadores.get(display_name, 0)
            
            categorias_legend_data[category_name] = {
                "color": color,
                "total": total,
                "display_name": display_name
            }
        
        # Renderiza a legenda de categorias
        render_category_legend(categorias_legend_data, title="")
    
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
        qtd_hubs_incubadoras_parquestecnologicos_vals = pd.to_numeric(df_regiao_com_match[coluna_qtd_hubs_incubadoras_parquestecnologicos], errors='coerce').fillna(0).astype(int).values if coluna_qtd_hubs_incubadoras_parquestecnologicos in df_regiao_com_match.columns else np.zeros(len(df_regiao_com_match))

        # Constrói hovertemplate dinamicamente baseado nas categorias selecionadas
        hovertemplate_parts = [
            "<b>Região:</b> %{customdata[0]}<br>",
            "<b>Município:</b> %{customdata[1]}<br>"
        ]
        
        # Se nenhuma categoria selecionada, mostra todas as disponíveis
        categorias_para_mostrar = categorias_selecionadas if categorias_selecionadas else categorias_disponiveis
        
        # Adiciona todas as categorias no customdata na ordem fixa: startups, empresas âncora, fundos, universidades, órgãos, hubs
        # Índices: 0=região, 1=município, 2=startups, 3=empresas âncora, 4=fundos e investidores, 5=universidades e ICTs, 6=órgãos, 7=hubs
        
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
        
        if "Hubs, Incubadoras e Parques Tecnológicos" in categorias_para_mostrar:
            hovertemplate_parts.append("<b>Total de Hubs, Incubadoras e Parques Tecnológicos:</b> %{customdata[7]}<br>")
        
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
                        qtd_hubs_incubadoras_parquestecnologicos_vals,
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
        margin=dict(l=0, r=0, t=0, b=0),
        title_text="",
        showlegend=True,
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.98)",  # Fundo branco
            bordercolor=SEBRAE_AZUL,  # Borda azul Sebrae
            font=dict(size=15, color=SEBRAE_CINZA_ESCURO, family="Arial, sans-serif"),  # Texto cinza escuro
            namelength=-1,
        ),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.95)",  # Fundo branco semi-transparente
            bordercolor=SEBRAE_AZUL,  # Borda azul Sebrae
            borderwidth=2,
            font=dict(color=SEBRAE_CINZA_ESCURO, size=13),  # Texto cinza escuro
            itemclick="toggleothers",
            itemdoubleclick="toggle",
            tracegroupgap=8,
            itemsizing="constant",
            itemwidth=30,
        ),
        height=MAP_HEIGHT,
        plot_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
        paper_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
    )

    # Mostra o mapa no lado direito (legenda está dentro do mapa)
    with col_map:
        # Habilita seleção no mapa para capturar cliques
        fig.update_layout(
            clickmode='event+select'
        )
        
        # Configura o mapa para permitir seleção
        map_config = MAP_CONFIG.copy()
        map_config['displayModeBar'] = True
        
        # Obtém o estado atual dos filtros para decidir o comportamento
        regiao_atual = st.session_state.get("filtro_regiao", "Todas")
        
        # Renderiza o mapa e captura seleções usando on_select (Streamlit 1.28+)
        try:
            selected_data = st.plotly_chart(
                fig, 
                use_container_width=True, 
                config=map_config,
                on_select="rerun",
                key="mapa_choropleth"
            )
            
            # Quando há uma seleção, armazena para processar na próxima renderização
            # IMPORTANTE: O on_select="rerun" faz rerun automaticamente quando há seleção
            # Na próxima renderização (que acontece imediatamente após o clique), 
            # a seleção será processada ANTES dos widgets serem criados
            if selected_data and isinstance(selected_data, dict):
                if 'selection' in selected_data:
                    selection = selected_data['selection']
                    if selection and 'points' in selection and len(selection['points']) > 0:
                        point = selection['points'][0]
                        if 'customdata' in point and len(point['customdata']) >= 2:
                            # Cria hash da seleção para verificar se é nova
                            selecao_hash = str(point['customdata'][0]) + "|" + str(point['customdata'][1])
                            ultima_hash = st.session_state.get("ultima_selecao_processada", None)
                            
                            # Se é uma seleção nova, armazena e força rerun para processar imediatamente
                            if selecao_hash != ultima_hash:
                                st.session_state.mapa_selecao_pendente = selection
                                # Força rerun para processar a seleção na próxima renderização
                                # (antes dos widgets serem criados)
                                st.rerun()
        except TypeError:
            # Fallback para versões antigas do Streamlit que não suportam on_select
            st.plotly_chart(fig, use_container_width=True, config=map_config)


def create_alternative_choropleth(df_regions):
    """
    Cria mapa alternativo (scatter) caso o GeoJSON não esteja disponível.
    """
    if df_regions.empty:
        st.warning("⚠️ Sem dados para gerar visualização alternativa.")
        return

    regioes = sorted(df_regions['regiao_final'].unique())
    
    # Cores especiais para regiões específicas
    TRIANGULO_COLOR = "#003366"  # Azul escuro para Triângulo e Alto Paranaíba
    RIO_DOCE_COLOR = "#8B0000"  # Vermelho escuro para Rio Doce e Vale do Aço
    
    base_colors = {}
    for i, regiao in enumerate(regioes):
        regiao_lower = str(regiao).lower().strip()
        
        # Verifica se é Triângulo e Alto Paranaíba
        if 'triângulo' in regiao_lower or 'triangulo' in regiao_lower or 'paranaíba' in regiao_lower or 'paranaiba' in regiao_lower:
            base_colors[regiao] = TRIANGULO_COLOR
        # Verifica se é Rio Doce e Vale do Aço
        elif 'rio doce' in regiao_lower or 'vale do aço' in regiao_lower or 'vale do aco' in regiao_lower:
            base_colors[regiao] = RIO_DOCE_COLOR
        else:
            base_colors[regiao] = REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)]

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
        margin=dict(l=0, r=0, t=0, b=0),
        title_text="",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.95)",  # Fundo branco semi-transparente
            bordercolor=SEBRAE_AZUL,  # Borda azul Sebrae
            borderwidth=2,
            font=dict(color=SEBRAE_CINZA_ESCURO, size=11),  # Texto cinza escuro
            itemclick="toggleothers",
            itemdoubleclick="toggle",
        ),
        height=MAP_HEIGHT,
        plot_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
        paper_bgcolor=SEBRAE_AZUL_CLARO,  # Fundo azul Sebrae
    )

    # Mostra o mapa ocupando toda a largura (legenda está dentro do mapa)
    st.plotly_chart(fig, use_container_width=True, config=MAP_CONFIG)

def _render_custom_html_table(df_display, styled_df, is_multiindex, categoria_col_for_style,
                             regiao_col_for_style, regioes_cores, coluna_site, format_dict):
    """
    Renderiza tabela usando HTML customizado em vez de st.dataframe.
    Esta função detecta automaticamente os parâmetros necessários.
    """
    html_table = _build_custom_html_table(
        df_display,
        styled_df,
        is_multiindex,
        categoria_col_for_style,
        regiao_col_for_style,
        regioes_cores,
        coluna_site,
        format_dict
    )
    # Separa o CSS do HTML para injetar corretamente
    if html_table.startswith('<style>'):
        # Extrai o CSS e o HTML
        css_end = html_table.find('</style>') + 8
        css_part = html_table[:css_end]
        html_part = html_table[css_end:]
        # Injeta o CSS primeiro
        st.markdown(css_part, unsafe_allow_html=True)
        # Depois injeta o HTML da tabela
        st.markdown(html_part, unsafe_allow_html=True)
    else:
        st.markdown(html_table, unsafe_allow_html=True)

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
    
    # Inicia construção do HTML com wrapper para controlar largura e altura
    # Altura aproximada para 10 linhas: 10 linhas * (altura da linha ~35px) + cabeçalho ~40px = ~390px
    html_parts = [f'<div style="width:100%;max-width:100%;overflow-x:auto;margin:0 auto;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);border:1px solid rgba(0,0,0,0.4);background-color:white;">']
    html_parts.append(f'<div style="max-height:390px;overflow-y:auto;overflow-x:auto;">')
    html_parts.append(f'<table id="data-table" style="width:100%;border-collapse:collapse;background-color:white;font-size:0.85rem;margin:0;">')
    
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
                # Cabeçalho agrupado também em azul escuro
                bg_color = "#003366"  # Azul escuro
                html_parts.append(f'<th colspan="{colspan}" style="background-color:{bg_color};color:white;font-weight:600;padding:6px 8px;text-align:left;border:1px solid rgba(0,0,0,0.1);font-size:0.85rem;white-space:nowrap;">{group_name}</th>')
        
        html_parts.append('</tr>')
        
        # Segunda linha: nomes das colunas
        html_parts.append('<tr>')
        for col_tuple in df_display.columns:
            if len(col_tuple) == 2:
                col_name = col_tuple[1]
            else:
                col_name = col_tuple
            style = f'padding:6px 8px;text-align:left;border:1px solid rgba(0,0,0,0.1);background-color:#003366;color:white;font-weight:600;font-size:0.85rem;white-space:nowrap;'
            html_parts.append(f'<th style="{style}">{col_name}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')
    else:
        html_parts.append('<thead><tr>')
        for col in df_display.columns:
            style = 'padding:6px 8px;text-align:left;border:1px solid rgba(0,0,0,0.1);background-color:#003366;color:white;font-weight:600;font-size:0.85rem;white-space:nowrap;'
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
            # Estilo base: fundo branco e texto escuro
            cell_style = f'padding:6px 8px;border:1px solid rgba(0,0,0,0.1);background-color:white !important;color:{SEBRAE_CINZA_ESCURO} !important;font-size:0.85rem;word-wrap:break-word;overflow-wrap:break-word;'
            
            # Se for a coluna de site, centraliza o conteúdo
            if col_idx == site_col_idx:
                cell_style += 'text-align:center;'
            
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
                    # Mostra apenas o ícone, sem o texto da URL
                    cell_value = f'<a href="{site_url}" target="_blank" rel="noopener noreferrer" style="color:{SEBRAE_AZUL};text-decoration:none;font-size:1.1rem;display:inline-block;text-align:center;" title="{site_url_title}">🔗</a>'
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
    html_parts.append('</div>')  # Fecha o div de scroll
    html_parts.append('</div>')  # Fecha o wrapper div principal
    
    # Adiciona CSS para estilização da tabela
    css_js = f"""
    <style>
        /* Container da tabela - mesma largura do heatmap */
        #data-table, #data-table-2 {{
            width: 100% !important;
            max-width: 100% !important;
            border-collapse: collapse !important;
            background-color: white !important;
            font-size: 0.85rem !important;
            table-layout: auto !important;
            border-radius: 0 !important; /* Remove border-radius da tabela, deixa no container */
        }}
        
        /* Estilização da barra de rolagem */
        div[style*="max-height"]::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        div[style*="max-height"]::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}
        
        div[style*="max-height"]::-webkit-scrollbar-thumb {{
            background: #888;
            border-radius: 4px;
        }}
        
        div[style*="max-height"]::-webkit-scrollbar-thumb:hover {{
            background: #555;
        }}
        /* Cabeçalho - azul escuro com texto branco */
        #data-table thead th, 
        #data-table-2 thead th,
        #data-table thead tr th,
        #data-table-2 thead tr th {{
            background-color: #003366 !important;
            color: white !important;
            font-weight: 600 !important;
            padding: 6px 8px !important;
            text-align: left !important;
            border: 1px solid rgba(0,0,0,0.1) !important;
            font-size: 0.85rem !important;
            white-space: nowrap !important;
            position: sticky !important;
            top: 0 !important;
            z-index: 10 !important;
        }}
        
        /* Primeira célula do cabeçalho - canto superior esquerdo arredondado */
        #data-table thead tr:first-child th:first-child,
        #data-table-2 thead tr:first-child th:first-child {{
            border-top-left-radius: 8px !important;
        }}
        
        /* Última célula do cabeçalho - canto superior direito arredondado */
        #data-table thead tr:first-child th:last-child,
        #data-table-2 thead tr:first-child th:last-child {{
            border-top-right-radius: 8px !important;
        }}
        
        /* Última linha - cantos inferiores arredondados */
        #data-table tbody tr:last-child td:first-child,
        #data-table-2 tbody tr:last-child td:first-child {{
            border-bottom-left-radius: 8px !important;
        }}
        
        #data-table tbody tr:last-child td:last-child,
        #data-table-2 tbody tr:last-child td:last-child {{
            border-bottom-right-radius: 8px !important;
        }}
        /* Células do corpo - fundo branco com texto escuro */
        #data-table tbody td, 
        #data-table-2 tbody td,
        #data-table tbody tr td,
        #data-table-2 tbody tr td {{
            color: {SEBRAE_CINZA_ESCURO} !important;
            background-color: white !important;
            padding: 6px 8px !important;
            border: 1px solid rgba(0,0,0,0.1) !important;
            font-size: 0.85rem !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
        }}
        /* Garante que células com cores especiais mantenham fundo branco quando não têm cor especial */
        #data-table tbody td:not([style*="background-color"]),
        #data-table-2 tbody td:not([style*="background-color"]) {{
            background-color: white !important;
        }}
        #data-table td a, #data-table-2 td a {{
            text-decoration: none;
        }}
        #data-table td a:hover, #data-table-2 td a:hover {{
            opacity: 0.8;
            transform: scale(1.1);
            transition: all 0.2s ease;
        }}
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
    
    # 1. Nome do ator - busca pelo nome exato primeiro, depois variações
    coluna_nome_ator = None
    # Primeiro tenta o nome exato "Nome do Ator"
    if 'Nome do Ator' in df.columns:
        coluna_nome_ator = 'Nome do Ator'
        adicionar_coluna('Nome do Ator')
    else:
        # Se não encontrar, busca por variações
        possiveis_colunas_nome = ['name', 'nome', 'nome do ator', 'nome_ator', 'actor_name', 'nome_do_ator']
        for col in df.columns:
            col_lower = col.lower().strip()
            # Verifica se é uma coluna de nome (não empresa/company)
            if any(nome in col_lower for nome in possiveis_colunas_nome) and \
               not any(palavra in col_lower for palavra in ['empresa', 'company', 'empres']):
                coluna_nome_ator = col
                adicionar_coluna(col)
                break
        
        # Se não encontrou, tenta buscar de forma mais ampla
        if not coluna_nome_ator:
            buscar_coluna(['name', 'nome', 'nome do ator'])
            if 'name' in df.columns and 'name' not in colunas_adicionadas:
                adicionar_coluna('name')
                coluna_nome_ator = 'name'
    
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
    
    # 4. Regiao Sebrae - busca pelo nome exato primeiro (sem acento)
    coluna_regiao_sebrae = None
    # Tenta os nomes exatos primeiro (com e sem acento)
    if 'Regiao Sebrae' in df.columns:
        coluna_regiao_sebrae = 'Regiao Sebrae'
        adicionar_coluna('Regiao Sebrae')
    elif 'Região Sebrae' in df.columns:
        coluna_regiao_sebrae = 'Região Sebrae'
        adicionar_coluna('Região Sebrae')
    else:
        # Se não encontrar, busca por variações
        for col in df.columns:
            col_lower = col.lower().strip()
            if ('sebrae' in col_lower or 'regiao' in col_lower or 'região' in col_lower or 'mesorregiao' in col_lower) and col not in colunas_adicionadas:
                coluna_regiao_sebrae = col
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
        
        # Garante que a coluna de região seja incluída se existir
        coluna_regiao_original = None
        for col in df.columns:
            col_lower = col.lower().strip()
            if ('sebrae' in col_lower or 'regiao' in col_lower or 'região' in col_lower or 'mesorregiao' in col_lower):
                coluna_regiao_original = col
                # Adiciona se não estiver presente
                if col not in colunas_disponiveis:
                    colunas_disponiveis.append(col)
                break
        
        # Cria uma cópia para estilização - IMPORTANTE: usa as colunas originais do DataFrame
        # Garante que todas as colunas selecionadas existem no DataFrame original
        colunas_validas = [col for col in colunas_disponiveis if col in df.columns]
        if not colunas_validas:
            # Se nenhuma coluna válida foi encontrada, usa todas as colunas disponíveis
            colunas_validas = list(df.columns)
        df_display = df[colunas_validas].copy()
        
        # Processa a coluna de site - garante que tenha URLs válidas para LinkColumn
        # IMPORTANTE: Isso deve ser feito ANTES de criar o MultiIndex
        if coluna_site:
            def formatar_site_url(url):
                """
                Formata o campo de site para garantir URL válida (com protocolo).
                Retorna string vazia para valores inválidos (LinkColumn precisa de strings).
                """
                if pd.isna(url) or str(url).strip() == '':
                    return ''  # Retorna string vazia (não None)
                url_str = str(url).strip()
                # Garante que a URL tenha protocolo
                if not url_str.startswith(('http://', 'https://')):
                    url_str = 'https://' + url_str
                return url_str
            
            # Aplica a função para formatar o site como URL válida
            # Garante que seja do tipo string
            if coluna_site in df_display.columns:
                df_display[coluna_site] = df_display[coluna_site].apply(formatar_site_url).astype(str)
        
        # Formata a coluna "Ano de Fundação" para remover casas decimais
        for col in df_display.columns:
            col_lower = str(col).lower().strip()
            if any(palavra in col_lower for palavra in ['foundation', 'ano de fundação', 'ano']):
                # Converte para numérico e depois para inteiro, removendo decimais
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                # Converte para inteiro, tratando NaNs
                df_display[col] = df_display[col].apply(lambda x: int(float(x)) if pd.notna(x) else pd.NA)
        
        # Mapeia nomes de colunas para nomes estáticos e limpos
        # IMPORTANTE: Preserva nomes exatos quando já estão corretos
        column_name_mapping = {}
        for col in df_display.columns:
            col_str = str(col).strip()
            col_lower = col_str.lower()
            col_parts = col_str.split()
            first_part = col_parts[0].lower() if col_parts else ''
            
            # Se o nome já está correto, preserva
            if col_str == 'Nome do Ator':
                column_name_mapping[col] = 'Nome do Ator'
            elif col_str == 'Regiao Sebrae' or col_str == 'Região Sebrae':
                column_name_mapping[col] = 'Regiao Sebrae'
            # Caso contrário, mapeia baseado no conteúdo
            elif (first_part in ['name', 'nome'] or 
                  col_lower.startswith('nome') or 
                  col_lower.startswith('name')) and \
                 not any(palavra in col_lower for palavra in ['empresa', 'company', 'empres']):
                column_name_mapping[col] = 'Nome do Ator'
            elif any(palavra in first_part for palavra in ['site', 'website', 'url', 'link', 'web', 'homepage']) or \
                 any(palavra in col_lower[:10] for palavra in ['site', 'website']):
                column_name_mapping[col] = 'Site'
            elif any(palavra in first_part for palavra in ['categoria', 'category', 'tipo', 'type']) or \
                 any(palavra in col_lower[:15] for palavra in ['categoria', 'category']):
                column_name_mapping[col] = 'Categoria'
            elif any(palavra in first_part for palavra in ['cidade', 'municipio', 'município', 'city']):
                column_name_mapping[col] = 'Cidade'
            elif 'regiao sebrae' in col_lower or 'região sebrae' in col_lower or col_str == 'Regiao Sebrae' or col_str == 'Região Sebrae':
                column_name_mapping[col] = 'Regiao Sebrae'
            elif any(palavra in first_part for palavra in ['regiao', 'região', 'sebrae', 'mesorregiao']) or \
                 any(palavra in col_lower[:15] for palavra in ['regiao', 'região', 'mesorregiao', 'sebrae']):
                column_name_mapping[col] = 'Região'
            elif any(palavra in first_part for palavra in ['sector', 'setor', 'setores']) or \
                 any(palavra in col_lower[:10] for palavra in ['sector', 'setor']):
                column_name_mapping[col] = 'Setor'
            elif any(palavra in first_part for palavra in ['foundation', 'ano']) or \
                 'ano de fundação' in col_lower or 'foundation' in col_lower[:15]:
                column_name_mapping[col] = 'Ano de Fundação'
            elif any(palavra in first_part for palavra in ['description', 'descrição', 'descricao']):
                column_name_mapping[col] = 'Descrição'
            else:
                # Para outras colunas, mantém o nome original
                column_name_mapping[col] = col_str
        
        # Renomeia as colunas usando o mapeamento estático
        df_display = df_display.rename(columns=column_name_mapping)
        
        # Verifica e corrige mapeamentos incorretos
        # Se há uma coluna "Nome" mas não "Nome do Ator", renomeia
        if 'Nome' in df_display.columns and 'Nome do Ator' not in df_display.columns:
            df_display = df_display.rename(columns={'Nome': 'Nome do Ator'})
        
        # Se há uma coluna que começa com "Nome" mas não é "Nome do Ator", tenta corrigir
        for col in list(df_display.columns):
            if col.startswith('Nome') and col != 'Nome do Ator' and 'Nome do Ator' not in df_display.columns:
                df_display = df_display.rename(columns={col: 'Nome do Ator'})
                break
        
        # Garante ordem correta das colunas: Nome do Ator primeiro
        ordem_colunas = ['Nome do Ator', 'Site', 'Categoria', 'Cidade', 'Regiao Sebrae', 'Região Sebrae', 'Região', 'Setor', 'Ano de Fundação', 'Descrição']
        colunas_existentes = [col for col in ordem_colunas if col in df_display.columns]
        colunas_restantes = [col for col in df_display.columns if col not in ordem_colunas]
        
        # Reordena as colunas
        df_display = df_display[colunas_existentes + colunas_restantes]
        
        # Verifica se está usando MultiIndex (sempre False agora)
        is_multiindex = False
        
        # Formata novamente após criar MultiIndex (caso necessário)
        # Garante que a coluna de site seja string após criar MultiIndex
        if is_multiindex and coluna_site:
            for col_tuple in df_display.columns:
                if len(col_tuple) == 2 and col_tuple[1] == coluna_site:
                    # Garante que seja string e formata URLs
                    def formatar_site_url_pos_multindex(url):
                        if pd.isna(url) or str(url).strip() == '':
                            return ''
                        url_str = str(url).strip()
                        if not url_str.startswith(('http://', 'https://')):
                            url_str = 'https://' + url_str
                        return url_str
                    
                    df_display[col_tuple] = df_display[col_tuple].apply(formatar_site_url_pos_multindex).astype(str)
                    df_display[col_tuple] = df_display[col_tuple].replace('nan', '')
                    break
        
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
        
        # Encontra a coluna de categoria para estilização
        categoria_col_for_style = None
        if coluna_categoria:
            # Usa o nome mapeado
            categoria_col_mapped = column_name_mapping.get(coluna_categoria, None)
            if categoria_col_mapped and categoria_col_mapped in df_display.columns:
                categoria_col_for_style = categoria_col_mapped
        
        # Encontra a coluna de região Sebrae para estilização
        # Usa o nome original da coluna antes do mapeamento
        coluna_regiao_sebrae = None
        # Procura no DataFrame original
        for col in df.columns:
            col_lower = col.lower().strip()
            if ('sebrae' in col_lower or 'regiao' in col_lower or 'região' in col_lower or 'mesorregiao' in col_lower):
                coluna_regiao_sebrae = col
                break
        
        # Obtém cores das regiões (mesma lógica do mapa)
        regioes_cores = {}
        if coluna_regiao_sebrae and coluna_regiao_sebrae in df.columns:
            # Obtém todas as regiões únicas do DataFrame
            regioes_unicas = sorted(df[coluna_regiao_sebrae].dropna().unique())
            # Atribui cores usando a mesma paleta do mapa
            # Cores especiais para regiões específicas
            TRIANGULO_COLOR = "#003366"  # Azul escuro para Triângulo e Alto Paranaíba
            RIO_DOCE_COLOR = "#8B0000"  # Vermelho escuro para Rio Doce e Vale do Aço
            
            regioes_cores = {}
            for i, regiao in enumerate(regioes_unicas):
                regiao_lower = str(regiao).lower().strip()
                
                # Verifica se é Triângulo e Alto Paranaíba
                if 'triângulo' in regiao_lower or 'triangulo' in regiao_lower or 'paranaíba' in regiao_lower or 'paranaiba' in regiao_lower:
                    regioes_cores[regiao] = TRIANGULO_COLOR
                # Verifica se é Rio Doce e Vale do Aço
                elif 'rio doce' in regiao_lower or 'vale do aço' in regiao_lower or 'vale do aco' in regiao_lower:
                    regioes_cores[regiao] = RIO_DOCE_COLOR
                else:
                    regioes_cores[regiao] = REGION_COLOR_PALETTE[i % len(REGION_COLOR_PALETTE)]
        
        # Encontra a coluna de região no DataFrame display
        regiao_col_for_style = None
        if coluna_regiao_sebrae:
            # Usa o nome mapeado
            regiao_col_mapped = column_name_mapping.get(coluna_regiao_sebrae, None)
            if regiao_col_mapped and regiao_col_mapped in df_display.columns:
                regiao_col_for_style = regiao_col_mapped
        
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
                # Cor semi-transparente para "Dados Gerais" (azul Sebrae)
                cor_dados_gerais = f"rgba(0, 82, 165, 0.15)"  # Azul Sebrae semi-transparente
                # Cor semi-transparente para "Dados (Startups)" (verde Sebrae)
                cor_dados_startups = f"rgba(0, 168, 89, 0.15)"  # Verde Sebrae semi-transparente
                
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
            
            # Configura column_config para coluna de site como LinkColumn
            # IMPORTANTE: Quando usamos column_config, precisamos usar o DataFrame original (df_display),
            # não o styled_df, porque o pandas Styler não funciona bem com column_config
            column_config = {}
            if coluna_site:
                # Usa o nome mapeado da coluna de site
                coluna_site_key = column_name_mapping.get(coluna_site, None)
                if not coluna_site_key or coluna_site_key not in df_display.columns:
                    coluna_site_key = None
                
                if coluna_site_key:
                    # Garante que a coluna seja do tipo string (LinkColumn requer strings)
                    # E que todas as URLs tenham protocolo
                    def garantir_url_valida(url):
                        if pd.isna(url) or str(url).strip() == '' or str(url).strip() in ['nan', 'None', 'NaN']:
                            return ''
                        url_str = str(url).strip()
                        # Garante que a URL tenha protocolo
                        if url_str and not url_str.startswith(('http://', 'https://')):
                            url_str = 'https://' + url_str
                        return url_str
                    
                    df_display[coluna_site_key] = df_display[coluna_site_key].apply(garantir_url_valida).astype(str)
                    
                    # Configura a coluna de site como LinkColumn
                    # Seguindo o exemplo do Streamlit exatamente
                    column_config[coluna_site_key] = st.column_config.LinkColumn(
                        help="Clique para abrir o site em uma nova aba"
                    )
            
            # Se há column_config, usa o DataFrame original ao invés do styled_df
            # porque column_config não funciona corretamente com pandas Styler
            if column_config:
                # IMPORTANTE: column_config não aceita tuplas como chaves (MultiIndex)
                # Precisamos aplanar o MultiIndex antes de aplicar o column_config
                df_para_display = df_display.copy()
                column_config_flat = {}
                
                if is_multiindex:
                    # Aplana o MultiIndex: usa apenas o segundo nível como nome da coluna
                    # Garante que estamos usando apenas os nomes das colunas, não os valores
                    new_columns = []
                    for col in df_para_display.columns:
                        if isinstance(col, tuple) and len(col) == 2:
                            # Usa apenas o segundo nível (nome da coluna)
                            new_columns.append(str(col[1]))
                        elif isinstance(col, tuple):
                            # Se for tupla mas não tiver 2 elementos, usa o último
                            new_columns.append(str(col[-1]))
                        else:
                            # Se não for tupla, usa o valor diretamente (mas garante que é string)
                            new_columns.append(str(col))
                    df_para_display.columns = new_columns
                    # Cria um novo column_config com chaves aplanadas (strings)
                    for old_key, config in column_config.items():
                        if isinstance(old_key, tuple) and len(old_key) == 2:
                            # Usa o segundo nível da tupla como chave (nome da coluna)
                            new_key = str(old_key[1])
                            column_config_flat[new_key] = config
                        else:
                            column_config_flat[str(old_key)] = config
                else:
                    column_config_flat = column_config
                
                # Usa HTML customizado em vez de st.dataframe
                _render_custom_html_table(
                    df_para_display,
                    None,
                    False,
                    categoria_col_for_style if 'categoria_col_for_style' in locals() else None,
                    regiao_col_for_style if 'regiao_col_for_style' in locals() else None,
                    regioes_cores if 'regioes_cores' in locals() else {},
                    coluna_site if 'coluna_site' in locals() else None,
                    format_dict if 'format_dict' in locals() else {}
                )
            else:
                # Sempre aplana o MultiIndex antes de renderizar para evitar problemas de renderização
                if is_multiindex:
                    df_para_display = df_display.copy()
                    new_columns = []
                    col_mapping = {}  # Mapeia colunas antigas para novas
                    for col in df_para_display.columns:
                        if isinstance(col, tuple) and len(col) == 2:
                            new_col_name = str(col[1])
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                        elif isinstance(col, tuple):
                            new_col_name = str(col[-1])
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                        else:
                            new_col_name = str(col)
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                    df_para_display.columns = new_columns
                    
                    # Recria o styled_df com as colunas aplanadas, preservando estilos
                    styled_df_flat = df_para_display.style
                    
                    # Aplica estilos de categoria se houver
                    if categoria_col_for_style:
                        categoria_col_flat = col_mapping.get(categoria_col_for_style, None)
                        if categoria_col_flat:
                            def style_categoria_flat(val):
                                if pd.isna(val):
                                    return ''
                                valor_str = str(val).strip()
                                cor = None
                                for categoria_key, categoria_cor in CATEGORIA_COLORS.items():
                                    if categoria_key.lower() in valor_str.lower() or valor_str.lower() in categoria_key.lower():
                                        cor = categoria_cor
                                        break
                                if not cor:
                                    cor = "#6c757d"
                                if cor.startswith('#'):
                                    r = int(cor[1:3], 16)
                                    g = int(cor[3:5], 16)
                                    b = int(cor[5:7], 16)
                                    cor_transparente = f"rgba({r}, {g}, {b}, 0.3)"
                                else:
                                    cor_transparente = cor
                                return f'background-color: {cor_transparente}; border-left: 3px solid {cor}; padding: 4px 8px;'
                            styled_df_flat = styled_df_flat.map(style_categoria_flat, subset=[categoria_col_flat])
                    
                    # Aplica estilos de região se houver
                    if regiao_col_for_style and regioes_cores:
                        regiao_col_flat = col_mapping.get(regiao_col_for_style, None)
                        if regiao_col_flat:
                            def style_regiao_flat(val):
                                if pd.isna(val):
                                    return ''
                                valor_str = str(val).strip()
                                cor_hex = regioes_cores.get(valor_str, "#6c757d")
                                cor_rgba = color_with_intensity(cor_hex, 0.0, min_alpha=0.18)
                                return f'background-color: {cor_rgba}; padding: 4px 8px;'
                            styled_df_flat = styled_df_flat.map(style_regiao_flat, subset=[regiao_col_flat])
                    
                    # Aplica formatação se houver
                    if format_dict:
                        format_dict_flat = {}
                        for old_key, fmt in format_dict.items():
                            new_key = col_mapping.get(old_key, old_key)
                            format_dict_flat[new_key] = fmt
                        if format_dict_flat:
                            styled_df_flat = styled_df_flat.format(format_dict_flat, na_rep='')
                    
                    # Usa HTML customizado em vez de st.dataframe
                    _render_custom_html_table(
                        df_para_display,
                        styled_df_flat,
                        False,
                        categoria_col_flat if 'categoria_col_flat' in locals() else None,
                        regiao_col_flat if 'regiao_col_flat' in locals() else None,
                        regioes_cores if 'regioes_cores' in locals() else {},
                        coluna_site if 'coluna_site' in locals() else None,
                        format_dict_flat if 'format_dict_flat' in locals() else {}
                    )
                else:
                    # Usa HTML customizado em vez de st.dataframe
                    _render_custom_html_table(
                        df_display,
                        styled_df,
                        is_multiindex,
                        categoria_col_for_style if 'categoria_col_for_style' in locals() else None,
                        regiao_col_for_style if 'regiao_col_for_style' in locals() else None,
                        regioes_cores if 'regioes_cores' in locals() else {},
                        coluna_site if 'coluna_site' in locals() else None,
                        format_dict if 'format_dict' in locals() else {}
                    )
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
                # Cor semi-transparente para "Dados Gerais" (azul Sebrae)
                cor_dados_gerais = f"rgba(0, 82, 165, 0.15)"  # Azul Sebrae semi-transparente
                # Cor semi-transparente para "Dados (Startups)" (verde Sebrae)
                cor_dados_startups = f"rgba(0, 168, 89, 0.15)"  # Verde Sebrae semi-transparente
                
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
            
            # Configura column_config para coluna de site como LinkColumn
            # IMPORTANTE: Quando usamos column_config, precisamos usar o DataFrame original (df_display),
            # não o styled_df, porque o pandas Styler não funciona bem com column_config
            column_config = {}
            if coluna_site:
                # Usa o nome mapeado da coluna de site
                coluna_site_key = column_name_mapping.get(coluna_site, None)
                if not coluna_site_key or coluna_site_key not in df_display.columns:
                    coluna_site_key = None
                
                if coluna_site_key:
                    # Garante que a coluna seja do tipo string (LinkColumn requer strings)
                    # E que todas as URLs tenham protocolo
                    def garantir_url_valida(url):
                        if pd.isna(url) or str(url).strip() == '' or str(url).strip() in ['nan', 'None', 'NaN']:
                            return ''
                        url_str = str(url).strip()
                        # Garante que a URL tenha protocolo
                        if url_str and not url_str.startswith(('http://', 'https://')):
                            url_str = 'https://' + url_str
                        return url_str
                    
                    df_display[coluna_site_key] = df_display[coluna_site_key].apply(garantir_url_valida).astype(str)
                    
                    # Configura a coluna de site como LinkColumn
                    # Seguindo o exemplo do Streamlit exatamente
                    column_config[coluna_site_key] = st.column_config.LinkColumn(
                        help="Clique para abrir o site em uma nova aba"
                    )
            
            # Se há column_config, usa o DataFrame original ao invés do styled_df
            # porque column_config não funciona corretamente com pandas Styler
            if column_config:
                # IMPORTANTE: column_config não aceita tuplas como chaves (MultiIndex)
                # Precisamos aplanar o MultiIndex antes de aplicar o column_config
                df_para_display = df_display.copy()
                column_config_flat = {}
                
                if is_multiindex:
                    # Aplana o MultiIndex: usa apenas o segundo nível como nome da coluna
                    # Garante que estamos usando apenas os nomes das colunas, não os valores
                    new_columns = []
                    for col in df_para_display.columns:
                        if isinstance(col, tuple) and len(col) == 2:
                            # Usa apenas o segundo nível (nome da coluna)
                            new_columns.append(str(col[1]))
                        elif isinstance(col, tuple):
                            # Se for tupla mas não tiver 2 elementos, usa o último
                            new_columns.append(str(col[-1]))
                        else:
                            # Se não for tupla, usa o valor diretamente (mas garante que é string)
                            new_columns.append(str(col))
                    df_para_display.columns = new_columns
                    # Cria um novo column_config com chaves aplanadas (strings)
                    for old_key, config in column_config.items():
                        if isinstance(old_key, tuple) and len(old_key) == 2:
                            # Usa o segundo nível da tupla como chave (nome da coluna)
                            new_key = str(old_key[1])
                            column_config_flat[new_key] = config
                        else:
                            column_config_flat[str(old_key)] = config
                else:
                    column_config_flat = column_config
                
                # Usa HTML customizado em vez de st.dataframe
                _render_custom_html_table(
                    df_para_display,
                    None,
                    False,
                    categoria_col_for_style if 'categoria_col_for_style' in locals() else None,
                    regiao_col_for_style if 'regiao_col_for_style' in locals() else None,
                    regioes_cores if 'regioes_cores' in locals() else {},
                    coluna_site if 'coluna_site' in locals() else None,
                    format_dict if 'format_dict' in locals() else {}
                )
            else:
                # Sempre aplana o MultiIndex antes de renderizar para evitar problemas de renderização
                if is_multiindex:
                    df_para_display = df_display.copy()
                    new_columns = []
                    col_mapping = {}  # Mapeia colunas antigas para novas
                    for col in df_para_display.columns:
                        if isinstance(col, tuple) and len(col) == 2:
                            new_col_name = str(col[1])
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                        elif isinstance(col, tuple):
                            new_col_name = str(col[-1])
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                        else:
                            new_col_name = str(col)
                            new_columns.append(new_col_name)
                            col_mapping[col] = new_col_name
                    df_para_display.columns = new_columns
                    
                    # Recria o styled_df com as colunas aplanadas, preservando estilos
                    styled_df_flat = df_para_display.style
                    
                    # Aplica estilos de categoria se houver
                    if categoria_col_for_style:
                        categoria_col_flat = col_mapping.get(categoria_col_for_style, None)
                        if categoria_col_flat:
                            def style_categoria_flat(val):
                                if pd.isna(val):
                                    return ''
                                valor_str = str(val).strip()
                                cor = None
                                for categoria_key, categoria_cor in CATEGORIA_COLORS.items():
                                    if categoria_key.lower() in valor_str.lower() or valor_str.lower() in categoria_key.lower():
                                        cor = categoria_cor
                                        break
                                if not cor:
                                    cor = "#6c757d"
                                if cor.startswith('#'):
                                    r = int(cor[1:3], 16)
                                    g = int(cor[3:5], 16)
                                    b = int(cor[5:7], 16)
                                    cor_transparente = f"rgba({r}, {g}, {b}, 0.3)"
                                else:
                                    cor_transparente = cor
                                return f'background-color: {cor_transparente}; border-left: 3px solid {cor}; padding: 4px 8px;'
                            styled_df_flat = styled_df_flat.map(style_categoria_flat, subset=[categoria_col_flat])
                    
                    # Aplica estilos de região se houver
                    if regiao_col_for_style and regioes_cores:
                        regiao_col_flat = col_mapping.get(regiao_col_for_style, None)
                        if regiao_col_flat:
                            def style_regiao_flat(val):
                                if pd.isna(val):
                                    return ''
                                valor_str = str(val).strip()
                                cor_hex = regioes_cores.get(valor_str, "#6c757d")
                                cor_rgba = color_with_intensity(cor_hex, 0.0, min_alpha=0.18)
                                return f'background-color: {cor_rgba}; padding: 4px 8px;'
                            styled_df_flat = styled_df_flat.map(style_regiao_flat, subset=[regiao_col_flat])
                    
                    # Aplica formatação se houver
                    if format_dict:
                        format_dict_flat = {}
                        for old_key, fmt in format_dict.items():
                            new_key = col_mapping.get(old_key, old_key)
                            format_dict_flat[new_key] = fmt
                        if format_dict_flat:
                            styled_df_flat = styled_df_flat.format(format_dict_flat, na_rep='')
                    
                    # Usa HTML customizado em vez de st.dataframe
                    _render_custom_html_table(
                        df_para_display,
                        styled_df_flat,
                        False,
                        categoria_col_flat if 'categoria_col_flat' in locals() else None,
                        regiao_col_flat if 'regiao_col_flat' in locals() else None,
                        regioes_cores if 'regioes_cores' in locals() else {},
                        coluna_site if 'coluna_site' in locals() else None,
                        format_dict_flat if 'format_dict_flat' in locals() else {}
                    )
                else:
                    # Usa HTML customizado em vez de st.dataframe
                    _render_custom_html_table(
                        df_display,
                        styled_df,
                        is_multiindex,
                        categoria_col_for_style if 'categoria_col_for_style' in locals() else None,
                        regiao_col_for_style if 'regiao_col_for_style' in locals() else None,
                        regioes_cores if 'regioes_cores' in locals() else {},
                        coluna_site if 'coluna_site' in locals() else None,
                        format_dict if 'format_dict' in locals() else {}
                    )
    else:
        st.warning("Nenhuma coluna encontrada nos dados.")

def main():
    """
    Função principal do dashboard
    """
    # Carrega dados do mapa (aba "Municípios e Regiões")
    with st.spinner("Carregando dados do mapa..."):
        df_mapa = load_data_municipios_regioes(force_reload=False)
    
    # Carrega dados da tabela (aba "Base | Atores MG")
    with st.spinner("Carregando dados das startups..."):
        df_startups = load_data_base_atores(force_reload=False)
    
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
        # Aplica os mesmos filtros do mapa aos dados das startups
        df_startups_para_tabela = df_startups_filtered.copy()
        
        # DEBUG: Mostra total inicial
        total_inicial = len(df_startups_para_tabela)
        with st.sidebar:
            st.info(f"🔍 DEBUG: Total inicial de registros: {total_inicial}")
        
        # Obtém os valores dos filtros do session_state (definidos no mapa)
        regiao_filtro_tabela = st.session_state.get("filtro_regiao", "Todas")
        municipio_filtro_tabela = st.session_state.get("filtro_municipio", "Todos")
        categorias_filtro_tabela = st.session_state.get("filtro_categoria", [])
        segmentos_filtro_tabela = st.session_state.get("filtro_segmentos", [])
        
        # Aplica filtro de região
        if regiao_filtro_tabela != "Todas":
                # DEBUG: Mostra total antes do filtro de região
                total_antes_regiao = len(df_startups_para_tabela)
                with st.sidebar:
                    st.info(f"🔍 DEBUG: Registros antes do filtro de região: {total_antes_regiao}")
                
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
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_regiao_startups].astype(str).str.strip() == regiao_filtro_tabela
                    ]
                    
                    # DEBUG: Mostra total depois do filtro de região
                    total_depois_regiao = len(df_startups_para_tabela)
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Registros depois do filtro de região: {total_depois_regiao} (perdidos: {total_antes_regiao - total_depois_regiao})")
        
        # Aplica filtro de município
        if municipio_filtro_tabela != "Todos":
                # DEBUG: Mostra total antes do filtro de município
                total_antes_municipio = len(df_startups_para_tabela)
                with st.sidebar:
                    st.info(f"🔍 DEBUG: Registros antes do filtro de município: {total_antes_municipio}")
                
                # Procura coluna de município/cidade nas startups
                coluna_municipio_startups = None
                possiveis_nomes_municipio = ['cidade', 'municipio', 'cidade_max', 'município']
                for col in df_startups_para_tabela.columns:
                    col_lower = col.lower().strip()
                    if any(nome in col_lower for nome in possiveis_nomes_municipio):
                        coluna_municipio_startups = col
                        break
                
                if coluna_municipio_startups:
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_municipio_startups].astype(str).str.strip() == municipio_filtro_tabela
                    ]
                    
                    # DEBUG: Mostra total depois do filtro de município
                    total_depois_municipio = len(df_startups_para_tabela)
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Registros depois do filtro de município: {total_depois_municipio} (perdidos: {total_antes_municipio - total_depois_municipio})")
        
        # Aplica filtro de categoria
        if categorias_filtro_tabela and len(categorias_filtro_tabela) > 0:
                # DEBUG: Mostra total antes do filtro de categoria
                total_antes_categoria = len(df_startups_para_tabela)
                with st.sidebar:
                    st.info(f"🔍 DEBUG: Registros antes do filtro de categoria: {total_antes_categoria}")
                
                # Procura coluna de categoria nas startups
                coluna_categoria_startups = None
                possiveis_nomes_categoria = ['categoria', 'category', 'tipo', 'type', 'tipo_ator', 'actor_type']
                for col in df_startups_para_tabela.columns:
                    col_lower = col.lower().strip()
                    if any(nome == col_lower or nome in col_lower for nome in possiveis_nomes_categoria):
                        coluna_categoria_startups = col
                        break
                
                # DEBUG: Mostra qual coluna foi encontrada
                if coluna_categoria_startups:
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Coluna de categoria encontrada: '{coluna_categoria_startups}'")
                        
                        # DEBUG: Mostra valores únicos na coluna de categoria
                        valores_unicos = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().unique()
                        st.info(f"🔍 DEBUG: Valores únicos na coluna '{coluna_categoria_startups}': {sorted(valores_unicos)[:10]}... (Total: {len(valores_unicos)} valores únicos)")
                        
                        # DEBUG: Mostra quantidade total por categoria ANTES do filtro
                        contagem_por_categoria = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().value_counts()
                        st.info(f"🔍 DEBUG: Quantidade total por categoria ANTES do filtro:")
                        for cat, qtd in contagem_por_categoria.head(15).items():
                            st.text(f"   • {cat}: {qtd}")
                        if len(contagem_por_categoria) > 15:
                            st.text(f"   ... e mais {len(contagem_por_categoria) - 15} categorias")
                        
                        # DEBUG: Mostra categorias que estão sendo filtradas
                        st.info(f"🔍 DEBUG: Categorias filtradas: {categorias_filtro_tabela}")
                
                if coluna_categoria_startups:
                    # Mapeia categorias do filtro do mapa para categorias reais na tabela
                    # Usa busca case-insensitive e parcial para melhor matching
                    # IMPORTANTE: Garante que a máscara tenha o mesmo índice do DataFrame
                    mask = pd.Series([False] * len(df_startups_para_tabela), index=df_startups_para_tabela.index)
                    
                    # Normaliza a coluna de categoria para comparação
                    coluna_categoria_normalizada = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().str.lower()
                    
                    for cat_filtro in categorias_filtro_tabela:
                        cat_filtro_str = str(cat_filtro).strip().lower()
                        
                        # 1. Match exato (case-insensitive) - mais específico primeiro
                        mask |= coluna_categoria_normalizada == cat_filtro_str
                        
                        # 2. Match parcial (contém a string completa) - mais inclusivo
                        mask |= coluna_categoria_normalizada.str.contains(cat_filtro_str, case=False, na=False, regex=False)
                        
                        # 3. Mapeamentos específicos para categorias com nomes diferentes
                        # IMPORTANTE: Usa condições separadas (não elif) para permitir múltiplos matches
                        # Startup
                        if cat_filtro_str == "startup":
                            mask |= coluna_categoria_normalizada.isin(["startup", "startups"])
                        
                        # Empresa Âncora / Grandes Empresas Âncoras
                        # Busca por qualquer combinação que contenha "ancora" (mais inclusivo)
                        if "ancora" in cat_filtro_str or "âncora" in cat_filtro_str or ("empresa" in cat_filtro_str and "grande" in cat_filtro_str):
                            # Busca mais inclusiva: qualquer registro que contenha "ancora" ou "âncora"
                            # Remove acentos para busca mais ampla
                            mask |= coluna_categoria_normalizada.str.contains("ancora", case=False, na=False, regex=False)
                            # Também busca combinação empresa + ancora (mais específico)
                            mask |= (coluna_categoria_normalizada.str.contains("empresa", case=False, na=False, regex=False) & 
                                    coluna_categoria_normalizada.str.contains("ancora", case=False, na=False, regex=False))
                            # Match exato para variações
                            mask |= coluna_categoria_normalizada == "empresa âncora"
                            mask |= coluna_categoria_normalizada == "empresa ancora"
                            mask |= coluna_categoria_normalizada == "grande empresa âncora"
                            mask |= coluna_categoria_normalizada == "grande empresa ancora"
                            mask |= coluna_categoria_normalizada == "grandes empresas âncoras"
                            mask |= coluna_categoria_normalizada == "grandes empresas ancora"
                            mask |= coluna_categoria_normalizada == "grandes empresas ancoras"
                            mask |= coluna_categoria_normalizada == "empresas âncoras"
                            mask |= coluna_categoria_normalizada == "empresas ancoras"
                        
                        # Empresa Estatal
                        if "empresa" in cat_filtro_str and "estatal" in cat_filtro_str:
                            mask |= coluna_categoria_normalizada.str.contains("empresa", case=False, na=False, regex=False) & \
                                   coluna_categoria_normalizada.str.contains("estatal", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada == "empresa estatal"
                        
                        # Fundos e Investidores - busca mais inclusiva
                        if "fundos" in cat_filtro_str or "investidor" in cat_filtro_str or "fundo" in cat_filtro_str:
                            # Busca por qualquer variação de "fundo" ou "investidor" (mais inclusivo)
                            # Se contém "fundo" OU "investidor", captura
                            mask |= coluna_categoria_normalizada.str.contains("fundo", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("fundos", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("investidor", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("investidores", case=False, na=False, regex=False)
                            # Também verifica se começa com essas palavras
                            mask |= coluna_categoria_normalizada.str.startswith("fundo", na=False)
                            mask |= coluna_categoria_normalizada.str.startswith("investidor", na=False)
                            # Match exato para variações
                            mask |= coluna_categoria_normalizada == "fundos e investidores"
                            mask |= coluna_categoria_normalizada == "fundo e investidor"
                            mask |= coluna_categoria_normalizada == "fundos e investidor"
                            mask |= coluna_categoria_normalizada == "fundo e investidores"
                        
                        # Universidades e ICTs - busca mais inclusiva
                        if "universidade" in cat_filtro_str or "ict" in cat_filtro_str:
                            # Captura qualquer registro que tenha "universidade" OU "ict"
                            mask |= coluna_categoria_normalizada.str.contains("universidade", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("ict", case=False, na=False, regex=False)
                            # Match exato para variações
                            mask |= coluna_categoria_normalizada == "ict"
                            mask |= coluna_categoria_normalizada == "universidade"
                            mask |= coluna_categoria_normalizada == "universidade/ict"
                            mask |= coluna_categoria_normalizada == "universidade / ict"
                            mask |= coluna_categoria_normalizada == "universidades e icts"
                            mask |= coluna_categoria_normalizada == "universidades e ict"
                            mask |= coluna_categoria_normalizada == "universidades e icts"
                            # Busca por qualquer combinação
                            mask |= (coluna_categoria_normalizada.str.contains("universidade", case=False, na=False, regex=False) |
                                    coluna_categoria_normalizada.str.contains("ict", case=False, na=False, regex=False))
                        
                        # Órgãos Públicos e Apoio - busca mais inclusiva
                        if "órgão" in cat_filtro_str or "orgao" in cat_filtro_str or "apoio" in cat_filtro_str or "publico" in cat_filtro_str:
                            # Captura qualquer registro que tenha "orgao" OU "publico" OU "apoio"
                            # Mais inclusivo: se tem qualquer um desses termos, captura
                            mask |= coluna_categoria_normalizada.str.contains("orgao", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("publico", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("apoio", case=False, na=False, regex=False)
                            # Match exato para variações
                            mask |= coluna_categoria_normalizada == "órgão público"
                            mask |= coluna_categoria_normalizada == "orgao publico"
                            mask |= coluna_categoria_normalizada == "órgão de apoio"
                            mask |= coluna_categoria_normalizada == "orgao de apoio"
                            mask |= coluna_categoria_normalizada == "órgãos públicos e apoio"
                            mask |= coluna_categoria_normalizada == "orgaos publicos e apoio"
                            mask |= coluna_categoria_normalizada == "órgãos públicos"
                            mask |= coluna_categoria_normalizada == "orgaos publicos"
                            # Busca mais ampla: qualquer combinação
                            mask |= (coluna_categoria_normalizada.str.contains("orgao", case=False, na=False, regex=False) |
                                    coluna_categoria_normalizada.str.contains("publico", case=False, na=False, regex=False) |
                                    coluna_categoria_normalizada.str.contains("apoio", case=False, na=False, regex=False))
                        
                        # Hubs, Incubadoras e Parques Tecnológicos
                        if "hub" in cat_filtro_str or "incubadora" in cat_filtro_str or "parque" in cat_filtro_str or "tecnologico" in cat_filtro_str:
                            # Busca mais inclusiva: qualquer uma dessas palavras
                            mask |= coluna_categoria_normalizada.str.contains("hub", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("incubadora", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("parque", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("tecnologico", case=False, na=False, regex=False)
                            # Match exato para a categoria completa
                            mask |= coluna_categoria_normalizada == "hubs, incubadoras e parques tecnologicos"
                            mask |= coluna_categoria_normalizada == "hubs, incubadoras e parques tecnológicos"
                            mask |= coluna_categoria_normalizada == "hubs incubadoras e parques tecnologicos"
                            # Busca por "aceleradora" também (pode estar incluída)
                            mask |= coluna_categoria_normalizada.str.contains("aceleradora", case=False, na=False, regex=False)
                        
                        # Aceleradora (categoria específica na planilha)
                        if "aceleradora" in cat_filtro_str:
                            mask |= coluna_categoria_normalizada == "aceleradora"
                            mask |= coluna_categoria_normalizada.str.contains("aceleradora", case=False, na=False, regex=False)
                        
                        # Ecossistema (categoria específica na planilha - pode incluir hubs, incubadoras, etc)
                        if "ecossistema" in cat_filtro_str:
                            mask |= coluna_categoria_normalizada == "ecossistema"
                            mask |= coluna_categoria_normalizada.str.contains("ecossistema", case=False, na=False, regex=False)
                            # Ecossistema pode incluir hubs, então também busca por essas palavras
                            mask |= coluna_categoria_normalizada.str.contains("hub", case=False, na=False, regex=False)
                            mask |= coluna_categoria_normalizada.str.contains("incubadora", case=False, na=False, regex=False)
                    
                    # DEBUG: Mostra quantos registros foram encontrados pela máscara
                    total_encontrados_mask = mask.sum()
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Registros encontrados pela máscara: {total_encontrados_mask}")
                        
                        # DEBUG: Mostra TODOS os valores únicos na coluna ANTES do filtro (para diagnóstico)
                        if coluna_categoria_startups in df_startups_para_tabela.columns:
                            todos_valores_unicos = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().unique()
                            st.info(f"🔍 DEBUG: TODOS os valores únicos na coluna '{coluna_categoria_startups}':")
                            for val in sorted(todos_valores_unicos)[:30]:
                                st.text(f"   • '{val}'")
                            if len(todos_valores_unicos) > 30:
                                st.text(f"   ... e mais {len(todos_valores_unicos) - 30} valores")
                        
                        # DEBUG: Mostra quais valores na coluna correspondem às categorias filtradas
                        if total_encontrados_mask > 0 and coluna_categoria_startups in df_startups_para_tabela.columns:
                            try:
                                # Garante que a máscara está alinhada com o índice do DataFrame
                                df_filtrado_debug = df_startups_para_tabela.loc[mask]
                                if coluna_categoria_startups in df_filtrado_debug.columns:
                                    valores_encontrados = df_filtrado_debug[coluna_categoria_startups].astype(str).str.strip().value_counts()
                                    st.info(f"🔍 DEBUG: Valores encontrados na coluna que correspondem ao filtro:")
                                    for valor, qtd in valores_encontrados.head(20).items():
                                        st.text(f"   • '{valor}': {qtd}")
                                    if len(valores_encontrados) > 20:
                                        st.text(f"   ... e mais {len(valores_encontrados) - 20} valores")
                            except Exception as e:
                                # Se houver erro no debug, apenas ignora (não quebra o app)
                                pass
                        elif total_encontrados_mask == 0:
                            st.warning(f"⚠️ DEBUG: Nenhum registro encontrado! Verifique se os nomes das categorias no filtro correspondem aos valores na coluna '{coluna_categoria_startups}'")
                    
                    # Aplica o filtro - usa .loc para garantir alinhamento correto do índice
                    df_startups_para_tabela = df_startups_para_tabela.loc[mask].copy()
                    
                    # DEBUG: Mostra total depois do filtro de categoria
                    total_depois_categoria = len(df_startups_para_tabela)
                    perdidos_categoria = total_antes_categoria - total_depois_categoria
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Registros depois do filtro de categoria: {total_depois_categoria} (perdidos: {perdidos_categoria})")
                        
                        # DEBUG: Mostra quantidade total por categoria DEPOIS do filtro
                        if total_depois_categoria > 0:
                            contagem_por_categoria_depois = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().value_counts()
                            st.info(f"🔍 DEBUG: Quantidade total por categoria DEPOIS do filtro:")
                            for cat, qtd in contagem_por_categoria_depois.head(15).items():
                                st.text(f"   • {cat}: {qtd}")
                            if len(contagem_por_categoria_depois) > 15:
                                st.text(f"   ... e mais {len(contagem_por_categoria_depois) - 15} categorias")
                    
                    # DEBUG: Se não encontrou registros, mostra mais detalhes
                    if total_depois_categoria == 0 and total_antes_categoria > 0:
                        with st.sidebar:
                            st.warning(f"⚠️ DEBUG: Nenhum registro encontrado! Verificando valores normalizados...")
                            # Mostra valores únicos normalizados da coluna de categoria
                            valores_unicos_normalizados = df_startups_filtered[coluna_categoria_startups].astype(str).str.strip().str.lower().unique() if coluna_categoria_startups in df_startups_filtered.columns else []
                            st.info(f"🔍 DEBUG: Valores normalizados (lowercase) na coluna: {sorted(valores_unicos_normalizados)[:20]}")
                            st.info(f"🔍 DEBUG: Categorias filtradas (normalizadas): {[str(c).strip().lower() for c in categorias_filtro_tabela]}")
                            
                            # Testa matching manual para cada categoria
                            for cat_filtro in categorias_filtro_tabela:
                                cat_filtro_str = str(cat_filtro).strip().lower()
                                coluna_normalizada = df_startups_filtered[coluna_categoria_startups].astype(str).str.strip().str.lower()
                                
                                # Testa match exato
                                matches_exato = coluna_normalizada == cat_filtro_str
                                total_matches_exato = matches_exato.sum()
                                st.info(f"🔍 DEBUG: '{cat_filtro}' -> {total_matches_exato} matches (exato)")
                                
                                # Testa contains
                                matches = coluna_normalizada.str.contains(cat_filtro_str, case=False, na=False, regex=False)
                                total_matches = matches.sum()
                                st.info(f"🔍 DEBUG: '{cat_filtro}' -> {total_matches} matches (contains)")
                                
                                # Mostra quais valores na coluna contêm essa categoria
                                valores_com_match = df_startups_filtered[coluna_categoria_startups][matches].astype(str).str.strip().value_counts()
                                if len(valores_com_match) > 0:
                                    st.info(f"🔍 DEBUG: Valores encontrados para '{cat_filtro}':")
                                    for valor, qtd in valores_com_match.head(10).items():
                                        st.text(f"   • '{valor}': {qtd}")
                                    if len(valores_com_match) > 10:
                                        st.text(f"   ... e mais {len(valores_com_match) - 10} valores")
                else:
                    with st.sidebar:
                        st.warning(f"⚠️ DEBUG: Coluna de categoria não encontrada! Colunas disponíveis: {list(df_startups_para_tabela.columns)[:10]}")
        
        # DEBUG: Mostra total antes do filtro de segmentos
        total_antes_segmentos = len(df_startups_para_tabela)
        if segmentos_filtro_tabela and len(segmentos_filtro_tabela) > 0:
            st.sidebar.info(f"🔍 DEBUG: Registros antes do filtro de segmentos: {total_antes_segmentos}")
        
        # Aplica filtro de segmentos (apenas para startups)
        if segmentos_filtro_tabela and len(segmentos_filtro_tabela) > 0:
            # Procura coluna de setor/segmento nas startups
            coluna_setor_startups = None
            possiveis_nomes_setor = ['setor', 'sector', 'segmento', 'segment', 'segmentos', 'setores']
            for col in df_startups_para_tabela.columns:
                col_lower = str(col).lower().strip()
                if any(nome in col_lower for nome in possiveis_nomes_setor):
                    coluna_setor_startups = col
                    break
            
            if coluna_setor_startups:
                # Procura coluna de categoria para filtrar apenas startups
                coluna_categoria_startups = None
                possiveis_nomes_categoria = ['categoria', 'category', 'tipo', 'type', 'tipo_ator', 'actor_type']
                for col in df_startups_para_tabela.columns:
                    col_lower = str(col).lower().strip()
                    if any(nome == col_lower or nome in col_lower for nome in possiveis_nomes_categoria):
                        coluna_categoria_startups = col
                        break
                
                if coluna_categoria_startups:
                    # Separa startups e outros atores
                    mask_startup = df_startups_para_tabela[coluna_categoria_startups].astype(str).str.strip().str.lower() == 'startup'
                    df_startups_filtrado = df_startups_para_tabela[mask_startup].copy()
                    df_outros_atores = df_startups_para_tabela[~mask_startup].copy()
                    
                    # Aplica filtro de segmentos apenas nas startups
                    df_startups_filtrado = df_startups_filtrado[
                        df_startups_filtrado[coluna_setor_startups].astype(str).str.strip().isin(
                            [str(seg).strip() for seg in segmentos_filtro_tabela]
                        )
                    ]
                    
                    # Combina startups filtradas com outros atores (não afetados)
                    df_startups_para_tabela = pd.concat([df_startups_filtrado, df_outros_atores], ignore_index=True)
                    
                    # DEBUG: Mostra total depois do filtro de segmentos
                    total_depois_segmentos = len(df_startups_para_tabela)
                    perdidos_segmentos = total_antes_segmentos - total_depois_segmentos
                    with st.sidebar:
                        st.info(f"🔍 DEBUG: Registros depois do filtro de segmentos: {total_depois_segmentos} (perdidos: {perdidos_segmentos})")
                else:
                    # Se não encontrou coluna de categoria, aplica filtro em todos (menos ideal)
                    df_startups_para_tabela = df_startups_para_tabela[
                        df_startups_para_tabela[coluna_setor_startups].astype(str).str.strip().isin(
                            [str(seg).strip() for seg in segmentos_filtro_tabela]
                        )
                    ]
        
        # Campo de pesquisa (fora do bloco if/else para funcionar em ambos os casos)
        texto_pesquisa = st.text_input(
            "🔍 Pesquisar por nome",
            value="",
            placeholder="Digite o nome do ator...",
            key="campo_pesquisa_tabela"
        )
        
        # Filtra os dados baseado na pesquisa
        df_tabela_filtrado = df_startups_para_tabela.copy()
        
        # DEBUG: Mostra total antes do filtro de texto
        total_antes_texto = len(df_tabela_filtrado)
        if texto_pesquisa and texto_pesquisa.strip():
            with st.sidebar:
                st.info(f"🔍 DEBUG: Registros antes do filtro de texto: {total_antes_texto}")
        
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
                
                # DEBUG: Mostra total depois do filtro de texto
                total_depois_texto = len(df_tabela_filtrado)
                perdidos_texto = total_antes_texto - total_depois_texto
                with st.sidebar:
                    st.info(f"🔍 DEBUG: Registros depois do filtro de texto: {total_depois_texto} (perdidos: {perdidos_texto})")
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
                
                # DEBUG: Mostra total depois do filtro de texto
                total_depois_texto = len(df_tabela_filtrado)
                perdidos_texto = total_antes_texto - total_depois_texto
                with st.sidebar:
                    st.info(f"🔍 DEBUG: Registros depois do filtro de texto: {total_depois_texto} (perdidos: {perdidos_texto})")
        
        # DEBUG: Mostra total final e compara com o esperado
        total_final = len(df_tabela_filtrado)
        total_esperado = 5140
        diferenca = total_esperado - total_final
        with st.sidebar:
            if diferenca > 0:
                st.warning(f"⚠️ DEBUG: Total final: {total_final} (esperado: {total_esperado}, faltam: {diferenca})")
            else:
                st.success(f"✅ DEBUG: Total final de registros na tabela: {total_final}")
        
        # Tabela de dados (usa dados filtrados)
        create_data_table(df_tabela_filtrado)
    
    
    # Footer

if __name__ == "__main__":
    main()
