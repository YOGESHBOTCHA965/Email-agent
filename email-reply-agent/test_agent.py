import os
import unittest
from dataclasses import replace
from agent import Incoming, Reply, ai_ready, deliver, generate, parse_email, validate_options

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.reply = Reply('me@example.com', 'alex@example.com', 'Re: Meeting', 'Hello', '<source@example.com>')
        self.sent = []
    def test_unapproved_blocked(self):
        with self.assertRaises(PermissionError): deliver(self.reply, None, self.sent.append)
        self.assertEqual(self.sent, [])
    def test_changed_body_or_recipient_blocked(self):
        for changed in (replace(self.reply, body='Changed'), replace(self.reply, recipient='other@example.com')):
            with self.assertRaises(PermissionError): deliver(changed, self.reply.digest(), self.sent.append)
        self.assertEqual(self.sent, [])
    def test_approved_exact_reply(self):
        deliver(self.reply, self.reply.digest(), self.sent.append)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]['To'], self.reply.recipient)
        self.assertEqual(self.sent[0].get_content().strip(), self.reply.body)
        self.assertEqual(self.sent[0]['In-Reply-To'], self.reply.in_reply_to)
    def test_invalid_model_output(self):
        with self.assertRaises(ValueError): validate_options({'options': []})
    def test_reply_to_used(self):
        mail = parse_email(b'From: a@example.com\nReply-To: b@example.com\nSubject: Hi\nContent-Type: text/plain\n\nHello')
        self.assertEqual(mail.sender, 'b@example.com')
    def test_header_injection_blocked(self):
        changed = replace(self.reply, recipient='a@example.com\nBcc: b@example.com')
        with self.assertRaises(ValueError): deliver(changed, changed.digest(), self.sent.append)
        self.assertEqual(self.sent, [])
    def test_reply_uses_display_name(self):
        mail = parse_email(b'From: Alex <alex@example.com>\nSubject: Hi\nContent-Type: text/plain\n\nHello')
        self.assertEqual(mail.sender, 'alex@example.com')
        self.assertEqual(mail.sender_name, 'Alex')
    def test_missing_key_uses_local_drafts(self):
        previous = os.environ.get('OPENAI_API_KEY')
        os.environ['OPENAI_API_KEY'] = 'sk-...'
        try:
            self.assertFalse(ai_ready())
            mail = Incoming('alex@example.com', 'Meeting next week', 'Can you meet?', sender_name='Alex')
            options = generate(mail, 'Tuesday at 2 PM works for me.', 'I will bring the notes')
        finally:
            if previous is None:
                os.environ.pop('OPENAI_API_KEY', None)
            else:
                os.environ['OPENAI_API_KEY'] = previous
        self.assertEqual(len(options), 3)
        self.assertIn('Tuesday at 2 PM works for me.', options[0]['body'])
        self.assertIn('I will bring the notes.', options[1]['body'])
        self.assertTrue(options[0]['body'].startswith('Hi Alex,'))

if __name__ == '__main__': unittest.main()
