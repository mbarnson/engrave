\version "2.24.4"

\header {
  title = "Simple Test Score"
  composer = "Test Composer"
}

\score {
  \new Staff {
    \clef treble
    \key c \major
    \time 4/4
    \tempo "Allegro" 4 = 120

    % Bars 1-4
    c'4 d' e' f' |
    g'2 a'2 |
    b'4 c'' d'' e'' |
    f''2 g''2 |

    % Bars 5-8
    c'4 e' g' c'' |
    d'4 f' a' d'' |
    e'4 g' b' e'' |
    f'4 a' c'' f'' |

    % Bar 9 - Rehearsal mark boundary
    \mark \default
    g'4 a' b' c'' |
    d''4 e'' f'' g'' |
    a'4 b' c'' d'' |
    e'4 f' g' a' |

    % Bar 13 - Key change boundary
    \key g \major
    g'4 a' b' c'' |
    d''4 e'' fis'' g'' |
    a'4 b' c'' d'' |
    g'2. r4 |
  }
  \layout { }
}
