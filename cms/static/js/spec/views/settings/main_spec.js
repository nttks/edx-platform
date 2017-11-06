define([
    'jquery', 'js/models/settings/course_details', 'js/views/settings/main',
    'common/js/spec_helpers/ajax_helpers'
], function($, CourseDetailsModel, MainView, AjaxHelpers) {
    'use strict';

    var SELECTORS = {
        entrance_exam_min_score: '#entrance-exam-minimum-score-pct',
        entrance_exam_enabled_field: '#entrance-exam-enabled',
        grade_requirement_div: '.div-grade-requirements div'
    };

    describe('Settings/Main', function () {
        var urlRoot = '/course/settings/org/DemoX/Demo_Course',
            modelData = {
                start_date: "2014-10-05T00:00:00Z",
                end_date: "2014-11-05T20:00:00Z",
                enrollment_start: "2014-10-00T00:00:00Z",
                enrollment_end: "2014-11-05T00:00:00Z",
                deadline_start: "2014-11-05T10:00:00Z",
                terminate_start: "2014-12-05T00:00:00Z",
                org : '',
                course_id : '',
                run : '',
                syllabus : null,
                short_description : '',
                overview : '',
                intro_video : null,
                effort : null,
                course_image_name : '',
                course_image_asset_path : '',
                pre_requisite_courses : [],
                entrance_exam_enabled : '',
                entrance_exam_minimum_score_pct: '50',
                license: null,
                language: '',
                course_category: ['gacco'],
                is_f2f_course: true,
                is_f2f_course_sell: true,
                playback_rate_1x_only: false,
                course_canonical_name: 'Course_Canonical_Name',
                course_contents_provider: 'Course_Contents_Provider',
                teacher_name: 'Teacher_Name',
                course_span: 'Course_Span',
                individual_end_days: null,
                individual_end_hours: null,
                individual_end_minutes: null
            },
            mockSettingsPage = readFixtures('mock/mock-settings-page.underscore');

        beforeEach(function () {
            setFixtures(mockSettingsPage);

            this.model = new CourseDetailsModel(modelData, {parse: true});
            this.model.urlRoot = urlRoot;
            this.view = new MainView({
                el: $('.settings-details'),
                model: this.model
            }).render();
        });

        afterEach(function () {
            // Clean up after the $.datepicker
            $("#start_date").datepicker("destroy");
            $("#due_date").datepicker("destroy");
            $('.ui-datepicker').remove();
        });

        it('Changing course start date after course deadline start date should result in error', function () {
            this.view.$el.find('#course-start-date')
                .val('11/06/2014')
                .trigger('change');
            expect(this.view.$el.find('span.message-error').text()).toContain("deadline start date cannot be before the course start date");
        });

        it('Changing course start date after course terminate start date should result in error', function () {
            this.view.$el.find('#course-start-date')
                .val('12/06/2014')
                .trigger('change');
            expect(this.view.$el.find('span.message-error').text()).toContain("terminate start date cannot be before the course start date");
        });

        it('Changing course enrollment end date after course terminate start date should result in error', function () {
            this.view.$el.find('#course-enrollment-end-date')
                .val('12/06/2014')
                .trigger('change');
            expect(this.view.$el.find('span.message-error').text()).toContain("terminate start date cannot be before the enrollment end date");
        });

        it('Input empty course canonical name should result in error', function () {
            this.view.$el.find('#course-canonical-name')
                .val('')
                .trigger('change');
            expect(this.view.$el.find('span.message-error').text()).toContain("Course Canonical Name is required input");
        });

        it('Input empty course teacher name should result in error', function () {
            this.view.$el.find('#course-teacher-name')
                .val('')
                .trigger('change');
            expect(this.view.$el.find('span.message-error').text()).toContain("Teacher Name is required input");
        });

        it('Changing the time field do not affect other time fields', function () {
            var requests = AjaxHelpers.requests(this),
                expectedJson = $.extend(true, {}, modelData, {
                    // Expect to see changes just in `start_date` field.
                    start_date: "2014-10-05T22:00:00.000Z"
                });
            this.view.$el.find('#course-start-time')
                .val('22:00')
                .trigger('input');

            this.view.saveView();
            // It sends `POST` request, because the model doesn't have `id`. In
            // this case, it is considered to be new according to Backbone documentation.
            AjaxHelpers.expectJsonRequest(
                requests, 'POST', urlRoot, expectedJson
            );
        });

        it('Selecting a course in pre-requisite drop down should save it as part of course details', function () {
            var pre_requisite_courses = ['test/CSS101/2012_T1'];
            var requests = AjaxHelpers.requests(this),
                expectedJson = $.extend(true, {}, modelData, {
                    pre_requisite_courses: pre_requisite_courses
                });
            this.view.$el.find('#pre-requisite-course')
                .val(pre_requisite_courses[0])
                .trigger('change');

            this.view.saveView();
            AjaxHelpers.expectJsonRequest(
                requests, 'POST', urlRoot, expectedJson
            );
            AjaxHelpers.respondWithJson(requests, expectedJson);
        });

        it('should disallow save with an invalid minimum score percentage', function(){
            var entrance_exam_enabled_field = this.view.$(SELECTORS.entrance_exam_enabled_field),
                entrance_exam_min_score = this.view.$(SELECTORS.entrance_exam_min_score);

            //input some invalid values.
            expect(entrance_exam_min_score.val('101').trigger('input')).toHaveClass("error");
            expect(entrance_exam_min_score.val('invalidVal').trigger('input')).toHaveClass("error");

        });

        it('should provide a default value for the minimum score percentage', function(){

            var entrance_exam_min_score = this.view.$(SELECTORS.entrance_exam_min_score);

            //if input an empty value, model should be populated with the default value.
            entrance_exam_min_score.val('').trigger('input');
            expect(this.model.get('entrance_exam_minimum_score_pct'))
                .toEqual(this.model.defaults.entrance_exam_minimum_score_pct);
        });

        it('show and hide the grade requirement section when the check box is selected and deselected respectively', function(){

            var entrance_exam_enabled_field = this.view.$(SELECTORS.entrance_exam_enabled_field);

            // select the entrance-exam-enabled checkbox. grade requirement section should be visible.
            entrance_exam_enabled_field
                .attr('checked', 'true')
                .trigger('change');

            this.view.render();
            expect(this.view.$(SELECTORS.grade_requirement_div)).toBeVisible();

            // deselect the entrance-exam-enabled checkbox. grade requirement section should be hidden.
            entrance_exam_enabled_field
                .removeAttr('checked')
                .trigger('change');

            expect(this.view.$(SELECTORS.grade_requirement_div)).toBeHidden();

        });

        it('should save entrance exam course details information correctly', function () {
            var entrance_exam_minimum_score_pct = '60',
                entrance_exam_enabled = 'true',
                entrance_exam_min_score = this.view.$(SELECTORS.entrance_exam_min_score),
                entrance_exam_enabled_field = this.view.$(SELECTORS.entrance_exam_enabled_field);

            var requests = AjaxHelpers.requests(this),
                expectedJson = $.extend(true, {}, modelData, {
                    entrance_exam_enabled: entrance_exam_enabled,
                    entrance_exam_minimum_score_pct: entrance_exam_minimum_score_pct
                });

            // select the entrance-exam-enabled checkbox.
            entrance_exam_enabled_field
                .attr('checked', 'true')
                .trigger('change');

            // input a valid value for entrance exam minimum score.
            entrance_exam_min_score.val(entrance_exam_minimum_score_pct).trigger('input');

            this.view.saveView();
            AjaxHelpers.expectJsonRequest(
                requests, 'POST', urlRoot, expectedJson
            );
            AjaxHelpers.respondWithJson(requests, expectedJson);
        });

        it('should save language as part of course details', function(){
            var requests = AjaxHelpers.requests(this);
            var expectedJson = $.extend(true, {}, modelData, {
                language: 'en',
            });
            $('#course-language').val('en').trigger('change');
            expect(this.model.get('language')).toEqual('en');
            this.view.saveView();
            AjaxHelpers.expectJsonRequest(
                requests, 'POST', urlRoot, expectedJson
            );
        });

        it('should not error if about_page_editable is False', function(){
            var requests = AjaxHelpers.requests(this);
            // if about_page_editable is false, there is no section.course_details
            $('.course_details').remove();
            expect(this.model.get('language')).toEqual('');
            this.view.saveView();
            AjaxHelpers.expectJsonRequest(requests, 'POST', urlRoot, modelData);
        });

        describe('Input invalid days, hours, minutes', function() {
            var daysErrorMessage = 'Please enter an integer between 0 and 999.',
                hoursErrorMessage = 'Please enter an integer between 0 and 23.',
                minutesErrorMessage = 'Please enter an integer between 0 and 59.';

            beforeEach(function() {
                this.model.set({self_paced: true});
            });

            it('Input non integer individual_end_days should result in error', function () {
                this.view.$el.find('#individual-course-end-days').val('a').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(daysErrorMessage);
                this.view.$el.find('#individual-course-end-days').val('1.0').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(daysErrorMessage);
                this.view.$el.find('#individual-course-end-days').val(0).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(daysErrorMessage);
            });

            it('Input negative individual_end_days should result in error', function () {
                this.view.$el.find('#individual-course-end-days').val(0).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(daysErrorMessage);
                this.view.$el.find('#individual-course-end-days').val(-1).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(daysErrorMessage);
            });

            it('Input too big individual_end_days should result in error', function () {
                this.view.$el.find('#individual-course-end-days').val(999).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(daysErrorMessage);
                this.view.$el.find('#individual-course-end-days').val(1000).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(daysErrorMessage);
            });

            it('Input non integer individual_end_hours should result in error', function () {
                this.view.$el.find('#individual-course-end-hours').val('a').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(hoursErrorMessage);
                this.view.$el.find('#individual-course-end-hours').val('1.0').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(hoursErrorMessage);
            });

            it('Input negative individual_end_hours should result in error', function () {
                this.view.$el.find('#individual-course-end-hours').val(0).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(hoursErrorMessage);
                this.view.$el.find('#individual-course-end-hours').val(-1).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(hoursErrorMessage);
            });

            it('Input too big individual_end_hours should result in error', function () {
                this.view.$el.find('#individual-course-end-hours').val(23).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(hoursErrorMessage);
                this.view.$el.find('#individual-course-end-hours').val(24).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(hoursErrorMessage);
            });

            it('Input non integer individual_end_minutes should result in error', function () {
                this.view.$el.find('#individual-course-end-minutes').val('a').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(minutesErrorMessage);
                this.view.$el.find('#individual-course-end-minutes').val('1.0').trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(minutesErrorMessage);
            });

            it('Input negative individual_end_minutes should result in error', function () {
                this.view.$el.find('#individual-course-end-minutes').val(0).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(minutesErrorMessage);
                this.view.$el.find('#individual-course-end-minutes').val(-1).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(minutesErrorMessage);
            });

            it('Input too big individual_end_minutes should result in error', function () {
                this.view.$el.find('#individual-course-end-minutes').val(59).trigger('change');
                expect(this.view.$el.find('span.message-error')).not.toContainText(minutesErrorMessage);
                this.view.$el.find('#individual-course-end-minutes').val(60).trigger('change');
                expect(this.view.$el.find('span.message-error')).toContainText(minutesErrorMessage);
            });
        });

    });
});
