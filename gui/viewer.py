"""Battery Prognosis Viewer with beginner-friendly controls.

Users can change panel/battery numbers here and re-run the pipeline without
touching code. Fields mirror config.yaml so the GUI and code stay in sync.
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
import yaml
from pathlib import Path
import logging
import threading
from src.config import load_config
from src.solar_pipeline import run_pipeline

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("data/exports")
CONFIG_FILE = Path("config.yaml")

# Dark mode color scheme
COLORS = {
    'bg': '#1e1e1e',           # Dark background
    'fg': '#e0e0e0',           # Light text
    'accent': '#4a9eff',       # Blue accent
    'success': '#4caf50',      # Green for success
    'warning': '#ff9800',      # Orange for warnings
    'input_bg': '#2d2d2d',     # Input field background
    'input_fg': '#ffffff',     # Input field text
    'border': '#3d3d3d',       # Border color
    'highlight': '#3d5a80',    # Highlight color
    'overlay': '#000000',      # Loading overlay
}


class LoadingOverlay:
    """Loading overlay with progress indicator"""
    
    def __init__(self, parent):
        self.parent = parent
        self.overlay = None
        self.progress_label = None
        self.spinner_after_id = None
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_idx = 0
    
    def show(self, message="Loading..."):
        """Show loading overlay"""
        if self.overlay:
            return
        
        # Semi-transparent overlay
        self.overlay = tk.Frame(self.parent, bg=COLORS['overlay'])
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.overlay.lift()
        
        # Make it 70% transparent
        self.overlay.attributes = lambda: None
        
        # Loading container
        loading_frame = tk.Frame(self.overlay, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Spinner
        self.spinner_label = tk.Label(loading_frame, text=self.spinner_chars[0], 
                                     font=('Segoe UI', 36), fg=COLORS['accent'], 
                                     bg='#2d2d2d', width=3, height=2)
        self.spinner_label.pack(pady=(20, 10))
        
        # Message
        self.progress_label = tk.Label(loading_frame, text=message, 
                                      font=('Segoe UI', 12), fg=COLORS['fg'], 
                                      bg='#2d2d2d', padx=40, pady=10)
        self.progress_label.pack(pady=(0, 20))
        
        self._animate_spinner()
    
    def _animate_spinner(self):
        """Animate the spinner"""
        if self.overlay and self.spinner_label.winfo_exists():
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            self.spinner_label.config(text=self.spinner_chars[self.spinner_idx])
            self.spinner_after_id = self.overlay.after(100, self._animate_spinner)
    
    def update_message(self, message):
        """Update loading message"""
        if self.progress_label and self.progress_label.winfo_exists():
            self.progress_label.config(text=message)
    
    def hide(self):
        """Hide loading overlay"""
        if self.spinner_after_id:
            self.overlay.after_cancel(self.spinner_after_id)
            self.spinner_after_id = None
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
            self.progress_label = None
            self.spinner_label = None


class PrognosisViewer:
    """Simple Tkinter GUI for viewing and recalculating prognosis"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("☀️ Solar Battery Prognosis")
        self.root.geometry("1200x750")
        self.root.minsize(900, 600)  # Set minimum size for responsive design
        self.root.configure(bg=COLORS['bg'])
        
        self.data = None
        self.config = load_config()
        self.loading = LoadingOverlay(self.root)
        self._init_vars()
        self._setup_styles()
        self._setup_ui()
        self._load_data()
    
    def _init_vars(self):
        cfg = self.config
        panel = cfg.get('solar_panel', {})
        battery = cfg.get('battery', {})
        
        self.panel_count = tk.IntVar(value=panel.get('count', 1))
        self.panel_eff = tk.DoubleVar(value=panel.get('efficiency', 0.20))
        self.panel_area = tk.DoubleVar(value=panel.get('area_per_panel_m2', panel.get('area_m2', 1.0)))
        
        self.battery_count = tk.IntVar(value=battery.get('count', 1))
        self.battery_capacity = tk.DoubleVar(value=battery.get('capacity_kwh_per_battery', battery.get('capacity_kwh', 10.0)))
        self.battery_rate = tk.DoubleVar(value=battery.get('max_charge_rate_kw_per_battery', battery.get('max_charge_rate_kw', 5.0)))
    
    def _setup_styles(self):
        """Configure dark mode styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors for all widgets
        style.configure('.',
                       background=COLORS['bg'],
                       foreground=COLORS['fg'],
                       fieldbackground=COLORS['input_bg'],
                       bordercolor=COLORS['border'],
                       darkcolor=COLORS['bg'],
                       lightcolor=COLORS['border'])
        
        style.configure('TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['fg'],
                       font=('Segoe UI', 10))
        
        style.configure('Title.TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['accent'],
                       font=('Segoe UI', 18, 'bold'))
        
        style.configure('Hint.TLabel',
                       background=COLORS['bg'],
                       foreground='#888888',
                       font=('Segoe UI', 9))
        
        style.configure('TLabelframe',
                       background=COLORS['bg'],
                       foreground=COLORS['fg'],
                       bordercolor=COLORS['border'],
                       relief='flat')
        
        style.configure('TLabelframe.Label',
                       background=COLORS['bg'],
                       foreground=COLORS['accent'],
                       font=('Segoe UI', 11, 'bold'))
        
        style.configure('TEntry',
                       fieldbackground=COLORS['input_bg'],
                       foreground=COLORS['input_fg'],
                       insertcolor=COLORS['fg'],
                       bordercolor=COLORS['border'])
        
        style.map('TEntry',
                 fieldbackground=[('focus', COLORS['highlight'])],
                 bordercolor=[('focus', COLORS['accent'])])
        
        style.configure('TButton',
                       background=COLORS['accent'],
                       foreground='#ffffff',
                       bordercolor=COLORS['accent'],
                       focuscolor=COLORS['accent'],
                       font=('Segoe UI', 10, 'bold'),
                       padding=8)
        
        style.map('TButton',
                 background=[('active', COLORS['highlight']), ('pressed', '#2c4d70')],
                 foreground=[('active', '#ffffff')])
        
        style.configure('Treeview',
                       background=COLORS['input_bg'],
                       foreground=COLORS['fg'],
                       fieldbackground=COLORS['input_bg'],
                       bordercolor=COLORS['border'],
                       font=('Consolas', 9))
        
        style.configure('Treeview.Heading',
                       background=COLORS['border'],
                       foreground=COLORS['accent'],
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Treeview',
                 background=[('selected', COLORS['highlight'])],
                 foreground=[('selected', COLORS['fg'])])
    
    def _setup_ui(self):
        # Main container with responsive layout
        main_container = tk.Frame(self.root, bg=COLORS['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        
        # Header with title and info
        header_frame = tk.Frame(main_container, bg=COLORS['bg'])
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = ttk.Label(header_frame, text="☀️ Solar Battery Prognosis", style='Title.TLabel')
        title.pack()
        
        subtitle = ttk.Label(header_frame, text="Adjust your system settings and see real-time predictions", style='Hint.TLabel')
        subtitle.pack(pady=(2, 0))
        
        # Configuration panel - simplified for better performance
        form_frame = ttk.LabelFrame(main_container, text="⚙️ System Configuration", padding=12)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a container for inputs and buttons
        input_container = tk.Frame(form_frame, bg=COLORS['bg'])
        input_container.pack(fill=tk.X)
        
        # Solar panels section
        panel_label = ttk.Label(input_container, text="🔆 Solar Panels", font=('Segoe UI', 10, 'bold'))
        panel_label.pack(anchor=tk.W, pady=(0, 6))
        
        self._add_input(input_container, "Number of panels:", self.panel_count, "panels")
        self._add_input(input_container, "Panel efficiency:", self.panel_eff, "from datasheet (0.20 = 20%)")
        self._add_input(input_container, "Area per panel (m²):", self.panel_area, "size of one panel")
        
        # Batteries section
        battery_label = ttk.Label(input_container, text="🔋 Batteries", font=('Segoe UI', 10, 'bold'))
        battery_label.pack(anchor=tk.W, pady=(12, 6))
        
        self._add_input(input_container, "Number of batteries:", self.battery_count, "total batteries")
        self._add_input(input_container, "Capacity per battery (kWh):", self.battery_capacity, "storage capacity")
        self._add_input(input_container, "Max charge rate (kW):", self.battery_rate, "charge speed")
        
        # Buttons section
        btn_container = tk.Frame(form_frame, bg=COLORS['bg'])
        btn_container.pack(fill=tk.X, pady=(12, 0))
        
        ttk.Label(btn_container, text="⚡ Actions", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))
        
        btn_frame = tk.Frame(btn_container, bg=COLORS['bg'])
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="▶️ Run Pipeline", command=self._run_with_settings, width=20).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="💾 Save & Run", command=self._save_and_run, width=20).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="🔄 Refresh", command=self._refresh_data, width=20).pack(side=tk.LEFT)
        
        # Results table
        results_frame = ttk.LabelFrame(main_container, text="📊 Forecast Results", padding=8)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 10))
        
        # Table with scrollbars
        table_container = tk.Frame(results_frame, bg=COLORS['bg'])
        table_container.pack(fill=tk.BOTH, expand=True)
        
        cols = [
            'Date', 'SolarRadiation_kWh_m2', 'PerPanelYield_kWh', 'PanelCount',
            'TotalYield_kWh', 'BatteryCapacityTotal_kWh', 'Chargeable_kWh', 'ChargePercentage'
        ]
        
        # Create frame for tree and scrollbars
        tree_frame = tk.Frame(table_container, bg=COLORS['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=12)
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        
        # Grid layout for tree and scrollbars
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        for col in cols:
            self.tree.heading(col, text=col)
            width = 130
            self.tree.column(col, anchor=tk.CENTER, width=width)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg=COLORS['border'], height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status = tk.Label(status_frame, text="✓ Ready to run", 
                              bg=COLORS['border'], fg=COLORS['fg'],
                              font=('Segoe UI', 9), anchor=tk.W, padx=10)
        self.status.pack(fill=tk.BOTH, expand=True)
    
    def _add_input(self, parent, label_text, variable, hint_text):
        """Helper to add a labeled input with hint - optimized for readability"""
        container = tk.Frame(parent, bg=COLORS['bg'])
        container.pack(fill=tk.X, pady=5)
        
        # Label row
        label_frame = tk.Frame(container, bg=COLORS['bg'])
        label_frame.pack(fill=tk.X)
        
        ttk.Label(label_frame, text=label_text, font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
        
        # Input row
        input_frame = tk.Frame(container, bg=COLORS['bg'])
        input_frame.pack(fill=tk.X, pady=(2, 0))
        
        entry = ttk.Entry(input_frame, textvariable=variable, font=('Segoe UI', 11), width=25)
        entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(input_frame, text=hint_text, style='Hint.TLabel').pack(side=tk.LEFT)
    
    def _load_data(self, show_loading=False):
        """Load prognosis data from CSV and show it"""
        if show_loading:
            self.loading.show("Loading data...")
        
        try:
            filepath = EXPORT_DIR / "battery_prognosis.csv"
            if not filepath.exists():
                self.status.config(text="⚠️ No data found. Run pipeline first.", fg=COLORS['warning'])
                if show_loading:
                    self.loading.hide()
                return
            self.data = pd.read_csv(filepath)
            self._populate_table()
            self.status.config(text=f"✓ Loaded {len(self.data)} records from {filepath.name}", fg=COLORS['success'])
        except Exception as e:
            self.status.config(text=f"❌ Error: {e}", fg=COLORS['warning'])
            logger.error(f"Error loading data: {e}")
        finally:
            if show_loading:
                self.loading.hide()
    
    def _refresh_data(self):
        """Refresh table data with loading indicator"""
        def refresh_thread():
            self._load_data(show_loading=True)
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def _populate_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if self.data is None or self.data.empty:
            return
        
        # Add rows with alternating background (handled by ttk theme)
        for i, (_, row) in enumerate(self.data.iterrows()):
            values = [row.get(col, '') for col in self.tree['columns']]
            # Format numbers for better readability
            formatted_values = []
            for col, val in zip(self.tree['columns'], values):
                if col in ['ChargePercentage'] and val != '':
                    formatted_values.append(f"{float(val):.1f}%")
                elif 'kWh' in col or 'kW' in col and val != '':
                    try:
                        formatted_values.append(f"{float(val):.3f}")
                    except:
                        formatted_values.append(val)
                else:
                    formatted_values.append(val)
            self.tree.insert('', tk.END, values=formatted_values)
    
    def _build_config_from_form(self):
        """Create a config dict from GUI fields."""
        cfg = load_config()
        cfg['solar_panel'] = cfg.get('solar_panel', {})
        cfg['battery'] = cfg.get('battery', {})
        cfg['solar_panel'].update({
            'count': max(1, self.panel_count.get()),
            'efficiency': float(self.panel_eff.get()),
            'area_per_panel_m2': float(self.panel_area.get()),
        })
        cfg['battery'].update({
            'count': max(1, self.battery_count.get()),
            'capacity_kwh_per_battery': float(self.battery_capacity.get()),
            'max_charge_rate_kw_per_battery': float(self.battery_rate.get()),
        })
        return cfg
    
    def _run_with_settings(self):
        """Re-run the pipeline using GUI values, then refresh the table."""
        def run_thread():
            try:
                self.root.after(0, lambda: self.loading.show("⏳ Fetching solar radiation forecast..."))
                cfg = self._build_config_from_form()
                
                self.root.after(0, lambda: self.loading.update_message("⏳ Processing data..."))
                success = run_pipeline(cfg)
                
                if success:
                    self.root.after(0, lambda: self.loading.update_message("✓ Reloading results..."))
                    self.root.after(0, lambda: self._load_data(show_loading=False))
                    self.root.after(0, lambda: self.status.config(text="✓ Pipeline completed successfully!", fg=COLORS['success']))
                else:
                    self.root.after(0, lambda: self.status.config(text="❌ Pipeline failed. Check console logs.", fg=COLORS['warning']))
            except Exception as e:
                self.root.after(0, lambda: self.status.config(text=f"❌ Error: {e}", fg=COLORS['warning']))
                logger.error(f"Error running pipeline: {e}")
            finally:
                self.root.after(0, lambda: self.loading.hide())
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def _save_and_run(self):
        """Save settings to config.yaml and automatically run pipeline"""
        def save_and_run_thread():
            try:
                self.root.after(0, lambda: self.loading.show("💾 Saving settings..."))
                cfg = self._build_config_from_form()
                
                with open(CONFIG_FILE, 'w') as f:
                    yaml.safe_dump(cfg, f, sort_keys=False)
                
                self.root.after(0, lambda: self.status.config(text=f"✓ Saved to {CONFIG_FILE}", fg=COLORS['success']))
                
                # Auto-run pipeline with new settings
                self.root.after(0, lambda: self.loading.update_message("⏳ Running pipeline with new settings..."))
                success = run_pipeline(cfg)
                
                if success:
                    self.root.after(0, lambda: self.loading.update_message("✓ Reloading results..."))
                    self.root.after(0, lambda: self._load_data(show_loading=False))
                    self.root.after(0, lambda: self.status.config(text="✓ Settings saved and pipeline completed!", fg=COLORS['success']))
                else:
                    self.root.after(0, lambda: self.status.config(text="⚠️ Settings saved but pipeline failed.", fg=COLORS['warning']))
            except Exception as e:
                self.root.after(0, lambda: self.status.config(text=f"❌ Error: {e}", fg=COLORS['warning']))
                logger.error(f"Error saving/running: {e}")
            finally:
                self.root.after(0, lambda: self.loading.hide())
        
        threading.Thread(target=save_and_run_thread, daemon=True).start()


def launch_gui():
    """Launch the GUI viewer"""
    root = tk.Tk()
    app = PrognosisViewer(root)
    root.mainloop()
