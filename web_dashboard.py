import tempfile
import streamlit as st
from datetime import date
from pathlib import Path
from garminconnect import Garmin
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Garmin 24/7 Dashboard", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #1E1E2E;
        border: 1px solid #313244;
        padding: 15px;
        border-radius: 12px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Performance & Triathlon Dashboard (24/7 Live)")

def init_garmin():
    client = Garmin()
    # Als hij online in de Cloud draait, leest hij je token uit de Streamlit kluis:
    if "GARMIN_TOKENS" in st.secrets:
        tmp_dir = Path(tempfile.gettempdir()) / ".garminconnect"
        tmp_dir.mkdir(exist_ok=True)
        token_file = tmp_dir / "garmin_tokens.json"
        token_file.write_text(st.secrets["GARMIN_TOKENS"], encoding="utf-8")
        client.login(str(tmp_dir))
    else:
        # Anders pakt hij gewoon je laptop-map:
        token_dir = str(Path.home() / ".garminconnect")
        client.login(token_dir)
    return client

@st.cache_data(ttl=900)  # Ververst automatisch elke 15 minuten
def fetch_all_data():
    client = init_garmin()
    today = date.today().isoformat()
    return {
        "today": today,
        "stats": client.get_stats(today),
        "hr": client.get_heart_rates(today),
        "sleep": client.get_sleep_data(today),
        "predictions": client.get_race_predictions(),
        "activities": client.get_activities(0, 40)
    }

if st.button("🔄 Nu Verversen"):
    st.cache_data.clear()

with st.spinner("Live Garmin data synchroniseren..."):
    data = fetch_all_data()
    today = data["today"]
    stats = data["stats"]
    hr_data = data["hr"]
    sleep_data = data["sleep"]
    predictions = data["predictions"]
    activities = data["activities"]

# --- RIJ 1: TOP METRICS ---
col1, col2, col3, col4, col5 = st.columns(5)
steps = stats.get("totalSteps") or 0
step_goal = stats.get("dailyStepGoal") or 10000
col1.metric("👣 Stappen", f"{steps:,}", f"{steps - step_goal:,} t.o.v. doel")
col2.metric("🔥 Actieve Kcal", f"{stats.get('activeKilocalories') or 0} kcal", f"Totaal: {stats.get('totalKilocalories') or 0}")
col3.metric("❤️ Rusthartslag", f"{hr_data.get('restingHeartRate') or 'n/a'} bpm", f"Max: {hr_data.get('maxHeartRate') or 'n/a'} bpm")

sleep_sec = sleep_data.get("dailySleepDTO", {}).get("sleepTimeSeconds") or 0
sleep_score = sleep_data.get("dailySleepDTO", {}).get("sleepScores", {}).get("overall", {}).get("value") or "n/a"
col4.metric("😴 Slaap vannacht", f"{round(sleep_sec / 3600, 1)} uur", f"Score: {sleep_score}")
col5.metric("🧘 Stress Niveau", f"{stats.get('averageStressLevel') or 'n/a'} / 100", "Dagelijks gemiddelde")

st.divider()

# --- RIJ 2: GAUGE METERS & RACE PREDICTOR ---
left_col, mid_col, right_col = st.columns([1, 1, 1.3])

with left_col:
    bb_val = stats.get("bodyBatteryMostRecentValue") or 0
    fig_bb = go.Figure(go.Indicator(
        mode="gauge+number", value=bb_val, title={'text': "🔋 Body Battery"},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00CC96"},
               'steps': [{'range': [0, 30], 'color': "#EF553B"}, {'range': [30, 70], 'color': "#FECB52"}, {'range': [70, 100], 'color': "#00CC96"}]}
    ))
    fig_bb.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_bb, use_container_width=True)

with mid_col:
    pct_steps = min(int((steps / step_goal) * 100), 100) if step_goal else 0
    fig_steps = go.Figure(go.Indicator(
        mode="gauge+number", value=pct_steps, number={'suffix': "%"}, title={'text': "🎯 Stappendoel"},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#636EFA"}}
    ))
    fig_steps.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_steps, use_container_width=True)

with right_col:
    st.subheader("🏁 Race Voorspellingen")
    if predictions:
        def fmt_time(sec):
            if not sec: return "n/a"
            h, r = divmod(int(sec), 3600)
            m, s = divmod(r, 60)
            return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
        r1, r2 = st.columns(2)
        r1.metric("🏃 5 KM", fmt_time(predictions.get("time5K")))
        r2.metric("🏃 10 KM", fmt_time(predictions.get("time10K")))
        r1.metric("🏅 Halve Marathon", fmt_time(predictions.get("timeHalfMarathon")))
        r2.metric("🏆 Marathon", fmt_time(predictions.get("timeMarathon")))

st.divider()

# --- RIJ 3: TRAINING ANALYSE ---
if activities:
    act_list = []
    for act in activities:
        act_list.append({
            "Datum": act.get("startTimeLocal", "")[:10],
            "Naam": act.get("activityName", "Training"),
            "Sport": act.get("activityType", {}).get("typeKey", "overig").replace("_", " ").title(),
            "Afstand (km)": round((act.get("distance") or 0) / 1000, 2),
            "Duur (min)": round((act.get("duration") or 0) / 60, 1),
            "Gem. HR": act.get("averageHR") or 0,
            "Max HR": act.get("maxHR") or 0,
            "Gem. Power (W)": act.get("avgPower") or 0,
            "Calorieën": act.get("calories") or 0
        })
    df = pd.DataFrame(act_list)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.plotly_chart(px.bar(df, x="Datum", y="Afstand (km)", color="Sport", title="Afstand per Training (Laatste 40 sessies)"), use_container_width=True)
    with c2:
        st.plotly_chart(px.pie(df, names="Sport", values="Duur (min)", hole=0.4, title="Tijdsbesteding per Sport"), use_container_width=True)
    st.dataframe(df, use_container_width=True)

with st.expander("🤖 Ruwe JSON-data (voor Claude)"):
    st.json(data)