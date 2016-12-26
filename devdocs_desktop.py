#! /usr/bin/python3

import os
import gi
import signal

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit', '3.0')

from gi.repository import Gtk, Gdk, WebKit


class DevdocsDesktop:

	def __init__(self):
		self.app_url = 'https://devdocs.io'

		self.main = Gtk.Builder()
		self.main.add_from_file('ui/main.ui')
		self.main.connect_signals(self)

		self.webview = WebKit.WebView()
		self.webview.load_uri(self.app_url)
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

		self.window = self.main.get_object('window_main')
		self.window.show_all()

	def run(self):
		Gtk.main()

	def quit(self):
		Gtk.main_quit()

	def set_webview_settings(self):
		userstyle = 'file://' + os.path.abspath('styles/user.css')
		settings  = self.webview.get_settings()

		settings.set_property('enable-plugins', False)
		settings.set_property('enable-java-applet', False)
		settings.set_property('enable-default-context-menu', False)
		settings.set_property('user-stylesheet-uri', userstyle)

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

	def on_header_search_entry_key_release_event(self, widget, event):
		kname = Gdk.keyval_name(event.keyval)

		if kname == 'Return':
			self.webview.grab_focus()
			self.js_click_element('._list-result.focus')

	def on_header_button_back_clicked(self, _widget):
		self.webview.go_back()

	def on_header_button_forward_clicked(self, _widget):
		self.webview.go_forward()

	def on_header_button_reload_clicked(self, _widget):
		self.webview.reload()

	def on_header_search_entry_search_changed(self, widget):
		text = widget.get_text()
		self.js_form_input(text)

	def on_menu_main_link_clicked(self, widget):
		link = Gtk.Buildable.get_name(widget).split('_')[-1]
		link = '/' if link == 'home' else '/' + link

		self.header_search.set_text('')
		self.js_click_element('a[href="' + link + '"]')

	def on_webview_load_commited(self, _widget, _frame):
		self.update_history_buttons()

	def on_webview_title_changed(self, _widget, _frame, title):
		self.header_title.set_label(title)

	def js_form_input(self, text):
		script = """
		var fi = document.querySelectorAll('._search-input')[0];
		var fe = document.querySelectorAll('._search')[0];
		var ev = new CustomEvent('input');
		if (fi !== undefined) { fi.value = '""" + text + """' };
		if (fe !== undefined) { fe.dispatchEvent(ev); }
		"""

		self.webview.execute_script(script)

	def js_click_element(self, selector):
		script = """
		var sl = document.querySelectorAll('""" + selector + """')[0];
		if (sl !== undefined) { sl.click(); }
		"""

		self.webview.execute_script(script)


if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL)

	devdocs = DevdocsDesktop()
	devdocs.run()
