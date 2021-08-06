from __future__ import unicode_literals

# ANSI_COLOR = "\x1b[{0}m"
ANSI_BOLD = 1
ANSI_RED = 31
ANSI_GREEN = 32
ANSI_YELLOW = 33
ANSI_RESET = 0
TTY_COLOR_MODE = "auto"


class TermColor(object):
    """
    Simple color setting helper class that's a context manager wrapper around a stream.
    This ensure that the color is always reset at the end of a session.
    """

    def __init__(self, stream):
        self.stream = stream

        mode = TTY_COLOR_MODE.lower()
        if mode in ("off", "no", "disable"):
            self.color_enabled = False
        elif mode in ("on", "force") or (hasattr(stream, "isatty") and stream.isatty()):
            self.color_enabled = True
        else:
            self.color_enabled = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reset()

    def write(self, content):
        return self.write(content)

    def color(self, *codes):
        if codes and self.color_enabled:
            self.stream.write("\x1b[{}m".format(";".join([str(i) for i in codes])))

    def reset(self):
        self.color(ANSI_RESET)
