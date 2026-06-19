
import io
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="SmartStock Analytics",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #111827 100%);
    color: #f8fafc;
}
.block-container {
    padding-top: 1rem;
}
[data-testid="stSidebar"] {
    background-color: #020617;
    border-right: 1px solid #1e293b;
}
.main-title {
    font-size: 42px;
    font-weight: 900;
    color: #f8fafc;
    margin-bottom: 0;
}
.subtitle {
    color: #94a3b8;
    font-size: 17px;
    margin-bottom: 24px;
}
.card {
    background: rgba(30, 41, 59, 0.92);
    padding: 20px;
    border-radius: 18px;
    border: 1px solid rgba(148, 163, 184, 0.18);
    box-shadow: 0 10px 30px rgba(0,0,0,.22);
}
.card-title {
    color: #94a3b8;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
}
.card-value {
    color: #f8fafc;
    font-size: 30px;
    font-weight: 900;
}
.insight {
    background: rgba(15, 23, 42, .9);
    border-left: 5px solid #38bdf8;
    padding: 14px 18px;
    border-radius: 12px;
    margin-bottom: 10px;
    color: #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


def parse_date(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, (datetime, pd.Timestamp)):
        dt = pd.to_datetime(value, errors="coerce")
    else:
        text = str(value).strip()
        if text.upper() == "DATA":
            return pd.NaT

        # Corrige casos de ano digitado com 5 números, exemplo: 28/01/20262
        parts = text.split("/")
        if len(parts) == 3 and len(parts[2]) > 4:
            text = f"{parts[0]}/{parts[1]}/{parts[2][:4]}"

        dt = pd.to_datetime(text, dayfirst=True, errors="coerce")

    if pd.isna(dt):
        return pd.NaT

    # Correção específica para erro de digitação da base:
    # o histórico real começa em dez/2025; datas em jan/2025 são tratadas como jan/2026.
    if dt.year == 2025 and dt.month < 12:
        dt = dt + pd.DateOffset(years=1)

    return dt


@st.cache_data
def load_data(file):
    raw = pd.read_excel(file, header=None)

    current_store = None
    header = None
    records = []

    for _, row in raw.iterrows():
        first = row.iloc[0]

        if pd.isna(first):
            continue

        first_text = str(first).strip()

        if first_text.upper() == "DATA":
            header = [str(x).strip() for x in row.tolist()]
            continue

        parsed = parse_date(first)

        if pd.isna(parsed):
            current_store = first_text
            continue

        if header is None:
            continue

        values = row.tolist()
        item = {"Loja": current_store if current_store else "Não informada", "DATA": parsed}

        for idx in range(1, min(len(header), len(values))):
            product_name = str(header[idx]).strip()

            if product_name == "" or product_name.lower().startswith("unnamed") or product_name.lower() == "nan":
                continue

            item[product_name] = values[idx]

        records.append(item)

    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError("Não foi possível ler dados válidos da planilha.")

    date_col = "DATA"
    fixed_cols = ["Loja", date_col]
    products = [c for c in df.columns if c not in fixed_cols]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    # Mantém o intervalo real do histórico usado no projeto
    df = df[(df[date_col] >= "2025-12-01") & (df[date_col] <= "2026-12-31")]

    for product in products:
        df[product] = pd.to_numeric(df[product], errors="coerce").fillna(0)

    df = df.sort_values(["Loja", date_col])

    return df, date_col, products


def format_number(value):
    try:
        return f"{int(round(value, 0)):,}".replace(",", ".")
    except Exception:
        return value


def metric_card(title, value):
    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">{title}</div>
            <div class="card-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def trend_label(series):
    s = series.dropna().astype(float)
    if len(s) < 3:
        return "Estável"
    x = np.arange(len(s))
    slope = np.polyfit(x, s.values, 1)[0]
    mean = s.mean() if s.mean() != 0 else 1
    rel = slope / mean
    if rel > 0.01:
        return "Crescimento"
    if rel < -0.01:
        return "Queda"
    return "Estável"


def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados_filtrados")
    return output.getvalue()


st.markdown('<div class="main-title">SmartStock Analytics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Dashboard para análise estatística, análise de dados e gestão da informação.</div>',
    unsafe_allow_html=True
)

uploaded = st.sidebar.file_uploader("Enviar planilha anonimizada", type=["xlsx", "xls"])

if uploaded is not None:
    df_original, date_col, products = load_data(uploaded)
else:
    try:
        df_original, date_col, products = load_data("data/estoque_anonimizado.xlsx")
        st.sidebar.success("Planilha padrão carregada.")
    except Exception:
        st.info("Envie a planilha anonimizada para iniciar o dashboard.")
        st.stop()

st.sidebar.header("Filtros")

stores = sorted(df_original["Loja"].dropna().unique().tolist())
selected_stores = st.sidebar.multiselect(
    "Lojas",
    stores,
    default=stores
)

df_store = df_original[df_original["Loja"].isin(selected_stores)].copy()

min_date = df_store[date_col].min().date()
max_date = df_store[date_col].max().date()

start_date = st.sidebar.date_input(
    "Data inicial",
    value=min_date,
    min_value=min_date,
    max_value=max_date
)

end_date = st.sidebar.date_input(
    "Data final",
    value=max_date,
    min_value=min_date,
    max_value=max_date
)

if start_date > end_date:
    st.sidebar.error("A data inicial não pode ser maior que a data final.")
    st.stop()

selected_products = st.sidebar.multiselect(
    "Produtos",
    products,
    default=products[:min(5, len(products))]
)

top_n = st.sidebar.slider("Quantidade de itens no ranking", 5, min(20, len(products)), min(10, len(products)))

df = df_store[
    (df_store[date_col].dt.date >= start_date) &
    (df_store[date_col].dt.date <= end_date)
].copy()

if df.empty:
    st.warning("Não há dados no período selecionado.")
    st.stop()

if not selected_products:
    selected_products = products[:min(5, len(products))]

# Agrega por data para evitar linhas duplicadas de várias lojas no gráfico temporal
df_by_date = df.groupby(date_col, as_index=False)[products].sum()

long_all = df.melt(
    id_vars=["Loja", date_col],
    value_vars=products,
    var_name="Produto",
    value_name="Unidades"
)

long_selected_by_date = df_by_date.melt(
    id_vars=date_col,
    value_vars=selected_products,
    var_name="Produto",
    value_name="Unidades"
)

ranking = df[products].sum().sort_values(ascending=False)
best_product = ranking.index[0]
worst_product = ranking.index[-1]
total_units = df[products].sum().sum()
general_mean = df[products].stack().mean()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Visão Geral",
    "Análise Temporal",
    "Estatística",
    "Mapa de Calor",
    "Dados"
])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Produtos monitorados", len(products))
    with c2:
        metric_card("Registros analisados", len(df))
    with c3:
        metric_card("Total de unidades", format_number(total_units))
    with c4:
        metric_card("Média geral", round(general_mean, 2))

    c5, c6 = st.columns(2)
    with c5:
        metric_card("Produto destaque", best_product)
    with c6:
        metric_card("Menor movimentação", worst_product)

    st.markdown("### Insights Gerenciais")

    media_produtos = ranking.mean()
    produto_acima_media = ranking[ranking > media_produtos].count()

    st.markdown(f'<div class="insight">O produto com maior volume no período foi <b>{best_product}</b>, com <b>{format_number(ranking.iloc[0])}</b> unidades.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight">O produto com menor volume no período foi <b>{worst_product}</b>, com <b>{format_number(ranking.iloc[-1])}</b> unidades.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight">{produto_acima_media} produtos ficaram acima da média geral de movimentação por produto.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("### Ranking de Produtos")
        rank_df = ranking.reset_index()
        rank_df.columns = ["Produto", "Total"]
        fig_rank = px.bar(
            rank_df.head(top_n).sort_values("Total"),
            x="Total",
            y="Produto",
            orientation="h",
            title=f"Top {top_n} produtos por unidades"
        )
        fig_rank.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#1e293b",
            height=460
        )
        st.plotly_chart(fig_rank, use_container_width=True)

    with col2:
        st.markdown("### Participação por Produto")
        fig_tree = px.treemap(
            rank_df,
            path=["Produto"],
            values="Total",
            title="Participação no total de unidades"
        )
        fig_tree.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            height=460
        )
        st.plotly_chart(fig_tree, use_container_width=True)

with tab2:
    st.markdown("### Evolução Temporal dos Produtos")
    fig_line = px.line(
        long_selected_by_date,
        x=date_col,
        y="Unidades",
        color="Produto",
        markers=True,
        title="Evolução das unidades ao longo do tempo"
    )
    fig_line.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#1e293b",
        height=520,
        xaxis_title="Data",
        yaxis_title="Unidades"
    )
    fig_line.update_xaxes(type="date", tickformat="%d/%m/%Y")
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("### Variação Acumulada por Data")
    total_by_date = long_selected_by_date.groupby(date_col, as_index=False)["Unidades"].sum()
    fig_area = px.area(
        total_by_date,
        x=date_col,
        y="Unidades",
        title="Volume total dos produtos selecionados por período"
    )
    fig_area.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#1e293b",
        height=420,
        xaxis_title="Data",
        yaxis_title="Unidades"
    )
    fig_area.update_xaxes(type="date", tickformat="%d/%m/%Y")
    st.plotly_chart(fig_area, use_container_width=True)

with tab3:
    st.markdown("### Estatística Aplicada")

    stats_rows = []
    for p in products:
        s = df[p].astype(float)
        moda = s.mode()
        stats_rows.append({
            "Produto": p,
            "Total": round(s.sum(), 2),
            "Média": round(s.mean(), 2),
            "Mediana": round(s.median(), 2),
            "Moda": moda.iloc[0] if not moda.empty else 0,
            "Desvio Padrão": round(s.std(), 2),
            "Variância": round(s.var(), 2),
            "Mínimo": s.min(),
            "Máximo": s.max(),
            "Amplitude": s.max() - s.min(),
            "Percentil 25": round(s.quantile(0.25), 2),
            "Percentil 75": round(s.quantile(0.75), 2),
            "Tendência": trend_label(s)
        })

    stats_df = pd.DataFrame(stats_rows)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Boxplot")
        fig_box = px.box(
            long_all[long_all["Produto"].isin(selected_products)],
            x="Produto",
            y="Unidades",
            points="outliers",
            title="Distribuição dos produtos selecionados"
        )
        fig_box.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#1e293b",
            height=430
        )
        st.plotly_chart(fig_box, use_container_width=True)

    with col2:
        st.markdown("### Histograma")
        fig_hist = px.histogram(
            long_all[long_all["Produto"].isin(selected_products)],
            x="Unidades",
            color="Produto",
            nbins=25,
            title="Frequência das unidades"
        )
        fig_hist.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#1e293b",
            height=430
        )
        st.plotly_chart(fig_hist, use_container_width=True)

with tab4:
    st.markdown("### Mapa de Calor")
    heat = df_by_date[[date_col] + selected_products].copy()
    heat[date_col] = heat[date_col].dt.strftime("%d/%m/%Y")
    heat = heat.set_index(date_col).T

    fig_heat = go.Figure(data=go.Heatmap(
        z=heat.values,
        x=heat.columns,
        y=heat.index,
        colorscale="Viridis",
        colorbar=dict(title="Unidades")
    ))
    fig_heat.update_layout(
        template="plotly_dark",
        title="Mapa de calor por produto e período",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#1e293b",
        height=580
    )
    st.plotly_chart(fig_heat, use_container_width=True)

with tab5:
    st.markdown("### Dados Filtrados")

    search = st.text_input("Pesquisar produto")
    table_df = long_all.copy()

    if search:
        table_df = table_df[table_df["Produto"].str.contains(search, case=False, na=False)]

    table_df = table_df.sort_values(["Loja", date_col])
    table_df[date_col] = table_df[date_col].dt.strftime("%d/%m/%Y")

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Baixar CSV",
            table_df.to_csv(index=False).encode("utf-8-sig"),
            "smartstock_dados_filtrados.csv",
            "text/csv"
        )
    with col2:
        st.download_button(
            "Baixar Excel",
            to_excel_bytes(table_df),
            "smartstock_dados_filtrados.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.markdown("---")
st.caption("Projeto acadêmico e de portfólio desenvolvido com Python, Streamlit, Pandas e Plotly.")
