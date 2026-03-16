//! MIDI file analysis for track listing and instrument detection.
//!
//! Uses the `midly` crate to parse MIDI files and extract track information
//! including channel assignments, note counts, and instrument guesses from
//! program change events or track names.

use crate::MidiTrack;
use midly::{MidiMessage, Smf, TrackEventKind};
use std::collections::HashMap;

/// General MIDI program number to instrument name mapping (subset for common instruments).
fn gm_instrument_name(program: u8) -> &'static str {
    match program {
        0..=7 => "Piano",
        8..=15 => "Chromatic Percussion",
        16..=23 => "Organ",
        24..=31 => "Guitar",
        32..=39 => "Bass",
        40..=47 => "Strings",
        48..=55 => "Ensemble",
        56..=63 => "Brass",
        64..=71 => "Reed",
        72..=79 => "Pipe",
        80..=87 => "Synth Lead",
        88..=95 => "Synth Pad",
        96..=103 => "Synth Effects",
        104..=111 => "Ethnic",
        112..=119 => "Percussive",
        120..=127 => "Sound Effects",
        _ => "Unknown",
    }
}

/// More specific GM instrument names for the most common jazz/big-band instruments.
fn gm_specific_name(program: u8) -> &'static str {
    match program {
        0 => "Acoustic Grand Piano",
        24 => "Acoustic Guitar (nylon)",
        25 => "Acoustic Guitar (steel)",
        26 => "Electric Guitar (jazz)",
        27 => "Electric Guitar (clean)",
        32 => "Acoustic Bass",
        33 => "Electric Bass (finger)",
        34 => "Electric Bass (pick)",
        35 => "Fretless Bass",
        56 => "Trumpet",
        57 => "Trombone",
        58 => "Tuba",
        59 => "Muted Trumpet",
        60 => "French Horn",
        61 => "Brass Section",
        64 => "Soprano Sax",
        65 => "Alto Sax",
        66 => "Tenor Sax",
        67 => "Baritone Sax",
        68 => "Oboe",
        69 => "English Horn",
        70 => "Bassoon",
        71 => "Clarinet",
        73 => "Flute",
        _ => gm_instrument_name(program),
    }
}

pub fn analyze_midi(path: &str) -> Result<Vec<MidiTrack>, Box<dyn std::error::Error>> {
    let data = std::fs::read(path)?;
    let smf = Smf::parse(&data)?;

    let mut tracks = Vec::new();

    for (track_idx, track) in smf.tracks.iter().enumerate() {
        let mut note_count: usize = 0;
        let mut channels: HashMap<u8, usize> = HashMap::new();
        let mut track_name = String::new();
        let mut program: Option<u8> = None;

        for event in track {
            match event.kind {
                TrackEventKind::Meta(midly::MetaMessage::TrackName(name)) => {
                    track_name = String::from_utf8_lossy(name).to_string();
                }
                TrackEventKind::Midi { channel, message } => {
                    let ch = channel.as_int();
                    match message {
                        MidiMessage::NoteOn { vel, .. } if vel.as_int() > 0 => {
                            note_count += 1;
                            *channels.entry(ch).or_insert(0) += 1;
                        }
                        MidiMessage::ProgramChange { program: p } => {
                            program = Some(p.as_int());
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }

        // Skip empty tracks (tempo/meta-only)
        if note_count == 0 {
            continue;
        }

        // Pick the most-used channel
        let primary_channel = channels
            .iter()
            .max_by_key(|(_, &count)| count)
            .map(|(&ch, _)| ch)
            .unwrap_or(0);

        // Guess instrument from program change or track name
        let instrument_guess = if primary_channel == 9 {
            "Drums".to_string()
        } else if let Some(prog) = program {
            gm_specific_name(prog).to_string()
        } else if !track_name.is_empty() {
            track_name.clone()
        } else {
            format!("Track {}", track_idx + 1)
        };

        let name = if track_name.is_empty() {
            format!("Track {}", track_idx + 1)
        } else {
            track_name
        };

        tracks.push(MidiTrack {
            index: track_idx,
            name,
            channel: primary_channel,
            note_count,
            instrument_guess,
        });
    }

    Ok(tracks)
}
