from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy_garden.graph import Graph, LinePlot
from app.watcher import DataWatcher
from app.database import (
    init_db, load_json_into_db, get_pool_counts, lookup_driver, confirm_pair,
    get_driver_levels, reset_matched_drivers, get_pool_serials,
    get_paired_list, unpair, delete_driver, load_settings, save_settings,
)
from app.matcher import compute_pairs


class TopBar(BoxLayout):
    pass


class BottomBar(BoxLayout):
    """Handles QR scan input and pairing workflow.

    States:
        waiting_first  – ready for first scan
        waiting_second – first driver scanned, expecting its partner
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state = "waiting_first"
        self._first_driver = None  # dict from lookup_driver

    def focus_input(self, *args):
        self.ids.scan_input.focus = True

    def on_scan(self, text):
        serial = text.strip()
        if not serial:
            return

        self.ids.scan_input.text = ""
        self.ids.scan_input.focus = True
        driver = lookup_driver(serial)

        if self._state == "waiting_first":
            self._handle_first_scan(serial, driver)
        else:
            self._handle_second_scan(serial, driver)

    def _handle_first_scan(self, serial, driver):
        if driver is None:
            self._show_status(f"Unknown driver: {serial}", error=True)
            return
        if driver["status"] == "unmatched":
            self._show_status(f"{serial} has no match yet — still in pool", error=True)
            return
        if driver["status"] == "paired":
            self._show_status(f"{serial} already paired with {driver['partner']}", error=True)
            return

        # status == 'matched' → valid first scan
        self._first_driver = driver
        self._state = "waiting_second"
        self._show_status(
            f"{serial} scanned — now scan partner: {driver['partner']}"
        )
        # Show first driver on chart
        app = App.get_running_app()
        chart = app.root_widget.ids.get("chart_area")
        if chart:
            side = driver["side"]
            chart.show_driver(serial, color=side)

    def _handle_second_scan(self, serial, driver):
        expected = self._first_driver["partner"]
        if serial != expected:
            self._show_status(
                f"Expected {expected}, got {serial} — try again", error=True
            )
            self._reset_state()
            return

        ok = confirm_pair(self._first_driver["serial"], serial)
        if ok:
            self._show_status(
                f"Paired: {self._first_driver['serial']} + {serial}",
                success=True,
            )
            app = App.get_running_app()
            app._refresh_top_bar()
            # Show both drivers overlaid
            chart = app.root_widget.ids.get("chart_area")
            if chart:
                left_s = self._first_driver["serial"] if self._first_driver["side"] == "left" else serial
                right_s = serial if self._first_driver["side"] == "left" else self._first_driver["serial"]
                chart.show_pair(left_s, right_s)
        else:
            self._show_status("Pairing failed — status changed?", error=True)

        self._reset_state()

    def _reset_state(self):
        self._state = "waiting_first"
        self._first_driver = None
        # Reset status text after 3 seconds, keep chart visible
        Clock.schedule_once(lambda dt: self._show_status("Scan first driver..."), 3)
        Clock.schedule_once(lambda dt: self.focus_input(), 0.1)

    def _show_status(self, text, error=False, success=False):
        label = self.ids.get("status_line")
        if not label:
            return
        label.text = text
        if error:
            label.color = (1, 0.4, 0.4, 1)  # red
        elif success:
            label.color = (0.4, 1, 0.4, 1)  # green
        else:
            label.color = (0.7, 0.7, 0.7, 1)  # neutral


class ChartArea(BoxLayout):
    """Frequency response chart using kivy-garden graph."""

    LEFT_COLOR = [0.2, 0.6, 1, 1]   # blue
    RIGHT_COLOR = [1, 0.4, 0.2, 1]  # orange

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._graph = Graph(
            xlabel="Frequency (Hz)",
            ylabel="Level (dB SPL)",
            xlog=True,
            x_ticks_major=1,   # major tick every decade in log space
            x_ticks_minor=10,  # minor subdivisions per decade
            y_ticks_major=10,
            x_grid=True,
            y_grid=True,
            x_grid_label=True,
            y_grid_label=True,
            xmin=10, xmax=20000,
            ymin=50, ymax=110,
            padding=5,
            border_color=[0.3, 0.3, 0.3, 1],
            label_options={"color": [0.7, 0.7, 0.7, 1], "bold": False},
            background_color=[0.1, 0.1, 0.1, 1],
            tick_color=[0.3, 0.3, 0.3, 1],
        )
        self._plot_left = LinePlot(color=self.LEFT_COLOR, line_width=1.5)
        self._plot_right = LinePlot(color=self.RIGHT_COLOR, line_width=1.5)
        self._graph.add_plot(self._plot_left)
        self._graph.add_plot(self._plot_right)
        self.add_widget(self._graph)

    def show_driver(self, serial, color="left"):
        """Show a single driver's frequency response."""
        freqs, levels = get_driver_levels(serial)
        if freqs is None:
            return
        points = list(zip(freqs, levels))
        if color == "left":
            self._plot_left.points = points
            self._plot_right.points = []
        else:
            self._plot_right.points = points
            self._plot_left.points = []
        self._auto_range(freqs, levels)

    def show_pair(self, serial_left, serial_right):
        """Overlay both drivers' frequency responses."""
        freqs_l, levels_l = get_driver_levels(serial_left)
        freqs_r, levels_r = get_driver_levels(serial_right)
        if freqs_l is None or freqs_r is None:
            return
        self._plot_left.points = list(zip(freqs_l, levels_l))
        self._plot_right.points = list(zip(freqs_r, levels_r))
        all_levels = levels_l + levels_r
        all_freqs = freqs_l if len(freqs_l) >= len(freqs_r) else freqs_r
        self._auto_range(all_freqs, all_levels)

    def clear(self):
        self._plot_left.points = []
        self._plot_right.points = []

    def _auto_range(self, freqs, levels):
        self._graph.xmin = max(min(freqs), 10)  # log scale needs xmin > 0
        self._graph.xmax = max(freqs)
        ymin = min(levels) - 5
        ymax = max(levels) + 5
        self._graph.ymin = int(ymin // 10 * 10)
        self._graph.ymax = int(-(-ymax // 10) * 10)  # ceil to next 10
        # Adjust tick spacing
        y_range = self._graph.ymax - self._graph.ymin
        self._graph.y_ticks_major = 5 if y_range <= 40 else 10


class PinPopup(Popup):
    """PIN dialog that gates access to Management."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Enter PIN"
        self.size_hint = (0.35, 0.25)
        self.auto_dismiss = True

        content = BoxLayout(orientation="vertical", spacing=10, padding=10)

        self._pin_input = TextInput(
            hint_text="PIN",
            password=True,
            multiline=False,
            input_filter="int",
            font_size="12sp",
            size_hint_y=None,
            height=50,
            padding=[12, 12, 12, 12],
        )
        self._pin_input.bind(on_text_validate=self._on_submit)
        content.add_widget(self._pin_input)

        self._error_label = Label(
            text="",
            font_size="14sp",
            color=(1, 0.3, 0.3, 1),
            size_hint_y=None,
            height=24,
        )
        content.add_widget(self._error_label)

        btn = Button(
            text="OK",
            size_hint_y=None,
            height=40,
        )
        btn.bind(on_release=self._on_submit)
        content.add_widget(btn)

        self.content = content
        # Focus PIN input after popup opens
        self.bind(on_open=lambda *a: self._on_popup_open())
        self.bind(on_dismiss=lambda *a: self._on_popup_close())

    def _on_popup_open(self):
        App.get_running_app().popup_open = True
        Clock.schedule_once(lambda dt: setattr(self._pin_input, 'focus', True), 0.1)

    def _on_popup_close(self):
        App.get_running_app().popup_open = False

    def _on_submit(self, *args):
        app = App.get_running_app()
        settings = load_settings()
        if self._pin_input.text == settings.get("pin", "1234"):
            self.dismiss()
            ManagePopup().open()
        else:
            self._error_label.text = "Wrong PIN"
            self._pin_input.text = ""


class ManagePopup(Popup):
    """Management overlay for configuring the RMSE threshold."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Management"
        self.size_hint = (0.6, 0.75)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: setattr(
            App.get_running_app(), 'popup_open', True))
        self.bind(on_dismiss=lambda *a: setattr(
            App.get_running_app(), 'popup_open', False))

        app = App.get_running_app()
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)

        # --- Threshold section ---
        threshold_label = Label(
            text=f"RMSE Threshold: {app.rmse_threshold:.2f} dB",
            font_size="15sp",
            size_hint_y=None,
            height=30,
        )
        self._threshold_label = threshold_label

        slider = Slider(
            min=0.1,
            max=2.0,
            value=app.rmse_threshold,
            step=0.05,
            size_hint_y=None,
            height=40,
        )
        slider.bind(value=self._on_slider_change)
        self._slider = slider

        # --- Frequency range section ---
        freq_range_label = Label(
            text=f"Freq Range: {app.freq_min} Hz – {app.freq_max} Hz",
            font_size="15sp",
            size_hint_y=None,
            height=30,
        )
        self._freq_range_label = freq_range_label

        freq_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=10)
        freq_min_slider = Slider(
            min=20, max=2000, value=app.freq_min, step=10,
        )
        freq_min_slider.bind(value=self._on_freq_change)
        self._freq_min_slider = freq_min_slider

        freq_max_slider = Slider(
            min=2000, max=20000, value=app.freq_max, step=100,
        )
        freq_max_slider.bind(value=self._on_freq_change)
        self._freq_max_slider = freq_max_slider

        freq_box.add_widget(freq_min_slider)
        freq_box.add_widget(freq_max_slider)

        rematch_btn = Button(
            text="Apply & Rematch",
            size_hint_y=None,
            height=42,
            font_size="14sp",
            background_color=(0.3, 0.6, 0.3, 1),
        )
        rematch_btn.bind(on_release=self._on_rematch)
        self._rematch_btn = rematch_btn

        self._info_label = Label(
            text="",
            font_size="13sp",
            size_hint_y=None,
            height=30,
            color=(0.7, 0.7, 0.7, 1),
        )

        content.add_widget(threshold_label)
        content.add_widget(slider)
        content.add_widget(freq_range_label)
        content.add_widget(freq_box)
        content.add_widget(rematch_btn)
        content.add_widget(self._info_label)

        # --- Waiting list section ---
        pool_header = Label(
            text="Waiting List (unmatched)",
            font_size="15sp",
            size_hint_y=None,
            height=30,
            bold=True,
        )
        content.add_widget(pool_header)

        pool_box = BoxLayout(orientation="horizontal", spacing=10)

        # Left column (IA)
        left_col = BoxLayout(orientation="vertical", spacing=2)
        self._left_header = Label(
            text="Left / IA  (--)",
            font_size="13sp", size_hint_y=None, height=24, bold=True,
            color=(0.2, 0.6, 1, 1),
        )
        left_col.add_widget(self._left_header)
        left_scroll = ScrollView()
        self._left_grid = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self._left_grid.bind(minimum_height=self._left_grid.setter("height"))
        left_scroll.add_widget(self._left_grid)
        left_col.add_widget(left_scroll)

        # Right column (IB)
        right_col = BoxLayout(orientation="vertical", spacing=2)
        self._right_header = Label(
            text="Right / IB  (--)",
            font_size="13sp", size_hint_y=None, height=24, bold=True,
            color=(1, 0.4, 0.2, 1),
        )
        right_col.add_widget(self._right_header)
        right_scroll = ScrollView()
        self._right_grid = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self._right_grid.bind(minimum_height=self._right_grid.setter("height"))
        right_scroll.add_widget(self._right_grid)
        right_col.add_widget(right_scroll)

        pool_box.add_widget(left_col)
        pool_box.add_widget(right_col)
        content.add_widget(pool_box)

        self._build_pool_rows()

        # --- Paired drivers section ---
        paired_header = Label(
            text="Paired Drivers",
            font_size="15sp",
            size_hint_y=None,
            height=30,
            bold=True,
        )
        content.add_widget(paired_header)

        paired_scroll = ScrollView(size_hint_y=1)
        self._paired_grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        self._paired_grid.bind(minimum_height=self._paired_grid.setter("height"))
        self._build_paired_rows()
        paired_scroll.add_widget(self._paired_grid)
        content.add_widget(paired_scroll)

        self.content = content

    def _build_paired_rows(self):
        self._paired_grid.clear_widgets()
        pairs = get_paired_list()
        if not pairs:
            self._paired_grid.add_widget(Label(
                text="No paired drivers yet",
                font_size="12sp", size_hint_y=None, height=24,
                color=(0.5, 0.5, 0.5, 1),
            ))
            return
        for left_s, right_s, matched_at in pairs:
            row = BoxLayout(
                orientation="horizontal", size_hint_y=None, height=28, spacing=6
            )
            row.add_widget(Label(
                text=f"{left_s}  +  {right_s}",
                font_size="12sp", color=(0.8, 0.8, 0.8, 1),
            ))
            btn = Button(
                text="Unpair",
                size_hint_x=None, width=60,
                font_size="11sp",
                background_color=(0.6, 0.25, 0.25, 1),
            )
            btn.bind(on_release=lambda inst, l=left_s, r=right_s: self._on_unpair(l, r))
            row.add_widget(btn)
            self._paired_grid.add_widget(row)

    def _on_slider_change(self, instance, value):
        self._threshold_label.text = f"RMSE Threshold: {value:.2f} dB"

    def _on_freq_change(self, instance, value):
        fmin = int(self._freq_min_slider.value)
        fmax = int(self._freq_max_slider.value)
        self._freq_range_label.text = f"Freq Range: {fmin} Hz \u2013 {fmax} Hz"

    def _build_pool_rows(self):
        self._left_grid.clear_widgets()
        self._right_grid.clear_widgets()
        left_serials, right_serials = get_pool_serials()
        self._left_header.text = f"Left / IA  ({len(left_serials)})"
        self._right_header.text = f"Right / IB  ({len(right_serials)})"
        for s in left_serials:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(
                text=s, font_size="12sp", color=(0.8, 0.8, 0.8, 1),
            ))
            btn = Button(
                text="X", size_hint_x=None, width=28,
                font_size="10sp", background_color=(0.5, 0.2, 0.2, 1),
            )
            btn.bind(on_release=lambda inst, serial=s: self._on_delete_driver(serial))
            row.add_widget(btn)
            self._left_grid.add_widget(row)
        for s in right_serials:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(
                text=s, font_size="12sp", color=(0.8, 0.8, 0.8, 1),
            ))
            btn = Button(
                text="X", size_hint_x=None, width=28,
                font_size="10sp", background_color=(0.5, 0.2, 0.2, 1),
            )
            btn.bind(on_release=lambda inst, serial=s: self._on_delete_driver(serial))
            row.add_widget(btn)
            self._right_grid.add_widget(row)

    def _on_delete_driver(self, serial):
        ok = delete_driver(serial)
        if ok:
            self._build_pool_rows()
            app = App.get_running_app()
            app._refresh_top_bar()

    def _on_rematch(self, instance):
        app = App.get_running_app()
        app.rmse_threshold = self._slider.value
        app.freq_min = int(self._freq_min_slider.value)
        app.freq_max = int(self._freq_max_slider.value)
        save_settings({
            "rmse_threshold": app.rmse_threshold,
            "freq_min": app.freq_min,
            "freq_max": app.freq_max,
        })
        reset_count = reset_matched_drivers()
        new_pairs = compute_pairs(
            rmse_threshold=app.rmse_threshold,
            freq_min=app.freq_min,
            freq_max=app.freq_max,
        )
        self._info_label.text = (
            f"Reset {reset_count} drivers, formed {new_pairs} new pairs"
        )
        self._info_label.color = (0.4, 1, 0.4, 1)
        app._refresh_top_bar()
        self._build_pool_rows()
        self._build_paired_rows()

    def _on_unpair(self, left_serial, right_serial):
        ok = unpair(left_serial, right_serial)
        if ok:
            self._build_paired_rows()
            self._build_pool_rows()
            app = App.get_running_app()
            app._refresh_top_bar()


class RootWidget(BoxLayout):
    pass


class MatchingApp(App):
    title = "H600 Matching"

    def build(self):
        Window.minimum_width = 800
        Window.minimum_height = 600
        init_db()
        settings = load_settings()
        save_settings(settings)  # ensure file exists on first run
        self.rmse_threshold = settings["rmse_threshold"]
        self.freq_min = settings["freq_min"]
        self.freq_max = settings["freq_max"]
        self.root_widget = RootWidget()
        self._watcher = DataWatcher(on_file_ready=self._on_file_ready)
        return self.root_widget

    def on_start(self):
        self._watcher.start()
        self._refresh_top_bar()
        self.popup_open = False
        # Force focus on scan input every 0.2s so workers never have to click
        bottom_bar = self.root_widget.ids.get("bottom_bar")
        if bottom_bar:
            Clock.schedule_interval(lambda dt: self._auto_focus(), 0.2)

    def _auto_focus(self):
        if self.popup_open:
            return
        bottom_bar = self.root_widget.ids.get("bottom_bar")
        if bottom_bar:
            bottom_bar.focus_input()

    def on_stop(self):
        self._watcher.stop()

    def open_manage_popup(self):
        PinPopup().open()

    def _on_file_ready(self, archive_path):
        inserted = load_json_into_db(archive_path)
        reset_matched_drivers()  # re-evaluate all non-paired drivers
        new_pairs = compute_pairs(
            rmse_threshold=self.rmse_threshold,
            freq_min=self.freq_min,
            freq_max=self.freq_max,
        )
        print(f"Loaded {inserted} new drivers, {new_pairs} new pairs")
        self._refresh_top_bar()

    def _refresh_top_bar(self):
        unmatched, matched, paired = get_pool_counts()
        top_bar = self.root_widget.ids.get("top_bar")
        if top_bar:
            top_bar.ids.pool_status.text = (
                f"In pool: {unmatched} | Matched: {matched} | Paired: {paired}"
            )
