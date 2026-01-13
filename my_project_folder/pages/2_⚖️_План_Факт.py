import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

st.set_page_config(page_title="План-Факт Расходов", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvNrboP0eML1Mc3lk2WJ2Oze0kA5RT8pakzgjETh_eM/edit?gid=1885685439#gid=1885685439"

# --- ЗАГРУЗКА ---
@st.cache_data(ttl=600)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["type"] = "service_account"
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    try:
        sh = client.open_by_url(SHEET_URL)
        # Загружаем вкладки по названиям из ваших скринов
        ws_plan = sh.worksheet("Согласованные расходы") 
        ws_fact = sh.worksheet("Фактические расходы")
        
        df_plan = pd.DataFrame(ws_plan.get_all_records())
        df_fact = pd.DataFrame(ws_fact.get_all_records())
        
        return df_plan, df_fact
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return pd.DataFrame(), pd.DataFrame()

def clean_money(x):
    if isinstance(x, str):
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x

# --- ОБРАБОТКА ---
st.title("⚖️ Анализ: План vs Факт")

df_plan_raw, df_fact_raw = load_data()

if df_plan_raw.empty or df_fact_raw.empty:
    st.warning("Нет данных. Проверьте названия вкладок 'Согласованные расходы' и 'Фактические расходы'.")
    st.stop()

# 1. Подготовка ПЛАНА
# На вашем скрине колонка с деньгами называется "Сумма, в дс"
df_plan = df_plan_raw.copy()
df_plan["Сумма_План"] = df_plan["Сумма, в дс"].apply(clean_money)
# Группируем, чтобы убрать дубли, если есть
df_plan_g = df_plan.groupby(["Менеджер", "Проект", "Статья расходов"])["Сумма_План"].sum().reset_index()

# 2. Подготовка ФАКТА
# На вашем скрине колонка называется "Сумма, в долл." (отличается от плана!)
df_fact = df_fact_raw.copy()
# Убираем пустые строки, если менеджер не заполнен (вижу пустые на скрине)
df_fact = df_fact[df_fact["Менеджер"] != ""] 
df_fact["Сумма_Факт"] = df_fact["Сумма, в долл."].apply(clean_money)
df_fact_g = df_fact.groupby(["Менеджер", "Проект", "Статья расходов"])["Сумма_Факт"].sum().reset_index()

# 3. ОБЪЕДИНЕНИЕ (Слияние)
# Соединяем две таблицы по трем ключевым колонкам
df_merged = pd.merge(
    df_plan_g, 
    df_fact_g, 
    on=["Менеджер", "Проект", "Статья расходов"], 
    how="outer" # outer = берем всё, даже если есть только в плане или только в факте
).fillna(0)

# 4. Расчет отклонений
df_merged["Отклонение"] = df_merged["Сумма_План"] - df_merged["Сумма_Факт"]
# Если План 100, Факт 120 -> Отклонение -20 (Перерасход, плохо)
# Если План 100, Факт 80 -> Отклонение +20 (Экономия, хорошо)

# --- ВИЗУАЛИЗАЦИЯ ---

# Фильтры слева
st.sidebar.header("Фильтры")
all_managers = df_merged["Менеджер"].unique()
sel_manager = st.sidebar.multiselect("Менеджер", all_managers, default=all_managers)

all_projects = df_merged[df_merged["Менеджер"].isin(sel_manager)]["Проект"].unique()
sel_project = st.sidebar.multiselect("Проект", all_projects, default=all_projects)

# Применяем фильтр
mask = (df_merged["Менеджер"].isin(sel_manager)) & (df_merged["Проект"].isin(sel_project))
df_final = df_merged[mask]

# Метрики
total_plan = df_final["Сумма_План"].sum()
total_fact = df_final["Сумма_Факт"].sum()
diff = total_plan - total_fact

m1, m2, m3 = st.columns(3)
m1.metric("Всего Согласовано (План)", f"${total_plan:,.0f}".replace(",", " "))
m2.metric("Всего Потрачено (Факт)", f"${total_fact:,.0f}".replace(",", " "))
m3.metric("Разница (Экономия)", f"${diff:,.0f}".replace(",", " "), 
          delta_color="normal") # Зеленый если +, Красный если -

st.divider()

# Таблица с подсветкой
st.subheader("Детальная таблица")

def highlight_diff(val):
    if val < -1: return 'color: #FF4B4B; font-weight: bold' # Красный (Перерасход)
    elif val > 1: return 'color: #09AB3B; font-weight: bold' # Зеленый (Экономия)
    return ''

st.dataframe(
    df_final.style
    .format("{:,.0f}", subset=["Сумма_План", "Сумма_Факт", "Отклонение"])
    .map(highlight_diff, subset=["Отклонение"]),
    use_container_width=True,
    height=600
)

# График
st.subheader("План vs Факт по Проектам")
df_chart = df_final.groupby("Проект")[["Сумма_План", "Сумма_Факт"]].sum().reset_index()
df_melt = df_chart.melt(id_vars="Проект", var_name="Тип", value_name="Сумма")

fig = px.bar(df_melt, x="Проект", y="Сумма", color="Тип", barmode="group",
             color_discrete_map={"Сумма_План": "#A7C7E7", "Сумма_Факт": "#FF6961"})
st.plotly_chart(fig, use_container_width=True)