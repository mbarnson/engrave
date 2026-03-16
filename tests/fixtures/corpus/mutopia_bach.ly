\version "2.24.0"

\header {
  mutopiatitle = "Invention No. 1 in C Major"
  mutopiacomposer = "BachJS"
  mutopiaopus = "BWV 772"
  mutopiainstrument = "Piano"
  date = "1723"
  style = "Baroque"
  source = "Bach-Gesellschaft Ausgabe Band III"
  license = "Public Domain"
  title = "Invention No. 1 in C Major"
  composer = "Johann Sebastian Bach"
}

\score {
  \new Staff {
    \clef treble
    \key c \major
    \time 4/4
    \tempo "Allegro" 4 = 120

    % Bars 1-4: Opening subject
    c'8 d' e' f' g' a' b' c'' |
    d''8 c'' b' a' g' f' e' d' |
    c'4 e'8 d' c' d' e' f' |
    g'4 c'' b'8 a' g' f' |

    % Bars 5-8
    e'8 f' g' a' b' c'' d'' e'' |
    f''8 e'' d'' c'' b' a' g' f' |
    e'4 g'8 f' e' f' g' a' |
    b'4 e'' d''8 c'' b' a' |

    \mark \default
    % Bars 9-12: Development
    g'8 a' b' c'' d'' e'' f'' g'' |
    a''8 g'' f'' e'' d'' c'' b' a' |
    g'4 b'8 a' g' a' b' c'' |
    d''4 g'' f''8 e'' d'' c'' |

    % Bars 13-16: Recapitulation
    \key g \major
    b'8 c'' d'' e'' fis'' g'' a'' b'' |
    a''8 g'' fis'' e'' d'' c'' b' a' |
    g'4 b'8 a' g' a' b' c'' |
    g'2. r4 |
  }
  \layout { }
}
