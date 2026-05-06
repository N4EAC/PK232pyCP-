"""pk232py.ui.screens – Opmode screen widgets.

Each module provides one QWidget subclass implementing one operating
mode screen.  All screens are embedded in MainWindow via QStackedWidget
and switched by ModeManager.

Available screens
-----------------
BaudotScreen      – Baudot / ITA-2 RTTY
AsciiScreen       – ASCII RTTY
AmtorScreen       – AMTOR (ARQ / FEC / SELFEC)
MorseScreen       – CW / Morse
NavtexScreen      – NAVTEX receive
SignalScreen      – Signal / SIAM analysis
FaxScreen         – HF-FAX / WEFAX receive
PactorScreen      – PACTOR I (ARQ + FEC/Unproto)
HFPacketScreen    – HF Packet (AX.25, 300 Bd)
VHFPacketScreen   – VHF Packet (AX.25, 1200 Bd)
"""

from .baudot_screen  import BaudotScreen
from .ascii_screen   import AsciiScreen
from .amtor_screen   import AmtorScreen
from .morse_screen   import MorseScreen
from .navtex_screen  import NavtexScreen
from .signal_screen  import SignalScreen
from .fax_screen     import FaxScreen
from .pactor_screen  import PactorScreen
from .packet_screen  import HFPacketScreen, VHFPacketScreen

__all__ = [
    "BaudotScreen",
    "AsciiScreen",
    "AmtorScreen",
    "MorseScreen",
    "NavtexScreen",
    "SignalScreen",
    "FaxScreen",
    "PactorScreen",
    "HFPacketScreen",
    "VHFPacketScreen",
]