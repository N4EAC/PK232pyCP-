# pk232py - Modern multimode terminal for AEA PK-232 / PK-232MBX TNC
# Copyright (C) 2026  OE3GAS  —  GPL v2
"""Unit tests for EpsonFaxParser (modes/fax.py).

The PK-232 sends FAX over $3F as an Epson 9-pin printer-graphics stream
(ESC L n1 n2 + N column bytes, ESC A n separators), NOT grayscale lines.
These tests pin the decode, the frame-overlapping buffer, and the rule that
0x1B is a valid DATA byte (never an escape inside a column run).

Qt-free: imports only EpsonFaxParser, so it runs without PyQt.
"""

from pk232py.modes.fax import EpsonFaxParser


def _collect(*chunks: bytes, invert: bool = False) -> list[bytes]:
    """Feed each chunk into one parser and return all emitted rows."""
    rows: list[bytes] = []
    p = EpsonFaxParser(on_row=rows.append, invert=invert)
    for ch in chunks:
        p.feed(ch)
    return rows


class TestEpsonFaxParser:
    """ESC L bit-image decoding, frame overlap, and ESC-as-data."""

    def test_single_block_8_rows(self):
        # ESC L 04 00  →  N=4 columns, then [0xFF,0x00,0xFF,0x00]
        # 0xFF = all pins set → black (0); 0x00 = no pins → white (255).
        block = b"\x1b\x4c\x04\x00" + bytes([0xFF, 0x00, 0xFF, 0x00])
        rows = _collect(block)
        assert len(rows) == 8                       # one ESC L block = 8 rows
        for row in rows:
            assert row == bytes([0, 255, 0, 255])   # every row identical

    def test_split_across_feeds_is_identical(self):
        # Same block, but split right after "1b 4c" — proves the internal
        # buffer survives across feed() calls (Host-Mode frame boundary).
        whole = b"\x1b\x4c\x04\x00" + bytes([0xFF, 0x00, 0xFF, 0x00])
        rows_whole = _collect(whole)
        rows_split = _collect(b"\x1b\x4c", b"\x04\x00\xFF\x00\xFF\x00")
        assert rows_split == rows_whole
        assert len(rows_split) == 8

    def test_split_inside_column_data(self):
        # Split inside the N-column run too (after 2 of 4 columns).
        rows = _collect(b"\x1b\x4c\x04\x00\xFF\x00", b"\xFF\x00")
        assert len(rows) == 8
        for row in rows:
            assert row == bytes([0, 255, 0, 255])

    def test_0x1b_is_a_valid_data_byte(self):
        # A column byte of 0x1B inside DATA must NOT be treated as ESC.
        # ESC L 01 00 → N=1 column == 0x1B.
        rows = _collect(b"\x1b\x4c\x01\x00\x1b")
        assert len(rows) == 8                       # parsed as 1px column, no resync
        assert all(len(r) == 1 for r in rows)
        # 0x1B = 0b0001_1011; D7..D0 top→bottom → black where bit set.
        expected = [255, 255, 255, 0, 0, 255, 0, 0]
        assert [r[0] for r in rows] == expected

    def test_esc_a_separator_is_consumed(self):
        # ESC A 08 between two ESC L blocks is a no-op separator (ignored).
        b1 = b"\x1b\x4c\x01\x00\xFF"     # block 1: 1 col, all black
        sep = b"\x1b\x41\x08"            # ESC A 8 — ignore the param
        b2 = b"\x1b\x4c\x01\x00\x00"     # block 2: 1 col, all white
        rows = _collect(b1 + sep + b2)
        assert len(rows) == 16                       # two blocks × 8 rows
        assert [r[0] for r in rows[:8]] == [0] * 8     # block 1 black
        assert [r[0] for r in rows[8:]] == [255] * 8   # block 2 white

    def test_top_pin_is_d7(self):
        # 0x80 = only D7 set → only the TOP row is black, rest white.
        rows = _collect(b"\x1b\x4c\x01\x00\x80")
        assert [r[0] for r in rows] == [0, 255, 255, 255, 255, 255, 255, 255]

    def test_invert_swaps_polarity(self):
        rows = _collect(b"\x1b\x4c\x02\x00\xFF\x00", invert=True)
        # invert: set bit → white (255), clear → black (0)
        for row in rows:
            assert row == bytes([255, 0])

    def test_reset_drops_partial_block(self):
        p = EpsonFaxParser(on_row=lambda r: None)
        p.feed(b"\x1b\x4c\x04\x00\xFF")   # mid-block (1 of 4 columns)
        p.reset()
        rows: list[bytes] = []
        p.on_row = rows.append
        # A clean, complete block after reset must decode on its own.
        p.feed(b"\x1b\x4c\x01\x00\xFF")
        assert len(rows) == 8
        assert all(r == bytes([0]) for r in rows)

    def test_empty_block_emits_nothing(self):
        # ESC L 00 00 → N=0 columns: no rows, parser stays usable.
        rows = _collect(b"\x1b\x4c\x00\x00" + b"\x1b\x4c\x01\x00\xFF")
        assert len(rows) == 8
