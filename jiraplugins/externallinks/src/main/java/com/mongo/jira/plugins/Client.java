package com.mongo.jira.plugins;

import java.util.List;

public class Client {

    private List<Ticket> checkin_tickets;
    public List<Ticket> getCheckin_tickets() {
        return checkin_tickets;
    }
    public void setCheckin_tickets(List<Ticket> checkin_tickets) {
        this.checkin_tickets = checkin_tickets;
    }
    public String getUpdated() {
        return updated;
    }
    public void setUpdated(String updated) {
        this.updated = updated;
    }
    public String getName() {
        return name;
    }
    public void setName(String name) {
        this.name = name;
    }
    public String getSf_account_id() {
        return sf_account_id;
    }
    public void setSf_account_id(String sf_account_id) {
        this.sf_account_id = sf_account_id;
    }
    public String getJira_group() {
        return jira_group;
    }
    public void setJira_group(String jira_group) {
        this.jira_group = jira_group;
    }
    public String getAccount_contact() {
        return account_contact;
    }
    public void setAccount_contact(String account_contact) {
        this.account_contact = account_contact;
    }
    public String getSf_account_name() {
        return sf_account_name;
    }
    public void setSf_account_name(String sf_account_name) {
        this.sf_account_name = sf_account_name;
    }
    public List<String> getSecondary_engs() {
        return secondary_engs;
    }
    public void setSecondary_engs(List<String> secondary_engs) {
        this.secondary_engs = secondary_engs;
    }
    public List<JiraGroup> getAssociated_jira_groups() {
        return associated_jira_groups;
    }
    public void setAssociated_jira_groups(List<JiraGroup> associated_jira_groups) {
        this.associated_jira_groups = associated_jira_groups;
    }
    public String getPrimary_eng() {
        return primary_eng;
    }
    public void setPrimary_eng(String primary_eng) {
        this.primary_eng = primary_eng;
    }
    public String get_id() {
        return _id;
    }
    public void set_id(String _id) {
        this._id = _id;
    }
    private String updated;
    private String name;
    private String sf_account_id;
    private String jira_group;
    private String account_contact;
    private String sf_account_name;
    private List<String> secondary_engs;
    private List<JiraGroup> associated_jira_groups;
    private String primary_eng;
    private String _id;
}
