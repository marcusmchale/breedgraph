import aiosmtplib.errors

from breedgraph.adapters.aiosmtp.notifications import _failure


def test_failures_are_logged_without_addresses():
    refused = aiosmtplib.errors.SMTPRecipientRefused(550, 'No such user: someone@example.org', 'someone@example.org')
    for error in (refused, aiosmtplib.errors.SMTPRecipientsRefused([refused])):
        assert 'someone@example.org' not in _failure(error)
    assert _failure(refused) == "Failed to send email: SMTPRecipientRefused (SMTP 550)"
    assert _failure(ConnectionRefusedError('refused')) == "Failed to send email: ConnectionRefusedError"
