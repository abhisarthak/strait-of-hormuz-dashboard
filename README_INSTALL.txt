STRAIT OF HORMUZ — SIDEBAR IDENTITY PATCH

This patch updates only strait_of_hormuz_v2/app.py. It adds a compact researcher/supervisor identity card to the sidebar. AIS services, energy data services, status records, and Script 98 outputs are not included or modified.

Install from the project root:
  unzip -o ~/Downloads/strait_of_hormuz_sidebar_identity_patch.zip -d ~/Strait_of_Hormuz_Research

Then restart Streamlit. Optional syntax check:
  cd ~/Strait_of_Hormuz_Research/strait_of_hormuz_v2
  ../.venv/bin/python -m py_compile app.py
