# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Advanced keyparsers."""

import traceback

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QKeySequence

from qutebrowser.keyinput import basekeyparser, keyutils
from qutebrowser.utils import message, utils
from qutebrowser.commands import runners, cmdexc


class CommandKeyParser(basekeyparser.BaseKeyParser):

    """KeyChainParser for command bindings.

    Attributes:
        _commandrunner: CommandRunner instance.
    """

    def __init__(self, win_id, parent=None, supports_count=None):
        super().__init__(win_id, parent, supports_count)
        self._commandrunner = runners.CommandRunner(win_id)

    def execute(self, cmdstr, count=None):
        try:
            self._commandrunner.run(cmdstr, count)
        except cmdexc.Error as e:
            message.error(str(e), stack=traceback.format_exc())


class PassthroughKeyParser(CommandKeyParser):

    """KeyChainParser which passes through normal keys.

    Used for insert/passthrough modes.

    Attributes:
        _mode: The mode this keyparser is for.
        _orig_sequence: Cuerrent sequence with no key_mappings applied
        _ignore_next_key: Whether to pass the next key through
    """

    do_log = False
    passthrough = True

    def __init__(self, win_id, mode, parent=None):
        """Constructor.

        Args:
            mode: The mode this keyparser is for.
            parent: Qt parent.
            warn: Whether to warn if an ignored key was bound.
        """
        super().__init__(win_id, parent)
        self._read_config(mode)
        self._orig_sequence = keyutils.KeySequence()
        self._mode = mode
        self._ignore_next_key = False

    def __repr__(self):
        return utils.get_repr(self, mode=self._mode)

    def handle(self, e, *, dry_run=False):
        """Override to pass the chain through on NoMatch

        Args:
            e: the KeyPressEvent from Qt.
            dry_run: Don't actually execute anything, only check whether there
                     would be a match.

        Return:
            A self.Match member.
        """
        if keyutils.is_modifier_key(e.key()) or self._ignore_next_key:
            self._ignore_next_key = self._ignore_next_key and dry_run
            return QKeySequence.NoMatch

        orig_sequence = self._orig_sequence.append_event(e)
        match = super().handle(e, dry_run=dry_run)

        if not dry_run and match == QKeySequence.PartialMatch:
            self._orig_sequence = orig_sequence

        if dry_run or len(orig_sequence) == 1 or match != QKeySequence.NoMatch:
            return match

        window = QApplication.focusWindow()
        if window is None:
            return match

        self._ignore_next_key = True
        for keyinfo in orig_sequence:
            press_event = keyinfo.to_event(QEvent.KeyPress)
            release_event = keyinfo.to_event(QEvent.KeyRelease)
            QApplication.postEvent(window, press_event)
            QApplication.postEvent(window, release_event)

        return QKeySequence.ExactMatch

    def clear_keystring(self):
        """Override to also clear the original sequence."""
        if self._orig_sequence:
            self._orig_sequence = keyutils.KeySequence()
        super().clear_keystring()
