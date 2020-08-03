#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smarty – smart typography transformation of HTML.

The module transform straight quotes, apostrophes, consecutive dashes and
consecutive dots into curly quotes, EN- and EM-dashes and ellipsis.

The name is a homage to John Gruber's SmartyPants, which serve the same purpose.

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

import re
from html.parser import HTMLParser

class Smarty(HTMLParser):

	def __init__(self):
	
		super().__init__(convert_charrefs = True)
		
		self.substitutions = {
			'left-single-quote'                 : '‘',
			'right-single-quote_and_apostrophe' : '’',
			'left-double-quote'                 : '“',
			'right-double-quote'                : '”',
			'ellipsis'                          : '…',
			'en-dash'                           : '–',
			'em-dash'                           : '—'
		}
		"""Substitutions to perform."""
	
		self.patterns = {
			'left-single-quote'                 : r"^'|(?<=\s)'",
			'right-single-quote_and_apostrophe' : r"(?<=\S)'",
			'left-double-quote'                 : r'^"|(?<=\s)"',
			'right-double-quote'                : r'(?<=\S)"',
			'ellipsis'                          : r'\.{3,}',
			'en-dash'                           : r'(?<!-)--(?!-)',
			'em-dash'                           : r'(?<!-)---(?!-)'
		}
		"""Regular expressions for what should be substituitet."""
	
		self.empty_elements = {'img', 'br', 'hr', 'embed', 'link', 'meta'}
		"""Set of elememts with no content."""

		self.raw_elements = {'code', 'pre', 'kbd', 'samp', 'var', 'script'}	
		"""Set of elements with content that should not be priocessed."""
		
		self.is_escaping_after = False
		"""If `True` the characters &, < and > are converted to corresponding
		HTML entities. Default: False."""

		# Stack of open elements.
		self._stack = []
		
		# Resulting HTML.
		self.html = ""

	@property
	def patterns(self):
		return self._patterns

	@patterns.setter
	def patterns(self, pattern_dictonary):
		self._patterns = pattern_dictonary
		self._regexs = {}
		for key, pattern in self._patterns.items():
			self._regexs[key] = re.compile(pattern)

	def reset(self):
		super().reset()
		self.html = ""
		return self

	def feed(self, text):
		super().feed(text)
		return self

	def close(self):
		super().close()
		return self.html

	def handle_starttag(self, tag, attrs):
		if tag not in self.empty_elements:
			self._stack.append(tag)
		self.html += self.get_starttag_text()

	def handle_endtag(self, tag):

		# Empty elements are already taken care of.
		if tag in self.empty_elements: return

		# Make sure we are closing the right element.
		expected_end_tag = self._stack.pop()
		if tag != expected_end_tag:
			raise Exception("Expected </{0}> but got </{1}>.".format(expected_end_tag, tag))

		# Close the element.
		self.html += "</{}>".format(tag)

	def handle_data(self, data):
		if len(self._stack) == 0 or self._stack[0] not in self.raw_elements:
			for key, substitution in self.substitutions.items():
				if substitution:
					try:
						data = self._regexs[key].sub(substitution, data)
					except KeyError:
						raise KeyError("No pattern defined for {}.".format(key))
		if self.is_escaping_after:
			data = escape(data)
		self.html += data
		
	def handle_comment(self, data):
		self.html += '<!--' + data + '-->'
