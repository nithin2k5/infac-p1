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
                database=db_config.get("database", "rpi_monitor")
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
        self.root.title("Raspberry Pi Monitor - Event Viewer")
        
        # Setup UI
        self._build_ui()
        
        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # Load initial data
        self.refresh_data()
    
    def _build_ui(self) -> None:
        """Build the main UI components."""
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Status bar (at top for outage indicator)
        self.status_frame = ttk.Frame(main_container)
        self.status_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        # LED Status Panel
        self._build_led_panel(main_container)
        
        # Statistics panel
        self._build_statistics_panel(main_container)
        
        # Filters panel
        self._build_filters_panel(main_container)
        
        # Main table area
        self._build_table_area(main_container)
        
        # Bottom toolbar
        self._build_toolbar(main_container)
    
    def _build_statistics_panel(self, parent) -> None:
        """Build statistics display panel."""
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
    
    def _build_led_panel(self, parent) -> None:
        """Build LED indicator panel for input status."""
        led_frame = ttk.LabelFrame(parent, text="Input Status LEDs", padding="10")
        led_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Container for LEDs
        led_container = ttk.Frame(led_frame)
        led_container.pack()
        
        # LED indicators storage
        self.led_widgets = {}
        
        # Input configurations
        inputs = [
            ('eb', 'EB', '#ff6b6b'),      # Red for EB
            ('gen1', 'GEN1', '#4ecdc4'),  # Teal for Gen1
            ('gen2', 'GEN2', '#45b7d1'),  # Blue for Gen2
            ('gen3', 'GEN3', '#96ceb4')   # Green for Gen3
        ]
        
        for input_id, label, color in inputs:
            # Create frame for each LED
            input_frame = ttk.Frame(led_container)
            input_frame.pack(side=tk.LEFT, padx=15, pady=5)
            
            # Label
            ttk.Label(input_frame, text=label, font=("Arial", 9, "bold")).pack()
            
            # LED canvas (circular LED with glow effect)
            led_canvas = tk.Canvas(input_frame, width=40, height=40, highlightthickness=0, bg='white')
            led_canvas.pack(pady=5)
            
            # Draw LED circle (will be updated based on state)
            # Outer glow circle for ON state
            glow_circle = led_canvas.create_oval(3, 3, 37, 37, fill="#e0e0e0", outline="", state="hidden")
            # Main LED circle
            led_circle = led_canvas.create_oval(10, 10, 30, 30, fill="#cccccc", outline="#888888", width=2)
            
            # Status label
            status_label = ttk.Label(input_frame, text="OFF", font=("Arial", 8))
            status_label.pack()
            
            # Store references
            self.led_widgets[input_id] = {
                'canvas': led_canvas,
                'circle': led_circle,
                'glow_circle': glow_circle,
                'status_label': status_label,
                'base_color': color,
                'state': None
            }
    
    def _update_led_indicators(self) -> None:
        """Update LED indicators based on latest states from database."""
        try:
            latest_states = self.db.get_latest_states()
            
            # Update each LED
            for input_id, led_data in self.led_widgets.items():
                state_info = latest_states.get(input_id, {})
                state = state_info.get('state', 0)
                canvas = led_data['canvas']
                circle_id = led_data['circle']
                status_label = led_data['status_label']
                base_color = led_data['base_color']
                
                # Determine colors based on state
                glow_circle_id = led_data.get('glow_circle')
                
                if state == 1:  # ON
                    # Bright version of base color for ON state
                    fill_color = base_color
                    outline_color = "#333333"
                    status_text = "ON"
                    status_fg = "#006600"
                    # Show glow effect for ON state
                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, fill=base_color, outline="", state="normal")
                        canvas.lower(glow_circle_id, circle_id)  # Put glow behind main circle
                else:  # OFF
                    # Gray for OFF state
                    fill_color = "#cccccc"
                    outline_color = "#888888"
                    status_text = "OFF"
                    status_fg = "#666666"
                    # Hide glow for OFF state
                    if glow_circle_id:
                        canvas.itemconfig(glow_circle_id, state="hidden")
                
                # Update LED circle
                canvas.itemconfig(circle_id, fill=fill_color, outline=outline_color, width=2)
                
                # Update status label
                status_label.config(text=status_text, foreground=status_fg)
                
                # Store current state
                led_data['state'] = state
                
        except Exception as e:
            logger.error(f"Error updating LED indicators: {e}", exc_info=True)
    
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
            
            # Load events
            self._load_events()
            
            # Update statistics
            self._update_statistics()
            
            # Update outage indicator
            self._update_outage_indicator()
            
            # Update LED indicators
            self._update_led_indicators()
            
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
            
            # Populate table
            for event in events:
                state_str = "ON" if event['state'] == 1 else "OFF"
                on_duration = self._format_duration(event.get('on_duration'))
                off_interval = self._format_duration(event.get('off_interval'))
                timestamp_str = self._format_timestamp(event['timestamp'])
                
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
                
                # Header
                writer.writerow([
                    'ID', 'Input ID', 'Input Name', 'State', 'Timestamp',
                    'Event Counter', 'On Duration (s)', 'Off Interval (s)'
                ])
                
                # Data rows
                for event in events:
                    state_str = "ON" if event['state'] == 1 else "OFF"
                    timestamp_str = datetime.fromtimestamp(event['timestamp']).isoformat()
                    
                    writer.writerow([
                        event['id'],
                        event['input_id'],
                        event['input_name'],
                        state_str,
                        timestamp_str,
                        event['event_counter'],
                        event.get('on_duration', ''),
                        event.get('off_interval', '')
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

