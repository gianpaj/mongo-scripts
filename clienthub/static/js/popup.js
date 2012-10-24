var popup_height = 0;

function displayPopup(type) {
	if (typeof(type)==='undefined') type = "newsletter";
	$(".popup .popup-body").add('.popup .popup-header span').hide();
	$(".popup .popup-header ." + type).show();
	$(".popup .popup-body."+type).show(function(){
		popup_height = ($(".popup").height())+60;
		$(".popup").animate({marginTop:-popup_height-20},400).animate({marginTop:-popup_height},200);
	});
}

function closePopup(object,toShow) {
	if (typeof(object)==='undefined') object = ".popup";
	if ($(".popup").css("marginTop") == "0px") return;
	if ($(".popup .popup-body:visible").size() > 1) {
		$(".popup").css("marginTop","0px");
		$(".popup .popup-body").hide();
		$(".popup .popup-body."+toShow).show();
		displayPopup(toShow);
	}
	else {	
		popup_height = ($(object).closest(".popup").height())+60;
		$(object).closest(".popup").animate({marginTop:-popup_height-20},200).animate({marginTop:0},400, function(){
			if(!(typeof(toShow)==='undefined')) displayPopup(toShow);
		});
	}
}

function showPopup(toShow) {
	if ($(".popup").css("margin-top") != "0px") closePopup(".popup",toShow);
	else displayPopup(toShow);
}

$(document).ready(function(){
	$(".popup select").dropkick();
	$(".popup").delegate(".close","click",function(e){
		e.preventDefault();
		closePopup(this);
	});
});
