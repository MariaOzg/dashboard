import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import time

st.set_page_config(page_title="KPI Дашборд", layout="wide")

# ==========================================
# 🔐 НАСТРОЙКИ ДОСТУПА И ПОЛЬЗОВАТЕЛИ
# ==========================================

# 1. СПИСОК ПОЛЬЗОВАТЕЛЕЙ (Логин : Пароль)
# Пароль "123" для всех для теста. Поменяйте на сложные!
USERS = {
    # Директора
    "Rustam": "Xk9#mP2z",
    "Vlad": "Qr5!vL8n",
    "Otabek": "Wa7$cB3s",  # Отабек здесь как директор
    
    # Менеджеры
    "Lana": "Yp4@hR9k",
    "Kristina": "Jm2&dS6f",
    "Sultan": "Zn8*tX5g",
    "Erkinoy": "Qw3bN7j",
    "Zarina": "Kd6#vM4p",
    "Nurik": "Ls9@fY2t",
}

# 2. КТО ЕСТЬ КТО (Логин -> Роль)
# admin - видит всё, manager - видит только себя
ROLES = {
    "Rustam": "admin",
    "Vlad": "admin",
    "Otabek": "admin",
    
    "Lana": "manager",
    "Kristina": "manager",
    "Sultan": "manager",
    "Erkinoy": "manager",
    "Zarina": "manager",
    "Nurik": "manager",
}

# 3. ПРИВЯЗКА К ИМЕНАМ В ТАБЛИЦЕ (Логин -> Имя в Excel)
# Важно для фильтрации данных
NAME_MAPPING = {
    "Otabek": "Отабек", # У Отабека есть и права админа, и свои проекты
    "Lana": "Лана",
    "Kristina": "Кристина",
    "Sultan": "Султан",
    "Erkinoy": "Еркиной",
    "Zarina": "Зарина",
    "Nurik": "Нурик"
}

# ==========================================
# 🚪 ФОРМА ВХОДА
# ==========================================
def check_password():
    """Возвращает True, если вход выполнен успешно"""
    if st.session_state.get("authenticated", False):
        return True

    st.title("🔐 Вход в систему")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        
        if st.button("Войти"):
            if username in USERS and USERS[username] == password:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = ROLES.get(username, "manager")
                st.session_state["real_name"] = NAME_MAPPING.get(username, username)
                st.success(f"Добро пожаловать, {st.session_state['real_name']}!")
                time.sleep(1) # Небольшая пауза для приятного UX
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    return False

if not check_password():
    st.stop() # Останавливаем загрузку всего остального, если не вошли

# ==========================================
# 📥 ЗАГРУЗКА ДАННЫХ (ТОЛЬКО ПОСЛЕ ВХОДА)
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvNrboP0eML1Mc3lk2WJ2Oze0kA5RT8pakzgjETh_eM/edit?gid=0#gid=0"

@st.cache_data(ttl=600)
def load_kpi_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["type"] = "service_account"
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url(SHEET_URL).worksheet("Общие параметры")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return pd.DataFrame()

def clean_money(x):
    if isinstance(x, str):
        x = x.replace(' ', '').replace(',', '.').replace('\xa0', '')
        if x == '' or x == '-': return 0.0
        try: return float(x)
        except: return 0.0
    return x if isinstance(x, (int, float)) else 0.0

# ==========================================
# 📊 ДАШБОРД (ГЛАВНАЯ ЧАСТЬ)
# ==========================================

# Кнопка выхода в сайдбаре
st.sidebar.write(f"Вы вошли как: **{st.session_state['username']}**")
if st.sidebar.button("Выйти"):
    st.session_state["authenticated"] = False
    st.rerun()

st.title("🏆 KPI Монитор: План vs Факт")

df_raw = load_kpi_data()

if df_raw.empty:
    st.warning("Нет данных.")
    st.stop()

# Подготовка данных
df_raw.columns = [c.strip() for c in df_raw.columns]
df = df_raw[df_raw["Менеджер"] != "Итого"].copy()

col_plan_rev = "План по выручке"
col_fact_rev = "Выручка факт"
col_plan_marg = "План по маржинальной прибыли"
col_fact_marg = "Маржинальная прибыль факт"

for col in [col_plan_rev, col_fact_rev, col_plan_marg, col_fact_marg]:
    if col in df.columns:
        df[col] = df[col].apply(clean_money)
    else:
        df[col] = 0.0

# --- ЛОГИКА ОТОБРАЖЕНИЯ ---
# Если Админ - видит всё. Если Менеджер - видит только СВОЮ строку в графиках (или всё, если хотите на 1 вкладке оставить общую картину).
# Обычно на KPI вкладке полезно видеть сравнение с другими. 
# ОСТАВЛЯЕМ ОБЩУЮ КАРТИНУ для духа соревнования (или можно отфильтровать, если нужно строго).
# ПРИМЕР: Оставим всем всё, чтобы видели лидеров.

# МЕТРИКИ
total_plan_rev = df[col_plan_rev].sum()
total_fact_rev = df[col_fact_rev].sum()
delta_rev = total_fact_rev - total_plan_rev

total_plan_marg = df[col_plan_marg].sum()
total_fact_marg = df[col_fact_marg].sum()
delta_marg = total_fact_marg - total_plan_marg

kpi1, kpi2 = st.columns(2)
kpi1.metric("💰 Общая Выручка", f"${total_fact_rev:,.0f}".replace(",", " "), f"{delta_rev:,.0f}")
kpi2.metric("📈 Общая Маржа", f"${total_fact_marg:,.0f}".replace(",", " "), f"{delta_marg:,.0f}")

st.divider()

tab1, tab2 = st.tabs(["📊 Выручка", "📉 Маржа"])

with tab1:
    df_rev = df[["Менеджер", col_plan_rev, col_fact_rev]].melt("Менеджер", var_name="Тип", value_name="Сумма")
    fig_rev = px.bar(df_rev, x="Менеджер", y="Сумма", color="Тип", barmode="group", text_auto='.2s',
                     color_discrete_map={col_plan_rev: "#A7C7E7", col_fact_rev: "#228B22"})
    st.plotly_chart(fig_rev, use_container_width=True)

with tab2:
    df_marg = df[["Менеджер", col_plan_marg, col_fact_marg]].melt("Менеджер", var_name="Тип", value_name="Сумма")
    fig_marg = px.bar(df_marg, x="Менеджер", y="Сумма", color="Тип", barmode="group", text_auto='.2s',
                      color_discrete_map={col_plan_marg: "#FFB347", col_fact_marg: "#FF4500"})
    st.plotly_chart(fig_marg, use_container_width=True)
