@shard_2
Feature: LMS.Instructor Dash Membership
    As an admin,
    In order to manage my class
    I want to handle membership data.

    Scenario: View Membership tab by user who is not allowed to access
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Membership" tab
       Examples:
       | Role          | Extra Role                |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View Membership tab by user who is allowed to access
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Membership" tab
       Examples:
       | Role          |
       | admin         |
