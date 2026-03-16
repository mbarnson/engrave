\version "2.24.0"

\header {
  title = "Multi-Part Test Score"
  composer = "Test Composer"
}

\score {
  <<
    \new Staff \with {
      instrumentName = "Violin"
    } {
      \clef treble
      \key d \major
      \time 3/4

      % Bars 1-4
      d'4 fis' a' |
      b'4 a' g' |
      fis'4 e' d' |
      a'2. |

      % Bar 5 - Double barline boundary
      \bar "||"
      d''4 cis'' b' |
      a'4 g' fis' |
      e'4 d' cis' |
      d'2. |

      % Bars 9-12
      fis'4 a' d'' |
      cis''4 b' a' |
      g'4 fis' e' |
      d'2. |
    }

    \new Staff \with {
      instrumentName = "Cello"
    } {
      \clef bass
      \key d \major
      \time 3/4

      % Bars 1-4
      d4 a, d |
      g,4 a, b, |
      d4 cis b, |
      a,2. |

      % Bar 5 - Double barline boundary
      \bar "||"
      d4 e fis |
      a4 g fis |
      e4 d cis |
      d2. |

      % Bars 9-12
      d4 fis a |
      a4 g fis |
      e4 d cis |
      d2. |
    }
  >>
  \layout { }
}
