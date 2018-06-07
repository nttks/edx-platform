@shard_2
Feature: LMS.Instructor Dash Student Admin
    As an admin,
    In order to manage my class
    I want to handle student data.

    Scenario: View Student Admin tab by user who is not allowed to access
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Student Admin" tab
       Examples:
       | Role          | Extra Role                |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View Student Admin tab by user who is allowed to access
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Student Admin" tab
       Examples:
       | Role          |
       | admin         |
