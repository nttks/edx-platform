###
Progress Report
###

# A typical section object.
# constructed with $section, a jquery object
# which holds the section body container.
std_ajax_err = -> window.InstructorDashboard.util.std_ajax_err.apply this, arguments

class ProgressReport 
  constructor: (@$section) ->
    # attach self to html so that instructor_dashboard.coffee can find
    #  this object to call event handlers like 'onClickTitle'
    @$section.data 'wrapper', @

    # gather elements
    #@$progress_grid_div = @$section.find("#ProgressGrid")
    #@$pgreport_request_response       = @$section.find '.request-response'
    #@$pgreport_request_response_error = @$section.find '.request-response-error'

  loadData: ->
    #@clear_display()
    #url = @$progress_grid_div.data 'endpoint-problems'
    #console.log(url);

    #problem_list_url = "${section_data['problem_list_url']}";
    #submission_scores_url = "${section_data['submission_scores_url']}";
    #openassessment_rubric_scores_url = "${section_data['openassessment_rubric_scores_url']}";

    #$.ajax
      #dataType: 'json'
      #url: url
      #error: std_ajax_err =>
        #@clear_display()
        #@$pgreport_request_response_error.text gettext("Error: Data load. Please try again.")
        #$(".msg-error").css({"display":"block"})
      #success: (data) =>
        #@clear_display()
        #setGrid(data);
        #@$pgreport_request_response.text data['status']
        #$(".msg-confirm").css({"display":"block"})

  clear_display: ->
    #@$pgreport_request_response.empty()
    #@$pgreport_request_response_error.empty()
    #$(".msg-confirm").css({"display":"none"})
    #$(".msg-error").css({"display":"none"})

  onClickTitle: ->
    #@loadData()

  onExit: ->

# export for use
# create parent namespaces if they do not already exist.
_.defaults window, InstructorDashboard: {}
_.defaults window.InstructorDashboard, sections: {}
_.defaults window.InstructorDashboard.sections,
  ProgressReport: ProgressReport
