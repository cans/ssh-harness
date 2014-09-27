# -*- coding: utf-8-unix; -*-
try:
    from unittest.mock import Mock, patch
except:
    from mock import Mock, patch
import multiprocessing
import os
from unittest import TestCase

from vcs_ssh import rejectpush, rejectcommand


class RejectFunctionsTestCase(TestCase):

    def test_rejectpush_without_argument(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectpush()

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            "remote: \033[1;41mYou only have read only access to this "
            "repository\033[0m: you cannot push anything into it !\n")

    def test_rejectpush_with_ui_argument(self):
        ui = Mock()
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectpush(ui)

        self.assertEqual(res, 255)
        ui.warn.assert_called_once_with('Permission denied\n')
        stderrmock.write.assert_called_once_with(
            "\033[1;41mYou only have read only access to this "
            "repository\033[0m: you cannot push anything into it !\n")

    def test_rejectcommand_without_extra(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectcommand('foo')

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            'remote: Illegal command "foo"\n')

    def test_rejectcommand_with_extra(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectcommand('foo', extra='bar')

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            'remote: Illegal command "foo": bar\n')
