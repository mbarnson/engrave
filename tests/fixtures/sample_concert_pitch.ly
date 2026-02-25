\version "2.24.4"

% Minimal concert-pitch music variables for testing generators.
% All content is in concert pitch -- transposition applied at render time.

globalMusic = {
  \key bes \major
  \time 4/4
  \tempo "Medium Swing" 4 = 140

  % Intro
  s1*4

  \mark \default  % A
  s1*8

  \mark \default  % B
  s1*8

  \mark \default  % C
  s1*8
}

chordSymbols = \chordmode {
  bes1:maj7 | ees:7 | bes:maj7 | f:7 |
  bes:maj7 | ees:7 | bes:maj7 | f:7 |
  ees:maj7 | aes:7 | ees:maj7 | bes:7 |
  ees:maj7 | aes:7 | ees:maj7 | bes:7 |
}

altoSaxOne = \relative c'' {
  \key bes \major
  r1 | r1 | r1 | r1 |
  bes4 c d ees | f2 d | bes4 c d f | ees2. r4 |
  bes4\mf c d ees | f2 d | bes4 c d f | ees1 |
  r1 | r1 | r1 | r1 |
  bes4\f c d ees | f2 g | a4 bes c d | ees1 |
  r1 | r1 | r1 | r1 |
  bes4 a g f | ees2 d | c4 bes a g | f1 |
}

trumpetOne = \relative c' {
  \key bes \major
  r1 | r1 | r1 | r1 |
  d4\f ees f g | a2 f | d4 ees f a | g2. r4 |
  d4 ees f g | a2 f | d4 ees f a | g1 |
  r1 | r1 | r1 | r1 |
  d4\ff ees f g | a2 bes | c4 d ees f | g1 |
  r1 | r1 | r1 | r1 |
  d4 c bes a | g2 f | ees4 d c bes | a1 |
}

guitar = \relative c' {
  \key bes \major
  % Rhythm slashes / comp
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
  bes4 bes bes bes | bes4 bes bes bes |
}
