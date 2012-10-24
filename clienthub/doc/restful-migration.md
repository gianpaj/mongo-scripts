# Notes on migrating clienthub endpoints into a RESTful world


## Post migration resources:
    /system
        GET /login
        POST /login
        POST /logout
        GET /heartbeat
    /client
        GET / ## Index of Clients (both all and mine)
        GET /new ## New Client Interface
        POST / ## Create Client
        GET /:client_id ## View - both html and csv view
        GET /:client_id/edit ## Edit Interface
        PUT /:client_id ## Update Client
        DELETE /:client_id ## Destroy Client
        PUT /:client_id/refresh ## Refresh Client's Cache
        /contact
            ## New, Create, Update Delete handled in SF
            PUT /:contact_id ## Update Contact Type
        /doc
            ## Index handled by client view.
            GET /:document_type/new ## New Document Interface - variable depending on type
            POST /:document_type ## Create Document
            GET /:document_id ## View Document
            GET /:document_id/edit # Edit Document Interface - also type dependant
            PUT /:document_id ## Update Document
            DELETE /:document_id ## Destroy Document
            GET /:document_id/upload ## Download Attachement
    /report
        GET / ## Index of Reports
        GET /new ## Schedule Report Interface
        POST / ## Schedule Report
        GET /:report_id ## View an Existing Report
    /doc
        GET / ## Index of Documents i.e. docsearch
    /group
        GET / ## Index of Jira Groups
        GET /new ## New Jira Group Interface
        POST / ## Create New Jira Group
        GET /:group_id ## View Jira Group
        POST /:group_id ## Partial Update - for example to toggle CS
        DELETE /:group_id ## Destroy Group
        PUT /:group_id/refresh ## Refresh Group Cache
        PUT /refresh ## Refresh Full Jira Cache
        /user
            GET /new ## New User Interface
            POST / ## Add user to group
            DELETE /:user_id ## Remove user from group

