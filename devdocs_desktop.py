#! /usr/bin/python

import os
import gi
import signal
import argparse
import webbrowser

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GLib', '2.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import Gtk, Gdk, GLib, WebKit2


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

    self.cookies = WebKit2.WebContext.get_default().get_cookie_manager()
    self.manager = WebKit2.UserContentManager()
    self.webview = WebKit2.WebView.new_with_user_content_manager(self.manager)
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

    self.window = self.main.get_object('window_main')
    self.window.show_all()

    self.create_settings_path()
    self.inject_custom_styles()
    self.enable_persistent_cookies()

  def run(self):
    Gtk.main()

  def quit(self):
    Gtk.main_quit()

  def url_with_search(self):
    url = "%s#q=%s" % (self.app_url, self.search)
    return url

  def create_settings_path(self):
    if not os.path.exists(self.settings_path()):
      os.makedirs(self.settings_path())

  def settings_path(self, filepath=''):
    root = "%s/devdocs-desktop" % os.path.expanduser('~/.config')
    return os.path.join(root, filepath)

  def file_path(self, filepath):
    root = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(root, filepath)

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

  def toggle_save_button(self, visible):
    self.header_save.set_visible(visible)
    self.header_search.set_visible(not visible)

  def on_window_main_destroy(self, _event):
    self.quit()

  def on_window_main_key_release_event(self, _widget, event):
    kname   = Gdk.keyval_name(event.keyval)
    text    = self.header_search.get_text()
    visible = self.header_search.get_visible()

    if kname == 'Escape' and visible:
      self.header_search.set_text('')
      self.header_search.grab_focus()

    if kname == 'Tab' and text and visible:
      self.webview.grab_focus()

    if kname == 'Down' and visible:
      self.webview.grab_focus()

  def on_header_search_entry_key_release_event(self, _widget, event):
    kname = Gdk.keyval_name(event.keyval)

    if kname == 'Return':
      self.webview.grab_focus()
      self.js_click_element('._list-result.focus')

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
    self.js_click_element('._sidebar-footer ._settings-btn')
    self.header_title.set_label('Downloading...')

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


if __name__ == '__main__':
  signal.signal(signal.SIGINT, signal.SIG_DFL)

  devdocs = DevdocsDesktop()
  devdocs.run()
