import streamlit as st
import random
import requests
import json
import re
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta

# ==========================================
# 1. API 設定
# ==========================================
GROQ_API_KEY = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ==========================================
# 2. 資料庫設定 (永久儲存防消失)
# ==========================================
def init_db():
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_records
                 (date TEXT PRIMARY KEY, weight REAL, calories INTEGER, protein INTEGER, carbs INTEGER, fat INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def save_to_db(record_date, weight, calories, protein, carbs, fat):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute('''REPLACE INTO daily_records (date, weight, calories, protein, carbs, fat)
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (record_date, weight, calories, protein, carbs, fat))
    conn.commit()
    conn.close()

def load_history_data(start_date, end_date):
    conn = sqlite3.connect('diet_tracker.db')
    query = f"SELECT * FROM daily_records WHERE date BETWEEN '{start_date}' AND '{end_date}' ORDER BY date ASC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_daily_record(date_str):
    conn = sqlite3.connect('diet_tracker.db')
    c = conn.cursor()
    c.execute("SELECT calories, protein, carbs, fat FROM daily_records WHERE date = ?", (date_str,))
    res = c.fetchone()
    conn.close()
    return res

# ==========================================
# 3. 網頁初始設定與側邊欄 (BMR/TDEE 個人數值設定)
# ==========================================
st.set_page_config(page_title="聚餐熱量計算機", page_icon="🍽️", layout="wide")
st.sidebar.header("👤 個人身體數值設定")

today_date = st.sidebar.date_input("今天日期：", date.today())
gender = st.sidebar.radio("性別：", ["女生", "男生"])
age = st.sidebar.number_input("年齡 (歲)：", value=22, min_value=1, max_value=100)
height = st.sidebar.number_input("身高 (公分)：", value=160.0, min_value=50.0, max_value=250.0)
weight = st.sidebar.number_input("今日體重 (公斤)：", value=55.0, min_value=10.0, max_value=300.0)

activity_level = st.sidebar.selectbox(
    "日常活動量：",
    ["久坐缺乏運動", "輕度活動量", "中度活動量", "高度活動量"]
)

goal = st.sidebar.radio("減重策略目標：", ["維持體重", "健康減脂", "積極瘦身", "乾淨增肌"])

# 智慧防消失引擎：切換日期或重整時自動從資料庫抓數據
date_str = today_date.strftime("%Y-%m-%d")

if 'current_date' not in st.session_state or st.session_state.current_date != date_str:
    st.session_state.current_date = date_str
    db_record = get_daily_record(date_str)
    if db_record:
        st.session_state.total_calories = db_record[0]
        st.session_state.total_protein = db_record[1]
        st.session_state.total_carbs = db_record[2]
        st.session_state.total_fat = db_record[3]
    else:
        st.session_state.total_calories = 0
        st.session_state.total_protein = 0
        st.session_state.total_carbs = 0
        st.session_state.total_fat = 0

atonement_tasks = ["波比跳 30 下", "開合跳 100 下", "深蹲 50 下", "快走 30 分鐘", "棒式維持 2 分鐘"]

# 動態計算 BMR & TDEE
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
# 4. 網頁主畫面 (三大功能分頁)
# ==========================================
st.title("🍽️ AI 飲食追蹤與數據分析報告")
tab_daily, tab_history, tab_chat = st.tabs(["📝 今日飲食紀錄", "📈 歷史數據與 AI 報告", "💬 AI 飲食小助理"])

# ----------------- 分頁 1: 今日飲食紀錄 -----------------
with tab_daily:
    st.subheader("📸 拍照或上傳今日餐點")
    col_cam, col_up = st.columns(2)
    with col_cam:
        camera_img = st.camera_input("開啟相機拍照")
    with col_up:
        uploaded_file = st.file_uploader("從相簿上傳照片", type=["jpg", "jpeg", "png"])
    
    st.markdown("### ✍️ 請補充說明這餐吃了什麼：")
    food_text = st.text_input("例如：照片裡是炸雞排一片、半糖去冰紅茶大杯", placeholder="請在此處輸入食物描述...")

    if st.button("🚀 送出進行 AI 解析", key="nutrition_btn"):
        if food_text:
            text_prompt = (
                f"妳是外食營養分析專家。請估算這段食物描述的總熱量（大卡）、蛋白質（克）、碳水化合物（克）、脂肪（克）：『{food_text}』。\n"
                "請只回傳一個標準的 JSON 格式字串，不要包含任何 markdown 語法，格式嚴格如下：\n"
                '{"calories": 120, "protein": 10, "carbs": 30, "fat": 5}'
            )
            with st.spinner("AI 正在深度解析食物營養成分..."):
                try:
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    # 修正：使用 json=payload 自動處理 UTF-8 編碼，防止 latin-1 報錯
                    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": text_prompt}], "temperature": 0.1}
                    response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
                    res_json = response.json()
                    
                    if "choices" in res_json:
                        ai_raw = res_json["choices"][0]["message"]["content"].strip()
                        json_match = re.search(r'\{.*\}', ai_raw, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(0))
                            
                            # 讀取當前這一餐的數值
                            cal = int(data.get("calories", 0))
                            prot = int(data.get("protein", 0))
                            carbs = int(data.get("carbs", 0))
                            fat = int(data.get("fat", 0))
                            
                            # 累加至今日進度
                            st.session_state.total_calories += cal
                            st.session_state.total_protein += prot
                            st.session_state.total_carbs += carbs
                            st.session_state.total_fat += fat
                            
                            # 背景即時自動同步寫入 SQLite 資料庫，不怕斷線重整
                            save_to_db(date_str, weight, st.session_state.total_calories, 
                                       st.session_state.total_protein, st.session_state.total_carbs, st.session_state.total_fat)
                            
                            # ✨ 成功框：同步顯示這份食物的所有熱量與營養素！
                            st.success(
                                f"✨ **解析成功並已即時自動存檔！**\n\n"
                                f"📋 **【此餐食物營養成分】**\n"
                                f"- 🔥 **熱量**：`{cal}` 大卡\n"
                                f"- 🥩 **蛋白質**：`{prot}` 克\n"
                                f"- 🍞 **碳水化合物**：`{carbs}` 克\n"
                                f"- 🥑 **脂肪**：`{fat}` 克"
                            )
                        else:
                            st.error("AI 回傳格式有誤，請再試一次。")
                    else:
                        st.error("Groq 伺服器忙碌中，請稍微再試一次。")
                except Exception as e:
                    st.error(f"解析失敗。錯誤: {e}")
        else:
            st.warning("請先輸入食物描述！")

    st.write("---")
    # ✅ 已修正：拿掉「巨量」兩個字
    st.subheader("📊 今日營養素攝取進度")
    st.metric(label="🔥 總熱量", value=f"{st.session_state.total_calories} / {budget_cal} kcal")
    st.progress(min(st.session_state.total_calories / budget_cal, 1.0) if budget_cal > 0 else 0.0)

    c1, c2, c3 = st.columns(3)
    c1.metric("🥩 蛋白質", f"{st.session_state.total_protein} / {target_protein} g")
    c2.metric("🍞 碳水", f"{st.session_state.total_carbs} / {target_carbs} g")
    c3.metric("🥑 脂肪", f"{st.session_state.total_fat} / {target_fat} g")

    st.write("---")
    if st.button("💾 點我進行今日結算 (看慶祝彩帶)"):
        save_to_db(date_str, weight, st.session_state.total_calories, 
                   st.session_state.total_protein, st.session_state.total_carbs, st.session_state.total_fat)
        st.success(f"✅ {date_str} 的數據已成功結算並更新！")
        
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
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        st.markdown("### 📈 數據視覺化圖表")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("🔥 熱量攝取變化曲線 (大卡)")
            st.line_chart(df['calories'], color="#FF4B4B")
        with chart_col2:
            st.caption("⚖️ 體重變化曲線 (公斤)")
            st.line_chart(df['weight'], color="#0068C9")

        st.markdown("### 📁 匯出成果報告")
        csv = df.to_csv().encode('utf-8-sig')
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

# ----------------- 分頁 3: AI 飲食小助理 (問答對話功能) -----------------
with tab_chat:
    st.subheader("💬 妳的專屬 AI 飲食生活顧問")
    st.caption("不管是不知道外食怎麼挑、還是減脂遇到瓶頸，都可以直接問我喔！")
    
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
                        {"role": "system", "content": "你是一位溫暖、專業且幽默的台灣營養師小助手。請用繁體中文回答使用者的各種減重、飲食、外食挑選疑問，多用鼓勵的口吻。"}
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