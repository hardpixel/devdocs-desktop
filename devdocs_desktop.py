#! /usr/bin/python

import os
import gi
import sys
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

    self.main = Gtk.Builder()
    self.main.add_from_file(self.file_path('ui/main.ui'))
    self.main.connect_signals(self)

    self.settings = WebKit2.Settings()
    self.settings.set_enable_offline_web_application_cache(False)

    self.cookies = WebKit2.WebContext.get_default().get_cookie_manager()
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
    self.enable_persistent_cookies()
    self.set_window_accel_groups()

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

  def toggle_save_button(self, visible):
    self.header_save.set_visible(visible)
    self.header_search.set_visible(not visible)

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
    style = open(self.file_path('styles/user.css'), 'r').read()
    frame = WebKit2.UserContentInjectedFrames.ALL_FRAMES
    level = WebKit2.UserStyleLevel.USER
    style = WebKit2.UserStyleSheet(style, frame, level, None, None)

    self.manager.add_style_sheet(style)

  def enable_persistent_cookies(self):
    filepath = self.settings_path('cookies.txt')
    storage  = WebKit2.CookiePersistentStorage.TEXT
    policy   = WebKit2.CookieAcceptPolicy.ALWAYS

    self.cookies.set_accept_policy(policy)
    self.cookies.set_persistent_storage(filepath, storage)

  def set_window_accel_groups(self):
    group = Gtk.AccelGroup()
    ctrl  = Gdk.ModifierType.CONTROL_MASK

    group.connect(Gdk.keyval_from_name('f'), ctrl, 0, self.on_revealer_accel_pressed)
    self.window.add_accel_group(group)

  def on_revealer_accel_pressed(self, _group, _widget, _code, _modifier):
    self.revealer.set_reveal_child(True)

  def on_window_main_destroy(self, _event):
    self.quit()

  def on_window_main_key_release_event(self, _widget, event):
    kname  = Gdk.keyval_name(event.keyval)
    text   = self.header_search.get_text()
    search = self.header_search.get_visible()
    finder = self.revealer.get_reveal_child()

    if kname == 'Escape' and finder:
      self.revealer.set_reveal_child(False)
      self.finder.search_finish()
      self.webview.grab_focus()

    if kname == 'Escape' and search and not finder:
      self.header_search.set_text('')
      self.header_search.grab_focus()

    if kname == 'Tab' and text and search:
      self.webview.grab_focus()

    if kname == 'Down' and search:
      self.webview.grab_focus()

    if kname == 'slash' and not finder:
      self.header_search.grab_focus_without_selecting()

  def on_header_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)

    if kname == 'Return':
      self.webview.grab_focus()
      self.js_click_element('._list-result.focus')

  def on_finder_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)

    if kname == 'Return':
      self.finder.search_next()

  def on_header_button_back_clicked(self, _widget):
    self.webview.go_back()
    self.header_search.set_text('')

  def on_header_button_forward_clicked(self, _widget):
    self.webview.go_forward()
    self.header_search.set_text('')

  def on_header_button_reload_clicked(self, _widget):
    self.webview.reload()
    self.header_search.set_text('')

  def on_header_search_entry_search_changed(self, widget):
    text = widget.get_text()
    self.js_form_input(text)

  def on_menu_main_link_clicked(self, widget):
    link = Gtk.Buildable.get_name(widget).split('_')[-1]
    link = '' if link == 'home' else link

    self.header_search.set_text('')
    self.js_open_link(link)

  def on_header_button_save_clicked(self, _widget):
    self.toggle_save_button(False)
    self.js_click_element('._settings-btn-save')
    self.header_title.set_label('Saving...')

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
    title = self.webview.get_title()
    self.header_title.set_label(title)

  def on_webview_uri_changed(self, _widget, _uri):
    save = self.webview.get_uri().endswith('settings')
    self.toggle_save_button(save)

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

  def js_click_element(self, selector):
    script = "var sl = $('%s'); if (sl) { sl.click(); }" % selector
    self.webview.run_javascript(script)

  def js_open_link(self, link):
    link = """a[href="/%s"]""" % link.split(self.app_url)[-1]
    self.js_click_element(link)


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
