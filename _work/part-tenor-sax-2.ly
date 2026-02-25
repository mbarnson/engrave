\version "2.24.4"


\include "music-definitions.ly"

\header {
  title = "Big Band"
  instrument = "Tenor Sax 2"
  tagline = ##f
}

\paper {
  #(set-paper-size "letter")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 15\mm
  right-margin = 12\mm
}

\bookOutputName "part-tenor-sax-2"

\score {
  \set Timing.beamExceptions = #'()
  \set Timing.baseMoment = #(ly:make-moment 1/4)
  \set Timing.beatStructure = 1,1,1,1
  <<
    \new Staff \with {
      instrumentName = "Tenor Sax 2"
      shortInstrumentName = "T.Sx. 2"
    } {
      \compressMMRests { << \globalMusic \transpose c' d' \tenorSaxTwo >> }
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
