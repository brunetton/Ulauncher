# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-

import time
import logging
import threading
from gi.repository import Gtk, Gdk, Keybinder

from ulauncher.helpers import singleton
from ulauncher.utils.display import get_current_screen_geometry
from ulauncher.config import get_data_file
from ulauncher.ui import create_item_widgets

# these imports are needed for Gtk to find widget classes
from ulauncher.ui.ResultItemWidget import ResultItemWidget
from ulauncher.ui.SmallResultItemWidget import SmallResultItemWidget

from ulauncher.ui.ItemNavigation import ItemNavigation
from ulauncher.search import Search
from ulauncher.search.apps.app_watcher import start as start_app_watcher
from ulauncher.utils.Settings import Settings
from ulauncher.ext.Query import Query
from .WindowBase import WindowBase
from .AboutUlauncherDialog import AboutUlauncherDialog
from .PreferencesUlauncherDialog import PreferencesUlauncherDialog

logger = logging.getLogger(__name__)


class UlauncherWindow(WindowBase):
    __gtype_name__ = "UlauncherWindow"

    _current_accel_name = None
    _resultsRenderTime = 0
    _mainWindowWasActivated = False

    @classmethod
    @singleton
    def get_instance(cls):
        return cls()

    def get_widget(self, id):
        """
        Return widget instance by its ID
        """
        return self.builder.get_object(id)

    def finish_initializing(self, builder):
        """
        Set up the main window
        """
        super(UlauncherWindow, self).finish_initializing(builder)

        self.results_nav = None
        self.builder = builder
        self.window = self.get_widget('ulauncher_window')
        self.input = self.get_widget('input')
        self.prefs_btn = self.get_widget('prefs_btn')
        self.result_box = builder.get_object("result_box")

        self.input.connect('changed', self.on_input_changed)
        self.prefs_btn.connect('clicked', self.on_mnu_preferences_activate)

        self.set_keep_above(True)

        self.AboutDialog = AboutUlauncherDialog
        self.PreferencesDialog = PreferencesUlauncherDialog

        self.position_window()
        self.init_styles()

        # bind hotkey
        Keybinder.init()
        accel_name = Settings.get_instance().get_property('hotkey-show-app')
        self.bind_show_app_hotkey(accel_name)

        start_app_watcher()

    def position_window(self):
        window_width = self.get_size()[0]
        current_screen = get_current_screen_geometry()

        # The topmost pixel of the window should be at 1/5 of the current screen's height
        # Window should be positioned in the center horizontally
        # Also, add offset x and y, in order to move window to the current screen
        self.move(current_screen['width'] / 2 - window_width / 2 + current_screen['x'],
                  current_screen['height'] / 5 + current_screen['y'])

    def init_styles(self):
        self.provider = Gtk.CssProvider()
        self.provider.load_from_path(get_data_file('ui', 'ulauncher.css'))
        self.apply_css(self, self.provider)
        self.screen = self.get_screen()
        self.visual = self.screen.get_rgba_visual()
        if self.visual is not None and self.screen.is_composited():
            self.set_visual(self.visual)

    def apply_css(self, widget, provider):
        Gtk.StyleContext.add_provider(widget.get_style_context(),
                                      provider,
                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        if isinstance(widget, Gtk.Container):
            widget.forall(self.apply_css, provider)

    def on_focus_out_event(self, widget, event):
        # apparently Gtk doesn't provide a mechanism to tell if window is in focus
        # this is a simple workaround to avoid hiding window
        # when user hits Alt+key combination or changes input source, etc.
        self.is_focused = False
        t = threading.Timer(0.07, lambda: self.is_focused or self.hide())
        t.start()

    def on_focus_in_event(self, *args):
        self.is_focused = True

    def show_window(self):
        self._mainWindowWasActivated = True
        # works only when the following methods are called in that exact order
        self.input.set_text('')
        self.position_window()
        self.window.set_sensitive(True)
        self.window.present()
        self.present_with_time(Keybinder.get_current_event_time())

    def cb_toggle_visibility(self, key):
        self.hide() if self.is_visible() else self.show_window()

    def bind_show_app_hotkey(self, accel_name):
        if self._current_accel_name == accel_name:
            return

        if self._current_accel_name:
            Keybinder.unbind(self._current_accel_name)
            self._current_accel_name = None

        logger.info("Trying to bind app hotkey: %s" % accel_name)
        Keybinder.bind(accel_name, self.cb_toggle_visibility)
        self._current_accel_name = accel_name

    def get_user_query(self):
        return Query(self.input.get_text())

    def on_input_changed(self, entry):
        """
        Triggered by user input
        """
        Search.get_instance().start(self.get_user_query())

    def select_result_item(self, index, onHover=False):
        if time.time() - self._resultsRenderTime > 0.05:
            # Work around issue #23 -- don't automatically select item if cursor is hovering over it upon render
            self.results_nav.select(index)

    def enter_result_item(self, index=None, alt=False):
        if not self.results_nav.enter(self.get_user_query(), index, alt=alt):
            # close the window if it has to be closed on enter
            self.hide()

    def show_results(self, result_items):
        """
        :param list result_items: list of ResultItem instances
        """
        self.results_nav = None
        self.result_box.foreach(lambda w: w.destroy())
        results = list(create_item_widgets(result_items, self.get_user_query()))  # generator -> list
        if results:
            self._resultsRenderTime = time.time()
            map(self.result_box.add, results)
            self.results_nav = ItemNavigation(self.result_box.get_children())
            self.results_nav.select_default(self.get_user_query())

            self.result_box.show_all()
            self.result_box.set_margin_bottom(10)
            self.result_box.set_margin_top(3)
            self.apply_css(self.result_box, self.provider)
        else:
            self.result_box.set_margin_bottom(0)
            self.result_box.set_margin_top(0)

    def on_input_key_press_event(self, widget, event):
        keyval = event.get_keyval()
        keyname = Gdk.keyval_name(keyval[1])
        alt = event.state & Gdk.ModifierType.MOD1_MASK
        Search.get_instance().on_key_press_event(widget, event, self.get_user_query())

        if self.results_nav:
            if keyname == 'Up':
                self.results_nav.go_up()
            elif keyname == 'Down':
                self.results_nav.go_down()
            elif alt and keyname in ('Return', 'KP_Enter'):
                self.enter_result_item(alt=True)
            elif keyname in ('Return', 'KP_Enter'):
                self.enter_result_item()
            elif alt and keyname.isdigit() and 0 < int(keyname) < 10:
                # on Alt+<num>
                try:
                    self.enter_result_item(int(keyname) - 1)
                except IndexError:
                    # selected non-existing result item
                    pass
            elif alt and len(keyname) == 1 and 97 <= ord(keyname) <= 122:
                # on Alt+<char>
                try:
                    self.enter_result_item(ord(keyname) - 97 + 9)
                except IndexError:
                    # selected non-existing result item
                    pass

        if keyname == 'Escape':
            self.hide()
