@shard_2
Feature: LMS.Instructor Dash Survey
    As an admin or an instructor or course staff,
    In order to manage my class
    I want to download survey data.

    Scenario: View Survey tab by user who is allowed to access it
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Survey" tab
       Examples:
       | Role          |
       | admin         |
       | instructor    |
       | staff         |
