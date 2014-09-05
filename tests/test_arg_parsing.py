# -*- coding: utf-8-unix; -*-
import os
from unittest import TestCase
from vcs_ssh import parse_args


class VcsSshArgsParserTestCase(TestCase):

    def setUp(self):
        self._rw_dirs = ['ABC', 'DEF', 'IJK']
        self._ro_dirs = ['LMN', 'OPQ', 'RST']

    def _mk_proof_list(self, attr='_rw_dirs'):
        cwd = os.getcwd()
        l = [os.path.sep.join([cwd, x]) for x in getattr(self, attr)]
        l.sort()
        return l

    def _mk_ro_proof(self):
        return self._mk_proof_list(attr='_ro_dirs')

    def _mk_rw_proof(self):
        return self._mk_proof_list()

    def test_all_implicit_rw_dirs_command_line(self):

        args = parse_args(self._rw_dirs * 1)

        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], [])

    def test_all_explicit_ro_dirs_command_line(self):

        args = parse_args(['--read-only'] + self._ro_dirs * 1)

        self.assertEqual(args['rw_dirs'], [])
        self.assertEqual(args['ro_dirs'], self._mk_ro_proof())

    def test_explicit_rw_and_ro_dirs_command_line(self):

        args = parse_args(['--read-only', ]
                          + self._ro_dirs * 1
                          + ['--read-write', ]
                          + self._rw_dirs * 1)

        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], self._mk_ro_proof())

    def test_explicit_and_implicit_rw_dirs_command_line(self):
        args = parse_args(self._rw_dirs[:2]
                          + ['--read-write', ]
                          + self._rw_dirs[2:])

        args['rw_dirs'].sort()
        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], [])

# vim:
