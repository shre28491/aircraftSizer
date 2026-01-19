import streamlit as st
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import aerosandbox as asb
import aerosandbox.numpy as np
import folium
from streamlit_folium import st_folium
from folium.plugins import Geocoder
from streamlit_searchbox import st_searchbox
from streamlit import cache_data
from aerosandbox.geometry import WingXSec
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from geopy.exc import GeocoderTimedOut
import time

st.set_page_config(page_title="Electric Airplane Sizing Tool", layout="wide")

# Custom styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        border-bottom: 3px solid #667eea;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>✈️ Electric Airplane Sizing Tool</h1><p>Design optimized aircraft for regional electric aviation</p></div>', unsafe_allow_html=True)

# Common cities database for fallback search (Tier 1 & 2 cities in India & Africa)
COMMON_AIRPORTS = {
    # INDIA - TIER 1 CITIES (8)
    "DEL": (28.5355, 77.1099, "Delhi"),
    "BOM": (19.0896, 72.8656, "Mumbai"),
    "BLR": (13.1939, 77.7064, "Bangalore"),
    "HYD": (17.3850, 78.4867, "Hyderabad"),
    "MAA": (12.9896, 80.1693, "Chennai"),
    "CCU": (22.6542, 88.4480, "Kolkata"),
    "PNQ": (18.5793, 73.8143, "Pune"),
    "AGX": (23.0225, 72.5714, "Ahmedabad"),
    
    # INDIA - TIER 2 CITIES (11)
    "JAI": (26.9124, 75.7873, "Jaipur"),
    "LKO": (26.8467, 80.9462, "Lucknow"),
    "CHD": (30.7333, 76.7794, "Chandigarh"),
    "IDR": (22.7196, 75.8577, "Indore"),
    "CJB": (11.0026, 76.6955, "Coimbatore"),
    "COK": (10.1924, 76.2597, "Kochi"),
    "SRT": (21.1702, 72.8311, "Surat"),
    "NAG": (21.1458, 79.0882, "Nagpur"),
    "VTZ": (17.6869, 83.2185, "Visakhapatnam"),
    "BHO": (23.1815, 79.9864, "Bhopal"),
    "PY": (12.0, 79.8330, "Pondicherry"),
    
    # AFRICA - TIER 1 CITIES (9)
    "JNB": (-24.6282, 28.2372, "Johannesburg"),
    "LOS": (6.5244, 3.3519, "Lagos"),
    "CAI": (30.0444, 31.2357, "Cairo"),
    "CPT": (-33.9249, 18.4241, "Cape Town"),
    "ACC": (5.6037, -0.2167, "Accra"),
    "DSS": (14.6749, -17.1360, "Dakar"),
    "NBO": (-1.2921, 36.7726, "Nairobi"),
    "ADD": (9.0320, 38.7469, "Addis Ababa"),
    "CMN": (33.5731, -7.5898, "Casablanca"),
    
    # AFRICA - TIER 2 CITIES (10)
    "FIH": (-4.3276, 15.3136, "Kinshasa"),
    "DAR": (-6.8016, 39.2083, "Dar es Salaam"),
    "KRT": (15.5007, 32.5599, "Khartoum"),
    "EBB": (0.0260, 32.4458, "Kampala"),
    "ABJ": (5.5471, -0.5567, "Abidjan"),
    "DLA": (3.8667, 11.5167, "Douala"),
    "LAD": (-8.8383, 13.2344, "Luanda"),
    "MPM": (-23.8650, 35.3180, "Maputo"),
    "GBE": (-24.6282, 25.9231, "Gaborone"),
    "RUN": (-20.8692, 55.4920, "Port Louis"),
    
    # INTERNATIONAL HUBS
    "DXB": (25.2528, 55.3644, "Dubai"),
}

geolocator = Nominatim(user_agent="electric_airplane_sizer_final", timeout=5)

# Default routes: Bengaluru hub with 500 km radius destinations
if "routes" not in st.session_state:
    st.session_state.routes = [
        {
            "origin_name": "Bengaluru",
            "origin_lat": 13.1939,
            "origin_lon": 77.7064,
            "dest_name": "Kochi",
            "dest_lat": 10.1924,
            "dest_lon": 76.2597,
            "dist_km": 350
        },
        {
            "origin_name": "Bengaluru",
            "origin_lat": 13.1939,
            "origin_lon": 77.7064,
            "dest_name": "Coimbatore",
            "dest_lat": 11.0026,
            "dest_lon": 76.6955,
            "dist_km": 270
        },
        {
            "origin_name": "Bengaluru",
            "origin_lat": 13.1939,
            "origin_lon": 77.7064,
            "dest_name": "Chennai",
            "dest_lat": 12.9896,
            "dest_lon": 80.1693,
            "dist_km": 340
        },
        {
            "origin_name": "Bengaluru",
            "origin_lat": 13.1939,
            "origin_lon": 77.7064,
            "dest_name": "Hyderabad",
            "dest_lat": 17.3850,
            "dest_lon": 78.4867,
            "dist_km": 560
        }
    ]

@cache_data
def search_locations(query: str):
    query = query.strip()
    if len(query) < 2:
        return []
    
    results = []
    query_upper = query.upper()
    seen_coordinates = set()
    
    # Stage 1: Exact IATA code match
    if query_upper in COMMON_AIRPORTS:
        lat, lon, name = COMMON_AIRPORTS[query_upper]
        results.append((f"✈️ {name} ({query_upper})", (lat, lon, name)))
        seen_coordinates.add((round(lat, 2), round(lon, 2)))
    
    # Stage 2: Fuzzy matching against IATA codes
    for code, (lat, lon, name) in COMMON_AIRPORTS.items():
        if query_upper in name.upper() or code.startswith(query_upper):
            coord_key = (round(lat, 2), round(lon, 2))
            if coord_key not in seen_coordinates:
                results.append((f"✈️ {name} ({code})", (lat, lon, name)))
                seen_coordinates.add(coord_key)
                if len(results) >= 5:
                    break
    
    # Stage 3: Always try Nominatim geocoding (to find ANY location on the map)
    try:
        effective_query = query
        if len(query) == 3 and query.isalpha():
            effective_query = query + " city"
        
        locations = geolocator.geocode(
            effective_query,
            exactly_one=False,
            limit=10,
            addressdetails=True,
            timeout=5
        )
        
        if locations:
            seen_cities = set()
            for loc in locations:
                try:
                    raw = loc.raw
                    addr = raw.get('address', {})
                    city = (
                        addr.get('city') or
                        addr.get('town') or
                        addr.get('village') or
                        addr.get('state_district') or
                        addr.get('county') or
                        addr.get('state') or
                        raw.get('display_name', '').split(',')[0].strip()
                    )
                    if city not in seen_cities and city:
                        seen_cities.add(city)
                        coord_key = (round(loc.latitude, 2), round(loc.longitude, 2))
                        
                        # Only add if not already in results from IATA database
                        if coord_key not in seen_coordinates:
                            is_airport = (
                                'airport' in raw.get('category', '').lower() or
                                'aerodrome' in raw.get('type', '').lower() or
                                'airport' in raw.get('display_name', '').lower()
                            )
                            display_name = f"✈️ {city}" if is_airport else f"🏙️ {city}"
                            value = (loc.latitude, loc.longitude, city)
                            results.append((display_name, value))
                            seen_coordinates.add(coord_key)
                            
                            if len(results) >= 10:
                                break
                except Exception:
                    continue
    except (GeocoderTimedOut, Exception):
        pass
    
    return results

st.markdown('<h3 class="section-header">📍 Define Your Routes</h3>', unsafe_allow_html=True)
st.info("🔍 Type IATA code (e.g., BOM, DEL, BLR, JNB) or city name. Codes auto-search as 'airport'.")

col1, col2, col3 = st.columns([3.5, 3.5, 2])

with col1:
    st.markdown("**✈️ Origin**")
    selected_origin = st_searchbox(
        search_locations,
        placeholder="e.g., DEL or Delhi",
        key="origin_sb"
    )

with col2:
    st.markdown("**🎯 Destination**")
    selected_dest = st_searchbox(
        search_locations,
        placeholder="e.g., BOM or Mumbai",
        key="dest_sb"
    )

with col3:
    st.write("##")
    if st.button("🔄 Clear", use_container_width=True):
        st.session_state.origin_sb = None
        st.session_state.dest_sb = None
        st.rerun()

if selected_origin and selected_dest:
    o_lat, o_lon, o_city = selected_origin
    d_lat, d_lon, d_city = selected_dest
    dist_km = geodesic((o_lat, o_lon), (d_lat, d_lon)).km
    
    col_info, col_btn = st.columns([4, 1])
    with col_info:
        st.success(f"✓ {o_city} → {d_city} ({dist_km:.0f} km)")
    with col_btn:
        if st.button("➕ Add Route", use_container_width=True):
            route_dict = {
                "origin_name": o_city,
                "origin_lat": o_lat,
                "origin_lon": o_lon,
                "dest_name": d_city,
                "dest_lat": d_lat,
                "dest_lon": d_lon,
                "dist_km": round(dist_km)
            }
            st.session_state.routes.append(route_dict)
            st.rerun()

# Routes list and Map
if st.session_state.routes:
    st.markdown('<h3 class="section-header">📋 Your Routes</h3>', unsafe_allow_html=True)
    
    route_cols = st.columns([6, 1])
    with route_cols[0]:
        for i, r in enumerate(st.session_state.routes):
            st.markdown(f"**Route {i+1}:** {r['origin_name']} → {r['dest_name']} ({r['dist_km']} km)")
    
    col_clear = st.columns([6, 1])[1]
    with col_clear:
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.routes = []
            st.rerun()
    
    # Calculate longest leg
    max_dist_km = max(r['dist_km'] for r in st.session_state.routes)
    max_route_idx = [r['dist_km'] for r in st.session_state.routes].index(max_dist_km)
    max_route = st.session_state.routes[max_route_idx]
    
    st.markdown(f'<div class="metric-card"><strong>📏 Longest Leg (Constrains Design):</strong> {max_route["origin_name"]} → {max_route["dest_name"]} ({max_dist_km} km) 🎯</div>', unsafe_allow_html=True)
    
    # Map and Configuration side by side
    st.markdown('<h3 class="section-header">🗺️ Route Map & ⚙️ Aircraft Configuration</h3>', unsafe_allow_html=True)
    
    map_col, config_col = st.columns([1.2, 1])
    
    # Map
    with map_col:
        default_center = [20.5937, 78.9629]
        m = folium.Map(location=default_center, zoom_start=4, tiles="OpenStreetMap")
        Geocoder(collapsed=False, position='topleft').add_to(m)
        
        unique_points = {}
        for r in st.session_state.routes:
            for lat_k, lon_k, name_k, is_origin in [
                ('origin_lat', 'origin_lon', 'origin_name', True),
                ('dest_lat', 'dest_lon', 'dest_name', False)
            ]:
                lat = r[lat_k]
                lon = r[lon_k]
                name = r[name_k]
                key = f"{round(lat, 4)}_{round(lon, 4)}"
                if key not in unique_points:
                    unique_points[key] = {'lat': lat, 'lon': lon, 'name': name}
                    folium.Marker(
                        [lat, lon],
                        tooltip=name,
                        icon=folium.Icon(color="blue" if is_origin else "green", icon="plane" if is_origin else "flag-checkered", prefix='fa')
                    ).add_to(m)

            folium.PolyLine(
                [[r['origin_lat'], r['origin_lon']], [r['dest_lat'], r['dest_lon']]],
                color="red",
                weight=3,
                opacity=0.7,
                tooltip=f"{r['origin_name']} → {r['dest_name']}: {r['dist_km']} km"
            ).add_to(m)

        all_lats = []
        all_lons = []
        for r in st.session_state.routes:
            all_lats.extend([r['origin_lat'], r['dest_lat']])
            all_lons.extend([r['origin_lon'], r['dest_lon']])
        
        if all_lats:
            m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])
        
        st_folium(m, width=500, height=500)
    
    # Configuration Panel
    with config_col:
        st.markdown("### Aircraft Configuration")
        
        mode = st.radio("**Aircraft Mode**", ["Passenger", "Cargo-only", "Mixed", "Hybrid (2E + 2TP)"])

        if mode == "Passenger":
            num_pass = st.number_input("👥 Passengers", 1, 20, 4)
            cargo_kg = st.number_input("📦 Cargo (kg)", 0, 1000, 50)
            is_hybrid = False
        elif mode == "Cargo-only":
            num_pass = 0
            cargo_kg = st.number_input("📦 Cargo (kg)", 0, 3000, 500)
            is_hybrid = False
        elif mode == "Mixed":
            num_pass = st.number_input("👥 Passengers", 0, 20, 3)
            cargo_kg = st.number_input("📦 Cargo (kg)", 0, 2000, 100)
            is_hybrid = False
        else:  # Hybrid
            num_pass = st.number_input("👥 Passengers", 1, 20, 4)
            cargo_kg = st.number_input("📦 Cargo (kg)", 0, 1000, 50)
            is_hybrid = True
        
        st.markdown("---")
        st.markdown("**Performance**")
        cruise_speed_kmh = st.slider("⚡ Cruise Speed (km/h)", 150, 400, 200)
        cruise_altitude_ft = st.slider("📊 Altitude (ft)", 3000, 16000, 6000, 500)
        cruise_altitude_m = cruise_altitude_ft * 0.3048  # Convert feet to meters
        
        st.markdown("---")
        st.markdown("**Power & Energy**")
        battery_density = st.slider("🔋 Battery Density (Wh/kg)", 200, 600, 240)
        efficiency = st.slider("⚙️ Efficiency", 0.70, 0.95, 0.85, 0.01)
        peak_to_cruise_ratio = st.slider("📈 Peak/Cruise Ratio", 1.5, 3.0, 1.8, 0.1)
        desired_charge_time_h = st.slider("⏱️ Charge Time (h)", 0.3, 4.0, 1.5, 0.1)
        
        st.markdown("---")
        st.markdown("**Aerodynamics & Weight**")
        parasite_cd0 = st.slider("🌪️ Parasite CD₀", 0.015, 0.040, 0.022, 0.001)
        empty_base_kg = st.number_input("⚖️ Empty Weight (kg)", 500, 4000, 900)
        pass_weight_kg = st.number_input("👤 Per Passenger (kg)", 80, 120, 100)
        
        # Hybrid-specific parameters
        if is_hybrid:
            st.markdown("---")
            st.markdown("**Hybrid Powertrain**")
            st.info("⚡ 2 Electric motors for takeoff/climb | 🔥 2 Turboprops for efficient cruise")
            turboprop_cruise_fraction = st.slider("🔥 Turboprop Power % (Cruise)", 50, 90, 75)
            cruise_fuel_consumption_kgh = st.slider("⛽ Fuel Consumption (kg/h at cruise)", 10, 50, 25)
            fuel_energy_density_mj_kg = 43.0  # Jet fuel
else:
    max_dist_km = 0
    st.info("👈 Add routes above to get started")

# Updated Calculate Optimal Sizing block (heuristic approach - no optimization)
if max_dist_km > 0 and st.button("🚀 Calculate Aircraft Sizing", use_container_width=True):
    with st.spinner("⏳ Computing sizing..."):
        distance_m = max_dist_km * 1000
        v_cruise_ms = cruise_speed_kmh / 3.6
        payload_kg = num_pass * pass_weight_kg + cargo_kg
        parachute_mass_kg = 60

        # Heuristic sizing (no CasADi optimization - avoids solver issues)
        atm = asb.Atmosphere(altitude=cruise_altitude_m)
        rho = float(atm.density())

        # Step 1: Estimate cruise power
        # Power = (Drag × Velocity) / Efficiency
        # For a given wing area and weight, CL = Weight / (0.5 * rho * v^2 * S)
        # Start with a reasonable estimate of wing area
        
        wing_area_guess = 12 + payload_kg / 25  # m² - empirical formula
        total_mass_guess = empty_base_kg + payload_kg + parachute_mass_kg + 200  # +200 kg for battery guess
        weight_n = total_mass_guess * 9.81
        
        # CL at cruise
        cl_cruise = weight_n / (0.5 * rho * v_cruise_ms**2 * wing_area_guess)
        cl_cruise = np.clip(cl_cruise, 0.25, 1.3)
        
        # Induced drag coefficient
        oswald_e = 0.82
        ar_guess = 12
        cd_induced = (cl_cruise**2) / (np.pi * ar_guess * oswald_e)
        cd_total = cd_induced + parasite_cd0 + 0.003
        
        # Drag and power
        drag_n = cd_total * 0.5 * rho * v_cruise_ms**2 * wing_area_guess
        p_mech_cruise_w = drag_n * v_cruise_ms
        p_elec_cruise_w = p_mech_cruise_w / efficiency
        
        # Energy budgets - top level calculation
        e_cruise_j = p_elec_cruise_w * (distance_m / v_cruise_ms)
        e_pot_j = total_mass_guess * 9.81 * cruise_altitude_m
        e_climb_j = e_pot_j * 2.2 / efficiency
        e_descent_j = e_pot_j * 0.3 / efficiency  # ~30% of climb energy
        e_taxi_j = 8e3 * 3600  # ~8 kWh for taxi
        e_fixed_j = 20e3 * 3600
        
        e_mission_j = e_cruise_j + e_climb_j + e_descent_j + e_taxi_j + e_fixed_j
        e_required_j = e_mission_j * 1.4  # 40% margin
        e_gross_j = e_required_j / 0.85  # Usable fraction 85%
        
        battery_kwh = e_gross_j / 3.6e6
        battery_mass_kg = (battery_kwh * 1000) / battery_density
        
        # Step 2: Refine total mass and wing area iteratively
        for iteration in range(3):
            # For hybrid: account for fuel tank mass
            fuel_mass_kg = 0
            if is_hybrid:
                # Estimate fuel needed for cruise on longest leg
                cruise_time_h = distance_m / v_cruise_ms / 3600
                turboprop_power_w = p_elec_cruise_w * (turboprop_cruise_fraction / (100 - turboprop_cruise_fraction))
                fuel_needed_kg = cruise_fuel_consumption_kgh * cruise_time_h * 1.3  # 30% reserve
                fuel_mass_kg = fuel_needed_kg
                # Add fuel tank structure (typically 10-15% of fuel mass)
                fuel_tank_mass_kg = fuel_mass_kg * 0.12
            else:
                fuel_mass_kg = 0
                fuel_tank_mass_kg = 0
            
            total_mass_kg = empty_base_kg + payload_kg + battery_mass_kg + parachute_mass_kg + fuel_mass_kg + fuel_tank_mass_kg
            weight_n = total_mass_kg * 9.81
            
            # Adjust wing area to maintain reasonable CL
            target_cl = 0.6  # Optimal cruise CL range
            wing_area = weight_n / (0.5 * rho * target_cl * v_cruise_ms**2)
            wing_area = np.clip(wing_area, 10, 75)
            
            # Recalculate power and energy
            cl_new = weight_n / (0.5 * rho * v_cruise_ms**2 * wing_area)
            cd_induced_new = (cl_new**2) / (np.pi * ar_guess * oswald_e)
            cd_total_new = cd_induced_new + parasite_cd0 + 0.003
            
            drag_n = cd_total_new * 0.5 * rho * v_cruise_ms**2 * wing_area
            p_mech_cruise_w = drag_n * v_cruise_ms
            p_elec_cruise_w = p_mech_cruise_w / efficiency
            
            e_cruise_j = p_elec_cruise_w * (distance_m / v_cruise_ms)
            e_climb_j = (total_mass_kg * 9.81 * cruise_altitude_m) * 2.2 / efficiency
            
            # Add descent and taxi energy
            e_descent_j = (total_mass_kg * 9.81 * cruise_altitude_m) * 0.3 / efficiency  # ~30% of climb energy
            e_taxi_j = 8e3 * 3600  # ~8 kWh for taxi (pre and post flight)
            
            e_mission_j = e_cruise_j + e_climb_j + e_descent_j + e_taxi_j + e_fixed_j
            
            if is_hybrid:
                # For hybrid: electric covers climb + taxi + descent + reserve
                # Turboprops cover cruise (75% power)
                e_electric_mission_j = e_climb_j + e_descent_j + e_taxi_j + e_fixed_j
                e_required_j = e_electric_mission_j * 1.4
            else:
                e_required_j = e_mission_j * 1.4
            
            e_gross_j = e_required_j / 0.85
            
            battery_kwh = e_gross_j / 3.6e6
            battery_mass_kg = (battery_kwh * 1000) / battery_density
        
        # Final calculations
        total_mass_kg = empty_base_kg + payload_kg + battery_mass_kg + parachute_mass_kg
        if is_hybrid:
            total_mass_kg += fuel_mass_kg + fuel_tank_mass_kg
        
        weight_n = total_mass_kg * 9.81
        cl_final = weight_n / (0.5 * rho * v_cruise_ms**2 * wing_area)
        cd_induced_final = (cl_final**2) / (np.pi * ar_guess * oswald_e)
        cd_final = cd_induced_final + parasite_cd0 + 0.003
        ld_final = cl_final / cd_final
        
        p_peak_kw = (p_elec_cruise_w / 1000) * peak_to_cruise_ratio
        motor_power_kw = round(p_peak_kw / 4)
        v_max_kmh = cruise_speed_kmh * (peak_to_cruise_ratio ** (1/3))
        charger_kw = (battery_kwh * 0.8) / desired_charge_time_h
        
        # Calculate travel time (cruise only, excludes climb and descent)
        travel_time_hours = max_dist_km / cruise_speed_kmh
        travel_time_minutes = int((travel_time_hours % 1) * 60)
        travel_time_hours_int = int(travel_time_hours)
        
        # Hybrid-specific calculations
        if is_hybrid:
            # Cruise power split: electric + turboprop
            electric_cruise_power_kw = p_elec_cruise_w / 1000 * (100 - turboprop_cruise_fraction) / 100
            turboprop_cruise_power_kw = p_elec_cruise_w / 1000 * turboprop_cruise_fraction / 100
            
            # Fuel needed for cruise on longest leg
            cruise_time_h = max_dist_km / cruise_speed_kmh
            fuel_for_cruise_kg = cruise_fuel_consumption_kgh * cruise_time_h
            fuel_reserve_kg = fuel_for_cruise_kg * 0.3  # 30% reserve
            total_fuel_capacity_kg = fuel_for_cruise_kg + fuel_reserve_kg
            
            # Calculate electric-only range with battery
            electric_only_range_km = (battery_kwh * 3600 / (p_elec_cruise_w / 1000)) * (cruise_speed_kmh / 3.6) / 1000 if p_elec_cruise_w > 0 else 0
            
            # Calculate fuel-only range with turboprops
            fuel_energy_j = total_fuel_capacity_kg * fuel_energy_density_mj_kg * 1e6  # Convert MJ to J
            turboprop_efficiency = 0.78
            fuel_mechanical_energy_j = fuel_energy_j * turboprop_efficiency
            turboprop_mechanical_power_w = (turboprop_cruise_power_kw * 1000) / efficiency  # Convert to mech power
            fuel_only_time_h = fuel_mechanical_energy_j / (turboprop_mechanical_power_w * 3600)
            fuel_only_range_km = fuel_only_time_h * cruise_speed_kmh
            
            # Total range: can fly on electric until battery low, then switch to turboprops
            total_extended_range_km = electric_only_range_km + fuel_only_range_km
        
        # Check battery feasibility (physical size constraint)
        battery_to_power_ratio_wh_kw = (battery_kwh * 1000) / p_peak_kw if p_peak_kw > 0 else 0
        max_practical_ratio = 800  # Wh/kW - anything higher is physically too large
        battery_feasible = battery_to_power_ratio_wh_kw <= max_practical_ratio
        battery_status = "✅ Feasible" if battery_feasible else "❌ Battery Too Large"
        battery_warning = "" if battery_feasible else f" (Ratio: {battery_to_power_ratio_wh_kw:.0f} Wh/kW, exceeds {max_practical_ratio} Wh/kW limit)"
        
        if not battery_feasible:
            st.warning(f"⚠️ **Battery Infeasible**: {battery_kwh:.0f} kWh for {p_peak_kw:.0f} kW peak power would be too large to fit in aircraft.{battery_warning}")
        
        # Display results in attractive format
        st.markdown('<h3 class="section-header">✈️ Aircraft Sizing Results</h3>', unsafe_allow_html=True)
        
        payload_desc = f"{num_pass} passengers + {cargo_kg} kg cargo" if cargo_kg else f"{num_pass} passengers"
        if num_pass == 0:
            payload_desc = f"{cargo_kg} kg cargo (cargo-only)"
        
        # Create result columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f'<div class="metric-card"><strong>👥 Payload:</strong> {payload_desc}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card"><strong>⚖️ MTOW:</strong> {total_mass_kg:.0f} kg</div>', unsafe_allow_html=True)
            battery_card_color = "background-color: #ffe6e6;" if not battery_feasible else "background-color: #f0f2f6;"
            st.markdown(f'<div class="metric-card" style="{battery_card_color}"><strong>🔋 Battery:</strong> {battery_kwh:.0f} kWh ({battery_mass_kg:.0f} kg) {battery_status}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card"><strong>🪟 Wing Area:</strong> {wing_area:.1f} m² (AR {ar_guess:.1f})</div>', unsafe_allow_html=True)
            if is_hybrid:
                st.markdown(f'<div class="metric-card"><strong>⛽ Fuel Capacity:</strong> {total_fuel_capacity_kg:.0f} kg ({total_fuel_capacity_kg/0.8:.0f} L)</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'<div class="metric-card"><strong>📊 L/D Ratio:</strong> {ld_final:.2f}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card"><strong>⚡ Cruise Power:</strong> {p_elec_cruise_w/1000:.0f} kW</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card"><strong>🚀 Peak Power:</strong> {p_peak_kw:.0f} kW (4 × {motor_power_kw} kW)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-card"><strong>💨 Max Speed:</strong> {v_max_kmh:.0f} km/h</div>', unsafe_allow_html=True)
            if is_hybrid:
                st.markdown(f'<div class="metric-card"><strong>🚀 Turboprop Power:</strong> {turboprop_cruise_power_kw:.0f} kW @ cruise</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("**Route & Performance**")
        route_col1, route_col2, route_col3, route_col4 = st.columns(4)
        with route_col1:
            st.metric("📏 Route Distance", f"{max_dist_km:.0f} km")
        with route_col2:
            st.metric("✈️ Cruise Speed", f"{cruise_speed_kmh:.0f} km/h")
        with route_col3:
            st.metric("⏱️ Travel Time", f"{travel_time_hours_int}h {travel_time_minutes}m")
        with route_col4:
            status_ratio = "✅" if battery_feasible else "❌"
            st.metric("🔋 Battery/Power", f"{battery_to_power_ratio_wh_kw:.0f} Wh/kW {status_ratio}", "800 Wh/kW max")
        
        st.markdown("---")
        st.markdown("**Energy Budget**")
        
        climb_kwh = e_climb_j / 3.6e6
        cruise_kwh = e_cruise_j / 3.6e6
        descent_kwh = e_descent_j / 3.6e6
        taxi_kwh = e_taxi_j / 3.6e6
        fixed_kwh = 20.0
        
        energy_col1, energy_col2, energy_col3, energy_col4, energy_col5 = st.columns(5)
        with energy_col1:
            st.metric("Taxi", f"{taxi_kwh:.1f} kWh")
        with energy_col2:
            st.metric("Climb", f"{climb_kwh:.1f} kWh")
        with energy_col3:
            st.metric("Cruise", f"{cruise_kwh:.1f} kWh")
        with energy_col4:
            st.metric("Descent", f"{descent_kwh:.1f} kWh")
        with energy_col5:
            st.metric("Reserve", f"{fixed_kwh:.1f} kWh")
        
        # Energy breakdown visualization
        st.markdown("---")
        st.markdown("**Energy Usage Breakdown**")
        
        # Create pie chart
        energy_stages = ['Taxi', 'Climb', 'Cruise', 'Descent', 'Reserve']
        energy_values = [taxi_kwh, climb_kwh, cruise_kwh, descent_kwh, fixed_kwh]
        colors = ['#FFB6B9', '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        
        fig = go.Figure(data=[go.Pie(
            labels=energy_stages,
            values=energy_values,
            marker=dict(colors=colors),
            textposition='inside',
            textinfo='label+percent+value',
            hovertemplate='<b>%{label}</b><br>Energy: %{value:.1f} kWh<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            height=400,
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.markdown(f'<div class="metric-card"><strong>🔌 Required Charger (for {desired_charge_time_h:.1f}h to 80%):</strong> {charger_kw:.0f} kW</div>', unsafe_allow_html=True)
        
        # Performance analysis for each route
        st.markdown("---")
        st.markdown('<h3 class="section-header">📊 Performance on Each Route</h3>', unsafe_allow_html=True)
        
        route_performance = []
        for idx, route in enumerate(st.session_state.routes):
            route_dist = route['dist_km']
            route_time = route_dist / cruise_speed_kmh
            route_time_h = int(route_time)
            route_time_m = int((route_time % 1) * 60)
            
            # Estimate energy for this route (simple linear scaling from cruise energy)
            route_cruise_energy = (cruise_kwh / max_dist_km) * route_dist if max_dist_km > 0 else cruise_kwh
            
            # Estimate total energy (climb + cruise + descent + taxi + reserve)
            route_climb_energy = (climb_kwh / max_dist_km) * route_dist if max_dist_km > 0 else climb_kwh
            route_descent_energy = (descent_kwh / max_dist_km) * route_dist if max_dist_km > 0 else descent_kwh
            route_total_mission = taxi_kwh + route_climb_energy + route_cruise_energy + route_descent_energy + fixed_kwh
            
            # Check if feasible
            feasible = "✅" if route_total_mission <= battery_kwh * 0.85 else "⚠️"
            margin = ((battery_kwh * 0.85 - route_total_mission) / (battery_kwh * 0.85)) * 100 if route_total_mission > 0 else 0
            
            route_performance.append({
                "Route": f"{route['origin_name']} → {route['dest_name']}",
                "Distance": f"{route_dist} km",
                "Flight Time": f"{route_time_h}h {route_time_m}m",
                "Mission Energy": f"{route_total_mission:.0f} kWh",
                "Battery Capacity": f"{battery_kwh:.0f} kWh (85%: {battery_kwh*0.85:.0f})",
                "Status": feasible,
                "Margin": f"{margin:.0f}%" if margin >= 0 else "❌ INFEASIBLE"
            })
        
        # Display as table
        import pandas as pd
        df_routes = pd.DataFrame(route_performance)
        st.dataframe(df_routes, use_container_width=True, hide_index=True)
        
        # Hybrid range analysis
        if is_hybrid:
            st.markdown("---")
            st.markdown('<h3 class="section-header">⚡🔥 Hybrid Range Analysis</h3>', unsafe_allow_html=True)
            
            hybrid_col1, hybrid_col2, hybrid_col3 = st.columns(3)
            with hybrid_col1:
                st.metric("🔋 Electric-Only Range", f"{electric_only_range_km:.0f} km")
            with hybrid_col2:
                st.metric("⛽ Turboprop Range", f"{fuel_only_range_km:.0f} km")
            with hybrid_col3:
                st.metric("🚀 Total Extended Range", f"{total_extended_range_km:.0f} km")
            
            st.markdown("---")
            st.markdown("**Cruise Power Split**")
            split_col1, split_col2, split_col3 = st.columns(3)
            with split_col1:
                st.metric("⚡ Electric Motors", f"{electric_cruise_power_kw:.0f} kW ({100-turboprop_cruise_fraction:.0f}%)")
            with split_col2:
                st.metric("🔥 Turboprops", f"{turboprop_cruise_power_kw:.0f} kW ({turboprop_cruise_fraction:.0f}%)")
            with split_col3:
                st.metric("📊 Total Cruise Power", f"{p_elec_cruise_w/1000:.0f} kW")
            
            st.markdown("---")
            st.markdown("**Fuel Management**")
            fuel_col1, fuel_col2, fuel_col3 = st.columns(3)
            with fuel_col1:
                st.metric("✈️ Cruise Duration", f"{cruise_time_h:.1f} h")
            with fuel_col2:
                st.metric("⛽ Fuel Burn Rate", f"{cruise_fuel_consumption_kgh:.1f} kg/h")
            with fuel_col3:
                st.metric("📦 Fuel Tank Mass", f"{fuel_tank_mass_kg:.0f} kg")
        
        # Pure Electric vs Hybrid Comparison
        st.markdown("---")
        st.markdown('<h3 class="section-header">⚡ Pure Electric vs 🔥 Hybrid Powertrain Comparison</h3>', unsafe_allow_html=True)
        
        # Calculate metrics for pure electric
        pure_electric_mass_kg = empty_base_kg + payload_kg + battery_mass_kg + parachute_mass_kg
        pure_electric_range_km = electric_only_range_km if is_hybrid else (battery_kwh * 3600 / (p_elec_cruise_w / 1000)) * (cruise_speed_kmh / 3.6) / 1000 if p_elec_cruise_w > 0 else 0
        pure_electric_weight_efficiency = pure_electric_mass_kg / pure_electric_range_km if pure_electric_range_km > 0 else 0
        pure_electric_energy_efficiency = pure_electric_range_km / battery_kwh if battery_kwh > 0 else 0
        
        # Calculate metrics for hybrid
        if is_hybrid:
            hybrid_mass_kg = total_mass_kg
            hybrid_combined_range_km = total_extended_range_km
            hybrid_weight_efficiency = hybrid_mass_kg / hybrid_combined_range_km if hybrid_combined_range_km > 0 else 0
            
            # Energy per distance: combined electric + fuel energy
            total_energy_mj = (battery_kwh * 3.6) + (total_fuel_capacity_kg * fuel_energy_density_mj_kg)
            hybrid_energy_efficiency = hybrid_combined_range_km / (total_energy_mj / 3.6) if (total_energy_mj / 3.6) > 0 else 0  # Convert MJ to kWh
        
        comp_col1, comp_col2, comp_col3 = st.columns(3)
        
        with comp_col1:
            st.markdown("**Pure Electric** ⚡")
            st.write(f"**Max Mass:** {pure_electric_mass_kg:.0f} kg")
            st.write(f"**Max Range:** {pure_electric_range_km:.0f} km")
            st.write(f"**Weight/Distance:** {pure_electric_weight_efficiency:.2f} kg/km")
            st.write(f"**Energy Efficiency:** {pure_electric_energy_efficiency:.2f} km/kWh")
            st.write(f"**Battery:** {battery_kwh:.0f} kWh")
        
        with comp_col2:
            if is_hybrid:
                st.markdown("**Hybrid (2E+2TP)** 🔥")
                st.write(f"**Max Mass:** {hybrid_mass_kg:.0f} kg")
                st.write(f"**Max Range:** {hybrid_combined_range_km:.0f} km")
                st.write(f"**Weight/Distance:** {hybrid_weight_efficiency:.2f} kg/km")
                st.write(f"**Energy Efficiency:** {hybrid_energy_efficiency:.2f} km/kWh-eq")
                st.write(f"**Battery:** {battery_kwh:.0f} kWh | **Fuel:** {total_fuel_capacity_kg:.0f} kg")
            else:
                st.info("Switch to 'Hybrid (2E + 2TP)' mode to see comparison")
        
        with comp_col3:
            if is_hybrid:
                st.markdown("**Advantage** 📊")
                range_improvement = ((hybrid_combined_range_km - pure_electric_range_km) / pure_electric_range_km * 100) if pure_electric_range_km > 0 else 0
                mass_difference = hybrid_mass_kg - pure_electric_mass_kg
                
                if range_improvement > 0:
                    st.write(f"🚀 **+{range_improvement:.0f}%** range increase")
                else:
                    st.write(f"📉 **{range_improvement:.0f}%** range difference")
                
                st.write(f"**+{mass_difference:.0f} kg** additional mass")
                
                if hybrid_weight_efficiency < pure_electric_weight_efficiency:
                    efficiency_gain = ((pure_electric_weight_efficiency - hybrid_weight_efficiency) / pure_electric_weight_efficiency * 100)
                    st.write(f"✅ **{efficiency_gain:.0f}%** better weight efficiency")
                else:
                    efficiency_loss = ((hybrid_weight_efficiency - pure_electric_weight_efficiency) / pure_electric_weight_efficiency * 100)
                    st.write(f"❌ **{efficiency_loss:.0f}%** worse weight efficiency")
                
                # Payload fraction analysis
                payload_fraction_pure = payload_kg / pure_electric_mass_kg * 100
                payload_fraction_hybrid = payload_kg / hybrid_mass_kg * 100
                st.write(f"**Payload %:** {payload_fraction_pure:.1f}% (E) vs {payload_fraction_hybrid:.1f}% (H)")
        
        st.markdown("---")
        st.success("✓ Sizing complete!")

st.markdown("---")
st.caption("✈️ Electric Airplane Sizing Tool | Default Route: Bengaluru → Delhi | Heuristic Sizing Model | Hybrid: 2 Electric + 2 Turboprop")