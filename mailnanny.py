from errbot import BotPlugin, botcmd, arg_botcmd, webhook, ValidationException
from errbot.plugin_manager import PluginActivationException

from datetime import datetime

class MailInfo(object):
    """Test class"""
    def __init__(self, content, monitored_emails, log):
        content = self.parse_content(content)
        self.headers = content
        self.frm = content['From']
        self.reply_to = content.get('Reply-To', content['From'])
        self.to = content['To']
        self.cc = content.get('Cc')
        self.subject = content['Subject']
        self.dateknown = datetime.now()
        self.monitored_emails = monitored_emails
        self.log = log

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
                name, value = header.split(": ")
            except:
                raise Exception("What is {} in {}".format(header, headers))
            headers_dict[name] = value

        return headers_dict

    def is_op(self):
        """Check whether this mail is an OP"""
        if self.to == "monitored_emails" and self.subject[:3].upper() == ("RE:"):
            return True
        else:
            return False

    def is_reply(other):
        if other.frm in self.monitored_emails \
            and (other.to == self.frm or other.to == self.reply_to) \
            and self.subject in other.subject:
            return True
        else:
            return False



class Mailnanny(BotPlugin):
    """
    Know which emails haven&#39;t yet been replied to
    """

    def activate(self):
        """
        Triggers on plugin activation

        You should delete it if you're not using it to override any default behaviour
        """
        super(Mailnanny, self).activate()
        if 'TOKENS' not in self:
            self['TOKENS'] = list()
        if 'mails' not in self:
            self['mails'] = list()

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
                'admin_token': None
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

        if auth not in map(str, self['TOKENS']):
            self.log.info("We dont have {0} in tokens {1}".format(auth, self['TOKENS']))
            abort(403, "Forbidden")

    @webhook("/debug/last-mail", raw=True)
    def last_email(self, request):
        from bottle import response
        response.set_header('Content-Type', 'text/plain')
        self.check_authorized(request)
        return "{0}\n\n{1}".format(b"".join(self['LATEST_REQUEST']).decode('utf-8'), MailInfo(self['LATEST_REQUEST'], self.config['incoming_addresses'], self.log))

    def check_mail_list(self):
        """This function forces a check on the mail list."""
        mails = self['mails']
        mails = [ MailInfo(content, self.config['incoming_addresses'], self.log) for content in mails]

        return None
          
    @webhook("/receive-mail-to/<address>", raw=True)
    def example_webhook(self, request, address):
        """A webhook which simply returns 'Example'"""
        from bottle import response
        self.check_authorized(request)

        content = request.body.readlines()
        self['LATEST_REQUEST'] = content

        if content:
            self['mails'] = self['mails'] + [content]
            self.check_mail_list()

        response.set_header('X-Powered-By', 'GPULMailReminderBot 0.0.1dev1')
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