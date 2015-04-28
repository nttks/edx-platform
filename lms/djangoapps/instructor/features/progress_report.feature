@shard_2
Feature: LMS.Instructor Dash Progress Report
    As an instructor or course staff,
    In order to manage my class
    I want to view and download data information about progress.

    Scenario: View modules progress
       Given I am "<Role>" for a course
       When I visit the "Progress Report" tab
       Then I see a progress summary
       Examples:
       | Role          |
       | instructor    |
       | staff         |
