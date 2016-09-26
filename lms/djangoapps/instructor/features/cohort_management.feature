@shard_2
Feature: LMS.Instructor Dash Cohorts
    As an admin,
    In order to manage my class
    I want to handle cohort data.

    Scenario: View Cohorts tab by user who is not allowed to access secret info
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Cohorts" tab
       Examples:
       | Role          |
       | instructor    |
       | staff         |

    Scenario: View Cohorts tab by user who is allowed to access secret info
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Cohorts" tab
       Examples:
       | Role          |
       | admin         |
