import streamlit as st
import random
import requests
import json
import re

# ==========================================
# 1. API 設定 (使用妳最新的金鑰！)
# ==========================================
GROQ_API_KEY = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ==========================================
# 2. 初始化暫存記憶體 (三大營養素)
# ==========================================
if 'total_calories' not in st.session_state:
    st.session_state.total_calories = 0
if 'total_protein' not in st.session_state:
    st.session_state.total_protein = 0
if 'total_carbs' not in st.session_state:
    st.session_state.total_carbs = 0
if 'total_fat' not in st.session_state:
    st.session_state.total_fat = 0
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# 贖罪運動清單
atonement_tasks = ["波比跳 30 下", "開合跳 100 下", "深蹲 50 下", "快走 30 分鐘", "棒式維持 2 分鐘"]

# ==========================================
# 3. 網頁介面排版 & 側邊欄 BMR / TDEE 計算
# ==========================================
st.title("🍽️ 聚餐熱量與三大營養素計算機")
st.caption("結合 Llama 3 深度語意分析 × 個人化 TDEE 每日營養素追蹤系統")

st.sidebar.header("👤 個人身體數值設定")

gender = st.sidebar.radio("性別：", ["女生", "男生"])
age = st.sidebar.number_input("年齡 (歲)：", value=22, min_value=1, max_value=100)
height = st.sidebar.number_input("身高 (公分)：", value=160.0, min_value=50.0, max_value=250.0)
weight = st.sidebar.number_input("體重 (公斤)：", value=55.0, min_value=10.0, max_value=300.0)

activity_level = st.sidebar.selectbox(
    "日常活動量：",
    [
        "久坐缺乏運動 (如：辦公室久坐、常躺著)",
        "輕度活動量 (如：每週運動 1-3 天、日常散步)",
        "中度活動量 (如：每週運動 3-5 天、勞動工作)",
        "高度活動量 (如：每週運動 6-7 天、高強度訓練)"
    ]
)

goal = st.sidebar.radio("減重策略目標：", ["維持體重", "健康減脂 (TDEE - 300)", "積極瘦身 (TDEE - 500)", "乾淨增肌 (TDEE + 200)"])

if gender == "男生":
    bmr = 66.47 + (13.75 * weight) + (5.0 * height) - (6.76 * age)
else:
    bmr = 655.1 + (9.56 * weight) + (1.85 * height) - (4.68 * age)

if "久坐" in activity_level:
    tdee = bmr * 1.2
elif "輕度" in activity_level:
    tdee = bmr * 1.375
elif "中度" in activity_level:
    tdee = bmr * 1.55
else:
    tdee = bmr * 1.725

if "健康減脂" in goal:
    budget_cal = int(tdee - 300)
elif "積極瘦身" in goal:
    budget_cal = int(tdee - 500)
elif "乾淨增肌" in goal:
    budget_cal = int(tdee + 200)
else:
    budget_cal = int(tdee)

target_protein = int((budget_cal * 0.25) / 4)
target_carbs = int((budget_cal * 0.45) / 4)
target_fat = int((budget_cal * 0.30) / 9)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 妳的專屬動態數據")
st.sidebar.info(f"🧬 **基礎代謝 (BMR)：** {int(bmr)} 大卡")
st.sidebar.warning(f"⚡ **每日消耗 (TDEE)：** {int(tdee)} 大卡")
st.sidebar.success(f"🎯 **建議今日預算：** {budget_cal} 大卡")

st.subheader("🍽️ 拍照或上傳今日餐點")

tab1, tab2 = st.tabs(["📷 開啟相機拍照", "📁 從手機/電腦上傳圖片"])

with tab1:
    camera_img = st.camera_input("請將鏡頭對準妳的美味食物：")
    if camera_img:
        st.image(camera_img, caption="📸 成功拍攝食物照片！", use_container_width=True)

with tab2:
    uploaded_file = st.file_uploader("選擇手機相簿中的食物照片：", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file, caption="📁 成功導入相簿相片！", use_container_width=True)

st.markdown("### ✍️ 請補充說明這餐吃了什麼：")
food_text = st.text_input("例如：照片裡是炸雞排一片、半糖去冰紅茶大杯", key="my_nutrition_input", placeholder="請在此處輸入食物描述...")

if st.button("🚀 送出進行 AI 影像與語意視覺化解析", key="nutrition_btn"):
    if food_text:
        text_prompt = (
            f"妳是外食營養分析專家。請估算這段食物描述的總熱量、蛋白質、碳水化合物、脂肪：『{food_text}』。\n"
            "請只回傳一個標準的 JSON 格式字串，不要包含任何 markdown 語法，格式嚴格如下：\n"
            '{"calories": 120, "protein": 0, "carbs": 30, "fat": 0}'
        )
        
        with st.spinner("Llama 3 正在對齊影像與進行巨量營養素拆解..."):
            try:
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile", 
                    "messages": [{"role": "user", "content": text_prompt}],
                    "temperature": 0.1
                }
                
                response = requests.post(API_URL, headers=headers, json=payload)
                res_json = response.json()
                
                if "choices" in res_json:
                    ai_raw = res_json["choices"][0]["message"]["content"].strip()
                    json_match = re.search(r'\{.*\}', ai_raw, re.DOTALL)
                    
                    if json_match:
                        data = json.loads(json_match.group(0))
                        cal = int(data.get("calories", 0))
                        protein = int(data.get("protein", 0))
                        carbs = int(data.get("carbs", 0))
                        fat = int(data.get("fat", 0))
                        
                        st.session_state.total_calories += cal
                        st.session_state.total_protein += protein
                        st.session_state.total_carbs += carbs
                        st.session_state.total_fat += fat
                        
                        st.success("🤖 **AI 解析成功！此餐營養成分如下：**")
                        st.markdown(f"🔥 熱量：`{cal}` 大卡 | 🥩 蛋白質：`{protein}` 克 | 🍞 碳水：`{carbs}` 克 | 🥑 脂肪：`{fat}` 克")
                    else:
                        st.error(f"AI 回傳格式有誤：{ai_raw}")
                else:
                    st.error("Groq 伺服器回傳錯誤。")
            except Exception as e:
                st.error(f"解析失敗。錯誤訊息: {e}")
    else:
        st.warning("請先輸入食物的描述文字！")

# --- 4. 數據看板與三大營養素視覺化 ---
st.write("---")
st.subheader("📊 今日巨量營養素攝取進度")

st.metric(label="🔥 今日總熱量攝取", value=f"{st.session_state.total_calories} / {budget_cal} 大卡")
cal_progress = min(st.session_state.total_calories / budget_cal, 1.0) if budget_cal > 0 else 0.0
st.progress(cal_progress)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="🥩 蛋白質", value=f"{st.session_state.total_protein} / {target_protein} g")
    p_prog = min(st.session_state.total_protein / target_protein, 1.0) if target_protein > 0 else 0.0
    st.progress(p_prog)
with col2:
    st.metric(label="🍞 碳水化合物", value=f"{st.session_state.total_carbs} / {target_carbs} g")
    c_prog = min(st.session_state.total_carbs / target_carbs, 1.0) if target_carbs > 0 else 0.0
    st.progress(c_prog)
with col3:
    st.metric(label="🥑 脂肪", value=f"{st.session_state.total_fat} / {target_fat} g")
    f_prog = min(st.session_state.total_fat / target_fat, 1.0) if target_fat > 0 else 0.0
    st.progress(f_prog)

st.write("---")
if st.button("🏁 今日餐點結算"):
    diff = st.session_state.total_calories - budget_cal
    if diff <= 0:
        st.balloons()
        st.success("🎉 太棒了！今天熱量完美控制在預算內！")
    else:
        st.warning(f"⚠️ 糟糕！今日熱量超標了 {diff} 大卡！")
        punishments = random.sample(atonement_tasks, 2)
        st.error("🚨 啟動動態贖罪機制！請完成以下隨機任務：")
        for i, task in enumerate(punishments, 1):
            st.write(f"**{i}. {task}**")

if st.button("🗑️ 清空今日數據重新計算"):
    st.session_state.total_calories = 0
    st.session_state.total_protein = 0
    st.session_state.total_carbs = 0
    st.session_state.total_fat = 0
    st.rerun()

# --- 6. AI 飲食諮詢對話框 ---
st.subheader("💬 減脂小助手線上諮詢")
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_query := st.chat_input("例如：我今天蛋白質還缺 20 克，有什麼超商宵夜推薦嗎？"):
    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    sys_msg = (
        "你是一個溫柔且專業的台灣減脂小助手。"
        f"使用者今天的每日熱量吃了 {st.session_state.total_calories}/{budget_cal} 大卡，"
        f"蛋白質吃了 {st.session_state.total_protein}克，"
        f"碳水吃了 {st.session_state.total_carbs}克，"
        f"脂肪吃了 {st.session_state.total_fat}克。"
        "請根據他目前缺少的營養素給予建議，並使用繁體中文回答。"
    )
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.7
        }
        response = requests.post(API_URL, headers=headers, json=payload)
        res_json = response.json()
        if "choices" in res_json:
            ai_reply = res_json["choices"][0]["message"]["content"]
            with st.chat_message("assistant"):
                st.markdown(ai_reply)
            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
    except Exception as e:
        st.error(f"小助手暫時離線中... 錯誤: {e}")