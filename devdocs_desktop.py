#! /usr/bin/python

import os
import gi
import sys
import json
import dbus
import signal
import argparse
import webbrowser
import dbus.service

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GLib', '2.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import Gtk, Gdk, GLib, WebKit2
from dbus.mainloop.glib import DBusGMainLoop

BUS_NAME = 'org.hardpixel.DevdocsDesktop'
BUS_PATH = '/org/hardpixel/DevdocsDesktop'

CTX_MENU = [
  WebKit2.ContextMenuAction.GO_BACK,
  WebKit2.ContextMenuAction.GO_FORWARD,
  WebKit2.ContextMenuAction.STOP,
  WebKit2.ContextMenuAction.RELOAD,
  WebKit2.ContextMenuAction.COPY,
  WebKit2.ContextMenuAction.CUT,
  WebKit2.ContextMenuAction.PASTE,
  WebKit2.ContextMenuAction.DELETE,
  WebKit2.ContextMenuAction.SELECT_ALL,
  WebKit2.ContextMenuAction.OPEN_LINK,
  WebKit2.ContextMenuAction.COPY_LINK_TO_CLIPBOARD,
  WebKit2.ContextMenuAction.COPY_IMAGE_TO_CLIPBOARD,
  WebKit2.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
  WebKit2.ContextMenuAction.COPY_VIDEO_LINK_TO_CLIPBOARD,
  WebKit2.ContextMenuAction.COPY_AUDIO_LINK_TO_CLIPBOARD
]


class DevdocsDesktop:

  def __init__(self):
    GLib.set_prgname('devdocs-desktop')
    GLib.set_application_name('DevDocs')

    parser = argparse.ArgumentParser(prog='devdocs-desktop')
    parser.add_argument('s', metavar='STR', help='the string to search', nargs='?', default='')

    self.app_url   = 'https://devdocs.io'
    self.args      = parser.parse_args()
    self.search    = None
    self.open_link = False
    self.hit_link  = None
    self.options   = self.read_settings_json('cookies')
    self.prefs     = self.read_settings_json('prefs')
    self.globals   = Gtk.Settings.get_default()

    self.main = Gtk.Builder()
    self.main.add_from_file(self.file_path('ui/main.ui'))
    self.main.connect_signals(self)

    self.settings = WebKit2.Settings()
    self.settings.set_enable_page_cache(True)
    self.settings.set_enable_offline_web_application_cache(True)

    self.cookies = WebKit2.WebContext.get_default().get_cookie_manager()
    self.cookies.connect('changed', self.on_cookies_changed)

    self.manager = WebKit2.UserContentManager()
    self.webview = WebKit2.WebView.new_with_user_content_manager(self.manager)
    self.webview.set_settings(self.settings)

    self.history = self.webview.get_back_forward_list()
    self.history.connect('changed', self.on_history_changed)

    self.webview.connect('notify::uri', self.on_webview_uri_changed)
    self.webview.connect('notify::title', self.on_webview_title_changed)
    self.webview.connect('decide-policy', self.on_webview_decide_policy)
    self.webview.connect('context-menu', self.on_webview_context_menu)
    self.webview.connect('mouse-target-changed', self.on_mouse_target_changed)
    self.webview.connect('button-release-event', self.on_button_release)

    self.window   = self.main.get_object('window_main')
    self.scrolled = self.main.get_object('scrolled_main')
    self.scrolled.add(self.webview)

    self.header_back    = self.main.get_object('header_button_back')
    self.header_forward = self.main.get_object('header_button_forward')
    self.header_title   = self.main.get_object('header_label_title')
    self.header_save    = self.main.get_object('header_button_save')
    self.header_sbox    = self.main.get_object('header_box_search')

    self.header_filter = self.main.get_object('header_button_filter')
    self.header_filter.set_label('')

    self.header_search = self.main.get_object('header_search_entry')
    self.header_search.set_text('')

    self.revealer      = self.main.get_object('revealer_main')
    self.finder_search = self.main.get_object('finder_search_entry')
    self.finder_next   = self.main.get_object('finder_button_next')
    self.finder_prev   = self.main.get_object('finder_button_prev')
    self.finder_label  = self.main.get_object('finder_label')

    self.finder = WebKit2.FindController(web_view=self.webview)
    self.finder.connect('counted-matches', self.on_finder_counted_matches)
    self.finder.connect('found-text', self.on_finder_found_text)
    self.finder.connect('failed-to-find-text', self.on_finder_failed_to_find_text)

    self.create_settings_path()
    self.inject_custom_styles()
    self.inject_custom_scripts()
    self.enable_persistent_cookies()
    self.set_window_accel_groups()
    self.toggle_theme_variation()
    self.set_zoom_level()

  def run(self):
    self.load_uri(self.args.s.strip())
    self.window.show_all()

    Gtk.main()

  def quit(self):
    Gtk.main_quit()

  def load_uri(self, term):
    string = "%s?q=%s" if bool(term) else "%s%s"
    self.webview.load_uri(string % (self.app_url, term))

  def settings_path(self, filepath=''):
    root = "%s/devdocs-desktop" % os.path.expanduser('~/.config')
    return os.path.join(root, filepath)

  def file_path(self, filepath):
    root = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(root, filepath)

  def toggle_theme_variation(self):
    site_theme = self.options.get('theme', 'light')
    dark_site  = bool(self.options.get('dark', site_theme == 'dark'))
    dark_theme = self.globals.get_property('gtk-application-prefer-dark-theme')

    if dark_site != dark_theme:
      self.globals.set_property('gtk-application-prefer-dark-theme', dark_site)

  def set_zoom_level(self):
    self.webview.set_zoom_level(self.prefs.get('zoom', 1.0))

  def search_webview(self):
    text = self.finder_search.get_text()
    opts = WebKit2.FindOptions.WRAP_AROUND | WebKit2.FindOptions.CASE_INSENSITIVE

    self.finder.count_matches(text, opts, 100)
    self.finder.search(text, opts, 100)

  def create_settings_path(self):
    path = self.settings_path()

    if not os.path.exists(path):
      os.makedirs(path)

  def inject_custom_styles(self):
    style = open(self.file_path('styles/webview.css'), 'r').read()
    frame = WebKit2.UserContentInjectedFrames.ALL_FRAMES
    level = WebKit2.UserStyleLevel.USER
    style = WebKit2.UserStyleSheet(style, frame, level, None, None)

    self.manager.add_style_sheet(style)

  def inject_custom_scripts(self):
    script = open(self.file_path('scripts/webview.js'), 'r').read()
    frame  = WebKit2.UserContentInjectedFrames.ALL_FRAMES
    time   = WebKit2.UserScriptInjectionTime.END
    script = WebKit2.UserScript(script, frame, time, None, None)

    self.manager.add_script(script)

    self.manager.connect('script-message-received::desktop', self.on_script_message)
    self.manager.register_script_message_handler('desktop')

  def enable_persistent_cookies(self):
    filepath = self.settings_path('cookies.txt')
    storage  = WebKit2.CookiePersistentStorage.TEXT
    policy   = WebKit2.CookieAcceptPolicy.ALWAYS

    self.cookies.set_accept_policy(policy)
    self.cookies.set_persistent_storage(filepath, storage)

  def retrieve_cookies_values(self):
    self.cookies.get_cookies(self.app_url, None, self.save_cookies_values)

  def save_cookies_values(self, _manager, result):
    data = self.cookies.get_cookies_finish(result)
    data = [(item.get_name(), item.get_value()) for item in data]

    self.options = dict(data)

    self.write_settings_json('cookies', self.options)
    self.toggle_theme_variation()

  def write_settings_json(self, filename, data):
    data = json.dumps(data)
    path = self.settings_path('%s.json' % filename)
    file = open(path, 'w')

    file.write(data)

  def read_settings_json(self, filename):
    path = self.settings_path('%s.json' % filename)
    data = open(path).read() if os.path.exists(path) else '{}'

    return json.loads(str(data))

  def run_javascript(self, method, *args):
    script = """desktop.run('%s', %s)""" % (method, list(args))
    self.webview.run_javascript(script)

  def set_window_accel_groups(self):
    group = Gtk.AccelGroup()
    ctrl  = Gdk.ModifierType.CONTROL_MASK

    group.connect(Gdk.keyval_from_name('f'), ctrl, 0, self.on_revealer_accel_pressed)

    group.connect(Gdk.keyval_from_name('KP_Subtract'), ctrl, 0, self.on_zoom_decrease_accel_pressed)
    group.connect(Gdk.keyval_from_name('minus'), ctrl, 0, self.on_zoom_decrease_accel_pressed)

    group.connect(Gdk.keyval_from_name('KP_Add'), ctrl, 0, self.on_zoom_increase_accel_pressed)
    group.connect(Gdk.keyval_from_name('plus'), ctrl, 0, self.on_zoom_increase_accel_pressed)

    group.connect(Gdk.keyval_from_name('KP_0'), ctrl, 0, self.on_zoom_reset_accel_pressed)
    group.connect(Gdk.keyval_from_name('0'), ctrl, 0, self.on_zoom_reset_accel_pressed)

    self.window.add_accel_group(group)

  def on_script_message(self, manager, data):
    data = data.get_js_value()
    data = json.loads(data.to_json(0))
    attr = data.get('callback')

    if attr and hasattr(self, attr):
      callback = getattr(self, attr)
      callback(data.get('value'))

  def on_apply_button_changed(self, visible):
    self.header_save.set_visible(visible)

  def on_search_tag_changed(self, label):
    self.header_filter.set_label(label)
    self.header_filter.set_visible(bool(label))

  def on_search_input_changed(self, text):
    if text != self.search:
      self.header_search.set_text(text)

  def on_cookies_changed(self, _manager):
    self.retrieve_cookies_values()

  def on_revealer_accel_pressed(self, _group, _widget, _code, _modifier):
    self.revealer.set_reveal_child(True)

  def on_zoom_decrease_accel_pressed(self, _group, _widget, _code, _modifier):
    self.prefs['zoom'] = round(self.webview.get_zoom_level() - 0.1, 1)

    self.set_zoom_level()
    self.write_settings_json('prefs', self.prefs)

  def on_zoom_increase_accel_pressed(self, _group, _widget, _code, _modifier):
    self.prefs['zoom'] = round(self.webview.get_zoom_level() + 0.1, 1)

    self.set_zoom_level()
    self.write_settings_json('prefs', self.prefs)

  def on_zoom_reset_accel_pressed(self, _group, _widget, _code, _modifier):
    self.prefs['zoom'] = 1.0

    self.set_zoom_level()
    self.write_settings_json('prefs', self.prefs)

  def on_window_main_destroy(self, _event):
    self.quit()

  def on_window_main_key_press_event(self, _widget, event):
    kname  = Gdk.keyval_name(event.keyval)
    kcode  = Gdk.keyval_to_unicode(event.keyval)
    search = self.header_sbox.get_visible()

    if kname == 'Tab' and bool(self.search) and search:
      self.run_javascript('sendKey', 'search', kcode)

      return True

  def on_window_main_key_release_event(self, _widget, event):
    kname  = Gdk.keyval_name(event.keyval)
    search = self.header_sbox.get_visible()
    finder = self.revealer.get_reveal_child()

    if kname == 'Escape' and finder:
      self.revealer.set_reveal_child(False)
      self.finder.search_finish()
      self.webview.grab_focus()

    if search and not finder:
      self.on_window_main_search_key_release_event(kname, event)

  def on_window_main_search_key_release_event(self, kname, event):
    if kname == 'Escape' and bool(self.search):
      self.header_search.set_text('')

    if not self.header_search.has_focus():
      self.on_window_main_unfocused_search_key_release_event(kname, event)

  def on_window_main_unfocused_search_key_release_event(self, kname, event):
    if kname == 'Escape':
      self.header_search.grab_focus()

    if kname == 'BackSpace':
      self.header_search.grab_focus_without_selecting()

      if bool(self.search):
        self.header_search.delete_text(len(self.search) - 1, -1)
        self.header_search.set_position(-1)

    if kname == 'slash':
      self.header_search.grab_focus_without_selecting()

    if len(kname) == 1:
      self.header_search.grab_focus_without_selecting()
      self.header_search.insert_text(kname, -1)
      self.header_search.set_position(-1)

  def on_header_search_entry_key_press_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)
    kcode = Gdk.keyval_to_unicode(event.keyval)

    if kname == 'BackSpace' and not bool(self.search):
      self.run_javascript('sendKey', 'search', kcode)

  def on_header_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)
    kcode = Gdk.keyval_to_unicode(event.keyval)

    if kname in ['Return', 'Down', 'Up']:
      self.run_javascript('sendKey', 'document', kcode)
      self.webview.grab_focus()

  def on_finder_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)

    if kname == 'Return':
      self.finder.search_next()

  def on_header_button_back_clicked(self, _widget):
    self.webview.go_back()

  def on_header_button_forward_clicked(self, _widget):
    self.webview.go_forward()

  def on_header_button_reload_clicked(self, _widget):
    self.webview.reload()

  def on_header_search_entry_search_changed(self, widget):
    self.search = widget.get_text()
    self.run_javascript('search', self.search)

  def on_menu_main_link_clicked(self, widget):
    link = Gtk.Buildable.get_name(widget).split('_')[-1]
    self.run_javascript('navigate', link)

  def on_header_button_save_clicked(self, _widget):
    self.header_title.set_label('Saving...')
    self.run_javascript('click', 'saveButton')

  def on_finder_search_entry_map(self, _widget):
    self.finder_search.grab_focus()
    self.search_webview()

  def on_finder_search_entry_search_changed(self, _widget):
    self.search_webview()

  def on_finder_button_next_clicked(self, _widget):
    self.finder.search_next()

  def on_finder_button_prev_clicked(self, _widget):
    self.finder.search_previous()

  def on_finder_button_close_clicked(self, _widget):
    self.revealer.set_reveal_child(False)
    self.finder.search_finish()

  def on_finder_counted_matches(self, _controller, count):
    label = "%s matches found" % count
    self.finder_label.set_label(label)

  def on_finder_found_text(self, _controller, count):
    self.finder_next.set_sensitive(True)
    self.finder_prev.set_sensitive(True)

  def on_finder_failed_to_find_text(self, _controller):
    self.finder_next.set_sensitive(False)
    self.finder_prev.set_sensitive(False)

  def on_webview_decide_policy(self, _widget, decision, dtype):
    if dtype == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
      nav = decision.get_navigation_action()
      uri = nav.get_request().get_uri()

      if self.open_link and not uri.startswith(self.app_url):
        webbrowser.open(uri)
        decision.ignore()

      self.open_link = False

  def on_webview_title_changed(self, _widget, _title):
    title = self.webview.get_title().replace(' — DevDocs', '')
    self.header_title.set_label(title)
    self.window.set_title(title)

  def on_webview_uri_changed(self, _widget, _uri):
    settings = self.webview.get_uri().endswith('settings')
    self.header_sbox.set_visible(not settings)

  def on_history_changed(self, _list, _added, _removed):
    back = self.webview.can_go_back()
    self.header_back.set_sensitive(back)

    forward = self.webview.can_go_forward()
    self.header_forward.set_sensitive(forward)

  def on_webview_open_link(self, _action, _variant):
    self.open_link = True

  def on_webview_context_menu(self, _widget, menu, _coords, _keyboard):
    for item in menu.get_items():
      action = item.get_stock_action()

      if not item.is_separator() and not action in CTX_MENU:
        menu.remove(item)

      if action == WebKit2.ContextMenuAction.OPEN_LINK:
        gaction = item.get_gaction()
        gaction.connect('activate', self.on_webview_open_link)

  def on_mouse_target_changed(self, _widget, hit, _modifiers):
    if hit.context_is_link():
      self.hit_link = hit.get_link_uri()
    else:
      self.hit_link = None

  def on_button_release(self, _widget, _event):
    if self.hit_link and not self.hit_link.startswith(self.app_url):
      webbrowser.open(self.hit_link)


class DevdocsDesktopService(dbus.service.Object):

  def __init__(self, app):
    self.app = app
    bus_name = dbus.service.BusName(BUS_NAME, bus=dbus.SessionBus())
    dbus.service.Object.__init__(self, bus_name, BUS_PATH)

  @dbus.service.method(dbus_interface=BUS_NAME)

  def search(self, argv):
    term = str(argv[-1])
    self.app.load_uri(term)
    self.app.window.present_with_time(Gdk.CURRENT_TIME)


if __name__ == '__main__':
  DBusGMainLoop(set_as_default=True)
  signal.signal(signal.SIGINT, signal.SIG_DFL)

  if dbus.SessionBus().request_name(BUS_NAME) != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
    devdocs = dbus.SessionBus().get_object(BUS_NAME, BUS_PATH)
    method  = devdocs.get_dbus_method('search')
    method(sys.argv)
  else:
    devdocs = DevdocsDesktop()
    service = DevdocsDesktopService(devdocs)
    devdocs.run()
