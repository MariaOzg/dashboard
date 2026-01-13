import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

st.set_page_config(page_title="План-Факт Расходов", layout="wide")

# ==========================================
# 🔒 ПРОВЕРКА ДОСТУПА
# ==========================================
if not st.session_state.get("authenticated", False):
    st.warning("⚠️ Пожалуйста, сначала войдите в систему на Главной странице.")
    st.stop()

# Получаем данные пользователя из сессии
current_user = st.session_state["username"]
user_role = st.session_state["role"]       # 'admin' или 'manager'
real_name = st.session_state["real_name"]  # 'Отабек', 'Лана' и т.д.

# ==========================================
# 📥 ЗАГРУЗКА
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvNrboP0eML1Mc3lk2WJ2Oze0kA5RT8pakzgjETh_eM/edit?gid=0#gid=0"

@st.cache_data(ttl=600)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["type"] = "service_account"
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_url(SHEET_URL)
        ws_plan = sh.worksheet("Согласованные расходы") 
        ws_fact = sh.worksheet("Фактические расходы")
        
        df_plan = pd.DataFrame(ws_plan.get_all_records())
        df_fact = pd.DataFrame(ws_fact.get_all_records())
        
        return df_plan, df_fact
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return pd.DataFrame(), pd.DataFrame()

def clean_money(x):
    if isinstance(x, str):
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x

def find_money_column(df, possible_names):
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        for name in possible_names:
            if name.lower() in col.lower():
                return col
    return None

# ==========================================
# ⚙️ ОБРАБОТКА ДАННЫХ
# ==========================================
st.title(f"⚖️ План-Факт: {real_name}")

df_plan_raw, df_fact_raw = load_data()

if df_plan_raw.empty or df_fact_raw.empty:
    st.warning("Данные не загружены.")
    st.stop()

# Обработка Плана
df_plan = df_plan_raw.copy()
plan_col = find_money_column(df_plan, ["Сумма", "в дс", "sum"])
if plan_col:
    df_plan["Сумма_План"] = df_plan[plan_col].apply(clean_money)
else:
    st.error("Не найдена колонка с суммой в Плане")
    st.stop()

# Группировка Плана
df_plan_g = df_plan.groupby(["Менеджер", "Проект", "Статья расходов"])["Сумма_План"].sum().reset_index()

# Обработка Факта
df_fact = df_fact_raw.copy()
df_fact = df_fact[df_fact["Менеджер"] != ""]
fact_col = find_money_column(df_fact, ["Сумма", "в долл", "sum"])
if fact_col:
    df_fact["Сумма_Факт"] = df_fact[fact_col].apply(clean_money)
else:
    st.error("Не найдена колонка с суммой в Факте")
    st.stop()

# Группировка Факта
df_fact_g = df_fact.groupby(["Менеджер", "Проект", "Статья расходов"])["Сумма_Факт"].sum().reset_index()

# Слияние
df_merged = pd.merge(
    df_plan_g, 
    df_fact_g, 
    on=["Менеджер", "Проект", "Статья расходов"], 
    how="outer"
).fillna(0)
df_merged["Отклонение"] = df_merged["Сумма_План"] - df_merged["Сумма_Факт"]

# ==========================================
# 🛡️ ФИЛЬТРАЦИЯ ПО ПРАВАМ ДОСТУПА
# ==========================================
st.sidebar.header("Фильтры")

df_final = pd.DataFrame()

if user_role == "admin":
    # --- ЛОГИКА АДМИНА ---
    st.sidebar.success("Режим: Директор (Видит всех)")
    
    # Может выбрать кого угодно
    all_managers = sorted(df_merged["Менеджер"].unique())
    selected_managers = st.sidebar.multiselect("Выберите менеджера", all_managers, default=all_managers)
    
    df_final = df_merged[df_merged["Менеджер"].isin(selected_managers)]

else:
    # --- ЛОГИКА МЕНЕДЖЕРА ---
    st.sidebar.info(f"Режим: Менеджер ({real_name})")
    
    # Жесткий фильтр: только своё имя
    df_final = df_merged[df_merged["Менеджер"] == real_name]
    
    if df_final.empty:
        st.info("По вашим проектам данных пока нет.")
        st.stop()

# ==========================================
# 📊 ВИЗУАЛИЗАЦИЯ
# ==========================================

# Фильтр проектов (внутри уже разрешенного списка)
available_projects = sorted(df_final["Проект"].unique())
sel_project = st.sidebar.multiselect("Проект", available_projects, default=available_projects)

df_show = df_final[df_final["Проект"].isin(sel_project)]

# Метрики
tp = df_show["Сумма_План"].sum()
tf = df_show["Сумма_Факт"].sum()
diff = tp - tf

c1, c2, c3 = st.columns(3)
c1.metric("План", f"${tp:,.0f}".replace(",", " "))
c2.metric("Факт", f"${tf:,.0f}".replace(",", " "))
c3.metric("Экономия", f"${diff:,.0f}".replace(",", " "), delta_color="normal")

st.divider()

# Таблица
st.subheader("Детализация")
def highlight_diff(val):
    if val < -10: return 'color: #FF4B4B' # Перерасход
    elif val > 10: return 'color: #09AB3B' # Экономия
    return ''

st.dataframe(
    df_show.style
    .format("{:,.0f}", subset=["Сумма_План", "Сумма_Факт", "Отклонение"])
    .map(highlight_diff, subset=["Отклонение"]),
    use_container_width=True,
    height=600
)
