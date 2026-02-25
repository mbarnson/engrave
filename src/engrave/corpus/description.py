"""Structured text description templating for corpus chunks.

Generates natural language descriptions from extracted metadata for embedding
in ChromaDB. Descriptions are templated, not LLM-generated (user decision:
LLM music descriptions lack the detail needed for meaningful retrieval).
"""

from __future__ import annotations


def generate_description(metadata: dict) -> str:
    """Generate a structured natural language description from metadata.

    Templates a human-readable description suitable for embedding in a vector
    database. Omits fields that are None or empty. Format follows the user's
    decision for structured descriptions:

        "Key: C major. Time: 4/4. Tempo: Allegro. Instrument: Piano, treble clef.
         Bars 1-8. Note density: 12.5 notes/bar. Dynamic range: mf-f.
         Articulations: 3. Chord symbols: none. Composer: J.S. Bach.
         Era: Baroque. Ensemble: solo. Source: Mutopia."

    Args:
        metadata: Dict with extracted metadata fields. Expected keys:
            key_signature, time_signature, tempo, instrument, clef,
            bar_start, bar_end, note_density, dynamic_range,
            articulation_count, has_chord_symbols, composer, era,
            ensemble_type, source_collection.

    Returns:
        Natural language description string suitable for embedding.
    """
    parts: list[str] = []

    # Key signature
    key_sig = metadata.get("key_signature")
    if key_sig:
        parts.append(f"Key: {key_sig}.")

    # Time signature
    time_sig = metadata.get("time_signature")
    if time_sig:
        parts.append(f"Time: {time_sig}.")

    # Tempo
    tempo = metadata.get("tempo")
    if tempo:
        parts.append(f"Tempo: {tempo}.")

    # Instrument and clef
    instrument = metadata.get("instrument")
    clef = metadata.get("clef")
    if instrument and clef:
        parts.append(f"Instrument: {instrument}, {clef} clef.")
    elif instrument:
        parts.append(f"Instrument: {instrument}.")
    elif clef:
        parts.append(f"Clef: {clef}.")

    # Bar range (always present)
    bar_start = metadata.get("bar_start")
    bar_end = metadata.get("bar_end")
    if bar_start is not None and bar_end is not None:
        parts.append(f"Bars {bar_start}-{bar_end}.")

    # Note density
    note_density = metadata.get("note_density")
    if note_density is not None:
        parts.append(f"Note density: {note_density:.1f} notes/bar.")

    # Dynamic range
    dynamic_range = metadata.get("dynamic_range")
    if dynamic_range:
        parts.append(f"Dynamic range: {dynamic_range}.")

    # Articulation count
    articulation_count = metadata.get("articulation_count")
    if articulation_count:
        parts.append(f"Articulations: {articulation_count}.")

    # Chord symbols
    has_chords = metadata.get("has_chord_symbols")
    if has_chords is not None:
        parts.append(f"Chord symbols: {'yes' if has_chords else 'none'}.")

    # Composer
    composer = metadata.get("composer")
    if composer:
        parts.append(f"Composer: {composer}.")

    # Era
    era = metadata.get("era")
    if era:
        parts.append(f"Era: {era}.")

    # Ensemble type
    ensemble_type = metadata.get("ensemble_type")
    if ensemble_type:
        parts.append(f"Ensemble: {ensemble_type}.")

    # Source collection
    source = metadata.get("source_collection")
    if source:
        parts.append(f"Source: {source}.")

    return " ".join(parts)
