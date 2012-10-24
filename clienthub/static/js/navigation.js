$(document).ready(function(){
  var navMaxLength = 0;
  $("nav ul li").not("nav ul li ul li").each(function(){
    navMaxLength = 0;
    $(this).find("li a").each(function(){
      if (($(this).text().length) * 7 > navMaxLength)
        navMaxLength = ($(this).text().length) * 7;
    });
    if (navMaxLength > $(this).outerWidth(true))
    {
      if ($(this).hasClass("first"))
        $(this).find("ul").css({width:navMaxLength,left:0});
      else if ($(this).hasClass("last"))
        $(this).find("ul").css({width:navMaxLength,left:-(navMaxLength - ($(this).outerWidth(true)))});
      else
        $(this).find("ul").css({width:navMaxLength,left:-(navMaxLength - ($(this).outerWidth(true)))/2});
    }
  });
  $("nav > ul li:not(:has(ul))").addClass("no-drop");
});
