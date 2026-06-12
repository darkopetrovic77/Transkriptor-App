"""Gemeinsame Datentypen und die abstrakte Engine-Schnittstelle.

Jede Transkriptions-Engine (lokal, Groq, OpenAI, ...) implementiert
`BaseEngine` und gibt ein `TranscriptResult` zurueck. So kann der Rest
der App (Backend, CLI) mit jeder Engine gleich arbeiten.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    """Ein Abschnitt des Transkripts mit Start-/Endzeit in Sekunden."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    """Ergebnis einer Transkription."""

    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = ""


class BaseEngine(ABC):
    """Abstrakte Basisklasse fuer alle Transkriptions-Engines."""

    @abstractmethod
    def transcribe(self, audio_path: str, language: str | None = None, model: str | None = None) -> TranscriptResult:
        """Transkribiert die Audiodatei unter `audio_path`.

        Args:
            audio_path: Pfad zur Audiodatei (mp3, wav, m4a, ...).
            language: Sprachcode (z.B. "de", "en") oder None fuer Auto-Erkennung.
            model: Engine-spezifischer Modellname (z.B. "small.en", "medium").

        Returns:
            TranscriptResult mit Volltext, Segmenten und erkannter Sprache.
        """
        raise NotImplementedError
