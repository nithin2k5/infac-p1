"""Main Tkinter GUI application for Raspberry Pi Monitor."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import csv
import threading
import sys

from .config import Config
from .db_reader import DatabaseReader

logger = logging.getLogger(__name__)

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available. Graphs will be disabled.")

logger = logging.getLogger(__name__)


class MonitorGUI:
    """Main application GUI for monitoring events."""
    
    def __init__(self):
        """Initialize the application."""
        # Load configuration
        self.config = Config()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize database reader
        db_config = self.config.get_database_config()
        try:
            self.db = DatabaseReader(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 3306),
                user=db_config.get("user", "root"),
                password=db_config.get("password", ""),
                database=db_config.get("database", "ebpc")
            )
            
            # Test connection
            if not self.db.test_connection():
                raise ConnectionError("Cannot connect to database")
        except Exception as e:
            messagebox.showerror(
                "Database Error",
                f"Cannot connect to database:\n{e}\n\nPlease check your configuration."
            )
            sys.exit(1)
        
        # UI configuration (refresh from DB matches GPIO poll rate unless ui overrides)
        ui_config = self.config.get_ui_config()
        gpio_poll = float(self.config.get("gpio.poll_interval", 0.5))
        self.auto_refresh_interval = float(ui_config.get("auto_refresh_interval", gpio_poll))
        self.page_size = ui_config.get("default_page_size", 100)
        self.show_utc = ui_config.get("show_utc", False)
        
        # State
        self.current_page = 0
        self.total_events = 0
        self.eb_history_page = 0
        self.total_eb_history = 0
        self.selected_events: List[int] = []
        self.auto_refresh_enabled = False
        self.auto_refresh_timer: Optional[threading.Timer] = None
        self.dashboard_auto_refresh_enabled = False
        self.dashboard_auto_refresh_timer: Optional[threading.Timer] = None
        
        # Current filters
        self.filters = {
            'input_id': None,
            'start_time': None,
            'end_time': None,
            'event_type': None,
            'search_text': None
        }
        
        # Sort settings
        self.sort_column = "timestamp"
        self.sort_desc = True
        
        # Create main window
        self.root = tk.Tk()
        window_width = ui_config.get("window_width", 1200)
        window_height = ui_config.get("window_height", 800)
        self.root.title("Raspberry Pi Monitor - Power Status & Events")
        self.root.minsize(900, 600)
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.attributes("-fullscreen", False)
        self._apply_maximized_window()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)
        
        # Setup UI
        self._build_ui()
        
        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # Load initial data and start dashboard auto-refresh automatically
        self.refresh_data()
        self.root.after(100, self._start_dashboard_auto_refresh)
    
    def _start_dashboard_auto_refresh(self) -> None:
        self.dashboard_auto_refresh_var.set(True)
        self.dashboard_auto_refresh_enabled = True
        self._schedule_dashboard_auto_refresh()

    def _apply_maximized_window(self) -> None:
        try:
            self.root.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.root.attributes("-zoomed", True)
            return
        except tk.TclError:
            pass
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
        except Exception:
            pass
    
    def _on_close(self) -> None:
        if self.auto_refresh_timer:
            self.auto_refresh_timer.cancel()
            self.auto_refresh_timer = None
        if self.dashboard_auto_refresh_timer:
            self.dashboard_auto_refresh_timer.cancel()
            self.dashboard_auto_refresh_timer = None
        self.root.destroy()
    
    def _build_ui(self) -> None:
        """Build the main UI components with two-page interface."""
        # Status bar (at top for outage indicator and connection)
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.outage_label = ttk.Label(
            self.status_frame,
            text="",
            background="",
            font=("Arial", 10, "bold")
        )
        self.outage_label.pack(side=tk.LEFT)
        
        # Connection status
        self.connection_label = ttk.Label(
            self.status_frame,
            text="● Connected",
            foreground="green",
            font=("Arial", 9)
        )
        self.connection_label.pack(side=tk.RIGHT)
        
        # Create Notebook (Tab container)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Page 1: Status Dashboard
        self.dashboard_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.dashboard_frame, text="Status Dashboard")
        self._build_dashboard_page()
        
        # Page 2: Report Page
        self.report_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.report_frame, text="Events Report")
        self._build_report_page()
        
        # Page 3: EB Power History
        self.eb_history_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.eb_history_frame, text="EB Power History")
        self._build_eb_history_page()
        
        # Page 4: Settings / Notifications
        self.settings_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.settings_frame, text="Notifications Settings")
        self._build_settings_page()
    
    def _build_dashboard_page(self) -> None:
        """
        Build the Status Dashboard page (Page 1).
        
        Layout:
          - Title (fixed)
          - Status indicators area pinned to ~40% of the page height
          - Combined graph for all 4 power inputs in the remaining space
        """
        self.dashboard_frame.columnconfigure(0, weight=1)
        self.dashboard_frame.rowconfigure(0, weight=0)
        self.dashboard_frame.rowconfigure(1, weight=2)
        self.dashboard_frame.rowconfigure(2, weight=0)
        self.dashboard_frame.rowconfigure(3, weight=3)
        self.dashboard_frame.rowconfigure(4, weight=0)
        
        # Title
        title_label = ttk.Label(
            self.dashboard_frame,
            text="Generator Power Status Monitor",
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky="w")
        
        # ========== SECTION 1: STATUS INDICATORS (TOP ~40%) ==========
        indicators_section = ttk.LabelFrame(
            self.dashboard_frame,
            text="Status Indicators",
            padding="10"
        )
        indicators_section.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Container for status cards (single row: EB + two generators)
        cards_container = ttk.Frame(indicators_section)
        cards_container.pack(fill=tk.BOTH, expand=True)
        
        # Create status cards for each input
        self.status_cards = {}
        inputs = [
            ('eb',   'EB (Electricity Board)', 'Main Power'),
            ('gen1', 'GEN1',                   'Generator 1'),
            ('gen2', 'GEN2',                   'Generator 2'),
            ('gen3', 'GEN3',                   'Generator 3'),
        ]
        
        for col, (input_id, title, subtitle) in enumerate(inputs):
            # Status card frame (reduced padding for smaller size)
            card_frame = ttk.LabelFrame(cards_container, text=title, padding="10")
            card_frame.grid(row=0, column=col, padx=10, pady=10, sticky="nsew")
            
            cards_container.columnconfigure(col, weight=1)
        
            # Build status card
            self._build_status_card(card_frame, input_id, subtitle)
        
        # ========== SECTION 2: DAILY SUMMARY ==========
        summary_section = ttk.LabelFrame(
            self.dashboard_frame,
            text="Today's Summary",
            padding="8"
        )
        summary_section.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self._build_summary_section(summary_section)

        # ========== SECTION 3: COMBINED GRAPH ==========
        graph_section = ttk.LabelFrame(
            self.dashboard_frame,
            text="Power Inputs History (All Sources)",
            padding="10"
        )
        graph_section.grid(row=3, column=0, sticky="nsew", pady=(0, 10))

        self._build_graph_panel(graph_section)

        # Bottom controls
        controls_frame = ttk.Frame(self.dashboard_frame)
        controls_frame.grid(row=4, column=0, sticky="ew", pady=(0, 5))
        
        # Last updated label
        self.last_updated_label = ttk.Label(
            controls_frame,
            text="Last updated: Never",
            font=("Arial", 9),
            foreground="gray"
        )
        self.last_updated_label.pack(side=tk.LEFT, padx=5)
        
        # Refresh button and auto-refresh checkbox
        refresh_frame = ttk.Frame(controls_frame)
        refresh_frame.pack(side=tk.RIGHT)
        
        refresh_btn = ttk.Button(
            refresh_frame,
            text="Refresh Status",
            command=self.refresh_data
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.dashboard_auto_refresh_var = tk.BooleanVar()
        dashboard_auto_refresh_cb = ttk.Checkbutton(
            refresh_frame,
            text=f"Auto-refresh ({self.auto_refresh_interval:g}s)",
            variable=self.dashboard_auto_refresh_var,
            command=self.toggle_dashboard_auto_refresh
        )
        dashboard_auto_refresh_cb.pack(side=tk.LEFT, padx=5)
    
    def _build_status_card(self, parent, input_id: str, subtitle: str) -> None:
        """Build a status card for an input with LED and graphical representation."""
        # Subtitle
        ttk.Label(
            parent,
            text=subtitle,
            font=("Arial", 9),
            foreground="gray"
        ).pack(pady=(0, 8))
        
        # LED indicator (larger for dashboard)
        led_container = ttk.Frame(parent)
        led_container.pack(pady=5)
        
        # Slightly smaller LED to reduce overall card height
        led_canvas = tk.Canvas(led_container, width=70, height=70, highlightthickness=0, bg='white')
        led_canvas.pack()
        
        # Draw LED circle (will be updated based on state)
        glow_circle = led_canvas.create_oval(3, 3, 67, 67, fill="#ff9999", outline="", state="normal")
        led_circle = led_canvas.create_oval(18, 18, 52, 52, fill="#ff3333", outline="#cc0000", width=2)

        # Status label
        status_label = ttk.Label(
            parent,
            text="OFF",
            font=("Arial", 11, "bold"),
            foreground="#cc0000"
        )
        status_label.pack(pady=3)
        
        # Timestamp label
        timestamp_label = ttk.Label(
            parent,
            text="Last update: N/A",
            font=("Arial", 8),
            foreground="gray"
        )
        timestamp_label.pack(pady=3)
        
        # Store references
        self.status_cards[input_id] = {
            'canvas': led_canvas,
            'circle': led_circle,
            'glow_circle': glow_circle,
            'status_label': status_label,
            'timestamp_label': timestamp_label,
            'state': None
        }
    
    def _build_graph_panel(self, parent) -> None:
        """Build graph panel showing state history for EB, GEN1, GEN2."""
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(
                parent,
                text="Graph plotting unavailable. Install matplotlib to enable graphs.",
                foreground="red"
            ).pack()
            return
        
        # Create matplotlib figure - larger for bottom section
        self.graph_fig = Figure(figsize=(12, 5), dpi=100)
        self.graph_ax = self.graph_fig.add_subplot(111)
        
        # Initial axis configuration (will be refined on each update)
        self.graph_ax.set_xlabel('Time')
        self.graph_ax.set_ylabel('Inputs')
        self.graph_ax.set_title('Power Inputs Timeline')
        self.graph_ax.grid(True, alpha=0.3)
        
        # Embed in tkinter
        self.graph_canvas = FigureCanvasTkAgg(self.graph_fig, parent)
        self.graph_canvas.draw()
        self.graph_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Store graph reference
        self.graph_frame = parent

    def _build_summary_section(self, parent) -> None:
        """Build the today's summary table inside the given LabelFrame."""
        from datetime import datetime as _dt
        hour = 6
        now = _dt.now()
        range_text = f"Today  {hour}:00 AM  →  {now.strftime('%I:%M %p')}"

        ttk.Label(parent, text=range_text, font=("Arial", 9), foreground="gray").grid(
            row=0, column=0, columnspan=5, sticky="w", pady=(0, 6)
        )

        headers = ["", "Power ON Duration", "Power OFF Duration", "No. of Power Cuts"]
        col_widths = [8, 22, 22, 18]
        for c, (h, w) in enumerate(zip(headers, col_widths)):
            ttk.Label(
                parent, text=h,
                font=("Arial", 9, "bold"),
                width=w,
                anchor="center"
            ).grid(row=1, column=c, padx=6, pady=2, sticky="ew")

        self._summary_rows = {}
        row_labels = [("eb", "EB"), ("gen1", "GEN1"), ("gen2", "GEN2"), ("gen3", "GEN3")]
        for r, (input_id, label) in enumerate(row_labels, start=2):
            ttk.Label(parent, text=label, font=("Arial", 9, "bold"), width=8, anchor="w").grid(
                row=r, column=0, padx=(10, 4), pady=2, sticky="w"
            )
            on_var = tk.StringVar(value="-")
            off_var = tk.StringVar(value="-")
            cuts_var = tk.StringVar(value="-")

            ttk.Label(parent, textvariable=on_var, font=("Arial", 9), width=22, anchor="center",
                      foreground="#009933").grid(row=r, column=1, padx=6, pady=2, sticky="ew")
            ttk.Label(parent, textvariable=off_var, font=("Arial", 9), width=22, anchor="center",
                      foreground="#cc0000").grid(row=r, column=2, padx=6, pady=2, sticky="ew")
            ttk.Label(parent, textvariable=cuts_var, font=("Arial", 9), width=18, anchor="center").grid(
                row=r, column=3, padx=6, pady=2, sticky="ew"
            )
            self._summary_rows[input_id] = (on_var, off_var, cuts_var)

        for c in range(4):
            parent.columnconfigure(c, weight=1 if c > 0 else 0)

    def _format_hrs(self, seconds: float) -> str:
        """Format seconds as H:MM Hrs."""
        seconds = abs(seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}:{m:02d} Hrs"

    def _update_summary(self) -> None:
        """Refresh the daily summary labels."""
        if not hasattr(self, '_summary_rows'):
            return
        try:
            data = self.db.get_daily_summary(since_hour=6)
            for input_id, (on_var, off_var, cuts_var) in self._summary_rows.items():
                d = data.get(input_id, {})
                on_var.set(self._format_hrs(d.get('on_seconds', 0)))
                off_var.set(self._format_hrs(d.get('off_seconds', 0)))
                cuts_var.set(str(d.get('power_cuts', 0)))
        except Exception as e:
            logger.error(f"Error updating summary: {e}")

    def _update_graph(self) -> None:
        """Update the state history graph."""
        if not MATPLOTLIB_AVAILABLE or not hasattr(self, 'graph_ax'):
            return
        
        try:
            # Get last 4 hours of events for better visualization
            end_time = datetime.now().timestamp()
            start_time = end_time - (4 * 3600)  # Last 4 hours
            
            inputs = ['eb', 'gen1', 'gen2', 'gen3']
            input_names = {'eb': 'EB', 'gen1': 'GEN1', 'gen2': 'GEN2', 'gen3': 'GEN3'}
            colors = {
                'eb':   '#0077ff',
                'gen1': '#00aa55',
                'gen2': '#cc0000',
                'gen3': '#ff8800',
            }
            linestyles = {
                'eb':   '-',
                'gen1': ':',
                'gen2': ':',
                'gen3': ':',
            }
            y_positions = {'eb': 3, 'gen1': 2, 'gen2': 1, 'gen3': 0}
            
            # Clear previous plot
            self.graph_ax.clear()
            
            has_data = False
            
            for input_id in inputs:
                try:
                    events, _ = self.db.get_events(
                        input_id=input_id,
                        start_time=start_time,
                        end_time=end_time,
                        limit=5000,
                        order_by="timestamp",
                        order_desc=False
                    )
                    
                    if events and len(events) > 0:
                        has_data = True
                        # Extract timestamps and states
                        times = [datetime.fromtimestamp(e['timestamp']) for e in events]
                        states = [e['state'] for e in events]

                        # Add current state if needed (extend to current time)
                        if times[-1] < datetime.now():
                            times.append(datetime.now())
                            states.append(states[-1])  # Keep last state

                        # Map ON states to the input's row position; hide OFF as gaps
                        y_val = y_positions.get(input_id, 0)
                        y_series = [y_val if s == 1 else np.nan for s in states]

                        input_name = input_names.get(input_id, input_id.upper())

                        # Plot horizontal timeline for ON periods of this input
                        self.graph_ax.step(
                            times,
                            y_series,
                            where='post',
                            label=input_name,
                            linewidth=2.5,
                            color=colors.get(input_id, '#ff0000'),
                            linestyle=linestyles.get(input_id, '-'),
                            alpha=0.9,
                        )
                
                except Exception as e:
                    logger.error(f"Error plotting {input_id}: {e}")
            
            # Configure axis for time vs inputs
            self.graph_ax.set_xlabel('Time', fontsize=10)
            self.graph_ax.set_ylabel('Inputs', fontsize=10)
            self.graph_ax.set_title('EB / GEN1 / GEN2 / GEN3 Timeline (Last 4 Hours)', fontsize=12, fontweight='bold')
            self.graph_ax.set_ylim(-0.5, 3.5)
            self.graph_ax.set_yticks([0, 1, 2, 3])
            self.graph_ax.set_yticklabels(['GEN3', 'GEN2', 'GEN1', 'EB'])
            self.graph_ax.grid(True, alpha=0.3, linestyle='--')
            
            if has_data:
                self.graph_ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
            
            # Format x-axis dates
            self.graph_fig.autofmt_xdate()
            self.graph_fig.tight_layout()
            
            # Redraw canvas
            self.graph_canvas.draw()
            
        except Exception as e:
            logger.error(f"Error updating graph: {e}", exc_info=True)
    
    def _build_report_page(self) -> None:
        """Build the Events Report page (Page 2)."""
        # Statistics panel
        self._build_statistics_panel(self.report_frame)
        
        # Filters panel
        self._build_filters_panel(self.report_frame)
        
        # Main table area
        self._build_table_area(self.report_frame)
        
        # Bottom toolbar
        self._build_toolbar(self.report_frame)
    
    def _build_eb_history_page(self) -> None:
        """Build the EB Power History page (Page 3)."""
        # Title
        title_label = ttk.Label(
            self.eb_history_frame,
            text="EB Power Cut History",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Description
        desc_label = ttk.Label(
            self.eb_history_frame,
            text="Shows when EB power was turned OFF and when it turned back ON, with duration",
            font=("Arial", 9),
            foreground="gray"
        )
        desc_label.pack(pady=(0, 10))
        
        # Table frame
        table_frame = ttk.LabelFrame(self.eb_history_frame, text="Power Cut Events", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Table with scrollbars
        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Define columns
        columns = ("#", "OFF Time", "ON Time", "Duration", "Status")
        self.eb_history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        column_widths = {
            "#": 50,
            "OFF Time": 180,
            "ON Time": 180,
            "Duration": 120,
            "Status": 100
        }
        
        for col in columns:
            self.eb_history_tree.heading(col, text=col)
            self.eb_history_tree.column(col, width=column_widths.get(col, 100))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.eb_history_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.eb_history_tree.xview)
        self.eb_history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.eb_history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Pagination controls
        pagination_frame = ttk.Frame(table_frame)
        pagination_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.eb_history_page_info_label = ttk.Label(pagination_frame, text="Page 1 of 1")
        self.eb_history_page_info_label.pack(side=tk.LEFT)
        
        button_frame = ttk.Frame(pagination_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="◄ First", command=self.eb_history_first_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="◄ Prev", command=self.eb_history_prev_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Next ►", command=self.eb_history_next_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Last ►", command=self.eb_history_last_page).pack(side=tk.LEFT, padx=2)
        
        # Bottom toolbar
        toolbar = ttk.Frame(self.eb_history_frame)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="Refresh (F5)", command=self.refresh_data).pack(side=tk.LEFT, padx=2)
    
    def _build_statistics_panel(self, parent) -> None:
        """Build statistics display panel for report page."""
        stats_frame = ttk.LabelFrame(parent, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Simple inner frame centered within the statistics area
        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(anchor="center")
        
        self.stats_inner = stats_inner
        # No scrolling canvas is used for stats in this layout
        self.stats_canvas = None
    
    def _update_led_indicators(self) -> None:
        """Update LED indicators and power bars on dashboard based on latest states."""
        try:
            latest_states = self.db.get_latest_states()
            
            # Update each status card
            for input_id, card_data in self.status_cards.items():
                state_info = latest_states.get(input_id, {})
                state = state_info.get('state', 0)
                timestamp = state_info.get('timestamp', None)
                
                canvas = card_data['canvas']
                circle_id = card_data['circle']
                glow_circle_id = card_data['glow_circle']
                status_label = card_data['status_label']
                timestamp_label = card_data['timestamp_label']
                
                # Update LED and power representation based on state
                if state == 1:  # ON - Green
                    fill_color = "#00cc44"
                    outline_color = "#009933"
                    status_text = "ON"
                    status_fg = "#009933"
                    power_level = 100
                    power_color = "#00cc44"

                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, fill="#66ffaa", outline="", state="normal")
                        canvas.lower(glow_circle_id, circle_id)
                else:  # OFF - Red
                    fill_color = "#ff3333"
                    outline_color = "#cc0000"
                    status_text = "OFF"
                    status_fg = "#cc0000"
                    power_level = 0
                    power_color = "#ff3333"

                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, fill="#ff9999", outline="", state="normal")
                        canvas.lower(glow_circle_id, circle_id)
                
                # Update LED circle
                canvas.itemconfig(circle_id, fill=fill_color, outline=outline_color, width=3)
                
                # Update status label
                status_label.config(text=status_text, foreground=status_fg)
                
                # Update timestamp
                if timestamp:
                    try:
                        dt = datetime.fromtimestamp(timestamp)
                        timestamp_label.config(text=f"Last update: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    except:
                        timestamp_label.config(text="Last update: N/A")
                else:
                    timestamp_label.config(text="Last update: N/A")
                
                # Store current state
                card_data['state'] = state
            
            # Update last updated time
            if hasattr(self, 'last_updated_label'):
                self.last_updated_label.config(
                    text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
        except Exception as e:
            logger.error(f"Error updating status indicators: {e}", exc_info=True)
    
    def _build_filters_panel(self, parent) -> None:
        """Build filter controls panel."""
        filters_frame = ttk.LabelFrame(parent, text="Filters", padding="10")
        filters_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Input filter
        ttk.Label(filters_frame, text="Input:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.input_var = tk.StringVar()
        self.input_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.input_var,
            values=["All", "eb", "gen1", "gen2", "gen3"],
            state="readonly",
            width=12
        )
        self.input_combo.current(0)
        self.input_combo.grid(row=0, column=1, padx=(0, 15), sticky=tk.W)
        
        # Event type filter
        ttk.Label(filters_frame, text="Event Type:").grid(row=0, column=2, padx=(0, 5), sticky=tk.W)
        self.event_type_var = tk.StringVar()
        self.event_type_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.event_type_var,
            values=["All", "ON", "OFF"],
            state="readonly",
            width=10
        )
        self.event_type_combo.current(0)
        self.event_type_combo.grid(row=0, column=3, padx=(0, 15), sticky=tk.W)
        
        # Start time filter
        ttk.Label(filters_frame, text="Start Time:").grid(row=0, column=4, padx=(0, 5), sticky=tk.W)
        self.start_time_var = tk.StringVar()
        start_time_entry = ttk.Entry(filters_frame, textvariable=self.start_time_var, width=18)
        start_time_entry.grid(row=0, column=5, padx=(0, 15), sticky=tk.W)
        ttk.Button(
            filters_frame,
            text="...",
            width=3,
            command=lambda: self._pick_datetime(self.start_time_var)
        ).grid(row=0, column=6, padx=(0, 15))
        
        # End time filter
        ttk.Label(filters_frame, text="End Time:").grid(row=1, column=0, padx=(0, 5), sticky=tk.W)
        self.end_time_var = tk.StringVar()
        end_time_entry = ttk.Entry(filters_frame, textvariable=self.end_time_var, width=18)
        end_time_entry.grid(row=1, column=1, padx=(0, 15), sticky=tk.W)
        ttk.Button(
            filters_frame,
            text="...",
            width=3,
            command=lambda: self._pick_datetime(self.end_time_var)
        ).grid(row=1, column=2, padx=(0, 15))
        
        # Search filter
        ttk.Label(filters_frame, text="Search:").grid(row=1, column=3, padx=(0, 5), sticky=tk.W)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filters_frame, textvariable=self.search_var, width=20)
        search_entry.grid(row=1, column=4, columnspan=2, padx=(0, 15), sticky=tk.W)
        search_entry.bind('<Return>', lambda e: self.apply_filters())
        
        # Filter buttons
        button_frame = ttk.Frame(filters_frame)
        button_frame.grid(row=1, column=6, columnspan=2, sticky=tk.E)
        
        ttk.Button(button_frame, text="Apply Filters", command=self.apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Clear", command=self.clear_filters).pack(side=tk.LEFT, padx=2)
    
    def _build_table_area(self, parent) -> None:
        """Build main table area with pagination."""
        table_frame = ttk.LabelFrame(parent, text="Events", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Table with scrollbars
        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Define columns
        columns = ("ID", "Input", "State", "Timestamp", "Counter", "On Duration", "Off Interval")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        column_widths = {
            "ID": 50,
            "Input": 100,
            "State": 70,
            "Timestamp": 180,
            "Counter": 70,
            "On Duration": 100,
            "Off Interval": 100
        }
        
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=column_widths.get(col, 100))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Bind selection
        self.tree.bind("<Double-1>", lambda e: self.view_event_details())
        self.tree.bind("<Button-1>", lambda e: self._on_tree_select())
        
        # Pagination controls
        pagination_frame = ttk.Frame(table_frame)
        pagination_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.page_info_label = ttk.Label(pagination_frame, text="Page 1 of 1")
        self.page_info_label.pack(side=tk.LEFT)
        
        button_frame = ttk.Frame(pagination_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="◄ First", command=self.first_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="◄ Prev", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Next ►", command=self.next_page).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Last ►", command=self.last_page).pack(side=tk.LEFT, padx=2)
    
    def _build_toolbar(self, parent) -> None:
        """Build bottom toolbar."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X)
        
        # Left side buttons
        left_frame = ttk.Frame(toolbar)
        left_frame.pack(side=tk.LEFT)
        
        ttk.Button(left_frame, text="View Details", command=self.view_event_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_frame, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_frame, text="Refresh (F5)", command=self.refresh_data).pack(side=tk.LEFT, padx=2)
        
        # Right side controls
        right_frame = ttk.Frame(toolbar)
        right_frame.pack(side=tk.RIGHT)
        
        self.auto_refresh_var = tk.BooleanVar()
        auto_refresh_cb = ttk.Checkbutton(
            right_frame,
            text="Auto-refresh",
            variable=self.auto_refresh_var,
            command=self.toggle_auto_refresh
        )
        auto_refresh_cb.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(right_frame, text="Interval (s):").pack(side=tk.LEFT, padx=2)
        self.interval_var = tk.StringVar(value=str(self.auto_refresh_interval))
        interval_spin = ttk.Spinbox(
            right_frame,
            from_=0.5,
            to=300,
            increment=0.5,
            textvariable=self.interval_var,
            width=5
        )
        interval_spin.pack(side=tk.LEFT, padx=2)
    
    def _pick_datetime(self, var: tk.StringVar) -> None:
        """Simple datetime picker (shows current datetime as default)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Date/Time")
        dialog.geometry("350x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter date/time (YYYY-MM-DD HH:MM:SS):").pack(pady=10)
        entry = ttk.Entry(dialog, width=30)
        entry.insert(0, var.get() or now)
        entry.pack(pady=5)
        entry.focus()
        entry.select_range(0, tk.END)
        
        def set_value():
            var.set(entry.get())
            dialog.destroy()
        
        entry.bind('<Return>', lambda e: set_value())
        ttk.Button(dialog, text="OK", command=set_value).pack(pady=5)
    
    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        self.root.bind('<F5>', lambda e: self.refresh_data())
        self.root.bind('<Control-f>', lambda e: self._focus_search())
        self.root.bind('<Control-e>', lambda e: self.export_csv())
        self.root.bind('<Escape>', lambda e: self.clear_filters())
    
    def _focus_search(self) -> None:
        """Focus search field."""
        # Find and focus the search entry
        widgets = [w for w in self.root.winfo_children() if isinstance(w, ttk.Frame)]
        for frame in widgets:
            for child in frame.winfo_children():
                if isinstance(child, ttk.LabelFrame) and child.cget('text') == 'Filters':
                    for widget in child.winfo_children():
                        if isinstance(widget, ttk.Entry) and widget.cget('textvariable') == str(self.search_var):
                            widget.focus()
                            return
    
    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp for display."""
        dt = datetime.fromtimestamp(timestamp)
        if self.show_utc:
            dt = datetime.utcfromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def _format_duration(self, seconds: Optional[float]) -> str:
        """Format duration in human-readable format."""
        if seconds is None:
            return "-"
        seconds = abs(seconds)
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def refresh_data(self) -> None:
        """Refresh all data from database."""
        try:
            # Update connection status
            if not self.db.test_connection():
                self.connection_label.config(text="● Disconnected", foreground="red")
                messagebox.showerror("Connection Error", "Cannot connect to database")
                return
            
            self.connection_label.config(text="● Connected", foreground="green")
            
            # Load events (only if on report page)
            if hasattr(self, 'tree'):
                self._load_events()
                
                # Update statistics
                self._update_statistics()
            
            # Update outage indicator
            self._update_outage_indicator()
            
            # Update dashboard status indicators (LEDs and power bars)
            self._update_led_indicators()
            
            # Update graph
            self._update_graph()

            # Update daily summary
            self._update_summary()

            # Update EB history (only if on EB history page)
            if hasattr(self, 'eb_history_tree'):
                self._load_eb_history()
            
        except Exception as e:
            logger.error(f"Error refreshing data: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to refresh data: {e}")
            self.connection_label.config(text="● Error", foreground="red")
    
    def _load_events(self) -> None:
        """Load events from database with current filters and pagination."""
        try:
            # Convert filters
            input_id = self.filters['input_id'] if self.filters['input_id'] != "All" else None
            event_type = self.filters['event_type'] if self.filters['event_type'] != "All" else None
            
            start_time = None
            if self.filters['start_time']:
                try:
                    start_time = datetime.strptime(self.filters['start_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                except:
                    pass
            
            end_time = None
            if self.filters['end_time']:
                try:
                    end_time = datetime.strptime(self.filters['end_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                except:
                    pass
            
            # Map sort column
            sort_map = {
                "ID": "id",
                "Timestamp": "timestamp",
                "Counter": "event_counter",
                "Input": "input_id"
            }
            order_by = sort_map.get(self.sort_column, "timestamp")
            
            # Get events
            offset = self.current_page * self.page_size
            events, total = self.db.get_events(
                input_id=input_id,
                start_time=start_time,
                end_time=end_time,
                event_type=event_type,
                search_text=self.filters['search_text'],
                limit=self.page_size,
                offset=offset,
                order_by=order_by,
                order_desc=self.sort_desc
            )
            
            self.total_events = total
            
            # Clear table
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Populate table with properly formatted data
            for event in events:
                state_str = "ON" if event['state'] == 1 else "OFF"
                on_duration = self._format_duration(event.get('on_duration'))
                off_interval = self._format_duration(event.get('off_interval'))
                timestamp_str = self._format_timestamp(event['timestamp'])
                
                # Format timestamp for better readability
                dt = datetime.fromtimestamp(event['timestamp'])
                formatted_time = dt.strftime('%Y-%m-%d\n%H:%M:%S')
                
                self.tree.insert("", tk.END, values=(
                    event['id'],
                    event['input_name'],
                    state_str,
                    timestamp_str,
                    event['event_counter'],
                    on_duration,
                    off_interval
                ), tags=(str(event['id']),))
            
            # Update pagination info
            total_pages = (total + self.page_size - 1) // self.page_size if total > 0 else 1
            current_page_display = self.current_page + 1 if total > 0 else 0
            self.page_info_label.config(
                text=f"Page {current_page_display} of {total_pages} ({total} total events)"
            )
            
        except Exception as e:
            logger.error(f"Error loading events: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load events: {e}")
    
    def _update_statistics(self) -> None:
        """Update statistics panel."""
        try:
            # Clear existing stats
            for widget in self.stats_inner.winfo_children():
                widget.destroy()
            
            # Get statistics
            start_time = None
            end_time = None
            if self.filters['start_time']:
                try:
                    start_time = datetime.strptime(self.filters['start_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                except:
                    pass
            if self.filters['end_time']:
                try:
                    end_time = datetime.strptime(self.filters['end_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                except:
                    pass
            
            stats = self.db.get_statistics(
                input_id=self.filters['input_id'] if self.filters['input_id'] != "All" else None,
                start_time=start_time,
                end_time=end_time
            )
            
            # Display stats
            stat_items = [
                ("Total Events", str(stats.get('total_events', 0))),
                ("Inputs", str(stats.get('unique_inputs', 0))),
                ("ON Events", str(stats.get('counts_by_state', {}).get('ON', 0))),
                ("OFF Events", str(stats.get('counts_by_state', {}).get('OFF', 0))),
            ]
            
            if stats.get('outages', {}).get('total', 0) > 0:
                avg_dur = stats['outages'].get('avg_duration', 0)
                stat_items.append(("Outages", f"{stats['outages']['total']} (avg: {self._format_duration(avg_dur)})"))
            
            for label, value in stat_items:
                frame = ttk.Frame(self.stats_inner)
                # Pack side-by-side, centered as a group, with small 2px spacing
                frame.pack(side=tk.LEFT, padx=2, pady=2)
                ttk.Label(frame, text=label, font=("Arial", 9)).pack()
                ttk.Label(frame, text=value, font=("Arial", 11, "bold")).pack()
            
            # Update layout if a canvas were present (kept safe for future changes)
            if getattr(self, "stats_canvas", None) is not None:
                self.stats_inner.update_idletasks()
                self.stats_canvas.configure(scrollregion=self.stats_canvas.bbox("all"))
            
        except Exception as e:
            logger.error(f"Error updating statistics: {e}", exc_info=True)
    
    def _update_outage_indicator(self) -> None:
        """Update outage status indicator."""
        try:
            # Check latest states
            latest_states = self.db.get_latest_states()
            active_outage = self.db.get_active_outage()
            
            eb_info = latest_states.get('eb')
            if not eb_info:
                self.outage_label.config(text="", background="")
                return
            eb_state = eb_info.get('state')
            if eb_state is None:
                self.outage_label.config(text="", background="")
                return
            
            if eb_state == 0 or active_outage:
                if active_outage:
                    duration = datetime.now().timestamp() - active_outage['outage_start']
                    duration_str = self._format_duration(duration)
                    self.outage_label.config(
                        text=f"ACTIVE OUTAGE - Duration: {duration_str}",
                        background="#ffcccc",
                        foreground="#cc0000"
                    )
                else:
                    self.outage_label.config(
                        text="EB POWER CUT DETECTED",
                        background="#ffcccc",
                        foreground="#cc0000"
                    )
            else:
                self.outage_label.config(text="", background="")
                
        except Exception as e:
            logger.error(f"Error updating outage indicator: {e}", exc_info=True)
    
    def apply_filters(self) -> None:
        """Apply current filter values."""
        self.filters['input_id'] = self.input_var.get()
        self.filters['event_type'] = self.event_type_var.get()
        self.filters['start_time'] = self.start_time_var.get() or None
        self.filters['end_time'] = self.end_time_var.get() or None
        self.filters['search_text'] = self.search_var.get() or None
        
        self.current_page = 0
        self.refresh_data()
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        self.input_var.set("All")
        self.event_type_var.set("All")
        self.start_time_var.set("")
        self.end_time_var.set("")
        self.search_var.set("")
        self.apply_filters()
    
    def _sort_column(self, column: str) -> None:
        """Handle column sorting."""
        if self.sort_column == column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = column
            self.sort_desc = True
        self.refresh_data()
    
    def _on_tree_select(self) -> None:
        """Handle tree selection."""
        selected_items = self.tree.selection()
        self.selected_events = []
        for item in selected_items:
            values = self.tree.item(item)['values']
            if values:
                self.selected_events.append(values[0])  # ID is first column
    
    def first_page(self) -> None:
        """Go to first page."""
        self.current_page = 0
        self.refresh_data()
    
    def prev_page(self) -> None:
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_data()
    
    def next_page(self) -> None:
        """Go to next page."""
        total_pages = (self.total_events + self.page_size - 1) // self.page_size if self.total_events > 0 else 1
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh_data()
    
    def last_page(self) -> None:
        """Go to last page."""
        total_pages = (self.total_events + self.page_size - 1) // self.page_size if self.total_events > 0 else 1
        if total_pages > 0:
            self.current_page = total_pages - 1
            self.refresh_data()
    
    def _load_eb_history(self) -> None:
        """Load EB power history from database with pagination."""
        try:
            # Get EB history with pagination
            offset = self.eb_history_page * self.page_size
            history, total = self.db.get_eb_power_history(
                limit=self.page_size,
                offset=offset
            )
            
            self.total_eb_history = total
            
            # Clear table
            for item in self.eb_history_tree.get_children():
                self.eb_history_tree.delete(item)
            
            # Populate table
            for idx, event in enumerate(history, start=offset + 1):
                off_time_str = self._format_timestamp(event['off_time'])
                on_time_str = self._format_timestamp(event['on_time']) if event['on_time'] else "Ongoing"
                duration_str = self._format_duration(event['duration_seconds']) if event['duration_seconds'] else "-"
                status = event['status']
                
                # Color code: Ongoing = red, Completed = green
                tag = "ongoing" if status == "Ongoing" else "completed"
                self.eb_history_tree.insert(
                    "", tk.END,
                    values=(idx, off_time_str, on_time_str, duration_str, status),
                    tags=(tag,)
                )
            
            # Configure tag colors
            self.eb_history_tree.tag_configure("ongoing", foreground="red")
            self.eb_history_tree.tag_configure("completed", foreground="green")
            
            # Update pagination info
            total_pages = (total + self.page_size - 1) // self.page_size if total > 0 else 1
            current_page_display = self.eb_history_page + 1 if total > 0 else 0
            self.eb_history_page_info_label.config(
                text=f"Page {current_page_display} of {total_pages} ({total} total events)"
            )
            
        except Exception as e:
            logger.error(f"Error loading EB history: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load EB history: {e}")
    
    def eb_history_first_page(self) -> None:
        """Go to first page of EB history."""
        self.eb_history_page = 0
        self._load_eb_history()
    
    def eb_history_prev_page(self) -> None:
        """Go to previous page of EB history."""
        if self.eb_history_page > 0:
            self.eb_history_page -= 1
            self._load_eb_history()
    
    def eb_history_next_page(self) -> None:
        """Go to next page of EB history."""
        total_pages = (self.total_eb_history + self.page_size - 1) // self.page_size if self.total_eb_history > 0 else 1
        if self.eb_history_page < total_pages - 1:
            self.eb_history_page += 1
            self._load_eb_history()
    
    def eb_history_last_page(self) -> None:
        """Go to last page of EB history."""
        total_pages = (self.total_eb_history + self.page_size - 1) // self.page_size if self.total_eb_history > 0 else 1
        if total_pages > 0:
            self.eb_history_page = total_pages - 1
            self._load_eb_history()
    
    def view_event_details(self) -> None:
        """View details of selected event."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select an event to view details.")
            return
        
        item = selected_items[0]
        values = self.tree.item(item)['values']
        event_id = values[0]
        
        try:
            event = self.db.get_event(event_id)
            if not event:
                messagebox.showerror("Error", f"Event {event_id} not found.")
                return
            
            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Event Details - ID {event_id}")
            details_window.geometry("600x700")
            details_window.transient(self.root)
            
            # Create scrollable text widget
            frame = ttk.Frame(details_window, padding="10")
            frame.pack(fill=tk.BOTH, expand=True)
            
            text_widget = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10, font=("Courier", 10))
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Format event details
            state_str = "ON" if event['state'] == 1 else "OFF"
            details_text = f"""EVENT DETAILS
{'='*50}

ID: {event['id']}
Input ID: {event['input_id']}
Input Name: {event['input_name']}
State: {state_str}
Timestamp: {self._format_timestamp(event['timestamp'])}
Event Counter: {event['event_counter']}

DURATIONS
{'='*50}
On Duration: {self._format_duration(event.get('on_duration'))}
Off Interval: {self._format_duration(event.get('off_interval'))}

PREVIOUS TIMES
{'='*50}
Previous Off Time: {self._format_timestamp(event['previous_off_time']) if event.get('previous_off_time') else 'N/A'}
Previous On Time: {self._format_timestamp(event['previous_on_time']) if event.get('previous_on_time') else 'N/A'}

METADATA
{'='*50}
{self._format_metadata(event.get('metadata', {}))}
"""
            text_widget.insert(tk.END, details_text)
            text_widget.config(state=tk.DISABLED)
            
            # Close button
            ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=10)
            
        except Exception as e:
            logger.error(f"Error viewing event details: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load event details: {e}")
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata dictionary as string."""
        if not metadata:
            return "  None"
        
        lines = []
        for key, value in metadata.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
    
    def export_csv(self) -> None:
        """Export events to CSV file."""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            # Determine what to export
            if self.selected_events:
                # Export selected events
                events = []
                for event_id in self.selected_events:
                    event = self.db.get_event(event_id)
                    if event:
                        events.append(event)
            else:
                # Export all filtered events (no pagination limit)
                input_id = self.filters['input_id'] if self.filters['input_id'] != "All" else None
                event_type = self.filters['event_type'] if self.filters['event_type'] != "All" else None
                
                start_time = None
                if self.filters['start_time']:
                    try:
                        start_time = datetime.strptime(self.filters['start_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                    except:
                        pass
                
                end_time = None
                if self.filters['end_time']:
                    try:
                        end_time = datetime.strptime(self.filters['end_time'], "%Y-%m-%d %H:%M:%S").timestamp()
                    except:
                        pass
                
                events, _ = self.db.get_events(
                    input_id=input_id,
                    start_time=start_time,
                    end_time=end_time,
                    event_type=event_type,
                    search_text=self.filters['search_text'],
                    limit=None,  # Get all
                    offset=0
                )
            
            # Write CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header with proper formatting
                writer.writerow([
                    'ID', 'Input ID', 'Input Name', 'State', 'Timestamp',
                    'Date', 'Time', 'Event Counter', 'On Duration', 'Off Interval',
                    'On Duration (seconds)', 'Off Interval (seconds)'
                ])
                
                # Data rows with formatted timings
                for event in events:
                    state_str = "ON" if event['state'] == 1 else "OFF"
                    timestamp = event['timestamp']
                    dt = datetime.fromtimestamp(timestamp)
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M:%S')
                    timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Format durations
                    on_duration_seconds = event.get('on_duration')
                    off_interval_seconds = event.get('off_interval')
                    
                    on_duration_formatted = self._format_duration(on_duration_seconds) if on_duration_seconds else '-'
                    off_interval_formatted = self._format_duration(off_interval_seconds) if off_interval_seconds else '-'
                    
                    writer.writerow([
                        event['id'],
                        event['input_id'],
                        event['input_name'],
                        state_str,
                        timestamp_str,
                        date_str,
                        time_str,
                        event['event_counter'],
                        on_duration_formatted,
                        off_interval_formatted,
                        on_duration_seconds if on_duration_seconds else '',
                        off_interval_seconds if off_interval_seconds else ''
                    ])
            
            messagebox.showinfo("Success", f"Exported {len(events)} event(s) to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export CSV: {e}")
    
    def toggle_auto_refresh(self) -> None:
        """Toggle auto-refresh functionality."""
        self.auto_refresh_enabled = self.auto_refresh_var.get()
        
        if self.auto_refresh_enabled:
            self._schedule_auto_refresh()
        else:
            if self.auto_refresh_timer:
                self.auto_refresh_timer.cancel()
                self.auto_refresh_timer = None
    
    def toggle_dashboard_auto_refresh(self) -> None:
        """Toggle auto-refresh for dashboard."""
        self.dashboard_auto_refresh_enabled = self.dashboard_auto_refresh_var.get()
        
        if self.dashboard_auto_refresh_enabled:
            self._schedule_dashboard_auto_refresh()
        else:
            if self.dashboard_auto_refresh_timer:
                self.dashboard_auto_refresh_timer.cancel()
                self.dashboard_auto_refresh_timer = None
    
    def _schedule_dashboard_auto_refresh(self) -> None:
        """Schedule next dashboard auto-refresh."""
        if self.dashboard_auto_refresh_enabled:
            interval = self.auto_refresh_interval
            self.refresh_data()
            self.dashboard_auto_refresh_timer = threading.Timer(float(interval), self._schedule_dashboard_auto_refresh)
            self.dashboard_auto_refresh_timer.daemon = True
            self.dashboard_auto_refresh_timer.start()
    
    def _schedule_auto_refresh(self) -> None:
        """Schedule next auto-refresh."""
        if self.auto_refresh_enabled:
            try:
                interval = int(self.interval_var.get())
                self.auto_refresh_interval = interval
            except:
                interval = self.auto_refresh_interval
            
            self.refresh_data()
            self.auto_refresh_timer = threading.Timer(float(interval), self._schedule_auto_refresh)
            self.auto_refresh_timer.daemon = True
            self.auto_refresh_timer.start()
    
    def _build_settings_page(self) -> None:
        """Build the Settings / Notifications page (Page 4)."""
        # Configure layout
        self.settings_frame.columnconfigure(0, weight=1)
        self.settings_frame.columnconfigure(1, weight=1)
        
        # --- Left Column: SMTP Configuration ---
        smtp_frame = ttk.LabelFrame(self.settings_frame, text="SMTP Configuration", padding="15")
        smtp_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        
        # Enabled Checkbox
        self.email_enabled_var = tk.BooleanVar(value=self.config.get("email.enabled", False))
        ttk.Checkbutton(
            smtp_frame, 
            text="Enable Email Notifications", 
            variable=self.email_enabled_var
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        
        # SMTP Server
        ttk.Label(smtp_frame, text="SMTP Server:").grid(row=1, column=0, sticky="w", pady=5)
        self.smtp_server_var = tk.StringVar(value=self.config.get("email.smtp_server", "smtp.gmail.com"))
        ttk.Entry(smtp_frame, textvariable=self.smtp_server_var, width=30).grid(row=1, column=1, sticky="w", pady=5)
        
        # SMTP Port
        ttk.Label(smtp_frame, text="SMTP Port:").grid(row=2, column=0, sticky="w", pady=5)
        self.smtp_port_var = tk.StringVar(value=str(self.config.get("email.smtp_port", 587)))
        ttk.Entry(smtp_frame, textvariable=self.smtp_port_var, width=10).grid(row=2, column=1, sticky="w", pady=5)
        
        # SMTP Username
        ttk.Label(smtp_frame, text="Username:").grid(row=3, column=0, sticky="w", pady=5)
        self.smtp_user_var = tk.StringVar(value=self.config.get("email.smtp_username", ""))
        ttk.Entry(smtp_frame, textvariable=self.smtp_user_var, width=30).grid(row=3, column=1, sticky="w", pady=5)
        
        # SMTP Password (masked)
        ttk.Label(smtp_frame, text="Password:").grid(row=4, column=0, sticky="w", pady=5)
        self.smtp_pass_var = tk.StringVar(value=self.config.get("email.smtp_password", ""))
        ttk.Entry(smtp_frame, textvariable=self.smtp_pass_var, width=30, show="*").grid(row=4, column=1, sticky="w", pady=5)
        
        # Email From
        ttk.Label(smtp_frame, text="Sender Email:").grid(row=5, column=0, sticky="w", pady=5)
        self.email_from_var = tk.StringVar(value=self.config.get("email.from", ""))
        ttk.Entry(smtp_frame, textvariable=self.email_from_var, width=30).grid(row=5, column=1, sticky="w", pady=5)
        
        # Rate Limit
        ttk.Label(smtp_frame, text="Rate Limit (sec):").grid(row=6, column=0, sticky="w", pady=5)
        self.rate_limit_var = tk.StringVar(value=str(self.config.get("email.rate_limit_seconds", 300)))
        ttk.Entry(smtp_frame, textvariable=self.rate_limit_var, width=10).grid(row=6, column=1, sticky="w", pady=5)
        
        # Save Button for SMTP
        ttk.Button(
            smtp_frame, 
            text="Save SMTP Settings", 
            command=self._save_email_settings
        ).grid(row=7, column=0, columnspan=2, pady=20)
        
        # --- Right Column: Recipient List ---
        recipients_frame = ttk.LabelFrame(self.settings_frame, text="Email Recipients", padding="15")
        recipients_frame.grid(row=0, column=1, sticky="nsew", pady=10)
        
        # List of recipients
        self.recipients_listbox = tk.Listbox(recipients_frame, height=10, width=40)
        self.recipients_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Load current recipients
        to_val = self.config.get("email.to", "")
        if isinstance(to_val, list):
            recipients = to_val
        else:
            recipients = [e.strip() for e in str(to_val).split(",") if e.strip()]
        
        for email in recipients:
            self.recipients_listbox.insert(tk.END, email)
            
        # Controls for recipients
        rec_controls = ttk.Frame(recipients_frame)
        rec_controls.pack(fill=tk.X)
        
        ttk.Label(rec_controls, text="New Email:").pack(side=tk.LEFT, padx=(0, 5))
        self.new_email_var = tk.StringVar()
        ttk.Entry(rec_controls, textvariable=self.new_email_var, width=25).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(rec_controls, text="Add", command=self._add_recipient).pack(side=tk.LEFT, padx=2)
        ttk.Button(rec_controls, text="Remove Selected", command=self._remove_recipient).pack(side=tk.LEFT, padx=2)
        
        # Instruction label
        ttk.Label(
            recipients_frame,
            text="Changes to recipients are saved automatically.",
            font=("Arial", 8, "italic"),
            foreground="gray"
        ).pack(pady=(10, 0))
        
        # --- Bottom Section: Notification History ---
        history_frame = ttk.LabelFrame(self.settings_frame, text="Notification History (Last 50 Outages)", padding="15")
        history_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=10)
        
        # Table for history
        columns = ("Time", "Duration", "Generator", "Notified")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=150)
            
        self.history_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        
        # Refresh button for history
        ttk.Button(history_frame, text="Refresh History", command=self._refresh_notification_history).pack(pady=10)
        
        # Load initial history
        self._refresh_notification_history()

    def _refresh_notification_history(self) -> None:
        """Refresh the notification history table."""
        # Clear current items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        try:
            from .db_reader import DatabaseReader
            db_config = self.config.get_database_config()
            reader = DatabaseReader(**db_config)
            history = reader.get_notification_history(50)
            
            for entry in history:
                start_time = datetime.fromtimestamp(entry['outage_start']).strftime("%Y-%m-%d %H:%M:%S")
                duration = f"{entry['duration_seconds']:.0f}s" if entry['duration_seconds'] else "Ongoing"
                gen = entry['generator_input_id'].upper() if entry['generator_input_id'] else "None"
                notified = "Yes" if entry['notification_sent'] else "No"
                
                self.history_tree.insert("", tk.END, values=(start_time, duration, gen, notified))
        except Exception as e:
            logger.error(f"Failed to refresh notification history: {e}")

    def _save_email_settings(self) -> None:
        """Save general email settings to config.json."""
        try:
            self.config.set("email.enabled", self.email_enabled_var.get())
            self.config.set("email.smtp_server", self.smtp_server_var.get())
            self.config.set("email.smtp_port", int(self.smtp_port_var.get()))
            self.config.set("email.smtp_username", self.smtp_user_var.get())
            self.config.set("email.smtp_password", self.smtp_pass_var.get())
            self.config.set("email.from", self.email_from_var.get())
            self.config.set("email.rate_limit_seconds", int(self.rate_limit_var.get()))
            
            self.config.save()
            messagebox.showinfo("Success", "Email settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _add_recipient(self) -> None:
        """Add a new recipient email address."""
        email = self.new_email_var.get().strip()
        if not email or "@" not in email:
            messagebox.showwarning("Invalid Input", "Please enter a valid email address.")
            return
            
        # Check if already exists
        all_emails = list(self.recipients_listbox.get(0, tk.END))
        if email in all_emails:
            messagebox.showwarning("Duplicate", "This email is already in the list.")
            return
            
        # Add to UI
        self.recipients_listbox.insert(tk.END, email)
        self.new_email_var.set("")
        
        # Save to config
        all_emails.append(email)
        self.config.set("email.to", all_emails)
        self.config.save()

    def _remove_recipient(self) -> None:
        """Remove the selected recipient."""
        selection = self.recipients_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select an email to remove.")
            return
            
        # Get selected value and index
        index = selection[0]
        
        # Confirm
        email = self.recipients_listbox.get(index)
        if not messagebox.askyesno("Confirm", f"Remove {email} from recipients?"):
            return
            
        # Remove from UI
        self.recipients_listbox.delete(index)
        
        # Save to config
        all_emails = list(self.recipients_listbox.get(0, tk.END))
        self.config.set("email.to", all_emails)
        self.config.save()

    def run(self) -> None:
        """Run the application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        finally:
            if self.auto_refresh_timer:
                self.auto_refresh_timer.cancel()
            if self.dashboard_auto_refresh_timer:
                self.dashboard_auto_refresh_timer.cancel()


