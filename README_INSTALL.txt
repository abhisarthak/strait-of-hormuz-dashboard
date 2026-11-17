STRAIT OF HORMUZ — BUILD 9 DECISION LAB PATCH

This patch updates only:
  strait_of_hormuz_v2/app.py

It uses the existing Script 98 result loader and the existing precomputed CSV outputs.
It does NOT modify:
  - services/simulation.py
  - services/live_data.py
  - Script 98 CSV outputs
  - original research scripts
  - AIS/news/energy integrations
  - status.json

What changed in Research Simulation:
- Clear scenario configuration for existing shock and affected-share values.
- Criterion-based ranking of the five stored recovery policies.
- Ranking criteria: M02 mean departure delay, M05 P90 delay, M07A unrecovered calls,
  M07B unrecovered vessels, and M06 paired recovery benefit.
- Selected policy rank and best result under the chosen criterion.
- Selected-policy vs no-recovery comparison.
- Existing call-level, vessel-level, Script 77 sensitivity and validation tabs retained.

Important:
- This is a decision-support view over precomputed Script 98 outputs.
- It does not rerun the model or support arbitrary shock values.
- "Best" means best under the selected metric for the selected scenario only.
- Script 77 remains sensitivity analysis, not operational recovery capacity.

INSTALL
1. Stop Streamlit with Ctrl+C.
2. Back up the current app:
   cd ~/Strait_of_Hormuz_Research
   cp strait_of_hormuz_v2/app.py strait_of_hormuz_v2/app_build8_backup.py
3. Extract this ZIP into the project root:
   unzip -o ~/Downloads/strait_of_hormuz_build9_decision_lab.zip -d ~/Strait_of_Hormuz_Research
4. Compile and run:
   cd ~/Strait_of_Hormuz_Research/strait_of_hormuz_v2
   ../.venv/bin/python -m py_compile app.py
   ../.venv/bin/python -m streamlit run app.py

Rollback:
   cp app_build8_backup.py app.py
