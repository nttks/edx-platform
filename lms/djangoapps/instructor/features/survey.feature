@shard_2
Feature: LMS.Instructor Dash Survey
    As an admin or an instructor or course staff or beta tester,
    In order to manage my class
    I want to download survey data.

    Scenario: View Survey tab by user who is allowed to access it
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Survey" tab
       Examples:
       | Role          | Extra Role                |
       | admin         |                           |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View Survey tab by user who is not allowed to access it
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Survey" tab
       Examples:
       | Role          |
       | instructor    |
       | staff         |
       | beta_tester   |
