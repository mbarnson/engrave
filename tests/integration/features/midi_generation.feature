Feature: MIDI to LilyPond generation
  The system generates compilable LilyPond source from MIDI files

  Scenario: Generate LilyPond from a type 1 MIDI file
    Given a type 1 MIDI file with piano and bass tracks
    When the user runs the generation pipeline
    Then the output is a compilable LilyPond source file
    And the output contains variables for each instrument
    And all pitches are in concert pitch

  Scenario: Generation halts on unrecoverable compilation failure
    Given a type 1 MIDI file with piano track
    And the LilyPond compiler always fails
    When the user runs the generation pipeline
    Then generation halts with a failure report
    And a structured failure log file is created

  Scenario: MIDI without instrument metadata generates generic parts
    Given a MIDI file with no instrument metadata
    When the user runs the generation pipeline
    Then the output contains parts with generic names
    And a warning about missing metadata is logged
