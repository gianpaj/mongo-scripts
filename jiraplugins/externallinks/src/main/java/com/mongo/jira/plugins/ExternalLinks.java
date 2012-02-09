package com.mongo.jira.plugins;

import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.CustomFieldManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.plugin.webfragment.contextproviders.AbstractJiraContextProvider;
import com.atlassian.jira.plugin.webfragment.model.JiraHelper;

import com.google.gson.Gson;
import com.google.gson.JsonIOException;
import com.google.gson.JsonSyntaxException;
import com.google.gson.stream.JsonReader;
import com.opensymphony.user.User;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Writer;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public class ExternalLinks extends AbstractJiraContextProvider {

    @Override
    public Map<String, Object> getContextMap(User user, JiraHelper jiraHelper) {

        Map<String, Object> contextMap = new HashMap<String, Object>();

        ComponentManager componentManager = ComponentManager.getInstance();
        CustomFieldManager customFieldManager = componentManager
                .getCustomFieldManager();
        CustomField customField = customFieldManager
                .getCustomFieldObjectByName("company");

        if (customField != null) {
            // retrieves the custom field (company) value object from the issue
            Issue currentIssue = (Issue) jiraHelper.getContextParams().get(
                    "issue");
            Object customFieldValue = currentIssue
                    .getCustomFieldValue((com.atlassian.jira.issue.fields.CustomField) customField);
            contextMap.put("clienthublink",
                    "http://www.10gen.com/clienthub/link/jira/"
                            + customFieldValue);
            contextMap.put("mmslink",
                    "https://mms.10gen.com/links/customer?id="
                            + customFieldValue + ",425989");
            contextMap.put("customcompany", customFieldValue);

            try {
                URL url = new URL("http://localhost:5000/client?jira_group=" + customFieldValue);
                URLConnection urlc = url.openConnection();
                urlc.setDoOutput(true);
                urlc.setAllowUserInteraction(false);

                JsonReader reader = new JsonReader(new InputStreamReader(
                        urlc.getInputStream()));
                reader.beginArray();
                while (reader.hasNext()) {
                    Client client = new Gson().fromJson(reader, Client.class);
                    contextMap.put("name", client.getName());
                    contextMap.put("account_contact",
                            client.getAccount_contact());
                    contextMap.put("primary_eng", client.getPrimary_eng());
                    Iterator<String> iter = client.getSecondary_engs()
                            .iterator();
                    int counter = 1;
                    while (iter.hasNext())
                        contextMap.put("secondary_eng" + counter, iter.next());
                }
                reader.endArray();
                reader.close();
            } catch (MalformedURLException ex) {
                displayErrorMessage(ex.getMessage());
            } catch (IOException ex) {
                displayErrorMessage(ex.getMessage());
            } catch (JsonIOException ex) {
                displayErrorMessage(ex.getMessage());
            } catch (JsonSyntaxException ex) {
                displayErrorMessage(ex.getMessage());
            }
        }
        return contextMap;
    }

    private static void displayErrorMessage(String message) {
        File file = new File("pluginerror.log");
        Writer output = null;
        try {
            output = new BufferedWriter(new FileWriter(file));
            output.write(message);
        } catch (IOException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
        }

    }
}
