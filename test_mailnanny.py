
from datetime import datetime, timedelta, timezone

def emailize(address):
    if '<' not in address:
        return "Somebody <{}>".format(address)
    else:
        return address

def generate_email(frm, to, subj, body, date):
    mail = """Return-Path: <srs0=nsvm=fr=mail.labs.gpul.org=errbot@labs.gpul.org>
Delivered-To: errbot@mail.labs.gpul.org
Received: from gpulon.gpul.org
	by gpulon.gpul.org with LMTP id 1
	for <errbot@mail.labs.gpul.org>; Fri, 23 Feb 2018 19:41:59 +0000
Received: from localhost (localhost [127.0.0.1])
	by gpulon.gpul.org (Postfix) with ESMTP id 1
	for <errbot@mail.labs.gpul.org>; Fri, 23 Feb 2018 19:41:59 +0000 (UTC)
Subject: {subject}
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/simple; d=mail.labs.gpul.org;
	s=mail; t=1519414918;
	bh=FP24jOH15PEKi8LtgBXlcx185Z9EQ6Bv0MH2KiqUCWc=;
	h=Subject:To:References:From:In-Reply-To;
	b=EdHneV0xK2dh4eyu22SNdlf3Iz/eTCgepDlyrdwDLSXXH5hmVX0I3ZKg9qcOyaGFT
	 xqRQ/bonjAgST0cua8rQtLRihCzrshbY8LaSCzh3BTR0dDGKt4DduO4rA0CBGk+l0x
	 idXuu+iVTY/1JDt72qsFnvc3CWJxrhb8pp0wsLw+36rfQQCbCiUdgHNoSClTwLcZyE
	 QgrRCg/58pfU80VHhny1pFfUHg+fPQbAh19tY9pNLySm/AoEj74mlnRIosscvv5LE+
	 Xw+jciSop9YeC+4YHwWRwpMNNjBZUSbUZPW1/lJUT6L8+AJ4m38q7OSbMBVR2T/ZfG
	 PxUrWgxZN5n4Q==
To: {to}
From: {frm}
Message-ID: <nonuniqueid@mail.labs.gpul.org>
Date: {date}
Mime-Version: 1.0
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit
Content-Language: en-US

{body}
""".format(
    to=emailize(to),
    frm=emailize(frm),
    subject=subj,
    date=date.strftime("%a, %d %b %Y %H:%M:%S %z"),
    body=body
)
    mail = mail.split("\n")
    return [line.encode('utf-8') + b"\r\n" for line in mail]
    


pytest_plugins = ["errbot.backends.test"]

extra_plugin_dir = '.'

def test_generate_one_mail_alone(testbot):
    plugin = testbot._bot.plugin_manager.get_plugin_obj_by_name('MailNanny')
    plugin.config = {
        'incoming_addresses': ["info@gpul.org"],
        'admin_token': "debug",
        'notify_stale': ['MYSELF']
    }
    lines = generate_email("foo@bar.com", "info@gpul.org", "Problem with stuff", "I have problem. Cheers.", datetime.now() - timedelta(days=30))
    plugin.receive_mail(lines, "info@gpul.org")
    assert 'You got mail.\nIs it a reply' in testbot.pop_message()

def test_generate_one_mail_alone_stale():
    from mailnanny import MailInfo, Mailnanny

    stale = []

    mail_list = [
        MailInfo(
            generate_email(
                "foo@abr.com",
                "info@gpul.org",
                "Problem with stuff",
                "I have problem. Cheers.",
                datetime.now(tz=timezone.utc) - timedelta(days=30)
            )
        ),
    ]

    Mailnanny.check_mail_list(mail_list, stale.append)

    assert len(stale) == 1
    
def test_generate_one_mail_with_answer():
    from mailnanny import MailInfo, Mailnanny

    stale = []

    mail = MailInfo(generate_email(
        "foo@bar.com",
        "info@gpul.org",
        "Problem with stuff",
        "I have problem. Cheers.",
        datetime.now(tz=timezone.utc) - timedelta(days=30)
    ))

    reply = MailInfo(generate_email(
        "info@gpul.org",
        "Orig <foo@bar.com>, GPUL <info@gpul.org>",
        "RE: Problem with stuff",
        "I have problem. Cheers.",
        datetime.now(tz=timezone.utc) - timedelta(days=29)
    ))

    mail.add_reply(reply, ["info@gpul.org"])

    assert mail.replies[-1] == reply
    assert reply.frm != mail.frm
    assert not mail.pending_answer()

    Mailnanny.check_mail_list([mail], stale.append)

    assert len(stale) == 0
    


if __name__ == "__main__":
    main()
