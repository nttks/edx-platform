define(['jquery', 'underscore', 'common/js/spec_helpers/ajax_helpers', 'js/progress_report'],
    function($, _, AjaxHelpers, ProgressReport) {
        describe('progress_report.js', function() {

            beforeEach(function() {
                loadFixtures("js/fixtures/progress_report.html")
                var p_url = "http://localhost/get_progress_list/org/cn/run/?force=false"
                var s_url = "http://localhost/get_submission_scores/org/cn/run/?force=false"
                var o_url = "http://localhost/get_oa_rubric_scores/org/cn/run/?force=false"
                this.view = ProgressReport(p_url, s_url, o_url, 'progress_report');
            });

            afterEach(function() {
                console.log("<<< after");
            });

            it('getColors', function() {
                var color1 = this.view.prototype.getColors(1);
                var colors = ['#e6821e', '#82e61e', '#1ee682', '#1e82e6', '#821ee6', '#e61e82']
                expect(color1).toEqual(colors);

                var color2 = this.view.prototype.getColors(2);
                expect(color2).toEqual(colors);

                var color6 = this.view.prototype.getColors(6);
                expect(color6).toEqual(colors);

                var color7 = this.view.prototype.getColors(7);
                expect(color7).not.toEqual(colors);

                var color_dummy = this.view.prototype.getColors('dummy');
                expect(color_dummy).toEqual([]);
            });

            it('setPulldownList', function() {
                var selector = "#BarChart_items";
                var option_ids = {
                    item_id: "i4x://org/cn/openassessment/7ae4ff1",
                    display_name: "Peer Assessment",
                    rubrics: ["Final_Score"],
                    selectors: ["#Final_Score0"]
                };
                this.view.prototype.setPulldownList(option_ids, selector);
                var option = $('#BarChart_items option[value="#Final_Score0"]');
                expect(option.size()).toBe(1);
                expect(option.text()).toBe(option_ids["rubrics"][0]);
            });

            it('setBars', function() {
                var selector = "#SubmissionScoreDistribution";
                var rubric_scores = {
                    "i4x://org/cn/openassessment/7ae4ff1": {
                        "display_name": "Peer Assessment",
                        "rubrics": {
                            "Final_Score": {
                                "0-6": [12, 0],
                                "7-12": [1, 1],
                                "13-18": [5, 2]
                            }
                        }
                    }
                };
                var xaxis = 'xlabel';
                var yaxis = 'ylabel';
                var spy_draw_bar = spyOn(this.view.prototype, 'drawBarChart');
                var spy_set_pulldown = spyOn(this.view.prototype, 'setPulldownList');
                expect(spy_draw_bar).toBe(this.view.prototype.drawBarChart);
                expect(spy_set_pulldown).toBe(this.view.prototype.setPulldownList);
                
                this.view.prototype.setBars(rubric_scores, selector, xaxis, yaxis);
                expect(this.view.prototype.drawBarChart).toHaveBeenCalledWith(
                    [[12, 0], [1, 1], [5, 2]],
                    [[0, '0-6'], [1, '7-12'], [2, '13-18']],
                    '#Final_Score0', 'xlabel', 'ylabel');
                expect(this.view.prototype.setPulldownList).toHaveBeenCalledWith({
                    "item_id": 'i4x://org/cn/openassessment/7ae4ff1',
                    "display_name": 'Peer Assessment',
                    "rubrics": [ 'Final_Score' ],
                    "selectors": [ '#Final_Score0' ]
                }, '#BarChart_items');
            });
        });
    }
)
