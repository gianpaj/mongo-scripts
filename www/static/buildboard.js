(function ($) {

  var headers = null;

  function title(value) {
    var parts = value.split(/ +/);
    $(parts).each(function(i) {
      parts[i] = this.substr(0, 1).toUpperCase() + this.slice(1);
    });
    return parts.join(' ');
  }

  /* add "categoryRows" layout to isotope */
  $.extend($.Isotope.prototype, {
    _categoryRowsReset : function() {
      this.categoryRows = {
        x : 0,
        y : 0,
        height : 0,
        currentCategory : null
      };
    },

  _categoryRowsLayout : function($elems) {
    $('.generated-header').remove();
    headers = [];

    var instance = this,
    containerWidth = this.element.width(),
    sortBy = this.options.sortBy,
    props = this.categoryRows;

    $elems.each(function() {
      var $this = $(this);
      var atomW = $this.outerWidth(true);
      var atomH = $this.outerHeight(true);
      var category = GROUP[groupkey]($this); // $.data(this, 'isotope-sort-data')[ sortBy ];
      var x, y;

      if (category !== props.currentCategory) {
        var $header = $('<h1 class="generated-header">' + title(category) + '</h1>');
        $('#buildboard').append($header);
        headers[headers.length] = $header;

        // new category, new row
        props.x = 0;
        props.height += props.currentCategory ? instance.options.categoryRows.gutter : 0;
        props.y = props.height;
        props.currentCategory = category;

        // position the header, add another gutter
        $header.css('top', parseInt(props.y + (instance.options.categoryRows.gutter * 1.5)) + 'px');

        props.y += parseInt($header.outerHeight(true) * 0.7);

      } else if (props.x !== 0 && atomW + props.x > containerWidth) {
        // if this element cannot fit in the current row
        props.x = 0;
        props.y = props.height;
      }

      // position the atom
      instance._pushPosition($this, props.x, props.y);

      props.height = Math.max(props.y + atomH, props.height);
      props.x += atomW;

      });
    },

    _categoryRowsGetContainerSize : function () {
      return { height : this.categoryRows.height };
    },

    _categoryRowsResizeChanged : function() {
      return true;
    }
  });

  function _trace(func) {
    function inner() {
      var out = func.apply(this, arguments);
      var args = [];
      for (var i=0; i<arguments.length; i++) {
        args[i] = arguments[i];
      }
      console.log('' + func.name + '(' + args.join(', ') + ') => ' + out);
      return out;
    }
    return inner;
  }

  /** data extractors **/
  function getStatus($elem) {
    // returns 'passed', 'failed', 'Running'
    // Running is intentionally capital so that it sorts first
    var cssClass = $elem.attr('class');
    if (cssClass.indexOf('running') != -1)
      return 'Running';
    else if (cssClass.indexOf('successful') != -1)
      return 'passed';
    else
      return 'failed';
  }

  function getHistory($elem) {
    // returns 'stable', 'Unstable', 'Failing'
    // 'stable' is intentionally lowercase to sort last
    var map = {
      failing: 'Failing',
      partfailing: 'Unstable',
      passing: 'stable'
    };
    return map[$elem.find('.history').text()];
  }

  function getName($elem) {
    return $elem.find('.buildname').text();
  }

  function getVersion($elem) {
    var name = getName($elem);
    if (/V[\d\.]+/.test(name)) {
      return /(V[\d\.]+)/.exec(name)[1];
    }
    return "master";
  }

  function getUpdated($elem) {
    var updated = parseInt($elem.find('.lastupdate').text(), 10);
    var now = parseInt(new Date().getTime() / 1000, 10);
    var out = now - updated;
    if (getStatus($elem) == 'Running') {
      // running builds get sorted first, so subtract
      // a days worth of seconds from the return value
      out -= 86400;
    }
    return out;
  }


  var GROUP = {
    status: getStatus,
    version: getVersion,
    history: getHistory
  }

  var SORT = {
    updated: getUpdated,
    name: getName
  }



  /** main **/
  var groupkey = 'status';
  var sortkey = 'updated';

  function update() {
    // "this" is the <a> element
    var type = $(this).parents('ul').attr('class');
    var key = $(this).attr('href').slice(1);

    if (type == 'group') {
      groupkey = key;
    } else if (type == 'sort') {
      sortkey = key;
    }

    var $items = $('#buildboard .item');
    $('.isotope').isotope('updateSortData', $items).isotope({sortBy: 'custom'}); //'reLayout');

    $('#controls .group a').css('font-weight', 'normal').filter('[href="#' + groupkey + '"]').css('font-weight', 'bold');
    $('#controls .sort  a').css('font-weight', 'normal').filter('[href="#' + sortkey  + '"]').css('font-weight', 'bold');

    return false;
  }

  $(document).ready(function() {
    $('#buildboard .isotope').isotope({
      itemSelector: '.item',
      layoutMode: 'fitRows',
      getSortData: {'custom': function($elem) { return GROUP[groupkey]($elem) + '::' + SORT[sortkey]($elem); }},
      sortBy: 'custom',
      layoutMode: 'categoryRows',
      categoryRows: {
        gutter: 30
      }
    });

    $('#controls a[href]').click(update);

    // TODO: remove
    $('#controls .group a').css('font-weight', 'normal').filter('[href="#' + groupkey + '"]').css('font-weight', 'bold');
    $('#controls .sort  a').css('font-weight', 'normal').filter('[href="#' + sortkey  + '"]').css('font-weight', 'bold');
  });

})(jQuery);
