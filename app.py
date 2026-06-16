import streamlit as st
import random
import requests
import json
import re
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta

# ==========================================
# 1. API 設定 (安全讀取 Secrets 金鑰)
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = ""

API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ==========================================
# 2. 資料庫設定
# ==========================================
def init_db():
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_records
                 (date TEXT PRIMARY KEY, weight REAL, calories INTEGER, protein INTEGER, carbs INTEGER, fat INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_profile
                 (id INTEGER PRIMARY KEY, gender TEXT, age INTEGER, height REAL, weight REAL, activity_level TEXT, goal TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS food_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, description TEXT, calories INTEGER, protein INTEGER, carbs INTEGER, fat INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def sync_daily_totals(date_str, current_weight):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("SELECT SUM(calories), SUM(protein), SUM(carbs), SUM(fat) FROM food_items WHERE date = ?", (date_str,))
    res = c.fetchone()
    
    calories = res[0] if res[0] is not None else 0
    protein = res[1] if res[1] is not None else 0
    carbs = res[2] if res[2] is not None else 0
    fat = res[3] if res[3] is not None else 0
    
    c.execute('''REPLACE INTO daily_records (date, weight, calories, protein, carbs, fat)
                 VALUES (?, ?, ?, ?, ?, ?)''', (date_str, current_weight, calories, protein, carbs, fat))
    conn.commit()
    conn.close()
    
    st.session_state.total_calories = calories
    st.session_state.total_protein = protein
    st.session_state.total_carbs = carbs
    st.session_state.total_fat = fat

def add_food_item(date_str, description, calories, protein, carbs, fat, current_weight):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute('''INSERT INTO food_items (date, description, calories, protein, carbs, fat)
                 VALUES (?, ?, ?, ?, ?, ?)''', (date_str, description, calories, protein, carbs, fat))
    conn.commit()
    conn.close()
    sync_daily_totals(date_str, current_weight)

def delete_food_item(item_id, date_str, current_weight):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("DELETE FROM food_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    sync_daily_totals(date_str, current_weight)

def get_food_items(date_str):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("SELECT id, description, calories, protein, carbs, fat FROM food_items WHERE date = ?", (date_str,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_daily_record(date_str):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("SELECT calories, protein, carbs, fat FROM daily_records WHERE date = ?", (date_str,))
    res = c.fetchone()
    conn.close()
    return res

def load_history_data(start_date, end_date):
    conn = sqlite3.connect('diet_tracker.db')
    query = f"SELECT * FROM daily_records WHERE date BETWEEN '{start_date}' AND '{end_date}' ORDER BY date ASC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def save_profile_db(gender, age, height, weight, activity_level, goal):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute('''REPLACE INTO user_profile (id, gender, age, height, weight, activity_level, goal)
                 VALUES (1, ?, ?, ?, ?, ?, ?)''', (gender, age, height, weight, activity_level, goal))
    conn.commit()
    conn.close()

def load_profile_db():
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("SELECT gender, age, height, weight, activity_level, goal FROM user_profile WHERE id = 1")
    res = c.fetchone()
    conn.close()
    return res

# ==========================================
# 3. 網頁初始設定與側邊欄
# ==========================================
st.set_page_config(page_title="聚餐熱量計算機", page_icon="🍽️", layout="wide")

profile = load_profile_db()
def_gender = profile[0] if profile else "女生"
def_age = profile[1] if profile else 22
def_height = profile[2] if profile else 160.0
def_weight = profile[3] if profile else 55.0
def_activity = profile[4] if profile else "輕度活動量"
def_goal = profile[5] if profile else "健康減脂"

st.sidebar.header("👤 個人身體數值設定")
today_date = st.sidebar.date_input("今天日期：", date.today())

gender_opts = ["女生", "男生"]
gender_index = gender_opts.index(def_gender) if def_gender in gender_opts else 0
gender = st.sidebar.radio("性別：", gender_opts, index=gender_index)

age = st.sidebar.number_input("年齡 (歲)：", value=int(def_age), min_value=1, max_value=100)
height = st.sidebar.number_input("身高 (公分)：", value=float(def_height), min_value=50.0, max_value=250.0)
weight = st.sidebar.number_input("今日體重 (公斤)：", value=float(def_weight), min_value=10.0, max_value=300.0)

activity_opts = ["久坐缺乏運動", "輕度活動量", "中度活動量", "高度活動量"]
activity_index = activity_opts.index(def_activity) if def_activity in activity_opts else 1
activity_level = st.sidebar.selectbox("日常活動量：", activity_opts, index=activity_index)

goal_opts = ["維持體重", "健康減脂", "積極瘦身", "乾淨增肌"]
goal_index = goal_opts.index(def_goal) if def_goal in goal_opts else 1
goal = st.sidebar.radio("減重策略目標：", goal_opts, index=goal_index)

if st.sidebar.button("💾 儲存個人預設資料"):
    save_profile_db(gender, age, height, weight, activity_level, goal)
    st.sidebar.success("✅ 設定已儲存！下次打開會自動帶入。")

if 'total_calories' not in st.session_state:
    st.session_state.total_calories = 0
    st.session_state.total_protein = 0
    st.session_state.total_carbs = 0
    st.session_state.total_fat = 0

atonement_tasks = ["波比跳 30 下", "開合跳 100 下", "深蹲 50 下", "快走 30 分鐘", "棒式維持 2 分鐘"]

if gender == "男生":
    bmr = 66.47 + (13.75 * weight) + (5.0 * height) - (6.76 * age)
else:
    bmr = 655.1 + (9.56 * weight) + (1.85 * height) - (4.68 * age)

if "久坐" in activity_level: tdee = bmr * 1.2
elif "輕度" in activity_level: tdee = bmr * 1.375
elif "中度" in activity_level: tdee = bmr * 1.55
else: tdee = bmr * 1.725

if "健康減脂" in goal: budget_cal = int(tdee - 300)
elif "積極瘦身" in goal: budget_cal = int(tdee - 500)
elif "乾淨增肌" in goal: budget_cal = int(tdee + 200)
else: budget_cal = int(tdee)

target_protein = int((budget_cal * 0.25) / 4)
target_carbs = int((budget_cal * 0.45) / 4)
target_fat = int((budget_cal * 0.30) / 9)

st.sidebar.markdown("---")
st.sidebar.info(f"🧬 基礎代謝 (BMR)：{int(bmr)} 大卡")
st.sidebar.warning(f"⚡ 每日消耗 (TDEE)：{int(tdee)} 大卡")
st.sidebar.success(f"🎯 今日預算：{budget_cal} 大卡")

# ==========================================
# 4. 網頁主畫面
# ==========================================
st.title("🍽️ AI 飲食追蹤與數據分析報告")
tab_daily, tab_history, tab_chat = st.tabs(["📝 今日飲食紀錄", "📈 歷史數據與 AI 報告", "💬 AI 飲食小助理"])

# ----------------- 分頁 1: 今日飲食紀錄 -----------------
with tab_daily:
    st.subheader("📅 第一步：確認您的紀錄日期")
    target_date = st.date_input("這筆餐點要記入哪一天的數據？", value=today_date, key="daily_record_date_picker")
    date_str = target_date.strftime("%Y-%m-%d")

    db_record = get_daily_record(date_str)
    st.session_state.total_calories = db_record[0] if (db_record and db_record[0]) else 0
    st.session_state.total_protein = db_record[1] if (db_record and db_record[1]) else 0
    st.session_state.total_carbs = db_record[2] if (db_record and db_record[2]) else 0
    st.session_state.total_fat = db_record[3] if (db_record and db_record[3]) else 0

    st.markdown("---")
    st.subheader("📸 拍照或上傳餐點照片")
    col_cam, col_up = st.columns(2)
    with col_cam:
        camera_img = st.camera_input("開啟相機拍照")
    with col_up:
        uploaded_file = st.file_uploader("從相簿上傳照片", type=["jpg", "jpeg", "png"])
    
    st.markdown(f"### ✍️ 請補充說明這餐吃了什麼 (將記入 {date_str})：")
    food_text = st.text_input("例如：照片裡有一顆茶葉蛋(50-60g)和120g的炒高麗菜和200g白飯以及130g柚香雞胸肉", placeholder="請在此處輸入食物描述...")

    if st.button("🚀 送出進行 AI 解析", key="nutrition_btn"):
        if not GROQ_API_KEY:
            st.error("🔑 偵測不到 API 金鑰，請確保您已在 .streamlit/secrets.toml 中設定 GROQ_API_KEY。")
        elif food_text:
            # 🧠 終極升級 Prompt：給予台灣外食參考值，並允許 AI 寫出完整計算過程！
            text_prompt = (
                f"妳是精準的台灣外食營養專家。請評估這段食物描述：『{food_text}』。\n"
                "【台灣常見食物營養參考 (每100g)】\n"
                "- 白飯：約 130大卡 (碳水28g, 蛋白3g, 脂肪0.3g)\n"
                "- 雞胸肉：約 110大卡 (蛋白23g, 脂肪1.5g)\n"
                "- 茶葉蛋1顆：約 75大卡 (蛋白7g, 脂肪5g)\n"
                "- 炒高麗菜：約 40大卡 (碳水5g, 脂肪2g)\n"
                "【計算步驟要求】\n"
                "1. 請先一步一步寫下各項食物換算克數後的熱量與三大營養素，並寫出加總的算式。\n"
                "2. 嚴格遵守熱量公式：(蛋白質*4) + (碳水*4) + (脂肪*9)。\n"
                "3. 最後，請『務必』附上標準 JSON 格式的總結，以便系統讀取，格式嚴格如下：\n"
                '{"calories": 總熱量整數, "protein": 總蛋白質整數, "carbs": 總碳水整數, "fat": 總脂肪整數}'
            )
            with st.spinner("AI 正在使用升級版大腦精準解析食物成分..."):
                try:
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": text_prompt}], "temperature": 0.1}
                    response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
                    res_json = response.json()
                    
                    if "choices" in res_json:
                        ai_raw = res_json["choices"][0]["message"]["content"].strip()
                        # 利用正則表達式，自動忽略前面 AI 碎碎念的算式，只抓取最後的 JSON 括號
                        json_match = re.search(r'\{.*\}', ai_raw, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(0))
                            cal = int(data.get("calories", 0))
                            prot = int(data.get("protein", 0))
                            carbs = int(data.get("carbs", 0))
                            fat = int(data.get("fat", 0))
                            
                            add_food_item(date_str, food_text, cal, prot, carbs, fat, weight)
                            st.success(f"✨ **解析成功！已順利寫入 {date_str} 的紀錄！**")
                            st.rerun()
                        else:
                            st.error("AI 回傳格式有誤，請再試一次。")
                    else:
                        st.error("伺服器忙碌中，請稍微再試一次。")
                except Exception as e:
                    st.error(f"解析失敗。錯誤: {e}")
        else:
            st.warning("請先輸入食物描述！")

    st.markdown("---")
    st.markdown(f"### 📝 或者有精準營養標示？手動輸入 (將記入 {date_str})：")
    with st.expander("點我展開：手動輸入營養素"):
        m_desc = st.text_input("🏷️ 食物/商品名稱", value="手動輸入項目")
        m_cal = st.number_input("🔥 總熱量 (大卡)", min_value=0, step=10)
        m_pro = st.number_input("🥩 蛋白質 (克)", min_value=0, step=1)
        m_carb = st.number_input("🍞 碳水化合物 (克)", min_value=0, step=1)
        m_fat = st.number_input("🥑 脂肪 (克)", min_value=0, step=1)
        if st.button("➕ 新增此筆手動紀錄"):
            if m_cal > 0 or m_pro > 0 or m_carb > 0 or m_fat > 0:
                add_food_item(date_str, m_desc, m_cal, m_pro, m_carb, m_fat, weight)
                st.success(f"✨ **手動紀錄成功儲存至 {date_str}！**")
                st.rerun()
            else:
                st.warning("請至少輸入一項大於 0 的數值喔！")

    st.write("---")
    st.subheader(f"📊 {date_str} 營養素攝取進度")
    st.metric(label="🔥 總熱量", value=f"{st.session_state.total_calories} / {budget_cal} kcal")
    st.progress(min(st.session_state.total_calories / budget_cal, 1.0) if budget_cal > 0 else 0.0)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("🥩 蛋白質", f"{st.session_state.total_protein} / {target_protein} g")
        st.progress(min(st.session_state.total_protein / target_protein, 1.0) if target_protein > 0 else 0.0)
    with c2:
        st.metric("🍞 碳水", f"{st.session_state.total_carbs} / {target_carbs} g")
        st.progress(min(st.session_state.total_carbs / target_carbs, 1.0) if target_carbs > 0 else 0.0)
    with c3:
        st.metric("🥑 脂肪", f"{st.session_state.total_fat} / {target_fat} g")
        st.progress(min(st.session_state.total_fat / target_fat, 1.0) if target_fat > 0 else 0.0)

    st.write("---")
    st.subheader(f"🗑️ {date_str} 飲食明細與刪除管理")
    current_items = get_food_items(date_str)
    if current_items:
        item_options = {}
        for idx, item_id, desc, c_cal, c_pro, c_carb, c_fat in zip(range(len(current_items)), *zip(*current_items)):
            display_text = f"{idx+1}. {desc} (🔥{c_cal}卡 | 🥩{c_pro}g | 🍞{c_carb}g | 🥑{c_fat}g)"
            item_options[display_text] = item_id
            st.text(f"• {display_text}")
        
        delete_choice = st.selectbox("選擇一筆你想刪除的錯誤紀錄：", list(item_options.keys()))
        if st.button("❌ 確定刪除此筆食物紀錄"):
            delete_food_item(item_options[delete_choice], date_str, weight)
            st.success("項目已成功移除，今日進度已自動扣除！")
            st.rerun()
    else:
        st.info("該日期目前還沒有任何飲食紀錄喔。")

    st.write("---")
    if st.button("💾 點我進行今日結算 (看慶祝彩帶)"):
        st.success(f"✅ {date_str} 的數據已成功結算！")
        diff = st.session_state.total_calories - budget_cal
        if diff > 0:
            st.error(f"🚨 今日超標 {diff} 大卡！隨機贖罪任務：{random.choice(atonement_tasks)}")
        else:
            st.balloons()

# ----------------- 分頁 2: 歷史數據與報表 -----------------
with tab_history:
    st.subheader("📅 選擇資料查詢區間")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input("開始日期", date.today() - timedelta(days=7))
    with col_d2:
        end_date = st.date_input("結束日期", date.today())
    
    df = load_history_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    
    if not df.empty:
        df_chart = df.copy()
        df_chart['date'] = pd.to_datetime(df_chart['date'])
        df_chart.set_index('date', inplace=True)
        
        st.markdown("### 📈 數據視覺化圖表")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("🔥 熱量攝取變化曲線 (大卡)")
            st.line_chart(df_chart['calories'], color="#FF4B4B")
        with chart_col2:
            st.caption("⚖️ 體重變化曲線 (公斤)")
            st.line_chart(df_chart['weight'], color="#0068C9")

        st.markdown("### 📁 匯出成果報告")
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 點我下載 CSV 歷史報表", data=csv, file_name='diet_report.csv', mime='text/csv')

        st.markdown("### 🤖 針對現狀的 AI 飲食建議")
        if st.button("✨ 產出專屬現狀分析報告"):
            avg_cal = df['calories'].mean()
            start_weight = df['weight'].iloc[0]
            end_weight = df['weight'].iloc[-1]
            weight_diff = end_weight - start_weight
            
            report_prompt = (
                f"你是一位專業營養師。使用者從 {start_date} 到 {end_date} 期間，"
                f"平均每日攝取 {avg_cal:.1f} 大卡。體重從 {start_weight}kg 變為 {end_weight}kg (變化 {weight_diff:+.1f}kg)。"
                f"使用者的目標是：{goal}。請根據這些真實歷史數據，給予他對現狀的「建議更改方向」與「具體的飲食建議」。用繁體中文回答，語氣溫暖專業。"
            )
            
            with st.spinner("AI 營養師正在研讀妳的歷史數據..."):
                try:
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": report_prompt}], "temperature": 0.5}
                    res = requests.post(API_URL, headers=headers, json=payload).json()
                    if "choices" in res:
                        st.info(res["choices"][0]["message"]["content"])
                    else:
                        st.error("產生報告失敗，請稍後再試。")
                except Exception as e:
                    st.error(f"連線錯誤: {e}")
    else:
        st.warning("📭 這段期間還沒有紀錄喔！請先到「今日飲食紀錄」結算並存檔。")

    st.write("---")
    st.subheader("🔍 單日飲食明細歷史查詢")
    search_date = st.date_input("選擇你想回顧的特定日期：", date.today(), key="history_search_picker")
    search_date_str = search_date.strftime("%Y-%m-%d")
    
    hist_items = get_food_items(search_date_str)
    if hist_items:
        st.markdown(f"📅 **{search_date_str} 的詳細飲食清單：**")
        hist_list = []
        for _, desc, h_cal, h_pro, h_carb, h_fat in hist_items:
            hist_list.append({
                "食物名稱/描述": desc,
                "熱量 (大卡)": h_cal,
                "蛋白質 (克)": h_pro,
                "碳水化合物 (克)": h_carb,
                "脂肪 (克)": h_fat
            })
        st.table(pd.DataFrame(hist_list))
    else:
        st.info(f"固定日期 {search_date_str} 沒有留下任何飲食紀錄喔。")

# ----------------- 分頁 3: AI 飲食小助理 -----------------
with tab_chat:
    st.subheader("💬 妳的專屬 AI 飲食生活顧問")
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_query := st.chat_input("輸入妳想問營養助理的問題..."):
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    chat_prompt = [
                        {"role": "system", "content": "你是一位溫慢、專業且幽默的台灣營養師小助手。請用繁體中文回答使用者的各種減重、飲食、外食挑選疑問，多用鼓勵的口吻。"}
                    ] + st.session_state.messages
                    
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    payload = {"model": "llama-3.3-70b-versatile", "messages": chat_prompt, "temperature": 0.7}
                    chat_res = requests.post(API_URL, headers=headers, json=payload).json()
                    if "choices" in chat_res:
                        reply = chat_res["choices"][0]["message"]["content"]
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    else:
                        st.error("小助理累倒了，請再問一次！")
                except Exception as e:
                    st.error(f"連線失敗: {e}")