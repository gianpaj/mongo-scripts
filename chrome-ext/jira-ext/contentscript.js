var doWork = function() {
    // look for the custom field and add link to clienthub
    var companyElem = document.getElementById("customfield_10030-field");
    if (companyElem != null) {
        var companyName = companyElem.innerText;

        // create clienthub link
        var clienthubLink = document.createElement("a");
        clienthubLink.href = "http://www.10gen.com/clienthub/link/jira/" + companyName;
        clienthubLink.innerHTML = "clienthub";
        clienthubLink.style.color = "red";

        // create mms link
        var mmsLink = clienthubLink.cloneNode(true);
        mmsLink.href = "https://mms.10gen.com/links/customer?id=" + companyName + ",425989";
        mmsLink.innerHTML = "mms";

        // add links
        companyElem.appendChild(document.createTextNode("("));
        companyElem.appendChild(clienthubLink);
        companyElem.appendChild(document.createTextNode(" | "));
        companyElem.appendChild(mmsLink);
        companyElem.appendChild(document.createTextNode(")"));
    }
}

doWork();
