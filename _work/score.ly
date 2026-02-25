\version "2.24.4"


\include "music-definitions.ly"

\header {
  title = "Big Band"
  tagline = ##f
}

\paper {
  #(set-paper-size "tabloid" 'landscape)
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 15\mm
  right-margin = 10\mm
  system-system-spacing.basic-distance = #14
  score-system-spacing.basic-distance = #16
}

\bookOutputName "score"

\score {
  <<
  \set Timing.beamExceptions = #'()
  \set Timing.baseMoment = #(ly:make-moment 1/4)
  \set Timing.beatStructure = 1,1,1,1
    \new StaffGroup = "Saxophones" \with {
      systemStartDelimiter = #SystemStartBracket
    } <<
      \new Staff = "altoSaxOne" \with {
        instrumentName = "Alto Sax 1"
        shortInstrumentName = "A.Sx. 1"
      } {
        << \globalMusic \altoSaxOne >>
      }

      \new Staff = "altoSaxTwo" \with {
        instrumentName = "Alto Sax 2"
        shortInstrumentName = "A.Sx. 2"
      } {
        << \globalMusic \altoSaxTwo >>
      }

      \new Staff = "tenorSaxOne" \with {
        instrumentName = "Tenor Sax 1"
        shortInstrumentName = "T.Sx. 1"
      } {
        << \globalMusic \tenorSaxOne >>
      }

      \new Staff = "tenorSaxTwo" \with {
        instrumentName = "Tenor Sax 2"
        shortInstrumentName = "T.Sx. 2"
      } {
        << \globalMusic \tenorSaxTwo >>
      }

      \new Staff = "baritoneSax" \with {
        instrumentName = "Baritone Sax"
        shortInstrumentName = "B.Sx."
      } {
        << \globalMusic \baritoneSax >>
      }

    >>
    \new StaffGroup = "Trumpets" \with {
      systemStartDelimiter = #SystemStartBracket
    } <<
      \new Staff = "trumpetOne" \with {
        instrumentName = "Trumpet 1"
        shortInstrumentName = "Tpt. 1"
      } {
        << \globalMusic \trumpetOne >>
      }

      \new Staff = "trumpetTwo" \with {
        instrumentName = "Trumpet 2"
        shortInstrumentName = "Tpt. 2"
      } {
        << \globalMusic \trumpetTwo >>
      }

      \new Staff = "trumpetThree" \with {
        instrumentName = "Trumpet 3"
        shortInstrumentName = "Tpt. 3"
      } {
        << \globalMusic \trumpetThree >>
      }

      \new Staff = "trumpetFour" \with {
        instrumentName = "Trumpet 4"
        shortInstrumentName = "Tpt. 4"
      } {
        << \globalMusic \trumpetFour >>
      }

    >>
    \new StaffGroup = "Trombones" \with {
      systemStartDelimiter = #SystemStartBracket
    } <<
      \new Staff = "tromboneOne" \with {
        instrumentName = "Trombone 1"
        shortInstrumentName = "Tbn. 1"
      } {
          \clef bass
        << \globalMusic \tromboneOne >>
      }

      \new Staff = "tromboneTwo" \with {
        instrumentName = "Trombone 2"
        shortInstrumentName = "Tbn. 2"
      } {
          \clef bass
        << \globalMusic \tromboneTwo >>
      }

      \new Staff = "tromboneThree" \with {
        instrumentName = "Trombone 3"
        shortInstrumentName = "Tbn. 3"
      } {
          \clef bass
        << \globalMusic \tromboneThree >>
      }

      \new Staff = "bassTrombone" \with {
        instrumentName = "Bass Trombone"
        shortInstrumentName = "B.Tbn."
      } {
          \clef bass
        << \globalMusic \bassTrombone >>
      }

    >>
    \new StaffGroup = "Rhythm" \with {
      systemStartDelimiter = #SystemStartBrace
    } <<
      \new PianoStaff \with {
        instrumentName = "Piano"
        shortInstrumentName = "Pno."
      } <<
        \new Staff = "piano-upper" {
          \clef treble
          << \globalMusic \piano >>
        }
        \new Staff = "piano-lower" {
          \clef bass
          << \globalMusic \pianoLeft >>
        }
      >>

      \new Staff = "guitar" \with {
        instrumentName = "Guitar"
        shortInstrumentName = "Gtr."
      } {
        << \globalMusic \guitar >>
      }

      \new Staff = "bass" \with {
        instrumentName = "Bass"
        shortInstrumentName = "Bass"
      } {
          \clef bass
        << \globalMusic \bass >>
      }

      \new DrumStaff \with {
        instrumentName = "Drums"
        shortInstrumentName = "Dr."
      } {
        << \globalMusic \drums >>
      }

    >>
  >>
\layout {
  #(layout-set-staff-size 14)
  \context {
    \Staff
    \RemoveEmptyStaves
    \override VerticalAxisGroup.remove-first = ##f
  }
  \context {
    \StaffGroup
    \consists Keep_alive_together_engraver
  }
  \context {
    \Score
    \override BarNumber.break-visibility = ##(#f #f #t)
    barNumberVisibility = #first-bar-number-invisible
  }
}

  \midi { }
}
