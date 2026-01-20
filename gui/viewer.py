"""Battery Prognosis Viewer with beginner-friendly controls.

Users can change panel/battery numbers here and re-run the pipeline without
touching code. Fields mirror config.yaml so the GUI and code stay in sync.
"""

import tkinter as tk
from tkinter import ttk, font
import pandas as pd
import yaml
from pathlib import Path
import logging
import threading
import sys
import ctypes
import os
from src.config import load_config
from src.solar_pipeline import run_pipeline

# Enable DPI awareness on Windows to prevent blurriness
if sys.platform == 'win32':
    try:
        # Try to set DPI awareness (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        try:
            # Fallback for older Windows versions
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

logger = logging.getLogger(__name__)

PROGNOSIS_DIR = Path("data/prognosis")
HISTORY_PROGNOSIS_PATH = Path("data/history/prognosis/battery_prognosis.csv")
LEGACY_EXPORT_DIR = Path("data/exports")
CONFIG_FILE = Path("config.yaml")

# Dark mode color scheme - Solar themed
COLORS = {
    'bg': '#1a1a1a',           # Dark background
    'fg': '#f0f0f0',           # Light text
    'accent': '#ff9500',       # Solar orange accent
    'accent_light': '#ffb84d', # Light orange for hover
    'success': '#4caf50',      # Green for success
    'warning': '#ff6b6b',      # Red for warnings
    'solar_gold': '#ffd700',   # Gold for highlights
    'input_bg': '#252525',     # Input field background
    'input_fg': '#ffffff',     # Input field text
    'border': '#3a3a3a',       # Border color
    'highlight': '#664200',    # Orange highlight
    'overlay': '#000000',      # Loading overlay
}


class ToggleSwitch(tk.Frame):
    """Custom toggle switch widget for Latest/History view selection"""
    
    def __init__(self, parent, on_command=None, scale=1.0, **kwargs):
        super().__init__(parent, bg=COLORS['bg'], **kwargs)
        self.on_command = on_command
        self.is_enabled = False  # False = Latest, True = History
        self.scale = scale
        
        # Dimensions
        self.width = int(160 * scale)
        self.height = int(32 * scale)
        self.radius = int(14 * scale)
        
        # Container with labels
        container = tk.Frame(self, bg=COLORS['bg'])
        container.pack()
        
        # Latest label
        self.latest_label = tk.Label(container, text="Latest", 
                                     font=('Segoe UI', int(10 * scale), 'bold'),
                                     bg=COLORS['bg'], fg=COLORS['solar_gold'],
                                     cursor='hand2')
        self.latest_label.pack(side=tk.LEFT, padx=(0, 8))
        self.latest_label.bind('<Button-1>', lambda e: self._set_state(False))
        
        # Create canvas for the switch
        self.canvas = tk.Canvas(container, width=self.width//2.5, height=self.height, 
                               bg=COLORS['bg'], highlightthickness=0, borderwidth=0,
                               cursor='hand2')
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind('<Button-1>', self._on_click)
        
        # History label
        self.history_label = tk.Label(container, text="History", 
                                      font=('Segoe UI', int(10 * scale), 'bold'),
                                      bg=COLORS['bg'], fg='#666666',
                                      cursor='hand2')
        self.history_label.pack(side=tk.LEFT, padx=(8, 0))
        self.history_label.bind('<Button-1>', lambda e: self._set_state(True))
        
        self.draw_switch()
    
    def draw_switch(self):
        """Draw the toggle switch"""
        self.canvas.delete('all')
        
        w = int(self.width // 2.5)
        h = self.height
        r = self.radius
        pad = 3
        
        # Background track (pill shape)
        track_color = COLORS['accent'] if self.is_enabled else COLORS['border']
        self.canvas.create_oval(pad, pad, h - pad, h - pad, fill=track_color, outline=track_color)
        self.canvas.create_oval(w - h + pad, pad, w - pad, h - pad, fill=track_color, outline=track_color)
        self.canvas.create_rectangle(h//2, pad, w - h//2, h - pad, fill=track_color, outline=track_color)
        
        # Sliding circle (knob)
        knob_pad = 5
        knob_x = w - h//2 - knob_pad if self.is_enabled else h//2 + knob_pad
        knob_r = h//2 - knob_pad - 2
        self.canvas.create_oval(knob_x - knob_r, h//2 - knob_r, 
                               knob_x + knob_r, h//2 + knob_r,
                               fill='#ffffff', outline='#ffffff')
        
        # Update label colors
        if self.is_enabled:
            self.latest_label.config(fg='#666666')
            self.history_label.config(fg=COLORS['solar_gold'])
        else:
            self.latest_label.config(fg=COLORS['solar_gold'])
            self.history_label.config(fg='#666666')
    
    def _set_state(self, enabled):
        """Set switch state directly"""
        if self.is_enabled != enabled:
            self.is_enabled = enabled
            self.draw_switch()
            if self.on_command:
                self.on_command()
    
    def _on_click(self, event):
        """Handle click on switch"""
        self.is_enabled = not self.is_enabled
        self.draw_switch()
        if self.on_command:
            self.on_command()
    
    def get(self):
        """Get current value as 'History' or 'Latest'"""
        return "History" if self.is_enabled else "Latest"


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
                                     font=('Segoe UI', 48), fg=COLORS['accent'], 
                                     bg='#2d2d2d', width=3, height=2)
        self.spinner_label.pack(pady=(30, 15))
        
        # Message
        self.progress_label = tk.Label(loading_frame, text=message, 
                                      font=('Segoe UI', 14), fg=COLORS['fg'], 
                                      bg='#2d2d2d', padx=50, pady=15)
        self.progress_label.pack(pady=(0, 30))
        
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
        self.root.title("☀️ Solar")
        
        # Get DPI scaling factor for proper font sizing
        try:
            dpi = self.root.winfo_fpixels('1i')
            self.scale_factor = dpi / 96.0  # 96 is standard DPI
        except:
            self.scale_factor = 1.0
        
        # Set proper scaling for high-DPI displays
        if sys.platform == 'win32':
            try:
                # Use system DPI scaling
                self.root.tk.call('tk', 'scaling', self.scale_factor)
            except:
                pass
        
        # Set default window size based on typical screen usage
        self.root.geometry("1800x1400")
        self.root.minsize(1400, 900)
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
        
        # Calculate font sizes based on scale factor - more compact
        base_font_size = 10
        title_font_size = int(18 * self.scale_factor)
        label_font_size = int(base_font_size * self.scale_factor)
        hint_font_size = int(9 * self.scale_factor)
        entry_font_size = int(11 * self.scale_factor)
        button_font_size = int(base_font_size * self.scale_factor)
        # Slightly smaller table fonts so headers fit without scrolling.
        table_font_size = max(8, int(8 * self.scale_factor))
        table_header_font_size = max(8, int(9 * self.scale_factor))
        
        style.configure('TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['fg'],
                       font=('Segoe UI', label_font_size))
        
        style.configure('Title.TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['solar_gold'],
                       font=('Segoe UI', title_font_size, 'bold'))
        
        style.configure('Hint.TLabel',
                       background=COLORS['bg'],
                       foreground='#888888',
                       font=('Segoe UI', hint_font_size))
        
        style.configure('TLabelframe',
                       background=COLORS['bg'],
                       foreground=COLORS['fg'],
                       bordercolor=COLORS['border'],
                       relief='flat')
        
        style.configure('TLabelframe.Label',
                       background=COLORS['bg'],
                       foreground=COLORS['accent'],
                       font=('Segoe UI', int(11 * self.scale_factor), 'bold'))
        
        style.configure('TEntry',
                       fieldbackground=COLORS['input_bg'],
                       foreground=COLORS['input_fg'],
                       insertcolor=COLORS['fg'],
                       bordercolor=COLORS['border'],
                       font=('Segoe UI', entry_font_size),
                       padding=4)
        
        style.map('TEntry',
                 fieldbackground=[('focus', '#333333')],
                 bordercolor=[('focus', COLORS['accent'])])
        
        style.configure('TButton',
                       background=COLORS['accent'],
                       foreground='#ffffff',
                       bordercolor=COLORS['accent'],
                       focuscolor=COLORS['accent'],
                       font=('Segoe UI', button_font_size, 'bold'),
                       padding=(8, 6))
        
        style.map('TButton',
                 background=[('active', COLORS['accent_light']), ('pressed', '#ff7f00')],
                 foreground=[('active', '#ffffff')])
        
        style.configure('Treeview',
                       background=COLORS['input_bg'],
                       foreground=COLORS['fg'],
                       fieldbackground=COLORS['input_bg'],
                       bordercolor=COLORS['border'],
                       font=('Consolas', table_font_size),
                       rowheight=int(20 * self.scale_factor))
        
        style.configure('Treeview.Heading',
                       background=COLORS['border'],
                       foreground=COLORS['solar_gold'],
                       font=('Segoe UI', table_header_font_size, 'bold'))
        
        style.map('Treeview',
                 background=[('selected', '#663300')],
                 foreground=[('selected', COLORS['solar_gold'])])
        
        # Scrollbar styling - Solar themed
        style.configure('Vertical.TScrollbar',
                       background=COLORS['accent'],
                       troughcolor=COLORS['input_bg'],
                       bordercolor=COLORS['border'],
                       darkcolor=COLORS['accent'],
                       lightcolor=COLORS['accent_light'],
                       arrowcolor=COLORS['bg'],
                       relief='flat')
        
        style.map('Vertical.TScrollbar',
                 background=[('active', COLORS['accent_light']), ('pressed', '#ff7f00')])
    
    def _setup_ui(self):
        # Main container with responsive layout - more compact
        main_container = tk.Frame(self.root, bg=COLORS['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        
        # Header with subtitle - more compact
        header_frame = tk.Frame(main_container, bg=COLORS['bg'])
        header_frame.pack(fill=tk.X, pady=(0, 8))
        
        subtitle = ttk.Label(header_frame, text="Adjust your system settings and see real-time predictions", 
                            style='Hint.TLabel', font=('Segoe UI', int(10 * self.scale_factor)))
        subtitle.pack(pady=(0, 0))
        
        # Configuration panel - simplified for better performance, more compact
        form_frame = ttk.LabelFrame(main_container, text="", padding=10)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a container for inputs - two column layout
        input_container = tk.Frame(form_frame, bg=COLORS['bg'])
        input_container.pack(fill=tk.X)
        
        # Left column - Solar panels section
        left_column = tk.Frame(input_container, bg=COLORS['bg'])
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Solar Panels header with colored icon - more compact
        panel_header = tk.Frame(left_column, bg=COLORS['bg'])
        panel_header.pack(anchor=tk.W, pady=(0, 6))
        panel_icon = tk.Label(panel_header, text="🔆", font=('Segoe UI', int(14 * self.scale_factor)), 
                             bg=COLORS['bg'], fg=COLORS['solar_gold'])
        panel_icon.pack(side=tk.LEFT, padx=(0, 6))
        panel_label = ttk.Label(panel_header, text="Solar Panels", 
                               font=('Segoe UI', int(11 * self.scale_factor), 'bold'))
        panel_label.pack(side=tk.LEFT)
        
        self._add_input(left_column, "Number of panels:", self.panel_count, "panels")
        self._add_input(left_column, "Panel efficiency:", self.panel_eff, "from datasheet (0.20 = 20%)")
        self._add_input(left_column, "Area per panel (m²):", self.panel_area, "size of one panel")
        
        # Right column - Batteries section
        right_column = tk.Frame(input_container, bg=COLORS['bg'])
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Batteries header with colored icon - more compact
        battery_header = tk.Frame(right_column, bg=COLORS['bg'])
        battery_header.pack(anchor=tk.W, pady=(0, 6))
        battery_icon = tk.Label(battery_header, text="🔋", font=('Segoe UI', int(14 * self.scale_factor)), 
                               bg=COLORS['bg'], fg=COLORS['accent'])
        battery_icon.pack(side=tk.LEFT, padx=(0, 6))
        battery_label = ttk.Label(battery_header, text="Batteries", 
                                 font=('Segoe UI', int(11 * self.scale_factor), 'bold'))
        battery_label.pack(side=tk.LEFT)
        
        self._add_input(right_column, "Number of batteries:", self.battery_count, "total batteries")
        self._add_input(right_column, "Capacity per battery (kWh):", self.battery_capacity, "storage capacity")
        self._add_input(right_column, "Max charge rate (kW):", self.battery_rate, "charge speed")
        
        # Buttons section - more compact
        btn_container = tk.Frame(form_frame, bg=COLORS['bg'])
        btn_container.pack(fill=tk.X, pady=(10, 0))
        
        # Actions header with colored icon - more compact
        actions_header = tk.Frame(btn_container, bg=COLORS['bg'])
        actions_header.pack(anchor=tk.W, pady=(0, 6))
        actions_icon = tk.Label(actions_header, text="⚡", font=('Segoe UI', int(14 * self.scale_factor)), 
                               bg=COLORS['bg'], fg=COLORS['accent'])
        actions_icon.pack(side=tk.LEFT, padx=(0, 6))
        actions_label = ttk.Label(actions_header, text="Actions", 
                                  font=('Segoe UI', int(11 * self.scale_factor), 'bold'))
        actions_label.pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(btn_container, bg=COLORS['bg'])
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="▶️ Run Pipeline", command=self._run_with_settings, width=18).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="💾 Save & Run", command=self._save_and_run, width=18).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="🔄 Refresh", command=self._refresh_data, width=18).pack(side=tk.LEFT)
        
        # Results section header with toggle switch
        results_header = tk.Frame(main_container, bg=COLORS['bg'])
        results_header.pack(fill=tk.X, pady=(16, 8))
        
        # Forecast Results label on the left
        results_title = tk.Label(results_header, text="📊 Forecast Results", 
                                font=('Segoe UI', int(11 * self.scale_factor), 'bold'),
                                bg=COLORS['bg'], fg=COLORS['accent'])
        results_title.pack(side=tk.LEFT)
        
        # Toggle switch on the right
        self.toggle_switch = ToggleSwitch(results_header, on_command=self._on_view_mode_changed, 
                                          scale=self.scale_factor)
        self.toggle_switch.pack(side=tk.RIGHT)
        
        # Results table - more compact (no label frame text since we have header)
        results_frame = ttk.LabelFrame(main_container, text="", padding=8)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Table with scrollbars
        table_container = tk.Frame(results_frame, bg=COLORS['bg'])
        table_container.pack(fill=tk.BOTH, expand=True)
        
        # Columns for Latest view (snapshot) vs History view.
        self.latest_cols = [
            'Date', 'DayName', 'SolarRadiation_kWh_m2',
            'PerPanelYield_kWh', 'Chargeable_kWh', 'ChargePercentage'
        ]
        self.history_cols = [
            'Date', 'FetchedAt', 'DayName', 'SolarRadiation_kWh_m2',
            'Chargeable_kWh', 'ChargePercentage'
        ]
        cols = self.latest_cols

        # Short, clear column labels for display (keeps internal column ids unchanged).
        col_labels = {
            'Date': 'Date',
            'FetchedAt': 'Fetched',
            'DayName': 'Day',
            'SolarRadiation_kWh_m2': 'Rad kWh/m²',
            'PerPanelYield_kWh': 'Panel kWh',
            'Chargeable_kWh': 'Charge kWh',
            'ChargePercentage': 'Batt %',
        }
        self.col_labels = col_labels
        
        # Create frame for tree and scrollbar (vertical only)
        tree_frame = tk.Frame(table_container, bg=COLORS['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=12)
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview, style='Vertical.TScrollbar')
        self.tree.configure(yscroll=vsb.set)
        
        # Grid layout for tree and scrollbar
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Set appropriate column widths for better fit without horizontal scroll - more compact
        self.latest_col_widths = {
            'Date': int(100 * self.scale_factor),
            'DayName': int(100 * self.scale_factor),
            'SolarRadiation_kWh_m2': int(130 * self.scale_factor),
            'PerPanelYield_kWh': int(120 * self.scale_factor),
            'Chargeable_kWh': int(130 * self.scale_factor),
            'ChargePercentage': int(100 * self.scale_factor)
        }
        self.history_col_widths = {
            'Date': int(100 * self.scale_factor),
            'FetchedAt': int(160 * self.scale_factor),
            'DayName': int(100 * self.scale_factor),
            'SolarRadiation_kWh_m2': int(130 * self.scale_factor),
            'Chargeable_kWh': int(130 * self.scale_factor),
            'ChargePercentage': int(100 * self.scale_factor)
        }

        # Store column configuration for responsive resizing (init to Latest)
        self._apply_table_mode("Latest")
        
        for col in cols:
            self.tree.heading(col, text=self.col_labels.get(col, col))
            width = self.col_widths.get(col, int(110 * self.scale_factor))
            self.tree.column(col, anchor=tk.CENTER, width=width, stretch=True)
        
        # Bind window resize event to adjust table columns
        self.root.bind('<Configure>', self._on_window_resize)
        self._last_width = self.root.winfo_width()
        
        # Status bar - more compact
        status_frame = tk.Frame(self.root, bg=COLORS['border'], height=int(28 * self.scale_factor))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status = tk.Label(status_frame, text="✓ Ready to run", 
                              bg=COLORS['border'], fg=COLORS['fg'],
                              font=('Segoe UI', int(9 * self.scale_factor)), anchor=tk.W, padx=10)
        self.status.pack(fill=tk.BOTH, expand=True)
    
    def _on_window_resize(self, event=None):
        """Adjust table columns based on window width"""
        if event and event.widget != self.root:
            return
        
        current_width = self.root.winfo_width()
        if current_width == 1:  # Window not yet rendered
            return
        
        # Only adjust if width changed significantly (more than 50px)
        if abs(current_width - self._last_width) < 50:
            return
        
        self._last_width = current_width
        
        # Calculate available width for table (account for padding, scrollbar, etc.)
        # Rough estimate: window width - margins - scrollbar - padding
        available_width = current_width - 100
        
        # Calculate minimum width needed for all columns
        min_total_width = sum(self.col_widths.values())
        
        if available_width < min_total_width:
            # Hide less important columns
            sorted_cols = sorted(self.cols, key=lambda c: self.col_priority.get(c, 999))
            visible_cols = []
            width_used = 0
            
            for col in sorted_cols:
                col_width = self.col_widths.get(col, int(110 * self.scale_factor))
                if width_used + col_width <= available_width:
                    visible_cols.append(col)
                    width_used += col_width
                else:
                    # Hide this column and less important ones
                    break
            
            # Show/hide columns
            for col in self.cols:
                if col in visible_cols:
                    self.tree.column(col, width=self.col_widths.get(col, int(110 * self.scale_factor)), stretch=True)
                else:
                    self.tree.column(col, width=0, stretch=False)
        else:
            # Show all columns with proper widths
            for col in self.cols:
                self.tree.column(col, width=self.col_widths.get(col, int(110 * self.scale_factor)), stretch=True)
    
    def _add_input(self, parent, label_text, variable, hint_text):
        """Helper to add a labeled input with hint - optimized for readability, more compact"""
        container = tk.Frame(parent, bg=COLORS['bg'])
        container.pack(fill=tk.X, pady=5)
        
        # Label row
        label_frame = tk.Frame(container, bg=COLORS['bg'])
        label_frame.pack(fill=tk.X)
        
        ttk.Label(label_frame, text=label_text, 
                 font=('Segoe UI', int(10 * self.scale_factor), 'bold')).pack(anchor=tk.W)
        
        # Input row
        input_frame = tk.Frame(container, bg=COLORS['bg'])
        input_frame.pack(fill=tk.X, pady=(2, 0))
        
        entry = ttk.Entry(input_frame, textvariable=variable, 
                         font=('Segoe UI', int(11 * self.scale_factor)), width=24)
        entry.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Label(input_frame, text=hint_text, style='Hint.TLabel',
                 font=('Segoe UI', int(9 * self.scale_factor))).pack(side=tk.LEFT)
    
    def _load_data(self, show_loading=False):
        """Load prognosis data from CSV and show it"""
        if show_loading:
            self.loading.show("Loading data...")
        
        try:
            mode = self.toggle_switch.get() if hasattr(self, "toggle_switch") else "Latest"
            self._apply_table_mode(mode)

            if mode == "History":
                filepath = HISTORY_PROGNOSIS_PATH
            else:
                filepath = PROGNOSIS_DIR / "battery_prognosis.csv"
                if not filepath.exists():
                    # Backward-compatible fallback to older folder name.
                    legacy = LEGACY_EXPORT_DIR / "battery_prognosis.csv"
                    if legacy.exists():
                        filepath = legacy
            if not filepath.exists():
                self.status.config(text="⚠️ No data found. Run pipeline first.", fg=COLORS['warning'])
                if show_loading:
                    self.loading.hide()
                return
            self.data = pd.read_csv(filepath)
            self._populate_table()
            self.status.config(text=f"✓ Loaded {len(self.data)} records from {filepath}", fg=COLORS['success'])
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
        
        mode = self.toggle_switch.get() if hasattr(self, "toggle_switch") else "Latest"
        if 'Date' in self.data.columns:
            if mode == "Latest":
                # Unique days for snapshot view.
                self.data = self.data.drop_duplicates(subset=['Date'], keep='first')
                self.data = self.data.sort_values('Date').reset_index(drop=True)
            else:
                # History view: keep all rows (sorted newest-first).
                sort_cols = [c for c in ['Date', 'FetchedAt'] if c in self.data.columns]
                if sort_cols:
                    self.data = self.data.sort_values(sort_cols, ascending=[False] * len(sort_cols)).reset_index(drop=True)
        
        # Add rows with alternating background (handled by ttk theme)
        for i, (_, row) in enumerate(self.data.iterrows()):
            values = [row.get(col, '') for col in self.tree['columns']]
            # Format numbers for better readability
            formatted_values = []
            for col, val in zip(self.tree['columns'], values):
                if val == '' or pd.isna(val):
                    formatted_values.append('')
                elif col == 'ChargePercentage':
                    try:
                        formatted_values.append(f"{float(val):.1f}%")
                    except:
                        formatted_values.append(str(val))
                elif 'kWh' in col or 'kW' in col:
                    try:
                        formatted_values.append(f"{float(val):.3f}")
                    except:
                        formatted_values.append(str(val))
                else:
                    formatted_values.append(str(val))
            self.tree.insert('', tk.END, values=formatted_values)

    def _apply_table_mode(self, mode: str) -> None:
        """Switch table columns/widths for Latest vs History."""
        if mode == "History":
            cols = self.history_cols
            self.col_widths = self.history_col_widths
            self.cols = cols
            self.col_priority = {
                'Date': 1,
                'FetchedAt': 2,
                'ChargePercentage': 3,
                'Chargeable_kWh': 4,
                'SolarRadiation_kWh_m2': 5,
                'DayName': 6,
            }
        else:
            cols = self.latest_cols
            self.col_widths = self.latest_col_widths
            self.cols = cols
            self.col_priority = {
                'Date': 1,
                'DayName': 2,
                'ChargePercentage': 3,
                'Chargeable_kWh': 4,
                'SolarRadiation_kWh_m2': 5,
                'PerPanelYield_kWh': 6,
            }

        # Reconfigure tree columns/headings.
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=self.col_labels.get(col, col))
            width = self.col_widths.get(col, int(110 * self.scale_factor))
            self.tree.column(col, anchor=tk.CENTER, width=width, stretch=True)

    def _on_view_mode_changed(self):
        """Handle view mode change from toggle switch"""
        self._load_data(show_loading=True)

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
