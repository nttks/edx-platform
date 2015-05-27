var ProgressReport = function(problem_list_url, submission_scores_url, openassessment_rubric_scores_url, section_key) {
  function ProgressReport() {}
  var that = this;

  var slickgrid_id = "#ProgressGrid";
  var piechart_id = "#AnswerDistribution";
  var piechart_state_id = "#SelectionStatus";
  var piechart_legend_container = "#legendContainer";
  var barchart_id  = "#ProgressGraphs";
  var barchart_pulldown_list = "#BarChart_items";
  var submission_bar_id = "#SubmissionScoreDistribution";
  var openassessment_bar_id = "#OpenassessmentScoreDistribution";
  var force_update_button = "#ForceUpdate";
  var last_update = "#ProgressUpdate";

  ProgressReport.prototype.setPulldownList = function(option_ids, selector) {
    var uuid = option_ids["item_id"].match(/[a-zA-Z0-9]+$/);

    if (option_ids["display_name"] && $.type(option_ids["display_name"]) === "string") {
      var optgrp_tag = "<optgroup" + ' label="' + option_ids["display_name"] + '" id="' + uuid[0] + '"></optgroup>';
    } else {
      var optgrp_tag = "<optgroup" + ' label="' + option_ids["item_id"] + '" id="' + uuid[0] + '"></optgroup>';
    }

    if ($(selector).children().length === 0) {
      $(selector).append('<option value="-1"></option>');
    }

    if ($("#" + uuid[0]).size() === 0) {
      $(selector).append(optgrp_tag);
    }

    _.each(option_ids["rubrics"], function(rubric, idx) {
      $("#" + uuid[0]).append("<option value=" + option_ids["selectors"][idx] + ">" + gettext(rubric) + "</option>");
    });

    $(selector).change(function(e) {
      $(selector + " option:selected").each(function () {
        var graph_id = $(this).val();
        $(barchart_id + " .progress_graphs").hide();
        $(graph_id).show();
      });
      e.stopImmediatePropagation();
    });
  };
 
  ProgressReport.prototype.drawBarChart = function(scores_data, ticks, div_id, xaxis_label, yaxis_label) {
    var size = scores_data.length;
    $(div_id).height(size * 50 * 1.2 + 100);

    var data = [{
      label: "test_label",
      data: scores_data,
      color: "blue"
    }];
    var options = {
      series: {
        bars: { show: true }
      },
      bars: {
        align: "center",
        barWidth: 0.9,
        fill: true,
        fillColor: { colors: [ { opacity: 0.8 }, { opacity: 0.1 } ] },
        horizontal: true
      },
      xaxis: {
        autoscaleMargin: 0.1,
        axisLabel: gettext(xaxis_label),
        axisLabelUseCanvas: true,
        axisLabelFontSizePixels: 15,
        axisLabelFontFamily: 'Meiryo',
        axisLabelPadding: 50 
      },
      yaxis: {
        autoscaleMargin: 0.1,
        axisLabel: gettext(yaxis_label),
        axisLabelUseCanvas: true,
        axisLabelFontSizePixels: 15,
        axisLabelFontFamily: 'Meiryo',
        axisLabelPadding: 50,
        ticks: ticks
      },
      legend: {
        show: false
      },
      grid: {
        hoverable: true,
        borderWidth: 2,
        backgroundColor: { colors: ["#ffffff", "#EDF5FF"] }
      }
    };
    var plot = $.plot(div_id, data, options);
  };

  ProgressReport.prototype.setBars = function(rubric_scores, selector, xaxis_label, yaxis_label) {
    var indent = 0;
    var duplicate = false;

    _.each(rubric_scores, function(data, item_id) {
      var option_ids = {};
      option_ids["item_id"] = item_id;
      option_ids["display_name"] = data["display_name"];
      option_ids["rubrics"] = [];
      option_ids["selectors"] = [];

      
      _.each(data["rubrics"], function(options, rubric_name) {
        var bars = [];
        var ticks = [];

        is_pulldown_id = $(barchart_pulldown_list + ' optgroup[label="' + item_id + '"] option[value^="#' + rubric_name + indent + '"]').size();
        is_pulldown_name = $(barchart_pulldown_list + ' optgroup[label="' + data["display_name"] + '"] option[value^="#' + rubric_name + indent + '"]').size();

        if (is_pulldown_id || is_pulldown_name) {
          duplicate = true;
        } else {
          option_ids["rubrics"].push(rubric_name);

          _.each(options, function(score, option_name) {
            bars.push([score[0], score[1]]);
            ticks.push([score[1], option_name]);
          });

          $(selector).append('<div id="' + rubric_name + indent + '" class="progress_graphs" style="display:none;height:500px;width:1000px;"></div>');
          ProgressReport.prototype.drawBarChart(bars, ticks, "#" + rubric_name + indent, xaxis_label, yaxis_label);
          option_ids["selectors"].push("#" + rubric_name + indent);
        }

        indent++;
      });

      if (!duplicate || option_ids["rubrics"].length !== 0) {
        ProgressReport.prototype.setPulldownList(option_ids, barchart_pulldown_list);
      }
    });
  };

  ProgressReport.prototype.drawPieChart = function(answers_data, div_id) {
    $(div_id).css({height: "300px", width: "300px"});
    var plot = $.plot(div_id, answers_data, {
      series: {
        pie: {
          show: true,
          radius: 1,
          tilt: 0.9,
          label: {
            show: false
          }
        }
      },
      legend: {
        show: true,
        labelFormatter: function(label, series){
          var data;
          _.each(answers_data, function(answer, idx) {
            if (answer["label"] == label) {
              data = answer["data"];  
            }
          });
          return '<div style="font-size:x-small;text-align:center;padding:1px;line-height:15px;">'+label+'<br/>'+Math.round(series.percent)+'%<br/>('+data+')</div>';
        },
        //container:$(piechart_legend_container)
      }
    });
  };

  ProgressReport.prototype.getColors = function(size) {
    var colors = []; 
    var color_min = 30;
    var color_max = 230;
    var loop = Math.ceil(size / 6);
    var color_base = Math.round((color_max - color_min) / (loop + 1));

    if ($.type(size) !== "number") {
      return [];
    }

    var rgbTo16 = function(rgb){
      return "#" + rgb.map(
        function(a) {
          return ("0" + parseInt(a).toString(16)).slice(-2);
        }
      ).join("");
    };

    for (var i=1; i<=loop; i++) {
      colors.push(rgbTo16([color_max, color_base * i + color_min, color_min]));
      colors.push(rgbTo16([color_base * i + color_min, color_max, color_min]));
      colors.push(rgbTo16([color_min, color_max, color_base * i + color_min]));
      colors.push(rgbTo16([color_min, color_base * i + color_min, color_max]));
      colors.push(rgbTo16([color_base * i + color_min, color_min, color_max]));
      colors.push(rgbTo16([color_max, color_min, color_base * i + color_min]));
    }

    return colors;
  };
  
  ProgressReport.prototype.setGrid = function(course_structure) {
    var dataView;
    var grid;
    var data = [];

    var CourseNameFormatter = function(row, cell, value, columnDef, dataContext) {
      value = value.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      var spacer = "<span style='display:inline-block;height:1px;width:" + (15 * dataContext["indent"]) + "px'></span>";
      var idx = dataView.getIdxById(dataContext.id);
      return spacer + " &nbsp;" + value;
    };

    var columns = [
      {id: "id", name: "#", field: "id"},
      {id: "course", name: gettext('Course'), field: "course", width: 400, formatter: CourseNameFormatter},
      {id: "question", name: gettext('Question'), field: "question"},
      {id: "counts", name: gettext('Sum of answer'), field: "counts"},
      {id: "correct", name: gettext('Percentage of correct answer'), field: "correct", formatter:Slick.Formatters.PercentCompleteFormatter},
      {id: "attempt", name: gettext('Average of attempts'), field: "attempt", selectable: true}
    ];

    var options = {
      enableTextSelectionOnCells: true,
      enableCellNavigation: true,
      enableColumnReorder: false,
      forceFitColumns: true
    };

    var i = 0;
    _.each(course_structure, function(module) {
      counts = module["counts"];
      question = ("module_id" in module)? module["module_id"].split("_")[1] - 1: "-";
      correct = ("correct_counts" in module)? module["correct_counts"] / counts * 100: "-";
      attempt = ("attempts" in module)? module["attempts"] / counts: "-";
      answer = ("student_answers" in module)? module["student_answers"]: "-";

      data[i] = {
        id: i + 1,
        course: module["display_name"],
        question: question,
        counts: counts,
        correct: correct,
        attempt: attempt,
        answer: answer,
        useage_id: module["usage_id"],
        indent: module["indent"],
        has_children: module["has_children"]
      };
      i++;
    });

    dataView = new Slick.Data.DataView();
    dataView.beginUpdate();
    dataView.setItems(data);
    dataView.endUpdate();
    dataView.getItemMetadata = function(row) {
      indent = dataView.getItem(row)["indent"];
      if (indent < 3) {
        return {"columns": {"1": {"colspan": 5}}};
      }
    };

    grid = new Slick.Grid(slickgrid_id, dataView, columns, options);
    grid.onClick.subscribe(function (e, args) {
      var data = grid.getDataItem(args.row);
      if ("answer" in data && $.type(data["answer"]) === "object") {
        $(piechart_state_id).text("#" + data["id"]);
        var answers_data = [];
        var colors = ProgressReport.prototype.getColors(Object.keys(data["answer"]).length);
        var i=0;
        _.each(data["answer"], function(answer, label) {
          answers_data.push({"label": label, "data": answer, "color": colors[i]});
          i++;
        });
        ProgressReport.prototype.drawPieChart(answers_data, piechart_id);
      }
      e.stopImmediatePropagation();
    });
  };

  ProgressReport.prototype.loadJson = function(force) {
    if ($.type(force) === "undefined") {
      force = false
    }
    var ajax_status = {};

    var get_pgreport_data = function(url, selector, func, args) {
      var interval_timer;
      ajax_status[url] = false;
      $(force_update_button).prop("disabled", true);
      $(last_update + " " +  selector).siblings("i").show();

      $.ajax({
        type: 'GET',
        url: url,
        dataType: 'json',
        cache: false,
        data: {'force': force},
        statusCode: {
          200: function(response, stat, xhr) {
            var cache_date = xhr.getResponseHeader('X-Cache-Date')

            if ($.type(args) === "undefined") {
              args = [response];
            } else {
              args.unshift(response);
            }

            func.apply(this, args);
            ajax_status[url] = true;
            $(last_update + " " +  selector).text(cache_date);
            $(last_update + " " +  selector).siblings("i").hide();
            clearInterval(interval_timer);
            if (_.every(ajax_status, function(stat){return stat;})) {
              $(force_update_button).removeAttr("disabled");
            }
          },
          202: function() {
            var _this = this;
            if ($.type(interval_timer) === "undefined") {
              interval_timer = setInterval(function(){
                _this.url = url;
                $.ajax(_this);
              }, 30000);
            }
          },
          504: function() {
            var _this = this;
            console.debug("Retry ajax call!");
            if ($.type(interval_timer) === "undefined") {
              interval_timer = setInterval(function(){
                _this.url = url;
                $.ajax(_this);
              }, 30000);
            }
          }
        }
      });
    };

    get_pgreport_data(problem_list_url, '.structure', ProgressReport.prototype.setGrid);
    get_pgreport_data(openassessment_rubric_scores_url, '.openassessment', 
      ProgressReport.prototype.setBars, [openassessment_bar_id, 'Number of assessments', 'Assessment']);
    get_pgreport_data(submission_scores_url, '.submission', 
      ProgressReport.prototype.setBars, [submission_bar_id, 'Number of students', 'Score']);
  };

  $('ul.instructor-nav li.nav-item a[data-section="' + section_key + '"]').click(
    function() {ProgressReport.prototype.loadJson();});
  $(force_update_button).click(function() {ProgressReport.prototype.loadJson(true);});

  return ProgressReport;
};
