import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="KPI Дашборд", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvNrboP0eML1Mc3lk2WJ2Oze0kA5RT8pakzgjETh_eM/edit?gid=1885685439#gid=1885685439" # <-- ПРОВЕРЬТЕ ССЫЛКУ

# --- ФУНКЦИЯ ЗАГРУЗКИ ---
@st.cache_data(ttl=600)
def load_kpi_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["type"] = "service_account"
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    try:
        # Открываем вкладку "Общие параметры"
        sheet = client.open_by_url(SHEET_URL).worksheet("Общие параметры")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return pd.DataFrame()

def clean_money(x):
    if isinstance(x, str):
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x

# --- ИНТЕРФЕЙС ---
st.title("🏆 Главная: KPI и Планы")

df = load_kpi_data()

if df.empty:
    st.warning("Данные не загружены.")
    st.stop()

# Чистим данные (Колонки из вашего скрина)
# Убираем пробелы в названиях колонок на всякий случай
df.columns = [c.strip() for c in df.columns]

if "План по выручке" in df.columns:
    df["План по выручке"] = df["План по выручке"].apply(clean_money)
if "План по маржинальной прибыли" in df.columns:
    df["План по маржинальной прибыли"] = df["План по маржинальной прибыли"].apply(clean_money)

# Удаляем строку "Итого", если она есть (чтобы не портить графики)
df_clean = df[df["Менеджер"] != "Итого"].copy()

# МЕТРИКИ (Суммируем планы)
total_revenue_plan = df_clean["План по выручке"].sum()
total_margin_plan = df_clean["План по маржинальной прибыли"].sum()

col1, col2 = st.columns(2)
col1.metric("🎯 Общий План по Выручке", f"{total_revenue_plan:,.0f}".replace(",", " "))
col2.metric("💰 Общий План по Марже", f"{total_margin_plan:,.0f}".replace(",", " "))

st.divider()

# ГРАФИКИ
c1, c2 = st.columns(2)

with c1:
    st.subheader("План по Выручке (по менеджерам)")
    fig_rev = px.bar(df_clean, x="Менеджер", y="План по выручке", text_auto=',.0f', color="План по выручке")
    st.plotly_chart(fig_rev, use_container_width=True)

with c2:
    st.subheader("План по Марже (по менеджерам)")
    fig_marg = px.bar(df_clean, x="Менеджер", y="План по маржинальной прибыли", text_auto=',.0f', color="План по маржинальной прибыли")
    st.plotly_chart(fig_marg, use_container_width=True)