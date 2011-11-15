$(function() {
    // Fix jQuery UI's autocomplete to allow multiple items in the list, comma-delimited
    // From http://www.codenition.com/jquery-ui-autocomplete-with-multiple-selections
    (function($){
        $.fn.multicomplete = function(opt) {
            var $t = $(this);
            // When menu item is selected and TAB is pressed, focus should remain on current element to allow adding more values
            $t.bind('keydown', function(e) {
                if ($t.data('autocomplete').menu.active && e.keyCode == $.ui.keyCode.TAB) {
                    e.preventDefault();
                }
            });

            // Call autocomplete() with our modified select/focus callbacks
            $t.autocomplete($.extend(opt,{
                // When a selection is made, replace everything after the last "," with the selection instead of replacing everything
                select: function(event,ui) {
                    this.value = this.value.replace(/[^,]+$/,(this.value.indexOf(',') != -1 ?' ':'')+ui.item.value + ', ');
                    return false;
                },
                // Disable replacing value on focus
                focus: function(){return false;}
            }));

            // Get the "source" callback that jQuery-UI prepared
            var $source = $t.data('autocomplete').source;

            // Modify the source callback to change request.term to everything after the last ",", than delegate to $source
            $t.autocomplete('option', 'source', function(request, response) {
                request.term = request.term.match(/\s*([^,]*)\s*$/)[1]; // get everything after the last "," and trim it
                $source(request, response);
            });
        };
    })(jQuery);

    /** Let the user test assignment rules and see which commits their pattern would match **/
    var TestResult = Backbone.Model.extend();

    var TestResultList = Backbone.Collection.extend({
        model: TestResult,

        url: function() {
            return '/codeReview/patternTest/' + this.branch_name + '/' + this.stop_tag + '/' + encodeURIComponent(this.pattern);
        },

        initialize: function(models, options) {
            this.branch_name = options.branch_name;
            this.stop_tag = options.stop_tag;
            this.pattern = options.pattern;
        }
    });

    var TestResultsView = Backbone.View.extend({
        tagName: 'div',

        initialize: function(options) {
            this.el = $(this.el);
            this.testResultList = options.testResultList;
            this.testResultList.bind('reset', this.render, this);
            this.template = _.template($('#test-results-template').html());
        },

        render: function(testResultList, options) {
            // Sort of a HACK: if we're rendering because testResultList.fetch() has completed,
            // then testResultList is non-null
            this.el.html(this.template({
                testResultList: testResultList,
                fetchComplete: (typeof testResultList !== 'undefined')
            }));

            return this;
        }
    });

    /** Let the user edit, create, and delete assignment rules **/
    var AssignmentRule = Backbone.Model.extend({
        defaults: {
            pattern: '',
            assignees: []
        },

        initialize: function() {
            if ( ! this.get('created_timestamp')) {
                this.set({
                    created_timestamp: new Date().getTime()
                })
            }
        }
    });

    var AssignmentRuleList = Backbone.Collection.extend({
        model: AssignmentRule,
        url: '/codeReview/rules',
        comparator: function(rule) {
            return rule.get('created_timestamp');
        }
    });

    var _AssignerView = Backbone.View.extend({
        // The current assignees the user has entered into the form
        formAssignees: function() {
            return _.filter(
                this.el.find('input[name="assignees"]').val().split(/\W+/),
                _.identity // filter out empty strings
            );
        }
    });

    var AssignmentRuleView = _AssignerView.extend({
        tagName: 'tr',
        className: 'rule',

        events: {
            'keypress input': 'keypress',
            'click button.test': 'test',
            'click button.save': 'submit',
            'click button.remove': 'remove'
        },

        initialize: function(options) {
            this.el = $(this.el);
            this.rule = options.rule;
            this.rule.bind('change', this.render, this);
            this.template = _.template($('#rule-template').html());
        },

        render: function() {
            this.el.html(this.template({
                rule: this.rule,
                releaseList: controller.releaseList
            }));
            return this;
        },

        // The current pattern the user has entered into the form
        formPattern: function() {
            return this.el.find('input[name="pattern"]').val();
        },

        keypress: function(e) {
            if (e.keyCode === 13) {
                // Enter key
                this.test();
            } else {
                // A key has been pressed, but the fields' values haven't actually
                // updated yet -- wait for them to be updated, then see if we
                // should enable the 'save' button

                setTimeout(_.bind(function() {
                    var $saveButton = this.el.find('button.save'),
                        pattern = this.formPattern(),
                        assignees = this.formAssignees(),
                        saveable = pattern && assignees && (
                            ! _.isEqual(assignees, this.rule.get('assignees'))
                            || ! _.isEqual(pattern, this.rule.get('pattern'))
                        );

                    $saveButton.attr('disabled', ! saveable);
                }, this), 0);
            }
        },

        test: function() {
            var branch_name = this.el.find('select[name="release"]').val(),
                stop_tag = controller.releaseList.detect(
                    function(release) { return release.get('branch_name') === branch_name; }
                ).get('stop_tag'),
                pattern = this.el.find('input[name="pattern"]').val(),
                testResultList = new TestResultList([], {
                    branch_name: branch_name,
                    stop_tag: stop_tag,
                    pattern: pattern
                }),
                testResultsView = new TestResultsView({
                    testResultList: testResultList
                }).render();

            // dialog() from jQuery UI
            testResultsView.el.dialog({
                width: 750,
                position: ['center', 100],
                title: 'Commits matching /' + pattern + '/ in branch ' + branch_name
            });
            testResultList.fetch();
        },

        submit: function() {
            var pattern = this.formPattern(),
                assignees = this.formAssignees(),
                oldAttrs = _.clone(this.rule.attributes);

            if (pattern && assignees[0]) {
                this.rule.save({
                    pattern: pattern,
                    assignees: assignees
                }, {
                    error: _.bind(function(rule, xhr) {
                        alert(xhr.responseText);
                        this.rule.set(oldAttrs);
                    }, this)
                });
            }
        },

        remove: function() {
            var outcome = confirm("Seriously?");
            if (outcome) {
                this.rule.destroy();
            }
        }
    });

    var AssignmentRulesView = Backbone.View.extend({
        events: {
            'click #new-rule': 'newRule'
        },

        initialize: function(options) {
            this.ruleList = options.ruleList;
            this.ruleList.bind('reset', _.bind(this.render, this));
            this.ruleList.bind('add', _.bind(this.render, this)); // TODO
            this.ruleList.bind('destroy', _.bind(this.render, this)); // TODO
            this.template = _.template($('#rules-template').html());
        },

        render: function() {
            this.el.html(this.template({
                ruleList: this.ruleList
            }));

            var $tbody = this.el.find('tbody');
            this.ruleList.each(_.bind(function(rule) {
                $tbody.append(new AssignmentRuleView({
                    rule: rule
                }).render().el);
            }, this));

            return this;
        },

        newRule: function() {
            this.ruleList.add();
            return false;
        }
    });

    /** Keep a static list of upcoming releases: which branches they're on and the tag-name of the
     *  last stable release **/
    var Release = Backbone.Model.extend();

    var ReleaseList = Backbone.Collection.extend({
        model: Release,

        // release is a Release model instance
        setCurrentRelease: function(release) {
            this.current_release = release;
            this.trigger('change:current_release', this.current_release);
        },

        setCurrentReleaseByBranchName: function(branch_name) {
            this.setCurrentRelease(
                this.find(function (release) {
                    return release.get('branch_name') === branch_name;
                })
            );
        }
    });

    var ReleasesView = Backbone.View.extend({
        events: {
            'click a': 'click'
        },

        initialize: function(options) {
            this.releaseList = options.releaseList;
            this.template = _.template($('#releases-template').html());
        },

        render: function() {
            var args = {
                releaseList: this.releaseList,
                current_release: this.current_release
            };

            this.el.html(this.template(args));
            return this;
        },

        // Click on a link that has a branch name, like '#v1.8'
        click: function(e) {
            var hash = $(e.target).attr('href');
            if (hash[0] == '#') {
                hash = hash.slice(1);
            }

            this.releaseList.setCurrentReleaseByBranchName(hash);

            return false;
        }
    });

    /** Show a list of commits that will go in to the next release **/
    var Commit = Backbone.Model.extend({
        url: function() {
            return '/codeReview/commit/' + this.get('hexsha')
        },

        defaults: {
            assigned_to: [],
            accepted_by: [],
            rejected_by: []
        },
        
        accepters: function() {
            var accepted_by = (this.get('accepted_by') || []).slice(0);
            if (this.get('user_accepted')) accepted_by.push(controller.user);
            return accepted_by;
        },
        
        rejecters: function() {
            var rejected_by = (this.get('rejected_by') || []).slice(0);
            if (this.get('user_rejected')) rejected_by.push(controller.user);
            return rejected_by;
        },
        
        state: function() {
            var assigned_to = this.get('assigned_to') || [],
                accepted_by = this.accepters(),
                rejected_by = this.rejecters();

            // If all assignees have accepted this commit, and at least 2 people have accepted, and no one rejected,
            // it's complete
            if(
                _.all(
                    assigned_to,
                    function(assignee) {
                        return _.any(
                            accepted_by,
                            function(accepter) {
                                return assignee == accepter;
                            }
                        );
                    }
                ) && accepted_by.length >= 2 && rejected_by.length === 0
            ) {
                return "complete";
            } else if (accepted_by.length > 0 || rejected_by.length > 0) {
                // At least one person has reviewed, but the commit is incomplete
                return "started";
            } else {
                // No one has reviewed
                return "new";
            }
        },
        
        section: function() {
            var state = this.state(),
                assigned_to_user = this.isAssignedTo(controller.user),
                user_has_reviewed = (this.get('user_accepted') || this.get('user_rejected'));

            if (state !== 'complete' && assigned_to_user && ! user_has_reviewed) {
                return { index: 0, name: 'For you to review' };
            } else if (state !== 'complete') {
                return { index: 1, name: 'Incomplete' };
            } else {
                return { index: 2, name: 'Complete' };
            }
        },
        
        isAssignedTo: function(user) {
            var assigned_to = this.get('assigned_to');
            return -1 !== assigned_to.indexOf(user);
        }
    });

    var CommitList = Backbone.Collection.extend({
        model: Commit,

        url: function() {
            return '/codeReview/commits/' + this.current_release.get('branch_name') + '/' + this.current_release.get('stop_tag');
        },

        // The list of commits is sorted by (incomplete and assigned to me,
        // incomplete, complete) and then by (older, newer) from top to bottom
        comparator: function(commit) {
            return '' + commit.section().index + commit.get('timestamp');
        },

        initialize: function() {
            this.current_release = null;
        }
    });

    var CommitView = _AssignerView.extend({
        tagName: 'li',
        className: 'commit',

        events: {
            'click .expander': 'expandMessage',
            'click .contractor': 'contractMessage',
            'click input[value="Reject"]': 'reject',
            'click input[value="Accept"]': 'accept',
            'submit form.assign': 'assign'
        },

        initialize: function(options) {
            this.el = $(this.el);
            this.commit = options.commit;
            this.commit.bind('change', this.render, this);

            this.template = _.template($('#commit-template').html());
        },

        render: function() {
            var user = controller.user,
                args = {
                    commit: this.commit,
                    state: this.commit.state(),
                    accepted_by: this.commit.accepters(),
                    rejected_by: this.commit.rejecters()
                };

            this.el.html(this.template(args));
            this.el.removeClass('new started complete').addClass(this.commit.state());
            // autocomplete() from jQuery UI, multicomplete() from the code at the top of this file
            this.el.find('input[name="assignees"]').multicomplete({
                source: controller.users,
                delay: 100
            });
            return this;
        },

        expandMessage: function() {
            this.el.find('.expander').hide();
            this.el.find('.message-remainder').fadeIn();
            return false;
        },

        contractMessage: function() {
            this.el.find('.message-remainder').fadeOut(_.bind(function() {
                this.el.find('.expander').show();
            }, this));
            return false;
        },

        reject: function() {
            this.commit.save({
                user_accepted: false,
                user_rejected: true
            }, {
                error: function(commit, xhr) {
                    commit.set({ user_rejected: false });
                    alert(xhr.responseText);
                }
            });
            return false;
        },

        accept: function() {
            this.commit.save({
                user_accepted: true,
                user_rejected: false
            }, {
                error: function(commit, xhr) {
                    commit.set({ user_accepted: false });
                    alert(xhr.responseText);
                }
            });
            return false;
        },

        assign: function() {
            var input = this.el.find('input[name="assignees"]'),
                users = this.formAssignees(),
                oldUsers = this.commit.get('assigned_to');

            if (users) {
                this.commit.save({
                    assigned_to: _.union(this.commit.get('assigned_to'), users)
                }, {
                    error: function(commit, xhr) {
                        commit.set({ assigned_to: oldUsers });
                        alert(xhr.responseText);
                    },
                    success: function() {
                        input.val('');
                    }
                });
            }
            return false;
        }
    });

    var CommitsView = Backbone.View.extend({
        events: {
            'change #show-complete': 'toggleShowComplete'
        },

        initialize: function(options) {
            this.commitList = options.commitList;
            this.commitList.bind('reset', this.render, this);
            this.template = _.template($('#commits-template').html());
            this.showComplete = false;
        },

        switchBranch: function(release) {
            this.commitList.current_release = release;
            this.commitList.reset([]);
            this.commitList.fetch({
                error: function(commitList, xhr) {
                    alert('Error loading commits: ' + xhr.responseText);
                }
            });
        },

        render: function() {
            this.el.html('');

            if ( ! this.commitList.length) {
                this.el.append('<img width="16px" height="16px" src="static/ajax-loader.gif"> Loading commits...');
            } else {
                this.el.html(this.template({
                    commitList: this.commitList,
                    showComplete: this.showComplete
                }));

                var $ol = this.el.find('ol'),
                    section;

                this.commitList.each(_.bind(function(commit) {
                    var newSection = commit.section().name;
                    if (newSection !== 'Complete' || this.showComplete) {
                        if (newSection !== section) {
                            var $sectionHeader = $('<li class="section-header">' + newSection + '</li>');
                            if (newSection === 'Complete') {
                                $sectionHeader.attr('id', 'complete-header');
                            }

                            $ol.append($sectionHeader);

                            section = newSection;
                        }

                        $ol.append((new CommitView({
                            commit: commit
                        })).render().el);
                    }
                }, this));
            }

            return this;
        },

        toggleShowComplete: function() {
            this.showComplete = ! this.showComplete;
            this.render();
            if (this.showComplete) {
                $.scrollTo('#complete-header', 500);
            }
        }
    });

    CodeReviewAppController = function() { };

    _.extend(CodeReviewAppController.prototype, Backbone.Events, {
        // param user: The logged-in user
        // param users: All the users in the engineering group
        init: function(user, users) {
            ///// DATA /////
            this.user = user;
            this.users = users;

            // TODO: verify these
            var releaseList = this.releaseList = new ReleaseList([
                new Release({ branch_name: 'v1.8', stop_tag: 'r1.8.4' }),
                new Release({ branch_name: 'v2.0', stop_tag: 'r2.0.1' })
                // TODO: Eliot thinks there's a 2.1.0 in the making?
                // new Release({ branch_name: 'v2.1.0', stop_tag: 'r2.0.0-rc1' })
            ]);

            this.ruleList = new AssignmentRuleList;
            this.commitList = new CommitList();

            ///// VIEWS /////
            this.rulesView = new AssignmentRulesView({
                ruleList: this.ruleList,
                el: $('#rules')
            });

            this.releasesView = new ReleasesView({
                releaseList: releaseList,
                el: $('#releases')
            }).render();

            this.commitsView = new CommitsView({
                commitList: this.commitList,
                el: $('#commits')
            }).render();

            ///// EVENTS /////
            releaseList.bind(
                'reset',
                this.rulesView.render,
                this.rulesView
            );

            releaseList.bind(
                'change:current_release',
                this.commitsView.switchBranch,
                this.commitsView
            );

            var $rules_button = $('#rules-button'), $rules_arrow = $('#rules-arrow');
            $rules_button.click(_.bind(function() {
                if ($rules_button.hasClass('primary')) {
                    this.rulesView.el.slideUp();
                    $rules_arrow.html('&darr;')
                    $rules_button.removeClass('primary');
                } else {
                    this.rulesView.el.slideDown();
                    $rules_arrow.html('&uarr;')
                    $rules_button.addClass('primary');
                }
            }, this));

            ///// INITIALIZE /////
            if (releaseList.length) {
                releaseList.setCurrentRelease(releaseList.at(releaseList.length-1));
            } else {
                releaseList.setCurrentRelease(null);
            }

            this.ruleList.fetch();
        }
    });

    window.controller = new CodeReviewAppController;
});
