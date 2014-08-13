#!/usr/bin/env python3

import urwid
import urwid.curses_display
import os
import re
import signal
from operator import itemgetter

PALETTE = [
    ('body', '', '', 'standout'),
    ('focus', 'light magenta', '', 'standout'),
    ('head', 'brown', ''),
    ('input', 'underline', ''),
    ('group', 'yellow', '')
]

class ConfigError(RuntimeError):
    pass

class Config:
    ITEM = re.compile('^\s*([^:]+?)\s*:\s*(.+)$')
    GROUP = re.compile('^\s*\{\s*(.*?)\s*\}\s*$')

    def __init__(self, path=None):
        if path is None:
            path = os.path.join(os.environ['HOME'], '.qr.conf')

        self.groups = []
        self.maxlen = 0
        self.read(path)

    def empty(self):
        return not self.groups

    def read(self, path):
        self.path = path
        group = ''
        groups = {}

        try:
            with open(path, 'r') as f:
                for lno, line in enumerate(f):
                    item = line.strip()
                    if item == '' or item.startswith('#'):
                        continue

                    match = self.ITEM.match(item)
                    if match is None:
                        match = self.GROUP.match(item)
                        if match is not None:
                            group = match.group(1)
                            continue

                        raise ConfigError('Invalid entry in %s:%d: %s' % (
                            path,
                            lno + 1,
                            line
                        ))

                    name = match.group(1)
                    nl = len(name)
                    if nl > self.maxlen:
                        self.maxlen = nl
                    groups.setdefault(group, [])
                    groups[group].append((name, match.group(2)))

            key = itemgetter(0)
            for group, items in sorted(groups.items(), key=key):
                items.sort(key=key)
                self.groups.append((group, items))

        except FileNotFoundError:
            pass

class CmdWidget(urwid.AttrMap):
    def __init__(self, name, command):
        self.name = name
        self.command = command
        urwid.AttrMap.__init__(self, urwid.SelectableIcon(name, 0), 'body', 'focus')

    def match(self, text):
        return text in self.name.lower()

class GroupWidget(urwid.AttrMap):
    filler = urwid.SolidFill('-')

    def __init__(self, name):
        self.name = name

        inner = urwid.Columns([
            self.filler,
            (urwid.PACK, urwid.Text(name)),
            self.filler
        ], 1, box_columns=[0, 2])

        urwid.AttrMap.__init__(self, inner, 'group')

    def selectable(self):
        return False

class ReadlineEdit(urwid.Edit):
    WORD_FW = re.compile(r'\S+\s')
    WORD_BC = re.compile(r'\S+\s*$')

    def find_next_word(self):
        match = self.WORD_FW.search(self.edit_text[self.edit_pos:])
        return match and len(match.group(0)) + self.edit_pos or len(self.edit_text)

    def find_prev_word(self):
        match = self.WORD_BC.search(self.edit_text[:self.edit_pos])
        return match and self.edit_pos - len(match.group(0)) or 0

    def keypress(self, size, key):
        if key == 'ctrl k':
            self.set_edit_text(self.edit_text[:self.edit_pos])
        elif key == 'ctrl a':
            self.set_edit_pos(0)
        elif key == 'ctrl w':
            prev_word = self.find_prev_word()
            self.set_edit_text(self.edit_text[:prev_word] + self.edit_text[self.edit_pos:])
            self.set_edit_pos(prev_word)
        elif key == 'ctrl e':
            self.set_edit_pos(len(self.edit_text))
        elif key == 'ctrl u':
            self.set_edit_text(self.edit_text[self.edit_pos:])
            self.set_edit_pos(0)
        elif key == 'meta b':
            self.set_edit_pos(self.find_prev_word())
        elif key == 'meta f':
            self.set_edit_pos(self.find_next_word())
        elif key == 'meta d':
            next_word = self.find_next_word()
            self.set_edit_text(self.edit_text[:self.edit_pos] + self.edit_text[next_word:])
        elif key == 'left' or key == 'right':
            return key
        else:
            return urwid.Edit.keypress(self, size, key)

class FocusNoCursor(urwid.Filler):
    def render(self, size, focus=False):
        canv = urwid.canvas.CompositeCanvas(urwid.Filler.render(self, size, True))
        canv.cursor = None
        return canv

class QR(urwid.Frame):
    def __init__(self, config):
        self.command = None
        self.config = config
        self._build_widgets()
        self._populate_pile()

        self.filter = ReadlineEdit('')
        urwid.connect_signal(self.filter, 'change', self.on_filter)

        header = urwid.Columns([
            ('pack', urwid.AttrMap(urwid.Text('Filter>'), 'head')),
            urwid.AttrMap(self.filter, 'input')
        ], 1)

        urwid.Frame.__init__(self, FocusNoCursor(self.pile, 'top'), header=header, focus_part='header')

    def _build_widgets(self):
        self.pile = urwid.Pile([])
        self._widgets = []
        opts = self.pile.options()

        for group, items in self.config.groups:
            out = [None, None, None]

            if group:
                out[0] = (GroupWidget(group), opts)

            out[1] = (urwid.GridFlow([], self.config.maxlen, 1, 0, urwid.LEFT), opts)
            go = out[1][0].options()
            out[2] = [
                (CmdWidget(*item), go)
                for item in items
            ]

            self._widgets.append(out)

        nf = urwid.BigText('Not found', urwid.HalfBlock5x4Font())
        nf = urwid.Padding(nf, 'center', 'clip')
        nf = urwid.Pile([urwid.Divider(), nf])

        self._not_found = (nf, opts)

    def _populate_pile(self, search=None):
        result = []
        opts = self.pile.options()

        for i, (gw, gfw, cmds) in enumerate(self._widgets):
            if search:
                cmds = [cmd for cmd in cmds if cmd[0].match(search)]
                if not cmds:
                    continue

            if gw:
                result.append(gw)

            result.append(gfw)
            gfw[0].contents = cmds
            gfw[0].set_focus(0)

        if not result:
            result.append(self._not_found)

        self.pile.contents = result
        idx = int(not isinstance(result[0][0], urwid.GridFlow))
        if idx < len(result):
            self.pile.set_focus(idx)

    def on_filter(self, _, text):
        self._populate_pile(text.lower())

    PASS_TO_GRID = ['up', 'down', 'left', 'right']

    def keypress(self, size, key):
        # an ugly hack to make page up/down to work at least somehow
        if key == 'esc':
            raise urwid.ExitMainLoop()
        elif key == 'enter':
            self.exec_cmd()
        elif key in self.PASS_TO_GRID:
            (maxcol, maxrow) = size

            if self.header is not None:
                maxrow -= self.header.rows((maxcol,))
            if self.footer is not None:
                maxrow -= self.footer.rows((maxcol,))

            if maxrow <= 0:
                return key

            return self.body.keypress((maxcol, maxrow), key)
        else:
            return self.__super.keypress(size, key)

    def exec_cmd(self):
        current = self.pile.focus
        current = current and current.focus
        if isinstance(current, CmdWidget):
            self.command = current
            raise urwid.ExitMainLoop()

def main():
    import sys
    config = Config()
    if config.empty():
        print('No items in config. Please add some in %s' % config.path)
        sys.exit(0)

    def exit_main_loop(*unused):
        raise urwid.ExitMainLoop()

    signal.signal(signal.SIGINT, exit_main_loop)
    signal.signal(signal.SIGTERM, exit_main_loop)

    qr = QR(config)
    urwid.MainLoop(qr, PALETTE, handle_mouse=False).run()
    sys.stdout.flush()
    sys.stderr.flush()
    if qr.command is not None:
        print('%s\n\033]2;%s\a' % (qr.command.command, qr.command.name), end='')
        os.execl('/bin/sh', '/bin/sh', '-c', qr.command.command,)

if __name__ == '__main__':
    main()
