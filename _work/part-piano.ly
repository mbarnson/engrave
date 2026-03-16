\version "2.24.0"


\include "music-definitions.ly"

\header {
  title = "Big Band"
  instrument = "Piano"
  tagline = ##f
}

\paper {
  #(set-paper-size "letter")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 15\mm
  right-margin = 12\mm
}

\bookOutputName "part-piano"

\score {
  \set Timing.beamExceptions = #'()
  \set Timing.baseMoment = #(ly:make-moment 1/4)
  \set Timing.beatStructure = 1,1,1,1
  <<
    \new PianoStaff \with {
      instrumentName = "Piano"
      shortInstrumentName = "Pno."
    } <<
      \new Staff = "piano-upper" {
        \clef treble
        \compressMMRests { << \globalMusic \piano >> }
      }
      \new Staff = "piano-lower" {
        \clef bass
        \compressMMRests { << \globalMusic \pianoLeft >> }
      }
    >>
  >>
\layout {
  \context {
    \Score
    \override BarNumber.break-visibility = ##(#f #f #t)
    barNumberVisibility = #first-bar-number-invisible
  }
}

}
