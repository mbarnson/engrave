"""Shared test fixtures for Engrave."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

if TYPE_CHECKING:
    from engrave.config.settings import Settings


MINIMAL_TOML = """\
[providers.vllm_mlx]
api_base = "http://localhost:8000/v1"

[roles.compile_fixer]
model = "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
max_tokens = 4096
tags = ["code"]

[roles.generator]
model = "hosted_vllm/mlx-community/Qwen3-Coder-30B-A3B-8bit"
max_tokens = 8192
tags = ["code", "lilypond"]

[roles.describer]
model = "anthropic/claude-sonnet-4-20250514"
max_tokens = 2048
tags = ["audio", "description"]

[lilypond]
min_version = "2.24"
compile_timeout = 60
max_fix_attempts = 5
context_lines = 20

[pipeline]
max_concurrent_groups = 8

[corpus]
embedding_model = "nomic-embed-text"
db_path = "data/corpus_db"
collection_name = "lilypond_phrases"

[audio]
target_sample_rate = 44100
target_channels = 1
max_duration_seconds = 900
supported_formats = ["mp3", "wav", "aiff", "flac"]
"""


def _make_settings_class(toml_path: str) -> type:
    """Create a Settings subclass that loads from a specific TOML path."""
    from engrave.config.settings import Settings

    class TestSettings(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
            **kwargs: Any,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            toml_settings = TomlConfigSettingsSource(settings_cls, toml_file=toml_path)
            return (
                init_settings,
                env_settings,
                dotenv_settings,
                toml_settings,
                file_secret_settings,
            )

    return TestSettings


@pytest.fixture
def tmp_engrave_toml(tmp_path: Path) -> Path:
    """Write a minimal engrave.toml to tmp_path and return its path."""
    toml_path = tmp_path / "engrave.toml"
    toml_path.write_text(MINIMAL_TOML)
    return toml_path


@pytest.fixture
def settings(tmp_engrave_toml: Path) -> Settings:
    """Load Settings from the tmp engrave.toml."""
    cls = _make_settings_class(str(tmp_engrave_toml))
    return cls(_env_file=None)


@pytest.fixture
def mock_acompletion():
    """Patch litellm.acompletion and return the mock."""
    mock = AsyncMock()
    # Default: return a simple completion response
    mock.return_value.choices = [AsyncMock(message=AsyncMock(content="Test response"))]
    with patch("litellm.acompletion", mock):
        yield mock


@pytest.fixture
def mock_compiler():
    """Mock LilyPondCompiler with configurable compile() responses.

    Default: returns a successful compilation result.
    Override compile.return_value or compile.side_effect in tests.
    """
    from engrave.lilypond.compiler import RawCompileResult

    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


@pytest.fixture
def mock_router():
    """Mock InferenceRouter with configurable complete() responses.

    Default: returns a simple fixed LilyPond source.
    Override complete.return_value or complete.side_effect in tests.
    """
    router = AsyncMock()
    router.complete.return_value = '\\version "2.24.4"\n\\relative c\' { c4 d e f | g2 g | }\n'
    return router


# ---------------------------------------------------------------------------
# Audio fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    """Create a minimal valid WAV file (1 second, 44.1kHz, mono, 440Hz sine).

    Uses the ``wave`` stdlib module -- no pydub dependency.
    """
    path = tmp_path / "sample.wav"
    sample_rate = 44100
    duration_s = 1.0
    frequency = 440.0
    n_frames = int(sample_rate * duration_s)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return path


# ---------------------------------------------------------------------------
# Corpus fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def corpus_config(tmp_path: Path):
    """Return a CorpusConfig pointing at a temp directory."""
    from engrave.config.settings import CorpusConfig

    return CorpusConfig(
        embedding_model="all-MiniLM-L6-v2",
        db_path=str(tmp_path / "test_corpus_db"),
        collection_name="test_phrases",
    )


@pytest.fixture
def corpus_store(corpus_config):
    """Return a CorpusStore backed by an in-memory ChromaDB client."""
    import chromadb

    from engrave.corpus.store import CorpusStore

    client = chromadb.Client()
    return CorpusStore(config=corpus_config, client=client)


# ---------------------------------------------------------------------------
# Ingestion pipeline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_lilypond_compiler(tmp_path: Path):
    """Mock LilyPondCompiler that produces a fake .midi file on success.

    Returns a successful RawCompileResult and writes a zero-byte .midi file
    to simulate LilyPond producing MIDI output.
    """
    from engrave.lilypond.compiler import RawCompileResult

    pdf_path = tmp_path / "out.pdf"
    midi_path = tmp_path / "out.midi"

    def fake_compile(source: str, output_dir: Path | None = None):
        # Write fake outputs
        pdf_path.write_text("fake pdf")
        midi_path.write_bytes(b"")
        return RawCompileResult(
            success=True,
            returncode=0,
            stdout="",
            stderr="",
            output_path=pdf_path,
        )

    compiler = MagicMock()
    compiler.compile.side_effect = fake_compile
    return compiler


@pytest.fixture
def sample_mutopia_score() -> str:
    """Load the mutopia_bach.ly fixture file as a string."""
    fixture_path = Path(__file__).parent / "fixtures" / "corpus" / "mutopia_bach.ly"
    return fixture_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Populated corpus fixture (for retrieval integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_corpus_store(request, tmp_path: Path):
    """In-memory ChromaDB store pre-populated with ~10 diverse test chunks.

    Covers different instrument families (brass, keyboard, strings, woodwind),
    ensemble types (solo, big_band, chamber), and styles (Jazz, Baroque,
    Classical, Romantic).
    """
    import chromadb

    from engrave.config.settings import CorpusConfig
    from engrave.corpus.models import Chunk, ScoreMetadata
    from engrave.corpus.store import CorpusStore

    config = CorpusConfig(
        embedding_model="all-MiniLM-L6-v2",
        db_path=str(tmp_path / "test_retrieval_db"),
        collection_name=f"test_retrieval_{request.node.name}",
    )
    client = chromadb.Client()
    store = CorpusStore(config=config, client=client)

    chunks = [
        Chunk(
            id="brass-jazz-trumpet-1",
            source="\\relative c'' { c4\\f d8 e f4 g | a4. b8 c4 r | }",
            description="Bright brass trumpet line in big band jazz swing style with forte dynamics and syncopated eighth notes",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/trumpet_swing.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Allegro",
                instrument="Trumpet",
                instrument_family="brass",
                clef="treble",
                ensemble_type="big_band",
                style="Jazz",
                composer="Anonymous",
            ),
        ),
        Chunk(
            id="brass-jazz-trombone-1",
            source="\\relative c { c2 e4 g | bes4. a8 g4 f | }",
            description="Trombone bass line in big band jazz style with walking bass motion and flat seventh",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/trombone_swing.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Moderato",
                instrument="Trombone",
                instrument_family="brass",
                clef="bass",
                ensemble_type="big_band",
                style="Jazz",
                composer="Anonymous",
            ),
        ),
        Chunk(
            id="brass-classical-horn-1",
            source="\\relative c' { c4( d e f) | g2.\\p r4 | }",
            description="French horn melodic phrase in classical style with legato slur and piano dynamics",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/horn_classical.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Andante",
                instrument="French Horn",
                instrument_family="brass",
                clef="treble",
                ensemble_type="chamber",
                style="Classical",
                composer="Mozart",
            ),
        ),
        Chunk(
            id="keyboard-baroque-piano-1",
            source="\\relative c' { c16 d e f g a b c | d c b a g f e d | }",
            description="Keyboard running passage in baroque style with rapid sixteenth note scales ascending and descending",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/bach_invention.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Allegro",
                instrument="Piano",
                instrument_family="keyboard",
                clef="treble",
                ensemble_type="solo",
                style="Baroque",
                composer="J.S. Bach",
            ),
        ),
        Chunk(
            id="keyboard-jazz-piano-1",
            source="\\relative c' { <c e g bes>4 <f a c e>4 <bes d f a>2 | }",
            description="Jazz piano chord voicings with dominant seventh and extended chords in comping style",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/jazz_piano.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=1,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Medium Swing",
                instrument="Piano",
                instrument_family="keyboard",
                clef="treble",
                ensemble_type="big_band",
                style="Jazz",
                composer="Anonymous",
                has_chord_symbols=True,
            ),
        ),
        Chunk(
            id="strings-baroque-violin-1",
            source="\\relative c'' { g8 a b c d4 b | c8 b a g fis4 d | }",
            description="Baroque violin passage with sequential eighth note motion and ornamental turns",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/bach_violin.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="G major",
                time_signature="4/4",
                tempo="Vivace",
                instrument="Violin",
                instrument_family="strings",
                clef="treble",
                ensemble_type="solo",
                style="Baroque",
                composer="J.S. Bach",
            ),
        ),
        Chunk(
            id="strings-romantic-cello-1",
            source="\\relative c { c4(\\pp d e f) | g2(\\< a) | bes1\\ff | }",
            description="Romantic cello melody with wide dynamic range from pianissimo to fortissimo with crescendo hairpin",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/romantic_cello.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=3,
                chunk_type="single_instrument",
                key_signature="C minor",
                time_signature="4/4",
                tempo="Adagio",
                instrument="Cello",
                instrument_family="strings",
                clef="bass",
                ensemble_type="chamber",
                style="Romantic",
                composer="Dvorak",
            ),
        ),
        Chunk(
            id="woodwind-classical-flute-1",
            source="\\relative c'' { c4 d8 e f4 g | a8 g f e d4 c | }",
            description="Classical flute melody with stepwise motion and gentle ornamental grace notes",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/classical_flute.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Allegretto",
                instrument="Flute",
                instrument_family="woodwind",
                clef="treble",
                ensemble_type="chamber",
                style="Classical",
                composer="Mozart",
            ),
        ),
        Chunk(
            id="woodwind-jazz-sax-1",
            source="\\relative c' { c8 d e g a4 c | bes8 a g f e4 d | }",
            description="Alto saxophone jazz improvisation line with bebop-style chromatic approach tones and swing phrasing",
            metadata=ScoreMetadata(
                source_collection="mutopia",
                source_path="test/jazz_sax.ly",
                chunk_index=0,
                bar_start=1,
                bar_end=2,
                chunk_type="single_instrument",
                key_signature="C major",
                time_signature="4/4",
                tempo="Up Tempo",
                instrument="Alto Saxophone",
                instrument_family="woodwind",
                clef="treble",
                ensemble_type="big_band",
                style="Jazz",
                composer="Anonymous",
            ),
        ),
        Chunk(
            id="brass-jazz-trumpet-2",
            source="\\relative c'' { r4 d8\\f e f g a4 | bes2 r2 | }",
            description="Trumpet lead line in swing big band arrangement with pickup notes and forte attack",
            metadata=ScoreMetadata(
                source_collection="pdmx",
                source_path="test/trumpet_lead.ly",
                chunk_index=1,
                bar_start=5,
                bar_end=6,
                chunk_type="single_instrument",
                key_signature="Bb major",
                time_signature="4/4",
                tempo="Bright Swing",
                instrument="Trumpet",
                instrument_family="brass",
                clef="treble",
                ensemble_type="big_band",
                style="Jazz",
                composer="Anonymous",
            ),
        ),
    ]

    store.add_chunks(chunks)
    return store


# ---------------------------------------------------------------------------
# Generation pipeline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rag_retriever():
    """Return a callable that always returns 3 hardcoded LilyPond example strings."""

    def _retriever(query: str, limit: int = 3) -> list[str]:
        examples = [
            "c'4 d'4 e'4 f'4 | g'2 g'2 |",
            "c4 e4 g4 c'4 | e'2 c'2 |",
            "g4 a4 b4 c'4 | d'2. r4 |",
        ]
        return examples[:limit]

    return _retriever


@pytest.fixture
def sample_midi_type0(tmp_path: Path) -> Path:
    """Create a simple type 0 MIDI file programmatically, return path."""
    import mido

    path = tmp_path / "test_type0.mid"
    mid = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(mido.Message("program_change", channel=0, program=0, time=0))
    track.append(mido.Message("program_change", channel=1, program=32, time=0))

    # Piano (ch0): 8 quarter notes
    for i in range(8):
        pitch = 60 + (i % 4)
        track.append(
            mido.Message("note_on", channel=0, note=pitch, velocity=80, time=0 if i == 0 else 30)
        )
        track.append(mido.Message("note_off", channel=0, note=pitch, velocity=0, time=450))

    # Bass (ch1): 2 whole notes
    for i in range(2):
        pitch = 36 + (i * 5)
        start_offset = i * 1920
        track.append(
            mido.Message(
                "note_on",
                channel=1,
                note=pitch,
                velocity=70,
                time=start_offset if i == 0 else 1920 - 450 + 30,
            )
        )
        track.append(mido.Message("note_off", channel=1, note=pitch, velocity=0, time=1800))

    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(str(path))
    return path


@pytest.fixture
def sample_midi_type1(tmp_path: Path) -> Path:
    """Create a simple type 1 MIDI file programmatically, return path."""
    import mido

    path = tmp_path / "test_type1.mid"
    mid = mido.MidiFile(type=1, ticks_per_beat=480)

    # Conductor track
    conductor = mido.MidiTrack()
    mid.tracks.append(conductor)
    conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("end_of_track", time=0))

    # Piano track
    piano = mido.MidiTrack()
    mid.tracks.append(piano)
    piano.append(mido.MetaMessage("track_name", name="Piano", time=0))
    piano.append(mido.Message("program_change", channel=0, program=0, time=0))
    for i in range(8):
        pitch = 60 + (i % 4)
        piano.append(
            mido.Message("note_on", channel=0, note=pitch, velocity=80, time=0 if i == 0 else 30)
        )
        piano.append(mido.Message("note_off", channel=0, note=pitch, velocity=0, time=450))
    piano.append(mido.MetaMessage("end_of_track", time=0))

    # Bass track
    bass = mido.MidiTrack()
    mid.tracks.append(bass)
    bass.append(mido.MetaMessage("track_name", name="Bass", time=0))
    bass.append(mido.Message("program_change", channel=1, program=32, time=0))
    for i in range(4):
        pitch = 36 + (i * 2)
        bass.append(
            mido.Message("note_on", channel=1, note=pitch, velocity=70, time=0 if i == 0 else 60)
        )
        bass.append(mido.Message("note_off", channel=1, note=pitch, velocity=0, time=900))
    bass.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(str(path))
    return path


@pytest.fixture
def mock_generator_router():
    """Mock InferenceRouter that returns formatted instrument blocks for parse_instrument_blocks().

    The response is formatted with ``% varName`` markers for parsing.
    """
    router = AsyncMock()

    def _generate_response(*args, **kwargs):
        """Return LilyPond music content formatted as instrument blocks."""
        messages = kwargs.get("messages", args[0] if args else [])
        # Extract prompt to determine instrument variable names
        prompt = ""
        if messages:
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")

        # Parse variable names from the template in the prompt
        import re

        var_pattern = re.compile(r"^([a-zA-Z]\w*)\s*=\s*\{", re.MULTILINE)
        var_names = var_pattern.findall(prompt)

        if not var_names:
            var_names = ["piano", "bass"]

        # Build response with instrument blocks
        blocks = []
        for var_name in var_names:
            blocks.append(f"% {var_name}\nc'4 d'4 e'4 f'4 | g'2 g'2 |")

        return "\n\n".join(blocks)

    router.complete.side_effect = _generate_response
    return router


@pytest.fixture
def mock_compiler_success():
    """Mock LilyPondCompiler that always returns compilation success."""
    from engrave.lilypond.compiler import RawCompileResult

    compiler = MagicMock()
    compiler.compile.return_value = RawCompileResult(
        success=True,
        returncode=0,
        stdout="",
        stderr="",
        output_path=Path("/tmp/out.pdf"),
    )
    return compiler


# ---------------------------------------------------------------------------
# Audio pipeline mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_normalizer():
    """Patch normalize_audio to copy input to output (no pydub dependency).

    The mock copies the source file content to the output path so downstream
    stages see a real file on disk.
    """
    import shutil

    def _fake_normalize(
        input_path: Path,
        output_path: Path,
        target_sr: int = 44100,
        channels: int = 1,
        max_duration_seconds: int = 900,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(input_path), str(output_path))
        return output_path

    with patch("engrave.audio.pipeline.normalize_audio", side_effect=_fake_normalize) as m:
        yield m


@pytest.fixture
def mock_separator(tmp_path: Path):
    """Patch run_separation to return fake StemOutput objects with WAV files.

    Creates minimal WAV files in the job's separation directory so
    downstream transcription can reference real paths.
    """
    from engrave.audio.separator import StemOutput

    def _fake_separation(
        audio_path: Path,
        steps: list,
        output_dir: Path,
    ) -> list[StemOutput]:
        output_dir.mkdir(parents=True, exist_ok=True)
        step_dir = output_dir / "step-00_mock"
        step_dir.mkdir(parents=True, exist_ok=True)

        stems = []
        for stem_name in ("drums", "bass", "vocals", "other"):
            wav_path = step_dir / f"{stem_name}.wav"
            # Write a minimal valid WAV (44 bytes header, no audio data)
            _write_minimal_wav(wav_path)
            stems.append(
                StemOutput(
                    stem_name=stem_name,
                    path=wav_path,
                    model_used="mock_model",
                    step_index=0,
                )
            )
        return stems

    with patch("engrave.audio.pipeline.run_separation", side_effect=_fake_separation) as m:
        yield m


@pytest.fixture
def mock_transcriber(tmp_path: Path):
    """Return a MagicMock satisfying the Transcriber protocol.

    transcribe() writes a minimal valid MIDI file (via pretty_midi) to the
    output directory and returns the path.
    """
    import pretty_midi

    transcriber = MagicMock()

    def _fake_transcribe(wav_path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        midi_path = output_dir / f"{wav_path.stem}.mid"
        # Create a minimal MIDI with one note
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        note = pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=1.0)
        instrument.notes.append(note)
        pm.instruments.append(instrument)
        pm.write(str(midi_path))
        return midi_path

    transcriber.transcribe = MagicMock(side_effect=_fake_transcribe)
    return transcriber


def _write_minimal_wav(path: Path) -> None:
    """Write a minimal valid WAV file (1-second, 44.1kHz, mono, silence)."""
    sample_rate = 44100
    n_frames = sample_rate  # 1 second
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
