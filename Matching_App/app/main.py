from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy_garden.graph import Graph, LinePlot
import csv
import json
import os
from datetime import datetime, timedelta
from app.database import (
    init_db, get_pool_counts, get_data_signature, lookup_driver, confirm_pair,
    get_driver_levels, get_frequency_vector, reset_matched_drivers, get_pool_serials,
    get_paired_list, get_status_serials, get_matched_pairs, get_status_count, get_all_drivers,
    unpair, unpair_by_serial, delete_driver, restore_from_quarantine, quarantine_old_modules,
    load_settings, save_settings,
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
    """PIN dialog that gates access to settings and operations."""

    def __init__(self, on_success=None, **kwargs):
        super().__init__(**kwargs)
        self._on_success = on_success
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
        settings = load_settings()
        if self._pin_input.text == settings.get("pin", "1234"):
            self.dismiss()
            if self._on_success:
                self._on_success()
            else:
                SettingsPopup().open()
        else:
            self._error_label.text = "Wrong PIN"
            self._pin_input.text = ""


class SettingsPopup(Popup):
    """Settings overlay for matching parameters and housekeeping."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Settings"
        self.size_hint = (0.6, 0.7)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: setattr(App.get_running_app(), 'popup_open', True))
        self.bind(on_dismiss=lambda *a: setattr(App.get_running_app(), 'popup_open', False))

        app = App.get_running_app()
        
        # Outer container
        outer = BoxLayout(orientation="vertical", padding=10, spacing=8)
        
        # Scrollable content
        scroll = ScrollView(size_hint=(1, 0.9))
        content = BoxLayout(orientation="vertical", spacing=12, padding=5, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # --- Threshold section ---
        threshold_label = Label(
            text=f"RMSE Threshold: {app.rmse_threshold:.2f} dB",
            font_size="15sp",
            size_hint_y=None,
            height=28,
        )
        self._threshold_label = threshold_label

        slider = Slider(
            min=0.1,
            max=2.0,
            value=app.rmse_threshold,
            step=0.05,
            size_hint_y=None,
            height=36,
        )
        slider.bind(value=self._on_slider_change)
        self._slider = slider

        # --- Frequency range section ---
        freq_range_label = Label(
            text=f"Freq Range: {app.freq_min} Hz – {app.freq_max} Hz",
            font_size="15sp",
            size_hint_y=None,
            height=28,
        )
        self._freq_range_label = freq_range_label

        freq_min_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=32, spacing=8)
        freq_min_box.add_widget(Label(text="Min:", size_hint_x=None, width=45, font_size="13sp"))
        freq_min_slider = Slider(
            min=20, max=2000, value=app.freq_min, step=10,
        )
        freq_min_slider.bind(value=self._on_freq_change)
        self._freq_min_slider = freq_min_slider
        freq_min_box.add_widget(freq_min_slider)

        freq_max_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=32, spacing=8)
        freq_max_box.add_widget(Label(text="Max:", size_hint_x=None, width=45, font_size="13sp"))
        freq_max_slider = Slider(
            min=2000, max=20000, value=app.freq_max, step=100,
        )
        freq_max_slider.bind(value=self._on_freq_change)
        self._freq_max_slider = freq_max_slider
        freq_max_box.add_widget(freq_max_slider)

        # --- Module age section ---
        age_label = Label(
            text=self._format_age(app.max_module_age_days),
            font_size="15sp",
            size_hint_y=None,
            height=28,
        )
        self._age_label = age_label

        age_slider = Slider(
            min=1,
            max=120,
            value=app.max_module_age_days,
            step=1,
            size_hint_y=None,
            height=36,
        )
        age_slider.bind(value=self._on_age_change)
        self._age_slider = age_slider

        # Add all to scrollable content
        content.add_widget(threshold_label)
        content.add_widget(slider)
        content.add_widget(Label(text="", size_hint_y=None, height=4))  # spacer
        content.add_widget(freq_range_label)
        content.add_widget(freq_min_box)
        content.add_widget(freq_max_box)
        content.add_widget(Label(text="", size_hint_y=None, height=4))  # spacer
        content.add_widget(age_label)
        content.add_widget(age_slider)
        
        scroll.add_widget(content)
        outer.add_widget(scroll)

        # --- Button section (not scrollable) ---
        rematch_btn = Button(
            text="Apply & Rematch",
            size_hint_y=None,
            height=40,
            font_size="14sp",
            background_color=(0.3, 0.6, 0.3, 1),
        )
        rematch_btn.bind(on_release=self._on_rematch)
        self._rematch_btn = rematch_btn

        self._info_label = Label(
            text="",
            font_size="12sp",
            size_hint_y=None,
            height=24,
            color=(0.7, 0.7, 0.7, 1),
        )
        
        outer.add_widget(rematch_btn)
        outer.add_widget(self._info_label)

        self.content = outer

    def _format_age(self, days):
        """Format age label with proper singular/plural."""
        day_word = "day" if days == 1 else "days"
        return f"Max Module Age: {int(days)} {day_word}"

    def _on_slider_change(self, instance, value):
        self._threshold_label.text = f"RMSE Threshold: {value:.2f} dB"

    def _on_freq_change(self, instance, value):
        fmin = int(self._freq_min_slider.value)
        fmax = int(self._freq_max_slider.value)
        self._freq_range_label.text = f"Freq Range: {fmin} Hz \u2013 {fmax} Hz"

    def _on_age_change(self, instance, value):
        self._age_label.text = self._format_age(value)

    def _on_rematch(self, instance):
        app = App.get_running_app()
        app.rmse_threshold = self._slider.value
        app.freq_min = int(self._freq_min_slider.value)
        app.freq_max = int(self._freq_max_slider.value)
        app.max_module_age_days = int(self._age_slider.value)
        save_settings({
            "rmse_threshold": app.rmse_threshold,
            "freq_min": app.freq_min,
            "freq_max": app.freq_max,
            "max_module_age_days": app.max_module_age_days,
        })
        reset_count, new_pairs = app.recompute_now()
        self._info_label.text = (
            f"Reset {reset_count} drivers, formed {new_pairs} new pairs"
        )
        self._info_label.color = (0.4, 1, 0.4, 1)


class PairedPopup(Popup):
    """Operations for paired devices: list, unpair by click, unpair by serial."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Paired Devices"
        self.size_hint = (0.55, 0.7)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: self._on_popup_open())
        self.bind(on_dismiss=lambda *a: self._on_popup_close())

        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        self._header = Label(text="Paired (0)", size_hint_y=None, height=28, font_size="15sp")
        content.add_widget(self._header)

        scroll = ScrollView(size_hint=(1, 1))
        self._grid = GridLayout(cols=1, size_hint_y=None, spacing=2)
        self._grid.bind(minimum_height=self._grid.setter("height"))
        scroll.add_widget(self._grid)
        content.add_widget(scroll)

        scan_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=38, spacing=6)
        self._serial_input = TextInput(
            hint_text="Scan or type serial to unpair",
            multiline=False,
        )
        self._serial_input.bind(on_text_validate=lambda *_: self._on_unpair_serial())
        btn = Button(text="Unpair Serial", size_hint_x=None, width=120)
        btn.bind(on_release=lambda *_: self._on_unpair_serial())
        scan_box.add_widget(self._serial_input)
        scan_box.add_widget(btn)
        content.add_widget(scan_box)

        self.content = content
        self.bind(on_open=lambda *_: self._refresh_rows())

    def _on_popup_open(self):
        App.get_running_app().popup_open = True
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.1)

    def _on_popup_close(self):
        App.get_running_app().popup_open = False

    def _show_info(self, title, text):
        popup = Popup(title=title, size_hint=(0.45, 0.25), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(Label(text=text))
        ok = Button(text="OK", size_hint_y=None, height=36)
        ok.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(ok)
        popup.content = box
        popup.bind(on_dismiss=lambda *_: self._focus_serial_input())
        popup.open()

    def _show_confirm(self, title, text, on_yes):
        popup = Popup(title=title, size_hint=(0.5, 0.3), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(Label(text=text))
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=36, spacing=8)
        yes = Button(text="Yes")
        no = Button(text="No")
        yes.bind(on_release=lambda *_: (popup.dismiss(), on_yes()))
        no.bind(on_release=lambda *_: popup.dismiss())
        row.add_widget(yes)
        row.add_widget(no)
        box.add_widget(row)
        popup.content = box
        popup.bind(on_dismiss=lambda *_: self._focus_serial_input())
        popup.open()

    def _focus_serial_input(self):
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.05)

    def _refresh_rows(self):
        self._grid.clear_widgets()
        pairs = get_paired_list()
        total = len(pairs) * 2
        self._header.text = f"Paired ({total})"
        if not pairs:
            self._grid.add_widget(Label(text="No paired devices", size_hint_y=None, height=24))
            return
        for left_s, right_s, _ in pairs:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(text=left_s))
            left_btn = Button(text="X", size_hint_x=None, width=24)
            left_btn.bind(on_release=lambda *_x, l=left_s, r=right_s: self._confirm_unpair(l, r))
            row.add_widget(left_btn)

            row.add_widget(Label(text=right_s))
            right_btn = Button(text="X", size_hint_x=None, width=24)
            right_btn.bind(on_release=lambda *_x, l=left_s, r=right_s: self._confirm_unpair(l, r))
            row.add_widget(right_btn)

            self._grid.add_widget(row)

    def _confirm_unpair(self, left_serial, right_serial):
        self._show_confirm(
            "Confirm Unpair",
            f"Unpair {left_serial} and {right_serial}?",
            lambda: self._do_unpair(left_serial, right_serial),
        )

    def _do_unpair(self, left_serial, right_serial):
        ok = unpair(left_serial, right_serial)
        if ok:
            app = App.get_running_app()
            app.recompute_now()
            self._refresh_rows()
            self._show_info("Unpaired", f"{left_serial} and {right_serial} moved back to pool.")
        else:
            self._show_info("Not Found", "Selected pair could not be unpaired.")
        self._focus_serial_input()

    def _on_unpair_serial(self):
        serial = self._serial_input.text.strip()
        self._serial_input.text = ""
        if not serial:
            self._focus_serial_input()
            return
        ok, left_serial, right_serial = unpair_by_serial(serial)
        if not ok:
            self._show_info("Not Found", f"Serial {serial} is not in paired devices.")
            self._focus_serial_input()
            return
        self._confirm_unpair(left_serial, right_serial)


class PoolPopup(Popup):
    """Operations for in-pool devices (matched and unmatched)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Pool Devices"
        self.size_hint = (0.7, 0.75)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: self._on_popup_open())
        self.bind(on_dismiss=lambda *a: self._on_popup_close())

        content = BoxLayout(orientation="vertical", spacing=8, padding=10)

        lists = BoxLayout(orientation="horizontal", spacing=10)
        self._unmatched_col = self._build_list_column("Unmatched")
        self._matched_col = self._build_list_column("Matched")
        lists.add_widget(self._unmatched_col["container"])
        
        # Divider
        divider = BoxLayout(size_hint_x=None, width=2)
        with divider.canvas.before:
            Color(0.0, 0.75, 1.0, 0.9)
            divider_rect = Rectangle(size=divider.size, pos=divider.pos)
        divider.bind(pos=lambda instance, value: setattr(divider_rect, "pos", value))
        divider.bind(size=lambda instance, value: setattr(divider_rect, "size", value))
        lists.add_widget(divider)
        
        lists.add_widget(self._matched_col["container"])
        content.add_widget(lists)

        scan_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=38, spacing=6)
        self._serial_input = TextInput(
            hint_text="Scan or type serial to remove from pool",
            multiline=False,
        )
        self._serial_input.bind(on_text_validate=lambda *_: self._remove_serial())
        btn = Button(text="Remove Serial", size_hint_x=None, width=120)
        btn.bind(on_release=lambda *_: self._remove_serial())
        scan_box.add_widget(self._serial_input)
        scan_box.add_widget(btn)
        content.add_widget(scan_box)

        self.content = content
        self.bind(on_open=lambda *_: self._refresh_rows())

    def _on_popup_open(self):
        App.get_running_app().popup_open = True
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.1)

    def _on_popup_close(self):
        App.get_running_app().popup_open = False

    def _build_list_column(self, title):
        container = BoxLayout(orientation="vertical", spacing=4)
        header = Label(text=f"{title} (0)", size_hint_y=None, height=24)
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=1)
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        container.add_widget(header)
        container.add_widget(scroll)
        return {"container": container, "header": header, "grid": grid}

    def _show_info(self, title, text):
        popup = Popup(title=title, size_hint=(0.45, 0.25), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(Label(text=text))
        ok = Button(text="OK", size_hint_y=None, height=36)
        ok.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(ok)
        popup.content = box
        popup.bind(on_dismiss=lambda *_: self._focus_serial_input())
        popup.open()

    def _focus_serial_input(self):
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.05)

    def _refresh_rows(self):
        unmatched = get_status_serials("unmatched")
        matched_pairs = get_matched_pairs()
        self._populate(self._unmatched_col, "Unmatched", unmatched)
        self._populate_matched_pairs(self._matched_col, "Matched", matched_pairs)

    def _populate(self, col, title, serials):
        col["grid"].clear_widgets()
        col["header"].text = f"{title} ({len(serials)})"
        if not serials:
            col["grid"].add_widget(Label(text="-", size_hint_y=None, height=20))
            return
        for serial in serials:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(text=serial))
            btn = Button(text="X", size_hint_x=None, width=28)
            btn.bind(on_release=lambda *_x, s=serial: self._remove_serial(s))
            row.add_widget(btn)
            col["grid"].add_widget(row)

    def _populate_matched_pairs(self, col, title, pairs):
        col["grid"].clear_widgets()
        total = len(pairs) * 2
        col["header"].text = f"{title} ({total})"
        if not pairs:
            col["grid"].add_widget(Label(text="-", size_hint_y=None, height=20))
            return

        for left_serial, right_serial in pairs:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(text=left_serial))
            left_btn = Button(text="X", size_hint_x=None, width=24)
            left_btn.bind(on_release=lambda *_x, s=left_serial: self._remove_serial(s))
            row.add_widget(left_btn)

            row.add_widget(Label(text=right_serial))
            right_btn = Button(text="X", size_hint_x=None, width=24)
            right_btn.bind(on_release=lambda *_x, s=right_serial: self._remove_serial(s))
            row.add_widget(right_btn)

            col["grid"].add_widget(row)

    def _remove_serial(self, serial=None):
        s = serial or self._serial_input.text.strip()
        self._serial_input.text = ""
        if not s:
            self._focus_serial_input()
            return
        driver = lookup_driver(s)
        if driver is None:
            self._show_info("Not Found", f"Serial {s} not found in database.")
            self._focus_serial_input()
            return
        if driver["status"] not in ("unmatched", "matched"):
            self._show_info("Not In Pool", f"Serial {s} has status '{driver['status']}' and cannot be removed here.")
            self._focus_serial_input()
            return
        ok = delete_driver(s)
        if ok:
            app = App.get_running_app()
            app.recompute_now()
            self._refresh_rows()
            self._show_info("Removed", f"Serial {s} removed from pool/database.")
        else:
            self._show_info("Failed", f"Could not remove serial {s}.")
        self._focus_serial_input()


class QuarantinePopup(Popup):
    """Operations for quarantined devices and age-based quarantine."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Quarantine"
        self.size_hint = (0.6, 0.75)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: self._on_popup_open())
        self.bind(on_dismiss=lambda *a: self._on_popup_close())

        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        self._header = Label(text="Quarantined (0)", size_hint_y=None, height=24)
        content.add_widget(self._header)

        quarantine_btn = Button(
            text="Quarantine Old Modules Now",
            size_hint_y=None,
            height=36,
            background_color=(0.5, 0.35, 0.2, 1),
        )
        quarantine_btn.bind(on_release=lambda *_: self._quarantine_old_now())
        content.add_widget(quarantine_btn)

        self._age_info = Label(text="", size_hint_y=None, height=20, color=(0.8, 0.8, 0.8, 1))
        content.add_widget(self._age_info)

        scroll = ScrollView()
        self._grid = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self._grid.bind(minimum_height=self._grid.setter("height"))
        scroll.add_widget(self._grid)
        content.add_widget(scroll)

        scan_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=38, spacing=6)
        self._serial_input = TextInput(
            hint_text="Scan or type quarantined serial",
            multiline=False,
        )
        self._serial_input.bind(on_text_validate=lambda *_: self._restore_serial(self._serial_input.text.strip()))
        restore_btn = Button(text="Restore", size_hint_x=None, width=90, background_color=(0.3, 0.5, 0.3, 1))
        restore_btn.bind(on_release=lambda *_: self._restore_serial(self._serial_input.text.strip()))
        remove_btn = Button(text="Delete", size_hint_x=None, width=90)
        remove_btn.bind(on_release=lambda *_: self._remove_serial(self._serial_input.text.strip()))
        scan_box.add_widget(self._serial_input)
        scan_box.add_widget(restore_btn)
        scan_box.add_widget(remove_btn)
        content.add_widget(scan_box)

        self.content = content
        self.bind(on_open=lambda *_: self._refresh_rows())

    def _on_popup_open(self):
        App.get_running_app().popup_open = True
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.1)

    def _on_popup_close(self):
        App.get_running_app().popup_open = False

    def _show_info(self, title, text):
        popup = Popup(title=title, size_hint=(0.45, 0.25), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(Label(text=text))
        ok = Button(text="OK", size_hint_y=None, height=36)
        ok.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(ok)
        popup.content = box
        popup.bind(on_dismiss=lambda *_: self._focus_serial_input())
        popup.open()

    def _focus_serial_input(self):
        Clock.schedule_once(lambda dt: setattr(self._serial_input, 'focus', True), 0.05)

    def _refresh_rows(self):
        serials = get_status_serials("quarantined")
        self._header.text = f"Quarantined ({len(serials)})"
        app = App.get_running_app()
        self._age_info.text = f"Max age threshold: {int(app.max_module_age_days)} days"
        self._grid.clear_widgets()
        if not serials:
            self._grid.add_widget(Label(text="No quarantined devices", size_hint_y=None, height=22))
            return
        for serial in serials:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=4)
            row.add_widget(Label(text=serial))
            restore_btn = Button(text="↑", size_hint_x=None, width=28, background_color=(0.3, 0.5, 0.3, 1))
            restore_btn.bind(on_release=lambda *_x, s=serial: self._restore_serial(s))
            row.add_widget(restore_btn)
            delete_btn = Button(text="X", size_hint_x=None, width=28)
            delete_btn.bind(on_release=lambda *_x, s=serial: self._remove_serial(s))
            row.add_widget(delete_btn)
            self._grid.add_widget(row)

    def _quarantine_old_now(self):
        app = App.get_running_app()
        moved = quarantine_old_modules(app.max_module_age_days)
        if moved > 0:
            app.recompute_now()
        self._refresh_rows()
        self._show_info("Quarantine", f"Moved {moved} modules to quarantine.")
        self._focus_serial_input()

    def _remove_serial(self, serial=None):
        s = serial or self._serial_input.text.strip()
        self._serial_input.text = ""
        if not s:
            self._focus_serial_input()
            return
        driver = lookup_driver(s)
        if driver is None:
            self._show_info("Not Found", f"Serial {s} not found in database.")
            self._focus_serial_input()
            return
        if driver["status"] != "quarantined":
            self._show_info("Not Quarantined", f"Serial {s} is '{driver['status']}', not quarantined.")
            self._focus_serial_input()
            return
        ok = delete_driver(s)
        if ok:
            self._refresh_rows()
            self._show_info("Removed", f"Serial {s} removed from database.")
        else:
            self._show_info("Failed", f"Could not remove serial {s}.")
        self._focus_serial_input()

    def _restore_serial(self, serial):
        """Restore a quarantined driver back to pool (unmatched status)."""
        s = serial.strip() if isinstance(serial, str) else ""
        self._serial_input.text = ""
        if not s:
            self._focus_serial_input()
            return
        ok = restore_from_quarantine(s)
        if ok:
            app = App.get_running_app()
            app.recompute_now()
            self._refresh_rows()
            self._show_info("Restored", f"Serial {s} moved back to pool.")
        else:
            driver = lookup_driver(s)
            if driver is None:
                self._show_info("Not Found", f"Serial {s} not found in database.")
            elif driver["status"] != "quarantined":
                self._show_info("Not Quarantined", f"Serial {s} is '{driver['status']}', not quarantined.")
            else:
                self._show_info("Failed", f"Could not restore serial {s}.")
        self._focus_serial_input()


class RootWidget(BoxLayout):
    pass


class ExportOptionsPopup(Popup):
    """Export options popup for time-windowed CSV/JSON exports."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = ""
        self.separator_height = 0
        self.size_hint = (0.56, 0.36)
        self.auto_dismiss = True
        self.bind(on_open=lambda *a: setattr(App.get_running_app(), 'popup_open', True))
        self.bind(on_dismiss=lambda *a: setattr(App.get_running_app(), 'popup_open', False))

        content = BoxLayout(orientation="vertical", spacing=12, padding=[16, 14, 16, 14])
        header = Label(
            text="Export Time Window",
            size_hint_y=None,
            height=24,
            color=(0.9, 0.9, 0.9, 1),
            font_size="16sp",
        )
        content.add_widget(header)

        window_type_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=38, spacing=10)
        window_type_label = Label(
            text="Window Type",
            size_hint_x=0.36,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
        )
        window_type_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        window_type_row.add_widget(window_type_label)
        self._window_type_values = ["Matching time", "Load time"]
        self._window_type = Button(
            text=self._window_type_values[0],
            size_hint_x=0.64,
            background_normal="",
            background_down="",
            background_color=(0.32, 0.32, 0.32, 1),
            color=(1, 1, 1, 1),
        )
        self._window_type.bind(on_release=lambda *_: self._cycle_value(self._window_type, self._window_type_values))
        window_type_row.add_widget(self._window_type)
        content.add_widget(window_type_row)

        time_range_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=38, spacing=10)
        time_range_label = Label(
            text="Time Range",
            size_hint_x=0.36,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
        )
        time_range_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        time_range_row.add_widget(time_range_label)
        self._range_type_values = [
            "Full snapshot", "Last 24h", "Last 3d", "Last 7d",
            "Last 14d", "Last 30d", "Last 60d", "Last 90d",
        ]
        self._range_type = Button(
            text=self._range_type_values[0],
            size_hint_x=0.64,
            background_normal="",
            background_down="",
            background_color=(0.32, 0.32, 0.32, 1),
            color=(1, 1, 1, 1),
        )
        self._range_type.bind(on_release=lambda *_: self._cycle_value(self._range_type, self._range_type_values))
        time_range_row.add_widget(self._range_type)
        content.add_widget(time_range_row)

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=10)
        export_btn = Button(
            text="Choose Folder & Export",
            background_normal="",
            background_down="",
            background_color=(0.12, 0.38, 0.14, 1),
            color=(1, 1, 1, 1),
        )
        cancel_btn = Button(
            text="Cancel",
            background_normal="",
            background_down="",
            background_color=(0.35, 0.35, 0.35, 1),
            color=(1, 1, 1, 1),
        )
        export_btn.bind(on_release=lambda *_: self._start_export())
        cancel_btn.bind(on_release=lambda *_: self.dismiss())
        btn_row.add_widget(export_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        self._info_label = Label(text="", size_hint_y=None, height=22, color=(0.7, 0.7, 0.7, 1))
        content.add_widget(self._info_label)

        self.content = content

    def _cycle_value(self, button, values):
        try:
            idx = values.index(button.text)
        except ValueError:
            idx = 0
        button.text = values[(idx + 1) % len(values)]

    def _build_filter_options(self):
        window_type = "matching" if self._window_type.text == "Matching time" else "load"
        range_type = self._range_type.text
        now = datetime.now()
        if range_type == "Full snapshot":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": None,
                "window_end": None,
            }
        if range_type == "Last 24h":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(hours=24),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 3d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=3),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 7d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=7),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 14d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=14),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 30d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=30),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 60d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=60),
                "window_end": now.replace(microsecond=0),
            }
        if range_type == "Last 90d":
            return {
                "window_type": window_type,
                "window_label": range_type,
                "window_start": now.replace(microsecond=0) - timedelta(days=90),
                "window_end": now.replace(microsecond=0),
            }

        raise ValueError("Unknown time range option.")

        return {
            "window_type": window_type,
            "window_label": range_type,
            "window_start": None,
            "window_end": None,
        }

    def _start_export(self):
        try:
            options = self._build_filter_options()
        except ValueError as exc:
            self._info_label.text = str(exc)
            self._info_label.color = (1, 0.4, 0.4, 1)
            return
        self.dismiss()
        App.get_running_app().run_export_with_options(options)


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
        self.max_module_age_days = int(settings.get("max_module_age_days", 14))
        self.root_widget = RootWidget()
        self._last_data_signature = None
        return self.root_widget

    def on_start(self):
        self._sync_from_db(force=True)
        self._refresh_top_bar()
        self.popup_open = False
        Clock.schedule_interval(self._sync_from_db, 1.0)
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
        pass

    def open_manage_popup(self):
        # Backward-compatible alias.
        self.open_settings_popup()

    def open_settings_popup(self):
        PinPopup(on_success=lambda: SettingsPopup().open()).open()

    def open_paired_popup(self):
        PinPopup(on_success=lambda: PairedPopup().open()).open()

    def open_pool_popup(self):
        PinPopup(on_success=lambda: PoolPopup().open()).open()

    def open_quarantine_popup(self):
        PinPopup(on_success=lambda: QuarantinePopup().open()).open()

    def open_export_popup(self):
        ExportOptionsPopup().open()

    def run_export_with_options(self, options):
        selected_dir = self._pick_export_directory()
        if not selected_dir:
            return
        out_dir, file_count = self.export_csv_bundle(selected_dir, options)
        if out_dir:
            self._show_export_info(
                "Export Complete",
                f"Exported {file_count} files to:\n{out_dir}",
            )
        else:
            self._show_export_info(
                "Export Failed",
                "Could not export files. Check destination permissions.",
                error=True,
            )

    def _pick_export_directory(self):
        selected_dir = None
        try:
            import tkinter as tk
            from tkinter import filedialog

            tk_root = tk.Tk()
            tk_root.withdraw()
            tk_root.attributes("-topmost", True)
            selected_dir = filedialog.askdirectory(
                title="Select export destination folder",
                initialdir=os.getcwd(),
                mustexist=True,
            )
            tk_root.destroy()
        except Exception:
            self._show_export_info(
                "Export Failed",
                "Could not open native folder picker on this system.",
                error=True,
            )
            return ""
        return selected_dir

    def _show_export_info(self, title, text, error=False):
        popup = Popup(title=title, size_hint=(0.55, 0.3), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(Label(text=text, color=(1, 0.4, 0.4, 1) if error else (0.8, 0.8, 0.8, 1)))
        ok = Button(text="OK", size_hint_y=None, height=36)
        ok.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(ok)
        popup.content = box
        popup.open()

    def _write_csv(self, path, headers, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    def _parse_iso_datetime(self, text):
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _row_reference_time(self, row, window_type):
        if window_type == "load":
            return self._parse_iso_datetime(row.get("loaded_at"))
        if row.get("status") in ("matched", "paired"):
            return self._parse_iso_datetime(row.get("matched_at"))
        return self._parse_iso_datetime(row.get("loaded_at"))

    def _filter_rows_by_window(self, rows, options):
        start = options.get("window_start")
        end = options.get("window_end")
        window_type = options.get("window_type", "matching")
        if start is None and end is None:
            return rows

        filtered = []
        for row in rows:
            ref_time = self._row_reference_time(row, window_type)
            if ref_time is None:
                continue
            if start is not None and ref_time < start:
                continue
            if end is not None and ref_time > end:
                continue
            filtered.append(row)
        return filtered

    def export_csv_bundle(self, base_dir, options):
        """Export filtered status lists into a timestamped directory inside base_dir."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = os.path.join(base_dir, f"matching_export_{timestamp}")
            os.makedirs(export_dir, exist_ok=True)

            all_rows = get_all_drivers(include_levels=True)
            filtered_rows = self._filter_rows_by_window(all_rows, options)
            by_serial = {r["serial"]: r for r in filtered_rows}

            unmatched = [r for r in filtered_rows if r["status"] == "unmatched"]
            quarantined = [r for r in filtered_rows if r["status"] == "quarantined"]

            matched_pairs = []
            paired_pairs = []
            for row in filtered_rows:
                if row["side"] != "left" or not row.get("partner"):
                    continue
                partner = by_serial.get(row["partner"])
                if not partner:
                    continue
                if row["status"] == "matched" and partner.get("status") == "matched":
                    matched_pairs.append((row["serial"], row["partner"], row.get("matched_at") or ""))
                if row["status"] == "paired" and partner.get("status") == "paired":
                    paired_pairs.append((row["serial"], row["partner"], row.get("matched_at") or ""))

            summary_counts = {
                "unmatched": len(unmatched),
                "matched": len([r for r in filtered_rows if r["status"] == "matched"]),
                "paired": len([r for r in filtered_rows if r["status"] == "paired"]),
                "quarantined": len(quarantined),
            }
            window_start = options.get("window_start")
            window_end = options.get("window_end")

            self._write_csv(
                os.path.join(export_dir, "summary.csv"),
                ["metric", "value"],
                [
                    ["exported_at", datetime.now().isoformat(timespec="seconds")],
                    ["window_type", options.get("window_type", "matching")],
                    ["window_label", options.get("window_label", "Full snapshot")],
                    ["window_start", window_start.isoformat(timespec="seconds") if window_start else ""],
                    ["window_end", window_end.isoformat(timespec="seconds") if window_end else ""],
                    ["total_devices", len(filtered_rows)],
                    ["unmatched", summary_counts["unmatched"]],
                    ["matched", summary_counts["matched"]],
                    ["paired", summary_counts["paired"]],
                    ["quarantined", summary_counts["quarantined"]],
                    ["rmse_threshold", self.rmse_threshold],
                    ["freq_min", self.freq_min],
                    ["freq_max", self.freq_max],
                    ["max_module_age_days", self.max_module_age_days],
                ],
            )

            self._write_csv(
                os.path.join(export_dir, "pool_unmatched.csv"),
                ["serial", "side", "loaded_at", "status"],
                [[r["serial"], r["side"], r["loaded_at"], r["status"]] for r in unmatched],
            )

            self._write_csv(
                os.path.join(export_dir, "pool_matched_pairs.csv"),
                ["left_serial", "right_serial", "matched_at"],
                [[left, right, matched_at] for left, right, matched_at in matched_pairs],
            )

            self._write_csv(
                os.path.join(export_dir, "paired.csv"),
                ["left_serial", "right_serial", "paired_at"],
                [[left, right, paired_at] for left, right, paired_at in paired_pairs],
            )

            self._write_csv(
                os.path.join(export_dir, "quarantined.csv"),
                ["serial", "side", "loaded_at", "status"],
                [[r["serial"], r["side"], r["loaded_at"], r["status"]] for r in quarantined],
            )

            self._write_csv(
                os.path.join(export_dir, "all_devices.csv"),
                ["serial", "side", "status", "partner", "loaded_at", "matched_at"],
                [
                    [
                        r["serial"],
                        r["side"],
                        r["status"],
                        r["partner"] or "",
                        r["loaded_at"],
                        r["matched_at"] or "",
                    ]
                    for r in filtered_rows
                ],
            )

            export_json = {
                "schema_version": "1.0",
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "window": {
                    "type": options.get("window_type", "matching"),
                    "label": options.get("window_label", "Full snapshot"),
                    "start": window_start.isoformat(timespec="seconds") if window_start else None,
                    "end": window_end.isoformat(timespec="seconds") if window_end else None,
                },
                "settings": {
                    "rmse_threshold": self.rmse_threshold,
                    "freq_min": self.freq_min,
                    "freq_max": self.freq_max,
                    "max_module_age_days": self.max_module_age_days,
                },
                "summary": {
                    "total_devices": len(filtered_rows),
                    "unmatched": summary_counts["unmatched"],
                    "matched": summary_counts["matched"],
                    "paired": summary_counts["paired"],
                    "quarantined": summary_counts["quarantined"],
                },
                "frequency_vector": get_frequency_vector() or [],
                "devices": filtered_rows,
                "matched_pairs": [
                    {"left_serial": left, "right_serial": right, "matched_at": matched_at}
                    for left, right, matched_at in matched_pairs
                ],
                "paired_pairs": [
                    {"left_serial": left, "right_serial": right, "paired_at": paired_at}
                    for left, right, paired_at in paired_pairs
                ],
            }
            with open(os.path.join(export_dir, "export_data.json"), "w", encoding="utf-8") as f:
                json.dump(export_json, f, indent=2)

            return export_dir, 7
        except Exception:
            return None, 0

    def recompute_now(self):
        reset_count = reset_matched_drivers()
        new_pairs = compute_pairs(
            rmse_threshold=self.rmse_threshold,
            freq_min=self.freq_min,
            freq_max=self.freq_max,
        )
        self._last_data_signature = get_data_signature()
        self._refresh_top_bar()
        return reset_count, new_pairs

    def _sync_from_db(self, dt=0, force=False):
        signature = get_data_signature()
        if not force and signature == self._last_data_signature:
            return

        self._last_data_signature = signature
        self.recompute_now()

    def _refresh_top_bar(self):
        unmatched, matched, paired = get_pool_counts()
        quarantined = get_status_count("quarantined")
        top_bar = self.root_widget.ids.get("top_bar")
        if top_bar:
            top_bar.ids.pool_status.text = (
                f"In pool: {unmatched} | Matched: {matched} | Paired: {paired} | Quarantine: {quarantined}"
            )
