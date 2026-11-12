import time
import pandas as pd
import streamlit as st
from simulation import Simulation, power

st.set_page_config(page_title="Green Data Center Lab", page_icon="🌿", layout="wide")
if 'sim' not in st.session_state:
    st.session_state.sim = Simulation()
    st.session_state.running = False
    st.session_state.last_tick = time.monotonic()

st.title("🌿 Green Data Center Lab")
st.caption("ENERGY & COOLING SIMULATION · Seminar demonstration")
st.info("Illustrative model using assumed parameters. These are simulated results, not measured data center performance.")

with st.sidebar:
    st.header("Experiment controls")
    mode = st.radio("Data center mode", ['Traditional', 'Green'], key='mode')
    workload = st.slider("Server workload (%)", 10, 100, 30, 5, key='workload')
    enabled = st.toggle("Liquid cooling", value=True, disabled=mode == 'Traditional', key='liquid')
    liquid = mode == 'Green' and enabled
    st.caption("Liquid OFF uses traditional air cooling. Both scenarios process the same workload.")
    a, b = st.columns(2)
    if a.button("Pause" if st.session_state.running else "Start", width='stretch'):
        st.session_state.running = not st.session_state.running
        st.session_state.last_tick = time.monotonic()
    if b.button("Reset", width='stretch'):
        st.session_state.sim = Simulation()
        st.session_state.running = False
        st.session_state.last_tick = time.monotonic()
    st.caption("1 live second ≈ 10 simulated seconds. Pause freezes temperature and accumulated energy. Reset keeps your controls.")
    with st.expander("2-minute seminar walkthrough"):
        st.markdown("1. Start Traditional at 30% workload.\n2. Increase workload to 90% and watch temperature rise.\n3. Select Green with liquid cooling ON.\n4. Compare power, PUE and the temperature response.\n5. Switch liquid OFF to demonstrate air cooling fallback.")


@st.fragment(run_every=1 if st.session_state.running else None)
def dashboard():
    sim = st.session_state.sim
    now = time.monotonic()
    # Widget reruns do not create extra time steps. No background catch-up.
    if st.session_state.running and now - st.session_state.last_tick >= 0.9:
        sim.step(workload, liquid)
        st.session_state.last_tick = now
    baseline, selected = power(workload), power(workload, liquid)
    st.subheader(f"{mode} · {'Liquid cooling' if liquid else 'Air cooling'}")
    st.caption(f"{'Running' if st.session_state.running else 'Paused'} · Simulated time {sim.seconds / 60:.1f} min · Workload {workload}%")
    cols = st.columns(5)
    cols[0].metric("IT equipment", f"{selected['it']:.1f} kW")
    cols[1].metric("Cooling", f"{selected['cooling']:.1f} kW")
    cols[2].metric("Total facility", f"{selected['total']:.1f} kW")
    cols[3].metric("Calculated PUE", f"{selected['pue']:.2f}")
    cols[4].metric("Modeled server temperature", f"{sim.selected_temp:.1f} °C")
    left, right = st.columns(2)
    with left:
        st.subheader("Power at current workload")
        breakdown = pd.DataFrame({
            'IT equipment': [baseline['it'], selected['it']],
            'Cooling': [baseline['cooling'], selected['cooling']],
            'Other overhead': [baseline['other'], selected['other']],
        }, index=['Traditional baseline', 'Selected configuration'])
        st.bar_chart(breakdown, y_label='Power (kW)', color=['#2563eb', '#10b981', '#94a3b8'])
    with right:
        st.subheader("Temperature response")
        data = pd.DataFrame(sim.history) if sim.history else pd.DataFrame([{
            'Time (min)': 0, 'Traditional temperature (C)': 30, 'Selected temperature (C)': 30,
            'Energy saved (kWh)': 0,
        }])
        st.line_chart(data, x='Time (min)', y=['Traditional temperature (C)', 'Selected temperature (C)'], y_label='Temperature (°C)', color=['#f97316', '#10b981'])
    c1, c2, c3 = st.columns(3)
    saved = sim.baseline_kwh - sim.selected_kwh
    c1.metric("Instantaneous power saved", f"{baseline['total'] - selected['total']:.1f} kW")
    c2.metric("Accumulated energy saved", f"{saved:.3f} kWh")
    c3.metric("Energy reduction over this run", f"{100 * saved / sim.baseline_kwh if sim.baseline_kwh else 0:.1f}%")
    st.subheader("Energy savings over simulated time")
    st.line_chart(data, x='Time (min)', y='Energy saved (kWh)', y_label='Saved energy (kWh)', color='#10b981')
    st.caption("Savings compare the selected configuration against continuous traditional air cooling at identical workload. Switching modes keeps the run history.")
    with st.expander("Energy totals and recorded samples"):
        st.write(f"Traditional baseline: {sim.baseline_kwh:.3f} kWh · Selected configuration: {sim.selected_kwh:.3f} kWh")
        st.dataframe(data.tail(20), hide_index=True, width='stretch')
        st.download_button("Download run CSV", data.to_csv(index=False), 'simulation-run.csv', 'text/csv')


dashboard()
with st.expander("Model assumptions and equations"):
    st.markdown("""
    - **IT power:** 20 kW idle + 80 kW × workload fraction. Same compute demand in both scenarios.
    - **Traditional:** cooling = 70% of IT power; other overhead = 10%. PUE = 1.8.
    - **Liquid:** cooling = 10% of IT power; other overhead = 10%. PUE = 1.2.
    - **PUE:** total facility power / IT power. These fixed ratios keep PUE constant within each cooling mode.
    - **Thermal response:** C × dT/dt = IT heat − K × (T − 22°C). C = 240 kJ/°C; K = 2 kW/°C for air or 5 for liquid. Exact exponential update at each 10-second step. Initial temperature = 30°C.
    - **Energy:** sum of power × step hours. Parameters are chosen to make the concept visible in a short seminar, without calibrating a real facility. Temperature is a representative server thermal mass, not room temperature.
    - Cooling electrical consumption and heat removal are distinct simplified assumptions. The coolant remains at 22°C. No weather, throttling, renewable generation, or hardware failures are modeled.
    - Graphs retain the latest 1,800 samples; energy totals include the full run. No internet or external data is used during the demo.
    """)
