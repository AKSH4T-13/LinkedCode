# Green Data Center Energy & Cooling Simulation

Standalone seminar demo matching the presentation's PUE and cooling topics. No LinkedCode services, accounts, API keys, or hardware are needed.

## Run on Windows

Double-click **run.bat**. First launch creates `.venv` and installs packages (internet required). Subsequent launches work offline. Keep the terminal open; Ctrl+C stops the server. If the browser does not open, visit http://localhost:8501.

Manual setup from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost --browser.gatherUsageStats false
```

## Seminar demo (2–3 minutes)

1. Select Traditional, workload 30%, then Start. Explain PUE = total power / IT power.
2. Increase workload to 90%. Both facilities get identical IT demand. Watch temperature respond gradually.
3. Select Green with liquid cooling enabled. Total power drops immediately; temperature gradually approaches a lower equilibrium.
4. Compare the power breakdown and accumulated energy savings. Liquid OFF selects air fallback, so the instantaneous power advantage disappears.
5. Pause to explain results. Download CSV if needed. Reset clears time, temperatures, energy, and history, and pauses without changing the controls.

## Assumptions

This is an illustrative model, not a prediction or measured result. IT power is `20 + 80 * workload / 100` kW. Cooling is 70% of IT power for air or 10% for liquid; other facility overhead is 10%. Therefore PUE is 1.8 or 1.2 by construction, not a measured improvement. At 90% workload: IT = 92 kW, traditional = 165.6 kW, liquid = 110.4 kW, saving = 55.2 kW (33.3%). One simulated hour at these settings saves 55.2 kWh.

Temperature uses `C*dT/dt = IT_power - K*(T-22)` with C=240 kJ/°C, air K=2 and liquid K=5 kW/°C. These chosen constants illustrate thermal inertia. Temperature starts at 30°C. The model uses an exact exponential solution per step, with no artificial random values. Cooling electricity and heat removal use separate simplified assumptions.

One scheduled live update advances 10 simulated seconds. Browser timer delays may slow the demo; it does not catch up in the background. Pausing freezes thermal state and accumulated energy, but control changes still preview current power. Switching mode preserves thermal state and history. A traditional air-cooled reference runs alongside the selected configuration at the same workload throughout. Graphs keep the latest 1,800 samples, while totals retain the entire run.

No emissions, water consumption, renewables, CFD, hardware throttling, or actual sensor values are included.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Streamlit timer reference: https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
