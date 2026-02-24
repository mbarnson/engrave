Feature: Compile-fix retry loop
  The system compiles LilyPond and fixes errors via LLM

  Scenario: Successful compilation of valid LilyPond
    Given a valid LilyPond source
    When I compile the source
    Then the compilation succeeds
    And no fix attempts were made

  Scenario: LLM fixes a broken LilyPond file within 5 attempts
    Given a LilyPond source with a syntax error
    And a mock LLM that returns the corrected source
    When I compile with the fix loop enabled
    Then the compilation succeeds
    And at most 5 fix attempts were made

  Scenario: Early exit on repeated error
    Given a LilyPond source with an unfixable error
    And a mock LLM that always returns the same broken code
    When I compile with the fix loop enabled
    Then the loop exits before 5 attempts
    And the diagnostics show a repeated error hash

  Scenario: Fail with diagnostics after max attempts
    Given a LilyPond source with a complex error
    And a mock LLM that returns different but still broken code each time
    When I compile with the fix loop enabled
    Then the compilation fails
    And 5 fix attempts were made
    And the diagnostics include the original error and all fix attempts
