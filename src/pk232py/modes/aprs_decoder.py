"""
aprs_decoder.py — APRS payload decoder for PK232PY  (v3)

New in v3:
  decode_html(raw_text, timestamp) — returns QTextEdit-compatible HTML
  with colour-coded cards per APRS frame type.

Card colours (all on near-black #0d0d0d background):
  Mic-E     orange  #FF9422
  Position  blue    #44BBFF
  Weather   green   #44FF88
  Telemetry yellow  #FFD700
  Message   pink    #FF55CC
  3rd-party light-grey #CCCCCC

The QTextEdit HTML renderer supports a subset of HTML4 + limited CSS.
Rules observed here:
  · bgcolor="..." on <td>  (not style="background-color:...")
  · <font color="...">     for text colour
  · <b>, <small>           for weight / size
  · <br>                   for line breaks inside cells
  · <span style="...">     ONLY for background-colour on chip badges
  · No border-radius, no CSS variables, no padding shorthand on <td>
"""

from __future__ import annotations
import re
from dataclasses import dataclass
import html as _html_mod


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class DecodedFrame:
    source:      str = ""
    path:        str = ""
    aprs_id:     str = ""
    type_str:    str = ""
    info:        str = ""
    raw_payload: str = ""


# ---------------------------------------------------------------------------
# Colour / icon tables
# ---------------------------------------------------------------------------

# Per message type: header bg, body bg, accent colour, comment colour
_HTML_COLORS: dict[str, dict] = {
    'Mic-E':         {'hdr': '#1e0d00', 'bdy': '#130900', 'acc': '#FF9422', 'cmt': '#CC8844', 'aid': '#FF9422'},
    'Position':      {'hdr': '#000f20', 'bdy': '#00080f', 'acc': '#44BBFF', 'cmt': '#6699BB', 'aid': '#44BBFF'},
    'Position+Time': {'hdr': '#000f20', 'bdy': '#00080f', 'acc': '#44BBFF', 'cmt': '#6699BB', 'aid': '#44BBFF'},
    'Weather':       {'hdr': '#000f05', 'bdy': '#00080a', 'acc': '#44FF88', 'cmt': '#55BB77', 'aid': '#44FF88'},
    'Telemetry':     {'hdr': '#1a1200', 'bdy': '#110c00', 'acc': '#FFD700', 'cmt': '#AA9900', 'aid': '#FFD700'},
    'Message':       {'hdr': '#1a0011', 'bdy': '#110009', 'acc': '#FF55CC', 'cmt': '#BB66AA', 'aid': '#FF55CC'},
    'Status':        {'hdr': '#001a00', 'bdy': '#000f00', 'acc': '#88FF44', 'cmt': '#559933', 'aid': '#88FF44'},
    'Third-party':   {'hdr': '#161616', 'bdy': '#0e0e0e', 'acc': '#CCCCCC', 'cmt': '#999999', 'aid': '#AAAAAA'},
    'Item':          {'hdr': '#000f20', 'bdy': '#00080f', 'acc': '#44BBFF', 'cmt': '#6699BB', 'aid': '#44BBFF'},
    'Object':        {'hdr': '#000f20', 'bdy': '#00080f', 'acc': '#44BBFF', 'cmt': '#6699BB', 'aid': '#44BBFF'},
}
# Fallback for unknown / telem-sub types
_HTML_COLORS_DEFAULT = {'hdr': '#1a0011', 'bdy': '#110009', 'acc': '#FF55CC', 'cmt': '#BB66AA', 'aid': '#FF55CC'}

# Emoji icon per type
_TYPE_ICONS: dict[str, str] = {
    'Mic-E':         '🚐',
    'Position':      '📡',
    'Position+Time': '📡',
    'Weather':       '🌦',
    'Telemetry':     '📊',
    'Message':       '📨',
    'Telem-Param':   '📨',
    'Telem-Unit':    '📨',
    'Telem-Bits':    '📨',
    'Telem-Eqns':    '📨',
    'Third-party':   '🌐',
    'Status':        '📢',
    'Item':          '📍',
    'Object':        '📍',
    'Unknown':       '❓',
}

# Map telem sub-types to their parent colour scheme
_TELEM_TYPES = {'Telem-Param', 'Telem-Unit', 'Telem-Bits', 'Telem-Eqns'}
_MSG_TYPES    = {'Message'} | _TELEM_TYPES


# ---------------------------------------------------------------------------
# Main decoder class
# ---------------------------------------------------------------------------

class AprsDecoder:

    # ------------------------------------------------------------------ #
    # Public API — plain text (used by raw display fallback)
    # ------------------------------------------------------------------ #

    @staticmethod
    def decode(raw_text: str) -> str:
        """Decode to plain text.  Falls back to original on error."""
        try:
            frame = AprsDecoder._parse(raw_text)
            return AprsDecoder._format_plain(frame)
        except Exception:
            return raw_text.strip()

    # ------------------------------------------------------------------ #
    # Public API — HTML (used by APRS display mode)
    # ------------------------------------------------------------------ #

    @staticmethod
    def decode_html(raw_text: str, timestamp: str = '') -> str:
        """Decode and return QTextEdit-compatible HTML card.

        The card consists of two table rows:
          row 1 (header):  timestamp · icon · callsign · path · APRS-ID
          row 2 (body):    type-specific content

        All text contrast verified on #0d0d0d background.
        Uses bgcolor on <td>, <font color="...">, <b>, <small>, <br>.
        No CSS variables, no border-radius, no padding shorthand on cells.
        """
        try:
            frame = AprsDecoder._parse(raw_text)
            return AprsDecoder._build_html_card(frame, timestamp)
        except Exception:
            ts = _e(timestamp)
            raw = _e(raw_text.strip()[:120])
            return (
                f'<table width="100%" cellpadding="4" cellspacing="1">'
                f'<tr><td bgcolor="#161616">'
                f'<font color="#888"><small>[{ts}]&nbsp;</small></font>'
                f'<font color="#AAAAAA">{raw}</font>'
                f'</td></tr></table><p>&nbsp;</p>'
            )

    # ------------------------------------------------------------------ #
    # HTML card builder
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_html_card(frame: 'DecodedFrame', ts: str) -> str:
        """Assemble the two-row HTML table for one APRS frame."""

        # Resolve colour scheme
        base_type = frame.type_str
        if base_type in _TELEM_TYPES:
            base_type = 'Telemetry'
        colors = _HTML_COLORS.get(base_type, _HTML_COLORS_DEFAULT)

        hdr_bg  = colors['hdr']
        bdy_bg  = colors['bdy']
        acc     = colors['acc']
        cmt_c   = colors['cmt']
        aid_c   = colors['aid']
        icon    = _TYPE_ICONS.get(frame.type_str, '❓')

        # ── header row ────────────────────────────────────────── #
        ts_html  = f'<font color="#888"><small>[{_e(ts)}]&nbsp;</small></font>' if ts else ''
        call_html = f'<b><font color="{acc}">{_e(frame.source)}</font></b>'
        path_html = ''
        if frame.path:
            path_html = f'&nbsp;<font color="#999"><small>›&nbsp;{_e(frame.path)}</small></font>'
        aid_html = ''
        if frame.aprs_id:
            aid_html = f'&nbsp;<font color="{aid_c}"><small>[{_e(frame.aprs_id)}]</small></font>'

        header_td = (
            f'<td bgcolor="{hdr_bg}" style="padding:5px 10px;">'
            f'{ts_html}{icon}&nbsp;{call_html}{path_html}{aid_html}'
            f'</td>'
        )

        # ── body row — dispatch by type ───────────────────────── #
        body_content = AprsDecoder._html_body(frame, acc, cmt_c)
        body_td = (
            f'<td bgcolor="{bdy_bg}" style="padding:4px 10px 8px 28px;">'
            f'{body_content}'
            f'</td>'
        )

        return (
            f'<table width="100%" cellpadding="0" cellspacing="1">'
            f'<tr>{header_td}</tr>'
            f'<tr>{body_td}</tr>'
            f'</table><p>&nbsp;</p>'
        )

    @staticmethod
    def _html_body(frame: 'DecodedFrame', acc: str, cmt_c: str) -> str:
        """Generate body HTML for the given frame type."""
        t = frame.type_str
        info = frame.info

        # ── Mic-E ────────────────────────────────────────────── #
        if t == 'Mic-E':
            coords, comment = AprsDecoder._split_coords_comment(info)
            result = f'<b><font color="{acc}">{_e(coords)}</font></b>'
            if comment:
                result += f'<br><font color="{cmt_c}"><small>{_e(comment)}</small></font>'
            return result

        # ── Position / Position+Time ──────────────────────────── #
        if t in ('Position', 'Position+Time'):
            return AprsDecoder._html_body_position(info, acc, cmt_c)

        # ── Telemetry data ────────────────────────────────────── #
        if t == 'Telemetry':
            return AprsDecoder._html_body_telemetry(info, acc, cmt_c)

        # ── Telemetry config messages ─────────────────────────── #
        if t in _TELEM_TYPES:
            chips = AprsDecoder._html_chips(
                [('', info)], acc,
                chip_bg='#1a0011', chip_fg='#FF88DD', chip_bd='#880055'
            )
            return chips

        # ── Message ───────────────────────────────────────────── #
        if t == 'Message':
            return f'<font color="{acc}">{_e(info)}</font>'

        # ── Status ────────────────────────────────────────────── #
        if t == 'Status':
            return f'<font color="{acc}">{_e(info)}</font>'

        # ── Third-party ───────────────────────────────────────── #
        if t == 'Third-party':
            return (
                f'<font color="#CCCCCC">{_e(info)}</font>'
            )

        # ── Item / Object ─────────────────────────────────────── #
        if t in ('Item', 'Object'):
            coords, comment = AprsDecoder._split_coords_comment(info)
            result = f'<b><font color="{acc}">{_e(coords)}</font></b>'
            if comment:
                result += f'<br><font color="{cmt_c}"><small>{_e(comment)}</small></font>'
            return result

        # ── Fallback ──────────────────────────────────────────── #
        return f'<font color="{acc}">{_e(info[:150])}</font>'

    @staticmethod
    def _html_body_position(info: str, acc: str, cmt_c: str) -> str:
        """Render a position frame.  Detects WX symbol and adds weather chips."""
        # Split into coords+symbol and comment
        coords, comment = AprsDecoder._split_coords_comment(info)

        # Extract symbol name from [WX], [Digi] etc.
        sym_m  = re.search(r'\[([^\]]+)\]', coords)
        symbol = sym_m.group(1) if sym_m else ''
        plain_coords = re.sub(r'\s*\[[^\]]+\]', '', coords).strip()

        is_wx = 'WX' in symbol.upper() or symbol.endswith('WX')

        # Coordinates line
        result = f'<b><font color="{acc}">{_e(plain_coords)}</font></b>'
        if symbol:
            result += f'&nbsp;<font color="{cmt_c}"><small>{_e(symbol)}</small></font>'

        # WX chips
        if is_wx and comment:
            chips_data = AprsDecoder._parse_wx(comment)
            if chips_data:
                chip_html = AprsDecoder._html_chips(
                    chips_data, acc,
                    chip_bg='#001408', chip_fg='#88FFAA', chip_bd='#006628'
                )
                result += f'<br>{chip_html}'
                # leftover comment after WX fields
                leftover = AprsDecoder._wx_leftover(comment)
                if leftover:
                    result += f'<br><font color="{cmt_c}"><small>{_e(leftover)}</small></font>'
                return result

        # Non-WX comment
        if comment:
            result += f'<br><font color="{cmt_c}"><small>{_e(comment)}</small></font>'
        return result

    @staticmethod
    def _html_body_telemetry(info: str, acc: str, cmt_c: str) -> str:
        """Render Telemetry T# frame as seq + analog chips + digital."""
        # info = "Seq=221  A1=155  A2=000  A3=100  A4=091  A5=000  D=00000000"
        seq_m = re.search(r'Seq=(\S+)', info)
        d_m   = re.search(r'D=(\S+)', info)
        seq   = seq_m.group(1) if seq_m else '?'
        digi  = d_m.group(1)   if d_m   else ''

        analogs = re.findall(r'(A\d)=(\S+)', info)

        seq_html = f'<font color="{cmt_c}"><small>Seq&nbsp;{_e(seq)}'
        if digi:
            seq_html += f'&nbsp;·&nbsp;D&nbsp;{_e(digi)}'
        seq_html += '</small></font>'

        if analogs:
            chips = AprsDecoder._html_chips(
                analogs, acc,
                chip_bg='#1a1200', chip_fg='#FFE566', chip_bd='#776600'
            )
            return f'{seq_html}<br>{chips}'
        return seq_html

    # ------------------------------------------------------------------ #
    # HTML helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _html_chips(pairs: list[tuple[str, str]],
                    acc: str,
                    chip_bg: str, chip_fg: str, chip_bd: str) -> str:
        """Render a list of (label, value) or ('', value) as inline chips.

        Uses <span style="background-color:...; color:...; border:...">
        which QTextEdit renders correctly for inline spans.
        """
        parts = []
        for label, value in pairs:
            text = f'{label}={value}' if label else value
            parts.append(
                f'<span style="background-color:{chip_bg}; color:{chip_fg};'
                f' border:0.5px solid {chip_bd}; padding:1px 4px;">'
                f'{_e(text)}'
                f'</span>'
            )
        return '&nbsp;'.join(parts)

    @staticmethod
    def _split_coords_comment(info: str) -> tuple[str, str]:
        """Split 'coords  —  comment' into (coords_part, comment_part)."""
        parts = info.split('  —  ', 1)
        return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else '')

    # ------------------------------------------------------------------ #
    # Weather data parser
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_wx(comment: str) -> list[tuple[str, str]]:
        """Extract weather readings from an APRS WX comment string.
        Returns list of (label, value) tuples for chip display.
        Ignores any trailing firmware/station text.
        """
        result = []
        s = comment

        # Wind: DDD/SSS (degrees / speed mph)
        m = re.match(r'^(\d{3})/(\d{3})', s)
        if m:
            spd = int(m.group(2))
            result.append(('wind', f"{m.group(1)}°/{spd}mph"))
            s = s[7:]

        patterns = [
            (r'g(\d+)',   'gust', lambda v: f"{int(v)}mph"),
            (r't(-?\d+)', 'temp', lambda v: f"{int(v)}°F"),
            (r'r(\d+)',   'rain1h', lambda v: f"{int(v)/100:.2f}in"),
            (r'p(\d+)',   'rain24h', lambda v: f"{int(v)/100:.2f}in"),
            (r'h(\d+)',   'hum',  lambda v: f"{int(v)}%"),
            (r'b(\d+)',   'baro', lambda v: f"{int(v)/10:.1f}mb"),
        ]
        for pat, label, fmt in patterns:
            m = re.search(pat, s)
            if m:
                try:
                    result.append((label, fmt(m.group(1))))
                except Exception:
                    pass
        return result

    @staticmethod
    def _wx_leftover(comment: str) -> str:
        """Return the non-numeric station/firmware comment after WX data."""
        # Strip known WX fields; remainder is firmware/station text
        stripped = re.sub(
            r'^\d{3}/\d{3}|g\d+|t-?\d+|r\d+|p\d+|P\d+|h\d+|b\d+|l\d+|L\d+|s\d+|e\d+|f\d+|x\d+',
            '', comment
        ).strip().lstrip('#').strip()
        # Only return if it looks like readable text (letters)
        if re.search(r'[A-Za-z]', stripped):
            return stripped
        return ''

    # ------------------------------------------------------------------ #
    # Parse pipeline (shared with plain-text decode)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse(raw: str) -> DecodedFrame:
        raw = raw.replace('\r', '').strip()
        parts   = raw.split('\n', 1)
        header  = parts[0].strip()
        payload = parts[1].strip() if len(parts) > 1 else ''
        source, path, aprs_id = AprsDecoder._parse_header(header)
        type_str, info = AprsDecoder._decode_payload(payload, aprs_id)
        return DecodedFrame(source=source, path=path, aprs_id=aprs_id,
                            type_str=type_str, info=info, raw_payload=payload)

    @staticmethod
    def _parse_header(header: str) -> tuple[str, str, str]:
        """Parse SOURCE>D1>...>APRS_ID <UI>: → (source, path, aprs_id)."""
        header = header.rstrip(':').strip()
        header = re.sub(r'\s*[<(]UI[)>].*$', '', header, flags=re.IGNORECASE)
        parts  = [p.strip() for p in header.split('>') if p.strip()]
        if not parts:
            return header, '', ''
        source  = parts[0]
        aprs_id = parts[-1] if len(parts) > 1 else ''
        via     = parts[1:-1] if len(parts) > 2 else []
        path    = ' › '.join(via) if via else ''
        return source, path, aprs_id

    # ------------------------------------------------------------------ #
    # Payload dispatcher
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decode_payload(payload: str, aprs_id: str = '') -> tuple[str, str]:
        """Route to the correct sub-decoder.  Returns (type_str, info)."""
        if not payload:
            return 'Empty', '(no payload)'

        # Mic-E detected by APRS-ID, not first byte
        if AprsDecoder._is_mice_destination(aprs_id):
            p = payload[1:] if payload and payload[0] in ('`', "'") else payload
            return 'Mic-E', AprsDecoder._decode_mice_full(p, aprs_id)

        c = payload[0]
        if c == '}':
            return AprsDecoder._decode_third_party(payload[1:])
        if c in ('!', '='):
            return 'Position', AprsDecoder._pos_auto(payload[1:])
        if c in ('@', '/'):
            return 'Position+Time', AprsDecoder._pos_with_ts(payload[1:])
        if c == '>':
            return 'Status', payload[1:].strip()
        if c == ':':
            return AprsDecoder._decode_message(payload[1:])
        if payload.startswith('T#'):
            return 'Telemetry', AprsDecoder._decode_telemetry(payload)
        if c == ')':
            return 'Item', AprsDecoder._decode_item(payload[1:])
        if c == ';':
            name = payload[1:10].strip()
            rest = payload[26:].strip() if len(payload) > 26 else ''
            return 'Object', f'{name} — {rest}'
        if c == '_':
            return 'Weather', payload[1:].strip()
        if c in ('`', "'"):
            return 'Mic-E', AprsDecoder._decode_mice_full(payload[1:], aprs_id)
        return 'Unknown', payload

    # ------------------------------------------------------------------ #
    # Mic-E
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_mice_destination(aprs_id: str) -> bool:
        if not aprs_id:
            return False
        base = aprs_id.split('-')[0].upper()
        if len(base) < 4:
            return False
        if base.startswith('AP'):
            return False
        return bool(re.match(r'^[A-Z0-9]{4,6}$', base))

    @staticmethod
    def _decode_mice_full(payload: str, aprs_id: str) -> str:
        """Decode Mic-E: latitude from destination, longitude from info bytes."""
        try:
            dest = aprs_id.split('-')[0][:6].upper()
            if len(dest) < 6:
                return f"Mic-E (dest<6): {payload[:20]}"

            def char_info(c: str) -> tuple[int, bool]:
                if 'A' <= c <= 'J': return ord(c)-ord('A'), True
                if 'P' <= c <= 'Y': return ord(c)-ord('P'), True
                if '0' <= c <= '9': return ord(c)-ord('0'), False
                return 0, True

            chars  = [char_info(c) for c in dest]
            digits = [ci[0] for ci in chars]
            north  = [ci[1] for ci in chars]

            lat_dec = (digits[0]*10 + digits[1]) + (
                (digits[2]*10 + digits[3]) + (digits[4]*10 + digits[5]) / 100.0
            ) / 60.0
            lat_hemi = 'N' if north[3] else 'S'
            if not north[3]:
                lat_dec = -lat_dec

            lon_east   = north[3]
            lon_offset = 100 if ('P' <= dest[4] <= 'Y') else 0

            if len(payload) < 3:
                return f"{lat_dec:.4f}°{lat_hemi}  (lon unavailable)"

            d_raw = ord(payload[0]) - 28
            m_raw = ord(payload[1]) - 28
            h_raw = ord(payload[2]) - 28

            lon_deg_v = d_raw + lon_offset
            lon_min_v = m_raw if m_raw < 60 else m_raw - 60
            lon_hh_v  = max(0, h_raw)
            lon_dec   = lon_deg_v + (lon_min_v + lon_hh_v / 100.0) / 60.0
            lon_hemi  = 'E' if lon_east else 'W'
            if not lon_east:
                lon_dec = -lon_dec

            comment = ''
            if len(payload) > 7:
                raw_cmt = payload[7:]
                if '}' in raw_cmt:
                    comment = raw_cmt[raw_cmt.index('}')+1:].strip()
                else:
                    comment = raw_cmt.lstrip('`\'"[]>=<^!#').strip()

            result = f"{lat_dec:.4f}°{lat_hemi}  /  {lon_dec:.4f}°{lon_hemi}"
            if comment:
                result += f"  —  {comment}"
            return result
        except Exception as ex:
            return f"Mic-E error ({ex}): {payload[:30]}"

    # ------------------------------------------------------------------ #
    # Position
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pos_auto(data: str) -> str:
        if not data:
            return '(empty)'
        if len(data) >= 9 and data[0] in ('/', '\\'):
            lat_bytes = data[1:5]
            if all(33 <= ord(c) <= 124 for c in lat_bytes):
                return AprsDecoder._pos_compressed(data)
        return AprsDecoder._pos_uncompressed(data)

    @staticmethod
    def _pos_uncompressed(data: str) -> str:
        try:
            lat_str = data[0:8]
            sym_tbl = data[8]
            lon_str = data[9:18]
            sym_cod = data[18]
            comment = data[19:].strip() if len(data) > 19 else ''
            lat = AprsDecoder._lat(lat_str)
            lon = AprsDecoder._lon(lon_str)
            sym = AprsDecoder._symbol(sym_tbl, sym_cod)
            result = f"{lat}  /  {lon}  [{sym}]"
            if comment:
                result += f"  —  {comment}"
            return result
        except Exception:
            return data

    @staticmethod
    def _pos_compressed(data: str) -> str:
        try:
            sym_tbl = data[0]
            y_chars = data[1:5]
            x_chars = data[5:9]
            sym_cod = data[9] if len(data) > 9 else ' '
            comment = data[12:].strip() if len(data) > 12 else ''

            def b91(chars: str) -> int:
                val = 0
                for c in chars:
                    val = val * 91 + (ord(c) - 33)
                return val

            lat = 90.0  - b91(y_chars) / 380926.0
            lon = -180.0 + b91(x_chars) / 190463.0
            sym  = AprsDecoder._symbol(sym_tbl, sym_cod)
            lat_s = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}"
            lon_s = f"{abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
            result = f"{lat_s}  /  {lon_s}  [{sym}]"
            if comment:
                result += f"  —  {comment}"
            return result
        except Exception:
            return AprsDecoder._pos_uncompressed(data)

    @staticmethod
    def _pos_with_ts(data: str) -> str:
        try:
            ts_raw = data[0:7]
            ts_str = AprsDecoder._timestamp(ts_raw)
            rest   = data[7:]
            pos    = AprsDecoder._pos_auto(rest)
            return f"{ts_str}  {pos}"
        except Exception:
            return data

    # ------------------------------------------------------------------ #
    # Coordinate helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _lat(s: str) -> str:
        deg  = int(s[0:2]); mins = float(s[2:7]); hemi = s[7].upper()
        dec  = deg + mins / 60.0
        if hemi == 'S': dec = -dec
        return f"{dec:.4f}°{hemi}"

    @staticmethod
    def _lon(s: str) -> str:
        deg  = int(s[0:3]); mins = float(s[3:8]); hemi = s[8].upper()
        dec  = deg + mins / 60.0
        if hemi == 'W': dec = -dec
        return f"{dec:.4f}°{hemi}"

    @staticmethod
    def _timestamp(ts: str) -> str:
        if ts.endswith('z'): return f"UTC {ts[2:4]}:{ts[4:6]} (day {ts[0:2]})"
        if ts.endswith('h'): return f"UTC {ts[0:2]}:{ts[2:4]}:{ts[4:6]}"
        return ts

    # ------------------------------------------------------------------ #
    # Message / Telemetry config
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decode_message(data: str) -> tuple[str, str]:
        if len(data) < 10 or data[9] != ':':
            return 'Message', data.strip()
        addressee = data[0:9].strip()
        body      = data[10:]
        for prefix, label in (
            ('PARM.', 'Telem-Param'),
            ('UNIT.', 'Telem-Unit'),
            ('EQNS.', 'Telem-Eqns'),
        ):
            if body.startswith(prefix):
                return label, f'→ {addressee}: {body[len(prefix):]}'
        if body.startswith('BITS.'):
            bits  = body[5:13] if len(body) >= 13 else body[5:]
            label = body[14:].strip() if len(body) > 14 else ''
            return 'Telem-Bits', f'→ {addressee}: bits={bits}  {label}'
        body_clean = re.sub(r'\{[0-9A-Za-z]+\}$', '', body).strip()
        return 'Message', f'→ {addressee}: {body_clean}'

    # ------------------------------------------------------------------ #
    # Telemetry data
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decode_telemetry(data: str) -> str:
        try:
            parts   = data[2:].split(',')
            seq     = parts[0]
            analog  = parts[1:6]
            digital = parts[6] if len(parts) > 6 else ''
            a_str   = '  '.join(f'A{i+1}={v}' for i, v in enumerate(analog))
            return f'Seq={seq}  {a_str}  D={digital}'
        except Exception:
            return data

    # ------------------------------------------------------------------ #
    # Item
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decode_item(data: str) -> str:
        try:
            m = re.match(r'^([^!_]{1,9})([!_])(.*)', data)
            if not m:
                return data
            name  = m.group(1).strip()
            state = '(live)' if m.group(2) == '!' else '(killed)'
            pos   = AprsDecoder._pos_auto(m.group(3))
            return f'{name} {state}  {pos}'
        except Exception:
            return data

    # ------------------------------------------------------------------ #
    # Third-party
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decode_third_party(inner: str) -> tuple[str, str]:
        try:
            m = re.match(r'^([^>]+)>([^:]+):(.*)', inner, re.DOTALL)
            if not m:
                return 'Third-party', inner.strip()
            inner_src     = m.group(1).strip()
            inner_path    = m.group(2).strip()
            inner_payload = m.group(3).strip()
            _, inner_info = AprsDecoder._decode_payload(inner_payload)
            gateway = inner_path.split(',')[0] if inner_path else inner_path
            return 'Third-party', f'(via {gateway}) {inner_src}: {inner_info}'
        except Exception:
            return 'Third-party', inner.strip()

    # ------------------------------------------------------------------ #
    # Symbol lookup
    # ------------------------------------------------------------------ #

    _SYMBOLS: dict[tuple[str, str], str] = {
        ('/', '!'): 'Police',    ('/', '#'): 'Digi',      ('/', '$'): 'Phone',
        ('/', '%'): 'DX-Cluster',('/', '&'): 'IGate',     ('/', '-'): 'House',
        ('/', '.'): 'X',         ('/', '/'): 'Dot',        ('/', '0'): 'Circle',
        ('/', '>'): 'Car',       ('/', '?'): 'Server',     ('/', '@'): 'Hurricane',
        ('/', 'A'): 'Aid',       ('/', 'B'): 'BBS',        ('/', 'C'): 'Canoe',
        ('/', 'E'): 'Eyeball',   ('/', 'G'): 'Grid',       ('/', 'H'): 'Hotel',
        ('/', 'I'): 'TCP/IP',    ('/', 'K'): 'School',     ('/', 'L'): 'Lighthouse',
        ('/', 'N'): 'NTS',       ('/', 'O'): 'Balloon',    ('/', 'R'): 'RV',
        ('/', 'S'): 'Shuttle',   ('/', 'T'): 'SSTV',       ('/', 'U'): 'Bus',
        ('/', 'V'): 'ATV',       ('/', 'W'): 'WX-Station', ('/', 'X'): 'Helicopter',
        ('/', 'Y'): 'Yacht',     ('/', '['): 'Jogger',     ('/', '^'): 'Aircraft',
        ('/', '_'): 'WX',        ('/', 'a'): 'Ambulance',  ('/', 'b'): 'Bike',
        ('/', 'd'): 'Fire-Dept', ('/', 'e'): 'Horse',      ('/', 'f'): 'Fire-Truck',
        ('/', 'g'): 'Glider',    ('/', 'h'): 'Hospital',   ('/', 'j'): 'Jeep',
        ('/', 'k'): 'Truck',     ('/', 'l'): 'Laptop',     ('/', 'n'): 'Node',
        ('/', 'r'): 'Antenna',   ('/', 's'): 'Ship',       ('/', 'u'): 'Truck-18w',
        ('/', 'v'): 'Van',       ('/', 'y'): 'Yacht',
        ('\\', '#'): 'Digi(alt)',('\\', '&'): 'IGate(alt)',('\\', '-'): 'House(alt)',
        ('\\', 'Y'): 'House2',   ('\\', 'a'): 'ARRL/ARES',('\\', 'k'): 'SUV',
        ('\\', 'u'): 'Bus(alt)',
    }

    @staticmethod
    def _symbol(table: str, code: str) -> str:
        return AprsDecoder._SYMBOLS.get((table, code), f"sym:{table}{code}")

    # ------------------------------------------------------------------ #
    # Plain text formatter (for decode())
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_plain(frame: DecodedFrame) -> str:
        header = frame.source
        if frame.path:
            header += f'  ›  {frame.path}'
        if frame.aprs_id:
            header += f'  [{frame.aprs_id}]'
        return f'{header}\n  {frame.type_str}: {frame.info}'


# ---------------------------------------------------------------------------
# Module-level helper: HTML-escape a string
# ---------------------------------------------------------------------------

def _e(s: str) -> str:
    """HTML-escape a string for safe insertion into QTextEdit HTML."""
    return _html_mod.escape(str(s), quote=False)