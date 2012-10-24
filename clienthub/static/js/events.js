$(function(){
  $('.description').each(function() {
    var descdiv = this;
    function open() {
      var $div     = $(this).closest('.session > div'),
          position = $div.position();
      $div.data('height', $div.height()).css({
        height:'auto',
        position:'absolute',
        top: position.top,
        left: position.left,
        width: $div.width()-2
      }).addClass('active');
      $(descdiv).find('.abbrev').hide();
      $(descdiv).find('.full').show();
    }
    function close() {
      var $div     = $(this).closest('.session > div');
      $div.css({
        height:$div.data('height'),
        width: $div.width()+2,
        position:'static'
      }).removeClass('active');
      $(descdiv).find('.full').hide();
      $(descdiv).find('.abbrev').show();
    }
    $(this).find('.abbrev span.more').click(open);
    $(this).find('.full').click(close);
  });

  $('.schedule td.session').each(function() {
    var item = $(this).find('> div'),
        height = $(this).height() - (item.outerHeight(true) - item.height());
    item.height(height);
  });
});
