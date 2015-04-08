# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014-2015, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of ssh-harness.
#
#  ssh-harness is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  ssh-harness is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ssh-harness.  If not, see <http://www.gnu.org/licenses/>.
#

# DO NOT IMPORT unicode_literals from __future__ here: we test stuff
# with literal strings we do not want to necessarily be Py2 unicode
# instances.
import sys
from unittest import TestCase
from ssh_harness import hexdump
if (3, 0, 0, ) > sys.version_info:
    from StringIO import StringIO
else:
    from io import StringIO


class HexDumpTestCase(TestCase):
    """Extensively tests the hexdump function to make sure it can gobble
    whatever it is fed with.

    For the tests with multi-byte, we are not very bold, we just try with
    european chars. I am not sure that doing more would prevent more flaws,
    but I'd like to know if I am wrong.

    As to what to expect given the different encodings (according GuCharMap),
    value are given in sequence of bytes which value is encoding in
    hexadecimal.

    ====== =============== ===============
    Symbol UTF-16 Encoding UTF-8 Encoding
    ====== =============== ===============
    €      20 AC           E2 82 AC
    ------ --------------- ---------------
    ê      00 EA           C3 AA
    ------ --------------- ---------------
    ë      00 EB           C3 AB
    ------ --------------- ---------------
    É      00 C9           C3 89
    ------ --------------- ---------------
    È      00 C8           C3 88
    ------ --------------- ---------------
    ẽ      1E BD           E1 BA BD
    ====== =============== ===============

    Also note that python seems to use Little-Endian utf-16 by default and adds
    the corresponding BOM (FF FE). This was found on Python 2.7.9 and
    3.4.3 on a Debian GNU/Linux distribution.
    """

    def setUp(self):
        self.output = StringIO()

    def tearDown(self):
        self.output = None

    def test_hexdump_on_empty_str(self):
        l = hexdump('', file=self.output)

        self.assertEqual(self.output.getvalue(),
                         '00000000\n')
        self.assertEqual(l, 0)

    def test_hexdump_on_empty_bytes(self):
        l = hexdump(b'', file=self.output)

        self.assertEqual(self.output.getvalue(),
                         '00000000\n')
        self.assertEqual(l, 0)

    def test_hexdump_on_empty_unicode(self):
        l = hexdump(u'', file=self.output)

        self.assertEqual(self.output.getvalue(),
                         '00000000\n')
        self.assertEqual(l, 0)

    def test_hexdump_on_plain_ascii_str(self):
        l = hexdump('0123456789ABCDEFGHIJKLMNOP',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010  47 48 49 4a 4b 4c 4d 4e  4f 50                    '
            '|GHIJKLMN OP|\n'
            '0000001a\n')
        self.assertEqual(l, 26)

    def test_hexdump_on_plain_ascii_bytes(self):
        l = hexdump(b'0123456789ABCDEFGHIJKLMNOP',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010  47 48 49 4a 4b 4c 4d 4e  4f 50                    '
            '|GHIJKLMN OP|\n'
            '0000001a\n')
        self.assertEqual(l, 26)

    def test_hexdump_on_plain_ascii_unicode(self):
        l = hexdump(u'0123456789ABCDEFGHIJKLMNOP',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010  47 48 49 4a 4b 4c 4d 4e  4f 50                    '
            '|GHIJKLMN OP|\n'
            '0000001a\n')
        self.assertEqual(l, 26)

    def test_hexdump_on_plain_ascii_str_8_bytes(self):
        """Makes sure that, when exactly 8 bytes are printed:

        - No space is inserted in the plain section;
        - there is the right amount of padding between the hex and the plain
          section;
        """
        l = hexdump('01234567',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37                           '
            '|01234567|\n'
            '00000008\n')
        self.assertEqual(l, 8)

    def test_hexdump_on_plain_ascii_unicode_8_bytes(self):
        """Makes sure that, when exactly 8 bytes are printed:

        - No space is inserted in the plain section;
        - there is the right amount of padding between the hex and the plain
          section;
        """
        l = hexdump(u'01234567',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37                           '
            '|01234567|\n'
            '00000008\n')
        self.assertEqual(l, 8)

    def test_hexdump_on_plain_ascii_bytes_8_bytes(self):
        """Makes sure that, when exactly 8 bytes are printed:

        - No space is inserted in the plain section;
        - there is the right amount of padding between the hex and the plain
          section;
        """
        l = hexdump(b'01234567',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37                           '
            '|01234567|\n'
            '00000008\n')
        self.assertEqual(l, 8)

    def test_hexdump_on_plain_ascii_str_16_bytes(self):
        l = hexdump('0123456789ABCDEF',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010\n')
        self.assertEqual(l, 16)

    def test_hexdump_on_plain_ascii_bytes_16_bytes(self):
        l = hexdump(b'0123456789ABCDEF',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010\n')
        self.assertEqual(l, 16)

    def test_hexdump_on_plain_ascii_unicode_16_bytes(self):
        """Makes sure no space is inserted in the section between pipes
        if exactly 8 bytes are printed.
        """
        l = hexdump(u'0123456789ABCDEF',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  30 31 32 33 34 35 36 37  38 39 41 42 43 44 45 46  '
            '|01234567 89ABCDEF|\n'
            '00000010\n')
        self.assertEqual(l, 16)

    def test_hexdump_on_string_with_multibyte_chars(self):
        l = hexdump('ÉÈ€eêëẽ', file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  c3 89 c3 88 e2 82 ac 65  c3 aa c3 ab e1 ba bd    '
            '|.......e .......|\n'
            '0000000f\n')
        self.assertEqual(l, 15)

    def test_hexdump_on_unicode_with_multibyte_chars(self):
        l = hexdump(u'ÉÈ€eêëẽ', file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  c3 89 c3 88 e2 82 ac 65  c3 aa c3 ab e1 ba bd    '
            '|.......e .......|\n'
            '0000000f\n')
        self.assertEqual(l, 15)

    def test_hexdump_on_bytes_with_multibyte_chars(self):
        l = hexdump(b'\xC3\x89\xC3\x88\xE2\x82\xACe\xC3\xAA\xC3\xAB'
                    b'\xE1\xBA\xBD',
                    file=self.output)

        self.assertEqual(
            self.output.getvalue(),
            '00000000  c3 89 c3 88 e2 82 ac 65  c3 aa c3 ab e1 ba bd    '
            '|.......e .......|\n'
            '0000000f\n')
        self.assertEqual(l, 15)
