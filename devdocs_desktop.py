#! /usr/bin/python3

import os
import gi
import signal
import argparse
import webbrowser

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GLib', '2.0')
gi.require_version('WebKit', '3.0')

from gi.repository import Gtk, Gdk, GLib, WebKit, Soup


class DevdocsDesktop:

	def __init__(self):
		GLib.set_prgname('devdocs-desktop')
		GLib.set_application_name('DevDocs')

		self.args = argparse.ArgumentParser(prog='devdocs-desktop')
		self.args.add_argument('s', metavar='STR', help='the string to search', nargs='?', default='')

		self.app_url = 'https://devdocs.io'
		self.do_link = False
		self.search  = self.args.parse_args().s
		self.session = WebKit.get_default_session()

		self.main = Gtk.Builder()
		self.main.add_from_file(self.file_path('ui/main.ui'))
		self.main.connect_signals(self)

		self.webview = WebKit.WebView()
		self.webview.load_uri(self.url_with_search())

		self.webview.connect('navigation-requested', self.on_webview_nav_requested)
		self.webview.connect('load-committed', self.on_webview_load_commited)
		self.webview.connect('load-finished', self.on_webview_load_finished)
		self.webview.connect('title-changed', self.on_webview_title_changed)
		self.webview.connect('context-menu', self.on_webview_context_menu)

		self.scrolled = self.main.get_object('scrolled_main')
		self.scrolled.add(self.webview)

		self.header_back = self.main.get_object('header_button_back')
		self.header_forward = self.main.get_object('header_button_forward')
		self.header_title = self.main.get_object('header_label_title')
		self.header_save = self.main.get_object('header_button_save')
		self.menu_layout = self.main.get_object('menu_main_toggle_layout')

		self.header_search = self.main.get_object('header_search_entry')
		self.header_search.get_style_context().remove_class('search')
		self.header_search.set_text(self.search)

		self.window = self.main.get_object('window_main')
		self.window.show_all()

		self.create_settings_path()
		self.set_webview_settings()
		self.enable_persistent_cookies()

	def run(self):
		Gtk.main()

	def quit(self):
		Gtk.main_quit()

	def url_with_search(self):
		url = self.app_url

		if self.search != '':
			url = url + '#q=' + self.search

		return url

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

		settings.set_property('enable-webaudio', True)
		settings.set_property('enable-media-stream', True)
		settings.set_property('user-stylesheet-uri', userstyle)
		settings.set_property('javascript-can-access-clipboard', True)

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

	def toggle_save_button(self, visible):
		self.header_save.set_visible(visible)
		self.header_search.set_visible(not visible)

	def toggle_menu_layout_button(self, sensitive):
		self.menu_layout.set_sensitive(sensitive)

	def on_window_main_destroy(self, _event):
		self.quit()

	def on_window_main_key_release_event(self, _widget, event):
		kname = Gdk.keyval_name(event.keyval)
		text = self.header_search.get_text()
		visible = self.header_search.get_visible()

		if kname == 'Escape':
			if visible:
				self.header_search.set_text('')
				self.header_search.grab_focus()
			else:
				self.toggle_save_button(False)

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
		self.js_click_element('a[href="/' + link + '"]')

	def on_menu_main_select_docs_clicked(self, _widget):
		self.header_search.set_text('')
		self.webview.grab_focus()
		self.js_click_element('._sidebar-footer-edit')
		self.toggle_save_button(True)

	def on_menu_main_toggle_layout_clicked(self, widget):
		self.js_click_element('._sidebar-footer-layout')

		self.js_click_element('._sidebar-footer-light')
	def on_menu_main_toggle_light_clicked(self, _widget):

		self.js_click_element('._sidebar-footer-save')
	def on_header_button_save_clicked(self, _widget):
		self.toggle_save_button(False)

	def on_webview_nav_requested(self, _widget, _frame, request):
		uri = request.get_uri()

		if self.do_link:
			if self.app_url in uri:
				link = uri.split(self.app_url)[-1]
				self.js_click_element('a[href="' + link + '"]')
			else:
				webbrowser.open(uri)

			return True

		self.do_link = False
		return False

	def on_webview_load_commited(self, _widget, frame):
		self.do_link = False
		self.toggle_save_button(False)
		self.update_history_buttons()

	def on_webview_load_finished(self, _widget, _frame):
		self.update_history_buttons()

	def on_webview_title_changed(self, _widget, _frame, title):
		self.header_title.set_label(title)

	def on_webview_open_link(self, _widget):
		self.do_link = True

	def on_webview_context_menu(self, _widget, menu, _coords, _keyboard):
		for item in menu.get_children():
			label = item.get_label()
			lnk_open = '_Open' in label
			new_open = '_Window' in label
			download = '_Download' in label

			if new_open or download:
				item.destroy()

			if lnk_open:
				item.connect('select', self.on_webview_open_link)

	def js_form_input(self, text):
		script = """
		var fi = $('._search-input');
		var fe = $('._search');
		var ev = new CustomEvent('input');
		if (fi) { fi.value = '%s' };
		if (fe) { fe.dispatchEvent(ev); }
		"""
		script = script % (text)

		self.webview.execute_script(script)

	def js_click_element(self, selector):
		script = "var sl = $('%s'); if (sl) { sl.click(); }"
		script = script % (selector)

		self.webview.execute_script(script)


if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL)

	devdocs = DevdocsDesktop()
	devdocs.run()
