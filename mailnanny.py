from errbot import BotPlugin, botcmd, arg_botcmd, webhook, ValidationException
from errbot.plugin_manager import PluginActivationException

from datetime import datetime, timedelta, timezone

try:
    import dateutil
    import dateutil.parser
except ImportError:
    log.exception("Could not start the mailnanny plugin")
    log.fatal(""" To use the mailnanny plugin you need to install python-dateutil:
    pip install python-dateutil
    """)
    sys.exit(-1)

def rfcmailtoaddresses(text):
    if not text:
        return text
    text = text.split(',')
    def remove_mail_from_name(address):
        if '<' in address:
            l = address.find('<')
            r = address.find('>')
            return address[l + 1:r]
        else:
            return address
    return [
        remove_mail_from_name(address)
        for address in text
    ]



class MailInfo(object):
    """Test class"""
    def __init__(self, content):
        content = self.parse_content(content)
        self.headers = content
        self.frm = rfcmailtoaddresses(content['From'])[0]
        self.reply_to = rfcmailtoaddresses(content.get('Reply-To', content['From']))[0]
        self.to = rfcmailtoaddresses(content['To'])
        self.cc = rfcmailtoaddresses(content.get('Cc'))
        self.subject = content['Subject']
        self.date = content['Date']
        self.replies = []
        self.parent = None

    def get_date(self):
        return dateutil.parser.parse(self.date)

    def parse_content(self, content):
        headers = []
        for line in content:
            line = line.rstrip().decode('utf-8')
            if not line:
                break
            elif line[0].isspace():
                headers[-1] = headers[-1] + "\n" + line
            else:
                headers.append(line)

        headers_dict = {}
        for header in headers:
            try:
                name, value = header.split(": ", 1)
            except:
                raise Exception("What is {} in {}".format(header, headers))
            headers_dict[name] = value

        return headers_dict

    def is_reply(self, other, monitored_emails):
        if other.frm in monitored_emails \
           and (self.frm in other.to or self.reply_to in other.to) \
           and self.subject in other.subject:
            return True
        else:
            return False

    def add_reply(self, other, monitored_emails):
        if not isinstance(other, MailInfo):
            other = MailInfo(other)
        if self.is_reply(other, monitored_emails):
            other.parent = self # TODO Oversimplification! Should go via the References/In-Reply-To headers
            self.replies.append(other)
            self.replies.sort(key=lambda m: m.get_date())
        else:
            raise Exception("Email {} is not a reply for {}".format(other, self))

    def __str__(self):
        return "<MailInfo from={frm} to={to} subj={subj}>".format(frm=self.frm, to=self.to, subj=self.subject)

    def pending_answer(self):
        if not self.replies:
            return True
        if self.replies[-1].frm == self.frm:
            # Last message is from OP
            return True
        else:
            # We assume that if the latest message is not from OP,
            # it's not pending an answer, from the bot POV. Later we
            # should add mechanisms to avoid messages from being
            # considered an answer.
            return False

    def should_remember(self, min_delta=timedelta(days=1)):
        if self.pending_answer() and self.last_message().get_date() + min_delta < datetime.now(tz=timezone.utc):
            return True
        else:
            return False

    def last_message(self):
        """Returns the last message in this conversation."""
        if self.replies:
            return self.replies[-1]
        else:
            return self


class Mailnanny(BotPlugin):
    """
    Know which emails haven&#39;t yet been replied to
    """

    def activate(self):
        """
        Triggers on plugin activation

        You should delete it if you're not using it to override any default behaviour
        """
        global dateutil
        super(Mailnanny, self).activate()
        if 'TOKENS' not in self:
            self['TOKENS'] = list()
        if 'mails' not in self:
            self['mails'] = list()

        try:
            import dateutil
            import dateutil.parser
        except ImportError:
            raise ValidationException("Cannot find python-dateutil in your modules. MailNanny needs dateutil.parser to parse the dates in the email headers")

    def deactivate(self):
        """
        Triggers on plugin deactivation

        You should delete it if you're not using it to override any default behaviour
        """
        super(Mailnanny, self).deactivate()

    def get_configuration_template(self):
        """
        Defines the configuration structure this plugin supports

        You should delete it if your plugin doesn't use any configuration like this
        """
        return {'incoming_addresses': ["info@gpul.org", "secretario@gpul.org", "secretaria@gpul.org"],
                'admin_token': None,
                'notify_stale': ['MYSELF']
               }

    def check_configuration(self, configuration):
        """
        Triggers when the configuration is checked, shortly before activation

        Raise a errbot.utils.ValidationException in case of an error

        You should delete it if you're not using it to override any default behaviour
        """
        super(Mailnanny, self).check_configuration(configuration)
        if 'incoming_addresses' not in configuration or type(configuration['incoming_addresses']) is not list:
            raise ValidationException("You need to configure a valid list as the incoming_addresses value")


    def callback_connect(self):
        """
        Triggers when bot is connected

        You should delete it if you're not using it to override any default behaviour
        """
        pass

    def callback_message(self, message):
        """
        Triggered for every received message that isn't coming from the bot itself

        You should delete it if you're not using it to override any default behaviour
        """
        pass

    def callback_botmessage(self, message):
        """
        Triggered for every message that comes from the bot itself

        You should delete it if you're not using it to override any default behaviour
        """
        pass

    @webhook("/admin/reload/plugin/<plugin_name>", raw=True)
    def reload_plugin_webook(self, request, plugin_name):
        self.check_authorized(request)
        try:
            self._bot.plugin_manager.reload_plugin_by_name(plugin_name)
            return "Plugin %s reloaded successfully" % plugin_name
        except PluginActivationException as pae:
            return "Error reactivating plugin %s: %s" % (plugin_name, pae)
    
    def check_authorized(self, request):
        from bottle import response, abort
        auth = request.get_header('Authorization', request.query.get('token', ''))
        if auth.lower().startswith('bearer '):
            auth = auth[len("bearer "):]

        if self.config and 'admin_token' in self.config and auth == self.config['admin_token']:
            self.log.warn("Somebody has used the DEBUG ADMIN TOKEN to log through the webhook {}".format(request.url))
        elif auth not in map(str, self['TOKENS']):
            self.log.info("We dont have {0} in tokens {1}".format(auth, self['TOKENS']))
            abort(403, "Forbidden")

    @webhook("/debug/last-mail", raw=True)
    def last_email(self, request):
        from bottle import response
        response.set_header('Content-Type', 'text/plain')
        self.check_authorized(request)
        return "{0}\n\n{1}".format(b"".join(self['LATEST_REQUEST']).decode('utf-8'), MailInfo(self['LATEST_REQUEST']))

    def on_stale_mail(self):
        def cb(mail):
            for receiver in self.config['notify_stale']:
                self.send(
                    self.build_identifier(receiver),
                    "Unanswered email warning.\n" +
                    "Subject: `{subj}`\n" +
                    "Originally from: `{frm}`" +
                    "Has {replies} replies, last was at {last}".format(
                        subj=mail.subject,
                        frm=mail.frm,
                        replies=len(mail.replies),
                        last=mail.last_message().date
                    )
                )
        return cb

    def on_non_stale_mail(self):
        def cb(mail):
            for receiver in self.config['notify_stale']:
                self.send(
                    self.build_identifier(receiver),
                    "Found not stale email.\n" +
                    "Pending answer: {n}\n" +
                    "Subject: `{subj}`\n" +
                    "Originally from: `{frm}`" +
                    "Has {replies} replies, last was at {last}".format(
                        n=mail.pending_answer(),
                        subj=mail.subject,
                        frm=mail.frm,
                        replies=len(mail.replies),
                        last=mail.last_message().date
                    )
                )
        return cb

    @staticmethod
    def check_mail_list(mails, stale_callback=None, non_stale_debug_callback=None):
        """This function forces a check on the mail list."""
        for mail in mails:
            if mail.should_remember():
                if callable(stale_callback):
                    stale_callback(mail)
            else:
                if callable(non_stale_debug_callback):
                    non_stale_debug_callback(mail)

        return mails

    def receive_mail(self, lines, address):
        """The non-hook version for easier testing.

        Assumes you're authorized. Don't ever call this function from
        non-validated call-sites or you will allow fake mails to be
        introducecd in the system.
        """
        self['LATEST_REQUEST'] = lines
        if lines:
            new = MailInfo(lines)
            mails = self['mails']
            is_reply = False
            for mail in mails:
                if mail.is_reply(new, self.config['incoming_addresses']):
                    mail.add_reply(new, self.config['incoming_addresses'])
                    is_reply = True
                    break

            if not is_reply:
                mails.append(new)
            # The shelve must be updated to refresh the object changes
            self['mails'] = mails
            self.alert_new_mail(new)

    def alert_new_mail(self, mail):
        for receiver in self.config['notify_stale']:
            self.send(
                self.build_identifier(receiver),
                ("You got mail.\n" +
                 "Is it a reply from a previous one? {n}\n" +
                 "Subject: `{subj}`\n" +
                 "Originally from: `{frm}`" +
                 "Has {replies} replies, last was at {last}").format(
                     n=mail.parent is not None,
                     subj=mail.subject,
                     frm=mail.frm,
                     replies=len(mail.replies),
                     last=mail.last_message().date
                 )
            )

          
    @webhook("/receive-mail-to/<address>", raw=True)
    def receive_mail_hook(self, request, address):
        """A webhook which simply returns 'Example'"""
        from bottle import response
        self.check_authorized(request)

        content = request.body.readlines()

        self.receive_mail(content, address)

        response.set_header('X-Powered-By', 'GPULMailNannyBot 0.0.1dev1')
        response.set_header('Content-Type', 'application/json')
        return {"gotcha": address}

    @botcmd(admin_only=True)
    def generate_mail_token(self, message, args):
        """
        Generate a token for sending to the incoming mail webook
        """
        import uuid
        token = str(uuid.uuid4())
        self['TOKENS'] = self['TOKENS'] + [token]
        return "Your new token is `{}`".format(token)

    @botcmd(admin_only=True)
    def get_mail_tokens(self, message, args):
        """Get all stored message tokens (this function should be disabled in prod.)"""
        return str.join("\n", [ "- `{0}`".format(str(token)) for token in self['TOKENS'] ])

    @botcmd(admin_only=True)
    def clear_mail_tokens(self, message, args):
        """Clear all previous tokens for webhooks"""
        self['TOKENS'] = list()

    @botcmd(admin_only=True)
    def mail_forget_all(self, message, args):
        """Forgets all emails so far. Please keep a backup before"""
        self['mails'] = list()
        return "Cleared all mails. I don't remember anything now."

    # Passing split_args_with=None will cause arguments to be split on any kind
    # of whitespace, just like Python's split() does
    @botcmd(split_args_with=None)
    def example(self, message, args):
        """A command which simply returns 'Example'"""
        return "Example"

    @arg_botcmd('name', type=str)
    @arg_botcmd('--favorite-number', type=int, unpack_args=False)
    def hello(self, message, args):
        """
        A command which says hello to someone.

        If you include --favorite-number, it will also tell you their
        favorite number.
        """
        if args.favorite_number is None:
            return "Hello {name}".format(name=args.name)
        else:
            return "Hello {name}, I hear your favorite number is {number}".format(
                name=args.name,
                number=args.favorite_number,
            )
