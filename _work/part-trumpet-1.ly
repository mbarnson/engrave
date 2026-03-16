\version "2.24.0"


\include "music-definitions.ly"

\header {
  title = "Big Band"
  instrument = "Trumpet 1"
  tagline = ##f
}

\paper {
  #(set-paper-size "letter")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 15\mm
  right-margin = 12\mm
}

\bookOutputName "part-trumpet-1"

\score {
  \set Timing.beamExceptions = #'()
  \set Timing.baseMoment = #(ly:make-moment 1/4)
  \set Timing.beatStructure = 1,1,1,1
  <<
    \new Staff \with {
      instrumentName = "Trumpet 1"
      shortInstrumentName = "Tpt. 1"
    } {
      \compressMMRests { << \globalMusic \transpose c' d' \trumpetOne >> }
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
