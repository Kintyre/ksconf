from __future__ import unicode_literals

# ANSI_COLOR = "\x1b[{0}m"
ANSI_BOLD = 1
ANSI_RED = 31
ANSI_GREEN = 32
ANSI_YELLOW = 33
ANSI_RESET = 0
FORCE_TTY_COLOR = False


def tty_color(stream, *codes):
    if codes and FORCE_TTY_COLOR or hasattr(stream, "isatty") and stream.isatty():
        stream.write("\x1b[{}m".format(";".join([str(i) for i in codes])))
