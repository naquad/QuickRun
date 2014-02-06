#!/usr/bin/env python3

import urwid
import urwid.curses_display
import os
import re
import signal
from operator import itemgetter
from urwid.canvas import CompositeCanvas

PALETTE = [
    ('body', '', '', 'standout'),
    ('focus', 'light magenta', '', 'standout'),
    ('head', 'brown', ''),
    ('input', 'underline', '')
]

class ConfigError(RuntimeError):
    pass

class Config:
    ITEM = re.compile('^\s*([^:]+?)\s*:\s*(.+)$')

    def __init__(self, path=None):
        if path is None:
            path = os.path.join(os.environ['HOME'], '.qr.conf')

        self.items = []
        self.maxlen = 0
        self.read(path)

    def empty(self):
        return not self.items

    def read(self, path):
        self.path = path

        try:
            with open(path, 'r') as f:
                for lno, line in enumerate(f):
                    item = line.strip()
                    if item == '' or item.startswith('#'):
                        continue

                    match = self.ITEM.match(item)
                    if match is None:
                        raise ConfigError('Invalid entry in %s:%d: %s' % (
                            path,
                            lno + 1,
                            line
                        ))

                    name = match.group(1)
                    nl = len(name)
                    if nl > self.maxlen:
                        self.maxlen = nl
                    self.items.append((name, match.group(2)))

            self.items.sort(key=itemgetter(0))
        except FileNotFoundError:
            pass

class CmdWidget(urwid.AttrMap):
    def __init__(self, name, command):
        self.name = name
        self.command = command
        urwid.AttrMap.__init__(self, urwid.SelectableIcon(name, 0), 'body', 'focus')

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

        self.items = [CmdWidget(*item) for item in config.items]
        self.max_width = config.maxlen
        self.grid = urwid.GridFlow(self.items, self.max_width, 1, 0, 'left')
        self.grid.set_focus(0)

        self.filter = ReadlineEdit('')
        urwid.connect_signal(self.filter, 'change', self.on_filter)

        header = urwid.Columns([
            ('pack', urwid.AttrMap(urwid.Text('Filter>'), 'head')),
            urwid.AttrMap(self.filter, 'input')
        ], 1)

        urwid.Frame.__init__(self, FocusNoCursor(self.grid, 'top'), header=header, focus_part='header')

    def on_filter(self, _, text):
        text = text.lower()

        self.grid.contents[:] = [
            (item, self.grid.options('given', self.max_width))
            for item in self.items
            if text in item.name
        ]

        if len(self.grid.contents):
            self.grid.set_focus(0)

    PASS_TO_GRID = ['up', 'down', 'left', 'right']

    def keypress(self, size, key):
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
            return urwid.Frame.keypress(self, size, key)

    def exec_cmd(self):
        current = self.grid.focus
        if current is not None:
            self.command = current.command
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
    urwid.MainLoop(qr, PALETTE).run()
    sys.stdout.flush()
    sys.stderr.flush()
    if qr.command is not None:
        print(qr.command, file=sys.stderr)
        os.execl('/bin/sh', '/bin/sh', '-c', qr.command)

if __name__ == '__main__':
    main()
