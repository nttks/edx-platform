@shard_2
Feature: LMS.Instructor Dash Data Download
    As an admin or an instructor or course staff or beta tester,
    In order to manage my class
    I want to view and download data information about my students.

    ### todos when more time can be spent on instructor dashboard
    #Scenario: Download profile information as a CSV
    #Scenario: Download student anonymized IDs as a CSV
    ## Need to figure out how to assert csvs will download without actually downloading them

    Scenario: View Data Download tab by user who is allowed to extract personal data
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I visit the instructor dashboard
       Then I see a "Data Download" tab
       Examples:
       | Role          | Extra Role                |
       | admin         |                           |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View Data Download tab by user who is not allowed to extract personal data
       Given I am "<Role>" for a course
       When I visit the instructor dashboard
       Then I do not see a "Data Download" tab
       Examples:
       | Role          |
       | instructor    |
       | staff         |
       | beta_tester   |

    Scenario: List enrolled students' profile information
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I click "List enrolled students' profile information"
       Then I see a table of student profiles
       Examples:
       | Role          | Extra Role                |
       | admin         |                           |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: View the grading configuration
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I click "Grading Configuration"
       Then I see the grading configuration for the course
       Examples:
       | Role          | Extra Role                |
       | admin         |                           |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: Generate & download a grade report by user who is allowed to execute
       Given I am "<Role>" for a course
       When I click "Generate Grade Report"
       Then I see a grade report csv file in the reports table
       Examples:
       | Role          |
       | admin         |

    Scenario: Generate & download a grade report by user who is not allowed to execute
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I do not see "Generate Grade Report" button
       Examples:
       | Role          | Extra Role                |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |

    Scenario: Generate & download a student profile report
       Given I am "<Role>" for a course
       And I am given extra "<Extra Role>" for a course
       When I click "Download profile information as a CSV"
       Then I see a student profile csv file in the reports table
       Examples:
       | Role          | Extra Role                |
       | admin         |                           |
       | instructor    | ga_extract_data_authority |
       | staff         | ga_extract_data_authority |
       | beta_tester   | ga_extract_data_authority |
