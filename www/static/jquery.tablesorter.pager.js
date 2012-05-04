(function($) {
  $.extend({
    tablesorterPager: new function() {

      function updatePageDisplay(c) {
        $(c.cssPageDisplay,c.container).val((c.page+1) + c.seperator + c.totalPages);
        $(c.cssPageSize).val(c.size);
      }

      function setPageSize(table,size) {
        var c = table.config;
        c.size = size;
        c.totalPages = Math.ceil(c.totalRows / c.size);
        c.pagerPositionSet = false;
        moveToPage(table);
      }

      function moveToFirstPage(table) {
        var c = table.config;
        c.page = 0;
        moveToPage(table);
      }

      function moveToLastPage(table) {
        var c = table.config;
        c.page = (c.totalPages-1);
        moveToPage(table);
      }

      function moveToNextPage(table) {
        var c = table.config;
        c.page++;
        if(c.page >= (c.totalPages-1)) {
          c.page = (c.totalPages-1);
        }
        moveToPage(table);
      }

      function moveToPrevPage(table) {
        var c = table.config;
        c.page--;
        if(c.page <= 0) {
          c.page = 0;
        }
        moveToPage(table);
      }


      function moveToPage(table) {
        var c = table.config;
        if(c.page < 0 || c.page > (c.totalPages-1)) {
          c.page = 0;
        }

        renderTable(table,c.rowsCopy);
        window.location.hash = '#s' + c.size + 'o' + c.page;
      }

      function renderTable(table,rows) {

        var c = table.config;
        var l = rows.length;
        var s = (c.page * c.size);
        var e = (s + c.size);
        if(e > rows.length ) {
          e = rows.length;
        }


        var tableBody = $(table.tBodies[0]);

        // clear the table body

        $.tablesorter.clearTableBody(table);

        for(var i = s; i < e; i++) {

          //tableBody.append(rows[i]);

          var o = rows[i];
          var l = o.length;
          for(var j=0; j < l; j++) {

            tableBody[0].appendChild(o[j]);

          }
        }

        $(table).trigger("applyWidgets");

        if( c.page >= c.totalPages ) {
              moveToLastPage(table);
        }

        updatePageDisplay(c);
      }

      this.appender = function(table,rows) {

        var c = table.config;

        c.rowsCopy = rows;
        c.totalRows = rows.length;
        c.totalPages = Math.ceil(c.totalRows / c.size);

        renderTable(table,rows);
      };

      this.defaults = {
        size: 10,
        offset: 0,
        page: 0,
        totalRows: 0,
        totalPages: 0,
        container: null,
        cssNext: '.next',
        cssPrev: '.prev',
        cssFirst: '.first',
        cssLast: '.last',
        cssPageDisplay: '.pagedisplay',
        cssPageSize: '.pagesize',
        seperator: "/",
        positionFixed: true,
        appender: this.appender
      };

      this.construct = function(settings) {

        return this.each(function() {

          config = $.extend(this.config, $.tablesorterPager.defaults, settings);

          var table = this, pager = config.container;

          $(this).trigger("appendCache");

          config.size = parseInt($(".pagesize",pager).val());

          $(config.cssFirst,pager).click(function() {
            moveToFirstPage(table);
            return false;
          });
          $(config.cssNext,pager).click(function() {
            moveToNextPage(table);
            return false;
          });
          $(config.cssPrev,pager).click(function() {
            moveToPrevPage(table);
            return false;
          });
          $(config.cssLast,pager).click(function() {
            moveToLastPage(table);
            return false;
          });
          $(config.cssPageSize,pager).change(function() {
            setPageSize(table,parseInt($(this).val()));
            return false;
          });

          if (window.location.hash) {
            var h = window.location.hash;
            var re = /s(\d+)o(\d+)/;
            if ( re.test(h) ) {
              var m = re(h);
              setPageSize(table, parseInt(m[1], 10));
              config.page = parseInt(m[2], 10);
              moveToPage(table);
            }
          }
        });
      };
    }
  });
  // extend plugin scope
  $.fn.extend({
        tablesorterPager: $.tablesorterPager.construct
  });

})(jQuery);
