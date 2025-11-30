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
        
        # UI configuration
        ui_config = self.config.get_ui_config()
        self.auto_refresh_interval = ui_config.get("auto_refresh_interval", 30)
        self.page_size = ui_config.get("default_page_size", 100)
        self.show_utc = ui_config.get("show_utc", False)
        
        # State
        self.current_page = 0
        self.total_events = 0
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
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.title("Raspberry Pi Monitor - Power Status & Events")
        
        # Setup UI
        self._build_ui()
        
        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # Load initial data
        self.refresh_data()
    
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
    
    def _build_dashboard_page(self) -> None:
        """Build the Status Dashboard page (Page 1) with two sections."""
        # Title
        title_label = ttk.Label(
            self.dashboard_frame,
            text="Generator Power Status Monitor",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # ========== SECTION 1: STATUS INDICATORS ==========
        indicators_section = ttk.LabelFrame(
            self.dashboard_frame,
            text="Status Indicators",
            padding="10"
        )
        indicators_section.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        # Container for status cards
        cards_container = ttk.Frame(indicators_section)
        cards_container.pack(fill=tk.X, expand=False)
        
        # Create status cards for each input
        self.status_cards = {}
        inputs = [
            ('eb', 'EB (Electricity Board)', 'Main Power'),
            ('gen1', 'GEN1', 'Generator 1'),
            ('gen2', 'GEN2', 'Generator 2'),
            ('gen3', 'GEN3', 'Generator 3')
        ]
        
        # Create grid layout (2x2)
        for idx, (input_id, title, subtitle) in enumerate(inputs):
            row = idx // 2
            col = idx % 2
            
            # Status card frame
            card_frame = ttk.LabelFrame(cards_container, text=title, padding="20")
            card_frame.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
            
            # Configure grid weights
            cards_container.columnconfigure(col, weight=1)
            cards_container.rowconfigure(row, weight=1)
            
            # Build status card
            self._build_status_card(card_frame, input_id, subtitle)
        
        # ========== SECTION 2: STATE HISTORY GRAPH ==========
        graph_section = ttk.LabelFrame(
            self.dashboard_frame,
            text="State History Graph - All Inputs Combined",
            padding="10"
        )
        graph_section.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Build graph panel inside graph section
        self._build_graph_panel(graph_section)
        
        # Bottom controls
        controls_frame = ttk.Frame(self.dashboard_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 5))
        
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
            text="Auto-refresh (30s)",
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
            font=("Arial", 10),
            foreground="gray"
        ).pack(pady=(0, 15))
        
        # LED indicator (larger for dashboard)
        led_container = ttk.Frame(parent)
        led_container.pack(pady=10)
        
        led_canvas = tk.Canvas(led_container, width=100, height=100, highlightthickness=0, bg='white')
        led_canvas.pack()
        
        # Draw LED circle (will be updated based on state)
        glow_circle = led_canvas.create_oval(5, 5, 95, 95, fill="#e0e0e0", outline="", state="hidden")
        led_circle = led_canvas.create_oval(25, 25, 75, 75, fill="#cccccc", outline="#888888", width=3)
        
        # Status label
        status_label = ttk.Label(
            parent,
            text="OFF",
            font=("Arial", 14, "bold"),
            foreground="#666666"
        )
        status_label.pack(pady=5)
        
        # Power bar/meter representation
        power_frame = ttk.LabelFrame(parent, text="Power Level", padding="10")
        power_frame.pack(fill=tk.X, pady=10)
        
        # Power bar canvas
        power_canvas = tk.Canvas(power_frame, height=30, highlightthickness=1, highlightbackground="#cccccc", bg='white')
        power_canvas.pack(fill=tk.X, pady=5)
        
        power_bar = power_canvas.create_rectangle(2, 2, 2, 28, fill="#cccccc", outline="")
        
        power_label = ttk.Label(
            power_frame,
            text="0%",
            font=("Arial", 10, "bold")
        )
        power_label.pack()
        
        # Timestamp label
        timestamp_label = ttk.Label(
            parent,
            text="Last update: N/A",
            font=("Arial", 8),
            foreground="gray"
        )
        timestamp_label.pack(pady=5)
        
        # Store references
        self.status_cards[input_id] = {
            'canvas': led_canvas,
            'circle': led_circle,
            'glow_circle': glow_circle,
            'status_label': status_label,
            'power_canvas': power_canvas,
            'power_bar': power_bar,
            'power_label': power_label,
            'timestamp_label': timestamp_label,
            'state': None
        }
    
    def _build_graph_panel(self, parent) -> None:
        """Build graph panel showing state history for all 4 inputs combined."""
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
        
        # Configure axis
        self.graph_ax.set_xlabel('Time')
        self.graph_ax.set_ylabel('State (ON=1, OFF=0)')
        self.graph_ax.set_title('All Input States Over Time')
        self.graph_ax.set_ylim(-0.2, 1.2)
        self.graph_ax.set_yticks([0, 1])
        self.graph_ax.set_yticklabels(['OFF', 'ON'])
        self.graph_ax.grid(True, alpha=0.3)
        
        # Embed in tkinter
        self.graph_canvas = FigureCanvasTkAgg(self.graph_fig, parent)
        self.graph_canvas.draw()
        self.graph_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Store graph reference
        self.graph_frame = parent
    
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
            # Red for all when ON (matching dashboard LEDs), different line styles for distinction
            colors = {'eb': '#ff0000', 'gen1': '#ff0000', 'gen2': '#ff0000', 'gen3': '#ff0000'}
            linestyles = {'eb': '-', 'gen1': '--', 'gen2': '-.', 'gen3': ':'}
            
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
                        
                        # Create step plot (state changes)
                        input_name = input_names.get(input_id, input_id.upper())
                        self.graph_ax.step(
                            times, states,
                            where='post',
                            label=input_name,
                            linewidth=2.5,
                            color=colors.get(input_id, '#ff0000'),
                            linestyle=linestyles.get(input_id, '-'),
                            alpha=0.9
                        )
                        
                        # Mark ON states with filled area for better visibility
                        self.graph_ax.fill_between(
                            times, 0, states,
                            step='post',
                            alpha=0.25,
                            color=colors.get(input_id, '#ff0000')
                        )
                
                except Exception as e:
                    logger.error(f"Error plotting {input_id}: {e}")
            
            # Configure axis
            self.graph_ax.set_xlabel('Time', fontsize=10)
            self.graph_ax.set_ylabel('State', fontsize=10)
            self.graph_ax.set_title('All Input States Over Time (Last 4 Hours)', fontsize=12, fontweight='bold')
            self.graph_ax.set_ylim(-0.1, 1.1)
            self.graph_ax.set_yticks([0, 1])
            self.graph_ax.set_yticklabels(['OFF', 'ON'])
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
    
    def _build_statistics_panel(self, parent) -> None:
        """Build statistics display panel for report page."""
        stats_frame = ttk.LabelFrame(parent, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a canvas with scrollbar for stats
        stats_canvas = tk.Canvas(stats_frame, height=80)
        stats_scroll = ttk.Scrollbar(stats_frame, orient="horizontal", command=stats_canvas.xview)
        stats_inner = ttk.Frame(stats_canvas)
        
        stats_canvas.configure(xscrollcommand=stats_scroll.set)
        stats_canvas.create_window((0, 0), window=stats_inner, anchor="nw")
        
        stats_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.stats_inner = stats_inner
        self.stats_canvas = stats_canvas
    
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
                power_canvas = card_data['power_canvas']
                power_bar = card_data['power_bar']
                power_label = card_data['power_label']
                timestamp_label = card_data['timestamp_label']
                
                # Update LED and power representation based on state
                if state == 1:  # ON - RED color
                    # Red LED for ON state
                    fill_color = "#ff0000"  # Red
                    outline_color = "#cc0000"
                    status_text = "ON"
                    status_fg = "#cc0000"
                    power_level = 100  # 100% when ON
                    power_color = "#ff0000"  # Red
                    
                    # Show glow effect for ON state
                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, fill="#ff6666", outline="", state="normal")
                        canvas.lower(glow_circle_id, circle_id)
                else:  # OFF - No color (gray)
                    # Gray for OFF state
                    fill_color = "#cccccc"
                    outline_color = "#888888"
                    status_text = "OFF"
                    status_fg = "#666666"
                    power_level = 0  # 0% when OFF
                    power_color = "#cccccc"  # Gray
                    
                    # Hide glow for OFF state
                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, state="hidden")
                
                # Update LED circle
                canvas.itemconfig(circle_id, fill=fill_color, outline=outline_color, width=3)
                
                # Update status label
                status_label.config(text=status_text, foreground=status_fg)
                
                # Update power bar
                power_canvas.update_idletasks()  # Ensure canvas is rendered
                canvas_width = power_canvas.winfo_width()
                if canvas_width > 1:
                    bar_width = int((power_level / 100) * (canvas_width - 4))
                    power_canvas.coords(power_bar, 2, 2, max(2, bar_width + 2), 28)
                    power_canvas.itemconfig(power_bar, fill=power_color)
                    power_label.config(text=f"{power_level}%")
                else:
                    # Canvas not ready yet, schedule update
                    power_canvas.after(100, lambda c=card_data, s=state: self._update_power_bar(c, s))
                
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
    
    def _update_power_bar(self, card_data: Dict[str, Any], state: int) -> None:
        """Update power bar after canvas is rendered."""
        power_canvas = card_data['power_canvas']
        power_bar = card_data['power_bar']
        power_label = card_data['power_label']
        
        power_level = 100 if state == 1 else 0
        power_color = "#ff0000" if state == 1 else "#cccccc"
        
        canvas_width = power_canvas.winfo_width()
        if canvas_width > 1:
            bar_width = int((power_level / 100) * (canvas_width - 4))
            power_canvas.coords(power_bar, 2, 2, max(2, bar_width + 2), 28)
            power_canvas.itemconfig(power_bar, fill=power_color)
            power_label.config(text=f"{power_level}%")
    
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
            from_=5,
            to=300,
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
            
            # Update power bars canvas width (needed for proper rendering)
            for input_id, card_data in self.status_cards.items():
                power_canvas = card_data['power_canvas']
                power_bar = card_data['power_bar']
                state = card_data.get('state', 0)
                
                # Update canvas dimensions
                power_canvas.update_idletasks()
                canvas_width = power_canvas.winfo_width()
                
                if canvas_width > 1:
                    power_level = 100 if state == 1 else 0
                    power_color = "#ff0000" if state == 1 else "#cccccc"
                    bar_width = int((power_level / 100) * (canvas_width - 4))
                    power_canvas.coords(power_bar, 2, 2, max(2, bar_width + 2), 28)
                    power_canvas.itemconfig(power_bar, fill=power_color)
            
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
                frame.pack(side=tk.LEFT, padx=10, pady=5)
                ttk.Label(frame, text=label, font=("Arial", 9)).pack()
                ttk.Label(frame, text=value, font=("Arial", 11, "bold")).pack()
            
            # Update canvas scroll region
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
            
            # Check if EB is LOW
            eb_state = latest_states.get('eb', {}).get('state', 1)
            
            if eb_state == 0 or active_outage:
                if active_outage:
                    duration = datetime.now().timestamp() - active_outage['outage_start']
                    duration_str = self._format_duration(duration)
                    self.outage_label.config(
                        text=f"⚠️ ACTIVE OUTAGE - Duration: {duration_str}",
                        background="#ffcccc",
                        foreground="#cc0000"
                    )
                else:
                    self.outage_label.config(
                        text="⚠️ EB POWER CUT DETECTED",
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

