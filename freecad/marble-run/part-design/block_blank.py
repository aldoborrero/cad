"""block-blank — plain building block (body + stud + socket, no marble path)."""

import lib

NAME = "block-blank"


def build(doc):
    return lib.base_block(doc, lib.HEIGHT)
