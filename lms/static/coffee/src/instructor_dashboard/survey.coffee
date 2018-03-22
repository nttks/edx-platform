###
Survey Section

imports from other modules.
wrap in (-> ... apply) to defer evaluation
such that the value can be defined later than this assignment (file load order).
###


class SurveyDownload
  constructor: (@$section) ->
    # attach self to html so that instructor_dashboard.coffee can find
    #  this object to call event handlers like 'onClickTitle'
    @$section.data 'wrapper', @
    # gather elements
    @$list_survey_btn = @$section.find("input[name='list-survey']'")
    @$encoding_utf8_chkbox = @$section.find("input[id='encoding-utf8']'")

    # attach click handlers
    @$list_survey_btn.click (e) =>
      encoding_utf8 = @$encoding_utf8_chkbox.prop 'checked'
      if encoding_utf8
        saveInstructorSurveyEncodingUTF8.call @ , 'true'
        url = @$list_survey_btn.data 'endpointUtf8'
      else
        saveInstructorSurveyEncodingUTF8.call @ , 'false'
        url = @$list_survey_btn.data 'endpoint'
      downloadFileUsingPost url

  # handler for when the section title is clicked.
  onClickTitle: ->
    @$encoding_utf8_chkbox.prop 'checked' , getInstructorSurveyEncodingUTF8.call @

  saveInstructorSurveyEncodingUTF8 = (value)->
    if window.localStorage
      window.localStorage.setItem 'instructor.survey.encodingUTF8', value

  getInstructorSurveyEncodingUTF8 = ->
    if window.localStorage
      return window.localStorage.getItem('instructor.survey.encodingUTF8') == 'true'


# export for use
# create parent namespaces if they do not already exist.
_.defaults window, InstructorDashboard: {}
_.defaults window.InstructorDashboard, sections: {}
_.defaults window.InstructorDashboard.sections,
  SurveyDownload: SurveyDownload
