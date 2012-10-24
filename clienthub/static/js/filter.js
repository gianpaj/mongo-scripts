$(document).ready(function(){
  // Initialize Filter
  populateFilter();
  populatePresentations();

  // If a hash exists
  if (getHash()) {
    var selected_filters = new Array(),
        hash = getHash();

    hash = hash.slice(1);
    selected_filters = hash.split("__");

    // Check boxes based off hash
    for (var i = 0; i < selected_filters.length; i++) {
      $(".filter .options #" + selected_filters[i]).prop("checked",true);
      checkRelatedBoxes($(".filter .options #" + selected_filters[i]));
    }

    updateMeta();
    updatePresentations();
  }
  // If no hash, show featured presentations
  else
    showPresentations(".featured");

  // Close dropdown if body is clicked
  // -------------------------------------
  $("body").click(function(e){
    if ($(e.target).is(".filter-label")) return;
    if ($(e.target).parents().is(".filter")) return;
    $(".filter-label").next().removeClass("visible").find("ul").slideUp();
  });

  // Toggle the main filter dropdown when
  // it is is clicked. Update if closing
  // -------------------------------------
  $(".filter-label").click(function(e){
    e.preventDefault();
    $(this).next().toggleClass("visible").find("ul").slideToggle();

    // Update presentations if it is being closed
    // if (!$(this).next().hasClass("visible")) updatePresentations();
  });

  // When View All button is clicked
  // -------------------------------------
  $(".filter li.buttons .select").click(function(e){
    e.preventDefault();
    // Select all facets besides featured
    if ($(this).hasClass("all")) {
      $(this).closest(".filter-dropdown").find("input[type='checkbox']").prop("checked",false);
      $(this).closest(".filter-dropdown").find("input[type='checkbox']").prop("indeterminate",false);
      // $(this).closest(".filter-dropdown").find(".section-title input[type='checkbox']").not("#featured").click();
      showPresentations();
      $(".filter .filter-label > strong").html("All Presentations");
      $(".filter .filter-label .selected-filters span").html("");
      $(this).html("View Featured");
    }
    // Select only featured
    else if ($(this).hasClass("featured")) {
      $(this).closest(".filter-dropdown").find("input[type='checkbox']").prop("checked",false);
      $(this).closest(".filter-dropdown").find("li.featured .section-title input[type='checkbox']").click();
      $(this).html("View All");
    }
    $(this).toggleClass("all").toggleClass("featured");
    $(".filter-label").click();
  });

  // Close filter when apply button is
  // clicked
  // -------------------------------------
  $(".filter li.buttons .apply").click(function(e){
    e.preventDefault();
    $(".filter-label").click();
  });

  // Toggle facet dropdown
  // -------------------------------------
  $(".filter").delegate(".filter-dropdown > ul > li > a","click",function(e){
    // If the object clicked is a checkbox, return and do the default
    if ($(e.target).is("input[type='checkbox']")) return;

    e.preventDefault();
    $(this).parent().toggleClass("visible").find(".options").slideToggle();
  });

  // When a checkbox value is changed
  // -------------------------------------
  $(".filter").delegate("input[type='checkbox']","change",function(){
    checkRelatedBoxes(this);
    updateMeta();
    updatePresentations();
  });
});

// Populate dropdown with the facets to
// filter by, taken from the JSON
// ------------------------------------
function populateFilter() {
  var filter_code="", num_sub=0, num_sub_col=0;

  // Loop through facets from JSON
  $.each(facets, function(i, item){
    // Top level HTML for each facet
    filter_code += "<li><a href='#'><span class='section-title'><span class='arrow'></span><input type='checkbox' id='" + item.name + "' name='" + item.name + "' value='" + item.display_name + "' /><strong>" + item.display_name + "</strong></span><span class='selected-items'><span class='selected-count'>(<span>0</span>)</span></span><span class='unshown'></span></a>";
    num_sub = item.values.length; // Number of sub-categories in each facet
    num_sub_col = Math.ceil(num_sub / 3); // Number of sub-categories to display in each column

    // Create HTML for sub-categories
    filter_code += "<div class='options'>";
    $.each(item.values, function(j, value){
      if (j == 0) // First sub-category
        filter_code += "<div class='col'>";
      else if (j % num_sub_col == 0) // If it's time for a new column
        filter_code += "</div><div class='col'>";
      // Append HTML for sub-category
      filter_code += "<label for='" + value.name + "'><input type='checkbox' id='" + value.name + "' class='sub-filter' name='" + value.name + "' value='" + value.display_name + "' /><span>" + value.display_name + "</span></label>";
    });
    filter_code += "</div></div><!-- /.options --></li>"; // Wrap up each facet
  });

  // Append facets to the filter
  $(".filter .filter-dropdown ul li.featured").after(filter_code);
}

// Populate page content with the
// presentation data from the JSON
// ------------------------------------
function populatePresentations() {
  var presentation_list = "", // Beginning of presentation data HTML
      url_prefix = "";

  // Loop through each presentation
  $.each(presentations, function(i, item){
    presentation_list_item = $("<li>")
    if (item.hasOwnProperty('featured')) {
      presentation_list_item.addClass('featured')
    }
    // Loop through each tag
    $.each(item.tags, function(j, tag) {
      if (tag) {
        var tag_cls = j + "-" + tag + " ";
        presentation_list_item.addClass(tag_cls)
      }
    });
    var today = new Date();
    var MS_PER_MONTH = 2551443840;
    var nine_months_ago = new Date(today.valueOf() - MS_PER_MONTH * 9);
    if (item.archived || new Date(item.date) < nine_months_ago ) {
      presentation_list_item.addClass('archived')
    }

    // Add rest of HTML for the filter and populate each section.
    var link = $('<a>')
    link.attr('href', url_prefix + item.url)
    presentation_list_item.append(link)

    var img = $('<img>')
    img.attr('rel', url_prefix + item.thumbnail)
    link.append(img)

    var h3 = $('<h3>')

    for (idx in item.speaker) {
      var speaker = item.speaker[idx];
      var content = [speaker.name, speaker.title, speaker.company].filter(Boolean)
      h3.html(h3.html() + " " + content.join(", "))
    }

    link.append(h3)

    var p = $('<p>')
    p.html(item.title)
    link.append(p)

    $(".presentation_event ul.container").append(presentation_list_item);
  });

  $(".presentation_event ul.container li").hide();

  formatVisiblePresentations();
}

// Set a clear class on each even
// presentation
// ------------------------------------
function formatVisiblePresentations() {
  $(".presentation_event ul.container li").removeClass("clear");
  // Loop through each visible presentation
  $(".presentation_event ul.container li:visible").each(function(i) {
    // Set the image src to the URL stored in the rel attribute
    $(this).find("img").attr("src",$(this).find("img").attr("rel"));

    if (i % 2 == 0) // Add clear class to every other presentation
      $(this).addClass("clear");
  });
}

// Set a clear class on each even
// presentation
// ------------------------------------
function checkRelatedBoxes(clicked){
  var sub_categories = $(clicked).closest("li").find(".options input[type='checkbox']"),
      top_level_facet = $(clicked).closest("li").find(".section-title input[type='checkbox']");

  // Clicked checkbox is a top-level facet
  if ($(clicked).parent().hasClass("section-title")) {
    // If checked box is the featured box
    if ($(clicked).attr("id") == "featured") {
      // Featured box is checked
      if ($(clicked).is(":checked")) {
        $(".filter input[type='checkbox']").not(clicked).prop("checked",false).prop("indeterminate",false);
      }
      // Featured box is unchecked
      else {
        top_level_facet.prop("checked",false);
      }
    }
    else {
      $(clicked).closest(".filter-dropdown").find("li.featured input[type='checkbox']").prop("checked",false);
    }
    sub_categories.prop("checked", $(clicked).is(":checked"));
  }
  // Clicked checkbox is a sub-category
  else if ($(clicked).parents().hasClass("options")) {
    $(clicked).closest(".filter-dropdown").find("li.featured input[type='checkbox']").prop("checked",false);

    // Adjust top level facet accordingly
    if (sub_categories.filter(":checked").length == sub_categories.length) {
      top_level_facet.prop("checked",true);
      top_level_facet.prop("indeterminate",false);
    }
    else if (sub_categories.filter(":checked").length == 0) {
      top_level_facet.prop("checked",false);
      top_level_facet.prop("indeterminate",false);
    }
    else {
      top_level_facet.prop("checked",false);
      top_level_facet.prop("indeterminate",true);
    }
  }
}

// Update meta data for selected
// presentations
// ------------------------------------
function updateMeta() {
  var filter_label = "",
      selected_filters = "";

  $(".filter .filter-dropdown > ul > li").each(function(i){
    $(this).find(".selected-count span").html($(this).find(".options input[type='checkbox']:checked").length);
  });

  if ($(".filter .featured input[type='checkbox']").is(":checked")) {
    filter_label = "Featured Presentations";
    selected_filters = "";
  }
  else {
    filter_label = "Presentations Matching:";
    selected_filters = "";

    $(".filter .filter-dropdown li").not(".featured").find(".options input[type='checkbox']:checked").each(function(i){
      if (i == 0)
        selected_filters += $(this).val();
      else
        selected_filters += ", " + $(this).val()
    });

    if (selected_filters.length == 0)
      filter_label = "All Presentations";
  }

  $(".filter .filter-label > strong").html(filter_label);
  $(".filter .filter-label .selected-filters span").html(selected_filters);
}

// Update visible presentations based
// on the selected facets
// ------------------------------------
function updatePresentations() {
  var selected_filters = new Array(),
      classes_to_have = new Array(),
      selected_filters_hash = "",
      selected_presentations = $(".presentation_event ul.container li");

  selected_presentations.hide();

  // If featured facet is selected
  if ($(".filter .featured input[type='checkbox']").is(":checked")) {
    selected_filters[0] = new Array();
    selected_filters[0].push("featured");
    selected_presentations = selected_presentations.filter(".featured");
  }
  else {
    // Get selected facets
    $(".filter .section-title input[type='checkbox']").not("#featured").each(function(i){
      selected_filters[i] = new Array();
      selected_filters[i].push(this.id);

      if (!($(this).closest("li").find(".section-title input[type='checkbox']").is(":checked"))) {
        $(this).closest("li").find(".options input[type='checkbox']:checked").each(function(j){
          selected_filters[i].push(this.id);
        });
      }
    });

    for (var i = 0; i < selected_filters.length; i++) { // Loop through each main group
      classes_to_have[i] = new Array();
      for (var j = 1; j < selected_filters[i].length; j++) { // Loop through each sub group
        classes_to_have[i].push("." + selected_filters[i][0] + "-" + selected_filters[i][j]);
      }
    }
    // Filter presentations by selected facets
    for (var i = 0; i < classes_to_have.length; i++) {
      if (classes_to_have[i].length > 0) {
        selected_presentations = selected_presentations.filter(classes_to_have[i].join(", "));
        selected_filters_hash += selected_filters[i].join("__");
        selected_filters_hash += "__";
      }
    }
    //make sure we only show archived presentations when one of the facets is the event it's in
    //classes_to_have's first element is the events to filter by.
    if (classes_to_have[0].length == 0)
    selected_presentations = selected_presentations.filter(function(index) {
      return !$(selected_presentations[index]).hasClass('archived')
    })
  }


  selected_filters_hash = selected_filters_hash.slice(0,-2);
  setHash(selected_filters_hash);
  selected_presentations.show();
  formatVisiblePresentations();
}

function showPresentations(show_tag) {
  if (show_tag)
    $(".presentation_event ul.container li").hide().filter(show_tag).show();
  else
    $(".presentation_event ul.container li").not('.archived').show();
  formatVisiblePresentations();
}

function getHash() { return window.location.hash }
function setHash(hash) { window.location.hash = hash }
