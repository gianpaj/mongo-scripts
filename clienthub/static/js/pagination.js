$(function() {
  $('.items').each(function() {
    var $this  = $(this),
        $items = $this.find('.item'),
        $nav   = $('<ul class="item_nav"></ul>'),
        width  = $this.outerWidth(),
        height = $this.outerHeight(),
        $shown = null,
        height = 0;
        
    $items.each(function(i) {
      $(this).show().css({
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: i == 0 ? 2 : 1,
        opacity: i == 0 ? 1 : 0,
        display:'block'
      });
      
      if ($(this).outerHeight(true) > height) {
        height = $(this).outerHeight(true);
      }
      
      if ($(this).closest(".items").hasClass("quotes")) {
        $(this).closest(".items").find(".item").each(function(){
          if (height < $(this).height()) {
            height = $(this).height();
          }
        });
      }
      
      $li = $('<li><span>Group ' + (i+1) + '</span></li>').appendTo($nav).data('item', $(this)).click(function() {
        var $item = $(this).data('item');

        // height = $item.height();
        // $item.parent().animate({height:height});
        
        if ($item != $shown) {
          if ($shown) { $shown.css('opacity', 0); }
          $item.css('opacity', 1);
          $shown = $item;
          $(this).closest('ul').find('li.current').removeClass('current');
          $(this).addClass('current');
          
          /*if ($(this).is('.last')) {
            $nav.find('.next').addClass('disabled');
          } else {
            $nav.find('.next').removeClass('disabled');
          }
          
          if ($(this).is('.first')) {
            $nav.find('.prev').addClass('disabled');
          } else {
            $nav.find('.prev').removeClass('disabled');
          }*/
        }
      });
      
      if (i == 0) {
        $li.addClass('first');
      }
    });
    
    $nav.find('li:last').addClass('last');

    go_prev = function() {
      if ($(this).hasClass('disabled')) {
        return false;
      }

      if ($nav.find('li.current').hasClass("first")) {
        var $prev = $nav.find('li.last');
      }
      else {
        var $prev = $nav.find('li.current').prev('li');
      }

      if ($prev) {
        $prev.click();
      }
    }

    go_next = function() {
      if ($(this).hasClass('disabled')) {
        return false;
      }

      if ($nav.find('li.current').hasClass("last")) {
        var $next = $nav.find('li.first');
      }
      else {
        var $next = $nav.find('li.current').next('li');
      }

      if ($next) {
        $next.click();
      }
    }

    if ($this.attr('data-prev-next') == 'true') {
      $('<li class="prev">Prev</li>').prependTo($nav).click(go_prev);
      $('<li class="next">Next</li>').prependTo($nav).click(go_next);
    }
    
    $this.css({
      position:'relative',
      background:'#fff',
      height: height
    })
    
    $nav.insertAfter($this);
    
    $nav.find('li:not(.prev,.next):first').click();

    if ($(this).hasClass("auto")) {
      setInterval(go_next, 3000);
    }
  });
});
