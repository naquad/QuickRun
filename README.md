# QuickRun

QuickRun is a simple tool to help you choose and run long commands.
Basically it is a launcher for shell with predefined set of commands.

## Motivation

I have couple dozens of SSH connections and I've got tired of
`$ ssh x<tab>y<tab>z<tab>` - shell completion was just not enough.
So I wrote this small script.

## Requirements

* Python 3
* Urwid

Maybe you'll have to edit the first line of `qr.py` to make sure it
points to correct Python interpreter.

## Installation

Put `qr.py` to some place in yout `$PATH` variable(
thats usually `/usr/local/bin` or `/usr/bin`). Enjoy.

## Usage

Create file file `.qr.conf` in your home directory that has following format:

```
# this is a comment
# it is ignored same as blank lines

# format is:
name : command to execute

# name will be displayed and command executed
# whitespace in the beginning and of line is ignored
# same as around :
# name can not contain :
```

Thats pretty much it.

**Hint:** if you're using Bash you can make it execute command on special
keysequence, for example I have `qr` bound to `Ctrl+]` in `~/.bashrc`:
```
bind -x '"\C-]":qr'
```
this way using QuickRun is even more convinient.

## Keys

* Escape / Ctrl+C - quit
* Enter - launch
* Arrow keys - navigate
* Any alphabetical character - filter

## TODO

* Make grid display items column-first, not row-first.
