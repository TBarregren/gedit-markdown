#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SimpleConfig – a facade that simplifies the use of `configparser.ConfigParser`.

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

from configparser import ConfigParser, DuplicateSectionError

class SimpleConfig:

	"""
		A facade that simplifies the use of `configparser.ConfigParser`.
		
		Python's ConfigParser class implements a basic configuration language
		which provides a structure similar to what’s found in Microsoft Windows
		INI files. SimpleConfig provides a facade to ConfigParser		
	"""
	
	# We can't use "0" and "1" for false and true in configuration files,
	# since __getitem__() shall return any number as a float. We don't use
	# ConfigParser.getboolean() in the implementation of __getitem__()
	# because that would require deletion of the keys "0" and "1" in
	# ConfigParser.BOOLEAN_STATES which is a class constant and hence
	# affect all instances of ConfigParser. Although it is not likely to
	# be more than one instnace, we take the safe route and implement an
	# own solution.
	BOOLEAN_STATES = {
		'false': False,
		'off': False,
		'no': False,
		'true': True,
		'on': True,
		'yes': True
	}

	def __init__(self, config=None):

		# The actual work is done by this ConfigParser object.
		if config is None:
			self._config = ConfigParser()
		elif isinstance(config, ConfigParser):
			self._config = config
		else:
			raise TypeError("The config object is not a configparser.ConfigParser")
		
		# Holds the name of the current section we work with.
		self._section = None
	
	@property
	def current_section(self):
		return self._section

	@current_section.setter
	def current_section(self, section):
		try:
			self._config.add_section(section)
		except DuplicateSectionError:
			pass
		self._section = section

	@property
	def current_dictionary(self):
		if self._section is None:
			raise LookupError("No current section set.")
		return dict(self._config.items(self._section))

	@current_dictionary.setter
	def current_dictionary(self, dictionary):
		if self._section is None:
			raise LookupError("No current section set.")
		self._config[self._section] = dictionary

	def __getitem__(self, key):
		if self._section is None:
			raise LookupError("No current section set.")
		val = self._config[self._section][key]
		if val.lower() in SimpleConfig.BOOLEAN_STATES:
			return SimpleConfig.BOOLEAN_STATES[val.lower()]
		try:
			return float(val)
		except ValueError:
			return val

	def __setitem__(self, key, value):
		if self._section is None:
			raise LookupError("No current section set.")
		self._config[self._section][key] = str(value)

	def read_files(self, *files):
		return self._config.read(files)

	def write_file(self, file):
		with open(file, 'w') as f:
			self._config.write(f)
			
	def get_ConfigParser(self):
		return self._config

	def to_dict(self):
		d = {}
		for section in self._config.sections():
			d[section] = dict(self._config.items(section))
		return d

	def __str__(self):
		return to_dict(self).__str__()

