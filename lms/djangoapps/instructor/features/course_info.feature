@shard_2
Feature: LMS.Instructor Dash Course Info
    As an admin or an instructor or course staff or beta tester,
    In order to manage my class
    I want to view course info.

    Scenario: View Course Info tab by user who is allowed to access it
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Course Info" tab
       Examples:
       | Role          |
       | admin         |
       | instructor    |
       | staff         |
       | beta_tester   |
