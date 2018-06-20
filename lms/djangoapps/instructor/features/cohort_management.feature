@shard_2
Feature: LMS.Instructor Dash Cohorts
    As an admin,
    In order to manage my class
    I want to handle cohort data.

    Scenario: View Cohorts tab by user who is not allowed to access
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Cohorts" tab
       Examples:
       | Role          | Extra Role                |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View Cohorts tab by user who is allowed to access
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Cohorts" tab
       Examples:
       | Role          |
       | admin         |
