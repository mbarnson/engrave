\version "2.24.0"

\header {
  title = "Repeat Test Score"
  composer = "Test Composer"
}

\score {
  \new Staff {
    \clef treble
    \key f \major
    \time 4/4
    \tempo "Moderato" 4 = 100

    % Bars 1-2: pre-repeat
    f'4 g' a' bes' |
    c''2 a'2 |

    % Bars 3-6: repeated section (volta 2)
    \repeat volta 2 {
      f'4 a' c'' f'' |
      e''4 d'' c'' bes' |
    }
    \alternative {
      { a'4 g' f' e' | d'2 c'2 | }
      { a'4 bes' c'' d'' | f''2. r4 | }
    }
  }
  \layout { }
}
