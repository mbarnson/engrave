"""CoherenceState model for musical context passing between section generation calls.

Carries full musical context between LLM generation calls: key, time sig,
tempo, dynamics, articulation, voicing, rhythmic density, open ties, summaries.
Serializes to compact prompt text within token budget.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

# Maximum character length for the generated_summary field (~300 tokens at 4 chars/token)
_SUMMARY_CHAR_LIMIT = 1200


class CoherenceState(BaseModel):
    """Musical state passed between section generation calls.

    Carries full musical context (per user decision): key, time sig,
    tempo, dynamics, articulation style, voicing patterns, rhythmic density.
    """

    section_index: int = 0
    total_sections: int = 1

    # Structural
    key_signature: str = "c \\major"  # LilyPond key format
    time_signature: str = "4/4"
    tempo_bpm: int = 120

    # Musical character
    dynamic_levels: dict[str, str] = {}  # track_name -> current dynamic (pp, p, mp, mf, f, ff)
    articulation_style: str = ""  # e.g., "legato", "staccato", "marcato-heavy"
    rhythmic_density: str = "moderate"  # "sparse", "moderate", "dense"
    voicing_patterns: list[str] = []  # e.g., ["close voicing", "drop-2", "unison"]

    # Cross-section continuity
    open_ties: dict[str, list[str]] = {}  # track_name -> list of tied pitches
    last_bar_summary: str = ""  # Brief text summary of final bar
    generated_summary: str = ""  # Running summary of all generated content

    def to_prompt_text(self) -> str:
        """Serialize to compact, human-readable text for LLM prompt inclusion.

        Only includes non-empty/non-default fields to minimize token usage.
        """
        parts = [
            f"Section {self.section_index + 1} of {self.total_sections}",
            f"Key: {self.key_signature}, Time: {self.time_signature}, Tempo: {self.tempo_bpm} BPM",
        ]
        if self.dynamic_levels:
            dynamics = ", ".join(f"{k}: {v}" for k, v in self.dynamic_levels.items())
            parts.append(f"Current dynamics: {dynamics}")
        if self.articulation_style:
            parts.append(f"Articulation style: {self.articulation_style}")
        if self.rhythmic_density and self.rhythmic_density != "moderate":
            parts.append(f"Rhythmic density: {self.rhythmic_density}")
        if self.voicing_patterns:
            parts.append(f"Voicing: {', '.join(self.voicing_patterns)}")
        if self.open_ties:
            ties = ", ".join(f"{k}: {v}" for k, v in self.open_ties.items())
            parts.append(f"Open ties from previous section: {ties}")
        if self.last_bar_summary:
            parts.append(f"Last bar: {self.last_bar_summary}")
        if self.generated_summary:
            parts.append(f"Previously generated: {self.generated_summary}")
        return "\n".join(parts)

    def update_from_section(
        self,
        section_ly: str,
        section_midi_text: str,
    ) -> CoherenceState:
        """Create updated state from generated LilyPond output.

        Increments section_index, detects open ties (notes ending with ~),
        updates dynamic_levels from last dynamic marking, and appends to
        generated_summary with truncation.

        Args:
            section_ly: The generated LilyPond source for this section.
            section_midi_text: The MIDI text that was in the prompt.

        Returns:
            A new CoherenceState with updated fields.
        """
        # Detect open ties: notes followed by ~ at section end
        new_ties: dict[str, list[str]] = {}
        tie_pattern = re.compile(r"([a-g](?:is|es|isis|eses)?(?:[',]*))~")
        matches = tie_pattern.findall(section_ly)
        if matches:
            # Group under "section" key since we don't have per-track info from raw LilyPond
            new_ties["section"] = list(set(matches))

        # Detect last dynamic marking per track
        new_dynamics = dict(self.dynamic_levels)
        dynamic_pattern = re.compile(r"\\(ppp|pp|p|mp|mf|f|ff|fff)")
        dyn_matches = dynamic_pattern.findall(section_ly)
        if dyn_matches:
            # Use the last dynamic found
            new_dynamics["section"] = dyn_matches[-1]

        # Build summary addition (brief description of this section)
        section_desc = f"Section {self.section_index + 1}: {section_midi_text[:100].strip()}"
        new_summary = self.generated_summary
        if new_summary:
            new_summary += "; " + section_desc
        else:
            new_summary = section_desc

        # Truncate summary if over char limit (simple truncation of oldest content)
        if len(new_summary) > _SUMMARY_CHAR_LIMIT:
            # Keep the most recent content, trim from the beginning
            new_summary = "..." + new_summary[-(_SUMMARY_CHAR_LIMIT - 3) :]

        # Extract last bar content as summary
        lines = section_ly.strip().split("\n")
        last_bar = lines[-1].strip() if lines else ""

        return CoherenceState(
            section_index=self.section_index + 1,
            total_sections=self.total_sections,
            key_signature=self.key_signature,
            time_signature=self.time_signature,
            tempo_bpm=self.tempo_bpm,
            dynamic_levels=new_dynamics,
            articulation_style=self.articulation_style,
            rhythmic_density=self.rhythmic_density,
            voicing_patterns=self.voicing_patterns,
            open_ties=new_ties,
            last_bar_summary=last_bar[:200] if last_bar else "",
            generated_summary=new_summary,
        )

    @classmethod
    def initial_from_analysis(cls, analysis: Any) -> CoherenceState:
        """Create initial coherence state from a MidiAnalysis-like object.

        The analysis object should have key_signature, time_signature,
        tempo_bpm, and total_sections attributes.

        Args:
            analysis: Object with musical analysis attributes.

        Returns:
            CoherenceState initialized from the analysis.
        """
        return cls(
            section_index=0,
            total_sections=getattr(analysis, "total_sections", 1),
            key_signature=getattr(analysis, "key_signature", "c \\major"),
            time_signature=getattr(analysis, "time_signature", "4/4"),
            tempo_bpm=getattr(analysis, "tempo_bpm", 120),
        )
