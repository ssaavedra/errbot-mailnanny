Errbot MailNanny
================

This is a plugin for Errbot and it is in a very early state.

The idea is that this bot will nag you for emails that it knows that
have been left unanswered.


Usage
=====

You need a way to provide the bot with emails. The bot exposes a
webhook at
`https://your.bot.domain.example/receive-mail-to/your@domain.tld`.

Currently it does not use the address in the bar for anything but that
should change in the short time. 

Idea: We should implement `self['mails']` as a dict of lists instead
of a list directly to support such change. Should be easy to implement.


The easiest way if you have access to a Sieve-capable server, such as
Dovecot, you should configure a Sieve file like this:

```
require [ "vnd.dovecot.pipe", "copy", "variables" ];

pipe "send-to-errbot" ["no parameters needed"];
```

Make sure to send only those emails you want to be nagged about. You
can fulfill that by producing a more complex sieve of your creation.

You will also have to provide a meaningful send-to-errbot script:

```bash
#!/bin/bash

token=your-token-from-bot

curl -H "Authorization: Bearer $token" --data-binary @- "https://your.bot.domain.example/receive-mail-to/your@domain.tld"
```

In order to get a token, invite your bot and use
`!generate_mail_token` to get one. You must be a bot admin in order to
receive a token.

You will need a token in order to use the webhook API for every API
call.
