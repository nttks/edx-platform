define(["backbone", "underscore", "gettext", "js/models/validation_helpers", "js/utils/date_utils"],
    function(Backbone, _, gettext, ValidationHelpers, DateUtils) {

var CourseDetails = Backbone.Model.extend({
    defaults: {
        org : '',
        course_id: '',
        run: '',
        language: '',
        start_date: null,	// maps to 'start'
        end_date: null,		// maps to 'end'
        individual_end_days: null,
        individual_end_hours: null,
        individual_end_minutes: null,
        enrollment_start: null,
        enrollment_end: null,
        deadline_start: null,
        terminate_start: null,
        syllabus: null,
        short_description: "",
        overview: "",
        intro_video: null,
        effort: null,	// an int or null,
        license: null,
        course_image_name: '', // the filename
        course_image_asset_path: '', // the full URL (/c4x/org/course/num/asset/filename)
        pre_requisite_courses: [],
        entrance_exam_enabled : '',
        entrance_exam_minimum_score_pct: '50',
        course_order: null,
        course_category: [],
        course_category_order: null,
        course_category2: '',
        course_category_order2: null,
        is_f2f_course: false,
        is_f2f_course_sell: false,
        playback_rate_1x_only: false,
        course_canonical_name: '',
        course_contents_provider: '',
        teacher_name: '',
        course_span: ''
    },

    validate: function(newattrs) {
        // Returns either nothing (no return call) so that validate works or an object of {field: errorstring} pairs
        // A bit funny in that the video key validation is asynchronous; so, it won't stop the validation.
        var errors = {};
        var dateFields = ["start_date", "end_date", "enrollment_start", "enrollment_end", "deadline_start", "terminate_start"];
        newattrs = DateUtils.convertDateStringsToObjects(
            newattrs, dateFields
        );

        if (newattrs.start_date === null) {
            errors.start_date = gettext("The course must have an assigned start date.");
        }
        if (newattrs.start_date && newattrs.enrollment_start && newattrs.start_date < newattrs.enrollment_start) {
            errors.enrollment_start = gettext("The course start date must be later than the enrollment start date.");
        }
        if (newattrs.enrollment_start && newattrs.enrollment_end && newattrs.enrollment_start >= newattrs.enrollment_end) {
            errors.enrollment_end = gettext("The enrollment start date cannot be after the enrollment end date.");
        }
        if (newattrs.self_paced) {
            if (newattrs.individual_end_days && !ValidationHelpers.validateIntegerRange(newattrs.individual_end_days, this._individual_end_days_range)) {
                errors.individual_end_days = interpolate(gettext("Please enter an integer between %(min)s and %(max)s."), this._individual_end_days_range, true);
            }
            if (newattrs.individual_end_hours && !ValidationHelpers.validateIntegerRange(newattrs.individual_end_hours, this._individual_end_hours_range)) {
                errors.individual_end_hours = interpolate(gettext("Please enter an integer between %(min)s and %(max)s."), this._individual_end_hours_range, true);
            }
            if (newattrs.individual_end_minutes && !ValidationHelpers.validateIntegerRange(newattrs.individual_end_minutes, this._individual_end_minutes_range)) {
                errors.individual_end_minutes = interpolate(gettext("Please enter an integer between %(min)s and %(max)s."), this._individual_end_minutes_range, true);
            }
        } else {
            if (newattrs.start_date && newattrs.end_date && newattrs.start_date >= newattrs.end_date) {
                errors.end_date = gettext("The course end date must be later than the course start date.");
            }
            if (newattrs.end_date && newattrs.enrollment_end && newattrs.end_date < newattrs.enrollment_end) {
                errors.enrollment_end = gettext("The enrollment end date cannot be after the course end date.");
            }
        }
        if (newattrs.deadline_start && newattrs.start_date && newattrs.deadline_start < newattrs.start_date) {
            errors.deadline_start = gettext("The deadline start date cannot be before the course start date.");
        }
        if (newattrs.terminate_start && newattrs.start_date && newattrs.terminate_start < newattrs.start_date) {
            errors.terminate_start = gettext("The terminate start date cannot be before the course start date.");
        }
        if (newattrs.terminate_start && newattrs.enrollment_end && newattrs.terminate_start < newattrs.enrollment_end) {
            errors.terminate_start = gettext("The terminate start date cannot be before the enrollment end date.");
        }
        if (newattrs.course_canonical_name === '') {
            errors.course_canonical_name = gettext("Course Canonical Name is required input.");
        }
        if (newattrs.teacher_name === '') {
            errors.teacher_name = gettext("Teacher Name is required input.");
        }
        if (newattrs.course_category.length > 0) {
            if (newattrs.course_category[0].match(/^(?=.*,).*$/)) {
                errors.course_category = gettext("Commas（,） can not be used");
            }
        }
        if (newattrs.course_category2 !== null && newattrs.course_category2 !== '' &&
            newattrs.course_category2 !==undefined) {
            if (newattrs.course_category.length <= 0) {
                errors.course_category2 = gettext("Please enter the course_category previously.");
            }
        }
        if (newattrs.course_order !== null) {
            if (! newattrs.course_order.match(/^[0-9]*$/)) {
                errors.course_order = gettext("Please enter only half-width numbers.");
            }
        }
        if (newattrs.course_category_order !== null) {
            if (! newattrs.course_category_order.match(/^[0-9]*$/)) {
                errors.course_category_order = gettext("Please enter only half-width numbers.");
            }
        }
        if (newattrs.course_category_order2 !== null) {
            if (! newattrs.course_category_order2.match(/^[0-9]*$/)) {
                errors.course_category_order2 = gettext("Please enter only half-width numbers.");
            }
        }
        if (newattrs.intro_video && newattrs.intro_video !== this.get('intro_video')) {
            if (this._videokey_illegal_chars.exec(newattrs.intro_video)) {
                errors.intro_video = gettext("Key should only contain letters, numbers, _, or -");
            }
            // TODO check if key points to a real video using google's youtube api
        }
        if(_.has(newattrs, 'entrance_exam_minimum_score_pct')){
            var range = {
                min: 1,
                max: 100
            };
            if(!ValidationHelpers.validateIntegerRange(newattrs.entrance_exam_minimum_score_pct, range)){
                errors.entrance_exam_minimum_score_pct = interpolate(gettext("Please enter an integer between %(min)s and %(max)s."), range, true);
            }
        }
        dateFields.forEach(function (key) {
            if (newattrs[key] && newattrs[key].getFullYear() < 1900) {
                errors[key] = gettext("Please enter the date on and after 1900.");
            }
        });
        if (!_.isEmpty(errors)) return errors;
        // NOTE don't return empty errors as that will be interpreted as an error state
    },

    _videokey_illegal_chars : /[^a-zA-Z0-9_-]/g,

    _individual_end_days_range: {min: 0, max: 999},
    _individual_end_hours_range: {min: 0, max: 23},
    _individual_end_minutes_range: {min: 0, max: 59},

    set_videosource: function(newsource) {
        // newsource either is <video youtube="speed:key, *"/> or just the "speed:key, *" string
        // returns the videosource for the preview which iss the key whose speed is closest to 1
        if (_.isEmpty(newsource) && !_.isEmpty(this.get('intro_video'))) this.set({'intro_video': null}, {validate: true});
        // TODO remove all whitespace w/in string
        else {
            if (this.get('intro_video') !== newsource) this.set('intro_video', newsource, {validate: true});
        }

        return this.videosourceSample();
    },

    videosourceSample : function() {
        if (this.has('intro_video')) return "//www.youtube.com/embed/" + this.get('intro_video');
        else return "";
    },

    // Whether or not the course pacing can be toggled. If the course
    // has already started, returns false; otherwise, returns true.
    canTogglePace: function () {
        return new Date() <= new Date(this.get('start_date'));
    }
});

return CourseDetails;

}); // end define()
