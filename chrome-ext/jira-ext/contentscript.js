var doWork = function() {
    // look for the custom field and add link to clienthub
    var companyElem = document.getElementById("customfield_10030-field");
    if (companyElem != null) {
        var companyName = companyElem.firstElementChild.innerHTML;
        var cNode = companyElem.firstElementChild.cloneNode(true);
        cNode.href = "http://www.10gen.com/clienthub/link/jira/" + companyName;
        cNode.innerHTML = "(clienthub)";
        companyElem.appendChild(cNode);
    }
}

doWork();
