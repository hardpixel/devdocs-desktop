#! /usr/bin/python3

import os
import gi
import signal
import argparse

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit', '3.0')

from gi.repository import Gtk, Gdk, WebKit, Soup


class DevdocsDesktop:

	def __init__(self):
		self.args = argparse.ArgumentParser(prog='devdocs-desktop')
		self.args.add_argument('s', metavar='STR', help='the string to search', nargs='?', default='')

		self.app_url = 'https://devdocs.io'
		self.search  = self.args.parse_args().s
		self.session = WebKit.get_default_session()

		self.main = Gtk.Builder()
		self.main.add_from_file(self.file_path('ui/main.ui'))
		self.main.connect_signals(self)

		self.webview = WebKit.WebView()
		self.webview.load_uri(self.url_with_search())
		self.set_webview_settings()

		self.webview.connect('load-committed', self.on_webview_load_commited)
		self.webview.connect('title-changed', self.on_webview_title_changed)

		self.scrolled = self.main.get_object('scrolled_main')
		self.scrolled.add(self.webview)

		self.header_back = self.main.get_object('header_button_back')
		self.header_forward = self.main.get_object('header_button_forward')
		self.header_title = self.main.get_object('header_label_title')

		self.header_search = self.main.get_object('header_search_entry')
		self.header_search.get_style_context().remove_class('search')
		self.header_search.set_text(self.search)

		self.window = self.main.get_object('window_main')
		self.window.show_all()

		self.create_settings_path()
		self.enable_persistent_cookies()

	def run(self):
		Gtk.main()

	def quit(self):
		Gtk.main_quit()

	def url_with_search(self):
		return self.app_url + '#q=' + self.search

	def create_settings_path(self):
		directory = self.settings_path()

		if not os.path.exists(directory):
			os.makedirs(directory)

	def settings_path(self, filepath=''):
		root = os.path.expanduser('~') + '/.devdocs-desktop'
		return os.path.join(root, filepath)

	def file_path(self, filepath):
		root = os.path.dirname(os.path.realpath(__file__))
		return os.path.join(root, filepath)

	def set_webview_settings(self):
		userstyle = 'file://' + self.file_path('styles/user.css')
		settings  = self.webview.get_settings()

		settings.set_property('enable-plugins', False)
		settings.set_property('enable-java-applet', False)
		settings.set_property('enable-default-context-menu', False)
		settings.set_property('user-stylesheet-uri', userstyle)

	def enable_persistent_cookies(self):
		cookiefile = self.settings_path('cookies.txt')
		cookiejar = Soup.CookieJarText.new(cookiefile, False)
		cookiejar.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)
		self.session.add_feature(cookiejar)

	def update_history_buttons(self):
		back = self.webview.can_go_back()
		self.header_back.set_sensitive(back)

		forward = self.webview.can_go_forward()
		self.header_forward.set_sensitive(forward)

	def on_window_main_destroy(self, _event):
		self.quit()

	def on_window_main_key_release_event(self, widget, event):
		kname = Gdk.keyval_name(event.keyval)
		text = self.header_search.get_text()

		if kname == 'Escape':
			self.header_search.set_text('')
			self.header_search.grab_focus()

		if kname == 'Tab' and text:
			self.webview.grab_focus()

		if kname == 'Down':
			self.webview.grab_focus()

	def on_header_search_entry_key_release_event(self, widget, event):
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
		self.js_click_element('a[href="/' + link + '"]')

	def on_webview_load_commited(self, _widget, _frame):
		self.update_history_buttons()

	def on_webview_title_changed(self, _widget, _frame, title):
		self.header_title.set_label(title)

	def js_form_input(self, text):
		script = """
		var fi = $('._search-input');
		var fe = $('._search');
		var ev = new CustomEvent('input');
		if (fi) { fi.value = '""" + text + """' };
		if (fe) { fe.dispatchEvent(ev); }
		"""

		self.webview.execute_script(script)

	def js_click_element(self, selector):
		script = """
		var sl = $('""" + selector + """');
		if (sl) { sl.click(); }
		"""

		self.webview.execute_script(script)


if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL)

	devdocs = DevdocsDesktop()
	devdocs.run()
