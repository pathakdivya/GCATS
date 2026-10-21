"""Setup pages, in the order the shell presents them."""

from .startup import StartupPage
from .participant import ParticipantPage
from .stimuli_page import StimuliPage
from .protocol import ProtocolPage
from .settings import SettingsPage
from .mapping import MappingPage
from .deadzone import DeadZonePage
from .verify import VerifyPage

# Each entry contains the page class, rail group, and displayed label.
SEQUENCE = [
    (StartupPage,     "setup",       "Startup"),
    (ParticipantPage, "setup",       "Participant"),
    (StimuliPage,     "setup",       "Stimuli"),
    (ProtocolPage,    "setup",       "Protocol"),
    (SettingsPage,    "setup",       "Configuration"),
    (MappingPage,     "calibration", "Controls"),
    (DeadZonePage,    "calibration", "Dead-zone"),
    (VerifyPage,      "calibration", "Check"),
]
