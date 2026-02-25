\version "2.24.4"


\include "music-definitions.ly"

\header {
  title = "Big Band"
  instrument = "Trumpet 3"
  tagline = ##f
}

\paper {
  #(set-paper-size "letter")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 15\mm
  right-margin = 12\mm
}

\bookOutputName "part-trumpet-3"

\score {
  \set Timing.beamExceptions = #'()
  \set Timing.baseMoment = #(ly:make-moment 1/4)
  \set Timing.beatStructure = 1,1,1,1
  <<
    \new Staff \with {
      instrumentName = "Trumpet 3"
      shortInstrumentName = "Tpt. 3"
    } {
      \compressMMRests { << \globalMusic \transpose c' d' \trumpetThree >> }
    }
  >>
\layout {
  \context {
    \Score
    \override BarNumber.break-visibility = ##(#f #f #t)
    barNumberVisibility = #first-bar-number-invisible
  }
}

}
