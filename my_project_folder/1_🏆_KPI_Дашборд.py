import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="KPI Дашборд", layout="wide")

# 👇 Вставьте вашу ссылку на таблицу
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvNrboP0eML1Mc3lk2WJ2Oze0kA5RT8pakzgjETh_eM/edit?gid=1885685439#gid=1885685439"

# ==========================================
# 📥 ЗАГРУЗКА ДАННЫХ
# ==========================================
@st.cache_data(ttl=600)
def load_kpi_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Авторизация
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["type"] = "service_account"
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Открываем вкладку "Общие параметры"
        sheet = client.open_by_url(SHEET_URL).worksheet("Общие параметры")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame()

def clean_money(x):
    if isinstance(x, str):
        # Убираем пробелы, знаки валют и меняем запятую на точку
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x if isinstance(x, (int, float)) else 0.0

# ==========================================
# 📊 ИНТЕРФЕЙС
# ==========================================
st.title("🏆 KPI Монитор: План vs Факт")

df_raw = load_kpi_data()

if df_raw.empty:
    st.warning("Данные не загружены. Проверьте доступ к таблице.")
    st.stop()

# 1. ОЧИСТКА И ПОДГОТОВКА КОЛОНОК
# Убираем пробелы в названиях колонок (чтобы найти "Выручка факт", а не "Выручка факт ")
df_raw.columns = [c.strip() for c in df_raw.columns]

# Убираем строку "Итого", если она есть в менеджерах (посчитаем сами)
df = df_raw[df_raw["Менеджер"] != "Итого"].copy()

# Список нужных нам колонок (как в вашей таблице)
col_plan_rev = "План по выручке"
col_fact_rev = "Выручка факт"
col_plan_marg = "План по маржинальной прибыли"
col_fact_marg = "Маржинальная прибыль факт"

# Превращаем текст в числа
cols_to_clean = [col_plan_rev, col_fact_rev, col_plan_marg, col_fact_marg]

for col in cols_to_clean:
    if col in df.columns:
        df[col] = df[col].apply(clean_money)
    else:
        # Если колонки нет (например, Факта еще нет), создаем пустую
        df[col] = 0.0

# ==========================================
# 📈 ГЛОБАЛЬНЫЕ МЕТРИКИ (Сверху)
# ==========================================
st.subheader("Общие показатели компании")

# Считаем суммы
total_plan_rev = df[col_plan_rev].sum()
total_fact_rev = df[col_fact_rev].sum()
delta_rev = total_fact_rev - total_plan_rev
perc_rev = (total_fact_rev / total_plan_rev * 100) if total_plan_rev > 0 else 0

total_plan_marg = df[col_plan_marg].sum()
total_fact_marg = df[col_fact_marg].sum()
delta_marg = total_fact_marg - total_plan_marg
perc_marg = (total_fact_marg / total_plan_marg * 100) if total_plan_marg > 0 else 0

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.metric(
        label="💰 Выручка (Факт / План)",
        value=f"${total_fact_rev:,.0f}".replace(",", " "),
        delta=f"{delta_rev:,.0f} ({perc_rev:.1f}%)",
        delta_color="normal" # Зеленый если плюс, красный если минус
    )

with kpi2:
    st.metric(
        label="📈 Маржа (Факт / План)",
        value=f"${total_fact_marg:,.0f}".replace(",", " "),
        delta=f"{delta_marg:,.0f} ({perc_marg:.1f}%)",
        delta_color="normal"
    )

with kpi3:
    # Пример простой метрики эффективности (Маржа / Выручка факт)
    margin_percent = (total_fact_marg / total_fact_rev * 100) if total_fact_rev > 0 else 0
    st.metric(
        label="Рентабельность (по факту)",
        value=f"{margin_percent:.1f}%",
        help="Отношение фактической маржи к фактической выручке"
    )

st.divider()

# ==========================================
# 📊 ГРАФИКИ ПО МЕНЕДЖЕРАМ
# ==========================================

tab1, tab2 = st.tabs(["📊 Анализ Выручки", "📉 Анализ Маржи"])

# --- ВКЛАДКА 1: ВЫРУЧКА ---
with tab1:
    st.subheader("Выполнение плана по Выручке")
    
    # Готовим данные для графика (превращаем в длинный формат)
    df_rev_chart = df[["Менеджер", col_plan_rev, col_fact_rev]].melt(
        id_vars="Менеджер", 
        var_name="Тип", 
        value_name="Сумма"
    )
    
    # Красивые названия для легенды
    df_rev_chart["Тип"] = df_rev_chart["Тип"].replace({
        col_plan_rev: "План",
        col_fact_rev: "Факт"
    })

    fig_rev = px.bar(
        df_rev_chart, 
        x="Менеджер", 
        y="Сумма", 
        color="Тип", 
        barmode="group", # Столбики рядом
        text_auto='.2s', # Сокращенные цифры (1M, 500k)
        color_discrete_map={"План": "#A7C7E7", "Факт": "#228B22"}, # Синий план, Зеленый факт
        height=500
    )
    st.plotly_chart(fig_rev, use_container_width=True)

# --- ВКЛАДКА 2: МАРЖА ---
with tab2:
    st.subheader("Выполнение плана по Марже")
    
    df_marg_chart = df[["Менеджер", col_plan_marg, col_fact_marg]].melt(
        id_vars="Менеджер", 
        var_name="Тип", 
        value_name="Сумма"
    )
    
    df_marg_chart["Тип"] = df_marg_chart["Тип"].replace({
        col_plan_marg: "План",
        col_fact_marg: "Факт"
    })

    fig_marg = px.bar(
        df_marg_chart, 
        x="Менеджер", 
        y="Сумма", 
        color="Тип", 
        barmode="group",
        text_auto='.2s',
        color_discrete_map={"План": "#FFB347", "Факт": "#FF4500"}, # Оранжевый план, Красный факт (для разнообразия)
        height=500
    )
    st.plotly_chart(fig_marg, use_container_width=True)

# ==========================================
# 📋 ДЕТАЛЬНАЯ ТАБЛИЦА
# ==========================================
st.subheader("Детальные данные")

# Считаем % выполнения для таблицы
df["% Выручки"] = (df[col_fact_rev] / df[col_plan_rev] * 100).fillna(0)
df["% Маржи"] = (df[col_fact_marg] / df[col_plan_marg] * 100).fillna(0)

# Функция раскраски для таблицы
def highlight_kpi(val):
    if val >= 100: return 'color: green; font-weight: bold'
    elif val < 80: return 'color: red'
    return 'color: orange'

# Показываем красивую таблицу
st.dataframe(
    df[["Менеджер", col_plan_rev, col_fact_rev, "% Выручки", col_plan_marg, col_fact_marg, "% Маржи"]]
    .style
    .format({
        col_plan_rev: "{:,.0f}", 
        col_fact_rev: "{:,.0f}", 
        col_plan_marg: "{:,.0f}", 
        col_fact_marg: "{:,.0f}",
        "% Выручки": "{:.1f}%",
        "% Маржи": "{:.1f}%"
    })
    .map(highlight_kpi, subset=["% Выручки", "% Маржи"]),
    use_container_width=True,
    hide_index=True
)
