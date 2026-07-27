"""block-blank — plain building block: body + stud + socket, no marble path."""

import lib

NAME = "block-blank"


def build():
    return lib.block_base(lib.HEIGHT).removeSplitter()
