#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gedit Markdown – a Gedit plugin that previews Markdown text as webpage or
HTML-code in bottom panel of Gedit.

FUTURE IMPROVEMENTS
===================
1. Configurable preview window height with 50% as default. Prevent WebKit from
   changing the preview window height

2. Makse a submeny with following Gedit Msrkdown menu items:

    * Show/hide preview
    * Refresh preview

3. Translate to Swedish

4. Use Gedit language settings in the tools menu to choose between different
   smartypants configurations.

© 2015 Thomas Barregren <thomas@barregren.se>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import os, shlex, webbrowser

from importlib import import_module
from gettext import lgettext as _
from gi.repository import GObject, Gtk, Gedit, WebKit
from subprocess import Popen, PIPE, TimeoutExpired
from simpleconfig import SimpleConfig
from xdg.BaseDirectory import xdg_config_home

class GeditMarkdownWindowActivatable(GObject.Object, Gedit.WindowActivatable):

	__gtype_name__ = "GeditMarkdownWindowActivatable"

	window = GObject.property(type=Gedit.Window)
	
	def __init__(self):

		GObject.Object.__init__(self)

		# Configurate the plugin.
		self._configurate(True)

		# Dynamically assign which Markdown and SmartyPants methods to use.
		self._cfg.current_section = 'General'
		self._markdown = self._markdown_external if self._cfg['use_external_markdown'] else self._markdown_internal
		self._smartypants = self._smartypants_external if self._cfg['use_external_smartypants'] else self._smartypants_internal

		# Lazy initialization of internal Markdown and SmartyPants
		# implementation.
		self._markdown_internal_object = None
		self._smartypants_internal_object = None

		# Lazy initialization of the preview window.
		self._preview_window = None

	def _configurate(self, write = False):

		# Create a configuration object and its only section
		self._cfg = SimpleConfig()

		# Default configuration for the application.
		self._cfg.current_section = 'General'
		self._cfg.current_dictionary = {
			"show_hide_accelerator_key": "<Ctrl><Alt>m",
			"use_external_markdown" : "No",
			"use_external_smartypants" : "No",
			"use_bottom_panel" : "No"
		}

		# Default configuration for internal Markdown library.
		self._cfg.current_section = 'Internal Markdown'
		self._cfg.current_dictionary = {
			"output_format": "html5",
			"lazy_ol": "False",
			"extensions": """
					markdown.extensions.extra,
					markdown.extensions.sane_lists
			"""
		}

		# Default configuration for external Markdown tool.
		self._cfg.current_section = 'External Markdown'
		self._cfg.current_dictionary = {
			"command_line": "",
			"timeout": "30"
		}

		# Default configuration for internal SmartyPants library.
		self._cfg.current_section = 'Internal SmartyPants'
		self._cfg.current_dictionary = {
			'left-double-quote'                 : '“',
			'right-double-quote'                : '”',
			'left-single-quote'                 : '‘',
			'right-single-quote_and_apostrophe' : '’',
			'en-dash'                           : '–',
			'em-dash'                           : '—',
			'ellipsis'                          : '…'
		}

		# Default configuration for external SmartyPants tool.
		self._cfg.current_section = 'External SmartyPants'
		self._cfg.current_dictionary = {
			"command_line": "",
			"timeout": "30"
		}

		# Read configuration file.
		config_file = os.path.join(xdg_config_home, "gedit", "gedit-markdown")
		files = self._cfg.read_files(config_file)

		# If no configuration file exists, create one with default values.
		if not files:
			self._cfg.write_file(config_file)

	def do_activate(self):
		self._add_to_menu()

	def do_deactivate(self):
		self._remove_from_menu()
		self._remove_preview();

	def do_update_state(self):
		self._action_group.set_sensitive(self.window.get_active_document() is not None)

	def _add_to_menu(self):

		# Get Gtk.UIManager
		manager = self.window.get_ui_manager()

		# Create an action group for Gedit Markdown
		self._action_group = Gtk.ActionGroup("GeditMarkdownPluginActions")
		manager.insert_action_group(self._action_group, -1)

		# Add preview action to Gedit Markdown's action group.
		self._cfg.current_section = 'General'
		self._action_group.add_actions([
			(
				"geditmarkdown_show_hide",
				None,
				_("Show/hide Markdown preview"),
				self._cfg['show_hide_accelerator_key'],
				_("Toggles the markdown preview on/off."),
				self.on_markdown_preview_activate
			)
		])

		# Add preview action to the Tools menu
		self._ui_id = manager.add_ui_from_string("""
			<ui>
			  <menubar name="MenuBar">
				<menu name="ToolsMenu" action="Tools">
				  <placeholder name="ToolsOps_3">
					<menuitem name="geditmarkdown-show-hide" action="geditmarkdown_show_hide"/>
				  </placeholder>
				</menu>
			  </menubar>
			</ui>
		""")

	def _remove_from_menu(self):

		# Get Gtk.UIManager
		manager = self.window.get_ui_manager()

		# Remove the ui
		manager.remove_ui(self._ui_id)

		# Remove the action group
		manager.remove_action_group(self._action_group)
		self._action_group = None

		# Make sure the manager updates
		manager.ensure_update()

	def _remove_preview(self):
		if self._preview_window is not None:
			self._panel.remove_item(self._preview_window)

	# Menu activate handler
	def on_markdown_preview_activate(self, action):

		# Setup the preview on the first call.
		if self._preview_window is None:

			# Create an empty preview
			self._preview = WebKit.WebView()
			self._preview.connect("navigation-policy-decision-requested", self.on_navigation_policy_decision_requested)
			self._preview.connect("populate-popup", self.on_populate_popup)

			# Add the preview to a window
			self._preview_window = Gtk.ScrolledWindow()
			self._preview_window.set_property("hscrollbar-policy", Gtk.PolicyType.AUTOMATIC)
			self._preview_window.set_property("vscrollbar-policy", Gtk.PolicyType.AUTOMATIC)
			self._preview_window.set_property("shadow-type", Gtk.ShadowType.IN)
			self._preview_window.add(self._preview)
			self._preview_window.show_all()

			# Get the panel
			self._cfg.current_section = 'General'
			self._panel = self.window.get_bottom_panel() if self._cfg['use_bottom_panel'] else self.window.get_side_panel()

			# Add the window to te bottom panel
			image = Gtk.Image()
			image.set_from_icon_name("gnome-mime-text-html", Gtk.IconSize.MENU)
			self._panel.add_item(self._preview_window, "GeditMarkdown", _("Markdown Preview"), image)

		# show/hide preview
		if self._panel.is_visible() and self._panel.item_is_active(self._preview_window):
			self._hide_preview()
		else:
			self._show_preview()

	def _show_preview(self, mime = "text/html"):

		# Get the selected text. If no text is selected, get all text.
		view = self.window.get_active_view()
		doc = view.get_buffer()
		if doc.get_selection_bounds():
			start = doc.get_iter_at_mark(doc.get_insert())
			end = doc.get_iter_at_mark(doc.get_selection_bound())
		else:
			start = doc.get_start_iter()
			end = doc.get_end_iter()
		text = doc.get_text(start, end, True)

		# Convert Markdown and SmartyPants to HTML
		html = self._markdown(text)
		html = self._smartypants(html)

		# Update the preview.
		self._preview.load_string(html, mime, "utf-8", "file:///")

		# Make sure the preview is shown.
		self._panel.activate_item(self._preview_window)
		self._panel.show()

	def _hide_preview(self):
		self._panel.hide()

	def on_navigation_policy_decision_requested(self, web_view, frame, request, navigation_action, policy_decision):
		uri = request.get_uri()
		if navigation_action.get_reason().value_nick == "link-clicked" and (uri.startswith('http://') or uri.startswith('https://')):
			policy_decision.ignore()
			webbrowser.open(uri)
		else:			
			policy_decision.use()
		return True

	def on_populate_popup(self, view, menu):

		# Remove all default popup menu items, as they don't make sense here.
		for item in menu.get_children():
			menu.remove(item)

		# Add toggle mode to the popup menu
		item = _("Reload as HTML code")
		item = Gtk.MenuItem(item)
		item.connect("activate", lambda x: self._show_preview('text/plain'))
		menu.append(item)
		item.show()

		# Add Reload to the popup menu
		item = Gtk.MenuItem(_("Reload as webpage"))
		item.connect("activate", lambda x: self._show_preview())
		menu.append(item)
		item.show()

	def _markdown(self, text):
		# This method is an alias for the one of _markdown_internal() and
		# _markdown_external() selected in the constructor. Its body is never
		# executed.
		assert True

	def _markdown_internal(self, text):

		self._cfg.current_section = 'Internal Markdown'

		if self._markdown_internal_object is None:

			# Import Waylan Limberg's Python-Markdown module and its extension.
			try:
				import markdown
			except ImportError:
				return "<p>Error: Markdown implementation is missing.</p>"

			# Build a list of extension objects.
			extensions = self._cfg['extensions']
			extensions = [ext.strip() for ext in extensions.split(',')]
			extension_objects = []
			for ext in extensions:
				try:
					obj = self._extension_factory(ext)
				except (ImportError, AttributeError) as e:
					return "<p>Error: " + e.args[0] + "</p>"
				else:
					extension_objects.append(obj)

			self._markdown_internal_object = markdown.Markdown(
				extensions = extension_objects,
				output_format = self._cfg['output_format'],
				lazy_ol = self._cfg['lazy_ol']
			)

		# Convert markdwon to HTML.
		# Following line should work according to documentation, but the
		# reset() doesn't do it. So therefore we don't use the obkect
		# for current being.
		return self._markdown_internal_object.reset().convert(text)

	def _extension_factory(self, extension):

		# Build a dictonary with the arguments.
		arguments = {}
		pos = extension.find('(')
		if pos > 0:

			# Get the arguments.
			args = extension[pos+1:-1]
			args = [arg.split('=') for arg in args.split(',')]
			arguments.update((key.strip(), val.strip()) for (key, val) in args)

			# Remove the arguments from the extension parameter.
			extension = extension[:pos]

		# Get class name (if provided): `path.to.module:ClassName`
		module_name, class_name = extension.split(':', 1) if ':' in extension else (extension, '')

		# Load the extension module.
		try:
			module = import_module(module_name)
		except ImportError as e:
			msg = _("Error: Failed loading extension {0} from {1}.").format(class_name, module_name)
			e.args = (msg, ) + e.args[1:]
			raise e

		# Return the class.
		try:
			if class_name:
				# If class name was given, instantiate an object of the named class.
				return getattr(module, class_name)(**arguments)
			else:
				# No class given. Let's hope the module has implemented the
				# makeExtension method described in API documentation:
				# https://pythonhosted.org/Markdown/extensions/api.html#makeextension
				return module.makeExtension(**arguments)
		except AttributeError as e:
			msg = _("Error: Failed loading extension {0} from {1}.").format(class_name, module_name)
			e.args = (msg, ) + e.args[1:]
			raise e

	def _markdown_external(self, text):
		self._cfg.current_section = 'External Markdown'
		return self._execute_command_line(text, self._cfg['command_line'], self._cfg['timeout'])

	def _smartypants(self, html):
		# This method is an alias for the one of _smartypants_internal() and
		# _smartypants_external() selected in the constructor. Its body is
		# never executed.
		assert True

	def _smartypants_internal(self, html):

		self._cfg.current_section = 'Internal SmartyPants'

		if self._smartypants_internal_object is None:

			# Import Thomas Barregren's Smarty module.
			try:
				import smarty
			except ImportError:
				return "<p>" + _("Error: SmartyPants implementation is missing.") + "</p>"

			# Initalize the internal SmartyPants library.
			self._smartypants_internal_object = smarty.Smarty()
			self._smartypants_internal_object.substitutions = self._cfg.current_dictionary

		try:
			return self._smartypants_internal_object.reset().feed(html).close()
		except Exception as err:
			return "<p>" + _("Error while calling internal SmartyPants library: {0}").format(err) + "</p>"

	def _smartypants_external(self, html):
		self._cfg.current_section = 'External SmartyPants'
		return self._execute_command_line(text, self._cfg['command_line'], self._cfg['timeout'])

	def _execute_command_line(self, text, command_line, timeout):
		try:
			args = shlex.split(command_line)
			cmd = Popen(args, stdin = PIPE, stdout = PIPE, stderr = PIPE, universal_newlines = True)
			text, error = cmd.communicate(text, timeout)
		except OSError as err:
			text = "<p>" + _("OS error: {0}").format(err) + "</p>"
		except TimeoutExpired:
			cmd.kill()
			text = "<p>" + _("Timeout error: {0} has not returned after {1} seconds").format(command_line, timeout) + "</p>"
		except Exception as err:
			text = "<p>" + _("Unexpected error when calling {0}: {1}").format(command_line, err) + "</p>"
		else:
			if error:
				text = "<p>" + _("Error: {0} failed with following error message: \"{1}\"").format(command_line, error) + "</p>"
		return text
