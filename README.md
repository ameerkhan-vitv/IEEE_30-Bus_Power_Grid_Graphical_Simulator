# IEEE_30-Bus_Power_Grid_Graphical_Simulator

The source code is organized into a modular design for simple troubleshooting:

• grid_data.py: Holds raw electrical parameters (R, X, B, ratings, generation setups, and standard bus loads).

• grid_engine.py: Contains the network graph island, the Ybus building function, and the polar Newton-Raphson numerical solver.

• grid_plots.py: Manages the coordinate mapping system, color-coded visual nodes, and the Matplotlib plotting functions.

• main_app.py: Contains the Tkinter user interface framework, event listeners for mouse clicks, tables, logs, and CSV data dumping features.
