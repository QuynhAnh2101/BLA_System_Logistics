# ====== IMPORT ======
import streamlit as st
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import requests
import datetime

# ====== CONFIG ======
st.set_page_config(layout="wide")

# ====== API Keys ======
OWM_API_KEY = "9becc31541efa6466c2a0c25bd05bf39"
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImY4MzU0ZjYyOGYyMDQwNTJhMGE5MTg2MjU1MzhlZmQ3IiwiaCI6Im11cm11cjY0In0="

geolocator = Nominatim(user_agent="BLA_app")

# ====== CSS ======
st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #0f172a, #1e293b); }
.header { background: #111827; padding: 18px; border-radius: 12px; color: #e5e7eb; font-size: 26px; text-align: center; margin-bottom: 20px; }
.card { background: white; padding: 20px; border-radius: 12px; color: black; }
.price { font-size: 32px; color: #2563eb; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='header'>BLA Ride System</div>", unsafe_allow_html=True)

# ====== FUZZY LOGIC ======
distance = ctrl.Antecedent(np.arange(0, 21, 1), 'distance')
traffic = ctrl.Antecedent(np.arange(0, 101, 1), 'traffic')
weather = ctrl.Antecedent(np.arange(0, 101, 1), 'weather')
multiplier = ctrl.Consequent(np.arange(1.0, 3.1, 0.1), 'multiplier')

distance['near'] = fuzz.trapmf(distance.universe, [0, 0, 2, 3])
distance['medium'] = fuzz.trimf(distance.universe, [2, 5, 8])
distance['far'] = fuzz.trapmf(distance.universe, [7, 10, 20, 20])

traffic['clear'] = fuzz.trapmf(traffic.universe, [0, 0, 20, 30])
traffic['dense'] = fuzz.trimf(traffic.universe, [20, 45, 70])
traffic['jam'] = fuzz.trapmf(traffic.universe, [60, 80, 100, 100])

weather['sunny'] = fuzz.trapmf(weather.universe, [0, 0, 20, 40])
weather['rain'] = fuzz.trimf(weather.universe, [30, 50, 70])
weather['storm'] = fuzz.trapmf(weather.universe, [60, 80, 100, 100])

multiplier['low'] = fuzz.trapmf(multiplier.universe, [1.0, 1.0, 1.1, 1.2])
multiplier['medium'] = fuzz.trimf(multiplier.universe, [1.1, 1.5, 1.8])
multiplier['high'] = fuzz.trimf(multiplier.universe, [1.6, 2.0, 2.5])
multiplier['very_high'] = fuzz.trapmf(multiplier.universe, [2.2, 2.5, 3.0, 3.0])

rule1 = ctrl.Rule(traffic['jam'] & weather['storm'], multiplier['very_high'])
rule2 = ctrl.Rule(distance['far'] & traffic['clear'], multiplier['low'])
rule3 = ctrl.Rule(traffic['dense'] & weather['sunny'], multiplier['medium'])

pricing_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
pricing_sim = ctrl.ControlSystemSimulation(pricing_ctrl)

# ====== FUNCTIONS ======
def get_location(address):
    try:
        loc = geolocator.geocode(address, timeout=10)
        return (loc.latitude, loc.longitude) if loc else None
    except:
        return None

def get_weather(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric&lang=vi"
        data = requests.get(url).json()
        desc = data['weather'][0]['description']
        temp = data['main']['temp']
        val = 20 if "nắng" in desc or "clear" in desc else 60 if "mưa" in desc else 90 if "bão" in desc else 40
        return val, f"{desc}, {temp}°C"
    except:
        return 40, "Không lấy được dữ liệu thời tiết"

def get_traffic(time_str):
    try:
        hour = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M").hour
        return (80, "Giờ cao điểm, kẹt xe") if (7 <= hour <= 9 or 17 <= hour <= 19) else (30, "Đường thoáng")
    except:
        return 30, "Đường thoáng"

def get_route(start, end):
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[start[1], start[0]], [end[1], end[0]]]}
    try:
        res = requests.post(url, json=body, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            feat = data["features"][0]
            return ([(lat, lon) for lon, lat in feat["geometry"]["coordinates"]], 
                    feat["properties"]["segments"][0]["distance"] / 1000, 
                    feat["properties"]["segments"][0]["duration"] / 60)
    except:
        pass
    return None, 0, 0

# ====== SIDEBAR ======
with st.sidebar:
    st.markdown("## 📍 Nhập địa chỉ")
    start_in = st.text_input("Điểm đi", "District 10, Ho Chi Minh")
    end_in = st.text_input("Điểm đến", "Thu Duc, Ho Chi Minh")
    time_in = st.text_input("Giờ đi", "2026-04-28 21:30")
    coupon = st.text_input("Mã giảm giá")
    payment = st.selectbox("Thanh toán", ['Tiền mặt','Ví điện tử','Thẻ'])
    vehicle = st.radio("Loại xe", ['2 bánh','4 bánh'])
    
    if st.button("Tính giá"):
        st.session_state["calc"] = True
        st.session_state["s"], st.session_state["e"] = start_in, end_in
        st.session_state["t"], st.session_state["cp"] = time_in, coupon
        st.session_state["pm"], st.session_state["vh"] = payment, vehicle

# ====== MAIN ======
if st.session_state.get("calc", False):
    start = get_location(st.session_state["s"])
    end = get_location(st.session_state["e"])

    if not start or not end:
        st.error("❌ Không tìm thấy địa chỉ")
    else:
        route, d_km, dur = get_route(start, end)
        w_val, w_txt = get_weather(*start)
        t_val, t_txt = get_traffic(st.session_state["t"])

        pricing_sim.input['distance'] = min(d_km, 20)
        pricing_sim.input['traffic'] = t_val
        pricing_sim.input['weather'] = w_val
        pricing_sim.compute()

        mult = pricing_sim.output.get('multiplier', 1.5)
        base = 3000 if st.session_state["vh"] == "2 bánh" else 5000
        price = max(d_km * base * mult, 12000 if st.session_state["vh"] == "2 bánh" else 20000)
        if st.session_state["cp"].strip().lower() == "thu20": price *= 0.8

        c1, c2 = st.columns([1,2])
        with c1:
            st.markdown(f"""<div class="card"><div class="price">{int(price):,} đ</div>
            <p>KC: {round(d_km,1)} km | TG: {int(dur)} phút</p>
            <p>GT: {t_txt} | TT: {w_txt}</p>
            <p>PT: {st.session_state["pm"]}</p></div>""", unsafe_allow_html=True)
        with c2:
            m = folium.Map(location=start, zoom_start=12)
            folium.Marker(start, icon=folium.Icon(color="green")).add_to(m)
            folium.Marker(end, icon=folium.Icon(color="red")).add_to(m)
            if route: folium.PolyLine(route, color="blue", weight=6).add_to(m)
            st_folium(m, width=800, height=500)