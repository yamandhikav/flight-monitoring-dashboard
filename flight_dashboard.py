import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- SETUP HALAMAN ---
st.set_page_config(page_title="Flight Control Center", page_icon="🛫", layout="wide")

# --- CUSTOM CSS (UI SUPERIOR) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    .stApp {
        background-color: #f3f6f9;
    }
    
    /* Header Styling */
    .main-header {
        background: linear-gradient(135deg, #002855 0%, #004b8d 100%);
        padding: 30px;
        border-radius: 20px;
        color: white;
        box-shadow: 0 10px 20px rgba(0, 40, 85, 0.15);
        margin-bottom: 30px;
    }
    .header-title { font-size: 2.5rem; font-weight: 900; letter-spacing: -1px; margin-bottom: 5px; }
    .header-sub { font-size: 1rem; color: #93c5fd; font-weight: 600; }
    
    /* Card Styling (Soft UI) */
    .flight-card {
        background: #ffffff;
        padding: 30px;
        border-radius: 24px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.5);
        margin-bottom: 40px;
        transition: transform 0.3s ease;
    }
    .flight-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 40px -10px rgba(0,0,0,0.12);
    }
    
    /* Typography di dalam Card */
    .airline-badge {
        background: rgba(37, 99, 235, 0.1);
        color: #2563eb;
        padding: 6px 16px;
        border-radius: 50px;
        font-size: 0.75rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    .flight-number {
        font-size: 3rem;
        font-weight: 900;
        color: #0f172a;
        margin-top: 15px;
        line-height: 1;
        background: -webkit-linear-gradient(45deg, #0f172a, #334155);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .schedule-info {
        font-size: 1.1rem;
        color: #64748b;
        font-weight: 600;
        margin-top: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Mempercantik Tabel Pandas Bawaan Streamlit */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Jadwal Asli (Baseline)
SCHEDULED_DEPARTURE = {
    "QZ254": "12:15",
    "XJ600": "23:30",
    "XJ607": "21:15",
    "QZ251": "11:05"
}

# Mapping Nama Maskapai untuk UI
AIRLINES = {
    "QZ254": "Indonesia AirAsia",
    "XJ600": "Thai AirAsia X",
    "XJ607": "Thai AirAsia X",
    "QZ251": "Indonesia AirAsia"
}

def calculate_delay_status(flight_code, actual_dep_str):
    if flight_code not in SCHEDULED_DEPARTURE: return "✅ On Time"
        
    time_match = re.search(r'(\d{1,2}):(\d{2})\s*([AaPp][Mm])?', actual_dep_str)
    if not time_match: return "✅ On Time"
        
    hr = int(time_match.group(1))
    mn = int(time_match.group(2))
    ampm = time_match.group(3)
    
    if ampm:
        ampm = ampm.upper()
        if ampm == 'PM' and hr < 12: hr += 12
        if ampm == 'AM' and hr == 12: hr = 0
        
    actual_minutes = (hr * 60) + mn
    sched_hr, sched_mn = map(int, SCHEDULED_DEPARTURE[flight_code].split(':'))
    sched_minutes = (sched_hr * 60) + sched_mn
    
    if actual_minutes < sched_minutes and (sched_minutes - actual_minutes) > 720:
        actual_minutes += 1440
    elif actual_minutes > sched_minutes and (actual_minutes - sched_minutes) > 720:
        actual_minutes -= 1440
        
    diff = actual_minutes - sched_minutes
    
    if diff >= 60: return f"🔴 DELAYED ({diff//60}h {diff%60}m)"
    elif diff >= 15: return f"🟡 Minor Delay ({diff}m)"
    elif diff < -15: return f"🟢 Early ({abs(diff)}m)"
    else: return "✅ On Time"

@st.cache_data(ttl=300)
def get_flightaware_history(flight_code):
    fa_code = flight_code.replace("QZ", "AWQ").replace("XJ", "TAX")
    url = f"https://www.flightaware.com/live/flight/{fa_code}/history"
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code in [403, 429]: return "BLOCKED"
            
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find("table", class_="prettyTable")
        if not table: return "NO_DATA"
            
        rows = table.find_all("tr")[1:] 
        past_flights = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 6: continue
                
            date_str = cols[0].get_text(strip=True)
            origin = cols[2].get_text(strip=True)
            dest = cols[3].get_text(strip=True)
            departure = cols[4].get_text(strip=True)
            arrival = cols[5].get_text(strip=True)
            
            if "Scheduled" in departure or ("Delayed" in departure and ":" not in departure): continue
                
            status_calc = calculate_delay_status(flight_code, departure)
                
            past_flights.append({
                "Date": date_str,
                "Route": f"{origin} ➔ {dest}",
                "Actual Dep.": departure,
                "Actual Arr.": arrival,
                "Status": status_calc
            })
            
            if len(past_flights) == 7: break
                
        return past_flights
    except:
        return "ERROR"

# --- RENDER UI ---

# 1. HEADER HERO SECTION
st.markdown(f"""
    <div class="main-header">
        <div class="header-title">✈️ Master Flight Deck</div>
        <div class="header-sub">Real-time schedule accuracy monitoring • Synced with FlightAware API</div>
    </div>
""", unsafe_allow_html=True)

# 2. TOP METRICS OVERVIEW
m1, m2, m3, m4 = st.columns(4)
m1.metric("Active Tracked Flights", "4 Aircrafts")
m2.metric("Data Source", "FlightAware Live")
m3.metric("Last Sync", datetime.now().strftime("%H:%M:%S WIB"))
with m4:
    if st.button('🔄 Sync Radar Now', use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# 3. FLIGHT CARDS (VERTICAL LAYOUT)
target_flights = ["QZ254", "XJ600", "XJ607", "QZ251"]

for fn in target_flights:
    # Buka kontainer kartu
    st.markdown('<div class="flight-card">', unsafe_allow_html=True)
    
    col_info, col_spacer, col_data = st.columns([1.5, 0.2, 4])
    
    # Kolom Kiri: Informasi Pesawat yang Elegan
    with col_info:
        st.markdown(f'<span class="airline-badge">{AIRLINES[fn]}</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="flight-number">{fn}</div>', unsafe_allow_html=True)
        st.markdown(f'''
            <div class="schedule-info">
                ⏱️ Sched. Dep: <b>{SCHEDULED_DEPARTURE[fn]} WIB</b>
            </div>
        ''', unsafe_allow_html=True)
        
        # Tambahan info kecil
        st.caption("Monitoring 7 past flights. Delay tolerance: 60 mins.")
    
    # Kolom Kanan: Tabel Data
    with col_data:
        with st.spinner('📡 Establishing satellite connection...'):
            data = get_flightaware_history(fn)
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
                
                # Fungsi styling pandas yang lebih modern
                def style_status(val):
                    if '🔴' in val: return 'color: white; font-weight: 800; background-color: #ef4444; border-radius: 4px;'
                    if '🟡' in val: return 'color: #92400e; font-weight: 800; background-color: #fef08a;'
                    if '🟢' in val: return 'color: #064e3b; font-weight: 800; background-color: #a7f3d0;'
                    if '✅' in val: return 'color: #065f46; font-weight: 800; background-color: #d1fae5;'
                    return ''
                
                # Set dataframe config untuk menyembunyikan header index
                styled_df = df.style.map(style_status, subset=['Status'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
            elif data == "BLOCKED":
                st.error("🚨 Anti-Bot Triggered. Data access blocked by Cloudflare.")
            elif data == "NO_DATA":
                st.info("Penerbangan belum beroperasi atau data tidak ditemukan.")
            else:
                st.error("Gagal menarik data dari server. Periksa koneksi.")
                
    st.markdown('</div>', unsafe_allow_html=True)