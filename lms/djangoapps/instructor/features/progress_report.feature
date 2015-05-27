@shard_2
Feature: LMS.Instructor Dash Progress Report
    As an instructor or course staff,
    In order to manage my class
    I want to view and download data information about progress.

    Scenario: View modules progress
       Given I am "<Role>" for a course with problem & openassessment
       When I visit the "Progress Report" tab
       Then I see a progress summary
       Then wait for AJAX to finish
       Then I see a Progress Update

       Examples:
       | Role          |
       | instructor    |
       | staff         |

