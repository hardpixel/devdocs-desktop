#! /usr/bin/python

import os
import gi
import sys
import json
import dbus
import shutil
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


class DevdocsDesktop:

  def __init__(self):
    GLib.set_prgname('devdocs-desktop')
    GLib.set_application_name('DevDocs')

    self.args = argparse.ArgumentParser(prog='devdocs-desktop')
    self.args.add_argument('s', metavar='STR', help='the string to search', nargs='?', default='')

    self.app_url   = 'https://devdocs.io'
    self.search    = self.args.parse_args().s
    self.open_link = False
    self.filter    = ''
    self.options   = self.read_settings_json('cookies')
    self.prefs     = self.read_settings_json('prefs')
    self.globals   = Gtk.Settings.get_default()

    self.main = Gtk.Builder()
    self.main.add_from_file(self.file_path('ui/main.ui'))
    self.main.connect_signals(self)

    self.settings = WebKit2.Settings()
    self.settings.set_enable_offline_web_application_cache(True)

    self.cookies = WebKit2.WebContext.get_default().get_cookie_manager()
    self.cookies.connect('changed', self.on_cookies_changed)

    self.manager = WebKit2.UserContentManager()
    self.webview = WebKit2.WebView.new_with_user_content_manager(self.manager)
    self.webview.set_settings(self.settings)
    self.webview.load_uri(self.url_with_search())

    self.history = self.webview.get_back_forward_list()
    self.history.connect('changed', self.on_history_changed)

    self.webview.connect('notify::uri', self.on_webview_uri_changed)
    self.webview.connect('notify::title', self.on_webview_title_changed)
    self.webview.connect('decide-policy', self.on_webview_decide_policy)
    self.webview.connect('context-menu', self.on_webview_context_menu)

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
    self.header_search.get_style_context().remove_class('search')
    self.header_search.set_text(self.search)

    self.revealer      = self.main.get_object('revealer_main')
    self.finder_search = self.main.get_object('finder_search_entry')
    self.finder_next   = self.main.get_object('finder_button_next')
    self.finder_prev   = self.main.get_object('finder_button_prev')
    self.finder_label  = self.main.get_object('finder_label')

    self.finder = WebKit2.FindController(web_view=self.webview)
    self.finder.connect('counted-matches', self.on_finder_counted_matches)
    self.finder.connect('found-text', self.on_finder_found_text)
    self.finder.connect('failed-to-find-text', self.on_finder_failed_to_find_text)

    self.window = self.main.get_object('window_main')
    self.window.show_all()

    self.create_settings_path()
    self.inject_custom_styles()
    self.add_custom_widget_styles()
    self.enable_persistent_cookies()
    self.set_window_accel_groups()
    self.toggle_theme_variation()
    self.set_zoom_level()

  def run(self):
    Gtk.main()

  def quit(self):
    Gtk.main_quit()

  def search_term(self, term):
    self.search = term
    self.header_search.set_text(self.search)
    self.webview.load_uri(self.url_with_search())

  def url_with_search(self):
    url = "%s#q=%s" % (self.app_url, self.search)
    return url

  def settings_path(self, filepath=''):
    root = "%s/devdocs-desktop" % os.path.expanduser('~/.config')
    return os.path.join(root, filepath)

  def file_path(self, filepath):
    root = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(root, filepath)

  def toggle_theme_variation(self):
    dark_site  = bool(self.options.get('dark', False))
    dark_theme = self.globals.get_property('gtk-application-prefer-dark-theme')

    if dark_site != dark_theme:
      self.globals.set_property('gtk-application-prefer-dark-theme', dark_site)

  def toggle_save_button(self, visible):
    self.header_save.set_visible(visible)
    self.header_sbox.set_visible(not visible)

  def set_zoom_level(self):
    self.webview.set_zoom_level(self.prefs.get('zoom', 1.0))

  def search_webview(self):
    text = self.finder_search.get_text()
    opts = WebKit2.FindOptions.WRAP_AROUND | WebKit2.FindOptions.CASE_INSENSITIVE

    self.finder.count_matches(text, opts, 100)
    self.finder.search(text, opts, 100)

  def create_settings_path(self):
    new_path = self.settings_path()
    old_path = os.path.expanduser('~/.devdocs-desktop')

    if os.path.exists(old_path):
      shutil.move(old_path, new_path)

    if not os.path.exists(new_path):
      os.makedirs(self.settings_path())

  def inject_custom_styles(self):
    style = open(self.file_path('styles/webview.css'), 'r').read()
    frame = WebKit2.UserContentInjectedFrames.ALL_FRAMES
    level = WebKit2.UserStyleLevel.USER
    style = WebKit2.UserStyleSheet(style, frame, level, None, None)

    self.manager.add_style_sheet(style)

  def add_custom_widget_styles(self):
    screen   = Gdk.Screen.get_default()
    priority = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    provider = Gtk.CssProvider()
    filename = self.file_path('styles/window.css')

    provider.load_from_path(filename)
    Gtk.StyleContext.add_provider_for_screen(screen, provider, priority)

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

  def update_header_filter(self, text):
    filter_exists = bool(text.strip())
    self.header_filter.set_visible(filter_exists)

    if filter_exists:
      self.filter = text.strip()
      self.header_filter.set_label(text)
      self.reset_header_search()
    else:
      self.filter = ''

  def reset_header_filter(self, value=''):
    if not bool(value.strip()):
      self.update_header_filter('')

  def reset_header_search(self, value=''):
    if not bool(value.strip()):
      self.header_search.set_text('')

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
    text  = self.header_search.get_text()
    value = bool(text.strip())
    focus = self.header_search.has_focus()

    if kname == 'Escape' and value:
      self.reset_header_search()

    if kname == 'Escape' and not value and self.webview.has_focus():
      self.reset_header_filter()

    if kname == 'Escape':
      self.header_search.grab_focus()

    if kname == 'BackSpace' and not focus:
      self.header_search.grab_focus_without_selecting()
      self.header_search.delete_text(len(text) - 1, -1)
      self.header_search.set_position(-1)

    if kname == 'slash' and not focus:
      self.header_search.grab_focus_without_selecting()

    if len(kname) == 1 and not focus:
      self.header_search.grab_focus_without_selecting()
      self.header_search.insert_text(kname, -1)
      self.header_search.set_position(-1)

  def on_window_main_key_press_event(self, _widget, event):
    kname  = Gdk.keyval_name(event.keyval)
    text   = self.header_search.get_text()
    value  = bool(text.strip())
    search = self.header_sbox.get_visible()

    if kname == 'Tab' and value and search:
      self.js_keyboard_event('._search', 9)
      self.js_element_value('._search-tag', self.update_header_filter)

      return True

  def on_header_search_entry_key_press_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)
    text  = self.header_search.get_text()
    value = bool(text.strip())

    if kname == 'BackSpace' and not value:
      self.js_keyboard_event('._search', 8)
      self.js_element_value('._search-tag', self.update_header_filter)

  def on_header_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)

    if kname == 'Return':
      self.js_keyboard_event('html', 13)
      self.webview.grab_focus()

    if kname == 'Down':
      self.js_keyboard_event('html', 40)
      self.webview.grab_focus()

    if kname == 'Up':
      self.js_keyboard_event('html', 38)
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
    self.js_form_input(widget.get_text())

  def on_menu_main_link_clicked(self, widget):
    link = Gtk.Buildable.get_name(widget).split('_')[-1]
    link = '' if link == 'home' else link

    self.js_open_link(link)

  def on_header_button_save_clicked(self, _widget):
    self.toggle_save_button(False)
    self.js_element_visible('._settings-btn-save', self.on_apply_button_visibility)

  def on_apply_button_visibility(self, visible):
    if visible:
      self.header_title.set_label('Downloading...')
      self.js_click_element('._settings-btn-save')
    else:
      self.header_title.set_label('Saving...')
      self.js_open_link('')

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
    types = WebKit2.PolicyDecisionType

    if self.open_link and dtype == types.NAVIGATION_ACTION:
      self.open_link = False
      uri = decision.get_request().get_uri()

      if not self.app_url in uri:
        decision.ignore()
        webbrowser.open(uri)

  def on_webview_title_changed(self, _widget, _title):
    title = self.webview.get_title().replace(' — DevDocs', '')
    self.header_title.set_label(title)
    self.window.set_title(title)

  def on_webview_uri_changed(self, _widget, _uri):
    save = self.webview.get_uri().endswith('settings')
    self.toggle_save_button(save)

    self.js_element_value('._search-input', self.reset_header_search)
    self.js_element_value('._search-tag', self.reset_header_filter)

  def on_history_changed(self, _list, _added, _removed):
    back = self.webview.can_go_back()
    self.header_back.set_sensitive(back)

    forward = self.webview.can_go_forward()
    self.header_forward.set_sensitive(forward)

  def on_webview_open_link(self, action):
    self.open_link = True

  def on_webview_context_menu(self, _widget, menu, _coords, _keyboard):
    actions = WebKit2.ContextMenuAction
    include = [
      actions.GO_BACK, actions.GO_FORWARD, actions.STOP, actions.RELOAD,
      actions.COPY, actions.CUT, actions.PASTE, actions.DELETE, actions.SELECT_ALL,
      actions.OPEN_LINK, actions.COPY_LINK_TO_CLIPBOARD,
      actions.COPY_IMAGE_TO_CLIPBOARD, actions.COPY_IMAGE_URL_TO_CLIPBOARD,
      actions.COPY_VIDEO_LINK_TO_CLIPBOARD, actions.COPY_AUDIO_LINK_TO_CLIPBOARD
    ]

    for item in menu.get_items():
      action = item.get_stock_action()

      if not action in include:
        menu.remove(item)

      if action == actions.OPEN_LINK:
        item.get_action().connect('activate', self.on_webview_open_link)

  def js_form_input(self, text):
    script = """
    var fi = $('._search-input');
    var fe = $('._search');
    var ev = new CustomEvent('input');
    if (fi) { fi.value = '%s' };
    if (fe) { fe.dispatchEvent(ev); }
    """

    script = script % text
    self.webview.run_javascript(script)

  def js_keyboard_event(self, selector, keycode, type='keydown'):
    script = """
    var fe = %s;
    var ev = new KeyboardEvent('%s', { which: %s });
    if (fe) { fe.dispatchEvent(ev); }
    """

    target = 'document' if selector == 'html' else "$('%s')" % selector
    script = script % (target, type, keycode)

    self.webview.run_javascript(script)

  def js_click_element(self, selector):
    script = "var sl = $('%s'); if (sl) { sl.click(); }" % selector
    self.webview.run_javascript(script)

  def js_open_link(self, link):
    link = """a[href="/%s"]""" % link.split(self.app_url)[-1]
    self.js_click_element(link)

  def js_element_value(self, selector, callback):
    script = "var sl = $('%s'); if (sl) { sl.value || sl.innerText; }" % selector
    self.webview.run_javascript(script, None, self.js_result_value, callback)

  def js_result_value(self, _webview, result, callback):
    data = self.webview.run_javascript_finish(result)
    data = data.get_js_value()

    callback(data.to_string())

  def js_element_visible(self, selector, callback):
    script = "var sl = $('%s'); if (sl) { window.getComputedStyle(sl).display !== 'none'; }" % selector
    self.webview.run_javascript(script, None, self.js_result_visibility, callback)

  def js_result_visibility(self, _webview, result, callback):
    data = self.webview.run_javascript_finish(result)
    data = data.get_js_value()

    callback(data.to_boolean())


class DevdocsDesktopService(dbus.service.Object):

  def __init__(self, app):
    self.app = app
    bus_name = dbus.service.BusName(BUS_NAME, bus=dbus.SessionBus())
    dbus.service.Object.__init__(self, bus_name, BUS_PATH)

  @dbus.service.method(dbus_interface=BUS_NAME)

  def search(self, argv):
    term = str(argv[-1])
    self.app.search_term(term)
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
